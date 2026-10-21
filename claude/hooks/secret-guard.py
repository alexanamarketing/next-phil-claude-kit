#!/usr/bin/env python3
"""PreToolUse secret scan for git commit/push.

Runs gitleaks before anything leaves the machine:
  commit -> scan the STAGED diff (`gitleaks git --pre-commit --staged`)
  push   -> scan only the commits no remote has yet, on the refs the
            command actually PUSHES (`<src> --not --remotes`). Commits already
            on any remote (main's history, commits pulled in by a rebase) are
            never rescanned, so a first push or a rebased branch is judged only
            on what it actually adds.
A command that does both (`git commit ... && git push`) runs both scans.

Which refs a push sends is read from the command itself (push_scan_revs):
the command is tokenised with shlex and split on `&&`, `||`, `;`, `|` and
newlines, and every `git ... push` in it is read on its own. `<src>:<dst>`
scans <src> (a leading `+` is dropped), a bare `<branch>` after the remote
scans that branch, no refspec scans HEAD, `--all`/`--branches` scan every
local branch, `--mirror` every branch and tag, `--tags`/`--follow-tags` add
the tags, `tag <name>` scans that tag, and value flags (`-o`,
`--push-option`, `--repo`, `--receive-pack`, `--exec`) never count as refs.
A delete (`:<dst>`, `--delete`, `-d`) sends no commits and scans nothing.
Whenever the parser cannot tell what is pushed (a shell variable or `$(...)`
in a ref, a wildcard refspec, an unknown flag, unbalanced quotes, a push
hidden inside a quoted string), it scans every local branch and tag plus
HEAD against the remotes, never HEAD alone.

gitleaks runs from the repo ROOT (`git rev-parse --show-toplevel`), because
it loads `.gitleaks.toml` only from its working directory; a command run
from a subfolder would otherwise ignore the repo's allowlist.

Exit 2 (block) only when gitleaks reports findings (its exit code 1).
gitleaks also exits 1 when `.gitleaks.toml` is malformed ("unable to load
gitleaks config"); that is reported as a config error and allowed. Any other
failure (not installed, not a repo) fails OPEN with a stderr note: a broken
scanner must not brick every commit.

Findings print with --redact so the secret itself never lands in the
session transcript, which is a file on disk.

When a command runs `git -C /abs/path ...`, the target repo is parsed
out of the command rather than assumed to be the session cwd.

Adapted from k0d3x8its/dotfiles (2026-07-25). gitleaks lives in
~/.local/bin or Homebrew, which a non-interactive hook subprocess may not
inherit, so PATH is extended explicitly.
"""

import json
import os
import re
import shlex
import shutil
import subprocess
import sys

# gitleaks may be installed via pip (~/.local/bin) or Homebrew. On Apple Silicon
# Homebrew installs to /opt/homebrew/bin, on Intel Macs to /usr/local/bin; a
# non-interactive hook subprocess does not inherit an interactive shell PATH, so
# extend it explicitly or an installed gitleaks is invisible and the guard fails open.
os.environ["PATH"] = os.pathsep.join([
    os.environ.get("PATH", ""),
    os.path.expanduser("~/.local/bin"),
    "/opt/homebrew/bin",
    "/usr/local/bin",
])

COMMIT_RE = re.compile(r"\bgit\b[^|;&]*\bcommit\b")
PUSH_RE = re.compile(r"\bgit\b[^|;&]*\bpush\b")
GIT_C_RE = re.compile(r"\bgit\s+-C\s+(?:\"([^\"]+)\"|'([^']+)'|(\S+))")
CD_RE = re.compile(r"\bcd\s+(?:\"([^\"]+)\"|'([^']+)'|([^\s;|&]+))")


def resolve_repo_cwd(command, session_cwd):
    """Best-effort target-repo resolution; falls back to the session cwd."""
    git_c = GIT_C_RE.search(command)
    if git_c:
        path = next(g for g in git_c.groups() if g)
    else:
        git_pos = command.find("git")
        cds = [m for m in CD_RE.finditer(command) if m.start() < git_pos]
        if not cds:
            return session_cwd
        path = next(g for g in cds[-1].groups() if g)
    path = os.path.expanduser(os.path.expandvars(path))
    if not os.path.isabs(path):
        path = os.path.join(session_cwd or ".", path)
    return path if os.path.isdir(path) else session_cwd


def run_gitleaks(args, cwd):
    """Returns (exit_code, output). gitleaks: 0 clean, 1 leaks, else error."""
    proc = subprocess.run(
        # -v prints the finding (file, line, rule id) so the block message is
        # actionable; --redact keeps the secret value itself out of the output.
        ["gitleaks"] + args + ["-v", "--redact", "--no-banner", "--no-color", "--exit-code", "1"],
        cwd=cwd or None,
        capture_output=True,
        text=True,
        timeout=45,
    )
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def repo_root(cwd):
    """The repo's top-level folder, so gitleaks finds the root .gitleaks.toml."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd or None,
            capture_output=True,
            text=True,
        )
    except Exception:
        return cwd
    root = proc.stdout.strip()
    return root if proc.returncode == 0 and root else cwd


CONFIG_ERROR = "unable to load gitleaks config"

# What a push scan covers when the command cannot be read for sure.
BROAD_REVS = ["HEAD", "--branches", "--tags"]

SEPARATORS = {"&&", "||", ";", "|", "&", "\n", "|&", ";;", "(", ")"}
# git's own options before the subcommand that take a separate value.
GIT_GLOBAL_VALUE_OPTS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace",
                         "--super-prefix", "--config-env", "--exec-path"}
# `git push` options that take a separate value (never read as a ref).
PUSH_VALUE_OPTS = {"-o", "--push-option", "--repo", "--receive-pack", "--exec"}
# `git push` options that take no separate value and do not change what is sent.
PUSH_FLAG_OPTS = {
    "-u", "--set-upstream", "-f", "--force", "-q", "--quiet", "-v", "--verbose",
    "-n", "--dry-run", "--no-verify", "--verify", "--atomic", "--no-atomic",
    "--porcelain", "--prune", "--thin", "--no-thin", "--progress", "--no-progress",
    "--force-with-lease", "--no-force-with-lease", "--force-if-includes",
    "--no-force-if-includes", "--signed", "--no-signed", "-4", "--ipv4",
    "-6", "--ipv6", "--no-recurse-submodules", "--no-tags", "--no-follow-tags",
}
# Short flags that may be bundled (`-fu`); `o` and `d` are handled apart.
PUSH_SHORT_FLAGS = set("ufqvn46")
UNSAFE_CHARS = set("$`*?[]{}\\")


def _tokens(command):
    """shlex tokens with shell operators as their own tokens. Raises ValueError
    on unbalanced quotes."""
    lex = shlex.shlex(command.replace("\\\n", " "), posix=True,
                      punctuation_chars="();<>|&\n")
    lex.whitespace = " \t\r"
    lex.whitespace_split = True
    return list(lex)


def _segments(tokens):
    """Split tokens into simple commands; drop redirections (`2>&1`, `> f`)."""
    segments, current, skip_next = [], [], False
    for tok in tokens:
        if skip_next:
            skip_next = False
            continue
        if tok in SEPARATORS or (tok and set(tok) <= set("&|;\n()")):
            if current:
                segments.append(current)
            current = []
            continue
        if tok and set(tok) <= set("<>&"):
            # A redirection: its fd number (if any) is the previous token and
            # its target is the next one; neither is a git argument.
            if current and current[-1].isdigit():
                current.pop()
            skip_next = True
            continue
        current.append(tok)
    if current:
        segments.append(current)
    return segments


def _push_args(segment):
    """The arguments after `push` when this segment runs `git ... push`."""
    for i, tok in enumerate(segment):
        if os.path.basename(tok) != "git":
            continue
        j = i + 1
        while j < len(segment):
            arg = segment[j]
            if arg in GIT_GLOBAL_VALUE_OPTS:
                j += 2
                continue
            if arg.startswith("-"):
                j += 1
                continue
            break
        if j < len(segment) and segment[j] == "push":
            return segment[j + 1:]
        return None
    return None


def _revs_for_push(args):
    """Revisions one `git push` sends, [] for a delete-only push, or None when
    unsure."""
    positionals, extra, delete, everything = [], [], False, False
    i, opts_done = 0, False
    while i < len(args):
        arg = args[i]
        i += 1
        if opts_done or not arg.startswith("-") or arg == "-":
            positionals.append(arg)
            continue
        if arg == "--":
            opts_done = True
            continue
        name = arg.split("=", 1)[0]
        if name in PUSH_VALUE_OPTS:
            if "=" not in arg:
                i += 1
            continue
        if name in ("--all", "--branches"):
            everything = True
            continue
        if name == "--mirror":
            everything = True
            extra.append("--tags")
            continue
        if name in ("--tags", "--follow-tags"):
            extra.append("--tags")
            continue
        if name in ("--delete", "-d"):
            delete = True
            continue
        if name in PUSH_FLAG_OPTS:
            continue
        if not arg.startswith("--") and len(arg) > 2:
            # Bundled short flags (`-fu`, `-uo <value>`, `-ovalue`).
            flags = arg[1:]
            if "o" in flags:
                before, after = flags.split("o", 1)
                if not set(before) <= PUSH_SHORT_FLAGS | {"d"}:
                    return None
                delete = delete or "d" in before
                if not after:
                    i += 1
                continue
            if set(flags) <= PUSH_SHORT_FLAGS | {"d"}:
                delete = delete or "d" in flags
                continue
        return None
    refspecs = positionals[1:]
    if delete:
        return []
    revs = []
    if everything:
        revs.append("--branches")
    elif not refspecs:
        revs.append("HEAD")
    k = 0
    while k < len(refspecs):
        spec = refspecs[k]
        k += 1
        if spec == "tag":
            if k >= len(refspecs):
                return None
            spec = "refs/tags/" + refspecs[k]
            k += 1
        if spec.startswith("+"):
            spec = spec[1:]
        src = spec.split(":", 1)[0]
        if not src:
            continue  # `:<dst>` deletes <dst>; it sends no commits
        if src.startswith("-") or UNSAFE_CHARS & set(src):
            return None
        revs.append(src)
    for rev in extra:
        if rev not in revs:
            revs.append(rev)
    return revs


def push_scan_revs(command):
    """The revisions a push scan must cover for this command, scanned as
    `<revs> --not --remotes`. None means the command pushes nothing that
    needs scanning (only deletes). Anything unclear returns BROAD_REVS."""
    try:
        segments = _segments(_tokens(command))
    except ValueError:
        return list(BROAD_REVS)
    revs, found = [], False
    for segment in segments:
        args = _push_args(segment)
        if args is None:
            continue
        found = True
        pushed = _revs_for_push(args)
        if pushed is None:
            return list(BROAD_REVS)
        for rev in pushed:
            if rev not in revs:
                revs.append(rev)
    if not found:
        # The text says git ... push, but no git push could be read (it sits
        # inside quotes, bash -c, ssh ...): scan everything rather than guess.
        return list(BROAD_REVS)
    return revs or None


def _abs_dir(path, base):
    path = os.path.expanduser(os.path.expandvars(path))
    if not os.path.isabs(path):
        path = os.path.join(base or ".", path)
    return path


def _segment_git_dir(segment, base):
    """The folder a `git ...` segment runs in: each `-C <dir>` applies on top of
    the one before (as git does), starting from `base`."""
    for i, tok in enumerate(segment):
        if os.path.basename(tok) != "git":
            continue
        d, j = base, i + 1
        while j < len(segment) and segment[j].startswith("-"):
            if segment[j] == "-C" and j + 1 < len(segment):
                d = _abs_dir(segment[j + 1], d)
            if segment[j] in GIT_GLOBAL_VALUE_OPTS:
                j += 2
            else:
                j += 1
        return d
    return base


def push_scan_plan(command, session_cwd):
    """[(repo folder, revs)] for every `git push` in the command, each read in
    its OWN repo (its -C, else the last `cd` before it, else the session cwd),
    so `git -C A push && git -C B push` scans B too. revs None = a delete-only
    push. Anything the parser cannot read falls back to one broad scan in the
    best-effort repo, as before."""
    fallback = [(resolve_repo_cwd(command, session_cwd), list(BROAD_REVS))]
    try:
        segments = _segments(_tokens(command))
    except ValueError:
        return fallback
    plan, here, found = [], session_cwd, False
    for segment in segments:
        if segment and segment[0] == "cd":
            if len(segment) > 1:
                here = _abs_dir(segment[1], here)
            continue
        args = _push_args(segment)
        if args is None:
            continue
        found = True
        pushed = _revs_for_push(args)
        repo = _segment_git_dir(segment, here)
        plan.append((repo if os.path.isdir(repo) else session_cwd,
                     list(BROAD_REVS) if pushed is None else (pushed or None)))
    return plan if found else fallback


def resolve_revs(revs, cwd):
    """Each named ref as the commit id it resolves to, flags kept. A bare name
    such as `tests` is ambiguous to `git log` when a folder of that name exists,
    so the scan must never pass the name itself. Returns None when a ref does
    not resolve here."""
    out = []
    for rev in revs:
        if rev.startswith("--"):
            out.append(rev)
            continue
        proc = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", rev + "^{commit}"],
            cwd=cwd or None, capture_output=True, text=True,
        )
        sha = proc.stdout.strip()
        if proc.returncode != 0 or not sha:
            return None
        if sha not in out:
            out.append(sha)
    return out


def resolvable(revs, cwd):
    """True when every named ref resolves to a commit in the repo."""
    return resolve_revs(revs, cwd) is not None


# gitleaks prints this when the `git log` it runs wrote to stderr (an ambiguous
# or unknown revision): it then reports 0 commits scanned and exits 0.
GIT_LOG_ERROR = "stderr is not empty"


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        command = payload.get("tool_input", {}).get("command", "")
        cwd = payload.get("cwd", "")
    except Exception:
        return 0

    if not isinstance(command, str):
        return 0

    is_commit = bool(COMMIT_RE.search(command))
    is_push = bool(PUSH_RE.search(command))
    if not (is_commit or is_push):
        return 0

    cwd = repo_root(resolve_repo_cwd(command, cwd))

    if not shutil.which("gitleaks"):
        print(
            "secret-guard: gitleaks not on PATH, scan skipped (fail-open)",
            file=sys.stderr,
        )
        return 0

    scans = []
    if is_commit:
        scans.append(("commit", ["git", "--pre-commit", "--staged"], cwd))
    if is_push:
        for repo, revs in push_scan_plan(command, payload.get("cwd", "")):
            if revs is None:
                continue
            root = repo_root(repo)
            ids = resolve_revs(revs, root)
            if ids is None:
                # A ref git cannot resolve here (a typo, a remote-only name):
                # scan every local branch and tag instead of guessing.
                ids = resolve_revs([r for r in BROAD_REVS if r != "HEAD"], root) or []
                head = resolve_revs(["HEAD"], root)
                ids = (head or []) + ids
            scan = ("push", ["git", "--log-opts=" + " ".join(ids + ["--not", "--remotes"])], root)
            if scan not in scans:
                scans.append(scan)

    for action, args, cwd in scans:
        try:
            code, out = run_gitleaks(args, cwd)
        except Exception as exc:
            print(f"secret-guard: gitleaks failed to run ({exc}), scan skipped", file=sys.stderr)
            continue

        if action == "push" and GIT_LOG_ERROR in out:
            print(
                "secret-guard: the push scan could not read the commits being pushed "
                f"(git log failed), so the push is blocked rather than sent unscanned:\n{out}",
                file=sys.stderr,
            )
            return 2

        if CONFIG_ERROR in out:
            print(
                "secret-guard: this repo's .gitleaks.toml could not be read, so the "
                f"{action} scan was skipped (config error, not a leak). Fix the toml:\n{out}",
                file=sys.stderr,
            )
            continue

        if code == 1:
            print(
                f"secret-guard: gitleaks found potential secrets, {action} blocked.\n"
                f"{out}\n"
                "If the finding is a real key, take it out of the file and keep it in "
                "your keychain or a Vercel env var instead. If it is a fake test value "
                "or a harmless id (a confirmed false positive), add it to the repo's "
                ".gitleaks.toml allowlist (path plus a regex for that value) and retry. "
                "Do not repeat the secret value back to the user.",
                file=sys.stderr,
            )
            return 2

        if code != 0:
            print(f"secret-guard: gitleaks error (exit {code}), scan skipped:\n{out}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
