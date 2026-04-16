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
- `ansible/roles/mise`: mise install plus generated global `config.toml` for devboxes
- `ansible/roles/oh_my_zsh`: zsh / Oh My Zsh setup for devboxes
- `ansible/roles/zellij`: zellij shell autostart for devboxes
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

## Ansible Patterns

- Do one-time operator preview/confirmation in a dedicated `localhost` play instead of using `run_once` with delegated tasks inside remote plays.
- Inside roles, prefix role-owned variables with the role name, for example `docker_host_*`, `ssh_hardening_*`, `swapfile_*`.
- When renaming role variables for lint compliance, keep compatibility by deriving the new prefixed default from the old external variable when needed.
- Prefer `get_url` plus `command` over `curl | sh` installers. Only use `shell` when shell features are actually required.
- For `command` tasks, express idempotency explicitly with `creates`, guards, or `changed_when: false/true` as appropriate.
- If a task sets `become_user`, set `become: true` on the same task.
- Prefer service modules over raw `systemctl`; use `ansible.builtin.service` with `state: reloaded` for reload handlers.
- Handlers and probe commands that only validate or refresh state, such as `sshd -t` or `sysctl --system`, should usually set `changed_when: false`.

## Runbook

- `ansible-playbook -i ansible/inventory.yml ansible/init-server.yml`
- `ansible-playbook -i ansible/inventory.yml ansible/init-devbox.yml`
