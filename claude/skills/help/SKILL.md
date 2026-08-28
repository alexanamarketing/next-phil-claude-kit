---
name: help
description: /help lists the commands and how to use the system day to day. /help off hides the startup command list; /help on brings it back. /help [topic] gives a focused explanation of one topic (hooks, sync, session-loop, shortcuts, index, output).
---

# /help - Teaching Prompts Toggle and Quick Reference

## Usage

```
/help          — show status and quick reference
/help on       — enable teaching prompts
/help off      — disable teaching prompts
/help [topic]  — focused explanation with example
```

Supported topics: `hooks`, `sync`, `session-loop`, `shortcuts`, `index`, `output`

## Step 0: Read Config

Read `<vault_root>/config.yaml` (to locate `<vault_root>`, read `~/.claude/starter-kit/config.json` first, then the `VAULT_ROOT` env var, else ask). Get the current `help_mode` value (treat absent key as `on`).

## /help on or /help off

Edit the `help_mode` line in `<vault_root>/config.yaml` to the new value (`on` or `off`). If the `help_mode` key is absent, insert a line `help_mode: <value>` immediately after the `hook_strictness` line. Confirm with exactly one line:

```
Help mode is now [on/off].
```

Do NOT print the reference card after toggling.

## bare /help

Print the status line, the full command list, then the short day-to-day guide below. Do not duplicate CLAUDE.md; point to it.

```
Help mode: [on/off]  (change with /help on or /help off)

Commonly used commands:
  /project        - open or continue a project (use /project system the first time, to set up your profile)
  /new-project    - start a brand new project
  /sync           - save your progress at the end of a session, or any time you want to save
  /helper         - turn the plain-English word-explainer on or off (it explains technical words as Claude talks)
  /explain        - ask Claude to say the last thing again in simpler words
  /help           - show this list. /help off hides the startup list once you know it; /help on brings it back
  /archive-docs   - tidy up your notes and to-do list when they get long
  /doctor         - check that everything is installed correctly

/helper explains the words; /help lists the commands.
```

Then print these short day-to-day notes:

```
How to use this day to day:

Open a project and work. Type /project and pick what you are working on, then just
ask Claude for what you need. Everything you do is saved into that project.

Save when you finish. Type /sync at the end of a session. It writes down where you
left off so the next session picks up in the same place. Do this before you close.

Ask when a word is unclear. If an answer used a technical word, type /explain and
Claude will say it again in plain English. /helper keeps the plain-English explaining
turned on as you go.

The safety nets run quietly. Claude will refuse a dangerous command, will not open
files that hold passwords, and saves every change to a private history in your vault.
You never type a save command; it just happens in the background.
```

Full quick reference: `~/.claude/CLAUDE.md`

## /help [topic]

If a topic argument is provided, print the focused explanation below instead of the reference card. Do not print the status line or the command list.

### hooks

Hooks are scripts that run before tool calls (PreToolUse). They can block an action, warn you, or inject context. The core kit ships these hooks:
- block-secrets.py: blocks any file write that contains a secret pattern (.env content, API keys, passwords)
- index-enforcer.py: blocks creating a new .md file in an indexed directory unless INDEX.md was updated first
- file-naming-check.py: warns when a filename breaks the lowercase-kebab-case convention
- pre-compact.sh: fires before /clear and prints a sync reminder

Set `hook_strictness: relaxed` in config.yaml to make index-enforcer advise instead of block while you are learning. Set it back to `normal` once the habit is set.

Example: to see every registered hook, open `~/.claude/settings.json` and look for the `"hooks"` key.

### sync

/sync is the end-of-session maintenance command. Run it before every /clear.

What it does:
- Rewrites HANDOFF.md with current state and what to pick up next session
- Prepends a dated entry to notes.md with key decisions and outcomes
- Reviews todo.md and marks completed items

Why it matters: /clear wipes Claude's memory. HANDOFF.md and notes.md are what the next session reads to know where things stand. Skipping /sync means the next session starts without context.

Example: finish work, run /sync, then /clear. Next session: run /project, read HANDOFF.md, and continue from exactly where you left off.

### session-loop

The session loop is the core workflow pattern this kit enforces:
1. /project [name] — load context (reads CLAUDE.md, HANDOFF.md, notes.md, todo.md)
2. Work — Claude has full project context; make progress on tasks
3. /sync — write outcomes back to docs (HANDOFF, notes, todo)
4. /clear — wipe Claude's memory (safe because the docs are current)
5. Repeat from step 1 next session

The files are what survive /clear. The loop only works if you sync every time. One skipped /sync means the next session loads stale context and you spend the first few minutes re-explaining.

Example: a 45-minute session wraps up. Run /sync (30 seconds), then /clear. Open a new session, run /project, and you are back in context with no re-explanation.

### shortcuts

Shortcuts are aliases in config.yaml that let you jump to a project with a short name instead of typing the full path.

Add a shortcut under the `shortcuts:` key in config.yaml:

```yaml
shortcuts:
  myproject: "active/my-project-slug"
  blog: "active/website-blog"
```

Then invoke with `/project myproject` or `/project blog`. The project list is always derived from disk, not from shortcuts — you can still browse the numbered list if you forget a shortcut name. Run `/project home` to jump to vault root with no project loaded (cross-project context only).

### index

Every directory in your vault has an INDEX.md that lists all .md files in it. The index-enforcer hook blocks writing a new .md file if INDEX.md was not updated first (the INDEX-before-write rule).

The correct sequence:
1. Read the directory's INDEX.md
2. Add an entry for the new file above the AUTO-GENERATED-BELOW marker
3. Write the new file

Or regenerate all indexes from disk at once:

```bash
python3 <vault-root>/scripts/rebuild_indexes.py --all-buckets
```

Use `--check` to verify without writing. The marker `<!-- AUTO-GENERATED-BELOW: do not edit manually; run rebuild_indexes.py -->` separates the curated header (edit freely) from the auto-generated file list (do not edit manually).

Set `hook_strictness: relaxed` in config.yaml to get a warning instead of a block if you forget.

### output

Long command output goes to a file first, then read only the slice you need. Redirect with `> /tmp/out.txt`, then read only the relevant section instead of dumping everything into the conversation. Prefer `--json` with selected fields, or `--plain` flags when available, to get compact structured output rather than full prose. Empty results should be explicit: a tool that returns nothing silently is harder to debug than one that prints "none found." This habit keeps the context window clean and makes it easier to spot what actually matters.

Example: `some-long-command > /tmp/out.txt` then read only the relevant part.

Reference: "Agent Output Discipline" section of `~/.claude/CLAUDE.md`.
