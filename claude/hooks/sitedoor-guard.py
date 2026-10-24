#!/usr/bin/env python3
"""sitedoor-guard: keep the editor token out of the conversation.

A PreToolUse hook on Bash. It blocks, with no exemption:

- any command that names the editor token's Keychain item (next-phil-editor),
  read after undoing shell quoting and escapes: quotes, backslashes, $'...'
  escapes (\\xHH, \\NNN, \\uHHHH), $VAR and ${VAR} markers are stripped first, so
  next-phil-"editor", next-phil-\\editor or $'next-phil-\\x65ditor' still match;
- any command where "next-phil" and "editor" both appear, which catches the name
  split across a variable (S=next-phil; ... $S-editor);
- a Keychain password lookup (find-generic-password with -w or -g) for account
  phil or phil-*, or one with no -s service at all (it would return the first
  password it finds), and dump-keychain -d.

The sitedoor tool reads the token inside its own process and never names the item
on its command line, so a normal sitedoor run is never blocked. The user adds the
token once in Terminal, outside Claude, as the setup note says.

This hook only catches accidents and the easy ways round; a determined script can
still get past a text match. The real control is the tool itself: it keeps the
token in its own process and sends it only to the live door.

Exit 2 with a reason on stderr blocks the command; exit 0 lets it run. A payload
that cannot be read fails open (exit 0) so a bad payload never bricks Bash.
"""
import json
import re
import sys

ITEM = "next-phil-editor"

HEX = re.compile(r"\\x([0-9a-fA-F]{2})")
UNI = re.compile(r"\\u([0-9a-fA-F]{4})")
OCT = re.compile(r"\\([0-7]{1,3})")
PASSWORD_FLAG = re.compile(r"(?:^|\s)-[a-z]*[wg][a-z]*(?=\s|$)")
ACCOUNT_PHIL = re.compile(r"(?:^|\s)-a\s+phil(?:-|\s|$)")
SERVICE_FLAG = re.compile(r"(?:^|\s)-s\s")
DUMP_SECRETS = re.compile(r"(?:^|\s)-[a-z]*d[a-z]*(?=\s|$)")


def normalise(command):
    text = HEX.sub(lambda m: chr(int(m.group(1), 16)), command)
    text = UNI.sub(lambda m: chr(int(m.group(1), 16)), text)
    text = OCT.sub(lambda m: chr(int(m.group(1), 8)), text)
    for ch in ('"', "'", "\\", "$", "{", "}", "`"):
        text = text.replace(ch, "")
    return text.lower()


def reason_for(command):
    text = normalise(command)
    if ITEM in text or ("next-phil" in text and "editor" in text):
        return "names the editor token's Keychain item"
    if "find-generic-password" in text and PASSWORD_FLAG.search(text):
        if ACCOUNT_PHIL.search(text) or not SERVICE_FLAG.search(text):
            return "asks the Keychain for a password that may be the editor token"
    if "dump-keychain" in text and DUMP_SECRETS.search(text):
        return "dumps Keychain passwords"
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        command = payload.get("tool_input", {}).get("command", "")
    except Exception:
        return 0
    if not isinstance(command, str) or not command:
        return 0
    why = reason_for(command)
    if why:
        print(
            "sitedoor-guard: this command %s, so it could show the token in the conversation, "
            "and it is blocked. Use the sitedoor tool (sitedoor.py whoami) instead. If the token "
            "is missing, ask the user to add it themselves in Terminal, following the setup note." % why,
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
