from __future__ import annotations

from pathlib import Path
from typing import Any

from gh_release_download.core import (
    command_output,
    eprint,
    install_release_rpm,
    require_command,
    require_red_hat_family,
)
from gh_release_download.sync_base import GitHubReleaseSyncEntry, normalize_version


def package_names_from_entry(entry: dict[str, Any], name: str) -> tuple[str, ...]:
    raw_package_names = entry.get("package_names")
    if isinstance(raw_package_names, list):
        package_names = tuple(
            item for item in raw_package_names if isinstance(item, str) and item
        )
        if package_names:
            return package_names

    raw_package = entry.get("package")
    if isinstance(raw_package, str) and raw_package:
        return (raw_package,)

    return (name,)


def rpm_query_version(package_name: str) -> str | None:
    code, stdout, _ = command_output(
        ["rpm", "-q", "--qf", "%{VERSION}\n", package_name],
        allow_failure=True,
    )
    if code != 0:
        return None

    version = stdout.strip().splitlines()[0] if stdout.strip() else ""
    return version or None


def installed_rpm_version(package_names: tuple[str, ...]) -> tuple[str, str] | None:
    for package_name in package_names:
        version = rpm_query_version(package_name)
        if version is not None:
            return package_name, version

    return None


class RpmSyncType:
    type_name = "rpm"
    table_path = ("apps", "rpm")
    updated_heading = "These tools may need a restart:"

    def extra_from_entry(
        self, entry: dict[str, Any], *, name: str, path: Path
    ) -> dict[str, object]:
        return {"package_names": package_names_from_entry(entry, name)}

    def require_environment(self) -> None:
        require_red_hat_family()
        require_command("gh", "Install it with: mise use gh@latest")
        require_command("rpm")

    def sync(
        self,
        entry: GitHubReleaseSyncEntry,
        *,
        retries: int,
        dry_run: bool,
        force: bool,
    ) -> bool:
        package_names = entry.extra["package_names"]
        if not isinstance(package_names, tuple):
            eprint(f"{entry.name} has invalid package_names.")
            raise SystemExit(1)

        expected_version = normalize_version(entry.version)
        installed = installed_rpm_version(package_names)

        if installed is None:
            package_label = ", ".join(package_names)
            print(f"{entry.name}: not installed as any of [{package_label}]")
        else:
            package_name, current_version = installed
            if normalize_version(current_version) == expected_version and not force:
                print(f"{entry.name}: ok ({package_name} {current_version})")
                return False

            print(
                f"{entry.name}: installed {package_name} {current_version}, "
                f"expected {expected_version}"
            )

        install_release_rpm(
            name=entry.name,
            repo=entry.repo,
            version=entry.version,
            pattern=entry.asset_pattern,
            asset_regex=entry.asset_regex,
            retries=retries,
            dry_run=dry_run,
        )
        return True
