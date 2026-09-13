# zsh-plugins

这个目录放了一些自用的 zsh 插件。

## 插件


- ~`exec-command-completion/exec-completion.zsh` 给 `infisical run -- ` 这类命令包装器补全后续命令~ 似乎不可用，回头再研究

## 安装

推荐使用 antidote

### 使用 [antidote](https://github.com/mattmc3/antidote)

在插件列表里添加需要的插件文件。Antidote 默认从 Github 下载插件，所以不需要指定完整仓库地址

```text
# zsh-plugins.txt
YewFence/YewNeedles path:zsh-plugins/exec-command-completion/exec-completion.zsh
```

### 手动安装

克隆仓库。

```zsh
git clone git@github.com:YewFence/YewNeedles.git ~/.local/share/yew-needles
```

在 `.zshrc` 里 source 需要的插件。

```zsh
source ~/.local/share/yew-needles/zsh-plugins/exec-command-completion/exec-completion.zsh
```
