#!/usr/bin/env python3
"""DONE 3 write-through proof: the self-learning path actually works end to end.

Builds a mock realtor record (tag flexmls/search), pushes it through
tool_module_store.upsert_record against a temp module dir, and asserts it
validates, persists, and reads back from the module file. Then asserts a record
carrying a tag OUTSIDE the locked glossary is rejected loudly (StoreError, exit
code 2), never silently dropped into success.

Run: python3 tests/test_tool_module_store.py   (exit 0 = pass)
"""
import importlib.util
import json
import os
import sys
import tempfile

HOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "claude", "hooks")


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HOOKS, filename))
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


EMPTY_BLOCK = (
    "# flexmls - Tool Module\n\n"
    "## Records (canonical, machine-read)\n\n"
    "```json\n"
    '{"schema_version": 1, "active": [], "journal": []}\n'
    "```\n"
)


def valid_record():
    return {
        "id": "flexmls-saved-search-radius",
        "date": "2026-08-28",
        "last_verified": "2026-08-28",
        "tags": ["flexmls/search"],
        "load": "scoped",
        "severity": "normal",
        "applicability": "global",
        "problem": "A saved FlexMLS search keeps its old radius even after you move the map.",
        "fix": "Re-set the radius in the filter panel and re-save; moving the map pin alone does not stick.",
        "confidence": "confirmed",
        "evidence": [],
        "supersedes": [],
    }


def main():
    tmp = tempfile.mkdtemp(prefix="tms-test-")
    os.environ["TOOL_MODULE_DIR"] = tmp
    with open(os.path.join(tmp, "flexmls.md"), "w") as f:
        f.write(EMPTY_BLOCK)

    # Import AFTER setting TOOL_MODULE_DIR so schema + store read the temp dir.
    _load("tool_module_schema", "tool_module_schema.py")
    store = _load("tool_module_store", "tool_module_store.py")

    # --- 1. valid record validates, persists, reads back -------------------
    status = store.upsert_record("flexmls", valid_record())
    assert status == "ok", f"expected 'ok', got {status!r}"

    text = open(os.path.join(tmp, "flexmls.md")).read()
    parsed = store.parse_records(text)
    assert parsed is not None, "records block vanished from the module file"
    obj, _, _ = parsed
    ids = [r.get("id") for r in obj["active"]]
    assert ids == ["flexmls-saved-search-radius"], f"record did not persist: {ids}"
    read_back = obj["active"][0]
    assert read_back["problem"].startswith("A saved FlexMLS search"), "record content wrong on read-back"
    assert read_back["tags"] == ["flexmls/search"], "record tags wrong on read-back"
    print("PASS: valid flexmls/search record validated, persisted, read back")

    # --- 2. unknown-tag record is rejected LOUDLY (not silently dropped) ----
    bad = valid_record()
    bad["id"] = "flexmls-bad-tag"
    bad["tags"] = ["flexmls/not-a-real-area"]   # namespace ok, tag NOT in glossary
    rejected = False
    try:
        store.upsert_record("flexmls", bad)
    except store.StoreError as e:
        rejected = True
        assert e.code == 2, f"expected validation code 2, got {e.code}"
        assert "glossary" in e.msg.lower(), f"expected a glossary rejection, got: {e.msg}"
    assert rejected, "unknown-tag record was NOT rejected (silent success = self-learning is broken)"

    # And prove it did not land: still exactly one active record.
    text2 = open(os.path.join(tmp, "flexmls.md")).read()
    obj2, _, _ = store.parse_records(text2)
    assert [r.get("id") for r in obj2["active"]] == ["flexmls-saved-search-radius"], \
        "a rejected record leaked into the store"
    print("PASS: unknown-tag record rejected loudly, nothing leaked")

    print("ALL WRITE-THROUGH ASSERTIONS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
