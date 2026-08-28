#!/usr/bin/env python3
"""PreToolUse hook: reject Write calls that use banned filename suffixes like
FINAL, DONE, COMPLETE, READY, APPROVED, PUBLISHED.

Matcher: Write
Behavior: deny with suggestion to use v1, v2, v3 instead.
Exception: files inside a deliverables/ folder use simple descriptive names,
no versions needed, so the check is skipped there.
"""
import json
import re
import sys

BANNED = ("FINAL", "DONE", "COMPLETE", "READY", "APPROVED", "PUBLISHED")

try:
    input_data = json.load(sys.stdin)
except json.JSONDecodeError:
    sys.exit(0)

tool_name = input_data.get("tool_name", "")
tool_input = input_data.get("tool_input", {})
file_path = tool_input.get("file_path", "")

if tool_name != "Write" or not file_path:
    sys.exit(0)

if "/deliverables/" in file_path:
    sys.exit(0)

filename = file_path.rsplit("/", 1)[-1]
name_without_ext = filename.rsplit(".", 1)[0]

pattern = r"(?i)(?:^(" + "|".join(BANNED) + r")$|.+[-_](" + "|".join(BANNED) + r")(?:[-_]?v?\d*)?$)"
match = re.search(pattern, name_without_ext)
if not match:
    sys.exit(0)

banned_word = (match.group(1) or match.group(2)).upper()
reason = (
    f'Filename "{filename}" contains banned word "{banned_word}". '
    "Naming convention: use v1, v2, v3 for versions; never FINAL, DONE, "
    "COMPLETE, READY, APPROVED, or PUBLISHED.\n\n"
    "Retry with a v{N} suffix or a simpler descriptive name. "
    "Exception: files in deliverables/ folders can use simple descriptive "
    "names without versions."
)

output = {
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }
}
print(json.dumps(output))
sys.exit(0)
