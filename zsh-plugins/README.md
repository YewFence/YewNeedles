# zsh-plugins

这个目录放了一些自用的 zsh 插件。

## 插件

- `sudo/ee-2-sudo.zsh` 按 `Alt + s` 给当前命令添加或移除 `sudo`
- `space/shortcut-2-space.zsh` 按 `Alt + i` 给当前命令添加或移除开头空格，并启用 `HIST_IGNORE_SPACE`

## 安装

仓库地址是 `github.com:YewFence/YewNeedles`。

### 使用 zinit

安装 `ee-2-sudo`。

```zsh
zinit ice pick"zsh-plugins/sudo/ee-2-sudo.zsh"
zinit light github.com:YewFence/YewNeedles
```

安装 `shortcut-2-space`。

```zsh
zinit ice pick"zsh-plugins/space/shortcut-2-space.zsh"
zinit light github.com:YewFence/YewNeedles
```

两个都安装。

```zsh
zinit ice multisrc"zsh-plugins/sudo/ee-2-sudo.zsh zsh-plugins/space/shortcut-2-space.zsh"
zinit light github.com:YewFence/YewNeedles
```

### 使用 antidote

在插件列表里添加需要的插件文件。

```zsh
YewFence/YewNeedles path:zsh-plugins/sudo/ee-2-sudo.zsh
YewFence/YewNeedles path:zsh-plugins/space/shortcut-2-space.zsh
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
```
