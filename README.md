# YewNeedles

个人服务器运维自动化脚本集，用于简化服务器初始化、备份、证书管理等常见运维任务。

## 脚本列表

| 脚本 | 功能 |
|------|------|
| `init-server.sh` | 新服务器一键初始化（系统优化、Docker 安装、安全配置等） |
| `init-zsh.sh` | Oh My Zsh + Powerlevel10k 一键安装配置 |
| `init-tmux.sh` | tmux 自动安装和配置 |
| `backup_vaultwarden.sh` | Vaultwarden 数据库自动备份 |
| `kopia-server.sh` | Kopia 备份服务器管理 |
| `ts-certs.sh` | Tailscale 证书自动续期 |
| `rename-docker.sh` | Docker Compose 文件批量重命名 |

## 脚本说明

### init-server.sh

新服务器初始化脚本，一键完成以下配置：

- 系统更新和基础工具安装
- 开启 BBR 拥塞控制算法
- 配置 4GB Swap 分区
- 配置 UFW 防火墙（开放 22/80/443 端口）
- 安装 Docker 和 Docker Compose
- 终端美化和 Vim 配置
- 创建用户并配置 SSH 公钥

```bash
sudo bash init-server.sh
```

### init-zsh.sh

Oh My Zsh 一键安装配置：

- 安装 Oh My Zsh 框架
- 安装 Powerlevel10k 主题
- 安装 zsh-autosuggestions 和 zsh-syntax-highlighting 插件
- 配置常用别名

```bash
bash init-zsh.sh
```

### init-tmux.sh

tmux 自动安装和配置：

- 自动检测包管理器并安装 tmux
- 配置自动启动 tmux session

```bash
bash init-tmux.sh
```

### backup_vaultwarden.sh

Vaultwarden 数据库热备份脚本：

- 使用 Docker 容器执行 SQLite 热备份
- 备份到 Syncthing 同步目录
- 自动清理 7 天前的旧备份
- 支持 crontab 定时执行

```bash
# 添加到 crontab（每小时执行一次）
0 * * * * /path/to/backup_vaultwarden.sh >> /var/log/vw-backup.log 2>&1
```

### kopia-server.sh

Kopia 备份服务器管理：

```bash
./kopia-server.sh start  # 启动服务器
./kopia-server.sh stop   # 停止服务器
./kopia-server.sh kill   # 强制停止
./kopia-server.sh log    # 查看日志
```

### ts-certs.sh

Tailscale 证书自动续期脚本，续期后自动重载 Nginx：

```bash
# 添加到 crontab（每月执行一次）
0 0 1 * * /path/to/ts-certs.sh
```

### rename-docker.sh

将旧版 `docker-compose.yml` 重命名为新版 `compose.yaml`：

```bash
./rename-docker.sh /path/to/docker/projects        # 执行重命名
./rename-docker.sh /path/to/docker/projects --dry  # 预览模式
```

## 环境要求

- Linux（Debian/Ubuntu 为主）
- Bash 4.0+
- root 或 sudo 权限（部分脚本）

## 许可证

MIT
