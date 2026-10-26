#!/usr/bin/env python3
"""setup.sh real-run test: a Mac re-install into an existing vault finishes.

Phil's Mac stopped twice on 2026-10-26:
- macOS cp -n exits 1 whenever it skips a file that already exists, so the
  vault merge (step 4) and the references merge ended the script under set -e.
- site-checkout.sh exits non-zero when the website code is not on the
  computer, and with pipefail that ended the script after the skills step.

A fake cp on PATH acts like the macOS one (runs the real cp, then exits 1 if
-n skipped anything). The temp HOME has no website code, so site-checkout
reports "not found" exactly as on Phil's Mac. Fake node, npm and claude stand
in for the prerequisites; nothing touches the network.

Run: python3 tests/test_setup_mac_rerun.py   (exit 0 = pass)
"""
import os
import shutil
import stat
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAILS = []

MAC_CP = """#!/bin/bash
# macOS cp: with -n, a skipped existing file makes the exit status 1.
noclobber=false; args=()
for a in "$@"; do
  case "$a" in -*n*) noclobber=true ;; esac
  args+=("$a")
done
dest="${args[${#args[@]}-1]}"; src="${args[${#args[@]}-2]}"
skipped=false
if $noclobber && [ -d "$src" ] && [ -d "$dest" ]; then
  while IFS= read -r rel; do
    [ -e "$dest/$rel" ] && skipped=true
  done < <(cd "$src" && find . -type f)
fi
/bin/cp "$@" || exit $?
$skipped && exit 1
exit 0
"""


def check(cond, label):
    print(("ok   " if cond else "FAIL ") + label)
    if not cond:
        FAILS.append(label)


def shim(d, name, body):
    p = os.path.join(d, name)
    with open(p, "w") as f:
        f.write(body)
    os.chmod(p, os.stat(p).st_mode | stat.S_IEXEC)


def main():
    home = tempfile.mkdtemp(prefix="setup-mac-")
    bins = os.path.join(home, "bin")
    os.makedirs(bins)
    shim(bins, "node", "#!/bin/sh\necho v20.11.0\n")
    shim(bins, "npm", "#!/bin/sh\necho 10.2.4\n")
    shim(bins, "claude", "#!/bin/sh\necho '2.1.0 (Claude Code)'\n")
    shim(bins, "cp", MAC_CP)
    vault = os.path.join(home, "vault")
    os.makedirs(os.path.join(vault, "scripts"))
    with open(os.path.join(vault, "notes.md"), "w") as f:
        f.write("mine\n")
    with open(os.path.join(vault, "scripts", "doctor.py"), "w") as f:
        f.write("# old doctor\n")
    # a reference Claude already learned must survive the re-install
    refs = os.path.join(REPO, "claude", "references")
    seed = next((os.path.join(dp, n) for dp, _, fs in os.walk(refs) for n in fs), None)
    if seed:
        mine = os.path.join(home, ".claude", "references", os.path.relpath(seed, refs))
        os.makedirs(os.path.dirname(mine), exist_ok=True)
        with open(mine, "w") as f:
            f.write("learned\n")
    env = dict(os.environ, HOME=home, PATH=bins + os.pathsep + os.environ.get("PATH", ""),
               PIP_NO_INDEX="1")
    env.pop("NEXT_SITE_REPO", None)
    r = subprocess.run(["bash", os.path.join(REPO, "setup.sh"), "--yes", "--vault-root", vault],
                       capture_output=True, text=True, env=env, timeout=300)
    out = r.stdout + r.stderr
    check(r.returncode == 0, "a Mac re-install exits 0 (rc=%d)" % r.returncode)
    check("Vault skeleton merged" in out, "the vault merge carries on past step 4")
    check("Website code not on this computer yet" in out, "a missing website copy is reported, not fatal")
    check("References installed" in out, "the references merge carries on")
    with open(os.path.join(vault, "notes.md")) as f:
        check(f.read() == "mine\n", "an existing vault file is not overwritten")
    if seed:
        with open(mine) as f:
            check(f.read() == "learned\n", "an existing reference is not overwritten")
    for rel in ("scripts",):
        check(os.path.isdir(os.path.join(vault, rel)), "the skeleton's %s/ is in the vault" % rel)
    if r.returncode != 0:
        print(out[-2000:])
    shutil.rmtree(home, ignore_errors=True)


if __name__ == "__main__":
    main()
    sys.exit(1 if FAILS else 0)
