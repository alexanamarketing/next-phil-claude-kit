#!/usr/bin/env python3
"""DONE proof for the scene library helper: init is idempotent and copies the 7
starter scenes, the catalog stays in step with the cards (check + heal), save
never silently replaces a scene (collision -> exit 3, plus overwrite and
keep-both), and resume finds only an unfinished video.

All local filesystem work in a temp vault root; no Higgsfield call anywhere.

Run: python3 tests/test_library.py   (exit 0 = pass)
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(REPO, "claude", "skills", "listing-video", "tools", "library.py")


def run(*args):
    return subprocess.run([sys.executable, LIB] + list(args),
                          capture_output=True, text=True)


def tree_hashes(base):
    out = {}
    for root, _dirs, files in os.walk(base):
        for f in sorted(files):
            p = os.path.join(root, f)
            rel = os.path.relpath(p, base)
            out[rel] = hashlib.sha256(open(p, "rb").read()).hexdigest()
    return out


def catalog_files(index_path):
    text = open(index_path).read()
    return [m for m in re.findall(r"([A-Za-z0-9._-]+\.md)", text) if m != "INDEX.md"]


def main():
    root = tempfile.mkdtemp(prefix="lib-test-")
    base = os.path.join(root, "listing-videos")
    scenes = os.path.join(base, "scenes")
    output = os.path.join(base, "output")
    index = os.path.join(scenes, "INDEX.md")

    # --- 1. init: folders, 7 cards, 7 catalog lines --------------------------
    r = run("init", "--vault-root", root)
    assert r.returncode == 0, "init failed: %s" % r.stderr
    assert os.path.isdir(scenes) and os.path.isdir(output), "init did not make folders"
    cards = [f for f in os.listdir(scenes) if f.endswith(".md") and f != "INDEX.md"]
    assert len(cards) == 7, "expected 7 cards, got %d" % len(cards)
    assert len(catalog_files(index)) == 7, "catalog should list 7 cards"
    print("PASS: init made the folders, copied 7 starter scenes, wrote a 7-line catalog")

    # --- 2. init is idempotent (byte-identical second run) -------------------
    before = tree_hashes(base)
    r = run("init", "--vault-root", root)
    assert r.returncode == 0, "second init failed"
    after = tree_hashes(base)
    assert before == after, "second init changed the library"
    print("PASS: a second init changed nothing")

    # --- 3. check clean ------------------------------------------------------
    r = run("check", "--vault-root", root)
    assert r.returncode == 0, "check on a clean library should exit 0: %s" % r.stdout
    print("PASS: check on a consistent library exits 0")

    # --- 4. drop a catalog line -> check 1, heal restores --------------------
    lines = open(index).read().splitlines()
    dropped = [ln for ln in lines if "kitchen.md" not in ln]
    open(index, "w").write("\n".join(dropped) + "\n")
    r = run("check", "--vault-root", root)
    assert r.returncode == 1, "stale catalog should make check exit 1"
    r = run("check", "--vault-root", root, "--heal")
    assert r.returncode == 0, "heal should exit 0"
    assert "kitchen.md" in catalog_files(index), "heal did not restore the dropped card"
    print("PASS: a dropped catalog line -> check exits 1, --heal restores it")

    # --- 5. an unlisted card on disk -> heal lists it ------------------------
    extra = os.path.join(scenes, "garage.md")
    open(extra, "w").write("---\ntitle: Garage, slow push in\nroom: Garage\nmove: push in\n---\n")
    r = run("check", "--vault-root", root)
    assert r.returncode == 1, "an unlisted card should make check exit 1"
    r = run("check", "--vault-root", root, "--heal")
    assert r.returncode == 0 and "garage.md" in catalog_files(index), "heal did not list the new card"
    print("PASS: an unlisted card -> --heal adds it to the catalog")

    # --- 6. save a new card --------------------------------------------------
    src = os.path.join(root, "newcard.md")
    open(src, "w").write("---\ntitle: My Test Scene\nroom: Office\nmove: slide across\n---\nbody one\n")
    r = run("save", "--vault-root", root, "--name", "My Test Scene", "--card", src)
    assert r.returncode == 0, "save failed: %s" % r.stdout
    saved = os.path.join(scenes, "my-test-scene.md")
    assert os.path.isfile(saved), "saved card not written"
    assert "my-test-scene.md" in catalog_files(index), "saved card not in catalog"
    print("PASS: save wrote a new card and added it to the catalog")

    # --- 7. name collision -> exit 3, original byte-identical ----------------
    original = open(saved, "rb").read()
    src2 = os.path.join(root, "other.md")
    open(src2, "w").write("---\ntitle: My Test Scene\nroom: Office\nmove: push in\n---\nDIFFERENT body\n")
    r = run("save", "--vault-root", root, "--name", "My Test Scene", "--card", src2)
    assert r.returncode == 3, "name collision should exit 3, got %s" % r.returncode
    assert open(saved, "rb").read() == original, "collision must not touch the original card"
    print("PASS: a taken name -> exit 3, original left byte-identical")

    # --- 8. --overwrite replaces ---------------------------------------------
    r = run("save", "--vault-root", root, "--name", "My Test Scene", "--card", src2, "--overwrite")
    assert r.returncode == 0, "overwrite should succeed"
    assert b"DIFFERENT body" in open(saved, "rb").read(), "overwrite did not replace the card"
    print("PASS: --overwrite replaced the card")

    # --- 9. --keep-both yields a -2 file -------------------------------------
    r = run("save", "--vault-root", root, "--name", "My Test Scene", "--card", src, "--keep-both")
    assert r.returncode == 0, "keep-both should succeed"
    assert os.path.isfile(os.path.join(scenes, "my-test-scene-2.md")), "keep-both did not make a -2 file"
    print("PASS: --keep-both wrote my-test-scene-2.md")

    # --- 10. resume lists only the unfinished video --------------------------
    done_dir = os.path.join(output, "4136-palace-station")
    live_dir = os.path.join(output, "221-oak")
    os.makedirs(done_dir); os.makedirs(live_dir)
    json.dump({"listing": "4136 Palace Station", "status": "stitched",
               "clips": [{"scene": "kitchen", "file": "k.mp4"}]},
              open(os.path.join(done_dir, "reel.json"), "w"))
    json.dump({"listing": "221 Oak", "status": "generating",
               "clips": [{"scene": "front", "file": "f.mp4"}, {"scene": "kitchen"}]},
              open(os.path.join(live_dir, "reel.json"), "w"))
    r = run("resume", "--vault-root", root, "--json")
    assert r.returncode == 0, "resume failed: %s" % r.stdout
    listed = json.loads(r.stdout)
    assert len(listed) == 1, "resume should list exactly one unfinished video, got %d" % len(listed)
    assert listed[0]["listing"] == "221 Oak", "resume listed the wrong video"
    assert listed[0]["made"] == 1 and listed[0]["planned"] == 2, "resume miscounted clips"
    print("PASS: resume listed only the unfinished video with its clip counts")

    print("ALL LIBRARY ASSERTIONS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
