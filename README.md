# YewNeedles

个人 IaC 仓库，正在从零散 shell 脚本迁移到 Ansible Playbook / Role 结构。

当前主要管理两类环境：

- `servers`：公网 VPS / 生产环境
- `devboxes`：PVE VM / WSL 开发环境

## 当前入口

### 生产环境

使用 `ansible/init-server.yml` 初始化 VPS：

- 共享基线：系统升级、基础包、用户、SSH key、Vim 配置
- SSH 加固：显式双开关控制是否关闭密码登录
- BBR / Swap / UFW / Docker / Tailscale

```bash
ansible-playbook -i ansible/inventory.yml ansible/init-server.yml
```

### 开发环境

使用 `ansible/init-devbox.yml` 初始化 PVE VM / WSL：

- 共享基线：基础包、用户、Vim 配置
- Oh My Zsh 与常用插件
- mise 安装、shell 激活与由 Ansible 变量生成的全局 `config.toml`
- zellij 与自动 attach 配置

`mise` 角色会渲染远端 `~/.config/mise/config.toml`，默认安装一组通用 CLI。
当 `dev_enable_zellij: true` 时，会额外把 `zellij` 和 `fastfetch` 写进这份全局配置，
然后统一执行 `mise install`。

```bash
ansible-playbook -i ansible/inventory.yml ansible/init-devbox.yml
```

## Inventory 约定

参考 [`ansible/inventory.example.yml`](ansible/inventory.example.yml)：

- `servers` 放 VPS / 生产机
- `devboxes` 放所有开发环境
- `wsl`、`pve_vms` 表达平台差异
- `docker_enabled`、`tailscale_enabled` 表达能力差异
- 默认值放在 `ansible/group_vars/*.yml`，inventory 主要描述主机和分组关系

SSH 密码登录关闭建议分两步做：

1. 先跑基线，确保 root 或目标用户的 `authorized_keys` 已就位。
2. 在确认第二个窗口可以正常密钥登录后，再设置：

```yaml
ssh_disable_password_auth: true
ssh_disable_password_auth_confirmed: true
```

## 目录结构

```text
ansible/
  group_vars/
    servers.yml
    devboxes.yml
    docker_enabled.yml
    tailscale_enabled.yml
  init-server.yml
  init-devbox.yml
  inventory.example.yml
  roles/
    common/
    ssh_hardening/
    bbr/
    swapfile/
    ufw/
    docker_host/
    tailscale/
    mise/
    oh_my_zsh/
    zellij/
```

## 旧脚本状态

仓库根目录下的 `*.sh` 仍然保留，主要作为迁移参考和临时兜底入口。
新增能力优先放进 Ansible，而不是继续扩展旧脚本。

## Devbox 建模建议

不要按 “需要 Docker / 不需要 Docker / 需要 Tailscale / 不需要 Tailscale” 直接拆四套组。
优先使用正交分组：

- 平台组：`wsl`、`pve_vms`
- 能力组：`docker_enabled`、`tailscale_enabled`

例外情况再放到 `host_vars/<hostname>.yml`，而不是把所有差异都写回 inventory。
