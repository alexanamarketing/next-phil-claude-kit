#!/usr/bin/env python3
"""PostToolUse wrapper for writing-lint. Advisory only: after a Write or Edit to a
prose file, it surfaces writing-quality findings (AI-tell words, em dashes, weasel
words, hollow phrases) to the assistant as a note. It NEVER blocks the write and
always exits 0, so a non-technical user is never stopped over a wording nit.

Prose files only (.md/.markdown/.mdx/.txt/.eml). On an Edit only the newly written
text is linted; a Write lints the whole file. Fails open on any error.
"""
import json
import os
import sys

LINT = os.path.expanduser("~/.claude/hooks/writing-lint")
PROSE_EXT = {".md", ".markdown", ".mdx", ".txt", ".eml"}
EDIT_TOOLS = {"Edit", "MultiEdit"}


def _load_engine():
    from importlib.machinery import SourceFileLoader
    import importlib.util
    loader = SourceFileLoader("writing_lint_cli", LINT)
    spec = importlib.util.spec_from_loader("writing_lint_cli", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def _new_text(tool_name, tool_input):
    if tool_name not in EDIT_TOOLS:
        return None
    if tool_name == "MultiEdit":
        edits = tool_input.get("edits") or []
        parts = [e.get("new_string", "") for e in edits if e.get("new_string")]
        return "\n\n".join(parts)
    return tool_input.get("new_string", "")


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    try:
        tool_name = data.get("tool_name", "")
        tool_input = data.get("tool_input", {}) or {}
        path = tool_input.get("file_path") or tool_input.get("path")
        if not path:
            return 0
        ext = os.path.splitext(path)[1].lower()
        if ext not in PROSE_EXT or not os.path.isfile(path):
            return 0

        wl = _load_engine()
        snippet = _new_text(tool_name, tool_input)
        if snippet is not None:
            if not snippet.strip():
                return 0
            text, scope_label = snippet, "in the edited text of"
        else:
            with open(path, encoding="utf-8") as f:
                text = f.read()
            scope_label = "in"

        result = wl.lint_text(text, surface="write", path=path)
        if result.get("excluded"):
            return 0
        findings = [f for f in result["findings"] if not f["suppressed"]]
        if not findings:
            return 0
        genre = result.get("genre") or "base-voice"
        lines = ["writing-lint ({}) flagged {} item(s) {} {}:".format(
            genre, len(findings), scope_label, os.path.basename(path))]
        for f in findings:
            m = " [{}]".format(f["match"]) if f.get("match") else ""
            lines.append("  L{} {} {}{}: {}".format(
                f.get("line", "?"), f.get("severity", "?"),
                f.get("rule_id", "?"), m, f.get("message", "")))
        if snippet is not None:
            lines.append("(Line numbers are relative to the edited text.)")
        lines.append("Advisory only (this write is not blocked). Fix or leave as-is.")
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": "\n".join(lines),
            }
        }))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
