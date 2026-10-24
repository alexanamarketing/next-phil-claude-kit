#!/usr/bin/env python3
"""sitedoor-guard: keep the editor token out of the conversation.

A PreToolUse hook on Bash. It blocks EVERY command whose text names the editor
token's Keychain item (next-phil-editor), with no exemption. A command that names
the item can only be a lookup, a store or a search of the token, and any of those
could print the token into the conversation. The sitedoor tool reads the token
inside its own process and never names the item on its command line, so a normal
sitedoor run is never blocked. The user adds the token once in Terminal, outside
Claude, as the setup note says.

Exit 2 with a reason on stderr blocks the command; exit 0 lets it run. A payload
that cannot be read fails open (exit 0) so a bad payload never bricks Bash.
"""
import json
import sys

ITEM = "next-phil-editor"


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        command = payload.get("tool_input", {}).get("command", "")
    except Exception:
        return 0
    if not isinstance(command, str) or not command:
        return 0
    if ITEM in command.lower():
        print(
            "sitedoor-guard: this command names the editor token's Keychain item, so it could "
            "show the token in the conversation, and it is blocked. Use the sitedoor tool "
            "(python3 ~/.claude/skills/sitedoor/tools/sitedoor.py whoami) instead. If the token "
            "is missing, ask the user to add it themselves in Terminal, following the setup note.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
