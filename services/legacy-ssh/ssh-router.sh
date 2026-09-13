#!/usr/bin/env bash
# 通过 ssh-legacy 容器登录 192.168.8.1（dropbear，仅支持 ssh-rsa 主机密钥）
# 宿主机 Fedora 的 OpenSSL 被 crypto-policies 禁了 SHA-1 签名验证，故借用容器里的干净 OpenSSL。
# 会话加密仍为 curve25519 + aes256-ctr + hmac-sha2-256，不降低会话安全。
set -euo pipefail
exec podman run -it --rm --network=host \
  -v ssh-router-kh:/root/.ssh \
  ssh-legacy \
  ssh -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedAlgorithms=+ssh-rsa \
  root@192.168.8.1 "$@"
