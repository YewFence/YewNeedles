# Volguard Tools

小工具，用于手动打开一个 Docker 命名卷，临时查看、编辑、通过 SFTP 访问里面的文件，在宿主机目录和命名卷之间同步内容，或者原地重建 volume 并更新它的 labels。

这些模板默认都按只读方式挂载目标卷。需要修改文件时，必须显式传入 `--rw` 或 `--write`。

## 前置条件

需要本机能运行 Docker，并且支持 `docker compose` 命令。`volume-shell` 和 `volume-sftp` 的目标 Docker volume 必须已经存在，因为这两个模板都把卷声明为 external volume，不会自动创建新卷。`volume-copy` 会要求源 Docker volume 已经存在，目标 Docker volume 不存在时会按 Docker 默认行为自动创建；源宿主机目录必须已经存在，目标宿主机目录不存在时会自动创建。`volume-relabel` 会要求目标 volume 已经存在、当前没有被任何容器占用，并且会先做一次临时备份再重建同名 volume。

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

`volume-sftp` 会启动一个 OpenSSH SFTP 容器，并把指定 Docker volume 暴露给一个受限的 SFTP 用户。默认监听 `127.0.0.1:2222`，默认用户是 `volguard`，默认只读挂载目标卷，并且只允许公钥登录。

使用当前用户的 `~/.ssh/authorized_keys` 启动。

```sh
volume-tools/volume-sftp/open.py app_data
```

指定端口、用户和读写模式。

```sh
volume-tools/volume-sftp/open.py app_data --rw --port 22222 --user volume
```

如果要使用其他公钥文件或 `authorized_keys` 文件，可以显式传入。

```sh
volume-tools/volume-sftp/open.py app_data --authorized-key ~/.ssh/id_ed25519.pub
```

也可以复制 `volume-sftp/.env.example` 为 `volume-sftp/.env`，至少设置 `VOLUME_NAME`，然后直接从 Compose 模板启动。

```sh
cd volume-tools/volume-sftp
docker compose up -d --build sftp
```

连接 SFTP。

```sh
sftp -P 2222 volguard@127.0.0.1
```

连接时使用和上面公钥配对的私钥。如果你的私钥不在默认位置，可以显式传 `-i`。

```sh
sftp -i ~/.ssh/id_ed25519 -P 2222 volguard@127.0.0.1
```

查看运行状态。

```sh
volume-tools/volume-sftp/open.py status
```

查看日志。

```sh
volume-tools/volume-sftp/open.py logs
```

停止 SFTP 容器。

```sh
volume-tools/volume-sftp/open.py stop
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

## 原地修改 volume labels

`volume-relabel` 会先把 volume 内容复制到一个临时备份 volume，然后删除原 volume，按原 driver 和 options 重建同名 volume，最后把数据再复制回去。因为 Docker 本地命名卷的 labels 不能直接原地更新，所以这个工具走的是“备份数据后重建元数据”的方式。执行前要求目标 volume 没有被任何运行中或已停止但仍挂载它的容器占用。

给现有 volume 增加或覆盖 labels。

```sh
mise run ops:relabel-volume -- app_data --label com.example.owner=ops --label com.example.env=prod
```

删除一个已有 label。

```sh
mise run ops:relabel-volume -- app_data --remove-label com.example.env
```

先清空所有 labels，再只写入自己指定的 labels。

```sh
mise run ops:relabel-volume -- app_data --clear-labels --label com.example.owner=ops
```

保留成功操作时产生的临时备份 volume，或者自己指定备份 volume 名称。

```sh
mise run ops:relabel-volume -- app_data --label com.example.owner=ops --keep-backup --backup-volume app_data_backup
```

如果你想直接跑 Compose 模板，不经过 `mise` task 也可以。最少要提供 `VOLUME_NAME`，改写 label 可以用 `VOLUME_LABELS_SET` 逐行写 `key=value`，也可以用 `VOLUME_LABELS_SET_JSON` 传一个 JSON 对象；删除 label 可以用 `VOLUME_LABELS_REMOVE` 逐行写 key，也可以用 `VOLUME_LABELS_REMOVE_JSON` 传一个 JSON 数组。`VOLUME_LABELS_CLEAR=true` 表示先清空已有 labels，`KEEP_BACKUP_VOLUME=true` 表示成功后也保留临时备份卷，`BACKUP_VOLUME_NAME` 可以固定备份卷名字，`COPY_HELPER_IMAGE` 可以覆盖内部数据复制所用镜像，`DOCKER_SOCKET_PATH` 可以覆盖 Docker socket 路径。`volume-tools/volume-relabel/.env.example` 里已经放了直接用 Compose 的示例。

```sh
VOLUME_NAME=app_data \
VOLUME_LABELS_SET=$'com.example.owner=ops\ncom.example.env=prod' \
docker compose -f volume-tools/volume-relabel/compose.yaml run --rm --build relabel
```

如果你更想把变量直接写进 `compose.yaml` 里，也可以把 `environment` 改成这样，然后直接跑 `docker compose -f volume-tools/volume-relabel/compose.yaml run --rm --build relabel`。

```yaml
environment:
  VOLUME_NAME: app_data
  VOLUME_LABELS_SET_JSON: '{"com.example.owner":"ops","com.example.env":"prod"}'
  VOLUME_LABELS_REMOVE_JSON: '["com.example.old"]'
  VOLUME_LABELS_CLEAR: "false"
  KEEP_BACKUP_VOLUME: "false"
  COPY_HELPER_IMAGE: volguard-volume-relabel:local
  TZ: Asia/Shanghai
```

## 安全边界

`volume-shell` 是一次性容器，退出后会自动删除容器。`volume-sftp` 是后台服务容器，需要手动执行 `volume-tools/volume-sftp/open.py stop` 停止。

SFTP 默认绑定到 `127.0.0.1`，只适合本机访问。如果要让局域网或公网访问，可以传入 `--bind 0.0.0.0`，但这会扩大暴露面，建议只在受控网络里临时使用。现在密码登录已经关闭，认证依赖你挂进去的公钥文件和本地对应私钥。

读写模式、`volume-copy` 和 `volume-relabel` 都会直接影响 Docker volume 或宿主机路径里的数据。对生产卷操作前，建议先通过 Volguard 或其他方式完成备份，再进入 `--rw` 模式、执行同步或重建 labels。

## 目录说明

| 路径 | 用途 |
| --- | --- |
| `volume-shell/compose.yaml` | 工具容器的 Compose 模板。 |
| `volume-shell/Dockerfile` | 基于 Debian 的工具镜像。 |
| `volume-shell/open.sh` | 打开工具容器的便捷脚本。 |
| `volume-sftp/compose.yaml` | SFTP 容器的 Compose 模板。 |
| `volume-sftp/Dockerfile` | SFTP 镜像。 |
| `volume-sftp/.env.example` | 直接通过 Compose 启动 SFTP 时使用的环境变量示例。 |
| `volume-sftp/entrypoint.py` | SFTP 用户、Chroot 和 SSHD 配置入口。 |
| `volume-sftp/open.py` | 启动、停止、查看 SFTP 容器的 Python 主脚本。 |
| `volume-copy/compose.yaml` | 路径和命名卷同步的一次性容器 Compose 模板。 |
| `volume-copy/Dockerfile` | 基于 Alpine 和 rsync 的同步镜像。 |
| `volume-copy/entrypoint.sh` | 执行 rsync 的容器入口脚本。 |
| `volume-copy/volume_copy.py` | 解析源和目标并启动同步容器的便捷脚本。 |
| `volume-relabel/compose.yaml` | 原地重建同名 volume 并更新 labels 的 Compose 模板。 |
| `volume-relabel/Dockerfile` | 包含 Docker CLI、Python 和 rsync 的重建镜像。 |
| `volume-relabel/.env.example` | 直接通过 Compose 启动 relabel 时使用的环境变量示例。 |
| `volume-relabel/entrypoint.py` | 执行备份、重建、恢复和回滚的容器入口。 |
| `volume-relabel/volume_relabel.py` | 解析参数并启动 relabel 容器的便捷脚本。 |
