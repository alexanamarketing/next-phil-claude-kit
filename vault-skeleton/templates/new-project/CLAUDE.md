---
project: [project-slug]
started: [YYYY-MM-DD]
---

# Claude AI Context - [PROJECT NAME]

- Project: [Brief description]

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

- Description: [One sentence describing what this project is]
- Type: [client / personal / code / research / writing]
- Status: active

## Folder Structure

```
[project-name]/
├── CLAUDE.md           # AI entry point
├── HANDOFF.md          # Current state, next steps
├── INDEX.md            # Auto-generated directory listing
├── todo.md             # Manual task surface
├── notes.md            # Running notes
├── archived/           # Old versions, monthly note archives
│   ├── notes/          # Archived monthly notes
│   └── INDEX.md
├── case-study/         # Screenshots & results for testimonials
├── deliverables/       # Final outputs
├── docs/               # Reference materials
├── media/              # Logos, images, brand assets
└── working-files/      # Work in progress
```

Every directory gets an INDEX.md (maintained by `rebuild_indexes.py`).

Common working-files subdirectories (create as needed):
- `audits/` - skill audit outputs
- `drafts/` - work-in-progress drafts
- `plans/` - implementation plans
- `references/` - reference docs and guides
- `research/` - research notes
- `skill-journals/` - skill run journals

Common docs subdirectories (create as needed):
- `plans/` - project plans and specs
- `references/` - reference materials

Auto-generated directories (excluded from INDEX tracking):
- `.firecrawl/` - firecrawl skill cache

## Current Work

[What's actively being worked on]

## Key Files

- `HANDOFF.md` - Current state, blockers, what to do next (ephemeral, never archived)
- `todo.md` - Current tasks, blockers, and metadata. Agents read the top execution sections by default
- `notes.md` - Session notes, call outcomes (archived monthly)

## Task Management

When user says "add a task" or "add a todo", add it to this project's `todo.md` file. If the task seems related to a different project, ask which project's todo.md should get it.

## Conventions

- Version files as v1, v2, v3 (not FINAL)
- Keep deliverables in `deliverables/`
- Archive old files to `archived/`
- Professional tone, concise docs
- Follow `<vault_root>/docs/MARKDOWN-STYLE-GUIDE.md` for formatting

## Note Archiving

Run `/archive-docs` when notes.md exceeds 1000 lines or monthly. (Requires the `archive-docs` Claude Code skill from the starter kit.)

Manual process (if needed):
1. Create `archived/notes/notes-YYYY-MM.md` with full session logs
2. Replace detailed entries in notes.md with 3-5 bullet summary
3. Add reference to archived file at bottom of notes.md

Keep in notes.md:
- Current month (full detail)
- Previous months (bullet summaries only)
- "Archived Notes" section with file references

Last updated: [DATE]
