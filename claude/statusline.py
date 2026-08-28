#!/usr/bin/env python3
"""Status line for Claude Code: the quiet bar at the bottom of the screen.

Claude Code runs this once every refresh and pipes it a JSON object on stdin.
This script prints ONE short line to stdout and always exits 0. It never crashes
the bar: any parse or read failure prints a safe minimal fallback and exits 0.

The line is tuned for a non-technical real-estate agent. It shows just three
things, no cost/token/model/git noise:

  📁 {project}   •   Helper Mode: {ON|OFF}   •   type /help for commands

  - {project}: the folder you are working in (the basename of the current dir),
    or "home" when you are sitting at the vault root or your home folder.
  - Helper Mode: ON/OFF, read from ~/.claude/helper-mode.json. Absent or
    unreadable is treated as ON, matching the kit default.

No hardcoded paths, Mac-safe. Override the state file with HELPER_MODE_STATE
(used by tests).
"""
import json
import os
import sys

# A light grey so the bar stays quiet. Claude Code allows ANSI colour escapes.
DIM = "\033[2m"
RESET = "\033[0m"
FALLBACK = "type /help for commands"


def _state_path():
    return os.environ.get("HELPER_MODE_STATE") or os.path.expanduser(
        "~/.claude/helper-mode.json"
    )


def _vault_root():
    """Read vault_root from the installer pointer file, if present."""
    try:
        pointer = os.path.expanduser("~/.claude/starter-kit/config.json")
        with open(pointer) as f:
            data = json.load(f)
        vr = data.get("vault_root")
        if isinstance(vr, str) and vr:
            return os.path.realpath(os.path.expanduser(vr))
    except Exception:
        pass
    return None


def _project_name(data):
    """Folder you are in: basename of current dir, or 'home' at the vault root."""
    workspace = data.get("workspace") or {}
    current = workspace.get("current_dir") or data.get("cwd") or ""
    if not isinstance(current, str) or not current:
        return "home"
    real = os.path.realpath(os.path.expanduser(current))
    home = os.path.realpath(os.path.expanduser("~"))
    vault = _vault_root()
    if real == home or (vault and real == vault):
        return "home"
    base = os.path.basename(real.rstrip("/"))
    return base or "home"


def _helper_mode_on():
    """Read Helper Mode state. Absent/unreadable/malformed = ON (kit default)."""
    try:
        with open(_state_path()) as f:
            data = json.load(f)
        if isinstance(data, dict) and "on" in data:
            return bool(data.get("on"))
    except Exception:
        pass
    return True


def main():
    try:
        raw = sys.stdin.read()
    except Exception:
        raw = ""
    try:
        data = json.loads(raw) if raw.strip() else {}
        if not isinstance(data, dict):
            data = {}
    except Exception:
        data = {}

    project = _project_name(data)
    helper = "ON" if _helper_mode_on() else "OFF"
    line = (
        f"{DIM}📁 {project}   •   Helper Mode: {helper}"
        f"   •   type /help for commands{RESET}"
    )
    print(line)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        # Never break the bar: print a safe minimal fallback and exit 0.
        try:
            print(FALLBACK)
        except Exception:
            pass
        sys.exit(0)
