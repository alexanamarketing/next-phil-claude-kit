#!/usr/bin/env python3
"""PreToolUse hook: warn (never block) when a CLAUDE.md write looks bloated.

Matcher: Edit|Write
A CLAUDE.md is injected into context every turn, so bloat is a recurring token
tax. This hook nudges toward the standard at ~/.claude/references/claude-md-standard.md:
- size: warns when the GLOBAL ~/.claude/CLAUDE.md grows past its line/byte cap
  (it loads every turn, so its size is a recurring token cost)
- completed: a "## Completed" section (history belongs in notes.md/todo.md)
- dated: dated history headings like "## 2026-07-08 ..." (belongs in notes.md)
- table: a data table over 5 rows (belongs in a reference doc)
- inventory: an unbroken bullet run over 20 lines (belongs in a reference doc)
- import: an unbackticked @path import (loads eagerly at launch, saves nothing;
  use a backticked path pointer read on demand instead)
Warn-once per file/rule/day via additionalContext. Always exits 0; fails open.
Escape hatches: <!-- claude-md-hygiene: allow rule1,rule2 --> in the file,
or CLAUDE_MD_HYGIENE_BYPASS=1 in the environment.
"""
import datetime
import json
import os
import re
import sys

STATE_FILE = os.environ.get(
    "CLAUDE_MD_HYGIENE_STATE",
    os.path.expanduser("~/.claude/hooks/state/claude-md-hygiene-warnings.json"),
)
BYTE_CAP = 250 * 1024
STANDARD = "~/.claude/references/claude-md-standard.md"
GLOBAL_PATH = os.path.expanduser("~/.claude/CLAUDE.md")
# Size check applies to the GLOBAL ~/.claude/CLAUDE.md only (it loads every turn).
GLOBAL_LINE_LIMIT = 200
# Byte cap for the GLOBAL ~/.claude/CLAUDE.md only (~40,000 B ~= 10,000 tokens).
# Warn-only, never blocks. The 0.70 headroom target means it nudges before the cap.
GLOBAL_BYTE_CAP = 40000
GLOBAL_HEADROOM_FRAC = 0.70
TABLE_ROW_LIMIT = 5
BULLET_RUN_LIMIT = 20


def read_stdin():
    try:
        return json.load(sys.stdin)
    except json.JSONDecodeError:
        return None


def build_pending_content(tool_name, tool_input, file_path):
    """Return (content, full_doc). full_doc=True when content is the whole file."""
    if tool_name == "Write":
        return tool_input.get("content", ""), True
    current = None
    try:
        if os.path.isfile(file_path) and os.path.getsize(file_path) <= BYTE_CAP:
            with open(file_path, encoding="utf-8", errors="replace") as f:
                current = f.read()
    except OSError:
        current = None
    if tool_name == "Edit":
        old = tool_input.get("old_string", "")
        new = tool_input.get("new_string", "")
        if current is not None and old:
            if tool_input.get("replace_all"):
                return current.replace(old, new), True
            if current.count(old) == 1:
                return current.replace(old, new, 1), True
        return new, False
    if tool_name == "MultiEdit":
        edits = tool_input.get("edits", [])
        if current is not None:
            pending = current
            ok = True
            for e in edits:
                old = e.get("old_string", "")
                if not old or old not in pending:
                    ok = False
                    break
                if e.get("replace_all"):
                    pending = pending.replace(old, e.get("new_string", ""))
                else:
                    pending = pending.replace(old, e.get("new_string", ""), 1)
            if ok:
                return pending, True
        return "\n".join(e.get("new_string", "") for e in edits), False
    return "", False


def parse_allows(*texts):
    allowed = set()
    for text in texts:
        if not text:
            continue
        for m in re.finditer(r"<!--\s*claude-md-hygiene:\s*allow\s+([a-z0-9, \-]+?)\s*-->", text):
            for tok in re.split(r"[,\s]+", m.group(1)):
                if tok:
                    allowed.add(tok.strip())
    return allowed


def line_flags(lines):
    """Per-line booleans: (in_fence, in_frontmatter)."""
    flags = []
    in_fence = False
    in_front = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if i == 0 and stripped == "---":
            in_front = True
            flags.append((False, True))
            continue
        if in_front:
            flags.append((False, True))
            if stripped == "---":
                in_front = False
            continue
        if re.match(r"^\s*(```|~~~)", line):
            flags.append((True, False))
            in_fence = not in_fence
            continue
        flags.append((in_fence, False))
    return flags


def check(content, full_doc, file_path, allowed):
    warns = []
    lines = content.split("\n")
    flags = line_flags(lines)

    def active(rule):
        return rule not in allowed and "all" not in allowed

    # Size is a claim the contract owns for every vault CLAUDE.md. What is left
    # here is the GLOBAL file, which no other enforcer sees. It loads every turn,
    # so we bound both its byte size (the real token tax) and its line count.
    if active("size") and full_doc and file_path == GLOBAL_PATH:
        nbytes = len(content.encode("utf-8"))
        if nbytes > GLOBAL_BYTE_CAP:
            warns.append(
                "size: %d tok (trim to ~%d, cap ~%d; every token loads every turn)"
                % (nbytes // 4, int(GLOBAL_BYTE_CAP * GLOBAL_HEADROOM_FRAC) // 4,
                   GLOBAL_BYTE_CAP // 4)
            )
        elif len(lines) > GLOBAL_LINE_LIMIT:
            warns.append(
                "size: %d lines (target under ~%d; every line loads every turn)"
                % (len(lines), GLOBAL_LINE_LIMIT)
            )

    table_run = 0
    bullet_run = 0
    table_warned = False
    inventory_warned = False
    for i, line in enumerate(lines):
        in_fence, in_front = flags[i]
        if in_fence or in_front:
            table_run = 0
            bullet_run = 0
            continue
        m = re.match(r"^(#{2,6})\s+(.*)$", line)
        if m:
            text = m.group(2).strip()
            if active("completed") and re.match(r"^Completed\b", text):
                warns.append("completed: '## Completed' history belongs in notes.md/todo.md, not CLAUDE.md (line %d)" % (i + 1))
            if active("dated") and re.search(r"\d{4}-\d{2}-\d{2}", text):
                warns.append("dated: dated history headings belong in notes.md (line %d: %r)" % (i + 1, text[:40]))
        if line.lstrip().startswith("|"):
            table_run += 1
            if active("table") and not table_warned and table_run - 2 > TABLE_ROW_LIMIT:
                warns.append("table: data table over %d rows belongs in a reference doc, linked by one line" % TABLE_ROW_LIMIT)
                table_warned = True
        else:
            table_run = 0
        scrubbed = re.sub(r"`[^`]*`", "", line)
        if active("import") and re.search(r"(^|\s)@[~./A-Za-z0-9]", scrubbed):
            warns.append("import: '@path' imports load eagerly at launch and save no context; use a backticked path pointer instead (line %d)" % (i + 1))
        if re.match(r"^\s*-\s+\S", line):
            bullet_run += 1
            if active("inventory") and not inventory_warned and bullet_run > BULLET_RUN_LIMIT:
                warns.append("inventory: %d+ consecutive bullets reads like a data inventory; move to a reference doc" % BULLET_RUN_LIMIT)
                inventory_warned = True
        else:
            bullet_run = 0
    return warns


def filter_warn_once(file_path, warns):
    """Only surface each (file, rule) warning once per day."""
    today = datetime.date.today().isoformat()
    state = {}
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            state = json.load(f)
    except (OSError, json.JSONDecodeError):
        state = {}
    state = {k: v for k, v in state.items() if v == today}
    fresh = []
    seen_rules = []
    for w in warns:
        rule = w.split(":", 1)[0]
        if rule in seen_rules:
            continue
        seen_rules.append(rule)
        key = "%s|%s" % (file_path, rule)
        if state.get(key) != today:
            state[key] = today
            fresh.append(w)
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except OSError:
        pass
    return fresh


def main():
    if os.environ.get("CLAUDE_MD_HYGIENE_BYPASS") == "1":
        sys.exit(0)
    data = read_stdin()
    if not data:
        sys.exit(0)
    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    if tool_name not in ("Edit", "Write", "MultiEdit") or os.path.basename(file_path) != "CLAUDE.md":
        sys.exit(0)

    content, full_doc = build_pending_content(tool_name, tool_input, file_path)
    if not content or len(content) > BYTE_CAP:
        sys.exit(0)

    existing_head = ""
    try:
        if os.path.isfile(file_path):
            with open(file_path, encoding="utf-8", errors="replace") as f:
                existing_head = f.read(2000)
    except OSError:
        pass
    allowed = parse_allows(content, existing_head)

    warns = check(content, full_doc, file_path, allowed)
    fresh = filter_warn_once(file_path, warns) if warns else []
    if fresh:
        out = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": (
                    "claude-md-hygiene (warn-only, write allowed): CLAUDE.md loads every turn, keep it lean.\n- "
                    + "\n- ".join(fresh)
                    + "\nStandard: %s" % STANDARD
                ),
            }
        }
        print(json.dumps(out))
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        sys.exit(0)
