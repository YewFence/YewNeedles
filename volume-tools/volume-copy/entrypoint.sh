#!/usr/bin/env sh
set -eu

: "${COPY_DELETE:=false}"

sync_dir() {
	source_dir="$1"
	target_dir="$2"

	if [ ! -d "$source_dir" ]; then
		printf '%s\n' "source directory does not exist: $source_dir" >&2
		exit 2
	fi

	if [ ! -d "$target_dir" ]; then
		printf '%s\n' "target directory does not exist: $target_dir" >&2
		exit 2
	fi

	delete_arg=""
	case "$COPY_DELETE" in
		true) delete_arg="--delete" ;;
		false) ;;
		*)
			printf '%s\n' "invalid COPY_DELETE, use true or false" >&2
			exit 2
			;;
	esac

	rsync -aH --numeric-ids $delete_arg "$source_dir"/ "$target_dir"/
}

sync_dir /source /target
