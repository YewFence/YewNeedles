#!/usr/bin/env python3
from __future__ import annotations

import grp
import os
import pwd
import re
import secrets
import subprocess
import sys
from pathlib import Path


AUTHORIZED_KEYS_DIR = Path("/etc/ssh/authorized_keys")
SSHD_CONFIG_PATH = Path("/etc/ssh/sshd_config")


def fail(message: str) -> None:
    raise SystemExit(message)


def read_env_int(name: str, default: int) -> int:
    raw_value = os.environ.get(name, str(default))
    if not raw_value.isdigit():
        fail(f"invalid {name}, use a numeric value")
    return int(raw_value)


def read_env_user() -> str:
    user = os.environ.get("SFTP_USER", "volguard")
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_-]*", user):
        fail("invalid SFTP_USER, use letters, numbers, underscore or dash only")
    return user


def run(command: list[str]) -> None:
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as exc:
        fail(f"command failed with exit code {exc.returncode}: {' '.join(command)}")


def read_authorized_keys(path: Path) -> str:
    try:
        raw_text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        fail(f"authorized key file does not exist: {path}")
    except OSError as exc:
        fail(f"failed to read authorized key file {path}: {exc}")

    keys = [line.strip() for line in raw_text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    if not keys:
        fail(f"authorized key file is empty: {path}")

    return "\n".join(keys) + "\n"


def ensure_group(gid: int) -> str:
    try:
        return grp.getgrgid(gid).gr_name
    except KeyError:
        group_name = f"sftpusers{gid}"
        run(["addgroup", "-g", str(gid), "-S", group_name])
        return group_name


def ensure_uid_available(user: str, uid: int) -> None:
    try:
        existing_user = pwd.getpwuid(uid).pw_name
    except KeyError:
        return

    if existing_user != user:
        fail(f"SFTP_UID {uid} is already used by {existing_user}")


def ensure_user(user: str, uid: int, gid: int, group_name: str, home: Path) -> None:
    try:
        passwd_entry = pwd.getpwnam(user)
    except KeyError:
        ensure_uid_available(user, uid)
        run(
            [
                "adduser",
                "-D",
                "-H",
                "-h",
                str(home),
                "-s",
                "/sbin/nologin",
                "-u",
                str(uid),
                "-G",
                group_name,
                user,
            ]
        )
        return

    if passwd_entry.pw_uid != uid:
        fail(f"SFTP_USER {user} already exists with uid {passwd_entry.pw_uid}, expected {uid}")
    if passwd_entry.pw_gid != gid:
        fail(f"SFTP_USER {user} already exists with gid {passwd_entry.pw_gid}, expected {gid}")


def unlock_user_for_pubkey(user: str) -> None:
    random_password = secrets.token_urlsafe(32)
    process = subprocess.run(
        ["chpasswd"],
        input=f"{user}:{random_password}\n",
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if process.returncode != 0:
        fail(f"failed to unlock {user} for public key authentication")


def prepare_filesystem(home: Path, authorized_keys_text: str, user: str) -> None:
    (home / "volume").mkdir(parents=True, exist_ok=True)
    Path("/run/sshd").mkdir(parents=True, exist_ok=True)
    AUTHORIZED_KEYS_DIR.mkdir(parents=True, exist_ok=True)

    os.chown(home, 0, 0)
    os.chmod(home, 0o755)
    os.chown(AUTHORIZED_KEYS_DIR, 0, 0)
    os.chmod(AUTHORIZED_KEYS_DIR, 0o755)

    authorized_keys_path = AUTHORIZED_KEYS_DIR / user
    authorized_keys_path.write_text(authorized_keys_text, encoding="utf-8")
    os.chown(authorized_keys_path, 0, 0)
    os.chmod(authorized_keys_path, 0o644)


def write_sshd_config(user: str, home: Path) -> None:
    config = f"""Port 22
HostKey /etc/ssh/ssh_host_ed25519_key
HostKey /etc/ssh/ssh_host_rsa_key
PasswordAuthentication no
PermitEmptyPasswords no
PermitRootLogin no
PubkeyAuthentication yes
KbdInteractiveAuthentication no
ChallengeResponseAuthentication no
AuthenticationMethods publickey
AuthorizedKeysFile /etc/ssh/authorized_keys/%u
X11Forwarding no
AllowTcpForwarding no
AllowAgentForwarding no
PermitTunnel no
PrintMotd no
Subsystem sftp internal-sftp
AllowUsers {user}

Match User {user}
    ChrootDirectory {home}
    ForceCommand internal-sftp -d /volume
    PasswordAuthentication no
"""
    SSHD_CONFIG_PATH.write_text(config, encoding="utf-8")


def main() -> int:
    user = read_env_user()
    uid = read_env_int("SFTP_UID", 1000)
    gid = read_env_int("SFTP_GID", 1000)
    authorized_key_path = Path(os.environ.get("SFTP_AUTHORIZED_KEY_PATH", "/run/volguard/authorized_key.pub"))
    home = Path("/home") / user

    authorized_keys_text = read_authorized_keys(authorized_key_path)
    group_name = ensure_group(gid)
    ensure_user(user, uid, gid, group_name, home)
    unlock_user_for_pubkey(user)
    prepare_filesystem(home, authorized_keys_text, user)
    run(["ssh-keygen", "-A"])
    write_sshd_config(user, home)

    os.execv("/usr/sbin/sshd", ["/usr/sbin/sshd", "-D", "-e", "-f", str(SSHD_CONFIG_PATH)])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
