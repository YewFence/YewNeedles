from __future__ import annotations

import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path


RED_HAT_FAMILY_IDS = {
    "almalinux",
    "centos",
    "fedora",
    "ol",
    "rhel",
    "rocky",
    "scientific",
}

ARCH_ALIASES = {
    "amd64": "x64",
    "x64": "x64",
    "x86_64": "x64",
    "aarch64": "arm64",
    "arm64": "arm64",
    "armhfp": "arm",
    "armv6hl": "arm",
    "armv6l": "arm",
    "armv7hl": "arm",
    "armv7l": "arm",
    "armv8hl": "arm",
    "armv8l": "arm",
}

ARCH_ASSET_PATTERNS = {
    "x64": re.compile(
        r"(^|[^A-Za-z0-9])(x86_64|amd64|x64)([^A-Za-z0-9]|$)",
        re.IGNORECASE,
    ),
    "arm64": re.compile(
        r"(^|[^A-Za-z0-9])(aarch64|arm64)([^A-Za-z0-9]|$)",
        re.IGNORECASE,
    ),
    "arm": re.compile(
        r"(^|[^A-Za-z0-9])"
        r"(armhfp|armv6hl|armv6l|armv7hl|armv7l|armv8hl|armv8l|arm)"
        r"([^A-Za-z0-9]|$)",
        re.IGNORECASE,
    ),
}

NOARCH_ASSET_PATTERN = re.compile(
    r"(^|[^A-Za-z0-9])noarch([^A-Za-z0-9]|$)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class InstalledAppImage:
    app_name: str
    path: Path
    desktop_file: Path
    version: str | None = None
    version_source: str | None = None


def eprint(message: str) -> None:
    print(message, file=sys.stderr)


def require_command(name: str, install_hint: str | None = None) -> None:
    if shutil.which(name) is not None:
        return

    if install_hint:
        eprint(f"{name} is not on PATH. {install_hint}")
    else:
        eprint(f"{name} is not on PATH.")
    raise SystemExit(1)


def parse_os_release(path: Path = Path("/etc/os-release")) -> dict[str, str]:
    values: dict[str, str] = {}

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        eprint("Missing /etc/os-release. This task only supports Fedora/RHEL family systems.")
        raise SystemExit(1)

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value

    return values


def os_family_tokens(os_release: dict[str, str]) -> set[str]:
    tokens = {os_release.get("ID", "").lower()}
    tokens.update(token.lower() for token in os_release.get("ID_LIKE", "").split())
    tokens.discard("")
    return tokens


def require_red_hat_family() -> None:
    os_release = parse_os_release()
    tokens = os_family_tokens(os_release)

    if tokens & RED_HAT_FAMILY_IDS:
        return

    pretty_name = os_release.get("PRETTY_NAME") or os_release.get("NAME") or "this system"
    eprint(f"{pretty_name} is not a Fedora/RHEL family system. Refusing to install an RPM.")
    raise SystemExit(1)


def command_output(args: list[str], *, allow_failure: bool = False) -> tuple[int, str, str]:
    result = subprocess.run(
        args,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0 and not allow_failure:
        error = result.stderr.strip() or result.stdout.strip() or "command failed"
        eprint(error)
        raise SystemExit(result.returncode)

    return result.returncode, result.stdout, result.stderr


def checked_output(args: list[str]) -> str:
    _, stdout, _ = command_output(args)
    return stdout


def run_streaming(args: list[str], *, dry_run: bool = False) -> None:
    print("+ " + " ".join(args))
    if dry_run:
        return

    result = subprocess.run(args, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def github_release(repo: str, tag_name: str | None = None) -> dict[str, object]:
    args = [
        "gh",
        "release",
        "view",
        "--repo",
        repo,
        "--json",
        "tagName,name,assets",
    ]
    if tag_name:
        args.insert(3, tag_name)

    raw_release = checked_output(args)

    try:
        release = json.loads(raw_release)
    except json.JSONDecodeError as error:
        eprint(f"Unable to parse gh release output: {error}")
        raise SystemExit(1) from error

    if not isinstance(release, dict):
        eprint("Unexpected gh release output.")
        raise SystemExit(1)

    return release


def release_assets(release: dict[str, object]) -> list[dict[str, object]]:
    assets = release.get("assets")
    if not isinstance(assets, list):
        return []

    return [asset for asset in assets if isinstance(asset, dict)]


def assets_with_extension(
    release: dict[str, object], extension: str
) -> list[dict[str, object]]:
    normalized_extension = extension.lower()
    return [
        asset
        for asset in release_assets(release)
        if asset_name(asset).lower().endswith(normalized_extension)
    ]


def rpm_assets(release: dict[str, object]) -> list[dict[str, object]]:
    return assets_with_extension(release, ".rpm")


def appimage_assets(release: dict[str, object]) -> list[dict[str, object]]:
    return assets_with_extension(release, ".appimage")


def zip_assets(release: dict[str, object]) -> list[dict[str, object]]:
    return assets_with_extension(release, ".zip")


def current_arch() -> tuple[str, str] | None:
    machine = platform.machine().lower()
    arch = ARCH_ALIASES.get(machine)
    if arch is None:
        return None

    return arch, machine


def asset_name(asset: dict[str, object]) -> str:
    return str(asset.get("name", ""))


def matches_arch(asset: dict[str, object], arch: str) -> bool:
    pattern = ARCH_ASSET_PATTERNS.get(arch)
    return bool(pattern and pattern.search(asset_name(asset)))


def is_noarch_asset(asset: dict[str, object]) -> bool:
    return bool(NOARCH_ASSET_PATTERN.search(asset_name(asset)))


def has_arch_marker(asset: dict[str, object]) -> bool:
    name = asset_name(asset)
    return any(pattern.search(name) for pattern in ARCH_ASSET_PATTERNS.values())


def eprint_assets(assets: list[dict[str, object]]) -> None:
    for asset in assets:
        eprint(f"  {asset.get('name', '<unnamed>')}")


def compile_asset_regex(asset_regex: str, *, asset_label: str) -> re.Pattern[str] | None:
    if not asset_regex:
        return None

    try:
        return re.compile(asset_regex)
    except re.error as error:
        eprint(f"Invalid {asset_label} asset_regex '{asset_regex}': {error}")
        raise SystemExit(1) from error


def filter_assets_by_name(
    assets: list[dict[str, object]],
    *,
    asset_label: str,
    asset_pattern: str = "",
    asset_regex: str = "",
) -> list[dict[str, object]]:
    if asset_pattern:
        matches = [asset for asset in assets if asset_pattern in asset_name(asset)]
        if not matches:
            eprint(f"No {asset_label} release asset matched pattern '{asset_pattern}'.")
            raise SystemExit(1)
        assets = matches

    compiled_regex = compile_asset_regex(asset_regex, asset_label=asset_label)
    if compiled_regex is not None:
        matches = [asset for asset in assets if compiled_regex.search(asset_name(asset))]
        if not matches:
            eprint(f"No {asset_label} release asset matched regex '{asset_regex}'.")
            raise SystemExit(1)
        assets = matches

    return assets


def filter_assets_by_arch(
    assets: list[dict[str, object]], *, asset_label: str
) -> list[dict[str, object]]:
    arch = current_arch()
    if arch is None:
        return assets

    arch_name, machine = arch
    arch_matches = [asset for asset in assets if matches_arch(asset, arch_name)]
    if arch_matches:
        return arch_matches

    noarch_matches = [asset for asset in assets if is_noarch_asset(asset)]
    if noarch_matches:
        return noarch_matches

    if any(has_arch_marker(asset) for asset in assets):
        eprint(
            f"No {asset_label} release asset matched current architecture "
            f"'{arch_name}' from machine '{machine}'."
        )
        eprint(f"Available {asset_label} release assets:")
        eprint_assets(assets)
        raise SystemExit(1)

    return assets


def choose_release_asset(
    assets: list[dict[str, object]],
    *,
    asset_label: str,
    asset_pattern: str = "",
    asset_regex: str = "",
    filter_arch: bool = True,
    config_hint: str,
) -> dict[str, object]:
    if not assets:
        eprint(f"Latest GitHub release does not include any {asset_label} assets.")
        raise SystemExit(1)

    assets = filter_assets_by_name(
        assets,
        asset_label=asset_label,
        asset_pattern=asset_pattern,
        asset_regex=asset_regex,
    )
    if filter_arch:
        assets = filter_assets_by_arch(assets, asset_label=asset_label)

    if len(assets) == 1:
        return assets[0]

    eprint(
        f"Found multiple {asset_label} release assets. Re-run with --pattern, "
        f"--asset-regex, or set asset_regex in {config_hint}:"
    )
    eprint_assets(assets)
    raise SystemExit(1)


def choose_rpm_asset(
    assets: list[dict[str, object]],
    *,
    asset_pattern: str = "",
    asset_regex: str = "",
) -> dict[str, object]:
    return choose_release_asset(
        assets,
        asset_label="RPM",
        asset_pattern=asset_pattern,
        asset_regex=asset_regex,
        config_hint="apps.toml",
    )


def choose_appimage_asset(
    assets: list[dict[str, object]],
    *,
    asset_pattern: str = "",
    asset_regex: str = "",
) -> dict[str, object]:
    return choose_release_asset(
        assets,
        asset_label="AppImage",
        asset_pattern=asset_pattern,
        asset_regex=asset_regex,
        config_hint="apps.toml",
    )


def choose_zip_asset(
    assets: list[dict[str, object]],
    *,
    asset_pattern: str = "",
    asset_regex: str = "",
) -> dict[str, object]:
    return choose_release_asset(
        assets,
        asset_label="ZIP",
        asset_pattern=asset_pattern,
        asset_regex=asset_regex,
        config_hint="apps.toml",
    )


def parse_retry_count(raw_retries: str) -> int:
    if not raw_retries:
        return 3

    try:
        retries = int(raw_retries)
    except ValueError:
        eprint("--retries must be an integer.")
        raise SystemExit(1)

    if retries < 1:
        eprint("--retries must be at least 1.")
        raise SystemExit(1)

    return retries


def download_asset(
    repo: str, tag_name: str, asset_name_value: str, dest_dir: Path, retries: int
) -> Path:
    output_path = dest_dir / asset_name_value
    args = [
        "gh",
        "release",
        "download",
        tag_name,
        "--repo",
        repo,
        "--pattern",
        asset_name_value,
        "--output",
        str(output_path),
        "--clobber",
    ]

    for attempt in range(1, retries + 1):
        print("+ " + " ".join(args) + f"  # attempt {attempt}/{retries}")
        result = subprocess.run(args, check=False)
        if result.returncode == 0 and output_path.is_file():
            return output_path

        if attempt == retries:
            raise SystemExit(result.returncode or 1)

        time.sleep(min(2**attempt, 10))

    raise SystemExit(1)


def install_command(rpm_path: Path) -> list[str]:
    package_manager = shutil.which("dnf") or shutil.which("yum")
    if package_manager:
        return [package_manager, "install", "-y", str(rpm_path)]

    require_command("rpm")
    return ["rpm", "-Uvh", str(rpm_path)]


def sudo_if_needed(args: list[str]) -> list[str]:
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return args

    require_command("sudo", "Install as root or make sudo available.")
    return ["sudo", *args]


def selected_asset_name(asset: dict[str, object], *, asset_label: str) -> str:
    name = asset.get("name")
    if not isinstance(name, str) or not name:
        eprint(f"Selected {asset_label} asset has no name.")
        raise SystemExit(1)

    return name


def print_release_selection(
    *,
    name: str,
    repo: str,
    tag_name: str,
    asset_name_value: str,
    target: Path | None = None,
) -> None:
    print(f"tool: {name}")
    print(f"repo: {repo}")
    print(f"release: {tag_name}")
    print(f"asset: {asset_name_value}")
    if target is not None:
        print(f"target: {target}")


def release_tag_name(release: dict[str, object]) -> str:
    tag_name = release.get("tagName")
    if not isinstance(tag_name, str) or not tag_name:
        eprint("GitHub release does not include a tag name.")
        raise SystemExit(1)

    return tag_name


def install_release_rpm(
    *,
    name: str,
    repo: str,
    version: str | None,
    pattern: str = "",
    asset_regex: str = "",
    retries: int,
    dry_run: bool,
) -> None:
    release = github_release(repo, version)
    tag_name = release_tag_name(release)
    asset = choose_rpm_asset(
        rpm_assets(release),
        asset_pattern=pattern,
        asset_regex=asset_regex,
    )
    rpm_asset_name = selected_asset_name(asset, asset_label="RPM")

    print_release_selection(
        name=name,
        repo=repo,
        tag_name=tag_name,
        asset_name_value=rpm_asset_name,
    )

    if dry_run:
        return

    with tempfile.TemporaryDirectory(prefix="gh-release-rpm-") as temp_dir:
        rpm_path = download_asset(repo, tag_name, rpm_asset_name, Path(temp_dir), retries)
        run_streaming(sudo_if_needed(install_command(rpm_path)))


def appimage_file_name(app_name: str) -> str:
    stem = app_name
    if stem.lower().endswith(".appimage"):
        stem = stem[: -len(".appimage")]

    gearlever_name = stem.lower().replace(" ", "_")
    gearlever_name = re.sub(r"[^\w\._]+", "", f"{gearlever_name}.appimage")
    return gearlever_name.lower()


def appimage_path(app_name: str, destination_dir: Path | None = None) -> Path:
    target_dir = destination_dir or Path.home() / "AppImages"
    return target_dir / appimage_file_name(app_name)


def appimage_version_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.version")


def read_installed_appimage_version(path: Path) -> str | None:
    version = read_installed_appimage_version_with_source(path)[0]
    return version


def read_installed_appimage_version_with_source(path: Path) -> tuple[str | None, str | None]:
    version_path = appimage_version_path(path)
    try:
        version = version_path.read_text(encoding="utf-8").strip() or None
    except FileNotFoundError:
        return None, None

    if version is None:
        return None, None

    return version, str(version_path)


def desktop_applications_dir() -> Path:
    return Path.home() / ".local" / "share" / "applications"


def read_desktop_entry_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    in_desktop_entry = False

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return values

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", ";")):
            continue

        if stripped.startswith("[") and stripped.endswith("]"):
            if stripped == "[Desktop Entry]":
                in_desktop_entry = True
                continue
            if in_desktop_entry:
                break
            continue

        if in_desktop_entry and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()

    return values


def desktop_entry_appimage_path(values: dict[str, str]) -> Path | None:
    try_exec = values.get("TryExec", "")
    if try_exec:
        return Path(try_exec).expanduser()

    exec_value = values.get("Exec", "")
    if not exec_value:
        return None

    try:
        parts = shlex_split(exec_value)
    except ValueError:
        return None

    if len(parts) >= 3 and parts[0] == "env":
        for index, part in enumerate(parts[1:], start=1):
            if "=" not in part:
                return Path(part).expanduser()
            if index == len(parts) - 1:
                return None
    if parts:
        return Path(parts[0]).expanduser()

    return None


def shlex_split(value: str) -> list[str]:
    import shlex

    return shlex.split(value)


def normalize_appimage_label(value: str) -> str:
    label = value.strip().lower()
    if label.endswith(".appimage"):
        label = label[: -len(".appimage")]
    if label.startswith("gearlever_"):
        label = label[len("gearlever_") :]
    return re.sub(r"[^a-z0-9]+", "", label)


def desktop_entry_matches_app(
    path: Path, values: dict[str, str], app_name: str
) -> bool:
    expected = normalize_appimage_label(app_name)
    candidates = [
        values.get("Name", ""),
        values.get("X-AppImage-Name", ""),
        path.stem,
    ]
    appimage = desktop_entry_appimage_path(values)
    if appimage is not None:
        candidates.append(appimage.stem)

    return any(normalize_appimage_label(candidate) == expected for candidate in candidates)


def find_gearlever_appimage(app_name: str) -> InstalledAppImage | None:
    applications_dir = desktop_applications_dir()
    if not applications_dir.is_dir():
        return None

    for desktop_file in sorted(applications_dir.glob("*.desktop")):
        values = read_desktop_entry_values(desktop_file)
        if not desktop_entry_matches_app(desktop_file, values, app_name):
            continue

        path = desktop_entry_appimage_path(values)
        if path is None or not path.is_file():
            continue
        if path.suffix.lower() != ".appimage":
            continue

        desktop_version = values.get("X-AppImage-Version")
        sidecar_version, sidecar_source = read_installed_appimage_version_with_source(path)
        return InstalledAppImage(
            app_name=values.get("Name") or app_name,
            path=path,
            desktop_file=desktop_file,
            version=desktop_version or sidecar_version,
            version_source=(
                f"{desktop_file} X-AppImage-Version"
                if desktop_version
                else sidecar_source
            ),
        )

    return None


def update_desktop_entry_key(path: Path, key: str, value: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    output: list[str] = []
    in_desktop_entry = False
    key_written = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if in_desktop_entry and not key_written:
                output.append(f"{key}={value}")
                key_written = True
            in_desktop_entry = stripped == "[Desktop Entry]"
            output.append(line)
            continue

        if in_desktop_entry and line.split("=", 1)[0].strip() == key:
            if not key_written:
                output.append(f"{key}={value}")
                key_written = True
            continue

        output.append(line)

    if in_desktop_entry and not key_written:
        output.append(f"{key}={value}")

    path.write_text("\n".join(output) + "\n", encoding="utf-8")


def make_executable(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def replace_appimage(
    downloaded_path: Path,
    destination_path: Path,
    version: str,
    desktop_file: Path | None = None,
) -> None:
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = destination_path.with_name(
        f".{destination_path.name}.tmp-{os.getpid()}"
    )
    shutil.move(str(downloaded_path), temporary_path)
    make_executable(temporary_path)
    temporary_path.replace(destination_path)
    appimage_version_path(destination_path).write_text(f"{version}\n", encoding="utf-8")
    if desktop_file is not None:
        update_desktop_entry_key(desktop_file, "X-AppImage-Version", version)


def install_release_appimage(
    *,
    name: str,
    repo: str,
    version: str | None,
    app_name: str,
    target_path: Path,
    desktop_file: Path | None,
    pattern: str = "",
    asset_regex: str = "",
    retries: int,
    dry_run: bool,
) -> None:
    release = github_release(repo, version)
    tag_name = release_tag_name(release)
    asset = choose_appimage_asset(
        appimage_assets(release),
        asset_pattern=pattern,
        asset_regex=asset_regex,
    )
    appimage_asset_name = selected_asset_name(asset, asset_label="AppImage")

    print_release_selection(
        name=name,
        repo=repo,
        tag_name=tag_name,
        asset_name_value=appimage_asset_name,
        target=target_path,
    )

    if dry_run:
        return

    with tempfile.TemporaryDirectory(prefix="gh-release-appimage-") as temp_dir:
        downloaded_path = download_asset(
            repo, tag_name, appimage_asset_name, Path(temp_dir), retries
        )
        replace_appimage(downloaded_path, target_path, tag_name, desktop_file)
