#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_NAME = "volguard-volume-relabel"
SCRIPT_DIR = Path(__file__).resolve().parent


def fail(message: str) -> None:
    raise SystemExit(message)


def ensure_docker() -> None:
    if shutil.which("docker") is None:
        fail("docker command not found")


def parse_label(value: str) -> str:
    if "=" not in value:
        raise argparse.ArgumentTypeError("label must use key=value")

    key, _ = value.split("=", 1)
    if not key.strip():
        raise argparse.ArgumentTypeError("label key must not be empty")

    return value


def parse_label_key(value: str) -> str:
    if not value.strip():
        raise argparse.ArgumentTypeError("label key must not be empty")
    return value.strip()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="volume-relabel",
        description="Rewrite Docker volume labels in place by recreating the volume with its data restored.",
    )
    parser.add_argument("volume", help="Existing Docker volume name.")
    parser.add_argument(
        "--label",
        dest="labels",
        action="append",
        default=[],
        type=parse_label,
        help="Set or overwrite a label with key=value. Repeat as needed.",
    )
    parser.add_argument(
        "--remove-label",
        dest="remove_labels",
        action="append",
        default=[],
        type=parse_label_key,
        help="Remove an existing label key. Repeat as needed.",
    )
    parser.add_argument(
        "--clear-labels",
        action="store_true",
        help="Start from an empty label set before applying --label.",
    )
    parser.add_argument(
        "--keep-backup",
        action="store_true",
        help="Keep the temporary backup volume after a successful relabel.",
    )
    parser.add_argument(
        "--backup-volume",
        default="",
        help="Use a specific temporary backup volume name instead of an auto-generated one.",
    )
    args = parser.parse_args(argv)

    label_keys = {item.split("=", 1)[0].strip() for item in args.labels}
    remove_keys = set(args.remove_labels)
    overlap = sorted(label_keys & remove_keys)
    if overlap:
        fail(f"same label key cannot be set and removed together: {', '.join(overlap)}")

    if not args.clear_labels and not args.labels and not args.remove_labels:
        fail("no label changes requested")

    if args.backup_volume and args.backup_volume == args.volume:
        fail("backup volume name must differ from the target volume")

    return args


def run_relabel(args: argparse.Namespace) -> int:
    env = os.environ.copy()
    env.update(
        {
            "VOLUME_NAME": args.volume,
            "VOLUME_LABELS_SET": "\n".join(args.labels),
            "VOLUME_LABELS_REMOVE": "\n".join(args.remove_labels),
            "VOLUME_LABELS_CLEAR": "true" if args.clear_labels else "false",
            "KEEP_BACKUP_VOLUME": "true" if args.keep_backup else "false",
        }
    )
    if args.backup_volume:
        env["BACKUP_VOLUME_NAME"] = args.backup_volume

    command = [
        "docker",
        "compose",
        "-p",
        PROJECT_NAME,
        "-f",
        str(SCRIPT_DIR / "compose.yaml"),
        "run",
        "--rm",
        "--build",
        "relabel",
    ]
    return subprocess.call(command, env=env)


def main(argv: list[str]) -> int:
    ensure_docker()
    args = parse_args(argv)
    return run_relabel(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
