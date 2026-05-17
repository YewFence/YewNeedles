#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import uuid
from dataclasses import dataclass


DEFAULT_HELPER_IMAGE = "volguard-volume-relabel:local"
TOOL_BACKUP_LABEL = "dev.volguard.tool"
SOURCE_VOLUME_LABEL = "dev.volguard.source-volume"


class DockerCommandError(RuntimeError):
    def __init__(self, command: list[str], returncode: int, stdout: str, stderr: str) -> None:
        self.command = command
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        rendered = " ".join(command)
        message = stderr.strip() or stdout.strip() or f"docker command failed with exit code {returncode}"
        super().__init__(f"{rendered}\n{message}")


@dataclass(frozen=True)
class VolumeSpec:
    name: str
    driver: str
    labels: dict[str, str]
    options: dict[str, str]
    scope: str


def log(message: str) -> None:
    print(message, flush=True)


def fail(message: str) -> None:
    raise SystemExit(message)


def ensure_docker() -> None:
    if shutil.which("docker") is None:
        fail("docker command not found inside the relabel helper image")


def parse_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default

    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    fail(f"{name} must be true or false")


def parse_label_lines(name: str) -> dict[str, str]:
    raw = os.environ.get(name, "")
    labels: dict[str, str] = {}

    for index, line in enumerate(raw.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        if "=" not in stripped:
            fail(f"{name} line {index} must use key=value")
        key, value = stripped.split("=", 1)
        key = key.strip()
        if not key:
            fail(f"{name} line {index} has an empty label key")
        labels[key] = value

    return labels


def parse_label_json(name: str) -> dict[str, str]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return {}

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{name} must be a JSON object") from exc

    if not isinstance(payload, dict):
        fail(f"{name} must be a JSON object")

    labels: dict[str, str] = {}
    for key, value in payload.items():
        text_key = str(key).strip()
        if not text_key:
            fail(f"{name} contains an empty label key")
        if isinstance(value, (dict, list)):
            fail(f"{name} label {text_key!r} must use a scalar value")
        labels[text_key] = "" if value is None else str(value)

    return labels


def parse_remove_lines(name: str) -> list[str]:
    raw = os.environ.get(name, "")
    keys: list[str] = []

    for index, line in enumerate(raw.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        if "=" in stripped:
            fail(f"{name} line {index} must contain a label key only")
        keys.append(stripped)

    return keys


def parse_remove_json(name: str) -> list[str]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return []

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{name} must be a JSON array") from exc

    if not isinstance(payload, list):
        fail(f"{name} must be a JSON array")

    keys: list[str] = []
    for item in payload:
        if isinstance(item, (dict, list)):
            fail(f"{name} must contain label keys only")
        key = str(item).strip()
        if not key:
            fail(f"{name} contains an empty label key")
        keys.append(key)

    return keys


def merge_label_maps(*sources: tuple[str, dict[str, str]]) -> dict[str, str]:
    merged: dict[str, str] = {}
    defined_by: dict[str, str] = {}

    for source_name, labels in sources:
        for key, value in labels.items():
            if key in merged and merged[key] != value:
                previous = defined_by[key]
                fail(f"label key {key!r} is defined with different values in {previous} and {source_name}")
            merged[key] = value
            defined_by[key] = source_name

    return merged


def merge_remove_lists(*sources: tuple[str, list[str]]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()

    for _, keys in sources:
        for key in keys:
            if key in seen:
                continue
            seen.add(key)
            merged.append(key)

    return merged


def docker(command: list[str], *, capture_output: bool = False, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["docker", *command],
        text=True,
        stdout=subprocess.PIPE if capture_output else None,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and completed.returncode != 0:
        raise DockerCommandError(["docker", *command], completed.returncode, completed.stdout or "", completed.stderr or "")
    return completed


def volume_exists(name: str) -> bool:
    result = docker(["volume", "inspect", name], capture_output=True, check=False)
    return result.returncode == 0


def inspect_volume(name: str) -> VolumeSpec:
    result = docker(["volume", "inspect", name], capture_output=True)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"failed to parse docker volume inspect output for {name}") from exc

    if not payload:
        fail(f"docker volume not found: {name}")

    raw = payload[0]
    labels = raw.get("Labels") or {}
    options = raw.get("Options") or {}
    return VolumeSpec(
        name=raw["Name"],
        driver=raw["Driver"],
        labels={str(key): str(value) for key, value in labels.items()},
        options={str(key): str(value) for key, value in options.items()},
        scope=str(raw.get("Scope") or ""),
    )


def containers_using_volume(name: str) -> list[str]:
    result = docker(
        [
            "ps",
            "-a",
            "--filter",
            f"volume={name}",
            "--format",
            "{{.ID}}\t{{.Names}}\t{{.Status}}",
        ],
        capture_output=True,
    )
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return lines


def compute_new_labels(
    original: dict[str, str],
    *,
    clear_existing: bool,
    set_labels: dict[str, str],
    remove_labels: list[str],
) -> dict[str, str]:
    overlap = sorted(set(set_labels) & set(remove_labels))
    if overlap:
        fail(f"same label key cannot be set and removed together: {', '.join(overlap)}")

    updated = {} if clear_existing else dict(original)
    updated.update(set_labels)
    for key in remove_labels:
        updated.pop(key, None)
    return updated


def choose_backup_volume_name(original_name: str) -> str:
    configured = os.environ.get("BACKUP_VOLUME_NAME", "").strip()
    if configured:
        return configured
    suffix = uuid.uuid4().hex[:12]
    return f"volguard-volume-relabel-backup-{suffix}"


def create_backup_volume(name: str, source_volume_name: str) -> None:
    command = [
        "volume",
        "create",
        "--label",
        f"{TOOL_BACKUP_LABEL}=volume-relabel-backup",
        "--label",
        f"{SOURCE_VOLUME_LABEL}={source_volume_name}",
        name,
    ]
    docker(command)


def create_volume(spec: VolumeSpec, labels: dict[str, str]) -> None:
    command = ["volume", "create", "--driver", spec.driver]
    for key, value in sorted(spec.options.items()):
        command.extend(["--opt", f"{key}={value}"])
    for key, value in sorted(labels.items()):
        command.extend(["--label", f"{key}={value}"])
    command.append(spec.name)
    docker(command)


def remove_volume(name: str) -> None:
    docker(["volume", "rm", name])


def copy_volume_data(source_volume: str, target_volume: str, helper_image: str) -> None:
    docker(
        [
            "run",
            "--rm",
            "--pull",
            "never",
            "--entrypoint",
            "rsync",
            "-v",
            f"{source_volume}:/source:ro",
            "-v",
            f"{target_volume}:/target",
            helper_image,
            "-aH",
            "--numeric-ids",
            "/source/",
            "/target/",
        ]
    )


def remove_volume_if_exists(name: str) -> None:
    if volume_exists(name):
        remove_volume(name)


def rollback_original_volume(spec: VolumeSpec, backup_volume: str, helper_image: str) -> None:
    remove_volume_if_exists(spec.name)
    create_volume(spec, spec.labels)
    copy_volume_data(backup_volume, spec.name, helper_image)


def cleanup_backup(backup_volume: str, keep_backup: bool) -> None:
    if keep_backup:
        log(f"kept backup volume {backup_volume}")
        return
    if volume_exists(backup_volume):
        remove_volume(backup_volume)


def main() -> int:
    ensure_docker()

    volume_name = os.environ.get("VOLUME_NAME", "").strip()
    if not volume_name:
        fail("set VOLUME_NAME")

    helper_image = os.environ.get("COPY_HELPER_IMAGE", DEFAULT_HELPER_IMAGE).strip() or DEFAULT_HELPER_IMAGE
    clear_existing = parse_bool("VOLUME_LABELS_CLEAR", default=False)
    keep_backup = parse_bool("KEEP_BACKUP_VOLUME", default=False)
    set_labels = merge_label_maps(
        ("VOLUME_LABELS_SET", parse_label_lines("VOLUME_LABELS_SET")),
        ("VOLUME_LABELS_SET_JSON", parse_label_json("VOLUME_LABELS_SET_JSON")),
    )
    remove_labels = merge_remove_lists(
        ("VOLUME_LABELS_REMOVE", parse_remove_lines("VOLUME_LABELS_REMOVE")),
        ("VOLUME_LABELS_REMOVE_JSON", parse_remove_json("VOLUME_LABELS_REMOVE_JSON")),
    )

    if not clear_existing and not set_labels and not remove_labels:
        fail("no label changes requested")

    backup_volume = choose_backup_volume_name(volume_name)
    if backup_volume == volume_name:
        fail("BACKUP_VOLUME_NAME must differ from VOLUME_NAME")
    if volume_exists(backup_volume):
        fail(f"backup volume already exists: {backup_volume}")

    original = inspect_volume(volume_name)
    if original.scope != "local":
        fail(f"only local-scope volumes are supported right now, got scope {original.scope!r}")

    updated_labels = compute_new_labels(
        original.labels,
        clear_existing=clear_existing,
        set_labels=set_labels,
        remove_labels=remove_labels,
    )
    if updated_labels == original.labels:
        log(f"volume {volume_name} already has the requested labels")
        return 0

    in_use = containers_using_volume(volume_name)
    if in_use:
        details = "\n".join(in_use)
        fail(f"volume {volume_name} is still attached to containers, detach them first\n{details}")

    log(f"creating backup volume {backup_volume}")
    create_backup_volume(backup_volume, volume_name)

    destructive_phase_started = False
    try:
        log(f"copying data from {volume_name} to backup volume {backup_volume}")
        copy_volume_data(volume_name, backup_volume, helper_image)

        log(f"removing original volume {volume_name}")
        remove_volume(volume_name)
        destructive_phase_started = True

        log(f"creating replacement volume {volume_name} with updated labels")
        create_volume(original, updated_labels)

        log(f"restoring data back into {volume_name}")
        copy_volume_data(backup_volume, volume_name, helper_image)
    except DockerCommandError as exc:
        if not destructive_phase_started:
            cleanup_backup(backup_volume, keep_backup=False)
            fail(f"relabel failed before replacing the original volume\n{exc}")

        try:
            log(f"relabel failed, rolling back original labels on {volume_name}")
            rollback_original_volume(original, backup_volume, helper_image)
        except DockerCommandError as rollback_exc:
            fail(
                "relabel failed after the original volume was removed and rollback also failed\n"
                f"backup volume kept at {backup_volume}\n"
                f"original error\n{exc}\n"
                f"rollback error\n{rollback_exc}"
            )

        fail(
            "relabel failed after the original volume was removed, but rollback restored the original volume\n"
            f"backup volume kept at {backup_volume}\n"
            f"{exc}"
        )

    cleanup_backup(backup_volume, keep_backup=keep_backup)
    log(f"updated labels for volume {volume_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
