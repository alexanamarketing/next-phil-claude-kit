#!/usr/bin/env python3
"""Secret-hook tests: every case runs against BOTH the pre-run hooks
(tests/fixtures/pre-run/, byte copies of kit commit 67ceb79) and the current
hooks (claude/hooks/), and asserts the exact before/after result per case.

secret-guard.py (gitleaks on git commit/push):
  (1) first push of a new branch whose parent commits are already on the
      remote and hold a fake token: old blocks (it rescanned the last 20
      commits), new allows (it scans only commits no remote has)
  (2) a NEW fake token on the branch: both block
  (3) branch pushed, a token commit lands on main, branch rebased onto it:
      old blocks (@{u}..HEAD rescans main's commit), new allows
  (4) push run from a SUBDIRECTORY with a repo-root .gitleaks.toml allowlist:
      old blocks (gitleaks only loads the toml from its cwd), new allows
  (5) trap lock: a .gitleaks.toml WITHOUT `[extend] useDefault = true`
      silently turns detection off (gitleaks itself exits 0 on a planted
      token); the kit's shipped template carries the line and still catches
      a canary
  (9) malformed .gitleaks.toml: gitleaks exits 1 "unable to load gitleaks
      config"; old reads that as leaks and blocks, new reports a config error
      and allows
  (G4) `git commit ... && git push`: old ran only the commit scan, new runs
      both and catches the unpushed token
block-secrets.py (Read/Edit/Write/MultiEdit on sensitive files):
  (6) Read is always allowed now (Read .env: old blocks, new allows)
  (7) Edit/Write on real secret files is blocked (exact names, not substrings)
  (8) source files that only contain a word like "api-key" are allowed now

Fake tokens are built at runtime with a random suffix; none is written
literally in this file. gitleaks MUST be installed: the secret-guard cases
FAIL (never skip) without it, because a skipped scanner test proves nothing.

Run: python3 tests/test_secret_hooks.py   (exit 0 = pass; prints a table)
 or: python3 -m pytest -q tests/test_secret_hooks.py
"""
import json
import os
import random
import shutil
import string
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS = {
    "old": {
        "secret-guard": os.path.join(ROOT, "tests", "fixtures", "pre-run", "secret-guard.py"),
        "block-secrets": os.path.join(ROOT, "tests", "fixtures", "pre-run", "block-secrets.py"),
    },
    "new": {
        "secret-guard": os.path.join(ROOT, "claude", "hooks", "secret-guard.py"),
        "block-secrets": os.path.join(ROOT, "claude", "hooks", "block-secrets.py"),
    },
}
TEMPLATE_TOML = os.path.join(ROOT, "claude", "references", "gitleaks-allowlist-template.toml")

# Comparison table rows: (case, old exit, new exit). Printed by the standalone run.
RESULTS = []


def _find_gitleaks():
    extra = [os.path.expanduser("~/.local/bin"), "/opt/homebrew/bin", "/usr/local/bin"]
    path = os.pathsep.join([os.environ.get("PATH", "")] + extra)
    return shutil.which("gitleaks", path=path)


GITLEAKS = _find_gitleaks()


def require_gitleaks():
    if not GITLEAKS:
        raise AssertionError(
            "gitleaks is not installed, so the secret-guard cases cannot run. "
            "Install it (brew install gitleaks) and re-run. This test fails "
            "rather than skips on purpose."
        )


def fake_github_token():
    alphabet = string.ascii_letters + string.digits
    return "gh" + "p_" + "".join(random.choice(alphabet) for _ in range(36))


def fake_aws_key():
    alphabet = string.ascii_uppercase + "234567"
    return "AK" + "IA" + "".join(random.choice(alphabet) for _ in range(16))


class Sandbox:
    """A throwaway HOME plus an isolated git config, so no hook or setting on
    the machine running the tests (global git hooks, a real allowlist sidecar)
    leaks into the results."""

    def __init__(self):
        self.dir = tempfile.mkdtemp(prefix="secret-hooks-")
        self.home = os.path.join(self.dir, "home")
        os.makedirs(os.path.join(self.home, ".claude", "hooks"))
        self.gitconfig = os.path.join(self.dir, "gitconfig")
        with open(self.gitconfig, "w") as f:
            f.write(
                "[user]\n\tname = Test\n\temail = test@example.com\n"
                "[init]\n\tdefaultBranch = main\n"
                "[commit]\n\tgpgsign = false\n"
                "[advice]\n\tdetachedHead = false\n"
            )
        path = os.environ.get("PATH", "")
        if GITLEAKS:
            path = os.path.dirname(GITLEAKS) + os.pathsep + path
        self.env = dict(os.environ)
        self.env.update({
            "HOME": self.home,
            "PATH": path,
            "GIT_CONFIG_GLOBAL": self.gitconfig,
            "GIT_CONFIG_NOSYSTEM": "1",
        })

    def git(self, cwd, *args):
        proc = subprocess.run(["git", *args], cwd=cwd, env=self.env,
                              capture_output=True, text=True)
        if proc.returncode != 0:
            raise AssertionError(f"git {' '.join(args)} failed: {proc.stderr}")
        return proc.stdout.strip()

    def repo(self):
        """A working clone with a local bare remote and one pushed commit on main."""
        remote = os.path.join(self.dir, "remote.git")
        work = os.path.join(self.dir, "work")
        self.git(self.dir, "init", "-q", "--bare", remote)
        self.git(self.dir, "clone", "-q", remote, work)
        self.write(work, "README.md", "demo repo\n")
        self.commit(work, "init")
        self.git(work, "push", "-q", "origin", "main")
        return work

    def write(self, work, rel, text):
        path = os.path.join(work, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text)

    def commit(self, work, msg):
        self.git(work, "add", "-A")
        self.git(work, "commit", "-q", "-m", msg)

    def cleanup(self):
        shutil.rmtree(self.dir, ignore_errors=True)


def run_hook(which, hook, payload, env):
    proc = subprocess.run([sys.executable, HOOKS[which][hook]], input=json.dumps(payload),
                          env=env, capture_output=True, text=True, timeout=120)
    return proc.returncode, proc.stderr


def _head(text):
    return " / ".join(text.strip().splitlines()[:2])


def compare(case, hook, payload, env, old, new):
    """Run old and new hook on the same payload and assert the exact exits."""
    old_code, old_err = run_hook("old", hook, payload, env)
    new_code, new_err = run_hook("new", hook, payload, env)
    RESULTS.append((case, old_code, new_code))
    assert (old_code, new_code) == (old, new), (
        f"{case}: expected old={old} new={new}, got old={old_code} new={new_code}\n"
        f"old stderr: {_head(old_err)}\nnew stderr: {_head(new_err)}"
    )
    return old_err, new_err


def bash(command, cwd):
    return {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd}


def token_line():
    return f"GITHUB_TOKEN={fake_github_token()}\n"


# ---------------------------------------------------------------- secret-guard

def test_first_push_ignores_commits_the_remote_already_has():
    require_gitleaks()
    sb = Sandbox()
    try:
        work = sb.repo()
        sb.write(work, "app.cfg", token_line())
        sb.commit(work, "old token, already on the remote")
        sb.git(work, "push", "-q", "origin", "main")
        sb.git(work, "checkout", "-q", "-b", "feat")
        sb.write(work, "page.txt", "clean change\n")
        sb.commit(work, "clean")
        compare("1 first push, token only in pushed history", "secret-guard",
                bash("git push -u origin feat", work), sb.env, old=2, new=0)
    finally:
        sb.cleanup()


def test_new_token_on_branch_blocks_both():
    require_gitleaks()
    sb = Sandbox()
    try:
        work = sb.repo()
        sb.git(work, "checkout", "-q", "-b", "feat")
        sb.write(work, "app.cfg", token_line())
        sb.commit(work, "new token")
        _, new_err = compare("2 new token on the branch", "secret-guard",
                             bash("git push -u origin feat", work), sb.env, old=2, new=2)
        assert ".gitleaks.toml" in new_err, new_err
        assert "Remove or rotate" not in new_err, new_err
    finally:
        sb.cleanup()


def test_rebase_onto_main_does_not_rescan_mains_commits():
    require_gitleaks()
    sb = Sandbox()
    try:
        work = sb.repo()
        sb.git(work, "checkout", "-q", "-b", "feat")
        sb.write(work, "page.txt", "clean change\n")
        sb.commit(work, "clean")
        sb.git(work, "push", "-q", "-u", "origin", "feat")
        sb.git(work, "checkout", "-q", "main")
        sb.write(work, "app.cfg", token_line())
        sb.commit(work, "token on main")
        sb.git(work, "push", "-q", "origin", "main")
        sb.git(work, "checkout", "-q", "feat")
        sb.git(work, "rebase", "-q", "main")
        compare("3 rebase onto main with a pushed token", "secret-guard",
                bash("git push", work), sb.env, old=2, new=0)
    finally:
        sb.cleanup()


def test_push_from_subdirectory_loads_repo_root_toml():
    require_gitleaks()
    sb = Sandbox()
    try:
        work = sb.repo()
        sb.git(work, "checkout", "-q", "-b", "feat")
        sb.write(work, ".gitleaks.toml", (
            "[extend]\nuseDefault = true\n\n"
            "[[allowlists]]\ndescription = \"fake fixture tokens\"\n"
            "paths = ['''^fixtures/''']\n"
        ))
        sb.write(work, "fixtures/fake.cfg", token_line())
        sb.write(work, "sub/page.txt", "clean\n")
        sb.commit(work, "fixture token, allowlisted at the repo root")
        compare("4 push from a subdirectory, root toml allowlist", "secret-guard",
                bash("git push -u origin feat", os.path.join(work, "sub")), sb.env, old=2, new=0)
    finally:
        sb.cleanup()


def _gitleaks_scan(sb, work):
    proc = subprocess.run(
        [GITLEAKS, "git", "--log-opts=HEAD", "--redact", "--no-banner", "--exit-code", "1"],
        cwd=work, env=sb.env, capture_output=True, text=True, timeout=120)
    return proc.returncode, proc.stdout + proc.stderr


def test_toml_without_use_default_turns_detection_off_and_template_does_not():
    require_gitleaks()
    sb = Sandbox()
    try:
        work = sb.repo()
        sb.write(work, "app.cfg", f"AWS_ACCESS_KEY_ID={fake_aws_key()}\n")
        sb.commit(work, "canary")
        code, _ = _gitleaks_scan(sb, work)
        assert code == 1, "control: gitleaks must catch the canary with no toml"
        # The trap: an allowlist-only toml replaces the default rules with none.
        with open(os.path.join(work, ".gitleaks.toml"), "w") as f:
            f.write("[[allowlists]]\npaths = ['''^fixtures/''']\n")
        code, out = _gitleaks_scan(sb, work)
        RESULTS.append(("5 toml without useDefault (gitleaks itself)", "-", code))
        assert code == 0, f"trap no longer reproduces (gitleaks exit {code}): {out}"
        # The kit's template carries the line and still catches the canary.
        assert os.path.isfile(TEMPLATE_TOML), f"missing {TEMPLATE_TOML}"
        with open(TEMPLATE_TOML) as f:
            template = f.read()
        assert "useDefault = true" in template
        shutil.copy(TEMPLATE_TOML, os.path.join(work, ".gitleaks.toml"))
        code, out = _gitleaks_scan(sb, work)
        RESULTS.append(("5 kit template toml (gitleaks itself)", "-", code))
        assert code == 1, f"template turned detection off (exit {code}): {out}"
    finally:
        sb.cleanup()


def test_malformed_toml_is_a_config_error_not_a_leak():
    require_gitleaks()
    sb = Sandbox()
    try:
        work = sb.repo()
        sb.git(work, "checkout", "-q", "-b", "feat")
        sb.write(work, ".gitleaks.toml", "[[allowlists]\npaths = [\n")
        sb.write(work, "page.txt", "clean\n")
        sb.commit(work, "broken toml")
        code, out = _gitleaks_scan(sb, work)
        assert code == 1 and "unable to load gitleaks config" in out, (code, out)
        _, new_err = compare("9 malformed .gitleaks.toml", "secret-guard",
                             bash("git push -u origin feat", work), sb.env, old=2, new=0)
        assert "config" in new_err.lower(), new_err
    finally:
        sb.cleanup()


def test_commit_and_push_in_one_command_runs_both_scans():
    require_gitleaks()
    sb = Sandbox()
    try:
        work = sb.repo()
        sb.git(work, "checkout", "-q", "-b", "feat")
        sb.write(work, "app.cfg", token_line())
        sb.commit(work, "unpushed token")
        sb.write(work, "page.txt", "clean\n")
        sb.git(work, "add", "page.txt")
        compare("G4 commit && push, token in an unpushed commit", "secret-guard",
                bash("git commit -m page && git push -u origin feat", work), sb.env, old=0, new=2)
    finally:
        sb.cleanup()


def test_staged_token_still_blocks_a_commit():
    require_gitleaks()
    sb = Sandbox()
    try:
        work = sb.repo()
        sb.write(work, "app.cfg", token_line())
        sb.git(work, "add", "app.cfg")
        compare("commit with a staged token", "secret-guard",
                bash("git commit -m cfg", work), sb.env, old=2, new=2)
    finally:
        sb.cleanup()


# --------------------------------------------------------------- block-secrets

def _file(tool, path):
    key = "file_path"
    return {"tool_name": tool, "tool_input": {key: path}}


def _block_cases(home):
    proj = os.path.join(home, "project")
    return [
        # (case, tool, path, old, new)
        ("6 Read .env", "Read", f"{proj}/.env", 2, 0),
        ("6 Read .env.local", "Read", f"{proj}/.env.local", 2, 0),
        ("7 Edit .env.production", "Edit", f"{proj}/.env.production", 2, 2),
        ("7 Write id_ed25519", "Write", f"{proj}/id_ed25519", 0, 2),
        ("7 Edit .npmrc", "Edit", f"{proj}/.npmrc", 0, 2),
        ("7 MultiEdit .env", "MultiEdit", f"{proj}/.env", 2, 2),
        ("7 Write server.pem", "Write", f"{proj}/certs/server.pem", 2, 2),
        ("7 Write credentials.json", "Write", f"{proj}/credentials.json", 2, 2),
        ("7 Write secrets.yaml", "Write", f"{proj}/config/secrets.yaml", 2, 2),
        ("7 Edit ~/.ssh/config", "Edit", f"{home}/.ssh/config", 0, 2),
        ("7 Edit ~/.aws/config", "Edit", f"{home}/.aws/config", 0, 2),
        ("8 Write src/id_card.tsx", "Write", f"{proj}/src/id_card.tsx", 0, 0),
        ("8 Edit lib/api-key-form.tsx", "Edit", f"{proj}/lib/api-key-form.tsx", 2, 0),
        ("8 Edit src/secrets-panel.tsx", "Edit", f"{proj}/src/secrets-panel.tsx", 2, 0),
        ("8 Edit docs/credentials-guide.md", "Edit", f"{proj}/docs/credentials-guide.md", 2, 0),
        ("8 Edit .env.example", "Edit", f"{proj}/.env.example", 0, 0),
        ("8 Edit allowlisted realtor_secrets.ts", "Edit", f"{proj}/src/realtor_secrets.ts", 0, 0),
        # (G2) names the exact set missed but the pre-run hook blocked
        ("G2 Edit config/prod.env", "Edit", f"{proj}/config/prod.env", 2, 2),
        ("G2 Write credentials.yml", "Write", f"{proj}/credentials.yml", 2, 2),
        ("G2 Write config/secrets.yaml", "Write", f"{proj}/config/secrets.yaml", 2, 2),
        ("G2 Edit src/realtor_secrets.ts", "Edit", f"{proj}/src/realtor_secrets.ts", 0, 0),
        ("G2 Read config/prod.env", "Read", f"{proj}/config/prod.env", 2, 0),
    ]


def test_block_secrets_reads_allowed_and_writes_exact():
    sb = Sandbox()
    try:
        with open(os.path.join(sb.home, ".claude", "hooks", "block-secrets-allow.txt"), "w") as f:
            f.write("# test sidecar\nrealtor_secrets.ts\n")
        failures = []
        for case, tool, path, old, new in _block_cases(sb.home):
            try:
                compare(case, "block-secrets", _file(tool, path), sb.env, old=old, new=new)
            except AssertionError as exc:
                failures.append(str(exc).splitlines()[0])
        assert not failures, "\n".join(failures)
    finally:
        sb.cleanup()


# (G2 sweep) ~40 realistic file names. Every one the pre-run hook blocked for
# Edit/Write must still be blocked now, except the documented allowances: source
# and doc files that only contain a word like "secrets" or "api-key" in their
# name, and the env templates. Each allowance carries its reason.
SWEEP_NAMES = [
    ".env", ".env.local", ".env.production", ".env.development.local", "prod.env",
    "config/prod.env", "staging.env", "docker/app.env", ".envrc", ".npmrc",
    "credentials", "credentials.json", "credentials.yml", "credentials.yaml",
    "credentials.toml", "aws-credentials.json", "gcp_credentials.yaml",
    "secrets.json", "secrets.yml", "config/secrets.yaml", "secrets.toml",
    "secrets.env", "app-secrets.json", "k8s/db-secrets.yaml", "prod_secrets.toml",
    "server.pem", "certs/tls.key", "master.key", "id_ed25519", "id_rsa",
    "service-account.json", "service-account-prod.json",
    ".env.example", ".env.sample", ".env.template",
    "src/realtor_secrets.ts", "lib/api-key-form.tsx", "src/secrets-panel.tsx",
    "docs/credentials-guide.md", "src/id_card.tsx", "src/app.tsx", "README.md",
    "package.json", "config/settings.yaml",
]
SWEEP_ALLOWANCES = {
    "src/realtor_secrets.ts": "source file, word in name only (also sidecar-allowlisted)",
    "lib/api-key-form.tsx": "source file, word in name only",
    "src/secrets-panel.tsx": "source file, word in name only",
    "docs/credentials-guide.md": "doc file, word in name only",
}


def test_block_secrets_sweep_keeps_every_old_block_but_the_allowances():
    sb = Sandbox()
    try:
        proj = os.path.join(sb.home, "project")
        regressions, table = [], []
        for rel in SWEEP_NAMES:
            for tool in ("Edit", "Write"):
                payload = _file(tool, f"{proj}/{rel}")
                old_code, _ = run_hook("old", "block-secrets", payload, sb.env)
                new_code, _ = run_hook("new", "block-secrets", payload, sb.env)
                table.append((tool, rel, old_code, new_code))
                if old_code == 2 and new_code != 2 and rel not in SWEEP_ALLOWANCES:
                    regressions.append(f"{tool} {rel}: old=2 new={new_code}")
        for rel in SWEEP_ALLOWANCES:
            for tool in ("Edit", "Write"):
                code, _ = run_hook("new", "block-secrets", _file(tool, f"{proj}/{rel}"), sb.env)
                assert code == 0, f"allowance {tool} {rel} now blocked ({code})"
        RESULTS.append(("G2 sweep: old-blocked names the new hook lets through",
                        "-", len(regressions)))
        assert not regressions, "\n".join(regressions)
    finally:
        sb.cleanup()


def test_block_secrets_without_tool_name_treats_it_as_a_write():
    sb = Sandbox()
    try:
        payload = {"tool_input": {"file_path": os.path.join(sb.home, "project", ".env")}}
        code, _ = run_hook("new", "block-secrets", payload, sb.env)
        assert code == 2, code
    finally:
        sb.cleanup()


# ------------------------------------------------------------------ standalone

def main():
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS {name}")
        except Exception as exc:  # noqa: BLE001 - report every failure, keep going
            failed += 1
            print(f"FAIL {name}: {exc}")
    print("\n| case | pre-run hook exit | current hook exit |\n|---|---|---|")
    for case, old, new in RESULTS:
        print(f"| {case} | {old} | {new} |")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
