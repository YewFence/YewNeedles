#!/bin/bash
# =============================================================================
# Oh My Zsh + Powerlevel10k 一键安装配置脚本
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

# 安装 git（如果没有的话）
if ! command -v git &> /dev/null; then
    echo "[2/6] 正在安装 git..."
    if command -v apt &> /dev/null; then
        sudo apt install -y git
    elif command -v yum &> /dev/null; then
        sudo yum install -y git
    elif command -v dnf &> /dev/null; then
        sudo dnf install -y git
    elif command -v pacman &> /dev/null; then
        sudo pacman -S --noconfirm git
    fi
else
    echo "[2/6] git 已安装，跳过..."
fi

# 安装 Oh My Zsh
if [ ! -d "$HOME/.oh-my-zsh" ]; then
    echo "[3/6] 正在安装 Oh My Zsh..."
    sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended
else
    echo "[3/6] Oh My Zsh 已安装，跳过..."
fi

# 安装 Powerlevel10k 主题
if [ ! -d "${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/themes/powerlevel10k" ]; then
    echo "[4/6] 正在安装 Powerlevel10k 主题..."
    git clone --depth=1 https://github.com/romkatv/powerlevel10k.git "${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/themes/powerlevel10k"
else
    echo "[4/6] Powerlevel10k 已安装，跳过..."
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

# 备份现有的 .zshrc
if [ -f "$HOME/.zshrc" ]; then
    echo "备份现有的 .zshrc 到 .zshrc.backup..."
    cp "$HOME/.zshrc" "$HOME/.zshrc.backup"
fi

# 写入新的 .zshrc 配置
echo "正在写入 .zshrc 配置..."
cat > "$HOME/.zshrc" << 'EOF'
# Enable Powerlevel10k instant prompt. Should stay close to the top of ~/.zshrc.
# Initialization code that may require console input (password prompts, [y/n]
# confirmations, etc.) must go above this block; everything else may go below.
if [[ -r "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh" ]]; then
  source "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh"
fi

# Path to your Oh My Zsh installation.
export ZSH="$HOME/.oh-my-zsh"

# Set name of the theme to load
ZSH_THEME="powerlevel10k/powerlevel10k"

# Which plugins would you like to load?
plugins=(git zsh-autosuggestions zsh-syntax-highlighting docker-compose docker)

source $ZSH/oh-my-zsh.sh

# User configuration

# --- 常用别名 ---
# 让 ls 自动带颜色
alias ls='ls --color=auto'
alias grep='grep --color=auto'
alias fgrep='fgrep --color=auto'
alias egrep='egrep --color=auto'
alias ll='ls -alF'
alias la='ls -A'
alias l='ls -CF'

# 防止 rm 误删
alias rm='rm -i'

# To customize prompt, run `p10k configure` or edit ~/.p10k.zsh.
[[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh
EOF

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
echo "请执行以下操作:"
echo "1. 重新登录或执行 'exec zsh' 启动 zsh"
echo "2. 首次启动会自动运行 p10k configure 配置向导"
echo "   (如果没有自动运行，可以手动执行 'p10k configure')"
echo ""
echo "提示: 为了获得最佳体验，请确保终端使用支持 Powerline 的字体"
echo "推荐字体: MesloLGS NF, Fira Code, JetBrains Mono 等"
echo ""
