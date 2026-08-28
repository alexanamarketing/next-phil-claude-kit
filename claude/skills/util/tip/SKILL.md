---
name: tip
description: Show a useful Claude Code tip. Run when you want a quick reminder about a workflow pattern, keyboard shortcut, or lesser-known feature.
---

# /tip - Claude Code Tip

Show one useful Claude Code tip from the list below, or a random one if no argument is given.

## Usage

```
/tip [topic]
```

Topics: `context`, `compact`, `config`, `hooks`, `skills`, `git`, `parallel`, `output`

## Tips

### context

Load only what you need. Every file you read costs tokens and compresses faster. Use capped reads (`limit:` param) for large files. Stop before the Completed section of `todo.md`. Use `source_of_truth:` in frontmatter for the one file that must always be in context.

### compact

Run `/sync` before `/clear` or compaction. The HANDOFF.md you write now is the first thing the next session loads. A good handoff takes 30 seconds and saves 5 minutes of re-orientation.

### config

`config.yaml` at your vault root is the single file that controls everything. Two settings worth knowing early: set `hook_strictness: relaxed` to make the index-enforcer give a warning instead of blocking while you learn the workflow; add entries under `shortcuts:` (e.g. `myproject: "active/my-project"`) so `/project myproject` jumps straight to that project without browsing the numbered list. Changes take effect immediately — no restart needed.

### hooks

Hooks fire before tool calls, not after. `block-secrets.py` stops a write before it happens. `index-enforcer.py` blocks a new file write before it lands. This means fixing the issue is always in the same turn, not a cleanup step after the fact.

### skills

Skills are just markdown files. If a skill does not do exactly what you want, read it and edit it. The file is at `~/.claude/skills/<name>/SKILL.md`. Changes take effect immediately — no restart needed.

### git

Always pass an explicit repo path to git: `git -C /absolute/path/to/repo status`. A bare `git add` from the wrong working directory can stage files from the wrong project. The vault CLAUDE.md has this as a hard rule for good reason.

### parallel

Two Claude sessions in the same folder clobber each other's staged files and commits. Use git worktrees to run parallel agents: `git worktree add ../project-task -b task-branch`. Each worktree is a separate folder with a separate branch but the same repo underneath.

### output

Long CLI output floods the context and compresses badly. Write it to a file first, then read only the slice you need: `some-command > /tmp/out.txt && head -50 /tmp/out.txt`. This is especially important for research tools, doc generators, and anything that dumps JSON.
