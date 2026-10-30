#!/usr/bin/env python3
"""adsdoor-guard hook test: any Bash command that names the ads check token's
Keychain item, loads the adsdoor tool's token reader, or reads its test-only token
variable is blocked (exit 2, a reason on stderr); a normal adsdoor run and other
commands pass; a bad payload fails open. Also checks the hook is registered in
settings.fragment.json, listed in uninstall.sh and in the hook roster.

Run: python3 tests/test_adsdoor_guard.py   (exit 0 = pass)
"""
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(REPO, "claude", "hooks", "adsdoor-guard.py")
FAILS = []


def check(cond, label):
    print(("ok   " if cond else "FAIL ") + label)
    if not cond:
        FAILS.append(label)


def run(stdin):
    r = subprocess.run([sys.executable, HOOK], input=stdin, capture_output=True, text=True, timeout=30)
    return r.returncode, r.stderr


def bash(cmd):
    return json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": "/tmp"})


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def main():
    check(os.path.isfile(HOOK), "adsdoor-guard.py exists")
    if not os.path.isfile(HOOK):
        print("%d failure(s)" % len(FAILS))
        return 1
    with open(HOOK) as f:
        check(f.readline().strip() == "#!/usr/bin/env python3", "portable shebang")
    # a hook that cannot run fails open, so nothing would be blocked
    check(os.access(HOOK, os.X_OK), "adsdoor-guard.py is executable on disk")
    r = subprocess.run(["git", "-C", REPO, "ls-files", "-s", "--", "claude/hooks/adsdoor-guard.py"],
                       capture_output=True, text=True, timeout=30)
    if r.returncode == 0 and r.stdout.strip():
        check(r.stdout.split()[0] == "100755", "adsdoor-guard.py is committed with its exec bit (100755)")

    blocked = [
        "security find-generic-password -s next-phil-ads-status -a phil -w",
        "security add-generic-password -U -s next-phil-ads-status -a phil -w abc",
        "python3 ~/.claude/skills/adsdoor/tools/adsdoor.py --all; echo next-phil-ads-status",
        "grep -r NEXT-PHIL-ADS-STATUS ~/Library",
        "secret-tool lookup service next-phil-ads-status account phil",
        # quoting and splitting
        'security find-generic-password -s next-phil-"ads-status" -a phil -w',
        "security find-generic-password -s next-phil-ads-st''atus -a phil -w",
        "security find-generic-password -s next-phil-\\ads-status -a phil -w",
        "S=next-phil; security find-generic-password -s $S-ads-status -a phil -w",
        "S=next-phil-ads; security find-generic-password -s ${S}-status -a phil -w",
        "security find-generic-password -s $'next-phil-\\x61ds-status' -a phil -w",
        "security find-generic-password -s $'next-phil-\\141ds-status' -a phil -w",
        "['security','find-generic-password','-s','next-phil-'+'ads-'+'status','-w']",
        # lookups that never name the service
        "security find-generic-password -a phil -w",
        "security find-generic-password -w",
        "security dump-keychain -d",
        # the tool's own reader, called from Python
        "python3 -c 'import adsdoor; print(adsdoor.read_token(\"phil\"))'",
        "python3 -c 'from adsdoor import read_token; print(read_token(\"phil\"))'",
        "python3 -c 'import adsdoor; print(adsdoor._SECRETS)'",
        "cd ~/.claude/skills/adsdoor/tools && python3 -c \"import adsdoor as a, builtins; builtins.print(a.read_token('phil'))\"",
        # the test-only token variable
        "echo $ADSDOOR_TOKEN",
        "printenv ADSDOOR_TOKEN",
        "env | grep -i adsdoor_token",
    ]
    for c in blocked:
        rc, err = run(bash(c))
        check(rc == 2 and err.strip(), "blocked: %s" % c[:70])
    rc, err = run(bash(blocked[0]))
    msg = " ".join(err.split()).lower()
    check("adsdoor.py" in msg and "anthony" in msg and "draft" in msg and "terminal" in msg,
          "the block message points to the tool, the Terminal step, and a drafted message to Anthony")
    check(not any(w in msg for w in ("ssh", "deploy key", "npx convex")),
          "the block message offers no side route")

    allowed = [
        "python3 ~/.claude/skills/adsdoor/tools/adsdoor.py --all",
        "python3 ~/.claude/skills/adsdoor/tools/adsdoor.py --agent sample-agent --json",
        "python3 /Users/phil/.claude/skills/adsdoor/tools/adsdoor.py --all --tests",
        "python3 ~/.claude/skills/sitedoor/tools/sitedoor.py whoami",
        "bash setup.sh",
        "git status",
        "cd ~/next-phil-claude-kit && git status",
        "git -C /Users/phil/next-phil-claude-kit log --oneline -- claude/skills/adsdoor  # ads status",
        "grep -rn ads README.md",
        "security find-generic-password -s some-other-app -a anthony -w",
        "python3 -c 'print([1, 2] + [3])'",
        'grep -rn "realtor_secrets" convex/',
    ]
    for c in allowed:
        rc, err = run(bash(c))
        check(rc == 0, "allowed: %s" % c[:70])

    rc, err = run("not json")
    check(rc == 0, "bad payload fails open")
    rc, err = run(json.dumps({"tool_name": "Bash", "tool_input": {}}))
    check(rc == 0, "empty command passes")

    frag = json.loads(read(os.path.join(REPO, "claude", "settings.fragment.json")))
    cmds = [h.get("command", "") for e in frag["hooks"].get("PreToolUse", [])
            if e.get("matcher") == "Bash" for h in e.get("hooks", [])]
    check(any(c.endswith("/adsdoor-guard.py") for c in cmds), "registered as a PreToolUse Bash hook")
    un = read(os.path.join(REPO, "uninstall.sh"))
    check(un.count("adsdoor-guard.py") >= 2, "uninstall.sh removes the file and its registration")
    roster = read(os.path.join(REPO, "scripts", "check-hook-roster.sh"))
    check("\nadsdoor-guard.py\n" in roster, "the hook roster lists adsdoor-guard.py")
    r = subprocess.run(["bash", os.path.join(REPO, "scripts", "check-hook-roster.sh")], capture_output=True,
                       text=True, timeout=30)
    check(r.returncode == 0, "check-hook-roster.sh passes")

    print("%d failure(s)" % len(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
