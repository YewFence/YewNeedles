#!/usr/bin/env python3
#USAGE arg "<source>" help="已有宿主机目录或 Docker 命名卷"
#USAGE complete "source" run="./packages/mise-completions/volume-locations locations '{{words[CURRENT] | escape_xml}}'"
#USAGE arg "<target>" help="宿主机目录或 Docker 命名卷"
#USAGE complete "target" run="./packages/mise-completions/volume-locations locations '{{words[CURRENT] | escape_xml}}'"
#USAGE flag "--delete" help="删除目标中源不存在的文件"
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


PROJECT_NAME = "volguard-volume-copy"
UNUSED_SOURCE_VOLUME = "volguard-volume-copy-unused-source"
UNUSED_TARGET_VOLUME = "volguard-volume-copy-unused-target"
SCRIPT_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Mount:
    type: str
    source: str
    volume_name: str
    external: bool = False

    @property
    def identity(self) -> tuple[str, str]:
        if self.type == "bind":
            return ("bind", os.path.normcase(os.path.realpath(self.source)))

        return ("volume", self.volume_name)


def parse_args(argv: list[str]) -> argparse.Namespace:
    env_source = os.environ.get("usage_source")
    env_target = os.environ.get("usage_target")
    if not argv and env_source and env_target:
        return argparse.Namespace(
            source=env_source,
            target=env_target,
            delete=os.environ.get("usage_delete") == "true",
        )

    parser = argparse.ArgumentParser(
        prog="volume-copy",
        description="Copy data between Docker named volumes and host directories.",
    )
    parser.add_argument("source", help="Existing host directory or Docker volume.")
    parser.add_argument("target", help="Host directory or Docker volume.")
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete files from the target that do not exist in the source.",
    )

    return parser.parse_args(argv)


def fail(message: str) -> None:
    raise SystemExit(message)


def split_prefix(value: str) -> tuple[str | None, str]:
    for prefix, kind in (("path:", "path"), ("bind:", "path"), ("volume:", "volume")):
        if value.startswith(prefix):
            return kind, value[len(prefix) :]

    return None, value


def is_path_like(value: str) -> bool:
    if value in {".", "..", "~"}:
        return True

    if value.startswith(("./", "../", "/", "~/")):
        return True

    if "/" in value or "\\" in value:
        return True

    return bool(Path(value).anchor)


def existing_directory(value: str, label: str) -> Path:
    path = Path(value).expanduser()

    if not path.is_dir():
        fail(f"{label} must be an existing directory: {value}")

    return path.resolve()


def target_directory(value: str) -> Path:
    path = Path(value).expanduser()

    if path.exists() and not path.is_dir():
        fail(f"target path exists but is not a directory: {value}")

    return Path(os.path.abspath(path))


def ensure_docker() -> None:
    if shutil.which("docker") is None:
        fail("docker command not found")


def docker_volume_exists(name: str) -> bool:
    result = subprocess.run(
        ["docker", "volume", "inspect", name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def source_volume(name: str) -> Mount:
    if not name:
        fail("source volume name must not be empty")

    if not docker_volume_exists(name):
        fail(f"source is neither an existing directory nor an existing Docker volume: {name}")

    return Mount("volume", "source-volume", name, True)


def target_volume(name: str) -> Mount:
    if not name:
        fail("target volume name must not be empty")

    return Mount("volume", "target-volume", name, docker_volume_exists(name))


def source_path(value: str) -> Mount:
    return Mount("bind", str(existing_directory(value, "source path")), UNUSED_SOURCE_VOLUME)


def target_path(value: str) -> Mount:
    return Mount("bind", str(target_directory(value)), UNUSED_TARGET_VOLUME)


def resolve_source(value: str) -> Mount:
    kind, raw_value = split_prefix(value)

    if kind == "path":
        return source_path(raw_value)

    if kind == "volume":
        return source_volume(raw_value)

    if Path(raw_value).expanduser().is_dir():
        return source_path(raw_value)

    if is_path_like(raw_value):
        return source_path(raw_value)

    return source_volume(raw_value)


def resolve_target(value: str) -> Mount:
    kind, raw_value = split_prefix(value)

    if kind == "path":
        return target_path(raw_value)

    if kind == "volume":
        return target_volume(raw_value)

    path = Path(raw_value).expanduser()
    if path.exists():
        if not path.is_dir():
            fail(f"target path exists but is not a directory: {raw_value}")
        return target_path(raw_value)

    if is_path_like(raw_value):
        return target_path(raw_value)

    return target_volume(raw_value)


def run_copy(source: Mount, target: Mount, delete: bool) -> int:
    env = os.environ.copy()
    env.update(
        {
            "COPY_DELETE": "true" if delete else "false",
            "SOURCE_MOUNT_TYPE": source.type,
            "SOURCE_MOUNT_SOURCE": source.source,
            "SOURCE_VOLUME_NAME": source.volume_name,
            "SOURCE_VOLUME_EXTERNAL": "true" if source.external else "false",
            "TARGET_MOUNT_TYPE": target.type,
            "TARGET_MOUNT_SOURCE": target.source,
            "TARGET_VOLUME_NAME": target.volume_name,
            "TARGET_VOLUME_EXTERNAL": "true" if target.external else "false",
        }
    )

    command = [
        "docker",
        "compose",
        "-p",
        PROJECT_NAME,
        "-f",
        str(SCRIPT_DIR / "compose.yaml"),
        "run",
        "--rm",
        "--build",
        "copy",
    ]

    return subprocess.call(command, env=env)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    ensure_docker()

    source = resolve_source(args.source)
    target = resolve_target(args.target)

    if source.identity == target.identity:
        fail("source and target resolve to the same location")

    return run_copy(source, target, args.delete)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
