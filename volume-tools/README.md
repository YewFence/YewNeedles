# Volguard Tools

小工具，用于手动打开一个 Docker 命名卷，临时查看、编辑、通过 SFTP 访问里面的文件，或者在宿主机目录和命名卷之间同步内容。

这些模板默认都按只读方式挂载目标卷。需要修改文件时，必须显式传入 `--rw` 或 `--write`。

## 前置条件

需要本机能运行 Docker，并且支持 `docker compose` 命令。`volume-shell` 和 `volume-sftp` 的目标 Docker volume 必须已经存在，因为这两个模板都把卷声明为 external volume，不会自动创建新卷。`volume-copy` 会要求源 Docker volume 已经存在，目标 Docker volume 不存在时会按 Docker 默认行为自动创建；源宿主机目录必须已经存在，目标宿主机目录不存在时会自动创建。

可以先确认卷是否存在。

```sh
docker volume ls
```

## 打开工具容器

`volume-shell` 会启动一个轻量 Debian 工具容器，并把指定 Docker volume 挂载到 `/volume`。镜像默认只包含 `bash`、`vim`、`nano`、`curl`、`wget`、`tree` 和常见文件查看工具，额外工具可以通过 `EXTRA_APT_PACKAGES` 传给镜像构建。

只读打开。

```sh
volume-tools/volume-shell/open.sh app_data
```

读写打开并使用 `vim` 编辑文件。

```sh
volume-tools/volume-shell/open.sh app_data --rw vim /volume/config.yml
```

只运行一个命令并退出。

```sh
volume-tools/volume-shell/open.sh app_data -- find /volume -maxdepth 2 -type f
```

启动时临时加入自己需要的 apt 包。

```sh
EXTRA_APT_PACKAGES="jq sqlite3 ripgrep rsync" volume-tools/volume-shell/open.sh app_data
```

## 打开 SFTP 访问

`volume-sftp` 会启动一个 OpenSSH SFTP 容器，并把指定 Docker volume 暴露给一个受限的 SFTP 用户。默认监听 `127.0.0.1:2222`，默认用户是 `volguard`，默认只读挂载目标卷。

用环境变量传密码启动。

```sh
SFTP_PASSWORD=change-me volume-tools/volume-sftp/open.sh app_data
```

指定端口、用户和读写模式。

```sh
volume-tools/volume-sftp/open.sh app_data --rw --port 22222 --user volume --password change-me
```

连接 SFTP。

```sh
sftp -P 2222 volguard@127.0.0.1
```

查看运行状态。

```sh
volume-tools/volume-sftp/open.sh status
```

查看日志。

```sh
volume-tools/volume-sftp/open.sh logs
```

停止 SFTP 容器。

```sh
volume-tools/volume-sftp/open.sh stop
```

## 在目录和命名卷之间复制

`volume-copy` 会启动一个一次性 rsync 容器，并把源和目标分别挂载进去。参数会自动识别，已有宿主机目录会作为 bind mount，其他普通名称会作为 Docker 命名卷；目标是 `.`、`..`、`~`、以 `./`、`../`、`/`、`~/` 开头，或包含 `/`、`\` 的值时，会作为宿主机路径处理并自动创建目录。默认是合并复制，不删除目标中多出来的文件；需要目标和来源完全一致时，可以传入 `--delete`。

把宿主机目录复制到指定命名卷。如果目标卷不存在，Docker 会自动创建它。

```sh
mise run ops:copy-volume -- ./data app_data
```

把指定命名卷复制回宿主机目录。源卷必须已经存在，目标目录不存在时会自动创建。

```sh
mise run ops:copy-volume -- app_data ./data
```

把一个命名卷复制到另一个命名卷，可以用来重命名命名卷。

```sh
mise run ops:copy-volume -- app_data app_data_new
```

在两个宿主机目录之间复制。

```sh
mise run ops:copy-volume -- ./data ./data-copy
```

当名称刚好和当前目录里的文件夹重名时，可以用 `volume:` 或 `path:` 前缀消除歧义。

```sh
mise run ops:copy-volume -- volume:app_data path:./data
```

让目标目录和来源目录保持一致，并删除目标中来源没有的文件。

```sh
mise run ops:copy-volume -- ./data app_data --delete
```

## 安全边界

`volume-shell` 是一次性容器，退出后会自动删除容器。`volume-sftp` 是后台服务容器，需要手动执行 `tools/volume-sftp/open.sh stop` 停止。

SFTP 默认绑定到 `127.0.0.1`，只适合本机访问。如果要让局域网或公网访问，可以传入 `--bind 0.0.0.0`，但这会扩大暴露面，建议只在受控网络里临时使用。

读写模式和 `volume-copy` 都会直接修改 Docker volume 或宿主机路径里的文件。对生产卷操作前，建议先通过 Volguard 或其他方式完成备份，再进入 `--rw` 模式或执行同步。

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
| `volume-copy/compose.yaml` | 路径和命名卷同步的一次性容器 Compose 模板。 |
| `volume-copy/Dockerfile` | 基于 Alpine 和 rsync 的同步镜像。 |
| `volume-copy/entrypoint.sh` | 执行 rsync 的容器入口脚本。 |
| `volume-copy/volume_copy.py` | 解析源和目标并启动同步容器的便捷脚本。 |
