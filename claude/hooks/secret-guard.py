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

Exit 2 (block) when gitleaks reports findings (its exit code 1), and when
a push scan's own `git log` failed (gitleaks prints "stderr is not empty",
scans 0 commits and exits 0, which would let the push out unscanned). Each
push is scanned in its own repo, by the commit ids it sends, so a branch
named like a folder (`tests`) is never an ambiguous name to git log.
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


# Words that can sit in front of a command without changing which command it
# is (`if cd B; then`, `{ cd B; }`, `builtin cd B`), and NAME=value prefixes.
PREFIX_WORDS = {"if", "then", "else", "elif", "do", "while", "until", "{", "}",
                "!", "builtin", "command", "time", "nohup", "exec", "env"}
ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


def _scoped_segments(tokens):
    """Like _segments, but keeps subshell scope: returns ("seg", tokens),
    ("open",) and ("close",) items in order, so a `cd` inside `( ... )` ends
    with the subshell."""
    items, current, skip_next = [], [], False

    def flush():
        if current:
            items.append(("seg", list(current)))
            current.clear()

    for tok in tokens:
        if skip_next:
            skip_next = False
            continue
        if tok in ("<(", ">("):
            # Process substitution: its `)` closes this, not the enclosing
            # subshell.
            flush()
            items.append(("open",))
            continue
        if tok and set(tok) <= set("<>&") and ("<" in tok or ">" in tok):
            if current and current[-1].isdigit():
                current.pop()
            skip_next = True
            continue
        if tok in SEPARATORS or (tok and set(tok) <= set("&|;\n()")):
            flush()
            for ch in tok:
                if ch == "(":
                    items.append(("open",))
                elif ch == ")":
                    items.append(("close",))
            continue
        current.append(tok)
    flush()
    return items


def _needs_shell(path):
    """True when a path still holds $ or a backtick after expanding the
    variables this process can see: only the shell can tell where it points."""
    p = os.path.expandvars(path)
    return "$" in p or "`" in p


def _dir_arg(args):
    """The folder argument of cd/pushd (flags skipped), or None."""
    for a in args:
        if a.startswith("-") or a.startswith("+"):
            continue
        return a
    return None


def _segment_git_dir(segment, base, env=None):
    """The work tree a `git ...` segment acts on: each `-C <dir>` applies on top
    of the one before (as git does), starting from `base`; `--work-tree` /
    GIT_WORK_TREE win, else `--git-dir` / GIT_DIR (its parent when it ends in
    .git)."""
    env = env or {}
    for i, tok in enumerate(segment):
        if os.path.basename(tok) != "git":
            continue
        d, j = base, i + 1
        git_dir, work_tree = env.get("GIT_DIR"), env.get("GIT_WORK_TREE")
        while j < len(segment) and segment[j].startswith("-"):
            arg = segment[j]
            nxt = segment[j + 1] if j + 1 < len(segment) else None
            if arg == "-C" and nxt is not None:
                d = _abs_dir(nxt, d)
            elif arg.startswith("--git-dir="):
                git_dir = arg.split("=", 1)[1]
            elif arg == "--git-dir" and nxt is not None:
                git_dir = nxt
            elif arg.startswith("--work-tree="):
                work_tree = arg.split("=", 1)[1]
            elif arg == "--work-tree" and nxt is not None:
                work_tree = nxt
            j += 2 if arg in GIT_GLOBAL_VALUE_OPTS else 1
        if any(v is not None and _needs_shell(v) for v in (git_dir, work_tree)) or _needs_shell(d):
            return None
        if work_tree:
            return _abs_dir(work_tree, d)
        if git_dir:
            g = _abs_dir(git_dir, d).rstrip("/")
            return os.path.dirname(g) if os.path.basename(g) == ".git" else g
        return d
    return base


def push_scan_plan(command, session_cwd, backups=None):
    """[(repo folder, revs)] for every `git push` in the command, each read in
    its OWN repo: its -C / --git-dir / --work-tree / GIT_DIR=, else the folder
    the shell is in by then (cd and pushd/popd, also behind if/then/{/builtin/
    command, with a subshell's cd ending at its `)`), else the session cwd.
    revs None = a delete-only push. Anything the parser cannot read falls back
    to one broad scan in the best-effort repo, as before. main() also always
    scans the repo the older single-repo rule picks, so this plan can only add
    repos to the scan, never drop that one.

    A repo of None means the push names its repo through a value only the
    shell can expand (`git -C "$X"`, `GIT_DIR=$d`): main() blocks it. When
    the scope tracking cannot be trusted (a `)` with no open scope, or a
    `case`), every folder the shell has been in, plus the session cwd, is
    added to `backups` as (folder, revs) for each later push."""
    fallback = [(resolve_repo_cwd(command, session_cwd), list(BROAD_REVS))]
    try:
        items = _scoped_segments(_tokens(command))
    except ValueError:
        return fallback
    plan, here, found = [], session_cwd, False
    scopes, dirstack, previous = [], [], None
    visited = [session_cwd]
    untrusted = any(item[0] == "seg" and "case" in item[1] for item in items)
    for item in items:
        if item[0] == "open":
            scopes.append((here, list(dirstack)))
            continue
        if item[0] == "close":
            if scopes:
                here, dirstack = scopes.pop()
            else:
                untrusted = True
            continue
        segment, env, k = item[1], {}, 0
        while k < len(segment) and (segment[k] in PREFIX_WORDS or ASSIGN_RE.match(segment[k])):
            if ASSIGN_RE.match(segment[k]):
                name, value = segment[k].split("=", 1)
                env[name] = value
            k += 1
        segment = segment[k:]
        if not segment:
            continue
        head = segment[0]
        if head == "cd":
            target = "-" if segment[1:] == ["-"] else _dir_arg(segment[1:])
            if target == "-":
                if previous is not None:
                    here, previous = previous, here
            elif target:
                previous, here = here, _abs_dir(target, here)
                visited.append(here)
            continue
        if head == "pushd":
            target = _dir_arg(segment[1:])
            if target:
                dirstack.append(here)
                here = _abs_dir(target, here)
                visited.append(here)
            continue
        if head == "popd":
            if dirstack:
                here = dirstack.pop()
            continue
        args = _push_args(segment)
        if args is None:
            continue
        found = True
        pushed = _revs_for_push(args)
        repo = _segment_git_dir(segment, here, env)
        revs = list(BROAD_REVS) if pushed is None else (pushed or None)
        if repo is not None and not os.path.isdir(repo):
            repo = session_cwd
        plan.append((repo, revs))
        if untrusted and backups is not None and revs is not None:
            for folder in visited:
                if (folder, revs) not in backups:
                    backups.append((folder, revs))
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


def is_repo(folder):
    """True when `folder` is inside a git repo (work tree or bare)."""
    if not folder or not os.path.isdir(folder):
        return False
    proc = subprocess.run(["git", "rev-parse", "--git-dir"], cwd=folder,
                          capture_output=True, text=True)
    return proc.returncode == 0


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
        backups = []
        plan = push_scan_plan(command, payload.get("cwd", ""), backups)
        if any(repo is None and revs is not None for repo, revs in plan):
            print(
                "secret-guard: cannot tell which repo this push runs in (its -C, "
                "--git-dir, --work-tree or GIT_DIR value needs the shell to expand), "
                "so it is blocked rather than scanned in the wrong repo. Run it as "
                "`git -C /absolute/path/to/repo push ...`.",
                file=sys.stderr,
            )
            return 2
        entries = [(repo, revs, True) for repo, revs in plan]
        if any(revs is not None for _, revs in plan):
            # Safety net: also scan the repo the older single-repo rule picks
            # (the first -C, else the last cd before git, else the session
            # cwd), plus every folder an untrusted scope may have left the
            # shell in. Backups run only in a real repo and only for refs that
            # resolve there, never as a broad scan, so they cannot block a
            # clean push from a plain folder.
            legacy = push_scan_revs(command)
            if legacy is not None and cwd not in {repo_root(r) for r, _ in plan}:
                entries.append((cwd, legacy, False))
            entries += [(folder, revs, False) for folder, revs in backups]
        for repo, revs, primary in entries:
            if revs is None:
                continue
            if not primary and not is_repo(repo):
                continue
            root = repo_root(repo)
            ids = resolve_revs(revs, root)
            if ids is None and not primary:
                continue
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
                f"(git log failed in {cwd}), so the push is blocked rather than sent unscanned:\n{out}\n"
                f"Run `git log {args[1][len('--log-opts='):]}` in {cwd} to see git's error, fix it "
                "(often a broken ref under .git/refs or an old .git/info/grafts file), then push again.",
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
