#!/usr/bin/env python3
"""Site code work test: the kit lets the user's Claude change the website code freely.

Design and layout changes are code changes in the user's copy of
DevNextRealEstate/next-listing-pages. These checks pin that nothing in the kit
stands in the way, and that the token protections still hold:

- the commands a design change runs (a branch, npm, the gate, a local preview,
  a commit, a branch push, a pull request, a merge, a vercel env pull) pass
  command-guard and sitedoor-guard;
- sitedoor-guard still blocks any command naming the editor token's Keychain item;
- file-naming-check lets code files whose names hold "complete", "ready", "done" or
  "published" through, and still refuses a document named like report-FINAL.md;
- site-checkout.sh finds a checkout, refuses a folder whose origin is another repo,
  remembers what it found, copies the repo when asked, and never overwrites a folder
  that is in the way.

Run: python3 tests/test_site_code_work.py   (exit 0 = pass)
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS = os.path.join(REPO, "claude", "hooks")
CHECKOUT = os.path.join(REPO, "claude", "skills", "sitedoor", "tools", "site-checkout.sh")

FAILS = []


def check(cond, label):
    print(("ok   " if cond else "FAIL ") + label)
    if not cond:
        FAILS.append(label)


def hook(name, payload, env=None):
    r = subprocess.run([sys.executable, os.path.join(HOOKS, name)], input=json.dumps(payload),
                       capture_output=True, text=True, timeout=30, env=env)
    return r.returncode, r.stdout + r.stderr


SITE = "/Users/phil/Projects/next-listing-pages"
# Built with join so the portability check (no Linux user-home paths) never trips on it.
HOME_COMPONENTS = os.path.join("src", "components", "home")
SITE_COMMANDS = [
    "cd %s && git fetch origin" % SITE,
    "git -C %s switch --no-track -c design/hero-spacing origin/main" % SITE,
    "cd %s && npm ci" % SITE,
    "cd %s && rm -rf node_modules .next && npm ci" % SITE,
    "cd %s && npm run dev" % SITE,
    "cd %s && bash scripts/gate.sh" % SITE,
    "cd %s && npx vercel link --yes --project next-listing-pages --scope next-real-estate-team" % SITE,
    "cd %s && npx vercel env pull .env.local --environment=preview --yes" % SITE,
    "git -C %s commit -m 'Wider hero spacing on every agent homepage' -- %s/Hero.tsx" % (SITE, HOME_COMPONENTS),
    "git -C %s push -u origin design/hero-spacing" % SITE,
    "cd %s && gh pr create --title 'Wider hero spacing' --body 'Phil asked for more room above the hero text.'" % SITE,
    "cd %s && gh pr checks 41" % SITE,
    "cd %s && gh pr merge 41 --merge" % SITE,
    "cd %s && bash scripts/sites/smoke-live-apexes.sh && bash scripts/sites/smoke-live-apexes.sh --team" % SITE,
    "grep -rn 'editor' %s/convex/editorDoor/policy.ts" % SITE,
    "bash ~/.claude/skills/sitedoor/tools/site-checkout.sh --clone",
]


def git(*args, cwd=None):
    subprocess.run(["git"] + list(args), cwd=cwd, check=True, capture_output=True, text=True)


def checkout_tests():
    d = tempfile.mkdtemp(prefix="sitecheckout-")
    home = os.path.join(d, "home")
    os.makedirs(home)
    origin = os.path.join(d, "remote", "DevNextRealEstate", "next-listing-pages.git")
    seed = os.path.join(d, "seed")
    os.makedirs(seed)
    git("init", "-q", "-b", "main", cwd=seed)
    git("-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "start", cwd=seed)
    os.makedirs(os.path.dirname(origin))
    git("clone", "-q", "--bare", seed, origin)
    env = dict(os.environ, HOME=home, NEXT_SITE_REPO_URL=origin)
    env.pop("NEXT_SITE_REPO", None)

    def run(*args):
        r = subprocess.run(["bash", CHECKOUT] + list(args), capture_output=True, text=True, timeout=60, env=env)
        return r.returncode, r.stdout + r.stderr

    rc, out = run()
    check(rc == 1 and "--clone" in out, "no copy found: exit 1 and the message names --clone")

    # a folder with the right name but another origin does not count
    other = os.path.join(home, "Projects", "next-listing-pages")
    os.makedirs(os.path.dirname(other))
    git("clone", "-q", seed, other)
    rc, out = run()
    check(rc == 1, "a next-listing-pages folder whose origin is another repo is not taken")
    rc, out = run("--clone")
    check(rc == 3 and os.path.isdir(os.path.join(other, ".git")) and "nothing was changed" in out,
          "--clone never overwrites a folder in the way")
    shutil.rmtree(other)

    # --clone copies it to the default folder and remembers it
    rc, out = run("--clone")
    real = os.path.realpath(other)
    check(rc == 0 and out.strip().splitlines()[-1] == "SITE_REPO=" + real, "--clone copies the repo and prints SITE_REPO")
    pointer = os.path.join(home, ".claude", "starter-kit", "site-repo")
    check(os.path.isfile(pointer) and open(pointer).read().strip() == real, "the folder is remembered")

    # found again without --clone; a remembered folder elsewhere is found first
    rc, out = run()
    check(rc == 0 and "SITE_REPO=" + real in out and "uncommitted changes: no" in out, "an existing copy is found and reported")
    elsewhere = os.path.join(home, "work", "site")
    os.makedirs(os.path.dirname(elsewhere))
    git("clone", "-q", origin, elsewhere)
    rc, out = run("--path", elsewhere)
    check(rc == 0 and out.strip().endswith("SITE_REPO=" + os.path.realpath(elsewhere)), "--path takes a copy anywhere")
    rc, out = run()
    check(rc == 0 and out.strip().endswith("SITE_REPO=" + os.path.realpath(elsewhere)), "the remembered --path copy is used next time")
    with open(os.path.join(elsewhere, "note.txt"), "w") as f:
        f.write("work in progress\n")
    rc, out = run()
    check("uncommitted changes: yes" in out and "Ask the user before switching" in out,
          "uncommitted work is reported with a warning to ask before switching")
    rc, out = run("--path", seed)
    check(rc == 1, "--path to a folder that is not the website repo is refused")
    rc, out = run("--bogus")
    check(rc == 2, "an unknown option is a usage error")

    # the script itself never touches env files
    src = open(CHECKOUT).read()
    check(".env.local" not in src.replace("Local runs need\n# .env.local", ""),
          "site-checkout.sh never reads or writes .env.local")
    shutil.rmtree(d, ignore_errors=True)


def main():
    for cmd in SITE_COMMANDS:
        p = {"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": SITE}
        rc1, out1 = hook("command-guard.py", p)
        rc2, out2 = hook("sitedoor-guard.py", p)
        check(rc1 == 0 and rc2 == 0, "site command passes the guards: %s" % cmd[:80])

    for cmd in ("security find-generic-password -s next-phil-editor -a phil -w",
                "S=next-phil; security find-generic-password -s $S-editor -w"):
        rc, out = hook("sitedoor-guard.py", {"tool_name": "Bash", "tool_input": {"command": cmd}})
        check(rc == 2, "sitedoor-guard still blocks the token lookup: %s" % cmd[:60])

    def naming(path):
        rc, out = hook("file-naming-check.py", {"tool_name": "Write", "tool_input": {"file_path": path, "content": "x"}})
        return "deny" in out

    for path in ("%s/%s/publish-complete.tsx" % (SITE, HOME_COMPONENTS), "%s/src/lib/use-ready.ts" % SITE,
                 "%s/public/step-done.svg" % SITE, "%s/data/ghl-layouts/x/home-published.json" % SITE):
        check(not naming(path), "file-naming-check lets a code file through: %s" % os.path.basename(path))
    for path in ("/Users/phil/vault/active/x/report-FINAL.md", "/Users/phil/vault/active/x/plan-done.txt"):
        check(naming(path), "file-naming-check still refuses a document: %s" % os.path.basename(path))

    checkout_tests()

    print("%d failure(s)" % len(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
