#!/usr/bin/env python3
"""Status line for Claude Code: the quiet bar at the bottom of the screen.

Claude Code runs this once every refresh and pipes it a JSON object on stdin.
This script prints ONE short line to stdout and always exits 0. It never crashes
the bar: any parse or read failure prints a safe minimal fallback and exits 0.

There are two modes, chosen by `status_detail` in <vault_root>/config.yaml
(set with /statusline; absent means simple):

  simple (default) — tuned for a non-technical real-estate agent, three things
  and no cost/token/model/git noise:

    📁 {project}   •   Helper Mode: {ON|OFF}   •   type /help for commands

    - {project}: the folder you are working in (the basename of the current
      dir), or "home" when you are sitting at the vault root or your home folder.
    - Helper Mode: ON/OFF, read from ~/.claude/helper-mode.json. Absent or
      unreadable is treated as ON, matching the kit default.

  technical — a developer bar built from the stdin fields: context usage,
  model name, session cost, and (if the current dir is a git repo) branch +
  dirty-file count, plus lines changed when present:

    ctx 34%  •  Sonnet 4.6  •  $0.12  •  main +3  •  +120/-14

  Any field that is absent is skipped (never "None"/"null"); a missing or
  non-repo git dir just drops the git segment.

No hardcoded paths, Mac-safe. Override the helper state file with
HELPER_MODE_STATE and the config file with STATUSLINE_CONFIG (used by tests).
"""
import json
import os
import re
import subprocess
import sys

# A light grey so the bar stays quiet. Claude Code allows ANSI colour escapes.
DIM = "\033[2m"
CYAN = "\033[36m"
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


def _config_path():
    """Locate config.yaml: STATUSLINE_CONFIG env override, else
    <vault_root>/config.yaml. Returns None when vault_root is unknown."""
    override = os.environ.get("STATUSLINE_CONFIG")
    if override:
        return override
    vault = _vault_root()
    if vault:
        return os.path.join(vault, "config.yaml")
    return None


def _status_detail():
    """Read `status_detail` from config.yaml. Absent/unreadable/anything other
    than 'technical' -> 'simple' (the kit default)."""
    path = _config_path()
    if not path:
        return "simple"
    try:
        with open(path) as f:
            text = f.read()
        m = re.search(r"^status_detail:\s*(\S+)", text, re.MULTILINE)
        if m and m.group(1).strip().lower() == "technical":
            return "technical"
    except Exception:
        pass
    return "simple"


def _git_segment(current):
    """Return 'branch +N' (N = dirty file count, dropped when 0) when `current`
    is inside a git work tree, else ''. Never raises."""
    try:
        real = os.path.realpath(os.path.expanduser(current))
        if not os.path.isdir(real):
            return ""
        branch = subprocess.run(
            ["git", "-C", real, "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=2)
        if branch.returncode != 0:
            return ""
        name = branch.stdout.strip()
        if not name:
            return ""
        status = subprocess.run(
            ["git", "-C", real, "status", "--porcelain"],
            capture_output=True, text=True, timeout=2)
        dirty = 0
        if status.returncode == 0:
            dirty = len([ln for ln in status.stdout.splitlines() if ln.strip()])
        return f"{name} +{dirty}" if dirty else name
    except Exception:
        return ""


def _technical_line(data):
    """Build the developer bar from the stdin fields. Every segment is optional;
    absent fields are skipped so the bar never prints 'None' or 'null'."""
    parts = []

    # context usage percent
    ctx = (data.get("context_window") or {}).get("used_percentage")
    if isinstance(ctx, (int, float)):
        parts.append(f"ctx {int(round(ctx))}%")

    # model display name (fallback to id)
    model = data.get("model") or {}
    name = model.get("display_name") or model.get("id")
    if isinstance(name, str) and name.strip():
        parts.append(name.strip())

    # session cost
    cost = (data.get("cost") or {}).get("total_cost_usd")
    if isinstance(cost, (int, float)):
        parts.append(f"${cost:.2f}")

    # git branch + dirty-file count
    workspace = data.get("workspace") or {}
    current = workspace.get("current_dir") or data.get("cwd") or ""
    if isinstance(current, str) and current:
        git = _git_segment(current)
        if git:
            parts.append(git)

    # lines changed this session
    cost_obj = data.get("cost") or {}
    added = cost_obj.get("total_lines_added")
    removed = cost_obj.get("total_lines_removed")
    if isinstance(added, int) and isinstance(removed, int) and (added or removed):
        parts.append(f"+{added}/-{removed}")

    if not parts:
        # nothing usable in the payload: keep the bar non-empty and safe
        return f"{DIM}{FALLBACK}{RESET}"
    return f"{CYAN}" + "   •   ".join(parts) + RESET


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

    if _status_detail() == "technical":
        print(_technical_line(data))
        return 0

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
