#!/usr/bin/env python3
"""PreToolUse hook: inject the relevant tool module's Hook brief - AND its hard-won
corrections - the first time a session touches that tool's surface (Bash or browser).

Corrections shipping WITH the brief (added 2026-07-26) is not cosmetic. Before it, this
hook read '## Hook brief' while tool-module-learn.py wrote to '## Learnings', and nothing
moved a fact between them. Measured cost: the Make brief was injected 67 minutes before a
session concluded "no API exists to purge a webhook queue" and left a live
pipeline down; the brief said "purge the queue" and never said how, because the endpoint
sat in Learnings. CORRECTED-tagged entries lead the block and get a RESERVED slice of the
cap - a fact that already cost someone outranks a generic trap bullet.

Part of the tool-knowledge toolkit. Modules live in
~/.claude/references/tool-modules/<tool>.md.

Behavior (codex gate 1 folded, 2026-07-23):
- Non-blocking BACKSTOP by design: the brief arrives with the first matching
  call's result (PreToolUse context is delivered on the next model request).
  Pre-action loading is owned by skills (READ FIRST lines) and project
  protocols (e.g. RR's backend work protocol). A deny-once variant was built
  and REJECTED after it live-false-denied a command whose TEXT merely
  contained mutation-looking fixtures (2026-07-23 build journal).
- One injection per (session, agent, tool): atomic marker files, cleared by
  pre-compact.sh so a compacted context re-receives the brief.
- Primary-match-only: the first matching tool gets the full brief; other
  tools matched in the same payload get a one-line router.
- Hard size caps: 12000 chars per brief, 14000 combined (raised from 3000/4500 on
  2026-07-26 after measuring, then to 12000 by policy as the STANDING
  DEFAULT for every tool present and future. Rationale to not re-litigate: the old
  cap discarded ~half of ghl and make, the two we work hardest and which hold the
  most learnings; and the brief injects ONCE PER SESSION PER TOOL, so the largest
  module today costs ~1700 tokens one time against a 1M context. Headroom is
  deliberate - modules grow, and a module should not start losing its tail again
  without someone deciding to let it.)
- Whole entry point wrapped; always exits 0; stdout carries only JSON.

RECORDS MODE (2026-08-06, tool-knowledge redesign Phase 2)
---------------------------------------------------------
A migrated module carries a fenced ```json records block
`{schema_version, active[], journal[]}` (design decision B). When that block is
present the injector renders from `active[]` instead of the old prose sections:

  - ALWAYS block: the full problem->fix text of every `load: always` record.
  - PROJECT FOCUS block (design sec 5 step 2; Phase 4.6 = gate F3 decision A): full
    text of records whose tags fall in the ACTIVE PROJECT's declared focus tags. The
    active project is resolved from the session's working directory (the PreToolUse
    payload `cwd`) against `references/tool-module-focus.json` (project roots -> focus
    tags). A session outside every declared root gets NO focus block (titles-only) -
    the safe default; it never over-injects, and `load: always` danger facts inject in
    full regardless. Env `TOOL_MODULE_FOCUS` still works as an explicit override.
    Focus tokens are exact tags (`ghl/workflows`) or namespace globs (`ghl/*`).
  - TAG INDEX (manifest): one GENERATED title per surviving active record, grouped
    by tag. Titles derive from `problem`; there is no stored title field. Scoped
    (non-always, non-focus) titles are capped (`TOOL_MODULE_SCOPED_CAP`); when the
    cap trims, the omitted COUNT and IDS are named in the text - never a silent drop
    (the silent drop of the old learnings budget was the original defect).

Ordering key everywhere records/titles are ranked: `last_verified` else `date`,
descending, with severity (critical>high>normal) as the tiebreak.

Correctness comes from structure, not substrings: a record whose id appears in
another active record's `supersedes[]` is excluded at render time (defensive - the
appender already journals it), and there is NO `"CORRECT" in text` promotion in the
records path (that substring test falsely promoted "CONFIRMED-CORRECT"; design D5).

A module with NO records block falls back to `_fallback_brief`, which injects its
old `## Hook brief` + `## Learnings` EXACTLY as before, so a partial migration
degrades gracefully (real modules are unmigrated until the Phase 3/5 cutover).
"""
import hashlib
import json
import os
import re
import sys

# TOOL_MODULE_DIR / TOOL_MODULE_MARKER_DIR env overrides exist ONLY so the test
# battery can run against a temp dir and never write into (or read stale markers
# from) the live tool-modules tree. Live invocation sets neither and uses the
# fixed paths below. (Added 2026-08-06, tool-knowledge redesign Phase 0.)
MODULE_DIR = os.environ.get("TOOL_MODULE_DIR") or os.path.expanduser("~/.claude/references/tool-modules")
# User-private state dir (matches the copy-standards sibling hook); moved off
# the fixed /tmp path per the 2026-07-23 Opus audit (MINOR-1a). Known accepted:
# pre-compact.sh clears it machine-wide for this user, so a compaction in one
# parallel session re-arms briefs in the others - re-injection is harmless.
MARKER_DIR = os.environ.get("TOOL_MODULE_MARKER_DIR") or os.path.expanduser("~/.claude/hooks/state/tool-module-brief")
# Per-project FOCUS config (Phase 4.6, gate F3 = decision A). Maps a project's
# on-disk roots to the tool-area tags it lives in; a session whose working
# directory sits inside one of those roots loads that project's focus tags'
# scoped records in FULL. Env override exists ONLY for the test battery. Live
# invocation uses the fixed path. Kept OUTSIDE MODULE_DIR on purpose so the live
# module tree stays byte-for-byte a pure data dir (the cutover verify hashes it).
FOCUS_CONFIG = os.environ.get("TOOL_MODULE_FOCUS_CONFIG") or os.path.expanduser("~/.claude/references/tool-module-focus.json")
BRIEF_HEADING = "## Hook brief"
LEARN_HEADING = "## Learnings"   # must match tool-module-learn.py's target section
ENTRY_RE = re.compile(r"^- \d{4}-\d{2}-\d{2}\b")   # a real learning always starts with its date
BRIEF_CAP = 12000
CORRECTIONS_RESERVE = 5000  # guaranteed slice for CORRECTED/recent learnings
# MUST stay comfortably ABOVE BRIEF_CAP. The combined cap slices the END of the
# assembled context, and corrections are appended at the END of a brief, so a
# combined cap equal to BRIEF_CAP would silently cut the highest-value content.
COMBINED_CAP = 14000

# --- records mode (Phase 2) ---
# A migrated module carries a fenced ```json block whose parsed value is a dict
# with an "active" key. Same shape the store writes; the injector only READS it.
RECORDS_FENCE_RE = re.compile(r"```json[ \t]*\n(.*?)\n```", re.DOTALL)
TITLE_CAP = 90          # derived-title length ceiling (trim at a word boundary)
SCOPED_CAP_DEFAULT = 40  # max scoped titles in the index before omission-reporting kicks in
SEV_DESC = {"critical": 2, "high": 1, "normal": 0}   # rank for the severity tiebreak


def _scoped_cap():
    """Max scoped titles before the index reports omitted count+ids. Env-overridable
    (the battery sets a tiny cap to exercise omission deterministically)."""
    raw = os.environ.get("TOOL_MODULE_SCOPED_CAP", "")
    if raw:
        try:
            return max(0, int(raw))
        except ValueError:
            pass
    return SCOPED_CAP_DEFAULT


def _norm_path(p):
    """Absolute, symlink-resolved, no trailing slash - so prefix comparison is stable."""
    try:
        return os.path.realpath(os.path.abspath(p)).rstrip("/")
    except Exception:
        return (p or "").rstrip("/")


def _under_root(cwd, root):
    """True if cwd is root or a descendant of root, matched on PATH boundaries
    (so /a/project-old does NOT match root /a/project)."""
    if not cwd or not root:
        return False
    return cwd == root or cwd.startswith(root + "/")


def _project_focus_from_config(cwd):
    """Resolve the active project from `cwd` (the session's working directory, taken
    from the PreToolUse payload) against FOCUS_CONFIG, and return its focus tags.

    Longest matching root wins (a nested project root beats its parent). Any failure
    - missing/broken config, cwd outside every declared root, no `focus` list - returns
    an EMPTY set, which the caller treats as "no focus" (titles-only). Never raises,
    never over-injects."""
    if not cwd:
        return set()
    try:
        with open(FOCUS_CONFIG) as f:
            cfg = json.load(f)
    except (OSError, ValueError):
        return set()
    ncwd = _norm_path(cwd)
    best_root, best_focus = "", set()
    for proj in (cfg.get("projects") or []):
        if not isinstance(proj, dict):
            continue
        focus = {t.strip() for t in (proj.get("focus") or []) if isinstance(t, str) and t.strip()}
        if not focus:
            continue
        for root in (proj.get("roots") or []):
            if not isinstance(root, str):
                continue
            nroot = _norm_path(root)
            if _under_root(ncwd, nroot) and len(nroot) > len(best_root):
                best_root, best_focus = nroot, focus
    return best_focus


def _focus_tags(cwd=None):
    """Session's project-focus tags (design sec 5 step 2): records matching these load
    in FULL, not title-only.

    Two sources, env first: the explicit env `TOOL_MODULE_FOCUS` (comma-separated) is
    an override the test battery and any manual run can set. When it is unset, the
    active project is resolved from `cwd` (the PreToolUse payload's working directory)
    via FOCUS_CONFIG. A session with neither an env override nor a cwd inside a declared
    project root gets an empty set = pure manifest (titles-only), which is the safe
    default: nothing over-injects, `load: always` danger facts still ship in full."""
    raw = os.environ.get("TOOL_MODULE_FOCUS", "")
    if raw.strip():
        return {t.strip() for t in raw.split(",") if t.strip()}
    return _project_focus_from_config(cwd)


def _tag_matches_focus(tag, focus):
    """A record tag counts as in-focus if the focus set names it exactly, or names its
    namespace as a glob (`ghl/*` matches every `ghl/...` tag, and `ghl` matches too)."""
    if tag in focus:
        return True
    for f in focus:
        if f.endswith("/*") and (tag == f[:-2] or tag.startswith(f[:-1])):
            return True
        if "/" not in f and tag.startswith(f + "/"):
            return True
    return False


def _record_in_focus(record, focus):
    return bool(focus) and any(_tag_matches_focus(t, focus) for t in (record.get("tags") or []))


def _effective_date(record):
    return record.get("last_verified") or record.get("date") or ""


def _rank_key(record):
    # used with reverse=True: date descending, then severity (critical>high>normal)
    return (_effective_date(record), SEV_DESC.get(record.get("severity"), -1))


def _sorted_by_rank(records):
    return sorted(records, key=_rank_key, reverse=True)


def derive_title(record):
    """A generated one-line title from `problem` (never a stored title field)."""
    p = (record.get("problem") or "").strip().rstrip(".")
    if len(p) > TITLE_CAP:
        head = p[:TITLE_CAP].rsplit(" ", 1)[0]
        p = (head or p[:TITLE_CAP]) + "..."
    return p or record.get("id") or "untitled"


def _full_line(record):
    p = (record.get("problem") or "").strip()
    fix = (record.get("fix") or "").strip()
    return f"- {p} Fix: {fix}" if fix else f"- {p}"


def parse_records_block(text):
    """First ```json fence whose parsed value is a dict with a list `active`, else None."""
    for m in RECORDS_FENCE_RE.finditer(text):
        try:
            obj = json.loads(m.group(1))
        except ValueError:
            continue
        if isinstance(obj, dict) and isinstance(obj.get("active"), list):
            return obj
    return None


def _build_manifest(records):
    """One derived title per record, grouped by tag (a multi-tag record appears under
    each of its tags), each group ordered by the universal rank key."""
    groups = {}
    for r in records:
        for tag in (r.get("tags") or ["(untagged)"]):
            groups.setdefault(tag, []).append(r)
    lines = ["TAG INDEX (read the full module for a tag's full records):"]
    for tag in sorted(groups):
        lines.append(f"{tag}:")
        for r in _sorted_by_rank(groups[tag]):
            lines.append(f"  - {derive_title(r)}")
    return "\n".join(lines)


def build_records_brief(obj, cwd=None):
    """Render the records-mode body from a parsed records block, or None if nothing
    active survives (caller then falls back to the prose brief). `cwd` is the session's
    working directory (from the PreToolUse payload); it resolves the active project's
    focus tags when no env override is set."""
    active = [r for r in obj.get("active", []) if isinstance(r, dict)]
    # Defensive supersession: never inject a record whose id is retired by another
    # active record's supersedes[] (the appender already journals it; this guards a
    # hand-mangled on-disk block). Structural, not a "CORRECT" substring test.
    superseded = set()
    for r in active:
        for s in (r.get("supersedes") or []):
            superseded.add(s)
    active = [r for r in active if r.get("id") not in superseded]
    if not active:
        return None

    focus = _focus_tags(cwd)
    always = [r for r in active if r.get("load") == "always"]
    focus_recs = [r for r in active
                  if r.get("load") != "always" and _record_in_focus(r, focus)]
    full_ids = {r.get("id") for r in always} | {r.get("id") for r in focus_recs}
    scoped = [r for r in active if r.get("id") not in full_ids]

    # Scoped selection cap: keep the top-ranked scoped titles; NAME the omitted ones.
    scoped_sorted = _sorted_by_rank(scoped)
    cap = _scoped_cap()
    kept_scoped = scoped_sorted[:cap]
    omitted_ids = [r.get("id") or "?" for r in scoped_sorted[cap:]]

    parts = []
    if always:
        parts.append("ALWAYS (apply on every touch of this tool):\n"
                     + "\n".join(_full_line(r) for r in _sorted_by_rank(always)))
    if focus_recs:
        parts.append(f"PROJECT FOCUS ({', '.join(sorted(focus))}) - full records:\n"
                     + "\n".join(_full_line(r) for r in _sorted_by_rank(focus_recs)))
    # The index lists a title for every SURVIVING active record (always + focus +
    # kept scoped), grouped by tag. Always/focus titles are never trimmed by the cap.
    parts.append(_build_manifest(always + focus_recs + kept_scoped))
    if omitted_ids:
        parts.append(f"[{len(omitted_ids)} lower-priority scoped record(s) omitted from the "
                     f"index; read the full module. ids: {', '.join(omitted_ids)}]")
    return "\n\n".join(parts)


# Order = priority (first match gets the full brief).
# Host patterns match a hostname or any subdomain of it, boundary-guarded on both
# sides (no foo-canva.com, no canva.com.evil.example). Token patterns treat _ and -
# as separators (so FLEXMLS_API_KEY, gohighlevel-webhook, ghl-token match) and are
# deliberately recall-biased: a false positive costs one small context injection
# (the hook grants no permissions), a miss costs the brief. Bare words too common
# in unrelated contexts are host-only.
HOST_LEFT = r"(?<![A-Za-z0-9_.-])"
HOST_RIGHT = r"(?=$|[^A-Za-z0-9_.-])"
TOK_LEFT = r"(?<![A-Za-z0-9])"
TOK_RIGHT = r"(?![A-Za-z0-9])"


def _host(suffix):
    return HOST_LEFT + r"(?:[A-Za-z0-9-]+\.)*" + re.escape(suffix) + HOST_RIGHT


def _tok(value):
    return TOK_LEFT + re.escape(value) + TOK_RIGHT


PATTERNS = [
    ("gmail", re.compile(_host("mail.google.com") + "|" + _tok("gmail"), re.I)),
    ("google-docs-drive", re.compile("|".join([
        _host("docs.google.com"), _host("drive.google.com"), _host("sheets.google.com"),
        _tok("gdrive"), _tok("gdocs")]), re.I)),
    ("flexmls", re.compile("|".join([
        _host("flexmls.com"), _host("sparkplatform.com"), _tok("flexmls")]), re.I)),
    ("gohighlevel", re.compile("|".join([
        _host("gohighlevel.com"), _host("leadconnectorhq.com"),
        _tok("gohighlevel"), _tok("leadconnectorhq"), _tok("ghl")]), re.I)),
    ("canva", re.compile(_host("canva.com") + "|" + _tok("canva"), re.I)),
]

HOST_TOOL = [
    (("mail.google.com",), "gmail"),
    (("docs.google.com", "drive.google.com", "sheets.google.com"), "google-docs-drive"),
    (("flexmls.com", "sparkplatform.com"), "flexmls"),
    (("gohighlevel.com", "leadconnectorhq.com", "app.gohighlevel.com"), "gohighlevel"),
    (("canva.com",), "canva"),
]


def destination_tool(haystack):
    """Tool owning the first RECOGNIZED destination URL in the payload."""
    for m in re.finditer(r"https?://([^/\s'\"\\)?#]+)", haystack):
        host = m.group(1).split(":")[0].lower()
        for suffixes, tool in HOST_TOOL:
            for s in suffixes:
                if host == s or host.endswith("." + s):
                    return tool
    return None


def section_lines(text, heading):
    """Lines under `heading`, stopping at the next '## '. Empty list if absent."""
    out, collecting = [], False
    for line in text.split("\n"):
        if not collecting:
            if line.strip() == heading:
                collecting = True
            continue
        if line.startswith("## "):
            break
        out.append(line)
    return out


def pick_corrections(text, budget):
    """Learnings entries worth shipping WITH the brief, newest first, within budget.

    Why this exists (2026-07-26): the brief and the capture section were disconnected.
    `extract_brief` read '## Hook brief'; `tool-module-learn.py` appends to '## Learnings';
    nothing moved a fact between them, and the module's own promotion rule ("promote into
    the sections above at ~10 entries") is a manual step nobody performs mid-incident.

    Cost of that gap, measured: the Make brief WAS injected 67 minutes before a session
    told the user "no API exists to purge a webhook queue" and left a live
    pipeline down. The brief said "purge the queue" and never said how, because the
    endpoint sat in Learnings. It had been in circulation for nine days.

    CORRECTED-tagged entries come first on purpose: an entry only earns that tag after a
    wrong belief was disproven, so it is exactly the fact most likely to be re-guessed.
    """
    # Only real dated entries. The schema is enforced by tool-module-learn.py, so a
    # leading date is what separates a learning from the placeholder line every fresh
    # module ships with ("- (append dated durable learnings here...)"), which was
    # otherwise delivered as a "correction" - caught live on a fresh module's brief
    # minutes after this shipped.
    entries = [ln for ln in section_lines(text, LEARN_HEADING)
               if ENTRY_RE.match(ln.strip())]
    if not entries:
        return []
    corrected = [e for e in entries if "CORRECT" in e.upper()]
    others = [e for e in entries if e not in corrected]
    picked, used = [], 0
    for e in corrected + list(reversed(others)):   # corrections first, then newest
        if used + len(e) + 1 > budget:
            break
        picked.append(e)
        used += len(e) + 1
    return picked


def _module_description(text):
    """The module's human description line: the first non-empty prose line after the
    H1, skipping headings and code fences. Used as the brief when a module has no real
    records yet, so a fresh session that touches the tool still gets a one-line 'what
    this tool is' instead of nothing (or a fabricated 'learned' record)."""
    saw_h1 = False
    for line in text.split("\n"):
        s = line.strip()
        if not saw_h1:
            if s.startswith("# "):
                saw_h1 = True
            continue
        if not s or s.startswith("#") or s.startswith("```"):
            continue
        return s
    return None


def extract_brief(tool, cwd=None):
    """Records-mode when the module carries a records block, else the prose fallback.
    `cwd` (session working directory from the payload) selects project focus."""
    try:
        with open(os.path.join(MODULE_DIR, f"{tool}.md")) as f:
            text = f.read()
    except OSError:
        return None
    try:
        obj = parse_records_block(text)
    except Exception:
        obj = None
    if obj is not None:
        try:
            body = build_records_brief(obj, cwd)
        except Exception:
            body = None
        if body:
            if len(body) > BRIEF_CAP:
                body = body[:BRIEF_CAP] + "\n[brief cap reached - read the full module]"
            return body
        # Records block present but nothing active yet (a seed module ships empty):
        # emit the module's one-line description so touching the tool still surfaces
        # what it is, WITHOUT shipping a fabricated record just to have a brief.
        desc = _module_description(text)
        if desc:
            return f"No tips learned yet. {desc}"
        # else degrade to the prose brief
    return _fallback_brief(text)


def _fallback_brief(text):
    """The pre-records injection: the module's `## Hook brief` plus corrections picked
    from `## Learnings`, EXACTLY as before records mode (unmigrated modules rely on it)."""
    body = "\n".join(section_lines(text, BRIEF_HEADING)).strip()

    # RESERVE room for corrections rather than spending what happens to be left.
    # First version gave corrections only the leftover cap, which meant the busiest
    # modules never delivered any: ghl's brief alone is ~2850 of the 3000 chars, so
    # its corrections were silently dropped. A CORRECTED entry is a fact that already
    # cost someone real time, which outranks a generic trap bullet, so it gets a
    # guaranteed slice and the BODY is trimmed at a line boundary to make room.
    label = ("\n\nCORRECTIONS + RECENT LEARNINGS (facts that already cost someone; "
             "full list in the module):\n")
    try:
        picked = pick_corrections(text, CORRECTIONS_RESERVE)
    except Exception:
        picked = []                                  # a brief without corrections beats no brief

    if not picked:
        if len(body) > BRIEF_CAP:
            body = body[:BRIEF_CAP] + "\n[truncated - read the full module]"
        return body or None

    block = label + "\n".join(picked)
    room = BRIEF_CAP - len(block)
    if len(body) > room:
        kept = []
        used = 0
        for line in body.split("\n"):               # trim whole lines, never mid-sentence
            if used + len(line) + 1 > room - 40:
                break
            kept.append(line)
            used += len(line) + 1
        body = "\n".join(kept) + "\n[trimmed - read the full module]"
    return (body + block) or None


def marker_path(session, agent, tool):
    key = hashlib.sha1(f"{session}|{agent}|{tool}".encode()).hexdigest()[:16]
    return os.path.join(MARKER_DIR, f"{key}.{tool}")


def claim(path):
    """Atomically claim a marker. True = we own the injection."""
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        return True
    except FileExistsError:
        return False
    except OSError:
        return True  # cannot persist markers; inject anyway (may repeat)


def main():
    payload = json.load(sys.stdin)
    tool_input = payload.get("tool_input") or {}
    try:
        haystack = json.dumps(tool_input)
    except Exception:
        haystack = str(tool_input)

    matched = [t for t, p in PATTERNS if p.search(haystack)]
    if not matched:
        return
    # the request's destination URL outranks pattern order for primary choice
    dest = destination_tool(haystack)
    if dest in matched:
        matched.remove(dest)
        matched.insert(0, dest)

    session = str(payload.get("session_id") or os.getppid())
    agent = str(payload.get("agent_id") or "main")
    # The session's working directory: Claude Code puts it in the PreToolUse payload
    # as `cwd` (the same field the live command-guard hook reads). It resolves which
    # declared project this session is in, hence which focus tags load in full. Fall
    # back to the hook process cwd if the payload omits it (older client / manual run).
    cwd = payload.get("cwd") or os.getcwd()
    os.makedirs(MARKER_DIR, mode=0o700, exist_ok=True)

    primary, routers = None, []
    for tool in matched:
        path = marker_path(session, agent, tool)
        if os.path.exists(path):
            continue
        if primary is None:
            if not claim(path):
                continue
            brief = extract_brief(tool, cwd)
            if brief is None:
                try:
                    os.unlink(path)
                except OSError:
                    pass
                continue
            primary = (tool, path, brief)
        else:
            # secondary tools: one-line router only, no marker (full brief
            # still owed on their own first direct touch)
            routers.append(f"Also touched [{tool}]: module at {MODULE_DIR}/{tool}.md")

    if primary is None:
        return
    tool, path, brief = primary

    header = (
        f"TOOL MODULE [{tool}] - durable recipes/traps "
        f"(injected once per session; full module: {MODULE_DIR}/{tool}.md):"
    )
    context = "\n\n".join([f"{header}\n{brief}"] + routers)
    if len(context) > COMBINED_CAP:      # say so rather than cut silently
        context = context[:COMBINED_CAP] + "\n[combined cap reached - read the full module]"

    try:
        out = {"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": context,
        }}
        print(json.dumps(out))
        sys.stdout.flush()
    except Exception:
        # delivery failed: release the claim so a later call can retry
        try:
            os.unlink(path)
        except OSError:
            pass


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
