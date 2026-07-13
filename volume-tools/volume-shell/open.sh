#!/usr/bin/env sh
#USAGE arg "<volume>" help="要挂载的现有 Docker 命名卷"
#USAGE complete "volume" run="./packages/mise-completions/volume-locations volumes '{{words[CURRENT] | escape_xml}}'"
#USAGE flag "--ro" help="只读挂载（默认）"
#USAGE flag "--rw --write" help="读写挂载"
#USAGE arg "[command]" help="在工具容器中执行的命令" var=#true var_min=0
set -eu

usage() {
	printf '%s\n' "usage: $0 <docker-volume> [--ro|--rw] [command...]"
	printf '%s\n' "example: $0 app_data --rw vim /volume/config.yml"
}

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
volume=""
mode="ro"

if [ "$#" -eq 0 ] && [ -n "${usage_volume:-}" ]; then
	set -- "$usage_volume"
	if [ "${usage_rw:-false}" = "true" ]; then
		set -- "$@" --rw
	elif [ "${usage_ro:-false}" = "true" ]; then
		set -- "$@" --ro
	fi
	if [ -n "${usage_command:-}" ]; then
		eval "set -- \"\$@\" $usage_command"
	fi
fi

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
