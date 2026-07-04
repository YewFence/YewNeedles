from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gh_release_download.core import (
    choose_zip_asset,
    command_output,
    download_asset,
    eprint,
    github_release,
    print_release_selection,
    release_tag_name,
    require_command,
    run_streaming,
    selected_asset_name,
    zip_assets,
)
from gh_release_download.sync_base import GitHubReleaseSyncEntry, normalize_version


VERSION_FILE_NAME = ".gh-release-download-version"


def non_empty_string_entry(
    entry: dict[str, Any],
    key: str,
    *,
    name: str,
    path: Path,
    default: str | None = None,
) -> str:
    raw_value = entry.get(key, default)
    if isinstance(raw_value, str) and raw_value:
        return raw_value

    eprint(f"{name} in {path} has an invalid {key}.")
    raise SystemExit(1)


def kpackage_show(package_type: str, package_id: str) -> tuple[int, str]:
    code, stdout, _ = command_output(
        [
            "kpackagetool6",
            "--type",
            package_type,
            "--show",
            package_id,
        ],
        allow_failure=True,
    )
    return code, stdout


def parse_kpackage_path(stdout: str) -> Path | None:
    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped.startswith("Path"):
            continue
        _, separator, value = stripped.partition(":")
        if separator and value.strip():
            return Path(value.strip()).expanduser()

    return None


def installed_kpackage_path(package_type: str, package_id: str) -> Path | None:
    code, stdout = kpackage_show(package_type, package_id)
    if code != 0:
        return None

    return parse_kpackage_path(stdout)


def kpackage_version_path(package_path: Path) -> Path:
    return package_path / VERSION_FILE_NAME


def read_kpackage_metadata_version(package_path: Path) -> str | None:
    try:
        metadata = json.loads((package_path / "metadata.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None

    if not isinstance(metadata, dict):
        return None

    plugin = metadata.get("KPlugin")
    if not isinstance(plugin, dict):
        return None

    version = plugin.get("Version")
    if not isinstance(version, str):
        return None

    return version.strip() or None


def read_kpackage_sidecar_version(package_path: Path) -> str | None:
    try:
        version = kpackage_version_path(package_path).read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None

    return version or None


def read_kpackage_version(package_path: Path) -> str | None:
    return read_kpackage_metadata_version(package_path) or read_kpackage_sidecar_version(
        package_path
    )


def install_release_kpackage(
    *,
    name: str,
    repo: str,
    version: str | None,
    package_id: str,
    package_type: str,
    installed_path: Path | None,
    pattern: str = "",
    asset_regex: str = "",
    retries: int,
    dry_run: bool,
) -> None:
    release = github_release(repo, version)
    tag_name = release_tag_name(release)
    asset = choose_zip_asset(
        zip_assets(release),
        asset_pattern=pattern,
        asset_regex=asset_regex,
    )
    zip_asset_name = selected_asset_name(asset, asset_label="ZIP")

    print_release_selection(
        name=name,
        repo=repo,
        tag_name=tag_name,
        asset_name_value=zip_asset_name,
        target=installed_path,
    )

    action = "--upgrade" if installed_path is not None else "--install"
    args = ["kpackagetool6", "--type", package_type, action]

    if dry_run:
        print("+ " + " ".join([*args, zip_asset_name]))
        return

    import tempfile

    with tempfile.TemporaryDirectory(prefix="gh-release-kpackage-") as temp_dir:
        zip_path = download_asset(repo, tag_name, zip_asset_name, Path(temp_dir), retries)
        run_streaming([*args, str(zip_path)])

    package_path = installed_kpackage_path(package_type, package_id)
    if package_path is None:
        eprint(f"{name}: installed package path not found after kpackagetool6 completed.")
        return

    kpackage_version_path(package_path).write_text(f"{tag_name}\n", encoding="utf-8")


class KPackageSyncType:
    type_name = "kpackage"
    table_path = ("apps", "kpackage")
    updated_heading = "These KDE packages may need a restart:"

    def extra_from_entry(
        self, entry: dict[str, Any], *, name: str, path: Path
    ) -> dict[str, object]:
        return {
            "package_id": non_empty_string_entry(
                entry, "package_id", name=name, path=path, default=name
            ),
            "package_type": non_empty_string_entry(
                entry, "package_type", name=name, path=path, default="Plasma/Wallpaper"
            ),
        }

    def require_environment(self) -> None:
        require_command("gh", "Install it with: mise use gh@latest")
        require_command("kpackagetool6")

    def sync(
        self,
        entry: GitHubReleaseSyncEntry,
        *,
        retries: int,
        dry_run: bool,
        force: bool,
    ) -> bool:
        package_id = entry.extra["package_id"]
        package_type = entry.extra["package_type"]
        if not isinstance(package_id, str):
            eprint(f"{entry.name} has invalid package_id.")
            raise SystemExit(1)
        if not isinstance(package_type, str):
            eprint(f"{entry.name} has invalid package_type.")
            raise SystemExit(1)

        expected_version = normalize_version(entry.version)
        installed_path = installed_kpackage_path(package_type, package_id)
        if installed_path is None:
            print(f"{entry.name}: not installed as {package_type} {package_id}")
        else:
            current_version = read_kpackage_version(installed_path)
            if current_version is None:
                print(f"{entry.name}: installed at {installed_path}, version unknown")
            elif normalize_version(current_version) == expected_version and not force:
                print(f"{entry.name}: ok ({package_id} {current_version})")
                return False
            else:
                print(
                    f"{entry.name}: installed {package_id} {current_version}, "
                    f"expected {expected_version}"
                )

        install_release_kpackage(
            name=entry.name,
            repo=entry.repo,
            version=entry.version,
            package_id=package_id,
            package_type=package_type,
            installed_path=installed_path,
            pattern=entry.asset_pattern,
            asset_regex=entry.asset_regex,
            retries=retries,
            dry_run=dry_run,
        )
        return True
