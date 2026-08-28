---
project: system
started: [INSTALL-DATE]
---

# Claude AI Context - System

Project: The meta project. Holds your identity and workflow knowledge so every session knows how to work with you.

> Start here: Read HANDOFF.md for current state. Fill out ABOUT.md if you have not yet.

## What This Is

`system` is not a client or work project. It is the operating layer for your entire vault. When you load it with `/project system`, you give the AI context about who you are and how you like to work, so you do not need to re-establish that in every session.

Two sources of truth run side by side:

- Global operating rules: `~/.claude/CLAUDE.md` (installed by the starter kit). This file defines how the AI behaves, what hooks are active, and the house style for the vault. You do not normally edit it session to session.
- Personal identity: `ABOUT.md` in this folder. This is what you fill out. It answers the questions a new AI session would need to know: who you are, what your expertise is, how you want to communicate, what to never do.

Neither file is loaded automatically without the `/project` skill. Load this project at the start of any session where you want the AI to know who it is working with.

## Where Things Live

- `ABOUT.md` - who you are, how you work, what you expect. The most important file in this project.
- `notes.md` - meta decisions: notes about workflow changes, system improvements, setup history.
- `todo.md` - system-improvement tasks only (not client or project work; that belongs in each project's own todo.md).
- `HANDOFF.md` - current state and what to load next session. Updated by `/sync`.
- `INDEX.md` - auto-maintained directory listing. Do not edit manually.

## How to Use This System

Load at the start of a working session when you want the AI to know your identity and preferences:

    /project system

Then pick a project to work in:

    /project

Or jump straight to a project by slug:

    /project my-project-slug

At the end of a session, run `/sync` before `/clear`. It updates HANDOFF.md and notes.md so the next session picks up where you left off.

If you only need to work in a project and do not need identity context, you can skip loading `system` and go straight to `/project`. Identity context is most valuable for new sessions or when changing how you work.

## Best Practices for Keeping Things Lean

- Run `/sync` before every `/clear`. Do not rely on memory surviving a context clear; it does not.
- Keep ABOUT.md current. If your role, stack, or communication preferences change, update it. Stale identity context trains the AI to work the wrong way.
- Run `/archive-docs` when notes.md exceeds 1000 lines, or once a month. This moves old entries to `archived/notes/` and keeps the active file fast to read.
- Follow INDEX-before-write: when adding a new `.md` file to any indexed directory, update INDEX.md first. The index-enforcer hook enforces this; following it voluntarily is faster than triggering a block.
- Keep todo.md scoped to system improvements only. Everything else belongs in the relevant project's todo.md.
