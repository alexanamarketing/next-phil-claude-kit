---
name: doctor
description: Verify your Claude Code setup is working correctly. Run after install, after any config change, or when something feels broken.
---

# /doctor - Verify Setup

Runs the verification suite and interprets the results.

## Command

To locate `<vault_root>`, read `~/.claude/starter-kit/config.json` first, then the `VAULT_ROOT` env var, else ask.

```bash
python3 <vault_root>/scripts/doctor.py
```

## What It Checks

The script verifies each item and prints a pass/fail line with the exact fix command for every failure. Checks are grouped as follows:

### Runtime

- Python 3.8+ available and `pyyaml` installed (optional but recommended)
- Node.js 18+ and npm present

### Claude CLI

- `claude` binary on PATH with a working version
- Login status (auth/credentials file as primary signal; non-fatal warning if absent)

### Kit payload

- `~/.claude/skills/` and `~/.claude/hooks/` directories present
- `~/.claude/settings.json` contains the hook registrations from `settings.fragment.json`
- Pointer file `~/.claude/starter-kit/config.json` exists and points to the vault

### Vault config

- `config.yaml` present at vault root with a non-empty `vault_root` field
- `hook_strictness`, `help_mode`, and shortcut target paths are valid
- `vault_root` in `config.yaml` matches the vault being checked

### Vault structure

- All five bucket directories present (active, inactive, potential, completed, lost)
- `system` meta-project exists with ABOUT.md, CLAUDE.md, and HANDOFF.md

### OS integration

- `os_open`, `os_copy`, and `os_trash` base commands are on PATH (non-fatal)

### Hooks smoke test

- Each installed hook is piped a mock payload and checked for correct exit code and output — confirms hooks actually fire, not just that they are registered (non-fatal)

### Optional

- superpowers plugin installed (non-fatal warning if missing)

Flags: `--json` for machine-readable output, `--strict` for a gating exit code (nonzero on fatal failures).

## Interpreting Results

Each line is one of:

- `[PASS]` — working as expected
- `[FAIL] <what is wrong>` — blocking issue, fix before working
- `[WARN] <what is missing>` — non-fatal, the kit works without it

For each `[FAIL]`, the script prints the exact command or step to fix it. Read the output and apply the fixes in order. Run `/doctor` again after fixing to confirm.

## When to Run

- After the initial `setup.sh` install
- After manually editing `config.yaml` or `~/.claude/settings.json`
- When a hook stops firing or a skill fails to load
- When sharing the kit with someone new (to verify their environment)
- Any time something feels wrong with the setup
