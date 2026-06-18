# yew-needles

一些简单的工具脚本

# volume-tools

docker named volume 的一些工具脚本

# mise-tasks

使用 mise 将一些可复用能力包装成 mise file tasks

新增任务时，跨平台能力优先使用 Python。如果只依赖标准库，直接写纯 Python 脚本；如果需要第三方 Python 依赖，统一使用 uv 运行脚本和管理依赖。明显依赖类 Unix 语义的任务可以继续使用 shell，例如修复执行权限这类只在 Unix 上成立的操作。

# zsh-plugins

一些自用的 zsh 插件，安装方式见 [zsh-plugins/README.md](zsh-plugins/README.md)

## 文档

- [Fedora Boot Backup Restore Guide](docs/fedora-boot-restore.md)
