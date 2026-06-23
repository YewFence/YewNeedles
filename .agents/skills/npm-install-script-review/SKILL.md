---
name: npm-install-script-review
description: Locate and review npm dependency install, postinstall, prepare, preinstall, install, and build scripts that were skipped by pnpm or aube for mise-installed npm tools. Use when asked to audit ignored builds, approve-builds candidates, npm install scripts, or whether a skipped dependency build script is safe to approve.
---

# Npm Install Script Review

Use this skill to audit dependency lifecycle scripts before `pnpm approve-builds` or `aube approve-builds` is run for a `mise` npm tool.

Do not approve builds, rebuild packages, or run skipped lifecycle scripts unless the user explicitly asks after reviewing the findings.

## Workflow

Run the locator script first.

```bash
uv run --script .agents/skills/npm-install-script-review/scripts/find-install-scripts.py npm:<tool>
```

The script accepts a `mise` npm tool spec, an installed tool directory, or a resolved pnpm or aube project directory. If the user already provides the package manager project directory, pass that path directly because it avoids another `mise where` lookup.

If the script output is missing packages, points at the wrong location, or does not expose enough context for review, read `scripts/find-install-scripts.py`, improve the locator logic there, and rerun it. Treat the script as the source of truth for package manager layout details instead of rebuilding the path resolution workflow in this file.

For each package reported by the script, inspect the printed `package.json`, lifecycle command, and referenced local files. Explain what the script would execute, call out network downloads, native builds, shell execution, writes outside the package directory, opaque or minified code, credential access, daemon startup, or privilege escalation, then recommend `approve`, `needs user confirmation`, or `do not approve yet`.

## Useful Commands

```bash
uv run --script .agents/skills/npm-install-script-review/scripts/find-install-scripts.py npm:@scope/tool
uv run --script .agents/skills/npm-install-script-review/scripts/find-install-scripts.py /path/to/global-aube/project
uv run --script .agents/skills/npm-install-script-review/scripts/find-install-scripts.py /path/to/pnpm/project
```
