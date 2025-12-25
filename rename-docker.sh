#!/bin/bash
set -euo pipefail

TARGET_DIR="${1:-.}"
DRY_RUN="${2:-}"

echo "🚀 开始在 $TARGET_DIR 中搜索 Compose 文件..."

find "$TARGET_DIR" -maxdepth 2 -type f \( -name "docker-compose.yml" -o -name "docker-compose.yaml" \) -print0 | while IFS= read -r -d '' old_file; do
    dir=$(dirname "$old_file")
    new_file="$dir/compose.yaml"

    if [ -f "$new_file" ]; then
        echo "⚠️  跳过: $dir 已存在 compose.yaml"
    elif [ "$DRY_RUN" = "--dry-run" ]; then
        echo "🔍 预览: $old_file -> $new_file"
    else
        echo "✅ 重命名: $old_file -> $new_file"
        mv -- "$old_file" "$new_file"
    fi
done

echo "✨ 完成！"
