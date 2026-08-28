#!/usr/bin/env python3
"""Shared schema + tag-glossary validation for the tool-knowledge system.

Imported by BOTH hooks (the injector `tool-module-brief.py` and the appender
`tool-module-learn.py`) and by the record store `tool_module_store.py`, so there
is ONE definition of a valid record and ONE glossary. Design of record:
`tool-knowledge-redesign-design-v1.md` sections 3 (record schema) and 4 (glossary).

Two things this module owns:
1. `validate_record(record, tool=None)` - returns None if the record is a valid
   `active[]`/`journal[]` entry, else a human-readable reason string. Rejects, on
   NEW writes: a non-glossary tag, a malformed record, evidence that is not an
   array of {type, ref} objects, and a problem/fix over the length cap (design
   pre-build gate: a paragraph-stuffed record must not pass as one migrated fact).
2. The tag glossary. Seeded from design section 4 (LOCKED loadable tool-area
   tags + the seeded-but-unused ones). NOT locked: `extend_glossary(tag, reason)`
   adds a namespaced tag during migration and writes a one-line log per addition,
   so a new tool area can be resolved at runtime (`flexmls/photos`, `canva/export`,
   a `gohighlevel/*` rule, etc.) without editing this file.

Import-time side effects: only reads the optional glossary-extension file. No I/O
beyond that; safe to import from a PreToolUse hook.
"""
import datetime
import json
import os
import re

# TOOL_MODULE_DIR override (test-only) mirrors the hooks; used only to locate the
# glossary-extension sidecar so a test temp dir gets its own extension state.
MODULE_DIR = os.environ.get("TOOL_MODULE_DIR") or os.path.expanduser("~/.claude/references/tool-modules")
GLOSSARY_EXT_JSON = os.path.join(MODULE_DIR, ".glossary-ext.json")
GLOSSARY_EXT_LOG = os.path.join(MODULE_DIR, ".glossary-ext.log")

SCHEMA_VERSION = 1

# --- controlled value sets (design section 3) ---
LOAD_VALUES = {"always", "scoped"}
SEVERITY_VALUES = {"critical", "high", "normal"}
APPLICABILITY_VALUES = {"global", "machine"}          # D4: plan-specific removed
CONFIDENCE_VALUES = {"confirmed", "inferred", "unverified"}
EVIDENCE_TYPES = {"file", "url", "help-article", "observation"}

REQUIRED_KEYS = {
    "id", "date", "last_verified", "tags", "load", "severity",
    "applicability", "problem", "fix", "confidence", "evidence", "supersedes",
}

# Per-record length caps. A single migrated fact is one sentence of problem and
# one of fix; the caps force a paragraph-stuffed entry to be SPLIT into one-fact
# records, not crammed into a single record.
# Chosen 2026-08-06: a real one-sentence fact runs ~160-235 chars, so 300 clears
# it with headroom while still forcing a multi-fact paragraph (1000+ chars) to
# split. Confirmed it does not force over-splitting of any genuine one-fact entry.
PROBLEM_MAX = 300
FIX_MAX = 300

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")                       # id / supersedes id
NS_TAG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*(?:/[a-z0-9][a-z0-9-]*)+$")  # namespaced tag
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Loadable tool-area tags, LOCKED to the realtor's 5 seed tools. Every record the
# self-learning path (/toolupdate, tool-module-learn.py) writes must carry a tag
# from this set, else the store rejects it. New tags are still learnable at runtime
# via extend_glossary (the .glossary-ext.json sidecar), e.g. tool-module-new.py
# seeds "<tool>/api" when a new module is scaffolded. Namespaces here MUST match the
# module filenames in references/tool-modules/ (gmail.md, flexmls.md, ...).
GLOSSARY_SEED = frozenset({
    # Gmail (email)
    "gmail/compose", "gmail/filters", "gmail/contacts", "gmail/labels", "gmail/api",
    # Google Docs / Drive (documents and files)
    "google-docs-drive/docs", "google-docs-drive/sheets", "google-docs-drive/drive",
    "google-docs-drive/sharing", "google-docs-drive/api",
    # FlexMLS (the MLS listing portal)
    "flexmls/search", "flexmls/listings", "flexmls/export", "flexmls/photos", "flexmls/api",
    # GoHighLevel (the CRM)
    "gohighlevel/contacts", "gohighlevel/workflows", "gohighlevel/pipelines",
    "gohighlevel/calendars", "gohighlevel/api",
    # Canva (design)
    "canva/design", "canva/brand-kit", "canva/export", "canva/templates", "canva/api",
})


def _load_ext():
    try:
        with open(GLOSSARY_EXT_JSON) as f:
            data = json.load(f)
        return {t for t in data if isinstance(t, str)}
    except (OSError, ValueError):
        return set()


# In-memory known set = seed + persisted extensions. Mutated by extend_glossary.
_KNOWN = set(GLOSSARY_SEED) | _load_ext()


def known_tags():
    return frozenset(_KNOWN)


def extend_glossary(tag, reason):
    """Add a namespaced tag to the glossary during migration, logging one line.

    Returns True if newly added, False if already known (idempotent no-op, no
    duplicate log line). Raises ValueError on a badly shaped tag.
    """
    if not isinstance(tag, str) or not NS_TAG_RE.match(tag):
        raise ValueError(f"glossary tag must be namespaced (<area>/<sub>): {tag!r}")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("extend_glossary requires a non-empty reason")
    if tag in _KNOWN:
        return False
    _KNOWN.add(tag)
    ext = sorted(_load_ext() | {tag})
    os.makedirs(MODULE_DIR, exist_ok=True)
    with open(GLOSSARY_EXT_JSON, "w") as f:
        json.dump(ext, f, indent=2)
        f.write("\n")
    today = datetime.date.today().isoformat()
    with open(GLOSSARY_EXT_LOG, "a") as f:
        f.write(f"{today} {tag} - {reason.strip()}\n")
    return True


def _valid_date(v):
    if not isinstance(v, str) or not DATE_RE.match(v):
        return False
    try:
        datetime.date.fromisoformat(v)
        return True
    except ValueError:
        return False


def _clean_one_liner(v):
    """True if v is a non-empty single-line string with no control chars."""
    if not isinstance(v, str) or not v.strip():
        return False
    if "\n" in v or "\r" in v:
        return False
    return not any(ord(c) < 32 for c in v)


def validate_record(record, tool=None):
    """None if `record` is a valid record, else a reason string.

    `tool`, when given, additionally requires the id to be prefixed `<tool>-`
    (the "stable tool-prefixed slug" of design section 3) and every tag to sit in
    that tool's namespace, so a record cannot land in the wrong module's file.
    """
    if not isinstance(record, dict):
        return "record is not an object"
    keys = set(record.keys())
    missing = REQUIRED_KEYS - keys
    if missing:
        return f"missing required field(s): {', '.join(sorted(missing))}"
    extra = keys - REQUIRED_KEYS
    if extra:
        return f"unexpected field(s): {', '.join(sorted(extra))}"

    # id
    rid = record["id"]
    if not isinstance(rid, str) or not SLUG_RE.match(rid):
        return f"id must be a lowercase slug: {rid!r}"
    if tool is not None and not rid.startswith(f"{tool}-"):
        return f"id must be tool-prefixed '{tool}-': {rid!r}"

    # dates
    if not _valid_date(record["date"]):
        return f"date must be YYYY-MM-DD: {record['date']!r}"
    lv = record["last_verified"]
    if lv is not None and not _valid_date(lv):
        return f"last_verified must be null or YYYY-MM-DD: {lv!r}"

    # tags
    tags = record["tags"]
    if not isinstance(tags, list) or not tags:
        return "tags must be a non-empty array"
    known = known_tags()
    for t in tags:
        if not isinstance(t, str):
            return f"tag is not a string: {t!r}"
        if t not in known:
            return f"tag not in glossary: {t!r}"
        if tool is not None and t.split("/", 1)[0] != tool:
            return f"tag {t!r} not in the {tool!r} namespace"

    # enums
    if record["load"] not in LOAD_VALUES:
        return f"load must be one of {sorted(LOAD_VALUES)}: {record['load']!r}"
    if record["severity"] not in SEVERITY_VALUES:
        return f"severity must be one of {sorted(SEVERITY_VALUES)}: {record['severity']!r}"
    if record["applicability"] not in APPLICABILITY_VALUES:
        if record["applicability"] == "plan-specific":
            return "applicability 'plan-specific' is removed (D4); keep account state in project docs"
        return f"applicability must be one of {sorted(APPLICABILITY_VALUES)}: {record['applicability']!r}"
    if record["confidence"] not in CONFIDENCE_VALUES:
        return f"confidence must be one of {sorted(CONFIDENCE_VALUES)}: {record['confidence']!r}"

    # problem / fix
    if not _clean_one_liner(record["problem"]):
        return "problem must be a non-empty single-line string"
    if len(record["problem"]) > PROBLEM_MAX:
        return f"problem over {PROBLEM_MAX} chars ({len(record['problem'])}); split into one-fact records"
    if not _clean_one_liner(record["fix"]):
        return "fix must be a non-empty single-line string"
    if len(record["fix"]) > FIX_MAX:
        return f"fix over {FIX_MAX} chars ({len(record['fix'])}); split into one-fact records"

    # evidence: array of {type, ref}; empty array allowed, bare strings rejected
    ev = record["evidence"]
    if not isinstance(ev, list):
        return "evidence must be an array"
    for item in ev:
        if not isinstance(item, dict):
            return f"evidence item must be a {{type, ref}} object, got {item!r}"
        if set(item.keys()) != {"type", "ref"}:
            return f"evidence item must have exactly keys type, ref: {sorted(item.keys())}"
        if item["type"] not in EVIDENCE_TYPES:
            return f"evidence type must be one of {sorted(EVIDENCE_TYPES)}: {item['type']!r}"
        if not isinstance(item["ref"], str) or not item["ref"].strip():
            return "evidence ref must be a non-empty string"

    # supersedes
    sup = record["supersedes"]
    if not isinstance(sup, list):
        return "supersedes must be an array"
    for s in sup:
        if not isinstance(s, str) or not SLUG_RE.match(s):
            return f"supersedes id must be a lowercase slug: {s!r}"
        if s == rid:
            return "a record cannot supersede itself"
    return None


def validate_block(obj):
    """None if `obj` is a valid records block {schema_version, active, journal}."""
    if not isinstance(obj, dict):
        return "records block is not an object"
    if obj.get("schema_version") != SCHEMA_VERSION:
        return f"schema_version must be {SCHEMA_VERSION}: {obj.get('schema_version')!r}"
    for key in ("active", "journal"):
        if not isinstance(obj.get(key), list):
            return f"{key} must be an array"
    return None
