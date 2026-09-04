#!/usr/bin/env python3
"""Manage the scene library that lives in the user's vault.

This is the only thing that writes scene cards, so cards never go in through the
Write tool (that would trip the index-enforcer hook on the user's first run). It
copies the shipped starter scenes into the user's library, keeps the catalog
(INDEX.md) in step with the cards on disk, saves new cards without ever silently
replacing one, and finds a half-finished video from a prior session.

Subcommands:
    init    --vault-root R
    list    --vault-root R [--json]
    check   --vault-root R [--heal]
    save    --vault-root R --name "<plain name>" --card <path> [--overwrite|--keep-both]
    resume  --vault-root R [--json]

The vault root comes from --vault-root; if that flag is omitted it falls back to
the HOOK_VAULT_ROOT or VAULT_ROOT environment variable. Everything lives under
<vault-root>/listing-videos/ with scenes/ (the cards), INDEX.md (the catalog),
and output/ (one folder per listing, each holding a reel.json progress file).

Exit codes:
    0  success / consistent
    1  check found a mismatch and --heal was not given
    2  a usage or filesystem error (plain sentence)
    3  save hit a name that is already taken (plain sentence, nothing written)
"""
import argparse
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SEED_DIR = os.path.normpath(os.path.join(HERE, "..", "seed-scenes"))


def resolve_root(flag):
    root = flag or os.environ.get("HOOK_VAULT_ROOT") or os.environ.get("VAULT_ROOT")
    if not root:
        print("I do not know where your vault is. Tell me the vault folder and I "
              "will set up your scenes there.")
        return None
    return os.path.abspath(os.path.expanduser(root))


def paths(root):
    base = os.path.join(root, "listing-videos")
    return {
        "base": base,
        "scenes": os.path.join(base, "scenes"),
        "output": os.path.join(base, "output"),
        "index": os.path.join(base, "scenes", "INDEX.md"),
    }


def slugify(name):
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "scene"


def read_field(text, field):
    m = re.search(r"^%s:\s*(.+)$" % re.escape(field), text, re.MULTILINE)
    return m.group(1).strip() if m else ""


def card_files(scenes_dir):
    if not os.path.isdir(scenes_dir):
        return []
    return sorted(f for f in os.listdir(scenes_dir)
                  if f.endswith(".md") and f != "INDEX.md")


def catalog_row(scenes_dir, fname):
    text = open(os.path.join(scenes_dir, fname)).read()
    title = read_field(text, "title") or fname[:-3]
    room = read_field(text, "room") or "-"
    move = read_field(text, "move") or "-"
    return title, room, move, fname


def write_index(scenes_dir, index_path):
    rows = [catalog_row(scenes_dir, f) for f in card_files(scenes_dir)]
    lines = [
        "# Your scenes",
        "",
        "These are the scenes in your library. Claude writes this list for you from "
        "the cards on disk; you do not edit it by hand.",
        "",
        "| title | room | move | file |",
        "| --- | --- | --- | --- |",
    ]
    for title, room, move, fname in rows:
        lines.append("| %s | %s | %s | %s |" % (title, room, move, fname))
    with open(index_path, "w") as f:
        f.write("\n".join(lines) + "\n")


def files_in_index(index_path):
    if not os.path.isfile(index_path):
        return set()
    text = open(index_path).read()
    return set(m for m in re.findall(r"([A-Za-z0-9._-]+\.md)", text)
               if m != "INDEX.md")


def cmd_init(args):
    root = resolve_root(args.vault_root)
    if not root:
        return 2
    p = paths(root)
    os.makedirs(p["scenes"], exist_ok=True)
    os.makedirs(p["output"], exist_ok=True)
    copied = 0
    for f in sorted(os.listdir(SEED_DIR)):
        if not f.endswith(".md") or f == "INDEX.md":
            continue
        dest = os.path.join(p["scenes"], f)
        if not os.path.exists(dest):
            shutil.copy(os.path.join(SEED_DIR, f), dest)
            copied += 1
    write_index(p["scenes"], p["index"])
    print("Set up your scene library at %s (copied %d new scene(s); %d in total)."
          % (p["base"], copied, len(card_files(p["scenes"]))))
    return 0


def cmd_list(args):
    root = resolve_root(args.vault_root)
    if not root:
        return 2
    p = paths(root)
    rows = [catalog_row(p["scenes"], f) for f in card_files(p["scenes"])]
    if args.json:
        print(json.dumps([{"title": t, "room": r, "move": m, "file": f}
                          for t, r, m, f in rows]))
        return 0
    if not rows:
        print("You have no scenes yet.")
        return 0
    for t, r, m, f in rows:
        print("%s  (%s, %s)  [%s]" % (t, r, m, f))
    return 0


def cmd_check(args):
    root = resolve_root(args.vault_root)
    if not root:
        return 2
    p = paths(root)
    on_disk = set(card_files(p["scenes"]))
    in_catalog = files_in_index(p["index"])
    missing_from_catalog = sorted(on_disk - in_catalog)
    gone_files = sorted(in_catalog - on_disk)

    if not missing_from_catalog and not gone_files:
        print("Your scene library and its list agree.")
        return 0

    for f in missing_from_catalog:
        print("Not in the list yet: %s" % f)
    for f in gone_files:
        print("Listed but the file is gone: %s" % f)

    if args.heal:
        write_index(p["scenes"], p["index"])
        print("I rebuilt the list from the scenes you have. No scene was deleted.")
        return 0
    return 1


def cmd_save(args):
    root = resolve_root(args.vault_root)
    if not root:
        return 2
    p = paths(root)
    if not os.path.isfile(args.card):
        print("I could not find the card to save: %s" % args.card)
        return 2
    os.makedirs(p["scenes"], exist_ok=True)
    slug = slugify(args.name)
    dest = os.path.join(p["scenes"], slug + ".md")
    content = open(args.card).read()

    if os.path.exists(dest) and not args.overwrite and not args.keep_both:
        print("You already have a scene named \"%s\". "
              "Tell me to overwrite it, keep both, or use a new name." % args.name)
        return 3

    if os.path.exists(dest) and args.keep_both:
        i = 2
        while os.path.exists(os.path.join(p["scenes"], "%s-%d.md" % (slug, i))):
            i += 1
        dest = os.path.join(p["scenes"], "%s-%d.md" % (slug, i))

    with open(dest, "w") as f:
        f.write(content)
    write_index(p["scenes"], p["index"])
    print("Saved \"%s\" as %s." % (args.name, os.path.basename(dest)))
    return 0


def cmd_resume(args):
    root = resolve_root(args.vault_root)
    if not root:
        return 2
    p = paths(root)
    unfinished = []
    if os.path.isdir(p["output"]):
        for slug in sorted(os.listdir(p["output"])):
            manifest = os.path.join(p["output"], slug, "reel.json")
            if not os.path.isfile(manifest):
                continue
            try:
                data = json.load(open(manifest))
            except (ValueError, OSError):
                continue
            if data.get("status") == "stitched":
                continue
            clips = data.get("clips", []) or []
            made = [c for c in clips if c.get("file")]
            unfinished.append({
                "listing": data.get("listing", slug),
                "status": data.get("status", "unknown"),
                "made": len(made),
                "planned": len(clips),
                "manifest": manifest,
            })
    if args.json:
        print(json.dumps(unfinished))
        return 0
    if not unfinished:
        print("No unfinished videos. You are all caught up.")
        return 0
    for u in unfinished:
        print("Unfinished: %s (%d of %d clips made, status %s)"
              % (u["listing"], u["made"], u["planned"], u["status"]))
    return 0


def main():
    parser = argparse.ArgumentParser(add_help=True)
    sub = parser.add_subparsers(dest="cmd", required=True)

    for name in ("init", "list", "check", "save", "resume"):
        sp = sub.add_parser(name)
        sp.add_argument("--vault-root", default=None)
        if name in ("list", "resume"):
            sp.add_argument("--json", action="store_true")
        if name == "check":
            sp.add_argument("--heal", action="store_true")
        if name == "save":
            sp.add_argument("--name", required=True)
            sp.add_argument("--card", required=True)
            sp.add_argument("--overwrite", action="store_true")
            sp.add_argument("--keep-both", action="store_true")

    args = parser.parse_args()
    return {
        "init": cmd_init,
        "list": cmd_list,
        "check": cmd_check,
        "save": cmd_save,
        "resume": cmd_resume,
    }[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
