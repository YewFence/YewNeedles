# zsh-completions-sync

`zsh-completions-sync` 是一个小型 zsh 补全脚本同步工具，用来把全局工具补全和项目工具补全分开放置，避免所有补全脚本都混在 `~/.zsh/completions` 里。

## 快速开始

后续发布标签后，可以通过 `mise` 安装这个 Python CLI 包。

```toml
[tools]
"pipx:git+https://github.com/YewFence/YewNeedles.git@v0.1.0#subdirectory=packages/zsh-completions-sync" = "latest"
```

安装后，全局补全通过下面的命令生成到 `~/.zsh/completions`。

```sh
zsh-completions-sync global
```

项目补全通过下面的命令生成到当前项目的 `.completions/zsh`。

```sh
zsh-completions-sync project
```

使用项目级 mise enter hook 运行如下脚本来加载项目级别的补全。

```zsh
zsh-completions-sync project

fpath=(
  "$PWD/.completions/zsh"
  "$HOME/.zsh/completions"
  $fpath
)

autoload -Uz compinit
compinit
```

## 背景

当前把所有补全脚本手动塞进 `~/.zsh/completions`，会让全局补全和项目内 `mise` 工具版本混在一起。对于 `gh`、`starship`、`git` 这类全局工具，全局维护一份补全就够了。对于 `kubectl`、`helm`、`uv`、`pnpm` 这类可能随项目版本变化的工具，更合理的方式是把项目特有补全放在项目里。

## 目标

1. 全局补全目录只维护全局工具和稳定工具的补全。

2. 项目特有工具的补全生成到项目内目录。

3. 通过 `mise` 的 hook 或 task 触发补全生成。

4. zsh 初始化只需要把当前项目补全目录和全局补全目录加入 `fpath`。

5. 实现保持轻量，不做版本化缓存，不做每次切目录同步，不做复杂垃圾回收。

## 非目标

1. 不自动识别所有工具的补全生成方式。

2. 不为每个工具版本保存历史补全缓存。

3. 不解决同一个已启动 shell 在多个项目之间频繁切换后补全函数已经加载的问题。

4. 不替换工具命令本身。

## 核心思路

把补全分成两层。

全局层放在用户目录 `~/.zsh/completions`，用于 `mise`、`gh`、`starship`、`git` 这类全局工具。这个目录由用户手动通过命令刷新。

项目层放在项目目录，输出目录默认为 `.completions/zsh/_<tools>`。项目进入时可以通过 `mise` 的 `enter` hook 来加载脚本。

因为项目补全目录在前面，所以当前目录启动的新 shell 会优先使用项目内的 `_kubectl`、`_helm` 等补全。没有项目补全时，再回退到全局补全或系统补全。

## 命令设计

只需要一个很小的命令，命名为 `zsh-completions-sync`。

```text
zsh-completions-sync project
zsh-completions-sync global
zsh-completions-sync list
```

`project` 在当前项目内生成补全脚本，输出目录默认为 `.completions/zsh/_<tools>`。

`global` 生成全局工具补全，输出目录默认为 `~/.zsh/completions/_<tools>`。

`list` 美观地列出当前合并后注册表支持的工具、作用域、补全来源，以及每个工具的配置从哪些注册表层加载。可以通过 `--scope global` 或 `--scope project` 只查看某个作用域的工具。

如果后续确实需要清理，可以加 `clean`，逻辑很简单，删除各个路径的补全脚本就好。

## 工具注册表

需要定义一个补全来源注册表，因为不同工具生成补全脚本或发布补全脚本的方式不统一。

注册表分三个级别：

1. 包内默认注册表
2. 用户配置
3. 项目配置

自动合并，优先级从高到低为：项目配置 > 用户配置 > 包内默认注册表。

用户配置优先读取 `~/.config/zsh-completions-sync/registry.toml`，也兼容读取 `~/.config/zsh-completions-sync-registry.toml`。如果两个文件同时存在，只读取 `~/.config/zsh-completions-sync/registry.toml`，并输出 warn 提示忽略另一个文件。设置了 `XDG_CONFIG_HOME` 时，用户配置路径会跟随 `XDG_CONFIG_HOME`。

项目配置优先读取当前项目的 `.config/zsh-completions-sync.toml`，也兼容读取 `.zsh-completions-sync.toml`。如果两个文件同时存在，只读取 `.config/zsh-completions-sync.toml`，并输出 warn 提示忽略另一个文件。

格式如下所示：

```toml
[tools.mise]
scopes = ["global"]
command = ["mise", "completion", "zsh"]

[tools.local-tool]
scopes = ["project"]
file = "$PWD/completions/_local-tool"

[tools.installing-tool]
scopes = ["project"]
check = "installing-tool"
pre-command = ["installing-tool", "completion", "install", "--shell", "zsh", "--output", ".completions/vendor/_installing-tool"]
file = ".completions/vendor/_installing-tool"

[tools.remote-tool]
scopes = ["global"]
file = "https://example.com/completions/_remote-tool"

[tools.git-tool]
scopes = ["global", "project"]
file = "git+https://github.com/example/tool.git//completions/_tool?ref=v1.2.3"

[tools.git-tool-alt]
scopes = ["project"]
file = { git = "https://github.com/example/tool.git", path = "completions/_tool", ref = "v1.2.3" }
```

`scopes = ["global"]` 表示这些工具补全只在执行 `zsh-completions-sync global` 时生成到全局目录。

`scopes = ["project"]` 表示这些工具补全只在执行 `zsh-completions-sync project` 时生成到项目目录。一个工具可以同时声明多个作用域。

每个工具需要配置一个补全来源。`command` 表示运行命令并从标准输出读取补全脚本。`file` 表示直接读取补全脚本，支持普通本地路径、`file://` 路径、HTTP 或 HTTPS 地址、`git+仓库//路径?ref=版本` 字符串，以及 `{ git = "...", path = "...", ref = "..." }` 形式的 Git 文件来源。本地路径会展开环境变量和 `~`，Git 来源的 `ref` 可以省略，省略时读取默认分支。

如果同时配置了 `file` 和 `command`，会优先使用 `file`。`pre-command` 可以在读取补全来源前先运行一个命令，适合那些只能通过安装型命令把补全写到文件的工具；这种情况下可以让 `pre-command` 生成固定路径的补全文件，再用 `file` 读取这个文件。`pre-command` 失败会输出 warn 并跳过该工具，不会覆盖已有补全。

`check` 用来判断当前工具是否可用。没有配置时默认检查工具名本身，也就是 `[tools.mise]` 默认检查 `mise` 是否在 `PATH` 中。可以配置成字符串来检查另一个可执行文件，也可以配置成命令数组来运行自定义检查，还可以配置成 `false` 来关闭检查。`check` 不通过时会静默跳过，所以工具不存在时不会把缺失当成错误。

## 项目生成逻辑

`zsh-completions-sync project` 的行为应该很保守。

1. 读取注册表中 `project` 分组的工具。

2. 如果工具没找到就静默跳过。

3. 如果工具生效，就先运行可选的 `pre-command`，再读取 `command` 或 `file` 配置的补全来源。

4. 生成结果先写临时文件，成功后移动到 `.completions/zsh/_<tools>`。

## 全局生成逻辑

`zsh-completions-sync global` 只处理注册表中 `global` 分组的工具。

先执行 `check` 判断工具是否可用，然后运行可选的 `pre-command`，再读取对应补全来源。

全局输出目录只保存一份当前全局环境对应的补全脚本。

## 错误处理

如果 `pre-command` 失败、补全命令失败，或者补全文件读取失败，不覆盖已有补全文件。

如果 `check` 判断工具不存在，静默失败。

如果对应目录不存在，命令自动创建。
