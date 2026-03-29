#!/usr/bin/env sh
set -eu

echo "⚠️  风险提示：禁用 SSH 密码登录可能导致你被锁在服务器外。"
echo "建议先用密钥登录测试；并且在断开当前连接前，先新开一个窗口验证还能正常登录。"
echo ""
printf "确认继续请输入 yes："
read -r answer
if [ "$answer" != "yes" ]; then
  echo "已取消。"
  exit 0
fi

if [ "$(id -u)" -ne 0 ]; then
  echo "需要 root 权限，请用 sudo 运行。"
  exit 1
fi

SSHD_CONFIG="/etc/ssh/sshd_config"
DROPIN_DIR="/etc/ssh/sshd_config.d"
DROPIN_FILE="$DROPIN_DIR/99-disable-password.conf"

if [ -f "$SSHD_CONFIG" ]; then
  cp "$SSHD_CONFIG" "${SSHD_CONFIG}.bak.$(date +%Y%m%d%H%M%S)"
fi

use_dropin="false"
if [ -d "$DROPIN_DIR" ]; then
  use_dropin="true"
elif [ -f "$SSHD_CONFIG" ] && grep -Eq '^[[:space:]]*Include[[:space:]]+/etc/ssh/sshd_config\.d/\*\.conf' "$SSHD_CONFIG"; then
  use_dropin="true"
  mkdir -p "$DROPIN_DIR"
fi

if [ "$use_dropin" = "true" ]; then
  cat > "$DROPIN_FILE" <<'EOF'
# 启用密钥登录 & 禁用密码登录
PubkeyAuthentication yes
PasswordAuthentication no
ChallengeResponseAuthentication no
UsePAM yes
EOF
  echo "已写入：$DROPIN_FILE"
else
  if [ ! -f "$SSHD_CONFIG" ]; then
    echo "未找到 $SSHD_CONFIG，无法修改。"
    exit 1
  fi
  # 启用密钥登录
  if grep -Eq '^[[:space:]]*PubkeyAuthentication[[:space:]]+' "$SSHD_CONFIG"; then
    sed -i 's/^[[:space:]]*PubkeyAuthentication[[:space:]]\+.*/PubkeyAuthentication yes/' "$SSHD_CONFIG"
  else
    printf "\nPubkeyAuthentication yes\n" >> "$SSHD_CONFIG"
  fi

  # 禁用密码登录
  if grep -Eq '^[[:space:]]*PasswordAuthentication[[:space:]]+' "$SSHD_CONFIG"; then
    sed -i 's/^[[:space:]]*PasswordAuthentication[[:space:]]\+.*/PasswordAuthentication no/' "$SSHD_CONFIG"
  else
    printf "\nPasswordAuthentication no\n" >> "$SSHD_CONFIG"
  fi

  if grep -Eq '^[[:space:]]*ChallengeResponseAuthentication[[:space:]]+' "$SSHD_CONFIG"; then
    sed -i 's/^[[:space:]]*ChallengeResponseAuthentication[[:space:]]\+.*/ChallengeResponseAuthentication no/' "$SSHD_CONFIG"
  else
    printf "\nChallengeResponseAuthentication no\n" >> "$SSHD_CONFIG"
  fi
  echo "已更新：$SSHD_CONFIG"
fi

echo "检查配置..."
if command -v sshd >/dev/null 2>&1; then
  if ! sshd -t; then
    echo "sshd 配置校验失败，请检查后再重启服务。"
    exit 1
  fi
fi

echo "重载 SSH 服务..."
if command -v systemctl >/dev/null 2>&1; then
  systemctl reload sshd 2>/dev/null || systemctl reload ssh 2>/dev/null || systemctl restart sshd 2>/dev/null || systemctl restart ssh 2>/dev/null
else
  service sshd reload 2>/dev/null || service ssh reload 2>/dev/null || service sshd restart 2>/dev/null || service ssh restart 2>/dev/null
fi

echo "完成 ✅ 请务必在新窗口验证密钥登录成功后，再断开当前连接。"
