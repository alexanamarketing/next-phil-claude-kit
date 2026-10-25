#!/usr/bin/env python3
"""claude-md-block.py test: one managed sitedoor block at the end of a CLAUDE.md.

Cases: an absent file stays absent; ensure appends the block; a second ensure is
byte-identical; a file with no trailing newline; an older block (v0, the v1 that knew only the
editor, or v2 with different text, or a block in the middle) is replaced so exactly one current block
sits at the end; remove takes it back out; a start marker with no end marker is
refused without touching the file; the kit's own claude/CLAUDE.md already carries
the current block, so ensure on a fresh copy is a no-op.

Run: python3 tests/test_claude_md_block.py   (exit 0 = pass)
"""
import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO, "scripts", "claude-md-block.py")
KIT_MD = os.path.join(REPO, "claude", "CLAUDE.md")
START = "<!-- kit-block:sitedoor v2 -->"
END = "<!-- /kit-block:sitedoor -->"

FAILS = []


def check(cond, label):
    print(("ok   " if cond else "FAIL ") + label)
    if not cond:
        FAILS.append(label)


def run(path, action):
    r = subprocess.run([sys.executable, SCRIPT, path, action], capture_output=True, text=True, timeout=30)
    return r.returncode, r.stdout + r.stderr


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def write(p, s):
    with open(p, "w", encoding="utf-8") as f:
        f.write(s)


def main():
    check(os.path.isfile(SCRIPT), "claude-md-block.py exists")
    if not os.path.isfile(SCRIPT):
        return 1
    d = tempfile.mkdtemp(prefix="mdblock-")
    p = os.path.join(d, "CLAUDE.md")

    # absent file: nothing created
    rc, out = run(p, "ensure")
    check(rc == 0 and not os.path.exists(p), "ensure on an absent file creates nothing")
    rc, out = run(p, "remove")
    check(rc == 0 and not os.path.exists(p), "remove on an absent file creates nothing")

    # ensure appends at the end
    orig = "# My rules\n\n- be kind\n"
    write(p, orig)
    rc, out = run(p, "ensure")
    s = read(p)
    check(rc == 0 and s.startswith(orig), "ensure keeps the existing text first")
    check(s.count(START) == 1 and s.rstrip("\n").endswith(END) and s.endswith("\n"),
          "ensure appends exactly one block at the end")
    check("sitedoor" in s and "npx convex" in s and "Keychain" in s, "block names the skill, the Keychain and npx convex")
    lines = s[s.index(START):].splitlines()
    check(3 <= len(lines) - 2 <= 6, "block body is a few lines")

    # idempotent
    rc, out = run(p, "ensure")
    check(rc == 0 and read(p) == s, "second ensure changes nothing")

    # remove restores the original bytes
    rc, out = run(p, "remove")
    check(rc == 0 and read(p) == orig, "remove restores the original file")
    rc, out = run(p, "remove")
    check(rc == 0 and read(p) == orig, "remove with no block changes nothing")

    # no trailing newline
    write(p, "# Rules\n- one")
    rc, out = run(p, "ensure")
    s = read(p)
    check(rc == 0 and s.startswith("# Rules\n- one\n") and s.count(START) == 1 and s.endswith(END + "\n"),
          "a file with no trailing newline gets the block on its own lines")
    rc, out = run(p, "remove")
    check(rc == 0 and read(p).rstrip("\n") == "# Rules\n- one", "remove after a no-newline ensure keeps the text")

    # an older v0 block is replaced
    write(p, "# Rules\n\n<!-- kit-block:sitedoor v0 -->\nold text\n<!-- /kit-block:sitedoor -->\n")
    rc, out = run(p, "ensure")
    s = read(p)
    check(rc == 0 and "old text" not in s and "v0" not in s and s.count(START) == 1, "an older v0 block is replaced")
    check(s.count("kit-block:sitedoor v") == 1 and s.count(END) == 1, "exactly one block after replacing")

    # the v1 block (editor only, no design work) on an installed CLAUDE.md becomes v2
    write(p, "# Rules\n\n<!-- kit-block:sitedoor v1 -->\n## Agent records on the website\n\n- old v1 text\n"
          + END + "\n")
    rc, out = run(p, "ensure")
    s = read(p)
    check(rc == 0 and "old v1 text" not in s and "sitedoor v1" not in s and s.count(START) == 1
          and "site-checkout.sh" in s, "an installed v1 block is replaced by the v2 block")

    # a current-version block with different text is replaced
    write(p, "# Rules\n\n" + START + "\nstale wording\n" + END + "\n")
    rc, out = run(p, "ensure")
    s = read(p)
    check(rc == 0 and "stale wording" not in s and s.count(START) == 1, "a v2 block with different text is refreshed")

    # a block in the middle moves to the end, the text after it stays
    write(p, "# Rules\n\n" + START + "\nmid\n" + END + "\n\n## Later section\n- keep me\n")
    rc, out = run(p, "ensure")
    s = read(p)
    check(rc == 0 and "## Later section\n- keep me\n" in s and s.rstrip("\n").endswith(END)
          and s.count(START) == 1 and "mid\n" not in s, "a block in the middle moves to the end")

    # two blocks collapse to one
    write(p, "# R\n" + START + "\na\n" + END + "\n" + START + "\nb\n" + END + "\n")
    rc, out = run(p, "ensure")
    s = read(p)
    check(rc == 0 and s.count(START) == 1 and s.count(END) == 1, "duplicate blocks collapse to one")

    # broken markers: refuse, file untouched
    broken = "# R\n" + START + "\nno end marker\n"
    write(p, broken)
    rc, out = run(p, "ensure")
    check(rc != 0 and read(p) == broken, "a start marker with no end marker is refused, file untouched")
    rc, out = run(p, "remove")
    check(rc != 0 and read(p) == broken, "remove also refuses broken markers")

    # lines outside the block are never touched, blank-line runs included (review K11)
    fenced = "# Rules\n\n```\nline one\n\n\n\nline two\n```\n\n\n\n## After\n- x\n"
    write(p, fenced)
    rc1, _ = run(p, "ensure")
    rc2, _ = run(p, "ensure")
    rc3, _ = run(p, "remove")
    check(rc1 == rc2 == rc3 == 0 and read(p) == fenced, "ensure, ensure, remove leaves a fenced blank-line run intact")
    write(p, "# A\n\n\n\n" + START + "\nold\n" + END + "\n\n## B\n```\nx\n\n\n\ny\n```\n")
    rc, _ = run(p, "ensure")
    s = read(p)
    check(rc == 0 and "```\nx\n\n\n\ny\n```\n" in s and s.count(START) == 1, "a block move keeps distant blank lines")

    # usage
    rc, out = run(p, "bogus")
    check(rc == 2, "an unknown action is a usage error")

    # the kit's own CLAUDE.md carries the current block already
    k = os.path.join(d, "kit.md")
    shutil.copy(KIT_MD, k)
    before = read(k)
    check(before.count(START) == 1, "kit claude/CLAUDE.md carries the block")
    rc, out = run(k, "ensure")
    check(rc == 0 and read(k) == before, "ensure on a fresh kit CLAUDE.md is a no-op")

    shutil.rmtree(d, ignore_errors=True)
    print("%d failure(s)" % len(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
