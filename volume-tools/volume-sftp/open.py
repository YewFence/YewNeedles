#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ipaddress
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_NAME = "volguard-volume-sftp"
SCRIPT_DIR = Path(__file__).resolve().parent
COMPOSE_FILE = SCRIPT_DIR / "compose.yaml"
MANAGEMENT_VOLUME_NAME = "volguard-volume-sftp-management"
ACTION_ALIASES = {
    "start": "start",
    "up": "start",
    "stop": "stop",
    "down": "stop",
    "logs": "logs",
    "status": "status",
    "ps": "status",
}


def fail(message: str) -> None:
    raise SystemExit(message)


def ensure_docker() -> None:
    if shutil.which("docker") is None:
        fail("docker command not found")


def parse_action(argv: list[str]) -> tuple[str, list[str]]:
    if argv and argv[0] in ACTION_ALIASES:
        return ACTION_ALIASES[argv[0]], argv[1:]
    return "start", argv


def parse_port(value: str) -> int:
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("port must be an integer") from exc

    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")

    return port


def parse_ip_address(value: str) -> str:
    try:
        ipaddress.ip_address(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("bind address must be a valid IP address") from exc
    return value


def parse_user(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_-]*", value):
        raise argparse.ArgumentTypeError("user must use letters, numbers, underscore or dash only")
    return value


def parse_id(value: str, label: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{label} must be an integer") from exc

    if parsed < 0:
        raise argparse.ArgumentTypeError(f"{label} must be zero or greater")

    return parsed


def parse_positive_int(value: str, label: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{label} must be an integer") from exc

    if parsed < 1:
        raise argparse.ArgumentTypeError(f"{label} must be 1 or greater")

    return parsed


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise argparse.ArgumentTypeError("value must be true or false")


def env_default(name: str, default: str, parser: object) -> object:
    raw_value = os.environ.get(name, default)
    try:
        return parser(raw_value)
    except argparse.ArgumentTypeError as exc:
        fail(f"invalid {name}: {exc}")


def parse_key_file(value: str) -> str:
    path = Path(value).expanduser()
    if not path.is_file():
        raise argparse.ArgumentTypeError(f"authorized key file does not exist: {value}")

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise argparse.ArgumentTypeError(f"failed to read authorized key file {value}: {exc}") from exc

    if not any(line.strip() and not line.lstrip().startswith("#") for line in lines):
        raise argparse.ArgumentTypeError(f"authorized key file is empty: {value}")

    return str(path.resolve())


def build_start_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="volume-sftp",
        description="Start or manage a temporary SFTP service for a Docker volume.",
    )
    parser.add_argument("volume", help="Existing Docker volume name.")
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--ro", dest="read_only", action="store_true", help="Mount the volume read-only.")
    mode_group.add_argument(
        "--rw",
        "--write",
        dest="read_only",
        action="store_false",
        help="Mount the volume read-write.",
    )
    parser.set_defaults(read_only=True)
    parser.add_argument("--port", type=parse_port, default=env_default("SFTP_PORT", "2222", parse_port))
    parser.add_argument(
        "--bind",
        dest="bind_address",
        type=parse_ip_address,
        default=env_default("SFTP_BIND_ADDRESS", "127.0.0.1", parse_ip_address),
    )
    parser.add_argument("--user", type=parse_user, default=env_default("SFTP_USER", "volguard", parse_user))
    parser.add_argument(
        "--authorized-key",
        dest="authorized_key_file",
        type=parse_key_file,
        default=None,
        help="Path to a public key or authorized_keys file to mount into the container. Defaults to ~/.ssh/authorized_keys.",
    )
    parser.add_argument(
        "--uid",
        type=lambda value: parse_id(value, "uid"),
        default=env_default("SFTP_UID", "1000", lambda value: parse_id(value, "uid")),
    )
    parser.add_argument(
        "--gid",
        type=lambda value: parse_id(value, "gid"),
        default=env_default("SFTP_GID", "1000", lambda value: parse_id(value, "gid")),
    )
    parser.add_argument(
        "--max-auth-tries",
        type=lambda value: parse_positive_int(value, "max auth tries"),
        default=env_default("SFTP_MAX_AUTH_TRIES", "6", lambda value: parse_positive_int(value, "max auth tries")),
        help="Maximum authentication attempts allowed per SSH connection.",
    )
    parser.add_argument(
        "--allow-root-login",
        action=argparse.BooleanOptionalAction,
        default=env_default("SFTP_ALLOW_ROOT_LOGIN", "false", parse_bool),
        help="Allow root to authenticate with the configured public keys.",
    )
    parser.add_argument(
        "--allow-ssh",
        action=argparse.BooleanOptionalAction,
        default=env_default("SFTP_ALLOW_SSH", "false", parse_bool),
        help="Allow regular SSH sessions in addition to SFTP.",
    )
    return parser


def default_key_file() -> str | None:
    configured = os.environ.get("SFTP_AUTHORIZED_KEY_FILE")
    default_path = configured or str(Path.home() / ".ssh" / "authorized_keys")

    try:
        return parse_key_file(default_path)
    except argparse.ArgumentTypeError as exc:
        if configured:
            fail(str(exc))
        fail(f"default authorized key file is not usable, pass --authorized-key or create {default_path}: {exc}")


def compose(command: list[str], env: dict[str, str] | None = None) -> int:
    full_command = [
        "docker",
        "compose",
        "-p",
        PROJECT_NAME,
        "-f",
        str(COMPOSE_FILE),
        *command,
    ]
    return subprocess.call(full_command, env=env)


def management_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("VOLUME_NAME", MANAGEMENT_VOLUME_NAME)
    env.setdefault("SFTP_AUTHORIZED_KEY_FILE", str(Path(__file__).resolve()))
    return env


def connect_host(bind_address: str) -> str:
    if bind_address == "0.0.0.0":
        return "127.0.0.1"
    if bind_address == "::":
        return "::1"
    return bind_address


def handle_start(argv: list[str]) -> int:
    parser = build_start_parser()
    args = parser.parse_args(argv)

    authorized_key_file = args.authorized_key_file or default_key_file()

    env = os.environ.copy()
    env.update(
        {
            "VOLUME_NAME": args.volume,
            "VOLUME_READ_ONLY": "true" if args.read_only else "false",
            "SFTP_PORT": str(args.port),
            "SFTP_BIND_ADDRESS": args.bind_address,
            "SFTP_USER": args.user,
            "SFTP_UID": str(args.uid),
            "SFTP_GID": str(args.gid),
            "SFTP_MAX_AUTH_TRIES": str(args.max_auth_tries),
            "SFTP_ALLOW_ROOT_LOGIN": "true" if args.allow_root_login else "false",
            "SFTP_ALLOW_SSH": "true" if args.allow_ssh else "false",
            "SFTP_AUTHORIZED_KEY_FILE": authorized_key_file,
        }
    )

    return_code = compose(["up", "-d", "--build", "sftp"], env=env)
    if return_code != 0:
        return return_code

    host = connect_host(args.bind_address)
    print(f"sftp is listening on {args.bind_address}:{args.port}")
    print(f"connect with: sftp -P {args.port} {args.user}@{host}")
    if args.allow_ssh:
        print(f"ssh with: ssh -t -p {args.port} {args.user}@{host}")
    print(f"authorized keys file: {authorized_key_file}")
    print("stop with: volume-sftp/open.py stop")
    return 0


def main(argv: list[str]) -> int:
    action, remaining = parse_action(argv)
    ensure_docker()

    if action == "stop":
        return compose(["down", "--remove-orphans"], env=management_env())
    if action == "logs":
        return compose(["logs", "-f", "sftp"], env=management_env())
    if action == "status":
        return compose(["ps"], env=management_env())
    return handle_start(remaining)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
