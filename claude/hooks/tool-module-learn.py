#!/usr/bin/env python3
"""Records-writing appender: the one call skills/sessions/orchestrate-reconcile
make to record a durable tool learning. It upserts a schema-valid RECORD into the
tool module's ```json records block through `tool_module_store`, under the module's
existing lock, so two parallel sessions cannot race and lose a write.

Phase 4.5 (2026-08-06) flipped this hook off the old prose path. Until then it
appended a dated line to the module's `## Learnings` section. After the injector
was rewritten to read the records block and IGNORE `## Learnings` (Phase 2), any
prose append landed in a section nobody reads and was wiped when Learnings was
emptied at cutover. So the prose path is RETIRED:
- The structured path (below) is the only write path. It routes a full record to
  `tool_module_store.upsert_record` (which resolves the module, validates the
  record against `tool_module_schema`, locks, upserts by id moving the prior
  revision to journal[], and rewrites atomically - one lock, one atomic write,
  shared with /toolupdate).
- The LEGACY prose call (old `<module> <prose-line>` positionals, or stdin
  `{"module","line"}`) FAILS LOUDLY (exit 2, message pointing at the structured
  path / /toolupdate) and writes NOTHING. It can never touch `## Learnings` again.

`_atomic_write` stays defined here because `tool_module_store` imports it verbatim
(one implementation of the mkstemp+fsync+os.replace+dir-fsync dance, no drift). The
lock now lives entirely in the store; this hook no longer takes its own lock.

Structured call (the only write path):
  CLI:   tool-module-learn.py --record-file REC.json [--module NAME] [--expected-revision TOKEN]
  stdin: echo '{"record": {...}, "module"?: "ghl", "expected_revision"?: "..."}' | tool-module-learn.py
The record must set every schema field (id, date, last_verified, tags, load,
severity, applicability, problem, fix, confidence, evidence, supersedes). The
module is taken from --module/`module` if given, else derived from the first tag's
namespace (`ghl/workflows` -> `ghl`); the schema separately rejects a record whose
id or tags disagree with that namespace, so it cannot file under the wrong module.

Exit: 0 ok ("ok" printed); 2 bad input / retired-legacy call / record rejected;
      3 io error; 4 stale-revision conflict (a correction landed first, nothing
      written); 5 module or records block not found; 75 lock timeout.
"""
import argparse
import json
import os
import sys
import tempfile

LEGACY_RETIRED_MSG = (
    "the prose '## Learnings' append path is RETIRED. Record a durable learning as "
    "a structured record instead: pass --record-file REC.json (or stdin "
    "{\"record\": {...}}) with every schema field set, or use /toolupdate. "
    "Nothing was written."
)


def fail(code, msg):
    sys.stderr.write(f"tool-module-learn: {msg}\n")
    sys.exit(code)


def _atomic_write(path, content):
    """Atomic replace preserving mode: mkstemp in the dir, flush+fsync, os.replace,
    fsync the dir. Imported verbatim by tool_module_store (one implementation)."""
    d = os.path.dirname(path)
    mode = os.stat(path).st_mode
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".learn-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, mode & 0o7777)
        os.replace(tmp, path)
        dfd = os.open(d, os.O_DIRECTORY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _module_for_record(record, explicit):
    """Module the record files under: explicit override, else the first tag's
    namespace. Returns (module, None) or (None, reason)."""
    if explicit:
        return explicit, None
    tags = record.get("tags") if isinstance(record, dict) else None
    if not isinstance(tags, list) or not tags:
        return None, "record.tags must be a non-empty array to route the record (or pass --module)"
    first = tags[0]
    if not isinstance(first, str) or "/" not in first:
        return None, f"first tag must be namespaced <tool>/<area> to route: {first!r}"
    return first.split("/", 1)[0], None


def _write_record(record, module, expected_revision):
    """Route + upsert a single record via the shared store. Exits the process."""
    if not isinstance(record, dict):
        fail(2, "record must be a JSON object")
    mod, rerr = _module_for_record(record, module)
    if rerr:
        fail(2, rerr)

    # Lazy import: keeps this file side-effect-free at import time (tool_module_store
    # imports THIS module for _atomic_write), and avoids pulling the store in until a
    # real write is requested.
    _here = os.path.dirname(os.path.abspath(__file__))
    if _here not in sys.path:
        sys.path.insert(0, _here)
    import tool_module_store as store  # noqa: E402

    try:
        status = store.upsert_record(mod, record, expected_revision=expected_revision)
    except store.StoreError as e:
        fail(e.code, e.msg)
    if status == "stale":
        fail(4, "stale revision; a concurrent correction landed first; nothing written")
    print("ok")
    sys.exit(0)


def main():
    ap = argparse.ArgumentParser(prog="tool-module-learn.py", add_help=True)
    ap.add_argument("legacy", nargs="*",
                    help="RETIRED old positional prose form; present args fail loudly")
    ap.add_argument("--record-file", help="JSON file holding one schema-valid record")
    ap.add_argument("--module", help="explicit target module (else derived from the record's tags)")
    ap.add_argument("--expected-revision", default=None,
                    help="optimistic-concurrency token from a prior read (updates only)")
    args = ap.parse_args()

    # RETIRED legacy prose call via CLI: any positional arg is the old
    # `<module> <learning-line>` form. Fail loudly, write nothing.
    if args.legacy:
        fail(2, LEGACY_RETIRED_MSG)

    if args.record_file is not None:
        try:
            with open(args.record_file) as f:
                record = json.load(f)
        except (OSError, ValueError) as e:
            fail(2, f"cannot read --record-file: {e}")
        _write_record(record, args.module, args.expected_revision)
        return

    # No CLI record: expect a structured JSON payload on stdin.
    if sys.stdin.isatty():
        fail(2, "no input: pass --record-file REC.json or a JSON {\"record\": {...}} on stdin")
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        fail(2, "stdin is not valid JSON and no --record-file was given")
    if not isinstance(payload, dict):
        fail(2, "stdin JSON must be an object")

    # RETIRED legacy prose call via stdin: the old shape carried a "line" string.
    if "line" in payload:
        fail(2, LEGACY_RETIRED_MSG)

    if "record" not in payload:
        fail(2, "stdin JSON must carry a \"record\" object (structured path), not a prose line")
    _write_record(payload["record"],
                  payload.get("module") or args.module,
                  payload.get("expected_revision", args.expected_revision))


if __name__ == "__main__":
    main()
