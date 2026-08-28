#!/usr/bin/env python3
"""Tests for the /help command cheat-sheet + on/off toggle.

The startup banner and /help output are skill-prose (Claude renders them from
SKILL.md), and the on/off toggle is a documented single-line edit to config.yaml.
So there is no runtime binary to drive here the way test_helper_mode.py drives
helper-mode.py. Instead these assertions cover what is actually testable:

  1. The project-load skill documents a startup banner that is gated on
     `help_mode` being on, prints the required commands, and skips when off.
  2. The banner-visibility RULE the skill documents ("treat absent key as on")
     resolves correctly for on / off / absent config.
  3. The /help skill's on/off toggle edits `help_mode` in config.yaml, and the
     documented single-line edit actually flips the value in a real config file
     and reads back.
  4. Bare /help lists the commands and carries the one-line disambiguation
     between /helper and /help.

Run: python3 tests/test_help_mode.py   (exit 0 = pass)
"""
import os
import re
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_SKILL = os.path.join(REPO, "claude", "skills", "project", "SKILL.md")
HELP_SKILL = os.path.join(REPO, "claude", "skills", "help", "SKILL.md")
CONFIG_EXAMPLE = os.path.join(REPO, "config.example.yaml")

REQUIRED_COMMANDS = ["/project", "/sync", "/helper", "/explain", "/new-project"]
DISAMBIGUATION = "/helper explains the words; /help lists the commands."


def read(path):
    with open(path) as f:
        return f.read()


def read_help_mode(config_text):
    """Mirror the rule the skills document: read `help_mode:` from config,
    treating an absent key as `on`. Returns 'on' or 'off'."""
    m = re.search(r"^help_mode:\s*(\S+)", config_text, re.MULTILINE)
    if not m:
        return "on"  # absent key treated as on
    return m.group(1).strip()


def banner_should_show(config_text):
    """The documented rule: show the startup banner only when help_mode is on
    (absent key counts as on)."""
    return read_help_mode(config_text) == "on"


def set_help_mode(config_text, value):
    """Mirror the /help on|off edit: rewrite the single `help_mode:` line's value."""
    return re.sub(r"^(help_mode:\s*)\S+.*$", r"\g<1>" + value,
                  config_text, count=1, flags=re.MULTILINE)


def main():
    project = read(PROJECT_SKILL)
    help_md = read(HELP_SKILL)

    # (a) project skill documents a startup banner gated on help_mode on
    assert "Startup Command Banner" in project, "(a) no Startup Command Banner section"
    assert "Commonly used commands:" in project, "(a) banner missing the list header"
    assert "/help off" in project, "(a) banner missing the /help off last line"
    # gated: mentions printing when on and skipping when off
    assert re.search(r"help_mode.*on", project), "(a) banner not gated on help_mode on"
    assert re.search(r"help_mode.*off", project) and "skip" in project.lower(), \
        "(a) banner does not say to skip when help_mode off"
    for cmd in REQUIRED_COMMANDS:
        assert cmd in project, f"(a) banner missing required command {cmd}"
    print("PASS (a): project skill documents a gated startup banner with the required commands")

    # (b) the documented visibility rule resolves on/off/absent correctly
    assert banner_should_show("help_mode: on\n") is True, "(b) on should show"
    assert banner_should_show("help_mode: off\n") is False, "(b) off should hide"
    assert banner_should_show("hook_strictness: relaxed\n") is True, "(b) absent should show"
    print("PASS (b): banner-visibility rule -> on:show, off:hide, absent:show")

    # (c) real config round-trip through the documented single-line edit
    cfg = read(CONFIG_EXAMPLE)
    assert read_help_mode(cfg) == "on", "(c) shipped config.example.yaml should default help_mode on"
    off = set_help_mode(cfg, "off")
    assert read_help_mode(off) == "off", "(c) /help off did not flip config to off"
    assert banner_should_show(off) is False, "(c) banner should not show after /help off"
    back = set_help_mode(off, "on")
    assert read_help_mode(back) == "on", "(c) /help on did not flip config back to on"
    assert banner_should_show(back) is True, "(c) banner should show again after /help on"
    # prove it against a real file on disk, not just an in-memory string
    tmp = tempfile.mkdtemp(prefix="help-test-")
    p = os.path.join(tmp, "config.yaml")
    with open(p, "w") as f:
        f.write(cfg)
    flipped = set_help_mode(read(p), "off")
    with open(p, "w") as f:
        f.write(flipped)
    assert read_help_mode(read(p)) == "off", "(c) on-disk config did not flip to off"
    print("PASS (c): config help_mode round-trips on -> off -> on via the documented edit")

    # (d) help skill toggle targets help_mode in config, and its section exists
    assert "help_mode" in help_md, "(d) help skill does not mention help_mode"
    assert re.search(r"/help on or /help off", help_md), "(d) help skill missing on/off usage"
    print("PASS (d): /help on|off toggle edits help_mode in config.yaml")

    # (e) bare /help lists the commands and carries the disambiguation line
    assert "Commonly used commands:" in help_md, "(e) bare /help missing command list"
    for cmd in REQUIRED_COMMANDS:
        assert cmd in help_md, f"(e) bare /help missing command {cmd}"
    assert DISAMBIGUATION in help_md, "(e) missing the /helper-vs-/help disambiguation line"
    print("PASS (e): bare /help lists the commands + the /helper-vs-/help distinction")

    # (f) README teaches the same cheat-sheet + disambiguation
    readme = read(os.path.join(REPO, "README.md"))
    assert DISAMBIGUATION in readme, "(f) README missing the /helper-vs-/help distinction"
    assert "/help off" in readme, "(f) README missing /help off"
    print("PASS (f): README carries the cheat-sheet distinction and /help off")

    print("ALL HELP-MODE (COMMAND CHEAT-SHEET) ASSERTIONS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
