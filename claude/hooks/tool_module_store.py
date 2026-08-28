#!/usr/bin/env python3
"""Single-file record store for the tool-knowledge system (design decision B).

Each tool is ONE file `<tool>.md`: human prose PLUS a fenced ```json block
`{schema_version, active[], journal[]}`. This module reads that block, validates
against `tool_module_schema`, upserts a record by id under the module's existing
lock, moves the superseded revision(s) to `journal[]`, re-serializes, and rewrites
the file atomically - leaving every byte OUTSIDE the fenced block untouched.

Concurrency machinery is REUSED from the appender unchanged, per the build plan:
- `_atomic_write` (mkstemp in the module dir + flush + fsync + os.replace + dir
  fsync) is imported directly from `tool-module-learn.py`, so there is one copy.
- The lock is the same permanent `.locks/<module>.lock` acquired with a BLOCKING
  `fcntl.flock` under a `SIGALRM` deadline (exit/raise on timeout, never an
  unlocked write). `module_lock()` below is a faithful structural copy of the
  appender's inline block (it cannot be a plain function around a critical
  section); Phase 5 unifies the two when the appender flips to the records path.

Upsert is optimistic-concurrency safe: the caller reads a record, computes its
`revision_token`, and passes it as `expected_revision`; if the on-disk record has
changed (a concurrent correction landed first), the write is REJECTED as stale
(status "stale", CLI exit 4) instead of silently overwriting it (lost update).

CLI: tool_module_store.py upsert <module> --record-file F [--expected-revision T]
     tool_module_store.py token <module> <id>          (print a record's token)
Exit: 0 ok, 2 bad input/validation, 4 stale-revision conflict, 75 lock timeout,
      3 io error, 5 record/module not found.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import signal
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import tool_module_schema as schema  # noqa: E402

# Reuse the appender's atomic write verbatim (one implementation, no drift).
_LEARN_PATH = os.path.join(_HERE, "tool-module-learn.py")
_spec = importlib.util.spec_from_file_location("_tool_module_learn", _LEARN_PATH)
_learn = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_learn)
_atomic_write = _learn._atomic_write

MODULE_DIR = os.environ.get("TOOL_MODULE_DIR") or os.path.expanduser("~/.claude/references/tool-modules")
LOCK_DIR = os.path.join(MODULE_DIR, ".locks")
MODULE_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
LOCK_TIMEOUT_S = 10.0

# The records block: a fenced ```json ... ``` whose parsed value is a dict with an
# "active" key. Non-greedy, captures the inner text span so we can rewrite ONLY it.
_FENCE_RE = re.compile(r"```json[ \t]*\n(.*?)\n```", re.DOTALL)


class StoreError(Exception):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code
        self.msg = msg


def resolve_module(name):
    """Existing regular non-symlink <name>.md directly under MODULE_DIR, else raise."""
    if not MODULE_NAME_RE.match(name or ""):
        raise StoreError(2, "invalid module name")
    path = os.path.join(MODULE_DIR, f"{name}.md")
    real = os.path.realpath(path)
    if os.path.dirname(real) != os.path.realpath(MODULE_DIR):
        raise StoreError(2, "module path escapes the module dir")
    if os.path.islink(path) or not os.path.isfile(path):
        raise StoreError(5, "module file missing or not a regular file")
    return path


def parse_records(text):
    """Locate the records block. Return (obj, content_start, content_end) or None.

    content_start/content_end bound the INNER json text (between the ```json line
    and the closing ```), so a rewrite replaces exactly that span and nothing else.
    """
    for m in _FENCE_RE.finditer(text):
        inner = m.group(1)
        try:
            obj = json.loads(inner)
        except ValueError:
            continue
        if isinstance(obj, dict) and "active" in obj:
            return obj, m.start(1), m.end(1)
    return None


def serialize_block(obj):
    """Canonical block text (no surrounding newlines; the fence lines are kept)."""
    return json.dumps(obj, indent=2, ensure_ascii=False)


def revision_token(record):
    """Stable content hash of a record; the optimistic-concurrency version token."""
    canon = json.dumps(record, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:16]


def apply_upsert(obj, new_record, expected_revision=None):
    """In-memory upsert. Returns "ok" or "stale". Mutates obj.

    - Locate the active record with the same id. If found and expected_revision is
      given, its current token must match, else "stale".
    - The prior revision (the record being replaced) moves to journal[].
    - Any OTHER active record whose id appears in new_record.supersedes[] moves to
      journal[] (enforces: no active id sits in any active supersedes[]).
    """
    active = obj["active"]
    journal = obj["journal"]
    idx = next((i for i, r in enumerate(active) if r.get("id") == new_record["id"]), None)

    if expected_revision is not None:
        if idx is None:
            return "stale"  # caller meant to update a record that is no longer active
        if revision_token(active[idx]) != expected_revision:
            return "stale"

    if idx is not None:
        journal.append(active[idx])      # archive the prior revision
        active[idx] = new_record
    else:
        active.append(new_record)

    sup = {s for s in new_record.get("supersedes", []) if s != new_record["id"]}
    if sup:
        keep = []
        for r in active:
            if r.get("id") != new_record["id"] and r.get("id") in sup:
                journal.append(r)
            else:
                keep.append(r)
        obj["active"] = keep
    return "ok"


class _LockTimeout(Exception):
    pass


class module_lock:
    """Faithful copy of the appender's flock+SIGALRM lock. Raises StoreError(75)
    on timeout without ever entering the critical section."""

    def __init__(self, module):
        self.module = module
        self.lfd = None
        self.acquired = False
        self._prev = None

    def __enter__(self):
        os.makedirs(LOCK_DIR, mode=0o700, exist_ok=True)
        lock_path = os.path.join(LOCK_DIR, f"{self.module}.lock")
        self.lfd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)

        def _on_alarm(signum, frame):
            raise _LockTimeout()

        self._prev = signal.signal(signal.SIGALRM, _on_alarm)
        signal.setitimer(signal.ITIMER_REAL, LOCK_TIMEOUT_S)
        try:
            try:
                fcntl.flock(self.lfd, fcntl.LOCK_EX)
                self.acquired = True
            except _LockTimeout:
                raise StoreError(75, "lock timeout; nothing written")
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
                signal.signal(signal.SIGALRM, self._prev)
        except StoreError:
            os.close(self.lfd)
            self.lfd = None
            raise
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.acquired:
            try:
                fcntl.flock(self.lfd, fcntl.LOCK_UN)
            except OSError:
                pass
        if self.lfd is not None:
            os.close(self.lfd)
        return False


def upsert_record(module, new_record, expected_revision=None):
    """Locked read -> validate -> upsert -> atomic rewrite. Returns "ok"/"stale".

    Raises StoreError(code, msg) for: bad module (2/5), invalid record (2),
    no records block (5), malformed on-disk block (3), lock timeout (75).
    """
    path = resolve_module(module)
    verr = schema.validate_record(new_record, tool=module)
    if verr:
        raise StoreError(2, verr)
    with module_lock(module):
        try:
            with open(path) as f:
                text = f.read()
        except OSError as e:
            raise StoreError(3, f"io error: {e}")
        parsed = parse_records(text)
        if parsed is None:
            raise StoreError(5, "no records block in module")
        obj, cs, ce = parsed
        berr = schema.validate_block(obj)
        if berr:
            raise StoreError(3, f"on-disk records block invalid: {berr}")
        status = apply_upsert(obj, new_record, expected_revision)
        if status == "stale":
            return "stale"
        new_text = text[:cs] + serialize_block(obj) + text[ce:]
        try:
            _atomic_write(path, new_text)
        except OSError as e:
            raise StoreError(3, f"io error: {e}")
        return "ok"


def _main(argv):
    ap = argparse.ArgumentParser(prog="tool_module_store.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    up = sub.add_parser("upsert")
    up.add_argument("module")
    up.add_argument("--record-file", required=True)
    up.add_argument("--expected-revision", default=None)
    tk = sub.add_parser("token")
    tk.add_argument("module")
    tk.add_argument("id")
    args = ap.parse_args(argv)

    try:
        if args.cmd == "upsert":
            try:
                with open(args.record_file) as f:
                    rec = json.load(f)
            except (OSError, ValueError) as e:
                raise StoreError(2, f"cannot read record file: {e}")
            status = upsert_record(args.module, rec, args.expected_revision)
            if status == "stale":
                sys.stderr.write("stale revision; nothing written\n")
                return 4
            print("ok")
            return 0
        if args.cmd == "token":
            path = resolve_module(args.module)
            with open(path) as f:
                parsed = parse_records(f.read())
            if parsed is None:
                raise StoreError(5, "no records block in module")
            obj, _, _ = parsed
            rec = next((r for r in obj["active"] if r.get("id") == args.id), None)
            if rec is None:
                raise StoreError(5, f"no active record with id {args.id!r}")
            print(revision_token(rec))
            return 0
    except StoreError as e:
        sys.stderr.write(f"tool-module-store: {e.msg}\n")
        return e.code
    return 2


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
