#!/bin/bash
# =============================================================================
# Oh My Zsh 一键安装配置脚本
# 作者: 叶晴樱
# =============================================================================

set -e

echo "=========================================="
echo "  Oh My Zsh 自动安装配置脚本"
echo "=========================================="

# 检查是否安装了 zsh
if ! command -v zsh &> /dev/null; then
    echo "[1/6] 正在安装 zsh..."
    if command -v apt &> /dev/null; then
        sudo apt update && sudo apt install -y zsh
    elif command -v yum &> /dev/null; then
        sudo yum install -y zsh
    elif command -v dnf &> /dev/null; then
        sudo dnf install -y zsh
    elif command -v pacman &> /dev/null; then
        sudo pacman -S --noconfirm zsh
    else
        echo "错误: 无法识别的包管理器，请手动安装 zsh"
        exit 1
    fi
else
    echo "[1/6] zsh 已安装，跳过..."
fi

# 安装 Oh My Zsh
if [ ! -d "$HOME/.oh-my-zsh" ]; then
    echo "[3/6] 正在安装 Oh My Zsh..."
    sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended
else
    echo "[3/6] Oh My Zsh 已安装，跳过..."
fi

# 安装 zsh-autosuggestions 插件
if [ ! -d "${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins/zsh-autosuggestions" ]; then
    echo "[5/6] 正在安装 zsh-autosuggestions 插件..."
    git clone https://github.com/zsh-users/zsh-autosuggestions "${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins/zsh-autosuggestions"
else
    echo "[5/6] zsh-autosuggestions 已安装，跳过..."
fi

# 安装 zsh-syntax-highlighting 插件
if [ ! -d "${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins/zsh-syntax-highlighting" ]; then
    echo "[6/6] 正在安装 zsh-syntax-highlighting 插件..."
    git clone https://github.com/zsh-users/zsh-syntax-highlighting.git "${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins/zsh-syntax-highlighting"
else
    echo "[6/6] zsh-syntax-highlighting 已安装，跳过..."
fi

# 将 zsh 设为默认 shell
echo "正在将 zsh 设为默认 shell..."
if [ "$SHELL" != "$(which zsh)" ]; then
    chsh -s "$(which zsh)"
fi

echo ""
echo "=========================================="
echo "  安装完成！"
echo "=========================================="
echo ""
echo "重新登录或执行 'exec zsh' 启动 zsh"
echo ""
