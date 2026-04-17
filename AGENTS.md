# AGENTS

## Scope

This repository is Ansible-based IaC.
It manages two distinct target classes:

- `servers`: public VPS / production hosts
- `devboxes`: PVE VMs and WSL development environments

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
- Only use `shell` when shell features are actually required.
- For `command` tasks, express idempotency explicitly with `creates`, guards, or `changed_when: false/true` as appropriate.

## Lint

- when finish change, run `mise r lint` to check
