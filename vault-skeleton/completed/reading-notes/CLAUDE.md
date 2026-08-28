---
project: reading-notes
started: 2026-03-08
---

# Claude AI Context - Reading Notes

- Project: Personal reading log tracking books, notes, and takeaways through H1 2026

> Start here: Load `HANDOFF.md` first for current state and next steps. Update it at session end.

## Contents

- Key Info
- Folder Structure
- Current Work
- Key Files
- Task Management
- Conventions
- Note Archiving

## Key Info

- Description: Personal reading log tracking books, notes, and takeaways through H1 2026
- Type: personal
- Status: completed

## Folder Structure

```
reading-notes/
├── CLAUDE.md           # AI entry point
├── HANDOFF.md          # Current state, next steps
├── INDEX.md            # Auto-generated directory listing
├── todo.md             # Reading list with statuses
└── notes.md            # Per-book notes and quotes
```

Every directory gets an INDEX.md (maintained by `rebuild_indexes.py`).

## Current Work

Project wrapped up May 2026. All H1 2026 reading goals are complete. Notes are in notes.md.

## Key Files

- `HANDOFF.md` - Current state and last book completed
- `todo.md` - Reading list with open and completed items
- `notes.md` - Per-book notes, quotes, and takeaways

## Task Management

When user says "add a task" or "add a todo", add it to this project's `todo.md` file.

## Conventions

- One ## heading per book in notes.md, with ### subheadings for Notes, Quotes, Takeaways
- Version files as v1, v2, v3 (not FINAL)
- Follow `<vault_root>/docs/MARKDOWN-STYLE-GUIDE.md` for formatting

## Note Archiving

Run `/archive-docs` when notes.md exceeds 1000 lines or after completing a major reading push.

Last updated: 2026-05-30
