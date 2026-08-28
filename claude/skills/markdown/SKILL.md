---
name: markdown
description: Load markdown formatting rules for this session. The markdown-rules hook enforces these on every .md write — invoke this skill only when you want the rules explained.
---

# /markdown - Markdown Style Reference

The `markdown-rules.py` hook enforces these rules automatically on every `.md` write. This skill is for when you want to review the rules explicitly or share them in context.

The full guide lives at `<vault_root>/docs/MARKDOWN-STYLE-GUIDE.md`.

## Quick Rules

1. Working files are plain text — files in `working-files/` or named `temp-*` are for copy/paste. No markdown formatting (`#`, `##`, `-`, `**`). Just plain text.
2. Lists for key-value pairs — never bold labels like `**Client:** Name`. Use `- Client: Name` instead.
3. Hyphens for bullets — use `-` not `*` or `+`
4. No skipped heading levels — H1 to H2 to H3, never H1 to H3
5. Tables only for 2D data — if it is just key-value pairs, use a list
6. Emphasis sparingly — bold only for critical emphasis in prose, not for labels or structure
7. Single blank lines — never double blank lines between elements
8. No trailing punctuation on headings — `## Section` not `## Section:`
9. Horizontal rules sparingly — only for major section breaks
10. No decoration — no `=====` banners or ASCII art
11. End files with a single newline — no trailing blank lines

## Before Writing Any Markdown File

- Is this a working file or temp file? If yes, use plain text only.
- Using lists instead of bold labels?
- Hyphens for bullets?
- Proper heading hierarchy?
- Tables only where data is truly two-dimensional?

Acknowledge these rules are active for this session.
