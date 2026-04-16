#!/bin/bash

# ================= 配置区域 =================
# 【重要】请修改为您实际的域名，并确保已解析到本机 IP
DOMAIN="exit.example.com"

# 【重要】请修改用于申请证书的邮箱 (ZeroSSL 需要邮箱注册)
ACME_EMAIL="yourname@example.com"

# 端口配置
SS_PORT=40000
TUIC_PORT=8443
# ===========================================

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 变量初始化
UUID=""
SS_PASSWORD=""
TUIC_PASSWORD=""
TARGET_DIR="$HOME/proxy"

# 最终报告函数
final_report() {
    # 只有当凭据已生成时才打印报告
    if [[ -n "$UUID" && -n "$SS_PASSWORD" && -n "$TUIC_PASSWORD" ]]; then
        echo -e "\n${YELLOW}================ 配置信息汇总 ================${NC}"
        echo -e "配置文件路径 : ${TARGET_DIR}"
        echo -e "域名 (DOMAIN): ${YELLOW}${DOMAIN}${NC}"
        echo -e "注册邮箱     : ${YELLOW}${ACME_EMAIL}${NC}"
        echo -e "--------------------------------------------"
        echo -e "${BLUE}[Shadowsocks]${NC}"
        echo -e "  端口     : ${YELLOW}${SS_PORT}${NC}"
        echo -e "  协议     : 2022-blake3-aes-128-gcm"
        echo -e "  密码     : ${YELLOW}${SS_PASSWORD}${NC}"
        echo -e "--------------------------------------------"
        echo -e "${BLUE}[TUIC]${NC}"
        echo -e "  端口     : ${YELLOW}${TUIC_PORT}${NC}"
        echo -e "  UUID     : ${YELLOW}${UUID}${NC}"
        echo -e "  密码     : ${YELLOW}${TUIC_PASSWORD}${NC}"
        echo -e "  SNI      : ${YELLOW}${DOMAIN}${NC}"
        echo -e "${YELLOW}==============================================${NC}"
        
        # 检查最终状态
        if [[ $1 -eq 0 ]]; then
            echo -e "${GREEN}>>> 部署成功 <<<${NC}"
            echo -e "提示: 您可以使用 'docker compose logs -f' 查看运行日志。"
        else
            echo -e "${RED}>>> 部署未完成，请检查上方错误日志 <<<${NC}"
            echo -e "注意：配置文件已生成（如果步骤已执行到那里），您可以手动修复问题后继续。"
        fi
    fi
}

# 错误处理函数
error_exit() {
    echo -e "${RED}错误: $1${NC}"
    # 调用报告函数，传入非0状态码表示失败
    final_report 1
    exit 1
}

# 1. 初始化检查
echo -e "${BLUE}>>> 正在检查环境依赖...${NC}"

# 检查必要命令
for cmd in docker curl socat openssl; do
    if ! command -v "$cmd" &> /dev/null; then
        error_exit "${YELLOW}未找到命令 '$cmd'。${NC}"
    fi
done

# 检查 Docker Compose
if docker compose version &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker compose"
elif docker-compose version &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker-compose"
else
    error_exit "未找到 docker compose 或 docker-compose。"
fi

# 2. 生成随机凭据
echo -e "${BLUE}>>> 正在生成随机凭据...${NC}"
# 生成 UUID
if [ -f /proc/sys/kernel/random/uuid ]; then
    UUID=$(cat /proc/sys/kernel/random/uuid)
else
    UUID=$(uuidgen) || error_exit "无法生成 UUID"
fi

# 生成强随机密码 (16位 Hex)
SS_PASSWORD=$(openssl rand -hex 16)
TUIC_PASSWORD=$(openssl rand -hex 16)

# 3. 打印配置并等待确认
echo -e "\n${YELLOW}================ 确认部署配置 ================${NC}"
echo -e "域名 (DOMAIN)       : ${GREEN}${DOMAIN}${NC}"
echo -e "申请邮箱 (EMAIL)    : ${GREEN}${ACME_EMAIL}${NC}"
echo -e "Shadowsocks 端口    : ${GREEN}${SS_PORT}${NC}"
echo -e "TUIC 端口           : ${GREEN}${TUIC_PORT}${NC}"
echo -e "----------------------------------------------"
echo -e "生成的 UUID         : ${GREEN}${UUID}${NC}"
echo -e "生成的 SS 密码      : ${GREEN}${SS_PASSWORD}${NC}"
echo -e "生成的 TUIC 密码    : ${GREEN}${TUIC_PASSWORD}${NC}"
echo -e "${YELLOW}==============================================${NC}"
echo -e "${RED}注意: 请确保域名 '${DOMAIN}' 已经解析到本机 IP。${NC}"
echo -e "${RED}注意: 证书申请需要占用 80 端口，请确保 80 端口未被占用。${NC}"
echo -e "${RED}>>> 请务必确认您已执行过以下命令之一：${NC}"
echo -e "${GREEN}sudo setcap 'cap_net_bind_service=+ep' $(readlink -f $(which socat))${NC}"
echo -e "${GREEN}sudo setcap 'cap_net_bind_service=+ep'${NC}"
echo -e "如果不执行此命令，证书申请将因 socat 无法绑定 80 端口而失败。"
echo

read -p "确认开始执行吗？(y/n): " confirm
if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
    echo "已取消。"
    exit 0
fi

# 4. 准备目录结构
CERT_DIR="$TARGET_DIR/certs"

echo -e "${BLUE}>>> 创建目录结构: ${TARGET_DIR} ...${NC}"
mkdir -p "$CERT_DIR"

# 5. 生成配置文件 (已提前)
echo -e "${BLUE}>>> 生成 config.json 和 compose.yaml ...${NC}"

# 写入 config.json
cat > "$TARGET_DIR/config.json" <<EOF
{
  "log": { "level": "info" },
  "inbounds": [
    {
      "type": "shadowsocks",
      "tag": "ss2022-in",
      "listen": "::",
      "listen_port": ${SS_PORT},
      "method": "2022-blake3-aes-128-gcm",
      "password": "${SS_PASSWORD}"
    },
    {
      "type": "tuic",
      "tag": "tuic-in",
      "listen": "::",
      "listen_port": ${TUIC_PORT},
      "users": [
        {
          "uuid": "${UUID}",
          "password": "${TUIC_PASSWORD}"
        }
      ],
      "tls": {
        "enabled": true,
        "server_name": "${DOMAIN}",
        "alpn": ["h3"],
        "certificate_path": "/etc/sing-box/certs/fullchain.pem",
        "key_path": "/etc/sing-box/certs/privkey.pem"
      }
    }
  ],
  "outbounds": [
    { "type": "direct" }
  ]
}
EOF

# 写入 compose.yaml
cat > "$TARGET_DIR/compose.yaml" <<EOF
services:
  singbox:
    image: ghcr.io/sagernet/sing-box:latest
    container_name: sing-box
    restart: unless-stopped
    network_mode: host
    volumes:
      - ./config.json:/etc/sing-box/config.json
      - ./certs:/etc/sing-box/certs:ro
    command: run -c /etc/sing-box/config.json
    logging:
      driver: "journald"
      options:
        tag: "{{.Name}}"
EOF

# 6. 证书申请 (acme.sh)
if [[ -f "$CERT_DIR/privkey.pem" && -f "$CERT_DIR/fullchain.pem" ]]; then
    echo -e "${GREEN}>>> 检测到已有证书 ($CERT_DIR)，跳过申请和安装流程。${NC}"
else
    echo -e "${BLUE}>>> 安装 acme.sh 并申请证书...${NC}"

    # 安装 acme.sh (如果未安装)
    if [ ! -f "$HOME/.acme.sh/acme.sh" ]; then
        echo -e "${BLUE}>>> 使用邮箱 ${ACME_EMAIL} 注册 acme.sh ...${NC}"
        curl https://get.acme.sh | sh -s email="${ACME_EMAIL}"
        if [ $? -ne 0 ]; then error_exit "acme.sh 安装失败"; fi
    fi

    # 申请证书 (Standalone 模式)
    echo -e "${BLUE}>>> 正在申请证书 (Standalone模式，需占用80端口)...${NC}"
    "$HOME/.acme.sh/acme.sh" --issue --standalone -d "$DOMAIN"
    if [ $? -ne 0 ]; then
        error_exit "证书申请失败！请检查：\n1. 域名是否正确解析到本机 IP\n2. 80 端口是否开放且未被占用\n3. socat 是否具有绑定 80 端口的权限"
    fi

    # 安装证书到目标目录
    echo -e "${BLUE}>>> 安装证书到 ${CERT_DIR} ...${NC}"
    "$HOME/.acme.sh/acme.sh" --install-cert -d "$DOMAIN" \
        --key-file       "$CERT_DIR/privkey.pem"  \
        --fullchain-file "$CERT_DIR/fullchain.pem" \
        --reloadcmd      "cd $TARGET_DIR && $DOCKER_COMPOSE_CMD restart singbox"

    if [ ! -f "$CERT_DIR/privkey.pem" ] || [ ! -f "$CERT_DIR/fullchain.pem" ]; then
        error_exit "证书文件未成功安装到指定目录。"
    fi
fi

# 7. 启动服务
echo -e "${BLUE}>>> 启动 Sing-box 服务...${NC}"
cd "$TARGET_DIR" || error_exit "无法进入目录 $TARGET_DIR"

# 尝试停止旧容器（如果存在）
$DOCKER_COMPOSE_CMD down 2>/dev/null

# 启动新容器
$DOCKER_COMPOSE_CMD up -d

if [ $? -ne 0 ]; then
    error_exit "Docker Compose 启动失败。"
fi

# 8. 成功结束
# 调用报告函数，传入0状态码表示成功
final_report 0
