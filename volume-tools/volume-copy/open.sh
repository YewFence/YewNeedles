#!/usr/bin/env sh
set -eu

usage() {
	printf '%s\n' "usage: $0 path-to-volume <host-path> <docker-volume> [--delete]"
	printf '%s\n' "usage: $0 volume-to-path <docker-volume> <host-path> [--delete]"
	printf '%s\n' "example: $0 path-to-volume ./data app_data"
	printf '%s\n' "example: $0 volume-to-path app_data ./data --delete"
}

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
direction=""
host_path=""
volume=""
delete="false"

if [ "$#" -eq 0 ]; then
	usage >&2
	exit 2
fi

direction="$1"
shift

case "$direction" in
	path-to-volume)
	host_path="${1:-}"
	volume="${2:-}"
	shift "$(( $# < 2 ? $# : 2 ))"
	;;
	volume-to-path)
	volume="${1:-}"
	host_path="${2:-}"
	shift "$(( $# < 2 ? $# : 2 ))"
	;;
	-h | --help)
	usage
	exit 0
	;;
	*)
	printf '%s\n' "invalid direction $direction" >&2
	usage >&2
	exit 2
	;;
esac

while [ "$#" -gt 0 ]; do
	case "$1" in
		--delete)
			delete="true"
			shift
			;;
		-h | --help)
			usage
			exit 0
			;;
		*)
			printf '%s\n' "unexpected argument $1" >&2
			usage >&2
			exit 2
			;;
	esac
done

if [ -z "$host_path" ] || [ -z "$volume" ]; then
	usage >&2
	exit 2
fi

case "$direction" in
	path-to-volume | volume-to-path) ;;
	*)
		printf '%s\n' "invalid direction $direction" >&2
		exit 2
		;;
esac

if [ ! -d "$host_path" ]; then
	printf '%s\n' "host path must be an existing directory: $host_path" >&2
	exit 2
fi

case "$host_path" in
	/*) absolute_host_path="$host_path" ;;
	*) absolute_host_path="$(CDPATH= cd -- "$host_path" && pwd)" ;;
esac

if [ "$direction" = "volume-to-path" ] && ! docker volume inspect "$volume" >/dev/null 2>&1; then
	printf '%s\n' "docker volume does not exist: $volume" >&2
	exit 2
fi

export COPY_DIRECTION="$direction"
export COPY_DELETE="$delete"
export HOST_PATH="$absolute_host_path"
export VOLUME_NAME="$volume"

exec docker compose \
	-p volguard-volume-copy \
	-f "$script_dir/compose.yaml" \
	run --rm --build copy
