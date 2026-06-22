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

from zsh_completions_sync.sources import (
    CommandSource,
    CompletionSource,
    GitFileSource,
    HttpFileSource,
    LocalFileSource,
    format_command,
    parse_command,
    parse_source,
    read_source,
)


PROJECT_CONFIG = ".zsh-completions-sync.toml"
PROJECT_CONFIG_DIR = ".config"
PROJECT_CONFIG_FILE = "zsh-completions-sync.toml"
USER_CONFIG_DIR = "zsh-completions-sync"
USER_CONFIG_FILE = "registry.toml"
USER_LEGACY_CONFIG_FILE = "zsh-completions-sync-registry.toml"
DEFAULT_REGISTRY = "registry.toml"
SUPPORTED_SCOPES = frozenset({"global", "project"})


@dataclass(frozen=True)
class CompletionTool:
    name: str
    source: CompletionSource
    check: "CompletionCheck | None"


@dataclass(frozen=True)
class RegistryLayer:
    label: str
    registry: Mapping[str, Any]


@dataclass(frozen=True)
class LoadedRegistry:
    registry: dict[str, Any]
    layers: tuple[RegistryLayer, ...]


@dataclass(frozen=True)
class ListedTool:
    name: str
    scopes: str
    source: str
    config_sources: str


@dataclass(frozen=True)
class WhichCheck:
    executable: str


@dataclass(frozen=True)
class CommandCheck:
    command: tuple[str, ...]


CompletionCheck = WhichCheck | CommandCheck


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="zsh-completions-sync",
        description="Synchronize zsh completion scripts.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("project", help="Generate project-local completions.")
    subparsers.add_parser("global", help="Generate global completions.")
    list_parser = subparsers.add_parser("list", help="List configured completion tools.")
    list_parser.add_argument(
        "--scope",
        choices=sorted(SUPPORTED_SCOPES),
        help="Only show tools enabled for the selected scope.",
    )

    args = parser.parse_args(argv)
    loaded_registry = load_registry(Path.cwd())

    if args.command == "list":
        list_tools(loaded_registry, args.scope)
        return 0

    scope = args.command
    output_dir = default_output_dir(scope)
    tools = parse_scope_tools(loaded_registry.registry, scope)
    sync_tools(tools, output_dir)
    return 0


def default_output_dir(scope: str) -> Path:
    if scope == "project":
        return Path.cwd() / ".completions" / "zsh"
    if scope == "global":
        return Path.home() / ".zsh" / "completions"
    raise ValueError(f"unsupported scope: {scope}")


def load_registry(project_dir: Path) -> LoadedRegistry:
    layers = (
        RegistryLayer("built-in registry", read_resource_toml(DEFAULT_REGISTRY)),
        read_preferred_config_layer("user config", user_config_paths()),
        read_preferred_config_layer("project config", project_config_paths(project_dir)),
    )
    registry: dict[str, Any] = {}
    for layer in layers:
        merge_mapping(registry, layer.registry)
    return LoadedRegistry(registry=registry, layers=layers)


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
    return read_preferred_config_layer("", paths).registry


def read_preferred_config_layer(label: str, paths: tuple[Path, Path]) -> RegistryLayer:
    preferred_path, fallback_path = paths
    preferred_exists = preferred_path.exists()
    fallback_exists = fallback_path.exists()

    if preferred_exists and fallback_exists:
        warn_duplicate_config(preferred_path, fallback_path)

    if preferred_exists:
        return RegistryLayer(format_config_label(label, preferred_path), read_toml(preferred_path))
    return RegistryLayer(format_config_label(label, fallback_path), read_toml(fallback_path))


def format_config_label(label: str, path: Path) -> str:
    if not label:
        return str(path)
    return f"{label}: {path}"


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
    tool_table = registry.get("tools", {})
    if not isinstance(tool_table, Mapping):
        return []

    tools: list[CompletionTool] = []
    for name, config in tool_table.items():
        if not isinstance(name, str) or not isinstance(config, Mapping):
            continue

        scopes = parse_scopes(config.get("scopes"))
        if scopes is None:
            warn_tool(name, "invalid scopes config")
            continue
        if scope not in scopes:
            continue

        tool = parse_tool(name, config)
        if tool is not None:
            tools.append(tool)

    return tools


def parse_scopes(value: object) -> frozenset[str] | None:
    if not isinstance(value, list):
        return None
    if not all(isinstance(item, str) and item for item in value):
        return None

    scopes = frozenset(value)
    if not scopes <= SUPPORTED_SCOPES:
        return None
    return scopes


def parse_tool(name: str, config: Mapping[str, Any]) -> CompletionTool | None:
    source = parse_source(config)
    if source is None:
        warn_tool(name, "invalid source config")
        return None

    check = parse_check(config.get("check"), name)
    if check is _INVALID_CHECK:
        warn_tool(name, "invalid check config")
        return None

    return CompletionTool(name=name, source=source, check=check)


_INVALID_CHECK = object()


def parse_check(value: object, default_executable: str) -> CompletionCheck | None | object:
    if value is None:
        return WhichCheck(default_executable)
    if value is False:
        return None
    if isinstance(value, str) and value:
        return WhichCheck(value)

    command = parse_command(value)
    if command is not None:
        return CommandCheck(command)

    return _INVALID_CHECK


def list_tools(loaded_registry: LoadedRegistry, scope: str | None) -> None:
    rows = listed_tools(loaded_registry, scope)
    if not rows:
        print("No configured tools.")
        return

    print_table(
        ("Tool", "Scopes", "Source", "Config loaded from"),
        tuple((row.name, row.scopes, row.source, row.config_sources) for row in rows),
    )


def listed_tools(loaded_registry: LoadedRegistry, scope: str | None) -> list[ListedTool]:
    tool_table = loaded_registry.registry.get("tools", {})
    if not isinstance(tool_table, Mapping):
        return []

    rows: list[ListedTool] = []
    for name in sorted(tool_table):
        config = tool_table[name]
        if not isinstance(name, str) or not isinstance(config, Mapping):
            continue

        scopes = parse_scopes(config.get("scopes"))
        if scopes is None:
            warn_tool(name, "invalid scopes config")
            continue
        if scope is not None and scope not in scopes:
            continue

        source = parse_source(config)
        if source is None:
            warn_tool(name, "invalid source config")
            continue

        rows.append(
            ListedTool(
                name=name,
                scopes=", ".join(sorted(scopes)),
                source=format_source(source),
                config_sources=" -> ".join(tool_config_sources(loaded_registry.layers, name)),
            )
        )

    return rows


def tool_config_sources(layers: Sequence[RegistryLayer], tool_name: str) -> list[str]:
    sources: list[str] = []
    for layer in layers:
        tool_table = layer.registry.get("tools", {})
        if isinstance(tool_table, Mapping) and tool_name in tool_table:
            sources.append(layer.label)
    return sources


def format_source(source: CompletionSource) -> str:
    if isinstance(source, CommandSource):
        return f"command: {format_command(source.command)}"

    file_source = source.file
    if isinstance(file_source, LocalFileSource):
        return f"file: {file_source.path}"
    if isinstance(file_source, HttpFileSource):
        return f"http: {file_source.url}"
    if isinstance(file_source, GitFileSource):
        ref = f" @ {file_source.ref}" if file_source.ref else ""
        return f"git: {file_source.repository}//{file_source.path}{ref}"

    return "unknown"


def print_table(headers: tuple[str, ...], rows: tuple[tuple[str, ...], ...]) -> None:
    widths = tuple(
        max(len(value) for value in column)
        for column in zip(headers, *rows, strict=True)
    )
    print(format_table_row(headers, widths))
    print(format_table_row(tuple("-" * width for width in widths), widths))
    for row in rows:
        print(format_table_row(row, widths))


def format_table_row(row: tuple[str, ...], widths: tuple[int, ...]) -> str:
    padded_cells = tuple(value.ljust(width) for value, width in zip(row, widths, strict=True))
    return "  ".join(padded_cells).rstrip()


def sync_tools(tools: Sequence[CompletionTool], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for tool in tools:
        sync_tool(tool, output_dir)


def sync_tool(tool: CompletionTool, output_dir: Path) -> None:
    if not tool_enabled(tool.check):
        return

    result = read_source(tool.source)
    if result.error is not None:
        warn_tool(tool.name, result.error)
        return

    destination = output_dir / f"_{tool.name}"
    write_atomic(destination, result.content or b"")


def tool_enabled(check: CompletionCheck | None) -> bool:
    if check is None:
        return True

    if isinstance(check, WhichCheck):
        return shutil.which(check.executable) is not None

    if shutil.which(check.command[0]) is None:
        return False

    try:
        result = subprocess.run(
            check.command,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return False

    return result.returncode == 0


def warn_tool(name: str, message: str) -> None:
    print(f"warn: skip {name}: {message}", file=sys.stderr)


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
