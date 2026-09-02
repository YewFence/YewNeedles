#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

read -rp "Wallpaper id or Workshop link: " input

id=""
url_pattern='[?&]id=([0-9]+)'
if [[ "$input" =~ ^[0-9]+$ ]]; then
  id="$input"
elif [[ "$input" =~ $url_pattern ]]; then
  id="${BASH_REMATCH[1]}"
fi

if [[ -z "$id" ]]; then
  echo "Could not parse a wallpaper id from the input" >&2
  exit 1
fi

echo "Downloading wallpaper $id ..."
WALLPAPER_ID="$id" docker compose --profile wallpaper run --rm wallpaper
