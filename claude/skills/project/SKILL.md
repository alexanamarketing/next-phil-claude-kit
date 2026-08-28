---
name: project
description: Load your vault workspace, pick a project, and load its context files. Use at the start of every session.
---

# /project - Project Loader

Load your vault and pick a project to work on.

## Step 0: Read Config

Read `<vault_root>/config.yaml` (to locate `<vault_root>`, read `~/.claude/starter-kit/config.json` first, then the `VAULT_ROOT` env var, else ask) to get:
- `vault_root` — the absolute path to your vault
- `shortcuts` — map of shortcut aliases to bucket/project-slug
- `os_copy` — clipboard command for this machine
- `help_mode` — whether to show teaching prompts (treat absent key as `on`)

## Step 1: Load Root Context

Read from `<vault_root>`:
- `README.md` (first 50 lines only, for the project table and structure)

Do NOT read root `notes.md` here. It is vault session history, loaded conditionally in Step 2 (home) or Step 3 (full-load projects only); code-paired light-load projects skip it.

## Step 2: Pick a Project

Check if an argument was provided: `$ARGUMENTS`

If the argument matches a key in `config.shortcuts`, resolve it to the corresponding `bucket/slug` path under `<vault_root>` and jump directly to that project. Skip the numbered list.

If the argument is `home` (or no argument or an unrecognized argument):
- Run `ls <vault_root>/active/` and display a numbered list as plain text. Include "Home base" as the final option. Tell the user to type a number, name, or shortcut.
- Do NOT infer the project list from `config.shortcuts`. Always derive from disk.

If the user picks **Home base** (or shortcut `home`):
- Working directory: `<vault_root>`
- Read root `notes.md` (first 110 lines only) for recent cross-project context
- Show vault root `todo.md` top tasks (if it exists)
- Skip to Step 4

If nothing is set up yet (no `config.shortcuts`, no projects in `active/`):
- Show the numbered list anyway (it will be empty or have only the template)
- After Step 4, print: "Type `/project system` to set up your workspace identity."

## Step 3: Load the Chosen Project

First read the project's `CLAUDE.md` (if it exists). Its frontmatter controls the load profile.

### Determine load profile

- **Full load** (default): if no `load_profile` key in frontmatter, OR the argument includes `full` (e.g. `/project myproject full`).
- **Light load** (code-paired): only when frontmatter explicitly contains `load_profile: code-paired-light` AND `full` was not requested. Light load is opt-in per project. Do NOT infer it from a `Code repo:` line or any other signal.

### Full load

Read from the chosen project folder:
- `CLAUDE.md` (already read above)
- `HANDOFF.md` (if it exists)
- `notes.md` (first 110 lines only)
- `todo.md` (stop before the Completed section — run `grep -n "^## Completed" todo.md` to find the line number, then read with `limit` set to that line minus 1)
- Vault root `notes.md` (first 110 lines only) for recent cross-project context
- If `CLAUDE.md` frontmatter declares a `source_of_truth:` path, read that file in full before doing any work. It is the canonical reference.

### Light load (code-paired)

The code repo is the source of truth. Read only:
- `CLAUDE.md` (already read) — project identity, repo path, rules
- `HANDOFF.md` (if it exists) — current state and resume point
- `todo.md` (stop before Completed section) — full active task list

Skip: vault root `notes.md`, project `notes.md`.

Do NOT eager-read `source_of_truth:`. Instead print:

```
Light load: source_of_truth NOT loaded. Read it in full before any design or architecture decision: <path>
```

### Show top 3 pending tasks

After loading, display the top 3 incomplete tasks from `todo.md` that are not marked `{blocked:...}`.

## Step 4: Session Ready

Print one line: "Context loaded."

If nothing in the vault is set up yet, append: "Type `/project system` to set up your workspace identity."

Session branching (optional): if you have session branching available through a Claude Code plugin or future CLI version, you can set a checkpoint now with `/branch baseline`. This is not a stable built-in feature yet — skip if the command is unrecognized.

## Startup Command Banner

Read `help_mode` from config.yaml (already loaded in Step 0). If `help_mode` is `on` (or the key is absent), print the banner below right after the "Context loaded." line, before any teaching notes. If `help_mode` is `off`, do NOT print it (skip silently).

Print it exactly like this:

```
Commonly used commands:
  /project      - open or continue a project. Type /project, then pick from the list.
  /sync         - save your progress. Run it at the end of a session, or any time you want to save what you have done.
  /helper       - turn the plain-English word-explainer on or off (it explains technical words as Claude talks).
  /explain      - ask Claude to say the last thing again in simpler words.
  /new-project  - start a brand new project.
  /help off     - hide this list once you know it. /help on brings it back; /help shows the full list.
```

The last line always tells the user how to turn the list off (`/help off`).

## Help-Mode Teaching Notes

After the banner (if shown), read `help_mode` from config.yaml (already loaded in Step 0). If `on` (or the key is absent), append the teaching note(s) below after all other output. If `off`, skip silently.

### T1 (every load, after the branch-checkpoint output)

"Session loop: /project loads context, you work, /sync updates HANDOFF.md and notes.md, /clear resets Claude's memory. The files are what survive /clear. Sync before you clear, every time."

### T2 (only when the loaded project is `system` AND ABOUT.md still contains the literal token `[Your answer here]`)

Detection: read the first 15 lines of `<vault_root>/system/ABOUT.md`. If `[Your answer here]` appears, the file is unfilled — show T2 after T1 and the HANDOFF next-steps.

"ABOUT.md is the most valuable setup step. Fill it out once and every future session will know your role, your expertise level, how you want the AI to communicate, and what to never do. The more specific you are, the less you re-explain yourself each session. Open ABOUT.md and work through each section now."

### T3 (any non-`system` project when ABOUT.md is unfilled AND help_mode is on)

Detection: same check as T2 — read the first 15 lines of `<vault_root>/system/ABOUT.md`. If `[Your answer here]` appears AND the loaded project is NOT `system`, show this one line after T1:

"Tip: your workspace identity (system/ABOUT.md) isn't filled out yet. Run /project system to set it up so sessions know how to work with you."

### T4 (graduation nudge — only when help_mode is on AND setup looks complete)

Detection: help_mode is on (from Step 0) AND `[Your answer here]` does NOT appear in the first 15 lines of `<vault_root>/system/ABOUT.md` AND `config.yaml` has at least one uncommented, non-empty shortcut entry under the `shortcuts:` key. If all three conditions are true, append this single line after all other output:

"You seem set up. When the teaching notes stop being useful, turn them off with /help off."
