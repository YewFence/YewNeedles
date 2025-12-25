#!/bin/bash

# tmux 安装和配置脚本
# 作者: 叶晴樱

set -e

echo "=== tmux 安装脚本 ==="

# 检测包管理器并安装 tmux
install_tmux() {
    if command -v tmux &> /dev/null; then
        echo "tmux 已经安装了，版本: $(tmux -V)"
        return 0
    fi

    echo "正在安装 tmux..."

    if command -v apt &> /dev/null; then
        sudo apt update
        sudo apt install -y tmux
    elif command -v yum &> /dev/null; then
        sudo yum install -y tmux
    elif command -v dnf &> /dev/null; then
        sudo dnf install -y tmux
    elif command -v pacman &> /dev/null; then
        sudo pacman -S --noconfirm tmux
    elif command -v brew &> /dev/null; then
        brew install tmux
    elif command -v apk &> /dev/null; then
        sudo apk add tmux
    else
        echo "错误: 无法识别的包管理器，请手动安装 tmux"
        exit 1
    fi

    echo "tmux 安装完成！版本: $(tmux -V)"
}

# 添加 tmux 自动启动配置到 shell rc 文件
add_tmux_config() {
    local rc_file="$1"
    local shell_name="$2"

    if [ ! -f "$rc_file" ]; then
        echo "$shell_name 配置文件不存在: $rc_file，跳过"
        return 0
    fi

    # 检查是否已经配置过
    if grep -q "# tmux auto-start" "$rc_file"; then
        echo "$shell_name 已经配置过 tmux 自动启动，跳过"
        return 0
    fi

    echo "正在配置 $shell_name..."

    cat >> "$rc_file" << 'EOF'

# tmux auto-start
# 如果不在 tmux 中，且是交互式 shell，则自动启动 tmux
if command -v tmux &> /dev/null && [ -z "$TMUX" ] && [ -n "$PS1" ] && [[ ! "$TERM" =~ screen ]] && [[ ! "$TERM" =~ tmux ]]; then
    # 尝试附加到已有 session，如果没有则创建新的
    tmux attach-session -t default 2>/dev/null || tmux new-session -s default
fi
EOF

    echo "$shell_name 配置完成！"
}

# 主流程
main() {
    # 安装 tmux
    install_tmux

    # 配置 bashrc
    add_tmux_config "$HOME/.bashrc" "bash"

    # 配置 zshrc（如果存在）
    add_tmux_config "$HOME/.zshrc" "zsh"

    echo ""
    echo "=== 全部完成！ ==="
    echo "重新打开终端或执行 'source ~/.bashrc' (或 ~/.zshrc) 即可生效"
}

main
