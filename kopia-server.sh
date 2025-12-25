#!/bin/bash
# ~/kopia-server.sh

# 配置变量
USERNAME="yewfence"
HOSTNAME="pacificyew"
IP_ADDRESS="100.118.101.41"
PORT="51515"
CONTROL_PASSWORD="kopia"

# 用法: ./kopia-server.sh {start|stop|kill|log}
case "$1" in
  start)
    KOPIA_SERVER_CONTROL_PASSWORD="$CONTROL_PASSWORD" \
    nohup kopia server start \
      --address=${IP_ADDRESS}:${PORT} \
      --insecure \
      --server-control-username=${USERNAME}@${HOSTNAME} \
      --without-password \
      > /tmp/kopia-server.log 2>&1 &
    echo "Started, pid: $!"
    ;;
  stop)
    kopia server shutdown \
      --address=http://${IP_ADDRESS}:${PORT} \
      --server-control-username=${USERNAME}@${HOSTNAME} \
      --server-control-password=${CONTROL_PASSWORD}
    ;;
  kill)
    pkill -9 -f "kopia server"
    ;;
  log)
    tail -f /tmp/kopia-server.log
    ;;
  *)
    echo "Usage: $0 {start|stop|kill|log}"
    ;;
  esac