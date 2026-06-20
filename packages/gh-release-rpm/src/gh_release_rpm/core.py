from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
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


def rpm_assets(release: dict[str, object]) -> list[dict[str, object]]:
    assets = release.get("assets")
    if not isinstance(assets, list):
        return []

    rpms: list[dict[str, object]] = []
    for asset in assets:
        if not isinstance(asset, dict):
            continue

        name = asset.get("name")
        if isinstance(name, str) and name.endswith(".rpm"):
            rpms.append(asset)

    return rpms


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


def choose_rpm_asset(assets: list[dict[str, object]], pattern: str) -> dict[str, object]:
    if not assets:
        eprint("Latest GitHub release does not include any RPM assets.")
        raise SystemExit(1)

    if pattern:
        matches = [asset for asset in assets if pattern in str(asset.get("name", ""))]
        if not matches:
            eprint(f"No RPM release asset matched pattern '{pattern}'.")
            raise SystemExit(1)
        assets = matches

    arch = current_arch()
    if arch is not None:
        arch_name, machine = arch
        arch_matches = [asset for asset in assets if matches_arch(asset, arch_name)]
        if arch_matches:
            assets = arch_matches
        else:
            noarch_matches = [asset for asset in assets if is_noarch_asset(asset)]
            if noarch_matches:
                assets = noarch_matches
            elif any(has_arch_marker(asset) for asset in assets):
                eprint(f"No RPM release asset matched current architecture '{arch_name}' from machine '{machine}'.")
                eprint("Available RPM release assets:")
                eprint_assets(assets)
                raise SystemExit(1)

    if len(assets) == 1:
        return assets[0]

    eprint("Found multiple RPM release assets. Re-run with --pattern or set asset_pattern in tools.toml:")
    eprint_assets(assets)
    raise SystemExit(1)


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


def download_asset(repo: str, tag_name: str, asset_name_value: str, dest_dir: Path, retries: int) -> Path:
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


def install_release_rpm(
    *,
    name: str,
    repo: str,
    version: str | None,
    pattern: str,
    retries: int,
    dry_run: bool,
) -> None:
    release = github_release(repo, version)
    tag_name = release.get("tagName")
    if not isinstance(tag_name, str) or not tag_name:
        eprint("GitHub release does not include a tag name.")
        raise SystemExit(1)

    asset = choose_rpm_asset(rpm_assets(release), pattern)
    selected_asset_name = asset.get("name")
    if not isinstance(selected_asset_name, str) or not selected_asset_name:
        eprint("Selected RPM asset has no name.")
        raise SystemExit(1)

    print(f"tool: {name}")
    print(f"repo: {repo}")
    print(f"release: {tag_name}")
    print(f"asset: {selected_asset_name}")

    if dry_run:
        return

    with tempfile.TemporaryDirectory(prefix="gh-release-rpm-") as temp_dir:
        rpm_path = download_asset(repo, tag_name, selected_asset_name, Path(temp_dir), retries)
        run_streaming(sudo_if_needed(install_command(rpm_path)))
