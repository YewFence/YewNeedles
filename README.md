# yew-needles

一些简单的工具脚本

## volume-tools

docker named volume 的一些工具，包括 cp / mv / relabel / sftp 访问之类的，具体见 [volume-tools/README.md](volume-tools/README.md)

## mise-tasks

快速开始

```bash
mise trust
mise install
mise tasks
```

使用 [mise](https://mise.jdx.dev) 将一些可复用能力包装成 mise file tasks， 一般用 Python 写，或者 shell， 看情况

## zsh-plugins

一些简单的 zsh 插件，安装方式和功能介绍见 [zsh-plugins/README.md](zsh-plugins/README.md)

## GitHub Release RPM 安装

`mise-tasks/gh/install-latest-rpm` 用于单个仓库的安装流程，具体为查询 release、按架构和可选的 `pattern` 选择 RPM 资产、下载并安装。

`mise-tasks/gh/sync-release` 会读取 `apps.toml`、按 `--type` 指定的类型检查本地版本、决定哪些工具需要更新，然后逐个复用对应的安装流程。

RPM 会检查当前系统里已经安装的包版本，AppImage 会通过 Gear Lever 生成的桌面入口定位应用并检查 `X-AppImage-Version` 或同名 `.version` 文件，KPackage 会通过 `kpackagetool6` 定位 KDE 包并读取脚本维护的 `.gh-release-download-version`。

### 使用方法

```bash
# 安装单个仓库当前最新 release 的 RPM
mise run gh:install-latest-rpm -- farion1231/cc-switch
# 支持预览
mise run gh:install-latest-rpm -- farion1231/cc-switch --dry-run
# 按 `apps.toml` 检查并同步全部已定义应用
mise run gh:sync-release
# 支持预览
mise run gh:sync-release -- --dry-run
# 只同步 RPM
mise run gh:sync-release -- --type rpm
# 只同步 AppImage
mise run gh:sync-release -- --type appimage
# 只同步 KDE KPackage
mise run gh:sync-release -- --type kpackage
```

#### 配置示例

```toml
[[apps.rpm]]
# 显示名称
name = "example"
# 仓库地址，从 Github 找
repo = "owner/example"
# 本地 rpm 包名，用于检测本地版本
package_names = ["example"]
# 可选：资产名称子串，当有多个资产时用于选定需要的资产
# asset_pattern = "server"
# 可选：资产名称正则，会在子串过滤之后继续过滤
# asset_regex = "x86_64.*\\.rpm$"
# 给 Renovate 工作用的注释
# renovate: datasource=github-releases depName=owner/example versioning=semver
version = "v1.2.3"
# 指定的版本号，注意，上面那行 Renovate 注释需要和这个版本号贴着写

[[apps.appimage]]
name = "example"
repo = "owner/example"
# 匹配 Gear Lever 生成的桌面入口 Name、X-AppImage-Name 或 AppImage 文件名
app_name = "Example"
asset_regex = "x86_64.*\\.AppImage$"
# renovate: datasource=github-releases depName=owner/example versioning=semver
version = "v1.2.3"

[[apps.kpackage]]
name = "example-kde"
repo = "owner/example"
# KDE 插件标识
package_id = "org.example.kde"
# kpackagetool6 --type 使用的类型
package_type = "Plasma/Wallpaper"
asset_regex = "^example-kde-.*\\.zip$"
# renovate: datasource=github-releases depName=owner/example versioning=semver
version = "v1.2.3"
```

依赖 [Renovate](https://github.com/renovatebot/renovate) 检测 Github Release，通过自定义 regex manager 跟踪 [apps.toml](apps.toml) 里的 `version` 字段，上游发布新 release 时，Renovate 会开 PR 来更新，需要手动合并。

#### AppImage 版本记录

AppImage 本身没有一个所有应用都会提供的标准版本字段，Gear Lever 会尽量把应用桌面入口里的 `X-AppImage-Version` 带到 `~/.local/share/applications/*.desktop`，但不是每个 AppImage 都会内嵌这个字段。

如果第一次安装后 `mise run gh:sync-release -- --type appimage --dry-run` 提示找不到版本，可以在 Gear Lever 指向的 AppImage 文件旁边手动创建同名 `.version` 文件，内容写 `apps.toml` 里当前的 `version` 值即可，后续脚本更新时会自动维护这个文件并同步更新桌面入口里的 `X-AppImage-Version`。

同步任务会在命中版本时输出版本来源，来源可能是桌面入口里的 `X-AppImage-Version`，也可能是 AppImage 旁边的 `.version` 文件；如果 Gear Lever 没有安装过这个应用，或者两处都找不到版本，会输出高亮的 warning。

本地 AppImage 文件名沿用 Gear Lever 的命名规则，使用应用名而不是 release 资产名，空格转下划线，移除除字母数字、下划线和点以外的字符，再写成全小写的 `<app-name>.appimage`。

```bash
printf '%s\n' 'v1.2.3' > "$HOME/AppImages/example.appimage.version"
```

#### 局限性

不会自动 remove 从列表中删除的 rpm 包
