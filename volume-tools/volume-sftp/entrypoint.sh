#!/usr/bin/env sh
set -eu

: "${SFTP_USER:=volguard}"
: "${SFTP_UID:=1000}"
: "${SFTP_GID:=1000}"
: "${SFTP_PASSWORD:?set SFTP_PASSWORD}"

case "$SFTP_USER" in
	"" | *[!abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-]*)
		printf '%s\n' "invalid SFTP_USER, use letters, numbers, underscore or dash only" >&2
		exit 2
		;;
esac

case "$SFTP_UID" in
	"" | *[!0123456789]*)
		printf '%s\n' "invalid SFTP_UID, use a numeric uid" >&2
		exit 2
		;;
esac

case "$SFTP_GID" in
	"" | *[!0123456789]*)
		printf '%s\n' "invalid SFTP_GID, use a numeric gid" >&2
		exit 2
		;;
esac

home="/home/$SFTP_USER"
group_name="sftpusers"

if getent group "$SFTP_GID" >/dev/null 2>&1; then
	group_name="$(getent group "$SFTP_GID" | cut -d: -f1)"
else
	addgroup -g "$SFTP_GID" -S "$group_name"
fi

if ! id -u "$SFTP_USER" >/dev/null 2>&1; then
	adduser -D -H -h "$home" -s /sbin/nologin -u "$SFTP_UID" -G "$group_name" "$SFTP_USER"
fi

printf '%s:%s\n' "$SFTP_USER" "$SFTP_PASSWORD" | chpasswd

mkdir -p "$home/volume" /run/sshd
chown root:root "$home"
chmod 755 "$home"

ssh-keygen -A

cat >/etc/ssh/sshd_config <<EOF
Port 22
HostKey /etc/ssh/ssh_host_ed25519_key
HostKey /etc/ssh/ssh_host_rsa_key
PasswordAuthentication yes
PermitEmptyPasswords no
PermitRootLogin no
PubkeyAuthentication no
ChallengeResponseAuthentication no
UsePAM no
X11Forwarding no
AllowTcpForwarding no
AllowAgentForwarding no
PermitTunnel no
PrintMotd no
Subsystem sftp internal-sftp

Match User $SFTP_USER
    ChrootDirectory $home
    ForceCommand internal-sftp -d /volume
    PasswordAuthentication yes
EOF

exec /usr/sbin/sshd -D -e -f /etc/ssh/sshd_config
