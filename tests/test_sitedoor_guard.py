#!/usr/bin/env python3
"""sitedoor-guard hook test: any Bash command naming the editor token's Keychain
item is blocked (exit 2, a reason on stderr); a normal sitedoor run and other
commands pass; a bad payload fails open. Also checks the hook is registered in
settings.fragment.json and listed in uninstall.sh.

Run: python3 tests/test_sitedoor_guard.py   (exit 0 = pass)
"""
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(REPO, "claude", "hooks", "sitedoor-guard.py")
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


def main():
    check(os.path.isfile(HOOK), "sitedoor-guard.py exists")
    if not os.path.isfile(HOOK):
        return 1
    with open(HOOK) as f:
        check(f.readline().strip() == "#!/usr/bin/env python3", "portable shebang")

    blocked = [
        "security find-generic-password -s next-phil-editor -a phil -w",
        "security add-generic-password -U -s next-phil-editor -a phil -w abc",
        "python3 ~/.claude/skills/sitedoor/tools/sitedoor.py whoami; echo next-phil-editor",
        "grep -r NEXT-PHIL-EDITOR ~/Library",
        "secret-tool lookup service next-phil-editor account phil",
        # quoting and splitting bypasses (review K1)
        'security find-generic-password -s next-phil-"editor" -a phil -w',
        "security find-generic-password -s next-phil-ed''itor -a phil -w",
        "security find-generic-password -s next-phil-\\editor -a phil -w",
        "S=next-phil; security find-generic-password -s $S-editor -a phil -w",
        "S=next-phil; security find-generic-password -s ${S}-editor -a phil -w",
        "security find-generic-password -s $'next-phil-\\x65ditor' -a phil -w",
        "security find-generic-password -s $'next-phil-\\145ditor' -a phil -w",
        # lookups that never name the service
        "security find-generic-password -a phil -w",
        "security find-generic-password -a phil-sim -g",
        "security find-generic-password -w",
        "security dump-keychain -d",
        # the tool's own reader, called from Python (gate G11 case K1)
        'cd ~/.claude/skills/sitedoor/tools && python3 -c "import sitedoor,builtins; '
        'builtins.print(sitedoor.read_token(\'phil\'))"',
        "python3 -c 'from sitedoor import read_token; print(read_token(\"phil\"))'",
        "python3 -c 'import sitedoor; print(sitedoor._SECRETS)'",
        "python3 -c 'import builtins, sitedoor as s; builtins.print(s.read_token(\"phil\"))'",
        "python3 -c 'from sitedoor import _SECRETS as x; print(x)'",
        # a Python argument list with the item name split by + (gate G11 case K2)
        "['security','find-generic-password','-s','next-phil-'+'edi'+'tor','-w']",
        "python3 -c \"import subprocess; print(subprocess.check_output("
        "['security','find-generic-password','-s','next-phil-'+'edi'+'tor','-w']))\"",
        "python3 -c \"import subprocess; subprocess.run(['security','find-generic-password',"
        "'-a','phil','-w'])\"",
    ]
    for c in blocked:
        rc, err = run(bash(c))
        check(rc == 2 and err.strip(), "blocked: %s" % c[:60])
    rc, err = run(bash(blocked[0]))
    flat = " ".join(err.split())
    check("pull request" in flat and "DevNextRealEstate/next-listing-pages" in flat and "Anthony reviews" in flat,
          "the block message says a change the editor cannot make goes in a pull request Anthony reviews")

    allowed = [
        "python3 ~/.claude/skills/sitedoor/tools/sitedoor.py plan anthony-test --payload /tmp/p.json",
        "python3 ~/.claude/skills/sitedoor/tools/sitedoor.py whoami --json",
        "python3 /Users/phil/.claude/skills/sitedoor/tools/sitedoor.py whoami",
        "python3 ~/.claude/skills/sitedoor/tools/sitedoor.py get victoria-kulszan --sales all",
        "bash setup.sh",
        "python3 -c 'print([1, 2] + [3])'",
        # ordinary commands in the website repo whose names only contain the words (gate G18)
        'grep -rn "realtor_secrets" convex/',
        "cat convex/realtor_secrets.ts",
        "git log --oneline -S HANDOFF_READ_TOKEN",
        "vercel env ls production | grep SECRETS_READ_TOKEN",
        "grep -rn SECRETS_GHL_READ_TOKEN src/ scripts/",
        "npx vitest run convex/realtor_secrets.test.ts",
        "git status",
        "security find-generic-password -s some-other-app -a anthony -w",
        "bash setup.sh --vault-root ~/vault",
        "grep -n editor README.md",
        "cd ~/next-phil-claude-kit && git log --grep editor",
        "git -C /Users/phil/next-phil-claude-kit log --oneline -- claude/hooks/sitedoor-guard.py  # editor door",
    ]
    for c in allowed:
        rc, err = run(bash(c))
        check(rc == 0, "allowed: %s" % c[:60])

    rc, err = run("not json")
    check(rc == 0, "bad payload fails open")
    rc, err = run(json.dumps({"tool_name": "Bash", "tool_input": {}}))
    check(rc == 0, "empty command passes")

    with open(os.path.join(REPO, "claude", "settings.fragment.json")) as f:
        frag = json.load(f)
    cmds = [h.get("command", "") for e in frag["hooks"].get("PreToolUse", [])
            if e.get("matcher") == "Bash" for h in e.get("hooks", [])]
    check(any(c.endswith("/sitedoor-guard.py") for c in cmds), "registered as a PreToolUse Bash hook")
    with open(os.path.join(REPO, "uninstall.sh")) as f:
        un = f.read()
    check(un.count("sitedoor-guard.py") >= 2, "uninstall.sh removes the file and its registration")

    print("%d failure(s)" % len(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
