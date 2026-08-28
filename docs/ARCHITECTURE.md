# Architecture

How the pieces fit, for anyone maintaining or extending this kit.

## The three-location model

The kit separates concerns across three locations on disk. Understanding this is the foundation for understanding everything else.

### ~/.claude (Claude Code user directory)

What lives here: the payload that Claude Code loads every session.

- `CLAUDE.md` — auto-loaded by Claude Code at the start of every session. This is the boot cheatsheet.
- `skills/<name>/SKILL.md` — skill definitions. Claude reads these when you invoke `/name` in a session.
- `hooks/*.py` and `hooks/*.sh` — Python and shell scripts that run at hook events (PreToolUse, PreCompact, etc.).
- `hooks/lib/hook_config.py` — shared config reader used by all hooks. Finds and parses config.yaml so hooks never hardcode paths.
- `references/` — reference data this realtor kit adds: `tool-modules/` (one Markdown file per tool, holding Claude's learned notes about it), `tool-module-focus.json`, `claude-md-standard.md`, `writing-standards/` (the advisory writing-lint rules + voice doc), and the AEO copywriting playbook.
- `agents/aeo-copywriter.md` — this kit ships one agent (the base kit shipped none), for AEO copywriting.
- `helper-mode.json` — the Helper Mode state (on/off, learning-week start, window length). Written on install (default on), read by the `helper-mode.py` hook every turn.
- `settings.json` — Claude Code configuration including hook registrations.

This location is owned by Claude Code, not by this repo. The installer copies the `claude/` directory from the repo into `~/.claude` and merges (never overwrites) settings.json. A full backup is made before touching anything.

### What this realtor kit adds over the base kit

- Signature features: a self-learning tool memory (the tool-module engine + `/toolupdate`) and Helper Mode (`helper-mode.py` + `/helper`).
- Safety hooks: `command-guard.py`, `secret-guard.py`, and the newer `block-secrets.py`.
- Git-backed-invisible: the installer git-inits the vault, `auto-stage.sh` (PostToolUse) stages every edit, and `auto-commit.sh` (Stop) commits them, so the user's work saves itself with no git commands.
- Advisory quality: `claude-md-hygiene.py` and the trimmed `writing-lint` stack, both warn-only.
- Skills/agent: `/explain`, `/helper`, `/toolupdate`, `unslop`, and the `aeo-copywriter` agent.

### The vault (user-chosen path, default ~/vault)

What lives here: all project folders and the config that drives everything.

- `config.yaml` — the single config file. Everything else reads from here.
- `active/`, `inactive/`, `potential/`, `completed/`, `lost/` — project bucket folders.
- `system/` — the meta-project (workspace identity, ABOUT.md, workflow notes).
- `templates/new-project/` — the template used by `/new-project` and `scripts/new_project.py`.
- `scripts/` — Python utilities: `rebuild_indexes.py`, `new_project.py`, and `doctor.py`.
- `docs/` — vault-level docs including `MARKDOWN-STYLE-GUIDE.md`.

The vault is instantiated from `vault-skeleton/` in the repo. Once instantiated, it is the user's live data store and is not tracked by this repo.

### Code repos (~/Projects/<name>)

What lives here: anything with a build step. Code projects are kept outside the vault to avoid accidentally committing them into the vault's git history or vice versa.

The vault holds planning docs, notes, and deliverables for a code project. The code itself lives in its own repo. A project's `CLAUDE.md` should link them with a `Code repo:` line.

## How config.yaml wires everything together

`config.yaml` at the vault root is the single source of truth for all runtime configuration.

Hooks discover it via `hook_config.py`, which searches in this order:

1. `HOOK_VAULT_ROOT` environment variable (set the vault root explicitly)
2. `VAULT_ROOT` environment variable
3. Walk up from the file being operated on, looking for `config.yaml`
4. Walk up looking for an `active/` directory, then check its parent for `config.yaml`

This means hooks work correctly regardless of which project file Claude is editing, without any hardcoded paths.

Scripts discover the vault root the same way (env var or `Path(__file__).parent.parent`).

Skills reference the vault root indirectly — they call scripts that resolve it, or they instruct Claude to use config.os_open, config.os_copy, etc., which Claude reads from the config at load time via the `/project` skill.

## How settings.json is managed

`settings.json` in `~/.claude/` is Claude Code's main config. This kit adds hook registrations to it without touching anything else.

The installer uses an inline Python script to:

1. Load existing `settings.json` (or start with `{}`).
2. Load `claude/settings.fragment.json` and expand `$HOME` to the real home path.
3. For each hook event type in the fragment, append only the entries whose commands are not already registered.
4. Write the merged result back.

This means running the installer a second time is safe — it will not duplicate hooks. It also means users who already have custom hooks or permissions will keep them.

`settings.fragment.json` is a minimal JSON object containing only the `hooks` block. It is not a complete `settings.json`. The merge is additive only.

## How backup and rollback work

Before touching `~/.claude`, the installer creates a timestamped tar.gz backup at `~/.claude-backup-<timestamp>.tar.gz`.

If an existing `~/.claude/CLAUDE.md` is found, it is copied to `~/.claude/CLAUDE.md.bak.<timestamp>` before being replaced.

To roll back: extract the tar.gz backup to restore the full `~/.claude` directory, or copy the `.bak` file back over `CLAUDE.md`.

## How to add a skill

1. Create `claude/skills/<name>/SKILL.md` in the repo.
2. The SKILL.md format is freeform markdown read by Claude when the skill is invoked. At minimum, include a YAML frontmatter block with `name` and `description`.
3. Copy the file to `~/.claude/skills/<name>/SKILL.md` (or re-run `./setup.sh`).
4. Invoke with `/<name>` in a Claude session.

Skills do not require registration anywhere — Claude Code discovers them by scanning `~/.claude/skills/`.

If the skill is part of a plugin (superpowers, dx, etc.), it is managed by the plugin system and lives in a plugin cache, not directly in `~/.claude/skills/`.

## How to add a hook

1. Write the hook script in `claude/hooks/`. Use `#!/usr/bin/env python3` shebang for Python hooks.
2. Use `hook_config.py` for all config access — never hardcode paths.
3. Read input from stdin as JSON (`json.load(sys.stdin)`). The payload contains `tool_name` and `tool_input`.
4. Exit 0 to allow, exit 2 to block (for PreToolUse hooks that block). Write to stderr for messages shown to Claude.
5. Add an entry to `claude/settings.fragment.json` under the appropriate event type with the correct matcher.
6. Re-run `./setup.sh` (or manually copy the hook and merge the settings fragment).

Hook event types used in this kit:

- `PreToolUse` — runs before a tool call. Can block (exit 2) or inject context (via JSON output).
- `PreCompact` — runs before Claude compacts context. Used to print preservation reminders.

The five core hooks and their matchers are documented in `claude/settings.fragment.json`.

## How doctor.py works

`vault-skeleton/scripts/doctor.py` is the verification suite. It checks:

- Python 3.8+ is available
- pyyaml is importable (non-fatal warning if absent)
- node 18+ and npm are available
- claude CLI is installed and logged in (non-fatal)
- `~/.claude/CLAUDE.md` exists
- `~/.claude/settings.json` contains all 5 core hook registrations
- `config.yaml` exists at the vault root and has a valid `vault_root`
- The vault skeleton structure (bucket folders, system/, templates/) is present
- superpowers plugin is installed (non-fatal)

Run it any time with `/doctor` or directly:

```bash
python3 <vault-root>/scripts/doctor.py --vault-root <vault-root>
```

It exits 0 regardless of failures. The report prints a pass/fail line for each check plus the exact fix command for each failure.

## Script output conventions

Kit scripts follow agent-ergonomic conventions: non-interactive, exit 0/nonzero, definitive empty states, success counts, fix/next-step hints on failure. `doctor.py` additionally offers `--json` (machine-readable) and `--strict` (gating exit code).

New scripts should follow the same conventions. Add `--json` only when another tool will actually consume the output.

## Vault structure conventions

Each project folder contains standard load-bearing files:

- `CLAUDE.md` — project context, loaded by `/project`
- `HANDOFF.md` — current state and next steps (ephemeral, rewritten by `/sync`)
- `todo.md` — tasks with status, priority, and date tags
- `notes.md` — dated session notes, prepended by `/sync`
- `INDEX.md` — lists all files in the directory (enforced by index-enforcer hook)

The `templates/new-project/` folder contains a template with all of these stubs plus subdirectory INDEX.md files. `/new-project` and `scripts/new_project.py` copy this template to create a new project.

The `system/` folder is a pre-made project that holds workspace identity (ABOUT.md) and workflow knowledge. It is not a regular project — it is the meta-layer that makes every other session work better.
