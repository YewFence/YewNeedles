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

## Ansible 常见用法

下面这些命令按官方 Ansible 文档的常见用法整理过，并结合了这个仓库当前的 playbook 入口。

### 1. 检查 inventory 解析

```bash
ansible-inventory -i ansible/inventory.yml --graph
```

适合先确认：

- 主机是否进了预期的组
- `servers` / `devboxes` / `wsl` / `pve_vms` / capability groups 关系是否正确

### 2. 语法检查

```bash
ansible-playbook -i ansible/inventory.yml ansible/init-server.yml --syntax-check
ansible-playbook -i ansible/inventory.yml ansible/init-devbox.yml --syntax-check
ansible-lint --offline ansible/init-server.yml ansible/init-devbox.yml ansible/roles
```

这一步只检查 playbook 语法和变量引用是否明显有问题，不会真正改机器。

### 3. 目标主机确认

```bash
ansible-playbook -i ansible/inventory.yml ansible/init-server.yml --list-hosts
ansible-playbook -i ansible/inventory.yml ansible/init-devbox.yml --list-hosts
```

查看任务列表

```bash
ansible-playbook -i ansible/inventory.yml ansible/init-server.yml --list-tasks
```

### 4. 只跑单个主机或单个组

```bash
ansible-playbook -i ansible/inventory.yml ansible/init-server.yml --limit example_vps
ansible-playbook -i ansible/inventory.yml ansible/init-devbox.yml --limit example_pve_vm
ansible-playbook -i ansible/inventory.yml ansible/init-devbox.yml --limit pve_vms
```

`--limit` 很适合做增量验证，先打一台确认没问题，再扩大范围。

### 5. 用 check mode dry-run

```bash
ansible-playbook -i ansible/inventory.yml ansible/init-server.yml --check --diff
ansible-playbook -i ansible/inventory.yml ansible/init-devbox.yml --check --diff
```

- `--check` 表示尽量模拟执行，不真正落盘
- `--diff` 会显示模板或配置文件的差异
- 实际效果取决于具体模块是否支持 check mode，所以它更适合做“预演”，不是绝对保证

### 6. 传入 sudo 密码

使用 `-K`

`init-devbox.yml` 使用了 `become: true`。如果你的 devbox 连接用户不是 root，且 sudo 需要密码，可以这样跑：

```bash
ansible-playbook -K -i ansible/inventory.yml ansible/init-devbox.yml --limit example_pve_vm
```

### 7. 临时覆盖

适合做一次性试跑；长期配置还是应该写回 `inventory.yml` 或 `group_vars`。

```bash
ansible-playbook -i ansible/inventory.yml ansible/init-server.yml \
  --limit example_vps \
  --extra-vars "enable_docker=false enable_tailscale=false swap_size=4G"
```

```bash
ansible-playbook -i ansible/inventory.yml ansible/init-devbox.yml \
  --limit example_pve_vm \
  --extra-vars '{"dev_enable_docker": true, "mise_tools_extra": {"node": "22"}}'
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
