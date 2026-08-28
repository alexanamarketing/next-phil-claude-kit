#!/usr/bin/env python3
"""Status-line test: pipe mock stdin JSON through statusline.py and assert the
one-line output, across every state that matters for a non-technical user.

  (a) helper-mode on   -> line shows the project, "Helper Mode: ON", and /help
  (b) helper-mode off  -> line shows "Helper Mode: OFF"
  (c) no helper file   -> defaults to ON (kit default)
  (d) malformed stdin  -> exits 0 with a safe fallback, no crash
  (e) empty stdin      -> exits 0, project falls back to "home"

Every case must exit 0.

Run: python3 tests/test_statusline.py   (exit 0 = pass)
"""
import json
import os
import subprocess
import sys
import tempfile

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "claude", "statusline.py")


def run(stdin, state=None):
    env = dict(os.environ)
    if state is not None:
        env["HELPER_MODE_STATE"] = state
    else:
        # Point at a guaranteed-absent path so the test never reads a real
        # ~/.claude/helper-mode.json on the build machine.
        env["HELPER_MODE_STATE"] = os.path.join(
            tempfile.gettempdir(), "statusline-test-no-such-file.json")
    return subprocess.run([sys.executable, SCRIPT], input=stdin,
                          capture_output=True, text=True, env=env)


def write_state(path, on):
    with open(path, "w") as f:
        json.dump({"on": on, "started": "2020-01-01", "window_days": 7}, f)


def main():
    tmp = tempfile.mkdtemp(prefix="statusline-test-")
    state = os.path.join(tmp, "helper-mode.json")
    stdin = '{"workspace":{"current_dir":"/tmp/x/my-listings"}}'

    # (a) helper on -> project name + ON + /help
    write_state(state, True)
    r = run(stdin, state=state)
    assert r.returncode == 0, f"(a) exit {r.returncode}: {r.stderr}"
    assert "my-listings" in r.stdout, f"(a) no project name: {r.stdout!r}"
    assert "Helper Mode: ON" in r.stdout, f"(a) not ON: {r.stdout!r}"
    assert "/help" in r.stdout, f"(a) no /help: {r.stdout!r}"
    print("PASS (a): on -> project + Helper Mode: ON + /help")

    # (b) helper off -> OFF
    write_state(state, False)
    r = run(stdin, state=state)
    assert r.returncode == 0, f"(b) exit {r.returncode}: {r.stderr}"
    assert "Helper Mode: OFF" in r.stdout, f"(b) not OFF: {r.stdout!r}"
    assert "my-listings" in r.stdout, f"(b) no project name: {r.stdout!r}"
    print("PASS (b): off -> Helper Mode: OFF")

    # (c) no helper-mode file -> defaults to ON
    absent = os.path.join(tmp, "does-not-exist.json")
    r = run(stdin, state=absent)
    assert r.returncode == 0, f"(c) exit {r.returncode}: {r.stderr}"
    assert "Helper Mode: ON" in r.stdout, f"(c) absent should default ON: {r.stdout!r}"
    print("PASS (c): absent state -> defaults to ON")

    # (d) malformed stdin -> exit 0, safe fallback, no crash
    write_state(state, True)
    r = run("this is not json {{{", state=state)
    assert r.returncode == 0, f"(d) exit {r.returncode}: {r.stderr}"
    assert r.stdout.strip() != "", f"(d) empty output on malformed input: {r.stdout!r}"
    assert "/help" in r.stdout, f"(d) fallback should still mention /help: {r.stdout!r}"
    print("PASS (d): malformed stdin -> exit 0, safe fallback")

    # (e) empty stdin -> exit 0, project falls back to home
    r = run("", state=absent)
    assert r.returncode == 0, f"(e) exit {r.returncode}: {r.stderr}"
    assert "home" in r.stdout, f"(e) empty stdin should fall back to home: {r.stdout!r}"
    print("PASS (e): empty stdin -> exit 0, project 'home'")

    print("ALL STATUS LINE ASSERTIONS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
