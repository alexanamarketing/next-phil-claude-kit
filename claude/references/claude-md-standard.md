# CLAUDE.md standard (keep it lean)

A CLAUDE.md file is loaded into Claude's context on every single turn, so every
line in it costs you a little speed and money forever. Keep it short and current.
The `claude-md-hygiene` hook warns (it never blocks) when a CLAUDE.md drifts from
these rules.

## What belongs in a CLAUDE.md

- The handful of standing facts Claude needs every time it works on this project:
  who it is for, where things live, the few rules that always apply.
- Pointers, not contents. Link to a longer reference doc by its path instead of
  pasting the whole thing in.

## What does NOT belong

- History. A "## Completed" section or dated headings ("## 2026-07-08 ...") belong
  in notes.md, not here.
- Big data tables (more than about 5 rows). Move them to a reference doc and link it.
- Long unbroken bullet lists (more than about 20 lines). That reads like an
  inventory; move it to a reference doc.
- Eager `@path` imports. A backticked path pointer that Claude reads only when it
  needs it is lighter than an `@import` that loads every launch.

## Size

The global `~/.claude/CLAUDE.md` is the heaviest, since it loads for every project.
Aim to keep it under about 200 lines. If the hook warns you are over, trim to
comfortably under the limit rather than right at the edge, so it does not warn again
on the next edit.

## Escape hatches

If a warning is a false alarm for a specific file, add a comment to that file:
`<!-- claude-md-hygiene: allow table,dated -->` (list the rule names to silence), or
set `CLAUDE_MD_HYGIENE_BYPASS=1` in the environment to silence it entirely.
