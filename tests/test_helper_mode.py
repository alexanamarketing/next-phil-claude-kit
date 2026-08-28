#!/usr/bin/env python3
"""DONE 4 Helper Mode test: seven deterministic assertions against a temp state file.

State transitions (a-d) run helper-mode.py's subcommands; the directive branch
(e-g) runs it in hook mode (a UserPromptSubmit payload on stdin). Dates are
deterministic: the test writes `started` a fixed number of days before today and
asserts the branch, comparing only to today.

Run: python3 tests/test_helper_mode.py   (exit 0 = pass)
"""
import datetime
import json
import os
import subprocess
import sys
import tempfile

HOOK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "claude", "hooks", "helper-mode.py")


def run(args, stdin=None, state=None):
    env = dict(os.environ)
    if state:
        env["HELPER_MODE_STATE"] = state
    return subprocess.run([sys.executable, HOOK, *args], input=stdin,
                          capture_output=True, text=True, env=env)


def read_state(path):
    with open(path) as f:
        return json.load(f)


def main():
    today = datetime.date.today().isoformat()
    tmp = tempfile.mkdtemp(prefix="helper-test-")
    state = os.path.join(tmp, "helper-mode.json")

    # (a) `on` on an empty state writes {on:true, started:today}
    r = run(["on"], state=state)
    assert r.returncode == 0, f"on failed: {r.stderr}"
    s = read_state(state)
    assert s["on"] is True and s["started"] == today, f"(a) on wrote {s}"
    print("PASS (a): on -> on:true, started:today")

    # (b) `off` sets on=false
    run(["off"], state=state)
    assert read_state(state)["on"] is False, "(b) off did not clear on"
    print("PASS (b): off -> on:false")

    # (d) `window N` sets window_days
    run(["window", "14"], state=state)
    assert read_state(state)["window_days"] == 14, "(d) window N did not set window_days"
    print("PASS (d): window 14 -> window_days:14")

    # (c) `reset` moves started to today (write an old started first)
    with open(state, "w") as f:
        json.dump({"on": True, "started": "2020-01-01", "window_days": 7}, f)
    run(["reset"], state=state)
    assert read_state(state)["started"] == today, "(c) reset did not move started to today"
    print("PASS (c): reset -> started:today")

    # (e) on + started inside window -> AGGRESSIVE
    with open(state, "w") as f:
        started = (datetime.date.today() - datetime.timedelta(days=2)).isoformat()
        json.dump({"on": True, "started": started, "window_days": 7}, f)
    r = run([], stdin='{"prompt": "hi"}', state=state)
    assert r.returncode == 0, f"(e) hook failed: {r.stderr}"
    assert "HELPER MODE" in r.stdout, "(e) no HELPER MODE directive"
    assert "learning week" in r.stdout.lower(), f"(e) expected AGGRESSIVE branch, got: {r.stdout[:200]}"
    print("PASS (e): started 2d ago -> AGGRESSIVE directive")

    # (f) on + started older than window -> GENTLE
    with open(state, "w") as f:
        started = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
        json.dump({"on": True, "started": started, "window_days": 7}, f)
    r = run([], stdin='{"prompt": "hi"}', state=state)
    assert r.returncode == 0, f"(f) hook failed: {r.stderr}"
    assert "HELPER MODE" in r.stdout, "(f) no HELPER MODE directive"
    assert "learning week" not in r.stdout.lower(), f"(f) expected GENTLE branch, got: {r.stdout[:200]}"
    print("PASS (f): started 30d ago -> GENTLE directive")

    # (g) state off emits nothing; absent state emits nothing; both exit 0
    with open(state, "w") as f:
        json.dump({"on": False, "started": today, "window_days": 7}, f)
    r = run([], stdin='{"prompt": "hi"}', state=state)
    assert r.returncode == 0 and r.stdout.strip() == "", f"(g) off should be silent, got: {r.stdout!r}"
    absent = os.path.join(tmp, "does-not-exist.json")
    r = run([], stdin='{"prompt": "hi"}', state=absent)
    assert r.returncode == 0 and r.stdout.strip() == "", f"(g) absent should be silent, got: {r.stdout!r}"
    print("PASS (g): off/absent -> silent, exit 0")

    print("ALL HELPER MODE ASSERTIONS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
