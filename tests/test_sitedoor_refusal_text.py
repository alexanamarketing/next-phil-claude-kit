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
    """No side route: no deploy key, no npx convex, no change to the door's code; a
    refused change goes in a pull request on the website repo that Anthony reviews."""
    t = " ".join(text.lower().split())
    return ("deploy key" in t and "npx convex" in t and "door's code" in t
            and "pull request" in t and "devnextrealestate/next-listing-pages" in t
            and "anthony reviews" in t)


def door_first(text):
    """Try the editor first; only a refusal sends the change to a pull request."""
    t = " ".join(text.lower().split())
    return "first" in t and "refuse" in t and "pull request" in t and "work around" in t


# Requests that must still load the skill, so the answer is "pull request", not a hunt
# through the repo for another way in.
REFUSED_WORDS = ("domain", "email", "gohighlevel", "publish", "unpublish",
                 "tracking pixel", "open house", "listing", "delet")
EDITABLE_WORDS = ("phone", "name", "logo", "partner", "website", "section", "everything")


def names_refused_fields(text):
    t = text.lower()
    return all(w in t for w in REFUSED_WORDS)


SHOWS_UP_PHRASES = ("portfolio page", "listing pages", "top 24", "no photo, no card", "draft",
                    "publish", "/preview/", "five minutes")


def main():
    skill = read(SKILL)
    m = re.search(r"^description:\s*(.+)$", skill, re.M)
    desc = m.group(1) if m else ""
    check(names_refused_fields(desc), "skill description names domain, email, GoHighLevel, "
          "publishing, tracking pixels, open houses, listings and deleting")
    check(all(w in desc.lower() for w in EDITABLE_WORDS),
          "skill description says it edits everything, phone, names, logos, partner, website and sections included")
    check("pull request" in desc.lower(), "skill description says a refused change becomes a pull request")

    block = block_body()
    check(names_refused_fields(block), "CLAUDE.md block names the refused fields")
    check(closes_side_routes(block), "CLAUDE.md block sends refused changes to a pull request Anthony reviews and closes the side routes")
    check(door_first(block), "CLAUDE.md block says try the editor first and open a pull request only when it refuses")
    check("phone numbers," not in block.split("not done this way")[0] if "not done this way" in block else True,
          "CLAUDE.md block no longer lists phone numbers as refused")
    check(block in read(KIT_MD), "kit claude/CLAUDE.md carries the current block byte for byte")

    body = skill.split("---", 2)[-1]
    when = body.split("## The order every time", 1)[0]
    check(closes_side_routes(when), "skill body's refusal list closes the side routes")
    check(door_first(when), "skill body says try the door first; if it refuses, open a pull request instead of working around it")
    refused_part = " ".join(when.lower().split())
    check("cannot change domains, phone numbers" not in refused_part, "skill body no longer refuses phone numbers")

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
    check("display_short_name" in low and "texts leads" in low,
          "When it shows up lists display_short_name as the name in the texts leads receive (G16)")
    flat = " ".join(low.split())
    check("first three)" not in flat and "shows first" in flat,
          "When it shows up says a new testimonial shows first on the listing pages (G17)")
    fields = body.split("Set fields on the agent's record", 1)[-1].split("Add a testimonial", 1)[0].lower()
    check("texts leads" in fields and "plain name" in fields,
          "realtor_set field list says display_short_name is the name in lead texts, a plain name only (G16)")

    token = body.split("## The token", 1)[-1].split("## When the door says no", 1)[0].lower()
    check("unauthorized" in token and "ask anthony for a new token" in token
          and "never paste" in token and "conversation" in token,
          "skill says what to do when the token is not accepted (ask Anthony, Terminal only, never paste into the conversation)")

    sp = skill.lower()
    check("stale_plan" in sp and "payload file changed" in sp,
          "skill says stale_plan also means the payload file changed since the plan")

    if FAILS:
        print("%d failed" % len(FAILS))
        sys.exit(1)
    print("all passed")


if __name__ == "__main__":
    main()
