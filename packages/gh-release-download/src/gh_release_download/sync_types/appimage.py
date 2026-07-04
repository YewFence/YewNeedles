from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from gh_release_download.core import (
    eprint,
    find_gearlever_appimage,
    install_release_appimage,
    require_command,
)
from gh_release_download.sync_base import GitHubReleaseSyncEntry, normalize_version


def warning(message: str) -> None:
    prefix = "warning"
    if os.environ.get("NO_COLOR") is None and os.environ.get("TERM") != "dumb":
        prefix = "\033[1;33mwarning\033[0m"
    eprint(f"{prefix}: {message}")


def app_name_from_entry(entry: dict[str, Any], name: str, *, path: Path) -> str:
    raw_app_name = entry.get("app_name")
    if raw_app_name is None:
        return name
    if isinstance(raw_app_name, str) and raw_app_name:
        return raw_app_name

    eprint(f"{name} in {path} has an invalid app_name.")
    raise SystemExit(1)


class AppImageSyncType:
    type_name = "appimage"
    table_path = ("apps", "appimage")
    updated_heading = "These apps may need a restart:"

    def extra_from_entry(
        self, entry: dict[str, Any], *, name: str, path: Path
    ) -> dict[str, object]:
        return {"app_name": app_name_from_entry(entry, name, path=path)}

    def require_environment(self) -> None:
        require_command("gh", "Install it with: mise use gh@latest")

    def sync(
        self,
        entry: GitHubReleaseSyncEntry,
        *,
        retries: int,
        dry_run: bool,
        force: bool,
    ) -> bool:
        app_name = entry.extra["app_name"]
        if not isinstance(app_name, str):
            eprint(f"{entry.name} has invalid app_name.")
            raise SystemExit(1)

        installed = find_gearlever_appimage(app_name)
        expected_version = normalize_version(entry.version)

        if installed is None:
            warning(f"{entry.name}: not installed by Gear Lever, install it once first")
            return False

        if installed.version is None:
            warning(f"{entry.name}: unable to locate AppImage version for {installed.path}")
            print(f"{entry.name}: installed at {installed.path}, version unknown")
        elif normalize_version(installed.version) == expected_version and not force:
            print(f"{entry.name}: ok ({installed.version} from {installed.version_source})")
            return False
        else:
            print(
                f"{entry.name}: installed {installed.version} from "
                f"{installed.version_source}, expected {expected_version}"
            )

        install_release_appimage(
            name=entry.name,
            repo=entry.repo,
            version=entry.version,
            app_name=app_name,
            target_path=installed.path,
            desktop_file=installed.desktop_file,
            pattern=entry.asset_pattern,
            asset_regex=entry.asset_regex,
            retries=retries,
            dry_run=dry_run,
        )
        return True
