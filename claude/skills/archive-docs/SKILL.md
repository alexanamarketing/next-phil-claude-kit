---
name: archive-docs
description: Keep notes.md and todo.md lean by archiving old entries. Run when notes.md exceeds 1000 lines, or monthly for active projects.
---

# /archive-docs - Archive Old Project Docs

## Thresholds

- Trigger: `notes.md` exceeds 1000 lines
- Target after archiving: 600-700 lines
- Archive aggressively to leave headroom for 15-20 sessions before hitting the threshold again. Archiving to just under 1000 wastes the effort.
- Token estimate: lines × 4

## Options

- `--dry-run` — preview without making changes
- `--all` — batch all projects (one confirmation per project, summary at end)
- `--force` — skip confirmation prompt

## Process

### Step 1: Scan

To locate `<vault_root>`, read `~/.claude/starter-kit/config.json` first, then the `VAULT_ROOT` env var, else ask. Count lines in `notes.md` and completed tasks in `todo.md`. Show current count vs. thresholds.

### Step 2: Identify Archive Candidates

Notes entries use `## YYYY-MM-DD - Title` headers. If the format is different, treat as unparseable and keep.

For `notes.md`:
1. First pass: archive everything except the most recent 2 weeks of entries
2. Second pass: if still over 700 lines, archive older entries until under target
3. Always keep entries that mention open todo items (flag for review if one would be archived)

For `todo.md`:
- Keep: all incomplete tasks
- Archive: completed tasks older than the current month
- Nested checklists: treat parent and all indented sub-items as one atomic unit. Never archive a parent and leave orphaned sub-items. A block is complete only when the parent line is `[x]`.

### Step 3: Preview

```
## Archive Preview: <project>/notes.md

KEEPING (131 lines):
- 2026-01-19: Session title (89 lines)
- 2026-01-16: Session title (42 lines)

ARCHIVING to archived/notes/notes-2025-12.md (1,269 lines):
- 2025-12-31: Session title (156 lines)
- 2025-12-28: Session title (203 lines)

Token savings: ~5,076 tokens (1,269 × 4)
Proceed? [y/N]
```

### Step 4: Update Archive INDEX Files

Before writing any archive file, update the INDEX files. This prevents index-enforcer from blocking the writes.

Append one entry to `archived/notes/INDEX.md`:

```
- notes-YYYY-MM.md (N lines) — topic1, topic2, topic3. K decisions extracted.
```

Derive topics from the `## YYYY-MM-DD - Title` headers in the entries being archived (3-5 most frequent themes, deduplicated).

If archiving completed todos, also append one entry to `archived/todos/INDEX.md`:

```
- completed-YYYY.md (N items) — completed tasks archived YYYY-MM-DD
```

If an INDEX.md does not exist, create it with `# Archive Index` as the header.

### Step 4b: Write Archive Files

Create directories if missing (`mkdir -p archived/notes archived/todos`).

Archive file locations:
- Notes: `archived/notes/notes-YYYY-MM.md`
- Todos: `archived/todos/completed-YYYY.md`

New archive file header:

```
# Archived Notes - Month YYYY

Project: <slug>
Archived: YYYY-MM-DD

---

[archived content here]
```

If the archive file already exists, append with a `---` separator. Never overwrite.

### Step 4c: Decision Extraction

Scan the entries being archived for decision-language. Extract strategic decisions that would affect future work if forgotten: tool choices, scope changes, strategic pivots, key agreements.

Trigger patterns:
- "decided", "chose", "picked", "went with", "approved", "rejected"
- "pivoted", "switched to", "killed", "dropped", "abandoned"
- "locked in", "committed to", "finalized"
- Structural: "X over Y", "instead of X", "rather than X"

Ignore low-stakes implementation details (selector changes, variable renames, minor debugging choices). Only extract decisions that would cause confusion or rework if forgotten.

Append to `archived/decisions.md`:

```
# Project Decisions

## YYYY-MM-DD

- Chose X over Y (reason: ...)
- Pivoted from A to B (reason: ...)
```

Rules:
- One line per decision: what was decided and a parenthetical reason if visible
- Group by date, using the entry's `## YYYY-MM-DD` header date
- If `decisions.md` exists, append new date sections. Never overwrite.
- Skip if no decisions found in the batch (don't add empty sections)
- Check existing decisions.md first to avoid duplicates (match by date and keywords)

### Step 5: Replace with Summaries

At the end of `notes.md`, add an "Archived Sessions" section:

```
---

## Archived Sessions

### YYYY-MM-DD through YYYY-MM-DD (Period Label)

See `archived/notes/notes-YYYY-MM.md`

Key events:
- YYYY-MM-DD: brief description
- YYYY-MM-DD: brief description
[5-10 bullets covering major milestones]
```

For older months (more than 3 months ago), collapse to a single line:

```
- YYYY-MM: Brief topic summary. See `archived/notes/notes-YYYY-MM.md`
```

### Step 5b: Summary Cap

After adding the new summary, count lines in the "Archived Sessions" section. If it exceeds 50 lines:
1. Find entries older than 3 months from today
2. Collapse each to the single-line format above
3. The INDEX.md has full detail, so no information is lost

### Step 6: Report

Show:
- Files created or updated (archive files, INDEX.md, decisions.md)
- New `notes.md` line count vs. target (600-700)
- Number of decisions extracted
- Total token savings (archived lines × 4)
- Whether summary cap was applied

## Help-Mode Teaching Note (T7)

After Step 6, read `help_mode` from `<vault_root>/config.yaml`. If `on` (or the key is absent), append this note after the final report. If `off`, skip silently.

"Long notes and todo files cost tokens on every /project load and /sync. /archive-docs moves old entries into archived/ with an index, so history is kept without the load cost. Watch for the suggestion after notes.md passes 1000 lines."

## Cross-Reference Protection

Before archiving, check whether any entries mention task titles from open todo items. Flag matches:

```
Flagged (mentions open todos):
- 2025-12-20: Setup notes — mentions "pipeline automation" (open task)
  Archive anyway? [y/N]
```

## Edge Cases

- No date header / unparseable format: keep (might be recent)
- Archive file already exists: append, never overwrite
- Entry mentions open todo: flag for review
- `archived/` does not exist: create silently
- Empty section after archiving: remove orphaned headers
- No decisions found in batch: skip `decisions.md` update
- `decisions.md` does not exist: create with `# Project Decisions` header
- `INDEX.md` does not exist: create with `# Archive Index` header
- Archived Sessions section under 50 lines: skip summary cap
- Duplicate decision in `decisions.md`: skip (match by date and keywords)
