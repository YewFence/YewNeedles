#!/bin/bash

# --- 配置区域 ---
DOMAIN="mikan.chaco-anaconda.ts.net"
CERT_DIR="/opt/docker_file/gateway/ssl/tailscale" # 宿主机上的证书挂载目录
CRT_NAME="mikan.chaco-anaconda.ts.net.crt"
KEY_NAME="mikan.chaco-anaconda.ts.net.key"
CONTAINER_NAME="nginx"
# ----------------

# 1. 申请/续期证书
# --cert-file 和 --key-file 参数可以直接指定输出位置，覆盖旧文件
tailscale cert --cert-file "$CERT_DIR/$CRT_NAME" --key-file "$CERT_DIR/$KEY_NAME" "$DOMAIN"

# 2. 检查命令是否执行成功
if [ $? -eq 0 ]; then
    echo "[$(date)] Tailscale cert check finished."

    # 3. 重载 Nginx (让新证书生效)
    # 只有当 tailscale cert 成功运行后才重载，虽然它不做更细的变更检测，但 reload 开销很小
    docker exec "$CONTAINER_NAME" nginx -s reload
    echo "[$(date)] Nginx reloaded."
else
    echo "[$(date)] Error: Failed to renew Tailscale cert."
fi