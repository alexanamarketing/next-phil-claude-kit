#!/usr/bin/env python3
"""claude-md-block.py: keep the kit's managed blocks (sitedoor, adsdoor) in a CLAUDE.md.

Usage:
  python3 scripts/claude-md-block.py <file> ensure [sitedoor|adsdoor]   add or refresh a block (idempotent)
  python3 scripts/claude-md-block.py <file> remove [sitedoor|adsdoor]   take a block out
  The block name defaults to sitedoor.

ensure: when the file is absent, nothing is created (setup.sh copies the kit's
CLAUDE.md, which already carries both blocks). When the file already holds the
current block exactly once and no other version of it, nothing changes. Otherwise
every existing block of that name (any version, anywhere in the file) is removed
and the current block is appended at the end on its own lines. A second run
changes nothing, and ensuring one block never moves or touches the other.
remove: takes every block of that name out. Only the blank lines right next to a block
change; every other line of the file is left exactly as it was.
A start marker without its end marker is refused (exit 1) and the file is left alone.
Exit codes: 0 ok, 1 refused, 2 usage.
"""
import os
import re
import sys

START = "<!-- kit-block:sitedoor v2 -->"
END = "<!-- /kit-block:sitedoor -->"
BODY = (
    "## Agent websites: content, design and code\n"
    "\n"
    "- Content on an agent's site (the record: name, bio, title, phone, testimonials, past sales, service areas, social links, license, office address, website and legal links, headshot, logos, partner details; and the homepage draft: SEO, hero, about text, sections) goes through the `sitedoor` skill first, using your own editor token from the Keychain. It shows the change first, writes only after you say yes, logs it in the MLS log and can undo it. Before applying, say where it will show: record fields on the agent's portfolio page in about five minutes, a new testimonial first on that agent's listing pages, a past sale on the homepage only with a photo and in the top 24 by price, and homepage draft fields in the draft only, live with Anthony's next publish.\n"
    "- Design and everything else on the site (layout, styling, colours, fonts, spacing, new or reworked sections, a different look for one agent, any page of properties.nextrealestate.team or an agent site) is a code change you make yourself in the user's copy of the website code. Never tell the user it is out of reach or needs Anthony. Find or set up that copy with `bash ~/.claude/skills/sitedoor/tools/site-checkout.sh` (add `--clone` to copy it from GitHub when none is found), run `git fetch origin` there and read the current rules with `git show origin/main:AGENTS.md` (section \"Design Changes from Phil's Chat\"), then follow them: a new branch, the change, `bash scripts/gate.sh`, push the branch, show the user the Vercel preview link, and merge to main only after the user says yes. Never skip a check (`--no-verify`, force-push), never run `npx convex dev` or `npx convex deploy`, and never put a draft agent site live.\n"
    "- The editor refuses only publishing or unpublishing a site, fields that would break things (the sign-in email, domains, GoHighLevel ids and forms, tracking pixels, MLS data, record ids), Phil's and Jim's own records, open houses, listings, and deleting an agent, a site or a whole record. Those refusals, anything a repo check or guard stops that fixing the change cannot pass, and backend changes under `convex/` (they need a deploy key the user does not hold) are the only edge cases: make them as a pull request on GitHub in DevNextRealEstate/next-listing-pages; Anthony reviews and merges it. Do not work around a refusal: do not offer a deploy key, `npx convex` or a change to the door's code, and never use a deploy key or `npx convex` for agent data.\n"
)
BLOCK = START + "\n" + BODY + END + "\n"

START_RE = re.compile(r"<!-- kit-block:sitedoor v\d+ -->")
BLOCK_RE = re.compile(r"<!-- kit-block:sitedoor v\d+ -->.*?<!-- /kit-block:sitedoor -->[ \t]*", re.S)


ADS_START = "<!-- kit-block:adsdoor v1 -->"
ADS_END = "<!-- /kit-block:adsdoor -->"
ADS_BODY = (
    "## Agent ads connection\n"
    "\n"
    "- To check whether an agent's Facebook ads connection works, use the `adsdoor` skill, with your own ads check token from the Keychain. It only reads. For each agent it says whether NEXT has the agent's Facebook Page with Ads and Content turned on, whether that Page id is on the agent's record, whether the agent is on the open-house text list and whether the ads engine turned the agent down, and for each problem what to do and whether it is Phil's or Anthony's.\n"
    "- Storing a Page id, changing the text list, restarting the ads engine and anything about the ads check token, the Facebook token or the server are Anthony's side. Say so plainly and offer to draft the message to Anthony with what the check found. Do not look for another way to do it: never offer ssh, a deploy key, `npx convex`, the sitedoor editor or the Facebook token.\n"
)
ADS_BLOCK = ADS_START + "\n" + ADS_BODY + ADS_END + "\n"


def _spec(name):
    return {
        "name": name,
        "start": START if name == "sitedoor" else ADS_START,
        "end": END if name == "sitedoor" else ADS_END,
        "block": BLOCK if name == "sitedoor" else ADS_BLOCK,
        "start_re": re.compile(r"<!-- kit-block:%s v\d+ -->" % name),
        "block_re": re.compile(r"<!-- kit-block:%s v\d+ -->.*?<!-- /kit-block:%s -->[ \t]*" % (name, name), re.S),
    }


BLOCKS = {"sitedoor": _spec("sitedoor"), "adsdoor": _spec("adsdoor")}


def strip_blocks(text, which="sitedoor"):
    """Cut every block of this name out where it sits. Only the newlines right next to a
    block are touched; every other line of the file stays byte for byte."""
    spec = BLOCKS[which]
    starts = len(spec["start_re"].findall(text))
    ends = text.count(spec["end"])
    if starts != ends:
        return None
    while True:
        m = spec["block_re"].search(text)
        if not m:
            return text
        before = text[:m.start()].rstrip("\n")
        after = text[m.end():].lstrip("\n")
        sep = "\n\n" if before and after else ("\n" if before else "")
        text = before + sep + after


def ensure(text, which="sitedoor"):
    spec = BLOCKS[which]
    if text.count(spec["block"]) == 1 and len(spec["start_re"].findall(text)) == 1 \
            and text.count(spec["end"]) == 1:
        return text
    base = strip_blocks(text, which)
    if base is None:
        return None
    base = base.rstrip("\n")
    return (base + "\n\n" if base else "") + spec["block"]


def remove(text, which="sitedoor"):
    return strip_blocks(text, which)


def main(argv):
    if len(argv) not in (3, 4) or argv[2] not in ("ensure", "remove") or (len(argv) == 4 and argv[3] not in BLOCKS):
        print(__doc__.strip().splitlines()[2], file=sys.stderr)
        print("usage: claude-md-block.py <file> ensure|remove [sitedoor|adsdoor]", file=sys.stderr)
        return 2
    path, action = argv[1], argv[2]
    which = argv[3] if len(argv) == 4 else "sitedoor"
    if not os.path.isfile(path):
        print("claude-md-block: %s not present, nothing to do" % path)
        return 0
    with open(path, encoding="utf-8") as f:
        text = f.read()
    new = ensure(text, which) if action == "ensure" else remove(text, which)
    if new is None:
        print("claude-md-block: %s has a %s start marker without its end marker (or the "
              "reverse); fix it by hand, nothing changed" % (path, which), file=sys.stderr)
        return 1
    if new == text:
        print("claude-md-block: %s already %s" % (path, "has the current block" if action == "ensure"
                                                   else "has no block"))
        return 0
    tmp = path + ".kit-block.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(new)
    os.replace(tmp, path)
    print("claude-md-block: %s the %s block %s %s" % ("added" if action == "ensure" else "removed", which,
                                                    "to" if action == "ensure" else "from", path))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
