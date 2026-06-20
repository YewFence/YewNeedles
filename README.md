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

## GitHub Release RPM 安装

`mise-tasks/gh-install-latest-rpm` 用于单个仓库的安装流程，具体为查询 release、按架构和可选的 `pattern` 选择 RPM 资产、下载并安装。

`mise-tasks/gh-sync-release-rpms` 会读取 `tools.toml`、检查当前系统里已经安装的 RPM 版本、决定哪些工具需要更新，然后逐个复用单个安装流程。

### 使用方法

```bash
# 安装单个仓库当前最新 release 的 RPM
mise run gh-install-latest-rpm -- farion1231/cc-switch
# 支持预览
mise run gh-install-latest-rpm -- farion1231/cc-switch --dry-run
# 按 `tools.toml` 检查并同步全部已定义工具
mise run gh-sync-release-rpms
# 支持预览
mise run gh-sync-release-rpms -- --dry-run
```

#### 配置示例

```toml
[[github_release_rpms]]
# 显示名称
name = "example"
# 仓库地址，从 Github 找
repo = "owner/example"
# 本地 rpm 包名，用于检测本地版本
package_names = ["example"]
# 可选：资产名称范式，当有多个资产时用于选定需要的资产
# asset_pattern = "server"
# 给 Renovate 工作用的注释
# renovate: datasource=github-releases depName=owner/example versioning=semver
version = "v1.2.3"
# 指定的版本号，注意，上面那行 Renovate 注释需要和这个版本号贴着写
```

依赖 [Renovate](https://github.com/renovatebot/renovate) 检测 Github Release，通过自定义 regex manager 跟踪 [tools.toml](tools.toml) 里的 `version` 字段，上游发布新 release 时，Renovate 会直接对这些版本开 PR。
