"""Command line interface for zsh-completions-sync."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any


PROJECT_CONFIG = ".zsh-completions-sync.toml"
PROJECT_CONFIG_DIR = ".config"
PROJECT_CONFIG_FILE = "zsh-completions-sync.toml"
USER_CONFIG_DIR = "zsh-completions-sync"
USER_CONFIG_FILE = "registry.toml"
USER_LEGACY_CONFIG_FILE = "zsh-completions-sync-registry.toml"
DEFAULT_REGISTRY = "registry.toml"


@dataclass(frozen=True)
class CompletionTool:
    name: str
    command: tuple[str, ...]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="zsh-completions-sync",
        description="Synchronize zsh completion scripts.",
    )
    subparsers = parser.add_subparsers(dest="scope", required=True)
    subparsers.add_parser("project", help="Generate project-local completions.")
    subparsers.add_parser("global", help="Generate global completions.")

    args = parser.parse_args(argv)
    scope = args.scope
    output_dir = default_output_dir(scope)

    registry = load_registry(Path.cwd())
    tools = parse_scope_tools(registry, scope)
    sync_tools(tools, output_dir)
    return 0


def default_output_dir(scope: str) -> Path:
    if scope == "project":
        return Path.cwd() / ".completions" / "zsh"
    if scope == "global":
        return Path.home() / ".zsh" / "completions"
    raise ValueError(f"unsupported scope: {scope}")


def load_registry(project_dir: Path) -> dict[str, Any]:
    registry = read_resource_toml(DEFAULT_REGISTRY)
    merge_mapping(registry, read_preferred_toml(user_config_paths()))
    merge_mapping(registry, read_preferred_toml(project_config_paths(project_dir)))
    return registry


def user_config_paths() -> tuple[Path, Path]:
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    config_home = Path(xdg_config_home).expanduser() if xdg_config_home else Path.home() / ".config"
    return (
        config_home / USER_CONFIG_DIR / USER_CONFIG_FILE,
        config_home / USER_LEGACY_CONFIG_FILE,
    )


def project_config_paths(project_dir: Path) -> tuple[Path, Path]:
    return (
        project_dir / PROJECT_CONFIG_DIR / PROJECT_CONFIG_FILE,
        project_dir / PROJECT_CONFIG,
    )


def read_preferred_toml(paths: tuple[Path, Path]) -> dict[str, Any]:
    preferred_path, fallback_path = paths
    preferred_exists = preferred_path.exists()
    fallback_exists = fallback_path.exists()

    if preferred_exists and fallback_exists:
        warn_duplicate_config(preferred_path, fallback_path)

    if preferred_exists:
        return read_toml(preferred_path)
    return read_toml(fallback_path)


def warn_duplicate_config(preferred_path: Path, ignored_path: Path) -> None:
    print(
        "warn: duplicate zsh-completions-sync registry config; "
        f"using {preferred_path} and ignoring {ignored_path}",
        file=sys.stderr,
    )


def read_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as file:
            data = tomllib.load(file)
    except FileNotFoundError:
        return {}

    if not isinstance(data, dict):
        return {}
    return data


def read_resource_toml(name: str) -> dict[str, Any]:
    text = resources.files("zsh_completions_sync").joinpath(name).read_text(encoding="utf-8")
    data = tomllib.loads(text)
    if not isinstance(data, dict):
        return {}
    return data


def clone_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    cloned: dict[str, Any] = {}
    for key, item in value.items():
        if isinstance(item, Mapping):
            cloned[key] = clone_mapping(item)
        else:
            cloned[key] = item
    return cloned


def merge_mapping(base: dict[str, Any], override: Mapping[str, Any]) -> None:
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(base.get(key), dict):
            merge_mapping(base[key], value)
        elif isinstance(value, Mapping):
            base[key] = clone_mapping(value)
        else:
            base[key] = value


def parse_scope_tools(registry: Mapping[str, Any], scope: str) -> list[CompletionTool]:
    scope_table = registry.get(scope, {})
    if not isinstance(scope_table, Mapping):
        return []

    tools: list[CompletionTool] = []
    for name, config in scope_table.items():
        if not isinstance(name, str) or not isinstance(config, Mapping):
            continue

        command = config.get("command")
        if is_command(command):
            tools.append(CompletionTool(name=name, command=tuple(command)))

    return tools


def is_command(value: object) -> bool:
    return (
        isinstance(value, list)
        and len(value) > 0
        and all(isinstance(item, str) and item for item in value)
    )


def sync_tools(tools: Sequence[CompletionTool], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for tool in tools:
        if shutil.which(tool.command[0]) is None:
            continue
        sync_tool(tool, output_dir)


def sync_tool(tool: CompletionTool, output_dir: Path) -> None:
    try:
        result = subprocess.run(
            tool.command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return

    if result.returncode != 0:
        return

    destination = output_dir / f"_{tool.name}"
    write_atomic(destination, result.stdout)


def write_atomic(destination: Path, content: bytes) -> None:
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as temp_file:
        temp_path = Path(temp_file.name)
        temp_file.write(content)

    try:
        temp_path.replace(destination)
    except OSError:
        temp_path.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    sys.exit(main())
