#!/bin/bash
# =============================================================================
# Homebrew 一键安装配置脚本
# 安装 Homebrew、编译工具链、常用 CLI 工具，并配置 shell 环境
# 作者: 叶晴樱
# =============================================================================

set -euo pipefail

echo "=========================================="
echo "  Homebrew 自动安装配置脚本"
echo "=========================================="

# ---------- 1. 安装 Homebrew ----------
if command -v brew &> /dev/null; then
    echo "[1/5] Homebrew 已安装，跳过..."
else
    echo "[1/5] 正在安装 Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # 立即加载环境变量，后续步骤需要 brew 命令
    eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv bash)"
fi

# ---------- 2. 安装编译工具链 ----------
echo "[2/5] 安装编译工具链..."
sudo apt-get install -y build-essential
brew install gcc

# ---------- 3. 配置 Shell 环境 (.zshrc) ----------
echo "[3/5] 配置 .zshrc Homebrew 环境..."

BREW_BLOCK='# ===== Homebrew =====
eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv zsh)"
export HOMEBREW_NO_ENV_HINTS=1'

if [ -f "$HOME/.zshrc" ] && grep -q "Homebrew" "$HOME/.zshrc"; then
    echo "  .zshrc 中已有 Homebrew 配置，跳过..."
else
    printf '\n%s\n' "$BREW_BLOCK" >> "$HOME/.zshrc"
    echo "  已写入 .zshrc"
fi

# ---------- 4. 安装 CLI 工具 ----------
echo "[4/5] 安装 fzf、zoxide、zellij bat rg fastfetch..."
brew install fzf zoxide zellij bat rg fastfetch

# ---------- 5. 配置 zoxide ----------
echo "[5/6] 配置 .zshrc zoxide 环境..."

ZOXIDE_BLOCK='# ===== zoxide =====
eval "$(zoxide init zsh)"'

if [ -f "$HOME/.zshrc" ] && grep -q "zoxide" "$HOME/.zshrc"; then
    echo "  .zshrc 中已有 zoxide 配置，跳过..."
else
    printf '\n%s\n' "$ZOXIDE_BLOCK" >> "$HOME/.zshrc"
    echo "  已写入 .zshrc"
fi

# ---------- 6. 配置 Zellij 自动启动 ----------
echo "[6/6] 配置 Zellij 自动启动..."

ZELLIJ_BLOCK='# ===== Zellij 自动启动 =====
if [[ -z "$ZELLIJ" ]]; then
    zellij attach --create main
elif [[ "$ZELLIJ_PANE_ID" == "0" ]]; then
    /home/linuxbrew/.linuxbrew/bin/fastfetch --pipe false
fi'

for RC_FILE in "$HOME/.bashrc" "$HOME/.zshrc"; do
    if [ ! -f "$RC_FILE" ]; then
        echo "  $RC_FILE 不存在，跳过..."
        continue
    fi
    if grep -q "Zellij 自动启动" "$RC_FILE"; then
        echo "  $(basename "$RC_FILE") 中已有 Zellij 配置，跳过..."
    else
        printf '\n%s\n' "$ZELLIJ_BLOCK" >> "$RC_FILE"
        echo "  已写入 $(basename "$RC_FILE")"
    fi
done

echo ""
echo "=========================================="
echo "  安装完成！"
echo "=========================================="
echo ""
echo "重新登录或执行以下命令使配置生效:"
echo "  exec zsh"
echo ""
