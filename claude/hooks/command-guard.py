#!/usr/bin/env python3
"""PreToolUse guard for Bash commands: the seatbelt for a non-technical user.

Blocks a small set of universally dangerous command shapes that the settings.json
deny globs cannot reliably match (a glob for `rm -rf *` misses `rm -fr`, `rm -r -f`,
and any delete that is not the first token). This hook matches the CLASS of danger,
so wording variations cannot slip past.

Rules:
  1. fetch piped or fed into a shell — the classic "paste this one-line installer"
     trap. Covers the pipe form (curl ... | sh), process substitution
     (bash <(curl ...)), and command substitution (sh -c "$(curl ...)").
  2. base64 decode piped into a shell or eval (obfuscated execution).
  3. recursive force-delete of a root-level or home path.
  4. chmod 777 / 666.
  5. recursive force-delete inside the user's configured vault (their documents) —
     asks them to send it to the Trash instead so it is recoverable, unless the
     target is a disposable build/cache dir.

Contract (Claude Code PreToolUse):
  stdin  - JSON: {"tool_name": "Bash", "tool_input": {"command": "..."}}
  exit 0 - allow (also on any parse error: fail open so a malformed payload cannot
           brick every Bash call)
  exit 2 - block; stderr text is fed back to the model as the reason
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
try:
    import hook_config  # type: ignore
except Exception:
    hook_config = None

# Shell binaries that turn text into execution.
SHELLS = r"(?:ba|z|da|k|fi)?sh"
FETCH = r"(?:curl|wget|fetch)"

# Filesystem roots where a recursive force-delete is never a sane action.
DANGEROUS_RM_TARGETS = (
    r"/(?:\s|$|\*)",           # rm -rf /  or  /*
    r"~/?(?:\s|$|\*)",         # rm -rf ~  or  ~/*
    r"\$HOME\b/?(?:\s|$|\*)",  # rm -rf $HOME
    r"/(?:home|Users|etc|usr|var|boot|bin|sbin|lib(?:64)?|opt|root|srv|sys|proc|dev)\b/?(?:\s|$|\*)",
)

# Recursive-force rm in either flag order or split across flags.
RM_FORCE = (
    r"\brm\s+(?:-[a-zA-Z]+\s+)*"
    r"(?:-[a-zA-Z]*(?:r[a-zA-Z]*f|f[a-zA-Z]*r)[a-zA-Z]*|"
    r"(?:-[a-zA-Z]*[rf][a-zA-Z]*\s+)+-[a-zA-Z]*[rf][a-zA-Z]*)\s+"
)

# Regenerable directories: rm -rf on these is routine, never data loss.
DISPOSABLE = (
    "node_modules", ".next", ".turbo", ".cache", ".venv", "__pycache__",
    "dist", "build", "out", "coverage", ".pytest_cache",
)

RM_TARGET_RE = re.compile(RM_FORCE + r"(?P<target>(?:\"[^\"]+\"|'[^']+'|[^\s;|&]+))")

RULES = [
    (
        # Fetch-and-execute in any of its three common shapes.
        re.compile(
            rf"\b{FETCH}\b[^|;&\n]*\|\s*(?:sudo\s+)?(?:env\s+\S+\s+)?{SHELLS}\b"       # curl ... | sh
            rf"|\b{SHELLS}\b[^\n]*<\(\s*{FETCH}\b"                                      # bash <(curl ...)
            rf"|\b{SHELLS}\s+-c\s*[\"']?\s*(?:\$\(|`)\s*(?:sudo\s+)?{FETCH}\b"          # sh -c "$(curl ...)"
        ),
        "pipe-to-shell (fetching content and running it in one step) is blocked. "
        "This is how a malicious one-line installer works. Download the file first, "
        "open it and read it, then run it explicitly if it is safe",
    ),
    (
        re.compile(
            rf"base64\b[^|;&\n]*(?:-d|--decode)[^|;&\n]*\|\s*(?:sudo\s+)?{SHELLS}\b"
            rf"|(?:eval|{SHELLS})\s*[\"']?\s*(?:\$\(|`)[^)`]*base64"
        ),
        "base64-decode-into-shell is blocked (a way to hide what a command really "
        "does). Decode it to a file and read it before running anything",
    ),
    (
        re.compile(RM_FORCE + r"(?:" + "|".join(DANGEROUS_RM_TARGETS) + r")"),
        "recursive force-delete of a root-level or home path is blocked",
    ),
    (
        re.compile(r"\bchmod\s+(?:-[a-zA-Z]+\s+)*0?(?:777|666)\b"),
        "chmod 777/666 is blocked. Grant the narrowest permission that works (755/644, or u+x)",
    ),
]


def protected_roots():
    """The user's vault (their documents) is the tree we protect from an
    accidental permanent recursive delete. Read from config; empty if unavailable
    (then only the catastrophic root/home rule applies)."""
    roots = []
    if hook_config is not None:
        try:
            roots.append(os.path.normpath(str(hook_config.vault_root())))
        except Exception:
            pass
    return tuple(r for r in roots if r and r != "/")


def trash_hint():
    """The user's configured 'move to trash' command, for the block message."""
    if hook_config is not None:
        try:
            return str(hook_config.os_trash())
        except Exception:
            pass
    return "the Trash"


def protected_rm_target(command, cwd):
    """Return the target path if this is an rm -rf inside the protected vault.

    Skips an unresolved shell variable (do not guess it into the vault) and
    anything under /tmp (disposable scratch). The catastrophe rule is unaffected.
    """
    roots = protected_roots()
    if not roots:
        return None
    for match in RM_TARGET_RE.finditer(command):
        raw = match.group("target").strip("\"'")
        if any(part in raw for part in DISPOSABLE):
            continue
        path = os.path.expanduser(os.path.expandvars(raw))
        if "$" in path:
            continue
        if not os.path.isabs(path):
            path = os.path.join(cwd or os.getcwd(), path)
        path = os.path.normpath(path)
        if path == "/tmp" or path.startswith("/tmp/"):
            continue
        if any(path == root or path.startswith(root + os.sep) for root in roots):
            return raw
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        command = payload.get("tool_input", {}).get("command", "")
        cwd = payload.get("cwd", "")
    except Exception:
        return 0  # fail open: never brick Bash on a bad payload

    if not isinstance(command, str) or not command:
        return 0

    for pattern, reason in RULES:
        if pattern.search(command):
            print(f"command-guard: {reason}. Command: {command!r}", file=sys.stderr)
            return 2

    target = protected_rm_target(command, cwd)
    if target:
        print(
            f"command-guard: a recursive delete inside your documents folder is "
            f"blocked so nothing is lost by accident. Send it to {trash_hint()} "
            f"instead so it can be recovered. Command: {command!r}",
            file=sys.stderr,
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
