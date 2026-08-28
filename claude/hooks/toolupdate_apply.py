#!/usr/bin/env python3
"""Deterministic write-half of /toolupdate: identified facts -> records + breadcrumb.

The /toolupdate skill has two halves with a hard seam between them:

  MODEL half  - sweep the session, decide which durable, cross-account-true tool
                facts are worth keeping, and shape each into a candidate record
                (id, tags, load, severity, ...). Judgement; not reproducible.
  WRITE half  - THIS FILE. Given those candidate records plus the project's
                notes.md path, it validates each, routes it to the right module
                by tag namespace, upserts it through `tool_module_store`, and
                appends exactly ONE dated breadcrumb line to notes.md. Pure
                function of its input plan: run it twice on the same plan against
                a fresh module dir and you get the same records and the same line.

That seam is what makes /toolupdate falsifiable (build DONE #7). A fixture plan
carrying N planted facts drives this file with no model in the loop; the harness
asserts exactly N schema-valid records landed with the planted tags and exactly
one breadcrumb line appeared. `toolupdate.battery.py` is that harness.

Routing: a record's tool is the namespace of its tags (`ghl/workflows` -> `ghl`).
Every tag must share that namespace and the id must be `<tool>-` prefixed; the
schema enforces both, so a record cannot be filed under the wrong module.

Pre-Phase-5 dependency: writes go through `tool_module_store.upsert_record`, which
needs the target `<tool>.md` to already carry a ```json records block. Real modules
gain those blocks at Phase 3 migration / Phase 5 cutover, so against the LIVE tree
today every upsert returns "no records block in module" (status "no-records-block")
until then. The fixture seeds blocks, so the contract is provable now regardless.

Plan file (JSON):
  {"facts": [<candidate record>, ...],
   "notes_path": "/abs/path/to/project/notes.md",
   "date": "YYYY-MM-DD"   # optional; defaults to today}

CLI: toolupdate_apply.py --plan PLAN.json  [--dry-run]
Module dir comes from TOOL_MODULE_DIR (unset = live tree), same as the hooks.
Exit: 0 all facts written (or dry-run clean), 1 one or more facts failed,
      2 bad plan / bad input.
"""
import argparse
import datetime
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import tool_module_schema as schema        # noqa: E402
import tool_module_store as store          # noqa: E402


def derive_tool(record):
    """Tool a record files under = the namespace shared by its tags.

    Returns (tool, None) or (None, reason). The tool is read from the FIRST tag's
    namespace; the schema separately rejects the record if any tag or the id
    disagrees with that namespace, so this never mis-files a valid record.
    """
    tags = record.get("tags")
    if not isinstance(tags, list) or not tags:
        return None, "tags must be a non-empty array to route the record"
    first = tags[0]
    if not isinstance(first, str) or "/" not in first:
        return None, f"first tag must be namespaced (<tool>/<area>): {first!r}"
    return first.split("/", 1)[0], None


def apply_plan(facts, notes_path, date=None, dry_run=False):
    """Validate, route, upsert each fact, then append one breadcrumb. Pure per plan.

    Returns a summary dict:
      {"written": [id...], "failed": [{"id", "reason", "status"}...],
       "notes_line": str|None, "notes_written": bool}
    A fact fails (never a hard raise) on a routing miss, a schema rejection, a
    stale-revision conflict, or a missing records block; failures never abort the
    other facts. The breadcrumb is appended once iff >=1 record was written and
    this is not a dry run.
    """
    if date is None:
        date = datetime.date.today().isoformat()
    written, failed = [], []

    for rec in facts:
        rid = rec.get("id") if isinstance(rec, dict) else None
        tool, rerr = derive_tool(rec) if isinstance(rec, dict) else (None, "record is not an object")
        if rerr:
            failed.append({"id": rid, "reason": rerr, "status": "route-error"})
            continue
        verr = schema.validate_record(rec, tool=tool)
        if verr:
            failed.append({"id": rid, "reason": verr, "status": "invalid"})
            continue
        if dry_run:
            written.append(rid)
            continue
        try:
            status = store.upsert_record(tool, rec, expected_revision=None)
        except store.StoreError as e:
            st = "no-records-block" if e.code == 5 else "store-error"
            failed.append({"id": rid, "reason": e.msg, "status": st})
            continue
        if status == "ok":
            written.append(rid)
        else:  # "stale" - a concurrent correction landed first
            failed.append({"id": rid, "reason": "stale revision", "status": "stale"})

    notes_line = None
    notes_written = False
    if written and not dry_run:
        ids = ", ".join(i for i in written if i)
        notes_line = f"- {date} /toolupdate: wrote {len(written)} tool-knowledge record(s): {ids}"
        _append_line(notes_path, notes_line)
        notes_written = True

    return {"written": written, "failed": failed,
            "notes_line": notes_line, "notes_written": notes_written}


def _append_line(path, line):
    """Append exactly one line, guaranteeing it starts on its own line."""
    sep = ""
    if os.path.exists(path) and os.path.getsize(path) > 0:
        with open(path, "rb") as f:
            f.seek(-1, os.SEEK_END)
            if f.read(1) != b"\n":
                sep = "\n"
    with open(path, "a") as f:
        f.write(sep + line + "\n")


def _main(argv):
    ap = argparse.ArgumentParser(prog="toolupdate_apply.py")
    ap.add_argument("--plan", required=True, help="JSON plan: {facts, notes_path, date?}")
    ap.add_argument("--dry-run", action="store_true",
                    help="validate + route only; write no records and no breadcrumb")
    args = ap.parse_args(argv)

    try:
        with open(args.plan) as f:
            plan = json.load(f)
    except (OSError, ValueError) as e:
        sys.stderr.write(f"toolupdate: cannot read plan: {e}\n")
        return 2
    facts = plan.get("facts")
    notes_path = plan.get("notes_path")
    if not isinstance(facts, list) or not facts:
        sys.stderr.write("toolupdate: plan.facts must be a non-empty array\n")
        return 2
    if not args.dry_run and not (isinstance(notes_path, str) and notes_path):
        sys.stderr.write("toolupdate: plan.notes_path is required (non-dry-run)\n")
        return 2

    result = apply_plan(facts, notes_path, date=plan.get("date"), dry_run=args.dry_run)
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if not result["failed"] else 1


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
