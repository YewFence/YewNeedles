#!/bin/bash
set -euo pipefail

# 初始化服务器脚本
# 该脚本用于在新服务器上进行基础环境配置，包括系统更新、工具安装、用户创建等。
# 请以 root 用户身份运行此脚本。
# 适用于 Debian/Ubuntu 系统。
# 常用配置
USERNAME="yewfence"
SSH_PORT=22
SWAP=2G

echo "=========================================="
echo "即将执行的配置预览:"
echo "用户: $USERNAME"
echo "SSH 端口: $SSH_PORT"
echo "Swap 大小: $SWAP"
echo "=========================================="
read -r -p "请确认是否继续执行? [y/N]: " CONFIRM_RUN
case "$CONFIRM_RUN" in
    y|Y) echo "确认执行，开始初始化...";;
    *) echo "已取消执行。"; exit 1;;
esac

# 1. 基础环境更新与工具安装
echo "Step 1: 更新系统并安装基础工具..."
apt update && apt upgrade -y
apt install -y curl wget git vim htop ufw unzip tar socat

# 2. 开启 BBR
echo "Step 2: 开启 Google BBR..."
if ! grep -q "net.ipv4.tcp_congestion_control = bbr" /etc/sysctl.conf; then
    echo "net.core.default_qdisc = fq" >> /etc/sysctl.conf
    echo "net.ipv4.tcp_congestion_control = bbr" >> /etc/sysctl.conf
    sysctl -p
fi
echo "BBR 已开启。"

# 3. 配置 Swap
echo "Step 3: 配置 Swap 交换空间..."
if [ $(free | awk '/^Swap:/ {print $2}') -eq 0 ]; then
    fallocate -l $SWAP /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    # 调整 Swappiness，让系统尽量先用物理内存
    if ! grep -q "vm.swappiness" /etc/sysctl.conf; then
        echo "vm.swappiness=10" >> /etc/sysctl.conf
    fi
    sysctl -p
    echo "Swap ($SWAP) 配置完成。"
else
    echo "Swap 已存在，跳过创建。"
fi

# 4. 配置 UFW 防火墙
echo "Step 4: 配置基础防火墙..."
ufw default deny incoming
ufw default allow outgoing
ufw allow $SSH_PORT/tcp comment "SSH"
ufw allow 80/tcp comment "HTTP"
ufw allow 443/tcp comment "HTTPS"
echo "y" | ufw enable
echo "防火墙已启用。"

# 5. 安装 Docker & Docker Compose
echo "Step 5: 安装 Docker..."
curl -fsSL https://get.docker.com | sh

# 6. 配置 Docker 日志轮转 (防止日志占满硬盘)
echo "Step 6: 配置 Docker 日志策略..."
mkdir -p /etc/docker
cat > /etc/docker/daemon.json <<EOF
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "50m",
    "max-file": "3"
  }
}
EOF
systemctl restart docker

# 7. 配置 Vim
cat > ~/.vimrc <<EOF
" 核心配置：解决 Docker 挂载文件热更新失效问题
set backupcopy=yes

" 基础开发体验优化
syntax on           " 语法高亮
set number          " 显示行号
set ruler           " 显示光标位置
set autoindent      " 自动缩进
set mouse=a         " 允许鼠标点击跳转(在某些终端好用)
set tabstop=2       " Tab 宽度
set shiftwidth=2    " 缩进宽度
set expandtab       " Tab 转空格 (Python/Yaml 友好)
EOF

# 8. 安装 Tailscale
echo "Step 9: 安装 Tailscale..."
curl -fsSL https://tailscale.com/install.sh | sh

# 9. 导入 Termius SSH ID
mkdir -p ~/.ssh && chmod 700 ~/.ssh
SSH_KEY=$(curl -fs https://sshid.io/yewfence)
if [ -n "$SSH_KEY" ] && ! grep -qF "$SSH_KEY" ~/.ssh/authorized_keys 2>/dev/null; then
    echo "$SSH_KEY" >> ~/.ssh/authorized_keys
    echo "SSH 公钥已导入。"
else
    echo "SSH 公钥已存在或获取失败，跳过。"
fi

echo "Step 11: 创建用户 $USERNAME 并配置权限..."

# 1. 创建用户 (如果不存在)
if id "$USERNAME" &>/dev/null; then
    echo "用户 $USERNAME 已存在，跳过创建。"
else
    # -m 创建家目录, -s 指定shell, -G 加入sudo组
    useradd -m -s /bin/bash -G sudo "$USERNAME"
    USER_CREATED=true
    echo "用户 $USERNAME 创建成功。"
fi

# 2. 加入 Docker 用户组 (免 sudo 运行 docker)
usermod -aG docker "$USERNAME"
echo "已将 $USERNAME 加入 docker 用户组。"

# 3. 设置为 Tailscale operator (免 sudo 管理 Tailscale)
tailscale set --operator="$USERNAME"
echo "已将 $USERNAME 设为 Tailscale operator。"

# 3. 复制 Root 的 SSH 公钥
# 确保目标 .ssh 目录存在
USER_SSH_DIR="/home/$USERNAME/.ssh"
mkdir -p "$USER_SSH_DIR"

# 复制 authorized_keys (如果 root 有配置的话)
if [ -f /root/.ssh/authorized_keys ]; then
    cp /root/.ssh/authorized_keys "$USER_SSH_DIR/authorized_keys"
    echo "Root 公钥已复制给 $USERNAME。"
else
    echo "⚠️ 警告: 未找到 /root/.ssh/authorized_keys，请稍后手动添加公钥。"
    touch "$USER_SSH_DIR/authorized_keys"
fi

# 4. 关键：修正权限 (权限不对 SSH 会拒绝登录)
chown -R "$USERNAME:$USERNAME" "/home/$USERNAME"
chmod 700 "$USER_SSH_DIR"
chmod 600 "$USER_SSH_DIR/authorized_keys"

# 5. 设置一个随机密码 (仅在新建用户时设置，避免重复执行覆盖已有密码)
if [ "${USER_CREATED:-false}" = true ]; then
    RANDOM_PASS=$(openssl rand -base64 12)
    echo "$USERNAME:$RANDOM_PASS" | chpasswd
fi

# 6. 复制 Vim 配置给新用户
cp ~/.vimrc "/home/$USERNAME/.vimrc"
chown "$USERNAME:$USERNAME" "/home/$USERNAME/.vimrc"

echo "=========================================="
echo "✅ 用户 $USERNAME 配置完成！"
if [ "${USER_CREATED:-false}" = true ]; then
    echo "🔑 临时密码: $RANDOM_PASS"
    echo "   (请务必复制保存，sudo 需要用到)"
else
    echo "ℹ️ 用户已存在，密码未更改。"
fi
echo ""
echo "测试流程:"
echo "1. 运行: ssh $USERNAME@<服务器IP> / 或者 su - $USERNAME"
echo "2. 验证: docker ps (应不需要 sudo)"
echo "3. 验证: sudo apt update (输入上面密码)"
echo "4. 可选的：安装 homebrew: /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)""
echo "=========================================="

echo "=========================================="
echo "✅ 初始化完成！你的 Yew 新基座已就绪。"
echo "Docker 版本: $(docker -v)"
echo "当前内存情况 (含 Swap):"
free -h
echo "=========================================="
