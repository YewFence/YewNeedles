#!/usr/bin/env sh
set -eu

usage() {
	printf '%s\n' "usage: $0 <docker-volume> [--ro|--rw] [command...]"
	printf '%s\n' "example: $0 app_data --rw vim /volume/config.yml"
}

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
volume=""
mode="ro"

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
		-h | --help)
			usage
			exit 0
			;;
		--)
			shift
			break
			;;
		*)
			if [ -z "$volume" ]; then
				volume="$1"
				shift
			else
				break
			fi
			;;
	esac
done

if [ -z "$volume" ]; then
	usage >&2
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

if [ "$#" -eq 0 ]; then
	set -- /bin/bash
fi

exec docker compose \
	-p volguard-volume-shell \
	-f "$script_dir/compose.yaml" \
	run --rm --build shell "$@"
