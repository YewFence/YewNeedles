#!/usr/bin/env python3
from __future__ import annotations

import grp
import ipaddress
import os
import pwd
import re
import secrets
import subprocess
import sys
from pathlib import Path


AUTHORIZED_KEYS_DIR = Path("/etc/ssh/authorized_keys")
SSHD_CONFIG_PATH = Path("/etc/ssh/sshd_config")
PASSWD_PATH = Path("/etc/passwd")


def fail(message: str) -> None:
    raise SystemExit(message)


def read_env_int(name: str, default: int) -> int:
    raw_value = os.environ.get(name, str(default))
    if not raw_value.isdigit():
        fail(f"invalid {name}, use a numeric value")
    return int(raw_value)


def read_env_bool(name: str, default: bool) -> bool:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default

    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    fail(f"invalid {name}, use true or false")


def read_env_positive_int(name: str, default: int) -> int:
    value = read_env_int(name, default)
    if value < 1:
        fail(f"invalid {name}, use a value of 1 or greater")
    return value


def read_env_port(name: str, default: int) -> int:
    port = read_env_int(name, default)
    if not 1 <= port <= 65535:
        fail(f"invalid {name}, use a value between 1 and 65535")
    return port


def read_env_bind_address() -> str:
    bind_address = os.environ.get("SFTP_BIND_ADDRESS", "127.0.0.1")
    try:
        ipaddress.ip_address(bind_address)
    except ValueError:
        fail("invalid SFTP_BIND_ADDRESS, use a valid IP address")
    return bind_address


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


def connect_host(bind_address: str) -> str:
    if bind_address == "0.0.0.0":
        return "127.0.0.1"
    if bind_address == "::":
        return "::1"
    return bind_address


def print_startup_info(
    *,
    bind_address: str,
    port: int,
    user: str,
    uid: int,
    gid: int,
    max_auth_tries: int,
    allow_root_login: bool,
    allow_ssh: bool,
    authorized_key_path: Path,
    authorized_keys_text: str,
) -> None:
    print("volume-sftp environment", flush=True)
    print(f"SFTP_BIND_ADDRESS={bind_address}", flush=True)
    print(f"SFTP_PORT={port}", flush=True)
    print(f"SFTP_USER={user}", flush=True)
    print(f"SFTP_UID={uid}", flush=True)
    print(f"SFTP_GID={gid}", flush=True)
    print(f"SFTP_MAX_AUTH_TRIES={max_auth_tries}", flush=True)
    print(f"SFTP_ALLOW_ROOT_LOGIN={str(allow_root_login).lower()}", flush=True)
    print(f"SFTP_ALLOW_SSH={str(allow_ssh).lower()}", flush=True)
    print(f"SFTP_AUTHORIZED_KEY_PATH={authorized_key_path}", flush=True)
    print("volume-sftp authorized public keys", flush=True)
    for key in authorized_keys_text.splitlines():
        print(key, flush=True)
    print("volume-sftp sftp command", flush=True)
    print(f"sftp -P {port} {user}@{connect_host(bind_address)}", flush=True)
    if allow_ssh:
        print("volume-sftp ssh command", flush=True)
        print(f"ssh -t -p {port} {user}@{connect_host(bind_address)}", flush=True)


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


def update_user_shell(user: str, shell: str) -> None:
    lines = PASSWD_PATH.read_text(encoding="utf-8").splitlines()
    updated_lines = []
    changed = False

    for line in lines:
        fields = line.split(":")
        if len(fields) == 7 and fields[0] == user:
            fields[-1] = shell
            line = ":".join(fields)
            changed = True
        updated_lines.append(line)

    if not changed:
        fail(f"failed to update shell for {user}")

    PASSWD_PATH.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")


def ensure_user(user: str, uid: int, gid: int, group_name: str, home: Path, shell: str) -> None:
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
                shell,
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
    if passwd_entry.pw_shell != shell:
        update_user_shell(user, shell)


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


def prepare_filesystem(
    home: Path,
    authorized_keys_text: str,
    user: str,
    uid: int,
    gid: int,
    allow_root_login: bool,
    allow_ssh: bool,
) -> None:
    (home / "volume").mkdir(parents=True, exist_ok=True)
    Path("/run/sshd").mkdir(parents=True, exist_ok=True)
    AUTHORIZED_KEYS_DIR.mkdir(parents=True, exist_ok=True)

    home_uid = uid if allow_ssh else 0
    home_gid = gid if allow_ssh else 0
    os.chown(home, home_uid, home_gid)
    os.chmod(home, 0o755)
    os.chown(AUTHORIZED_KEYS_DIR, 0, 0)
    os.chmod(AUTHORIZED_KEYS_DIR, 0o755)

    authorized_keys_path = AUTHORIZED_KEYS_DIR / user
    authorized_keys_path.write_text(authorized_keys_text, encoding="utf-8")
    os.chown(authorized_keys_path, 0, 0)
    os.chmod(authorized_keys_path, 0o644)

    if allow_root_login:
        root_authorized_keys_path = AUTHORIZED_KEYS_DIR / "root"
        root_authorized_keys_path.write_text(authorized_keys_text, encoding="utf-8")
        os.chown(root_authorized_keys_path, 0, 0)
        os.chmod(root_authorized_keys_path, 0o644)


def allowed_users(user: str, allow_root_login: bool) -> str:
    users = [user]
    if allow_root_login and user != "root":
        users.append("root")
    return " ".join(users)


def matched_users(user: str, allow_root_login: bool) -> str:
    users = [user]
    if allow_root_login and user != "root":
        users.append("root")
    return ",".join(users)


def write_sshd_config(
    user: str,
    home: Path,
    max_auth_tries: int,
    allow_root_login: bool,
    allow_ssh: bool,
) -> None:
    permit_root_login = "yes" if allow_root_login else "no"
    permit_tty = "yes" if allow_ssh else "no"
    allow_users = allowed_users(user, allow_root_login)
    match_users = matched_users(user, allow_root_login)
    sftp_only_match = (
        ""
        if allow_ssh
        else f"""
Match User {match_users}
    ChrootDirectory {home}
    ForceCommand internal-sftp -d /volume
    PasswordAuthentication no
"""
    )
    config = f"""Port 22
HostKey /etc/ssh/ssh_host_ed25519_key
HostKey /etc/ssh/ssh_host_rsa_key
PasswordAuthentication no
PermitEmptyPasswords no
PermitRootLogin {permit_root_login}
PubkeyAuthentication yes
KbdInteractiveAuthentication no
ChallengeResponseAuthentication no
AuthenticationMethods publickey
MaxAuthTries {max_auth_tries}
AuthorizedKeysFile /etc/ssh/authorized_keys/%u
X11Forwarding no
AllowTcpForwarding no
AllowAgentForwarding no
PermitTunnel no
PermitTTY {permit_tty}
PrintMotd no
Subsystem sftp internal-sftp
AllowUsers {allow_users}
{sftp_only_match}"""
    SSHD_CONFIG_PATH.write_text(config, encoding="utf-8")


def main() -> int:
    bind_address = read_env_bind_address()
    port = read_env_port("SFTP_PORT", 2222)
    user = read_env_user()
    uid = read_env_int("SFTP_UID", 1000)
    gid = read_env_int("SFTP_GID", 1000)
    max_auth_tries = read_env_positive_int("SFTP_MAX_AUTH_TRIES", 6)
    allow_root_login = read_env_bool("SFTP_ALLOW_ROOT_LOGIN", False)
    allow_ssh = read_env_bool("SFTP_ALLOW_SSH", False)
    authorized_key_path = Path(os.environ.get("SFTP_AUTHORIZED_KEY_PATH", "/run/volguard/authorized_key.pub"))
    home = Path("/home") / user
    shell = "/bin/sh" if allow_ssh else "/sbin/nologin"

    authorized_keys_text = read_authorized_keys(authorized_key_path)
    print_startup_info(
        bind_address=bind_address,
        port=port,
        user=user,
        uid=uid,
        gid=gid,
        max_auth_tries=max_auth_tries,
        allow_root_login=allow_root_login,
        allow_ssh=allow_ssh,
        authorized_key_path=authorized_key_path,
        authorized_keys_text=authorized_keys_text,
    )
    group_name = ensure_group(gid)
    ensure_user(user, uid, gid, group_name, home, shell)
    unlock_user_for_pubkey(user)
    if allow_root_login and user != "root":
        unlock_user_for_pubkey("root")
    prepare_filesystem(home, authorized_keys_text, user, uid, gid, allow_root_login, allow_ssh)
    run(["ssh-keygen", "-A"])
    write_sshd_config(user, home, max_auth_tries, allow_root_login, allow_ssh)

    os.execv("/usr/sbin/sshd", ["/usr/sbin/sshd", "-D", "-e", "-f", str(SSHD_CONFIG_PATH)])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
