#!/usr/bin/env python3
"""sitedoor refusal text test: a request for a field the door does not take must
still reach the sitedoor rules, and those rules must close the side routes.

In a rehearsal, "change anthony-test's main domain and GHL location id" never
loaded the skill (its description named only the fields it CAN change), so the
answer came from reading the repo and ended by offering the deploy key "if you
say so explicitly". These checks pin the text that prevents that:

- the skill description names the fields it refuses (domain, phone, email,
  GoHighLevel), so a request about them loads the skill;
- the managed CLAUDE.md block (script and the kit's own CLAUDE.md copy) says
  those fields are not changed this way, that Anthony handles them, and not to
  offer a deploy key, `npx convex` or a change to the door's code instead;
- the skill body says the same next to its refusal list.

Run: python3 tests/test_sitedoor_refusal_text.py   (exit 0 = pass)
"""
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(REPO, "claude", "skills", "sitedoor", "SKILL.md")
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


def block_body():
    ns = {"__name__": "claude_md_block_under_test"}
    src = read(SCRIPT)
    exec(compile(src, SCRIPT, "exec"), ns)
    return ns["BLOCK"]


def closes_side_routes(text):
    t = text.lower()
    return ("deploy key" in t and "npx convex" in t and "door's code" in t
            and "anthony handles" in t)


REFUSED_WORDS = ("domain", "phone", "email", "gohighlevel", "publish", "unpublish",
                 "tracking pixel", "open house", "listing", "delet")


def names_refused_fields(text):
    t = text.lower()
    return all(w in t for w in REFUSED_WORDS)


SHOWS_UP_PHRASES = ("portfolio page", "listing pages", "top 24", "no photo, no card", "draft",
                    "publish", "/preview/", "five minutes")


def main():
    skill = read(SKILL)
    m = re.search(r"^description:\s*(.+)$", skill, re.M)
    desc = m.group(1) if m else ""
    check(names_refused_fields(desc), "skill description names domain, phone, email, GoHighLevel, "
          "publishing, tracking pixels, open houses, listings and deleting")

    block = block_body()
    check(names_refused_fields(block), "CLAUDE.md block names the refused fields")
    check(closes_side_routes(block), "CLAUDE.md block says Anthony handles them and closes the side routes")
    check(block in read(KIT_MD), "kit claude/CLAUDE.md carries the current block byte for byte")

    body = skill.split("---", 2)[-1]
    when = body.split("## The order every time", 1)[0]
    check(closes_side_routes(when), "skill body's refusal list closes the side routes")

    shows = body.split("## When it shows up", 1)[-1].split("## The token", 1)[0]
    low = shows.lower()
    check("## When it shows up" in body and all(p in low for p in SHOWS_UP_PHRASES),
          "skill says where each kind of change shows (portfolio page, listing pages, top 24, "
          "no photo no card, draft until Anthony publishes, /preview/)")
    check("within seconds. the agent's portfolio page" not in body.lower()
          and "the homepage shows a change within seconds" not in body.lower(),
          "skill no longer promises every change on the homepage within seconds")
    check("before" in low and "where" in low and "tell the user" in low,
          "skill tells Claude to say where a change will show before applying it")
    check("next publish" in low, "skill says draft text goes live with Anthony's next publish")

    token = body.split("## The token", 1)[-1].split("## When the door says no", 1)[0].lower()
    check("unauthorized" in token and "ask anthony for a new token" in token
          and "never paste" in token and "conversation" in token,
          "skill says what to do when the token is not accepted (ask Anthony, Terminal only, never paste into the conversation)")

    if FAILS:
        print("%d failed" % len(FAILS))
        sys.exit(1)
    print("all passed")


if __name__ == "__main__":
    main()
