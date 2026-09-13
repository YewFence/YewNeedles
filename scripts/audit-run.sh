#!/usr/bin/env bash
# audit-run.sh — 把任意命令丢进"HOME 写时拷贝"沙箱执行，事后打印精确的文件变更清单。
#
# 用法: audit-run.sh <命令...>
#   例: audit-run.sh gh skill install owner/repo skill-name
#
# 原理: bwrap 将整个根目录只读绑定，把 $HOME 用 overlayfs 覆盖，
#       命令的所有写入落进 /tmp 下的 upper 目录；真实 HOME 全程零接触。
#       命令结束后 upper 目录保留在磁盘上，它就是一份完整的变更证据。

set -euo pipefail

if [[ $# -eq 0 ]]; then
  echo "用法: $0 <命令...>" >&2
  exit 2
fi

SESSION=$(mktemp -d "/tmp/audit-run.XXXXXX")
UPPER="$SESSION/upper"
WORK="$SESSION/work"
mkdir -p "$UPPER" "$WORK"

echo "==> 沙箱会话: $SESSION"
echo "==> 执行: $*"
echo

set +e
bwrap \
  --ro-bind / / \
  --dev /dev \
  --proc /proc \
  --tmpfs /tmp \
  --tmpfs /var/tmp \
  --tmpfs /run/user/"$(id -u)" \
  --overlay-src "$HOME" --overlay "$UPPER" "$WORK" "$HOME" \
  --new-session \
  "$@"
rc=$?
set -e

echo
echo "==> 退出码: $rc"
echo "==> 真实 HOME 未被修改（写入全部捕获在 upper 层）"
echo

if [[ -n "$(find "$UPPER" -mindepth 1 -print -quit 2>/dev/null)" ]]; then
  echo "==> 变更清单（路径相对真实 \$HOME）:"
  find "$UPPER" -mindepth 1 -printf '%y %p\n' | sed "s#^\(.\) $UPPER/\(.*\)#\1 ~/\2#"
else
  echo "==> 变更清单: （空）该命令没有写 \$HOME"
fi

echo
echo "==> upper 层保留在: $UPPER"
echo "   审计完成后自行清理: rm -r '$SESSION'"
