#!/usr/bin/env python3
"""Helper Mode: make Claude explain technical terms in plain English for a
non-technical user, harder during a learning window than after it.

Two jobs in one file:

1. HOOK MODE (no subcommand): a UserPromptSubmit hook. On every turn it reads the
   state file. If Helper Mode is OFF or the state is absent, it prints nothing and
   exits 0. If ON, it injects one behavioral directive so the assistant explains
   dev jargon in ordinary words. Inside the learning window (started no more than
   `window_days` ago) it injects the AGGRESSIVE directive (re-explain every term
   every time it appears, because the reader is still learning the vocabulary);
   after the window, the GENTLE directive (explain each term on first use per
   conversation). Re-injecting every turn is deliberate: it survives context
   compaction and never drifts.

2. COMMAND MODE (a subcommand): the /helper skill calls these to toggle state.
     helper-mode.py on            set on, stamp `started` today if unset
     helper-mode.py off           set on=false
     helper-mode.py reset         restart the learning window from today (on=true)
     helper-mode.py window N       set window_days
     helper-mode.py status        print current state in plain English

State file: ~/.claude/helper-mode.json  ({on, started:YYYY-MM-DD, window_days}).
Override with HELPER_MODE_STATE (tests). "Today" may be overridden with
HELPER_MODE_TODAY=YYYY-MM-DD for fully deterministic tests; live runs use the
system date only. No hardcoded paths, Mac-safe.
"""
import datetime
import json
import os
import sys

DEFAULT_WINDOW_DAYS = 7

AGGRESSIVE = (
    "HELPER MODE (learning week). The reader is a real-estate agent, not a "
    "developer, and is still learning the words. Lead every answer with the "
    "plain-English point in one sentence. EVERY time you use any technical or dev "
    "term (repo, commit, branch, deploy, API, hook, skill, JSON, YAML, CLI, "
    "terminal, environment variable, token, endpoint, cache, and the like), explain "
    "it in ordinary words right there, every time it appears, not only the first. "
    "Describe what a thing DOES, never just its name. No assumed background, no "
    "unexplained acronyms. Short and concrete, never condescending."
)

GENTLE = (
    "HELPER MODE (plain-English floor). The reader is a real-estate agent, not a "
    "developer. Lead every answer with the plain-English point in one sentence. The "
    "first time you use any technical or dev term (repo, commit, branch, deploy, "
    "API, hook, skill, JSON, YAML, CLI, terminal, environment variable, token, "
    "endpoint, cache, and the like) in a conversation, explain it in ordinary words "
    "right there. Describe what a thing DOES, never just its name. No assumed "
    "background, no unexplained acronyms. Short and concrete, never condescending."
)


def state_path():
    return os.environ.get("HELPER_MODE_STATE") or os.path.expanduser("~/.claude/helper-mode.json")


def today():
    override = os.environ.get("HELPER_MODE_TODAY")
    if override:
        try:
            return datetime.date.fromisoformat(override)
        except ValueError:
            pass
    return datetime.date.today()


def load_state():
    try:
        with open(state_path()) as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except (OSError, ValueError):
        pass
    return None


def save_state(state):
    path = state_path()
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w") as f:
        json.dump(state, f, indent=2)
        f.write("\n")


def _window_days(state):
    wd = state.get("window_days")
    return wd if isinstance(wd, int) and wd >= 0 else DEFAULT_WINDOW_DAYS


# ---------------------------------------------------------------- command mode
def cmd_on():
    state = load_state() or {}
    state["on"] = True
    if not state.get("started"):
        state["started"] = today().isoformat()
    state.setdefault("window_days", DEFAULT_WINDOW_DAYS)
    save_state(state)
    print(f"Helper Mode ON (learning week: {_window_days(state)} days from {state['started']}).")


def cmd_off():
    state = load_state() or {}
    state["on"] = False
    state.setdefault("window_days", DEFAULT_WINDOW_DAYS)
    save_state(state)
    print("Helper Mode OFF. Answers go back to normal.")


def cmd_reset():
    state = load_state() or {}
    state["on"] = True
    state["started"] = today().isoformat()
    state.setdefault("window_days", DEFAULT_WINDOW_DAYS)
    save_state(state)
    print(f"Helper Mode learning week restarted today ({state['started']}).")


def cmd_window(n):
    try:
        n = int(n)
        if n < 0:
            raise ValueError
    except (TypeError, ValueError):
        sys.stderr.write("usage: helper-mode.py window N   (N is a whole number of days)\n")
        return 2
    state = load_state() or {}
    state["window_days"] = n
    state.setdefault("on", True)
    if not state.get("started"):
        state["started"] = today().isoformat()
    save_state(state)
    print(f"Helper Mode learning week set to {n} days.")
    return 0


def cmd_status():
    state = load_state()
    if not state or not state.get("on"):
        print("Helper Mode is OFF. Turn it on with: /helper on")
        return 0
    started = state.get("started")
    wd = _window_days(state)
    try:
        elapsed = (today() - datetime.date.fromisoformat(started)).days
    except (TypeError, ValueError):
        elapsed = None
    if elapsed is None:
        print(f"Helper Mode is ON (learning week: {wd} days).")
        return 0
    left = wd - elapsed
    if left >= 0:
        print(f"Helper Mode is ON, in the learning week: day {elapsed} of {wd}, "
              f"{left} day(s) left. Claude re-explains every technical term while you learn.")
    else:
        print(f"Helper Mode is ON, past the learning week ({elapsed} days in). "
              f"Claude explains each technical term the first time it comes up.")
    return 0


# ------------------------------------------------------------------- hook mode
def hook_mode():
    """UserPromptSubmit: read state, inject the right directive (or nothing)."""
    try:
        sys.stdin.read()  # drain the payload; we do not need its content
    except Exception:
        pass
    state = load_state()
    if not state or not state.get("on"):
        return 0
    started = state.get("started")
    wd = _window_days(state)
    try:
        elapsed = (today() - datetime.date.fromisoformat(started)).days
    except (TypeError, ValueError):
        elapsed = 0  # malformed start date: default to the aggressive floor
    directive = AGGRESSIVE if elapsed <= wd else GENTLE
    out = {"hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": directive,
    }}
    print(json.dumps(out))
    return 0


def main(argv):
    if len(argv) >= 1:
        cmd = argv[0]
        if cmd == "on":
            cmd_on(); return 0
        if cmd == "off":
            cmd_off(); return 0
        if cmd == "reset":
            cmd_reset(); return 0
        if cmd == "window":
            return cmd_window(argv[1] if len(argv) > 1 else None)
        if cmd == "status":
            return cmd_status()
        sys.stderr.write(f"helper-mode: unknown command {cmd!r}\n")
        return 2
    return hook_mode()


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception:
        # Never break a turn on a hook error.
        sys.exit(0)
