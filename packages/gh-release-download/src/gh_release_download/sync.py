from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    tomllib = None  # type: ignore[assignment]

from .core import eprint, parse_retry_count
from .sync_base import GitHubReleaseSyncEntry, ReleaseSyncType
from .sync_types import SYNC_TYPES


def is_true(name: str) -> bool:
    return os.environ.get(name, "false") == "true"


def usage_value(name: str, default: str = "") -> str:
    return os.environ.get(f"usage_{name}", default).strip()


def optional_string(entry: dict[str, object], key: str, *, name: str, path: Path) -> str:
    value = entry.get(key, "")
    if not isinstance(value, str):
        eprint(f"{name} in {path} has a non-string {key}.")
        raise SystemExit(1)
    return value


def read_apps_file(path: Path) -> dict[str, object]:
    if tomllib is None:
        eprint(
            "Python 3.11 or newer is required to read apps.toml with the standard library tomllib module."
        )
        raise SystemExit(1)

    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        eprint(f"Missing apps file: {path}")
        raise SystemExit(1)
    except tomllib.TOMLDecodeError as error:
        eprint(f"Unable to parse {path}: {error}")
        raise SystemExit(1) from error

    if not isinstance(raw, dict):
        eprint(f"{path} must contain TOML tables.")
        raise SystemExit(1)

    return raw


def table_path_label(path: tuple[str, ...]) -> str:
    return ".".join(path)


def nested_table(raw: dict[str, object], path: tuple[str, ...]) -> object:
    current: object = raw
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def load_sync_entries(path: Path, sync_types: list[ReleaseSyncType]) -> list[GitHubReleaseSyncEntry]:
    raw = read_apps_file(path)
    apps: list[GitHubReleaseSyncEntry] = []

    for sync_type in sync_types:
        table_label = table_path_label(sync_type.table_path)
        entries = nested_table(raw, sync_type.table_path)
        if entries is None:
            continue
        if not isinstance(entries, list):
            eprint(f"{path} must define [[{table_label}]] entries.")
            raise SystemExit(1)

        for index, entry in enumerate(entries, start=1):
            if not isinstance(entry, dict):
                eprint(f"Entry {index} in {path} is not a table.")
                raise SystemExit(1)

            name = entry.get("name")
            repo = entry.get("repo")
            version = entry.get("version")
            if not isinstance(name, str) or not name:
                eprint(f"Entry {index} in {path} is missing name.")
                raise SystemExit(1)
            if not isinstance(repo, str) or "/" not in repo:
                eprint(f"{name} in {path} has an invalid repo.")
                raise SystemExit(1)
            if not isinstance(version, str) or not version:
                eprint(f"{name} in {path} is missing version.")
                raise SystemExit(1)

            apps.append(
                GitHubReleaseSyncEntry(
                    type_name=sync_type.type_name,
                    name=name,
                    repo=repo,
                    version=version,
                    asset_pattern=optional_string(
                        entry, "asset_pattern", name=name, path=path
                    ),
                    asset_regex=optional_string(entry, "asset_regex", name=name, path=path),
                    extra=sync_type.extra_from_entry(entry, name=name, path=path),
                )
            )

    return apps


def selected_sync_types(raw_sync_type: str, *, default_type: str) -> list[ReleaseSyncType]:
    sync_type = raw_sync_type or default_type
    if sync_type == "all":
        return list(SYNC_TYPES.values())

    selected = SYNC_TYPES.get(sync_type)
    if selected is None:
        supported = ", ".join(["all", *SYNC_TYPES])
        eprint(f"Unsupported sync type '{sync_type}'. Supported types: {supported}")
        raise SystemExit(1)

    return [selected]


def sync_release_apps(
    *,
    apps_file: Path,
    sync_types: list[ReleaseSyncType],
    retries: int,
    dry_run: bool,
    force: bool,
) -> dict[str, list[str]]:
    entries = load_sync_entries(apps_file, sync_types)
    entries_by_type: dict[str, list[GitHubReleaseSyncEntry]] = {
        sync_type.type_name: [] for sync_type in sync_types
    }
    for entry in entries:
        entries_by_type[entry.type_name].append(entry)

    updated: dict[str, list[str]] = {sync_type.type_name: [] for sync_type in sync_types}
    for sync_type in sync_types:
        type_entries = entries_by_type[sync_type.type_name]
        if not type_entries:
            continue

        sync_type.require_environment()
        for entry in type_entries:
            if sync_type.sync(entry, retries=retries, dry_run=dry_run, force=force):
                updated[sync_type.type_name].append(entry.name)

    return updated


def print_updated_apps(
    updated: dict[str, list[str]], sync_types: list[ReleaseSyncType]
) -> None:
    for sync_type in sync_types:
        names = updated.get(sync_type.type_name, [])
        if not names:
            continue

        print(sync_type.updated_heading)
        for name in names:
            print(name)


def sync_release_main(*, default_type: str = "all") -> int:
    sync_type_value = usage_value("type") or usage_value("sync_type")
    retries = parse_retry_count(usage_value("retries"))
    apps_file = Path(usage_value("apps_file") or usage_value("tools_file", "apps.toml"))
    dry_run = is_true("usage_dry_run")
    force = is_true("usage_force")

    sync_types = selected_sync_types(sync_type_value, default_type=default_type)
    updated = sync_release_apps(
        apps_file=apps_file,
        sync_types=sync_types,
        retries=retries,
        dry_run=dry_run,
        force=force,
    )
    print_updated_apps(updated, sync_types)
    return 0


if __name__ == "__main__":
    raise SystemExit(sync_release_main(default_type=sys.argv[1] if len(sys.argv) > 1 else "all"))
