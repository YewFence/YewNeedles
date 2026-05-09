# Volguard Tools

小工具，用于手动打开一个 Docker 命名卷，临时查看、编辑或通过 SFTP 访问里面的文件。

这些模板默认都按只读方式挂载目标卷。需要修改文件时，必须显式传入 `--rw` 或 `--write`。

## 前置条件

需要本机能运行 Docker，并且支持 `docker compose` 命令。目标 Docker volume 必须已经存在，因为两个模板都把卷声明为 external volume，不会自动创建新卷。

可以先确认卷是否存在。

```sh
docker volume ls
```

## 打开工具容器

`volume-shell` 会启动一个轻量 Debian 工具容器，并把指定 Docker volume 挂载到 `/volume`。镜像默认只包含 `bash`、`vim`、`nano`、`curl`、`wget`、`tree` 和常见文件查看工具，额外工具可以通过 `EXTRA_APT_PACKAGES` 传给镜像构建。

只读打开。

```sh
tools/volume-shell/open.sh app_data
```

读写打开并使用 `vim` 编辑文件。

```sh
tools/volume-shell/open.sh app_data --rw vim /volume/config.yml
```

只运行一个命令并退出。

```sh
tools/volume-shell/open.sh app_data -- find /volume -maxdepth 2 -type f
```

启动时临时加入自己需要的 apt 包。

```sh
EXTRA_APT_PACKAGES="jq sqlite3 ripgrep rsync" tools/volume-shell/open.sh app_data
```

## 打开 SFTP 访问

`volume-sftp` 会启动一个 OpenSSH SFTP 容器，并把指定 Docker volume 暴露给一个受限的 SFTP 用户。默认监听 `127.0.0.1:2222`，默认用户是 `volguard`，默认只读挂载目标卷。

用环境变量传密码启动。

```sh
SFTP_PASSWORD=change-me tools/volume-sftp/open.sh app_data
```

指定端口、用户和读写模式。

```sh
tools/volume-sftp/open.sh app_data --rw --port 22222 --user volume --password change-me
```

连接 SFTP。

```sh
sftp -P 2222 volguard@127.0.0.1
```

查看运行状态。

```sh
tools/volume-sftp/open.sh status
```

查看日志。

```sh
tools/volume-sftp/open.sh logs
```

停止 SFTP 容器。

```sh
tools/volume-sftp/open.sh stop
```

## 安全边界

`volume-shell` 是一次性容器，退出后会自动删除容器。`volume-sftp` 是后台服务容器，需要手动执行 `tools/volume-sftp/open.sh stop` 停止。

SFTP 默认绑定到 `127.0.0.1`，只适合本机访问。如果要让局域网或公网访问，可以传入 `--bind 0.0.0.0`，但这会扩大暴露面，建议只在受控网络里临时使用。

读写模式会直接修改 Docker volume 里的文件。对生产卷操作前，建议先通过 Volguard 或其他方式完成备份，再进入 `--rw` 模式。

## 目录说明

| 路径 | 用途 |
| --- | --- |
| `volume-shell/compose.yaml` | 工具容器的 Compose 模板。 |
| `volume-shell/Dockerfile` | 基于 Debian 的工具镜像。 |
| `volume-shell/open.sh` | 打开工具容器的便捷脚本。 |
| `volume-sftp/compose.yaml` | SFTP 容器的 Compose 模板。 |
| `volume-sftp/Dockerfile` | SFTP 镜像。 |
| `volume-sftp/entrypoint.sh` | SFTP 用户、Chroot 和 SSHD 配置入口。 |
| `volume-sftp/open.sh` | 启动、停止、查看 SFTP 容器的便捷脚本。 |
