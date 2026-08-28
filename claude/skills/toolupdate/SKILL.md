---
name: toolupdate
description: Sweep the current session for durable tool facts and write them into the tool-knowledge store as structured records, with one dated notes.md breadcrumb. Run by hand at session wrap.
disable-model-invocation: true
---

# /toolupdate - Save what Claude learned about your tools

This is how Claude's memory of your tools (Gmail, FlexMLS, GoHighLevel, Canva, and
the rest) fills itself in. At the end of a session, it looks back over the work,
picks out any durable fact worth keeping about a tool (a step that always trips you
up, a setting that matters), and saves it. Next time you touch that tool, Claude
reads its notes back.

Two halves with a hard seam. Claude does the first: read this session and decide
which durable, generally-true tool facts are worth keeping, then shape each into a
candidate record. A deterministic helper does the second: it checks, routes, and
saves those records, and drops one dated line in the project's notes.md. Claude's
judgement decides WHAT is kept; the helper owns HOW it lands.

Storage: each tool is one file, `~/.claude/references/tool-modules/<tool>.md`, with
a fenced ```json records block. The helper writes through `tool_module_store`.

## When to use

At session wrap, after real tool work, when Claude learned a durable trap, recipe,
or correction about a tool. You type `/toolupdate`. One record per fact; a session
may yield zero, and that is fine.

## The keep-bar (Step 1: sweep)

Keep a fact only if ALL hold. When any fails, drop it:

- DURABLE: true next month, not a passing state. "FlexMLS export is under the
  Actions menu" keeps; "this listing is pending right now" does not.
- GENERAL, not about one client's data. A specific client's name, phone, or list
  size belongs in that project's own notes, never this shared tool memory. A
  record's `applicability` is `global` or `machine` only.
- ONE FACT: one problem, one fix, each a single sentence under 300 characters. A
  paragraph carrying several traps splits into several records.
- WORTH IT: it changes what a future session does on this tool.

A correction to an existing record is a keep: list the id(s) it retires in
`supersedes`, and the helper archives the old version for you.

## New tool with no module yet (do this BEFORE shaping the record)

If a kept fact is about a tool that has NO
`~/.claude/references/tool-modules/<tool>.md`, the store rejects it and nothing
lands. Create the module first: run `python3 ~/.claude/hooks/tool-module-new.py
<tool>` (add `--host <domain>` for a website tool). That writes the file with an
empty records block, wires up detection in `tool-module-brief.py`, seeds the
`<tool>/api` glossary tag, and adds the INDEX line. Only once the module exists does
the record save succeed.

## Shape each fact into a record (Step 2)

One JSON object per fact, every field present (the helper rejects a malformed or
mis-tagged record rather than write it):

| field | value |
|---|---|
| `id` | stable slug, `<tool>-` prefixed, e.g. `flexmls-saved-search-radius` |
| `date` | first-confirmed date, `YYYY-MM-DD` |
| `last_verified` | `null` (or a date if you reconfirmed an older fact) |
| `tags` | array from the glossary, ALL in one tool's namespace, e.g. `["flexmls/search"]` |
| `load` | `always` if it can bite on any touch of this tool; else `scoped` |
| `severity` | `critical` / `high` / `normal` - cost if ignored (independent of load) |
| `applicability` | `global` or `machine` |
| `problem` | the trap or behaviour, one sentence |
| `fix` | the correct move, one sentence |
| `confidence` | `confirmed` / `inferred` / `unverified` |
| `evidence` | array of `{type, ref}`, type in `file/url/help-article/observation` |
| `supersedes` | array of retired ids (empty if new) |

Routing is automatic: the tool is the tags' namespace (`flexmls/search` ->
`flexmls.md`), so pick the right tags and the record files itself. When a fact needs
a tag the glossary lacks, add it once (it logs the addition), then use it:

```
python3 -c "import sys; sys.path.insert(0,'$HOME/.claude/hooks'); \
import tool_module_schema as s; print(s.extend_glossary('<tool>/<area>', '<why>'))"
```

Keep the `load: always` tier tiny; most facts are `scoped`.

## Write them (Step 3)

Put the facts and the project's notes.md path in one plan file, then run the helper once:

```
# plan.json
{"facts": [ <record>, <record>, ... ],
 "notes_path": "/abs/path/to/<project>/notes.md"}
```

```
python3 ~/.claude/hooks/toolupdate_apply.py --plan plan.json
```

`notes_path` is the current project's notes.md. Preview first with `--dry-run`
(checks and routes, writes nothing). The helper prints a JSON summary: `written`
ids, `failed` (each with a reason and a `status`), and the `notes_line` it appended.

On a `failed` entry, fix by status and re-run only that fact: `invalid` = a field
broke a schema or glossary rule (the reason names it); `no-records-block` = that
module file has no records block yet (create the module as above); `stale` = a
concurrent correction landed first, so re-read the current record and rebuild your
`supersedes`.

## Report (Step 4)

State the count written and to which modules, the one notes.md line, and any facts
dropped for the keep-bar. The records and the breadcrumb are the record; do not
leave a todo to "review" the writes.
