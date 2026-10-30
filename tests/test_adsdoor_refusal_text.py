#!/usr/bin/env python3
"""adsdoor refusal text test: a request the ads check does not do must still load
the adsdoor rules, and those rules must close the side routes.

The lesson from the sitedoor rehearsal (2026-10-24): when a skill's description
names only what it CAN do, a request for something else never loads it, and the
answer comes from wherever Claude looks next, ending in an offer of ssh or a deploy
key. These checks pin the text that prevents that:

- the skill description says what it reads and names what it refuses (storing a
  Page id, the text list, restarting the engine, the token), so those requests load
  the skill;
- the skill body and the managed CLAUDE.md block (the script's copy and the kit's
  own CLAUDE.md) say those are Anthony's side, offer to draft the message to him,
  and never offer ssh, a deploy key, `npx convex`, the editor or the Facebook token;
- nothing offers a "Send Meta request" button or an automatic request;
- setup.sh adds the block and uninstall.sh takes it out, and the block script keeps
  both managed blocks without disturbing the other;
- the help list, the architecture doc and the README name the skill.

Run: python3 tests/test_adsdoor_refusal_text.py   (exit 0 = pass)
"""
import os
import re
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(REPO, "claude", "skills", "adsdoor", "SKILL.md")
SCRIPT = os.path.join(REPO, "scripts", "claude-md-block.py")
KIT_MD = os.path.join(REPO, "claude", "CLAUDE.md")

FAILS = []


def check(cond, label):
    print(("ok   " if cond else "FAIL ") + label)
    if not cond:
        FAILS.append(label)


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def flat(text):
    return " ".join(text.lower().split())


def script_ns():
    ns = {"__name__": "claude_md_block_under_test"}
    src = read(SCRIPT)
    exec(compile(src, SCRIPT, "exec"), ns)
    return ns


REFUSED = ("page id", "text list", "restart", "token")
SIDE_ROUTES = ("ssh", "deploy key", "npx convex")
NEGATION = re.compile(r"\b(never|not|no|don't|do not|refus\w*|cannot|can't)\b", re.I)


def names_refusals(text):
    t = flat(text)
    return all(w in t for w in REFUSED) and "anthony" in t and "draft" in t


def side_routes_closed(text):
    """Every side route is named, and only in a sentence that says no to it."""
    t = flat(text)
    if not all(w in t for w in SIDE_ROUTES):
        return False
    for sentence in re.split(r"(?<=[.!?])\s+|\n", text):
        s = sentence.lower()
        if any(w in s for w in SIDE_ROUTES) and not NEGATION.search(s):
            return False
    return True


def run_block(path, action, which):
    r = subprocess.run([sys.executable, SCRIPT, path, action, which], capture_output=True, text=True, timeout=30)
    return r.returncode


def main():
    check(os.path.isfile(SKILL), "adsdoor SKILL.md exists")
    if not os.path.isfile(SKILL):
        print("%d failure(s)" % len(FAILS))
        return 1
    skill = read(SKILL)
    m = re.search(r"^name:\s*(.+)$", skill, re.M)
    check(m is not None and m.group(1).strip() == "adsdoor", "skill name is adsdoor")
    m = re.search(r"^description:\s*(.+)$", skill, re.M)
    desc = m.group(1) if m else ""
    d = flat(desc)
    check("ads connection" in d and "only reads" in d, "description says it checks the ads connection and only reads")
    check(names_refusals(desc), "description names the refused requests and the drafted message to Anthony")
    check("is dana's ads connection working" in d or "ads connection working" in d,
          "description carries the phrase Phil will use")

    body = skill.split("---", 2)[-1]
    no = body.split("## What it says no to", 1)[-1].split("\n## ", 1)[0] if "## What it says no to" in body else ""
    check(bool(no), "skill body has a 'What it says no to' section")
    check(names_refusals(no), "that section names each refused request and offers the drafted message")
    bullets = [ln.strip().lower() for ln in no.splitlines() if ln.strip().startswith("- ")]
    for phrase in ("- storing or fixing a page id on an agent's record",
                   "- adding an agent to the open-house text list, or taking them off it",
                   "- restarting the ads engine"):
        check(any(b.startswith(phrase) for b in bullets), "that section refuses, as its own bullet: %s" % phrase[2:])
    check(side_routes_closed(no), "that section names ssh, a deploy key and npx convex only to rule them out")
    check("sitedoor" in flat(no) and "facebook token" in flat(no),
          "that section rules out the editor and the Facebook token as a way to store a Page id")
    check("That is Anthony's side. I can draft the message to him with what the check found." in body,
          "the store/map/restart refusal is the approved sentence")
    check("I can't share that. The check only reads the status." in body, "the token refusal is the approved sentence")
    check(side_routes_closed(body), "no line of the skill body offers a side route")

    ns = script_ns()
    block = ns.get("ADS_BLOCK", "")
    check(bool(block) and "<!-- kit-block:adsdoor v1 -->" in block, "claude-md-block.py carries the adsdoor block")
    check(names_refusals(block), "the CLAUDE.md block names the refused requests and the drafted message")
    check(side_routes_closed(block), "the CLAUDE.md block closes the side routes")
    check("adsdoor" in block and "keychain" in flat(block), "the block names the skill and the Keychain token")
    check(block and block in read(KIT_MD), "kit claude/CLAUDE.md carries the adsdoor block byte for byte")
    check(ns.get("BLOCK", "") in read(KIT_MD), "kit claude/CLAUDE.md still carries the sitedoor block")

    for label, text in (("skill", skill), ("block", block)):
        t = flat(text)
        check("send meta request" not in t and "request button" not in t,
              "%s offers no Send Meta request button or automatic request" % label)

    # setup and uninstall manage the block
    setup, un = read(os.path.join(REPO, "setup.sh")), read(os.path.join(REPO, "uninstall.sh"))
    check(re.search(r"claude-md-block\.py\"? \"?\$CLAUDE_MD_DEST\"? ensure adsdoor", setup) is not None,
          "setup.sh ensures the adsdoor block")
    check(re.search(r"claude-md-block\.py\"? \"?\$CLAUDE_MD\"? remove adsdoor", un) is not None,
          "uninstall.sh removes the adsdoor block")
    check(re.search(r"^\s+adsdoor$", un, re.M) is not None, "uninstall.sh lists the adsdoor skill")

    # the block script keeps both blocks apart
    tmp = tempfile.mkdtemp(prefix="adsblock-")
    p = os.path.join(tmp, "CLAUDE.md")
    with open(p, "w", encoding="utf-8") as f:
        f.write("# Rules\n")
    rc1 = run_block(p, "ensure", "sitedoor")
    rc2 = run_block(p, "ensure", "adsdoor")
    once = read(p)
    rc3 = run_block(p, "ensure", "sitedoor")
    rc4 = run_block(p, "ensure", "adsdoor")
    check(rc1 == rc2 == rc3 == rc4 == 0 and read(p) == once, "ensuring both blocks twice changes nothing")
    check(once.count("<!-- kit-block:adsdoor v1 -->") == 1 and once.count("<!-- kit-block:sitedoor v2 -->") == 1,
          "one block of each")
    rc5 = run_block(p, "remove", "adsdoor")
    left = read(p)
    check(rc5 == 0 and "kit-block:adsdoor" not in left and ns["BLOCK"] in left,
          "removing the adsdoor block leaves the sitedoor block")
    with open(p, "w", encoding="utf-8") as f:
        f.write("# Rules\n\n<!-- kit-block:adsdoor v1 -->\nold words\n<!-- /kit-block:adsdoor -->\n")
    run_block(p, "ensure", "adsdoor")
    check("old words" not in read(p) and block in read(p), "an adsdoor block with old text is refreshed")
    r = subprocess.run([sys.executable, SCRIPT, p, "ensure", "nosuch"], capture_output=True, text=True, timeout=30)
    check(r.returncode == 2, "an unknown block name is a usage error")

    # where the skill is listed
    check("/adsdoor" in read(os.path.join(REPO, "claude", "skills", "help", "SKILL.md")), "the help list names /adsdoor")
    check("adsdoor" in read(os.path.join(REPO, "docs", "ARCHITECTURE.md")), "ARCHITECTURE.md names adsdoor")
    check("adsdoor" in read(os.path.join(REPO, "README.md")), "README.md names adsdoor")

    print("%d failure(s)" % len(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
