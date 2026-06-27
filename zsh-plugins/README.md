# zsh-plugins

这个目录放了一些自用的 zsh 插件。

## 插件

- `sudo/ee-2-sudo.zsh` 按 `Alt + s` 给当前命令添加或移除 `sudo`
- `space/shortcut-2-space.zsh` 按 `Alt + i` 给当前命令添加或移除开头空格，并启用 `HIST_IGNORE_SPACE`
- `exec-command-completion/exec-completion.zsh` 给 `infisical run -- ` 这类命令包装器补全后续命令

## 安装

推荐使用 antidote

### 使用 [antidote](https://github.com/mattmc3/antidote)

在插件列表里添加需要的插件文件。Antidote 默认从 Github 下载插件，所以不需要指定完整仓库地址

```text
# zsh-plugins.txt
YewFence/YewNeedles path:zsh-plugins/sudo/ee-2-sudo.zsh
YewFence/YewNeedles path:zsh-plugins/space/shortcut-2-space.zsh
YewFence/YewNeedles path:zsh-plugins/exec-command-completion/exec-completion.zsh
```

### 手动安装

克隆仓库。

```zsh
git clone git@github.com:YewFence/YewNeedles.git ~/.local/share/yew-needles
```

在 `.zshrc` 里 source 需要的插件。

```zsh
source ~/.local/share/yew-needles/zsh-plugins/sudo/ee-2-sudo.zsh
source ~/.local/share/yew-needles/zsh-plugins/space/shortcut-2-space.zsh
source ~/.local/share/yew-needles/zsh-plugins/exec-command-completion/exec-completion.zsh
```
