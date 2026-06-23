#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


LIFECYCLE_KEYS = (
    "preinstall",
    "install",
    "postinstall",
    "prepare",
    "prepack",
    "postpack",
)

LOCAL_FILE_RE = re.compile(
    r"(?:^|\s)(?:node\s+|node\s+--[^\s]+\s+|bash\s+|sh\s+)?"
    r"(?P<path>(?:\./|\../|scripts/|bin/|dist/|lib/|src/)[^\s\"';&|]+)"
)


def run_capture(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def normalize_tool_spec(value: str) -> str:
    if value.startswith("npm:"):
        return value
    return f"npm:{value}"


def resolve_install_dir(tool_spec: str) -> Path:
    result = run_capture(["mise", "where", tool_spec])
    if result.returncode != 0:
        message = result.stderr.strip()
        raise SystemExit(f"Unable to resolve {tool_spec!r} with mise where.\n{message}")
    path = result.stdout.strip()
    if not path:
        raise SystemExit(f"mise where returned an empty path for {tool_spec!r}.")
    return Path(path)


def is_aube_project_dir(path: Path) -> bool:
    return (path / "package.json").is_file() and (path / "aube-lock.yaml").is_file()


def is_pnpm_project_dir(path: Path) -> bool:
    return (path / "package.json").is_file() and (path / "pnpm-lock.yaml").is_file()


def has_aube_state(path: Path) -> bool:
    return (
        (path / "node_modules" / ".aube-state").is_dir()
        or (path / "node_modules" / ".aube").is_dir()
    )


def has_pnpm_state(path: Path) -> bool:
    return (
        (path / "node_modules" / ".modules.yaml").is_file()
        or (path / ".pnpm").is_dir()
        or (path / "node_modules" / ".pnpm").is_dir()
    )


def child_dirs(path: Path) -> list[Path]:
    if not path.is_dir():
        return []
    return sorted((entry for entry in path.iterdir() if entry.is_dir()), key=lambda item: item.name)


def resolve_aube_project_dir(base: Path) -> Path | None:
    candidates: list[Path] = []
    seen: set[Path] = set()

    def append(path: Path) -> None:
        if is_aube_project_dir(path):
            resolved = path.resolve(strict=True)
            if resolved not in seen:
                seen.add(resolved)
                candidates.append(resolved)

    append(base)
    for entry in child_dirs(base):
        append(entry)
        if entry.name == "global-aube":
            for nested in child_dirs(entry):
                append(nested)

    if len(candidates) == 1:
        return candidates[0]

    stateful = [path for path in candidates if has_aube_state(path)]
    if len(stateful) == 1:
        return stateful[0]
    return None


def resolve_pnpm_project_dir(base: Path) -> Path | None:
    candidates: list[Path] = []
    seen: set[Path] = set()

    def append(path: Path) -> None:
        if is_pnpm_project_dir(path):
            resolved = path.resolve(strict=True)
            if resolved not in seen:
                seen.add(resolved)
                candidates.append(resolved)

    append(base)
    for entry in child_dirs(base):
        append(entry)

    if len(candidates) == 1:
        return candidates[0]

    stateful = [path for path in candidates if has_pnpm_state(path)]
    if len(stateful) == 1:
        return stateful[0]
    return None


def resolve_project_dir(base: Path, manager: str) -> tuple[str, Path]:
    if manager in ("auto", "aube"):
        project = resolve_aube_project_dir(base)
        if project is not None:
            return "aube", project
    if manager in ("auto", "pnpm"):
        project = resolve_pnpm_project_dir(base)
        if project is not None:
            return "pnpm", project
    raise SystemExit(f"Could not find a package manager project under {base}.")


def parse_package_name(build: str) -> str:
    build = build.strip()
    if build.startswith("@"):
        scope_and_name, _sep, _version = build.rpartition("@")
        return scope_and_name or build
    name, _sep, _version = build.partition("@")
    return name or build


def ignored_builds(manager: str, project_dir: Path) -> list[str]:
    command = [manager, "--dir", str(project_dir), "ignored-builds"]
    result = run_capture(command)
    if result.returncode != 0:
        message = result.stderr.strip()
        raise SystemExit(f"Failed to list ignored builds with {' '.join(command)}.\n{message}")

    packages: list[str] = []
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("The following "):
            continue
        if line.startswith("- "):
            line = line[2:].strip()
        if "@" not in line:
            continue
        packages.append(parse_package_name(line))
    return packages


def package_path(package: str) -> Path:
    if package.startswith("@"):
        scope, name = package.split("/", 1)
        return Path(scope) / name
    return Path(package)


def manifest_candidates(project_dir: Path, package: str) -> list[Path]:
    fragment = package_path(package)
    candidates = [
        project_dir / "node_modules" / fragment / "package.json",
        project_dir / "node_modules" / ".aube" / "node_modules" / fragment / "package.json",
        project_dir / "node_modules" / ".pnpm" / "node_modules" / fragment / "package.json",
        project_dir / ".pnpm" / "node_modules" / fragment / "package.json",
    ]

    found: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate.exists():
            resolved = candidate.resolve(strict=True)
            if resolved not in seen:
                seen.add(resolved)
                found.append(resolved)

    if found:
        return found

    expected_suffix = Path("node_modules") / fragment / "package.json"
    search_roots = [
        project_dir / "node_modules" / ".aube",
        project_dir / "node_modules" / ".pnpm",
        project_dir / ".pnpm",
        project_dir / "node_modules",
    ]
    for root in search_roots:
        if not root.is_dir():
            continue
        for manifest in root.rglob("package.json"):
            if manifest.parts[-len(expected_suffix.parts) :] != expected_suffix.parts:
                continue
            try:
                resolved = manifest.resolve(strict=True)
            except OSError:
                continue
            if resolved not in seen:
                seen.add(resolved)
                found.append(resolved)
    return found


def read_package_json(manifest: Path) -> dict[str, Any]:
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Failed to parse {manifest}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"{manifest} does not contain a JSON object.")
    return data


def referenced_files(package_dir: Path, command: str) -> list[str]:
    paths: list[str] = []
    seen: set[Path] = set()
    for match in LOCAL_FILE_RE.finditer(command):
        raw_path = match.group("path").rstrip(",)")
        candidate = (package_dir / raw_path).resolve()
        if candidate in seen:
            continue
        if candidate.exists():
            seen.add(candidate)
            paths.append(str(candidate))
    return paths


def package_report(project_dir: Path, package: str) -> dict[str, Any]:
    manifests = manifest_candidates(project_dir, package)
    if not manifests:
        return {"package": package, "found": False, "error": "package.json not found"}

    manifest = manifests[0]
    package_dir = manifest.parent
    data = read_package_json(manifest)
    scripts = data.get("scripts", {})
    if not isinstance(scripts, dict):
        scripts = {}

    lifecycle_scripts: dict[str, dict[str, Any]] = {}
    for key in LIFECYCLE_KEYS:
        value = scripts.get(key)
        if isinstance(value, str):
            lifecycle_scripts[key] = {
                "command": value,
                "referenced_files": referenced_files(package_dir, value),
            }

    return {
        "package": package,
        "found": True,
        "name": data.get("name"),
        "version": data.get("version"),
        "manifest": str(manifest),
        "package_dir": str(package_dir),
        "lifecycle_scripts": lifecycle_scripts,
    }


def print_text(report: dict[str, Any]) -> None:
    print(f"manager: {report['manager']}")
    print(f"project: {report['project_dir']}")
    print()

    for item in report["packages"]:
        print(item["package"])
        if not item["found"]:
            print(f"  error: {item['error']}")
            print()
            continue

        print(f"  package: {item.get('name')}@{item.get('version')}")
        print(f"  manifest: {item['manifest']}")
        print(f"  package dir: {item['package_dir']}")
        scripts = item["lifecycle_scripts"]
        if not scripts:
            print("  lifecycle scripts: none")
        for key, script in scripts.items():
            print(f"  {key}: {script['command']}")
            for referenced in script["referenced_files"]:
                print(f"    file: {referenced}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Locate npm lifecycle scripts skipped by pnpm or aube."
    )
    parser.add_argument(
        "target",
        help="mise npm tool spec, installed tool directory, or package manager project directory",
    )
    parser.add_argument(
        "--manager",
        choices=("auto", "aube", "pnpm"),
        default="auto",
        help="package manager project type",
    )
    parser.add_argument(
        "-p",
        "--package",
        action="append",
        dest="packages",
        help="package name to inspect; repeat to avoid calling ignored-builds",
    )
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args()

    target_path = Path(os.path.expanduser(args.target))
    if target_path.exists():
        base = target_path.resolve()
        tool_spec = None
    else:
        tool_spec = normalize_tool_spec(args.target)
        base = resolve_install_dir(tool_spec).resolve()

    manager, project_dir = resolve_project_dir(base, args.manager)
    packages = args.packages or ignored_builds(manager, project_dir)

    report = {
        "target": args.target,
        "tool_spec": tool_spec,
        "manager": manager,
        "project_dir": str(project_dir),
        "packages": [package_report(project_dir, package) for package in packages],
    }

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_text(report)


if __name__ == "__main__":
    main()
