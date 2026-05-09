#!/usr/bin/env sh
set -eu

usage() {
	printf '%s\n' "usage: $0 [start] <docker-volume> [--ro|--rw] [--port 2222] [--bind 127.0.0.1] [--user volguard] [--password secret] [--uid 1000] [--gid 1000]"
	printf '%s\n' "usage: $0 stop|logs|status"
	printf '%s\n' "example: SFTP_PASSWORD=secret $0 app_data --port 2222"
}

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
action="start"

case "${1:-}" in
	start | up)
		action="start"
		shift
		;;
	stop | down)
		action="stop"
		shift
		;;
	logs)
		action="logs"
		shift
		;;
	status | ps)
		action="status"
		shift
		;;
esac

compose() {
	docker compose -p volguard-volume-sftp -f "$script_dir/compose.yaml" "$@"
}

case "$action" in
	stop)
		exec compose down --remove-orphans
		;;
	logs)
		exec compose logs -f sftp
		;;
	status)
		exec compose ps
		;;
esac

volume=""
mode="ro"
port="${SFTP_PORT:-2222}"
bind_address="${SFTP_BIND_ADDRESS:-127.0.0.1}"
user="${SFTP_USER:-volguard}"
password="${SFTP_PASSWORD:-}"
uid="${SFTP_UID:-1000}"
gid="${SFTP_GID:-1000}"

while [ "$#" -gt 0 ]; do
	case "$1" in
		--ro)
			mode="ro"
			shift
			;;
		--rw | --write)
			mode="rw"
			shift
			;;
		--port)
			port="${2:?missing value for --port}"
			shift 2
			;;
		--bind)
			bind_address="${2:?missing value for --bind}"
			shift 2
			;;
		--user)
			user="${2:?missing value for --user}"
			shift 2
			;;
		--password)
			password="${2:?missing value for --password}"
			shift 2
			;;
		--uid)
			uid="${2:?missing value for --uid}"
			shift 2
			;;
		--gid)
			gid="${2:?missing value for --gid}"
			shift 2
			;;
		-h | --help)
			usage
			exit 0
			;;
		*)
			if [ -z "$volume" ]; then
				volume="$1"
				shift
			else
				printf '%s\n' "unexpected argument $1" >&2
				usage >&2
				exit 2
			fi
			;;
	esac
done

if [ -z "$volume" ]; then
	usage >&2
	exit 2
fi

if [ -z "$password" ]; then
	printf '%s\n' "set SFTP_PASSWORD or pass --password before starting sftp" >&2
	exit 2
fi

case "$mode" in
	ro) VOLUME_READ_ONLY=true ;;
	rw) VOLUME_READ_ONLY=false ;;
	*)
		printf '%s\n' "invalid mode $mode" >&2
		exit 2
		;;
esac

export VOLUME_NAME="$volume"
export VOLUME_READ_ONLY
export SFTP_PORT="$port"
export SFTP_BIND_ADDRESS="$bind_address"
export SFTP_USER="$user"
export SFTP_PASSWORD="$password"
export SFTP_UID="$uid"
export SFTP_GID="$gid"

compose up -d --build sftp

connect_host="$bind_address"
if [ "$connect_host" = "0.0.0.0" ]; then
	connect_host="127.0.0.1"
fi

printf '%s\n' "sftp is listening on $bind_address:$port"
printf '%s\n' "connect with: sftp -P $port $user@$connect_host"
printf '%s\n' "stop with: $0 stop"
