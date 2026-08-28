#!/usr/bin/env python3
"""Status-line test: pipe mock stdin JSON through statusline.py and assert the
one-line output, across every state that matters for a non-technical user.

  (a) helper-mode on   -> line shows the project, "Helper Mode: ON", and /help
  (b) helper-mode off  -> line shows "Helper Mode: OFF"
  (c) no helper file   -> defaults to ON (kit default)
  (d) malformed stdin  -> exits 0 with a safe fallback, no crash
  (e) empty stdin      -> exits 0, project falls back to "home"
  (f) technical mode   -> developer bar: model + cost + git 'main +1' + ctx +
                          lines changed, and NO "Helper Mode" (different bar)
  (g) /statusline toggle round-trips status_detail simple <-> technical through
      the documented config path (and the insert-when-absent branch)
  (h) technical mode + malformed/empty stdin -> exits 0 with a safe fallback

Every case must exit 0.

Run: python3 tests/test_statusline.py   (exit 0 = pass)
"""
import json
import os
import re
import subprocess
import sys
import tempfile

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "claude", "statusline.py")


def run(stdin, state=None, config=None):
    env = dict(os.environ)
    if state is not None:
        env["HELPER_MODE_STATE"] = state
    else:
        # Point at a guaranteed-absent path so the test never reads a real
        # ~/.claude/helper-mode.json on the build machine.
        env["HELPER_MODE_STATE"] = os.path.join(
            tempfile.gettempdir(), "statusline-test-no-such-file.json")
    if config is not None:
        env["STATUSLINE_CONFIG"] = config
    else:
        # Absent config -> the script defaults to simple. Point at a
        # guaranteed-absent path so a real vault config.yaml on the build
        # machine can never flip these simple-mode cases to technical.
        env["STATUSLINE_CONFIG"] = os.path.join(
            tempfile.gettempdir(), "statusline-test-no-such-config.yaml")
    return subprocess.run([sys.executable, SCRIPT], input=stdin,
                          capture_output=True, text=True, env=env)


def write_state(path, on):
    with open(path, "w") as f:
        json.dump({"on": on, "started": "2020-01-01", "window_days": 7}, f)


def write_config(path, value):
    """Write a minimal config.yaml carrying a `status_detail` line."""
    with open(path, "w") as f:
        f.write("help_mode: on\nstatus_detail: %s\n" % value)


def set_status_detail(config_text, value):
    """Mirror the /statusline documented edit: rewrite the single
    `status_detail:` line's value, or insert it after `help_mode` when absent."""
    if re.search(r"^status_detail:", config_text, re.MULTILINE):
        return re.sub(r"^(status_detail:\s*)\S+.*$", r"\g<1>" + value,
                      config_text, count=1, flags=re.MULTILINE)
    return re.sub(r"^(help_mode:.*)$", r"\1\nstatus_detail: " + value,
                  config_text, count=1, flags=re.MULTILINE)


def read_status_detail(config_text):
    """Mirror the read rule: absent key -> 'simple'."""
    m = re.search(r"^status_detail:\s*(\S+)", config_text, re.MULTILINE)
    return m.group(1).strip() if m else "simple"


def make_git_repo(parent, dirty_files=1):
    """Create a real git repo on branch `main` with `dirty_files` untracked
    files. Returns the repo path."""
    repo = os.path.join(parent, "listings-repo")
    os.makedirs(repo)
    genv = dict(os.environ)
    genv.update({
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
    })

    def git(*args):
        subprocess.run(["git", "-C", repo, *args], env=genv,
                       capture_output=True, text=True, check=True)

    subprocess.run(["git", "-C", repo, "init"], env=genv,
                   capture_output=True, text=True, check=True)
    with open(os.path.join(repo, "seed.txt"), "w") as f:
        f.write("seed\n")
    git("add", "seed.txt")
    git("commit", "-m", "init")
    git("branch", "-M", "main")
    for i in range(dirty_files):
        with open(os.path.join(repo, "dirty%d.txt" % i), "w") as f:
            f.write("x\n")
    return repo


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

    # (f) technical mode -> developer bar with model + cost + branch +1, no Helper Mode
    cfg = os.path.join(tmp, "config.yaml")
    write_config(cfg, "technical")
    repo = make_git_repo(tmp, dirty_files=1)
    tech_stdin = json.dumps({
        "workspace": {"current_dir": repo},
        "model": {"display_name": "Sonnet 4.6", "id": "claude-sonnet-4-6"},
        "cost": {"total_cost_usd": 0.34, "total_lines_added": 120,
                 "total_lines_removed": 14},
        "context_window": {"used_percentage": 34},
    })
    r = run(tech_stdin, state=absent, config=cfg)
    assert r.returncode == 0, f"(f) exit {r.returncode}: {r.stderr}"
    assert "Sonnet 4.6" in r.stdout, f"(f) no model name: {r.stdout!r}"
    assert "$0.34" in r.stdout, f"(f) no cost: {r.stdout!r}"
    assert "main +1" in r.stdout, f"(f) no branch + dirty count: {r.stdout!r}"
    assert "ctx 34%" in r.stdout, f"(f) no context usage: {r.stdout!r}"
    assert "+120/-14" in r.stdout, f"(f) no lines changed: {r.stdout!r}"
    assert "Helper Mode" not in r.stdout, f"(f) technical bar leaked simple bar: {r.stdout!r}"
    assert "None" not in r.stdout and "null" not in r.stdout, \
        f"(f) technical bar printed a None/null: {r.stdout!r}"
    print("PASS (f): technical -> model + cost + 'main +1' + ctx + lines, no Helper Mode")

    # (g) /statusline toggle round-trips status_detail through the config path
    #     the skill documents (technical <-> simple), on a real file on disk.
    toggle = os.path.join(tmp, "toggle.yaml")
    write_config(toggle, "simple")
    with open(toggle) as fh:
        base = fh.read()
    assert read_status_detail(base) == "simple", "(g) seed should be simple"
    with open(toggle, "w") as fh:
        fh.write(set_status_detail(base, "technical"))
    with open(toggle) as fh:
        after_tech = fh.read()
    assert read_status_detail(after_tech) == "technical", "(g) did not flip to technical"
    # and the script reads that flip as technical
    r = run(tech_stdin, state=absent, config=toggle)
    assert "Helper Mode" not in r.stdout, f"(g) config technical still showed simple: {r.stdout!r}"
    with open(toggle, "w") as fh:
        fh.write(set_status_detail(after_tech, "simple"))
    with open(toggle) as fh:
        after_simple = fh.read()
    assert read_status_detail(after_simple) == "simple", "(g) did not flip back to simple"
    # insert-when-absent branch the skill documents
    inserted = set_status_detail("help_mode: on\n", "technical")
    assert read_status_detail(inserted) == "technical", "(g) absent-key insert failed"
    print("PASS (g): /statusline config edit round-trips simple <-> technical (+insert)")

    # (h) technical mode with malformed / empty stdin -> exit 0, safe fallback
    r = run("this is not json {{{", state=absent, config=cfg)
    assert r.returncode == 0, f"(h) malformed exit {r.returncode}: {r.stderr}"
    assert r.stdout.strip() != "", f"(h) empty output on malformed input: {r.stdout!r}"
    assert "None" not in r.stdout and "null" not in r.stdout, \
        f"(h) fallback printed None/null: {r.stdout!r}"
    r = run("", state=absent, config=cfg)
    assert r.returncode == 0, f"(h) empty exit {r.returncode}: {r.stderr}"
    assert r.stdout.strip() != "", f"(h) empty output on empty input: {r.stdout!r}"
    print("PASS (h): technical mode, malformed/empty stdin -> exit 0, safe fallback")

    print("ALL STATUS LINE ASSERTIONS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
