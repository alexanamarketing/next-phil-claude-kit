# Markdown Style Guide

House style for all .md files in the vault. The markdown-rules hook injects these rules before every write, so they are enforced automatically. Read this when you need to understand why a write was blocked or when writing a new skill or template.

## Core rules

- Bullets: use `-`, never `*` or `+`
- Key-value pairs: `- Key: value` or plain `Key: value`, never `**Key:** value`
- One H1 per document
- Never skip heading levels (H1 then H2 then H3, never H1 directly to H3)
- Tables only for true 2D data (rows and columns that are not just key-value pairs)
- Single blank line between elements, never double blank lines
- No trailing punctuation on headings (`## Section` not `## Section:`)
- Bold only for emphasis in running prose, not for labels or section intros
- Horizontal rules (`---`) only for major section breaks, and even then sparingly
- End every file with a single newline, no trailing blank lines

## File type rules

Different file types have different formatting requirements because they serve different audiences.

### Standard vault docs (CLAUDE.md, HANDOFF.md, notes.md, todo.md, INDEX.md)

Full markdown is fine here. Use headings, bullets, code blocks, and bold emphasis as needed.

### working-files/ reference and research docs

Basic markdown only: headings and bullets. No bold labels, no `---` separators between sections, no tables used as key-value lists. These files are often long-lived references and heavy formatting makes them harder to maintain.

### Deliverables meant for copy-paste

Plain text only. No `#`, `##`, `-`, `**`, or any markup. Write as if the file will be pasted directly into an email or message. The recipient sees the raw text, not rendered markdown.

### Temp files and drafts (`temp-*`)

Plain text. No markdown markup.

### Email drafts

Plain text. No `##` headings. Use plain section labels like `Subject:` and `Body:` if needed. The email client will not render markdown.

## Naming conventions

- Files: `lowercase-kebab-case.md`
- Versions: `v1`, `v2`, `v3` (never FINAL, DONE, COMPLETE, READY, APPROVED, PUBLISHED)
- Dates: `YYYY-MM-DD`

## INDEX.md rules

Every directory that Claude might write new files into should have an INDEX.md listing those files. The index-enforcer hook blocks writes to indexed directories when the new filename is not yet listed in the INDEX.

Required workflow before creating a new file in an indexed directory:

1. Read the INDEX.md
2. Edit the INDEX.md to add an entry for the new file
3. Write the new file

Never skip step 1 or 2. The hook will block the write and print the required sequence.

INDEX.md format: one entry per file, with a short description.

```
# Index

- filename.md — brief description of what this file contains
- another-file.md — brief description
```

Sacred files that bypass index enforcement: `INDEX.md`, `CLAUDE.md`, `HANDOFF.md`, `notes.md`, `todo.md`, `README.md`, `ABOUT.md`. You can write these without updating the INDEX first.

## Common mistakes

These are the patterns the hook catches most often:

- Using `**Label:**` at the start of a bullet instead of `- Label: value`
- Using `*` for bullets instead of `-`
- Adding double blank lines between sections
- Putting a colon at the end of a heading
- Using a table to display key-value pairs
- Naming a file `report-FINAL.md` instead of `report-v3.md`
- Skipping from H1 directly to H3
- Writing markdown in a file that will be copy-pasted
