#!/usr/bin/env python3
"""claude-md-block.py: keep one managed sitedoor block at the end of a CLAUDE.md.

Usage:
  python3 scripts/claude-md-block.py <file> ensure   add or refresh the block (idempotent)
  python3 scripts/claude-md-block.py <file> remove   take the block out

ensure: when the file is absent, nothing is created (setup.sh copies the kit's
CLAUDE.md, which already carries the block). Otherwise every existing sitedoor
block (any version, anywhere in the file) is removed and the current block is
appended at the end on its own lines. A second run changes nothing.
remove: takes every sitedoor block out. Only the blank lines right next to a block
change; every other line of the file is left exactly as it was.
A start marker without its end marker is refused (exit 1) and the file is left alone.
Exit codes: 0 ok, 1 refused, 2 usage.
"""
import os
import re
import sys

START = "<!-- kit-block:sitedoor v1 -->"
END = "<!-- /kit-block:sitedoor -->"
BODY = (
    "## Agent records on the website\n"
    "\n"
    "- A change to an agent's record on the website database (bio, title, testimonials, past sales, service areas, social links, license number, office address, headshot, and the homepage draft's SEO and hero text) goes through the `sitedoor` skill, using your own editor token from the Keychain.\n"
    "- It shows the change first and writes only after you say yes. Every change is logged in the MLS log and can be undone.\n"
    "- Before applying a change, say where it will show: record fields on the agent's portfolio page in about five minutes, a new testimonial first on that agent's listing pages, a past sale on the homepage only with a photo and in the top 24 by price, and homepage SEO and hero text in the draft only, live with Anthony's next publish.\n"
    "- Domains, phone numbers, email addresses, GoHighLevel ids or settings, publishing or unpublishing a site, tracking pixels, open houses, listings, and deleting an agent, a site or a whole record are not done this way (removing one testimonial or past sale is fine). Say so plainly and that Anthony handles them. Do not offer a deploy key, `npx convex` or a change to the door's code as another way to do it, and never use a deploy key or `npx convex` for agent data.\n"
)
BLOCK = START + "\n" + BODY + END + "\n"

START_RE = re.compile(r"<!-- kit-block:sitedoor v\d+ -->")
BLOCK_RE = re.compile(r"<!-- kit-block:sitedoor v\d+ -->.*?<!-- /kit-block:sitedoor -->[ \t]*", re.S)


def strip_blocks(text):
    """Cut every sitedoor block out where it sits. Only the newlines right next to a
    block are touched; every other line of the file stays byte for byte."""
    starts = len(START_RE.findall(text))
    ends = text.count(END)
    if starts != ends:
        return None
    while True:
        m = BLOCK_RE.search(text)
        if not m:
            return text
        before = text[:m.start()].rstrip("\n")
        after = text[m.end():].lstrip("\n")
        sep = "\n\n" if before and after else ("\n" if before else "")
        text = before + sep + after


def ensure(text):
    base = strip_blocks(text)
    if base is None:
        return None
    base = base.rstrip("\n")
    return (base + "\n\n" if base else "") + BLOCK


def remove(text):
    return strip_blocks(text)


def main(argv):
    if len(argv) != 3 or argv[2] not in ("ensure", "remove"):
        print(__doc__.strip().splitlines()[2], file=sys.stderr)
        print("usage: claude-md-block.py <file> ensure|remove", file=sys.stderr)
        return 2
    path, action = argv[1], argv[2]
    if not os.path.isfile(path):
        print("claude-md-block: %s not present, nothing to do" % path)
        return 0
    with open(path, encoding="utf-8") as f:
        text = f.read()
    new = ensure(text) if action == "ensure" else remove(text)
    if new is None:
        print("claude-md-block: %s has a sitedoor start marker without its end marker (or the "
              "reverse); fix it by hand, nothing changed" % path, file=sys.stderr)
        return 1
    if new == text:
        print("claude-md-block: %s already %s" % (path, "has the current block" if action == "ensure"
                                                   else "has no block"))
        return 0
    tmp = path + ".kit-block.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(new)
    os.replace(tmp, path)
    print("claude-md-block: %s the sitedoor block %s %s" % ("added" if action == "ensure" else "removed",
                                                         "to" if action == "ensure" else "from", path))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
