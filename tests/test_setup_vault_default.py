#!/usr/bin/env python3
"""setup.sh re-run test: a second run remembers the vault folder and refreshes doctor.py.

Runs setup.sh --dry-run in a temp HOME whose pointer file already names a vault.
Pressing Enter at the vault question must keep that vault (not fall back to
~/vault), and the merge step must say it refreshes the kit-owned doctor.py.
Fake node, npm and claude programs on PATH stand in for the prerequisites, so
nothing is installed and nothing touches the network.

Run: python3 tests/test_setup_vault_default.py   (exit 0 = pass)
"""
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAILS = []


def check(cond, label):
    print(("ok   " if cond else "FAIL ") + label)
    if not cond:
        FAILS.append(label)


def shim(d, name, out):
    p = os.path.join(d, name)
    with open(p, "w") as f:
        f.write("#!/bin/sh\necho '%s'\nexit 0\n" % out)
    os.chmod(p, os.stat(p).st_mode | stat.S_IEXEC)


def main():
    home = tempfile.mkdtemp(prefix="setup-home-")
    bins = os.path.join(home, "bin")
    os.makedirs(bins)
    shim(bins, "node", "v20.11.0")
    shim(bins, "npm", "10.2.4")
    shim(bins, "claude", "2.1.0 (Claude Code)")
    vault = os.path.join(home, "Documents", "MyVault")
    os.makedirs(os.path.join(vault, "scripts"))
    with open(os.path.join(vault, "scripts", "doctor.py"), "w") as f:
        f.write("# old doctor\n")
    os.makedirs(os.path.join(home, ".claude", "starter-kit"))
    with open(os.path.join(home, ".claude", "starter-kit", "config.json"), "w") as f:
        json.dump({"vault_root": vault}, f)
    env = dict(os.environ, HOME=home, PATH=bins + os.pathsep + os.environ.get("PATH", ""))
    r = subprocess.run(["bash", os.path.join(REPO, "setup.sh"), "--dry-run"], input="\ny\n",  # Enter at the vault question, y to merge
                       capture_output=True, text=True, env=env, timeout=300)
    out = r.stdout + r.stderr
    check(r.returncode == 0, "setup --dry-run exits 0 (rc=%d)" % r.returncode)
    check("[%s]" % vault in out or "Vault root: %s" % vault in out,
          "the vault question offers the remembered vault")
    check("Vault root: %s" % vault in out and "Vault root: %s/vault" % home not in out,
          "pressing Enter keeps the remembered vault")
    check("doctor.py" in out and "refresh" in out.lower(), "the merge step refreshes the kit-owned doctor.py")
    with open(os.path.join(vault, "scripts", "doctor.py")) as f:
        check(f.read() == "# old doctor\n", "a dry run changes nothing")
    # a typed ~/X lands in $HOME/X, never $HOME/~/X (review K16)
    r = subprocess.run(["bash", os.path.join(REPO, "setup.sh"), "--dry-run"], input="~/OtherVault\ny\n",
                       capture_output=True, text=True, env=env, timeout=300)
    out = r.stdout + r.stderr
    check(r.returncode == 0 and "Vault root: %s/OtherVault" % home in out and "/~/" not in out,
          "a typed ~/OtherVault becomes $HOME/OtherVault")
    # a first install (no pointer file): Enter gives $HOME/vault
    os.remove(os.path.join(home, ".claude", "starter-kit", "config.json"))
    r = subprocess.run(["bash", os.path.join(REPO, "setup.sh"), "--dry-run"], input="\ny\n",
                       capture_output=True, text=True, env=env, timeout=300)
    out = r.stdout + r.stderr
    check(r.returncode == 0 and "Vault root: %s/vault" % home in out and "/~/" not in out,
          "Enter on a first install gives $HOME/vault")
    r = subprocess.run(["bash", os.path.join(REPO, "setup.sh"), "--dry-run", "--vault-root", "~/ArgVault"],
                       input="y\n", capture_output=True, text=True, env=env, timeout=300)
    out = r.stdout + r.stderr
    check(r.returncode == 0 and "Using --vault-root: %s/ArgVault" % home in out, "--vault-root '~/X' expands too")
    shutil.rmtree(home, ignore_errors=True)
    print("%d failure(s)" % len(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
