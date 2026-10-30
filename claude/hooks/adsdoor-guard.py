#!/usr/bin/env python3
"""adsdoor-guard: keep the ads check token out of the conversation.

A PreToolUse hook on Bash, the twin of sitedoor-guard.py. It blocks, with no
exemption:

- any command that names the ads check token's Keychain item
  (next-phil-ads-status), read after undoing shell quoting and escapes: quotes,
  backslashes, $'...' escapes (\\xHH, \\NNN, \\uHHHH), $VAR and ${VAR} markers are
  stripped first, so next-phil-"ads-status" or $'next-phil-\\x61ds-status' still
  match;
- any command where "next-phil", "ads" and "status" all appear, which catches the
  name split across a variable (S=next-phil-ads; ... ${S}-status); the kit's own
  folder name (next-phil-claude-kit) does not count as "next-phil" for this rule;
- a Keychain password lookup (find-generic-password with -w or -g) for account
  phil or phil-*, or one with no -s service at all, and dump-keychain -d. Commas,
  brackets, parentheses and + count as spaces, so the same lookup written as a
  Python list is caught too, and a name glued together with + is read joined up;
- any command that loads the adsdoor tool as a Python module or calls its token
  reader: import adsdoor, from adsdoor, adsdoor.read_token, or read_token or
  _SECRETS as whole names;
- any command that names ADSDOOR_TOKEN, the variable the tool's tests and the
  kit's rehearsals use to hand it a test token.

The adsdoor tool reads the token inside its own process and never names the item
on its command line, so a normal adsdoor run is never blocked. The user adds the
token once in Terminal, outside Claude, as the setup message says.

This hook only catches accidents and the easy ways round; a determined script can
still get past a text match. The real control is the tool itself: it keeps the
token in its own process and sends it only to the live ads check.

Exit 2 with a reason on stderr blocks the command; exit 0 lets it run. A payload
that cannot be read fails open (exit 0) so a bad payload never bricks Bash.
"""
import json
import re
import sys

ITEM = "next-phil-ads-status"
KIT_FOLDER = "next-phil-claude-kit"
TEST_VAR = "adsdoor_token"

HEX = re.compile(r"\\x([0-9a-fA-F]{2})")
UNI = re.compile(r"\\u([0-9a-fA-F]{4})")
OCT = re.compile(r"\\([0-7]{1,3})")
PASSWORD_FLAG = re.compile(r"(?:^|\s)-[a-z]*[wg][a-z]*(?=\s|$)")
ACCOUNT_PHIL = re.compile(r"(?:^|\s)-a\s+phil(?:-|\s|$)")
SERVICE_FLAG = re.compile(r"(?:^|\s)-s\s")
DUMP_SECRETS = re.compile(r"(?:^|\s)-[a-z]*d[a-z]*(?=\s|$)")

# Whole identifiers only: realtor_secrets or HANDOFF_READ_TOKEN in the website repo
# contain the same letters and must pass.
TOKEN_READER = re.compile(
    r"import\s+adsdoor\b|from\s+adsdoor\b|adsdoor\.(?:read_token|_secrets)\b"
    r"|(?<![a-z0-9_])(?:read_token|_secrets)(?![a-z0-9_])"
)
SEPARATORS = (",", "[", "]", "(", ")", "+")


def unquote(command):
    text = HEX.sub(lambda m: chr(int(m.group(1), 16)), command)
    text = UNI.sub(lambda m: chr(int(m.group(1), 16)), text)
    text = OCT.sub(lambda m: chr(int(m.group(1), 8)), text)
    for ch in ('"', "'", "\\", "$", "{", "}", "`"):
        text = text.replace(ch, "")
    return text.lower()


def normalise(command):
    text = unquote(command)
    for ch in SEPARATORS:
        text = text.replace(ch, " ")
    return text


def names_item(text):
    rest = text.replace(KIT_FOLDER, "")
    return ITEM in text or ("next-phil" in rest and "ads" in rest and "status" in rest)


def reason_for(command):
    text = normalise(command)
    joined = unquote(command).replace("+", "")
    if names_item(text) or names_item(joined):
        return "names the ads check token's Keychain item"
    if TEST_VAR in text:
        return "reads the ads check's test token variable"
    if TOKEN_READER.search(text):
        return "loads the adsdoor tool's token reader"
    if "find-generic-password" in text and PASSWORD_FLAG.search(text):
        if ACCOUNT_PHIL.search(text) or not SERVICE_FLAG.search(text):
            return "asks the Keychain for a password that may be the ads check token"
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
            "adsdoor-guard: this command %s, so it could show the token in the conversation, "
            "and it is blocked. Use the adsdoor tool (adsdoor.py --all, or --agent <slug>) instead; "
            "it reads the token itself and never shows it. If the token is missing, ask the user to "
            "add it themselves in Terminal, following the setup message. The ads check only reads: "
            "storing a Page id, changing the text list or restarting the ads engine is Anthony's side, "
            "so offer to draft the message to Anthony with what the check found." % why,
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
