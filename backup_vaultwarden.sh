#!/bin/bash

# ================= 脚本说明 =================
# 该脚本用于备份 Vaultwarden (Bitwarden_RS) 的 SQLite 数据库文件。
# 备份文件将存储在指定的 Syncthing 同步目录中，方便跨设备同步和存储。
# 备份过程使用 Docker 容器运行 SQLite 的热备份功能，确保在备份过程中数据库的一致性。
# 由于需要 chmod 和 chown 操作，建议将其放入 sudo crontab 中执行。
# 0 * * * * /home/yewfence/scripts/backup_vaultwarden.sh > /var/log/vault-backup.log 2>&1
# ================= 配置区域 =================
# 备份存放的根目录 (Syncthing 同步目录)
BACKUP_ROOT="/home/yewfence/syncthing-file/vw-data"
# 日志文件路径
LOG_FILE="$BACKUP_ROOT/backup.log"
# 锁文件路径
LOCK_FILE="/tmp/backup_vaultwarden.lock"

# Vaultwarden 数据在宿主机的路径
# 注意：确保这个路径和 docker-compose 中的挂载路径一致
DATA_DIR="/opt/docker_file/vaultwarden/vw-data"

# 备份文件名 (带时间戳)
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILENAME="db-$TIMESTAMP.sqlite3"
TEMP_BACKUP_NAME="db-backup-temp.sqlite3"

# ================= 函数定义 =================
# 定义日志函数，同时输出到屏幕和文件
log() {
    local level="$1"
    local message="$2"
    local time_str=$(date +"%Y-%m-%d %H:%M:%S")
    # 如果日志目录存在才写入文件
    if [ -d "$BACKUP_ROOT" ]; then
        echo "[$time_str] [$level] $message" | tee -a "$LOG_FILE"
    else
        echo "[$time_str] [$level] $message"
    fi
}

# 清理函数，用于退出时释放锁
cleanup() {
    rm -f "$LOCK_FILE"
}

# ================= 加锁防止并发 =================
if [ -f "$LOCK_FILE" ]; then
    log "WARN" "另一个备份任务正在运行，退出。"
    exit 0
fi

# 创建锁文件，并设置退出时自动清理
trap cleanup EXIT
echo $$ > "$LOCK_FILE"

# ================= 开始备份 =================
log "INFO" ">>> 开始执行 Vaultwarden 数据库备份任务..."

# 1. 检查备份目录是否存在，不存在则创建
if [ ! -d "$BACKUP_ROOT" ]; then
    mkdir -p "$BACKUP_ROOT"
    exit_code=$?
    if [ $exit_code -eq 0 ]; then
        log "INFO" "创建备份目录成功: $BACKUP_ROOT"
    else
        log "ERROR" "无法创建备份目录，脚本终止！"
        exit 1
    fi
fi

# 2. 检查 Docker 镜像是否存在
if ! docker image inspect nouchka/sqlite3 > /dev/null 2>&1; then
    log "INFO" "Docker 镜像 nouchka/sqlite3 不存在，正在拉取..."
    docker pull nouchka/sqlite3
    pull_exit_code=$?
    if [ $pull_exit_code -ne 0 ]; then
        log "ERROR" "拉取 Docker 镜像失败！请检查网络连接。"
        exit 1
    fi
fi

# 3. 执行 Docker 热备份
# 使用 nouchka/sqlite3 执行备份，生成一个临时文件在原数据目录
log "INFO" "正在执行 SQLite 热备份..."
docker run --rm \
  --volumes-from vaultwarden \
  nouchka/sqlite3 \
  /data/db.sqlite3 ".backup '/data/$TEMP_BACKUP_NAME'"
docker_exit_code=$?

# 检查 Docker 命令的退出状态码
if [ $docker_exit_code -eq 0 ]; then
    log "INFO" "SQLite 备份命令执行成功。"
else
    log "ERROR" "SQLite 备份命令执行失败！请检查容器状态或路径。"
    exit 1
fi

# 4. 移动并重命名文件
# 检查生成的临时文件是否存在
if [ -f "$DATA_DIR/$TEMP_BACKUP_NAME" ]; then
    mv "$DATA_DIR/$TEMP_BACKUP_NAME" "$BACKUP_ROOT/$BACKUP_FILENAME"
    mv_exit_code=$?
    if [ $mv_exit_code -eq 0 ]; then
        log "INFO" "备份文件已移动至: $BACKUP_ROOT/$BACKUP_FILENAME"
    else
        log "ERROR" "移动备份文件失败！"
        exit 1
    fi
else
    log "ERROR" "未找到生成的临时备份文件: $DATA_DIR/$TEMP_BACKUP_NAME"
    exit 1
fi

# 5. 修改所有者为 Syncthing 容器用户 (UID 1000)
chown 1000:1000 "$BACKUP_ROOT/$BACKUP_FILENAME"
log "INFO" "所有者已修改为 1000:1000 (Syncthing 容器用户)。"

# 6. 清理旧备份 (保留7天)
log "INFO" "开始清理 7 天前的旧备份..."
# 使用 wc -l 统计被删除的行数，只是为了日志好看
DELETE_COUNT=$(find "$BACKUP_ROOT" -type f -name "db-*.sqlite3" -mtime +7 -print -delete | wc -l)

if [ "$DELETE_COUNT" -gt 0 ]; then
    log "INFO" "清理完成，共删除了 $DELETE_COUNT 个旧备份文件。"
else
    log "INFO" "没有过期的备份文件需要清理。"
fi

log "INFO" "<<< 备份任务全部完成。"
echo "-----------------------------------------------------" >> "$LOG_FILE"