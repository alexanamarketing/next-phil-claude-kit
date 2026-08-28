---
name: sync
description: End-of-session doc maintenance. Update notes.md, HANDOFF.md, CLAUDE.md, and todo.md with capped reads. Run before /clear or ending a session.
---

# /sync - Update Project Docs

## Step 0: Inline or Subagent

Default: run inline. The session context already has everything needed.

If you type `/sync sub`, launch a general-purpose subagent instead (useful for long sessions near compaction):
1. Write a concise session summary (what changed, new tasks, blockers)
2. Launch the agent with that summary plus the update steps below
3. Cap all file reads in the agent prompt: `notes.md` 30 lines, `HANDOFF.md` 25 lines, `CLAUDE.md` 50 lines, `todo.md` 40 lines
4. Include no formatting rules in the prompt (the global CLAUDE.md covers it)

## Step 1: Identify Project

Determine the active project directory from the current session context. If unclear, ask. To resolve `<vault_root>`, read `~/.claude/starter-kit/config.json` first, then the `VAULT_ROOT` env var, else ask.

- Project-specific work goes to that project's docs
- Vault-level or cross-project work goes to the vault root docs

## Step 1.5: Detect Load Profile

Auto-detect: if the active project's `CLAUDE.md` frontmatter explicitly contains `load_profile: code-paired-light`, the project is code-paired. Use the Code-Paired Light Path (Step 2-Light) instead of the full Step 2.

Overrides:
- `/sync full` — force the full path
- `/sync lite` or `/sync code` — force the light path
- `/sync sub` — subagent, following whichever path applies

If detection is unclear, ask rather than guess.

## Step 2: Full Update

Default for non-code projects, or when `/sync full` is passed. Run in this order.

All tasks discovered during sync go to the project's `todo.md`. No exceptions.

### notes.md

Read first 30 lines only. Insert a new entry after the opening metadata:

```
## YYYY-MM-DD - Brief Topic

One-sentence summary. Bullets for details.
- What was done
- Key decisions or findings
- Files created or changed
- New tasks discovered
```

Keep entries 10-20 lines. Match the style of existing entries.

### HANDOFF.md

Read first 25 lines only (to get the H1 and any frontmatter). Then rewrite the whole file fresh, preserving frontmatter at top:

```
---
project: <slug>
updated: YYYY-MM-DD
priority: <high|medium|low>
next_session: "<one-line description>"
blocked: <true|false>
blocker: <null or "string">
---

# HANDOFF - [Project Name]

Last updated: YYYY-MM-DD

## What Just Happened

[2-4 bullets from this session]

## Next Session Should

[Prioritized list of what to do next]

## Blockers

[Active blockers, or "None"]

## Key Reference Files

[Only files relevant to next actions]
```

HANDOFF is ephemeral. Write what is true now, do not preserve old content.

When to full-rewrite vs. targeted edit: if only 1-2 small things changed and the "Next Session Should" priorities are unchanged, do a targeted Edit instead. Full rewrite when priorities or overall state shifted meaningfully.

### CLAUDE.md

Only update if status, phase, or key files changed. Read first 50 lines to find the relevant area. Make one targeted Edit. Skip if nothing meaningful changed.

### todo.md

1. Read first 40 lines (frontmatter and metadata). Update `last_updated`, `latest_update`, and `session_notes` fields inside the frontmatter fences.
2. Match session work against active todos: `grep -n "\[ \]"` in active sections. Change `[ ]` to `[x]` for any task completed this session.
3. When moving completed items to `## Completed`: only move a parent block when all its sub-items are `[x]`. Move the parent and all sub-items together as a unit. Never orphan nested items.
4. For new tasks: check if they belong under an existing initiative (nest as a sub-item if yes). Add a new top-level entry only if genuinely independent.
5. Do NOT read the full file. Use targeted grep and read-around-line for sections beyond the metadata.

### README.md

Almost always skip. Update only if project structure or major milestones changed.

## Step 2-Light: Code-Paired Path

For code-paired projects or when `/sync lite` is passed. The code repo (git history, plans, journals) is the real record. Update only `todo.md` and a compact `HANDOFF.md`.

Read caps (do not scan the repo itself):
- vault `todo.md`: first 40 lines and targeted checkbox greps
- vault `HANDOFF.md`: first 25 lines
- repo: `git -C <repo_path> status -sb` and `git -C <repo_path> log --oneline -10`

### todo.md (light)

Keep at initiative level only. One line per active workstream pointing to the repo source of truth. Mark items `[x]` when completed this session. Update metadata. Do not mirror the repo's task queue into the vault.

### HANDOFF.md (light)

Preserve frontmatter. Keep under about 35 lines:

```
## Current State

- Code repo: <absolute repo path>
- Active branch: <branch name or "main">
- Current focus: <one sentence>
- Resume point: <repo file path — journal, run ledger, plan, or queue>
- Dashboard task: <todo.md top-level task name>

## Next Session Should

1. <highest-priority next action>
2. <optional second if genuinely active>

## Blockers

<None, or concrete blocker and decision needed>

## Key References

- <repo path> - <why it matters>
```

### notes.md (light)

Skip for ordinary code work. Write a `notes.md` entry only for something the repo does not durably hold: a vault-only decision, a cross-project process change, a non-code deliverable, or a milestone that must appear in the vault chronology.

### CLAUDE.md (light)

Update only if load instructions, the repo path, source-of-truth files, or a status/phase changed.

### Parallel sessions note

The vault is single-writer. If another session is active on this project, prefer a targeted edit over a full rewrite of HANDOFF.md to avoid clobbering the other session's state.

## Step 2.9: Rescue scratch files

Before reporting, check whether anything worth keeping was written to a temporary
location this session (a `/tmp` file, a scratchpad, a draft). If so, and it belongs
to this project, move it into the project (its `working-files/` or the right folder)
and note it, so nothing useful is lost when the temp files are cleared. If it is
throwaway, leave it. When reading long files during sync, read only the slice you
need (head/tail or a line range), not the whole file, so a long notes.md or todo.md
does not eat the context budget.

## Step 3: Report

One line per file: what changed or "skipped — reason".

## Help-Mode Teaching Note (T4)

After the per-file report, read `help_mode` from `<vault_root>/config.yaml`. If `on` (or the key is absent), append this note after the report. If `off`, skip silently.

"/sync is the session closer. Claude's context does not persist through /clear — these files carry the work forward. The habit is /sync then /clear, in that order."

## Step 4: Archive Check

Run `wc -l <vault_root>/<project>/notes.md`. If the result exceeds 1000 lines, suggest running `/archive-docs`.
