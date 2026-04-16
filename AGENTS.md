# AGENTS

## Scope

This repository is moving from standalone shell scripts toward Ansible-based IaC.
It manages two distinct target classes:

- `servers`: public VPS / production hosts
- `devboxes`: PVE VMs and WSL development environments

When extending the repo, prefer new Ansible roles and playbooks over adding more ad-hoc bootstrap scripts.

## Layout

- `ansible/init-server.yml`: production-oriented bootstrap for `servers`
- `ansible/init-devbox.yml`: development bootstrap for `devboxes`
- `ansible/roles/common`: shared baseline used by both environments
- `ansible/roles/ssh_hardening`: SSH auth policy and password-login shutdown
- `ansible/roles/homebrew`: Homebrew install plus shellenv setup for devboxes
- `ansible/roles/oh_my_zsh`: zsh / Oh My Zsh setup for devboxes
- `ansible/roles/zellij`: zellij install and shell autostart for devboxes
- top-level `*.sh`: legacy scripts kept as migration references until their behavior is fully absorbed by Ansible

## Conventions

- Keep production-only and development-only concerns separate.
- Prefer `group_vars` defaults over repeating booleans in every host entry.
- Model platform and capability separately: use groups like `wsl` / `pve_vms`
  plus orthogonal capability groups like `docker_enabled` / `tailscale_enabled`.
- Keep `common` minimal and reusable; do not leak VPS-only or dev-only choices into it.
- Avoid destructive SSH changes unless the playbook already contains validation for them.

## SSH Safety

- Do not disable SSH password auth by default.
- Treat password-login shutdown as a staged rollout:
  1. Provision user and SSH keys.
  2. Verify key login works from a second session.
  3. Then set both `ssh_disable_password_auth: true` and `ssh_disable_password_auth_confirmed: true`.
- Any SSH auth change must stay behind `sshd -t` validation before the service reloads.

## Runbook

- `ansible-playbook -i ansible/inventory.yml ansible/init-server.yml`
- `ansible-playbook -i ansible/inventory.yml ansible/init-devbox.yml`
