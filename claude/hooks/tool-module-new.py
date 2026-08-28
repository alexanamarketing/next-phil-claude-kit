#!/usr/bin/env python3
"""Scaffold a NEW tool-knowledge module - the audit-recommended fast path for
steps 1-4 of "Adding a new tool module" (references/tool-modules/INDEX.md).

Motivation (audit 2026-08-06): standing up a new module by hand has two traps a
helper removes. (1) Step 2 is a hand-edit of tool-module-brief.py, a PreToolUse
hook that runs on EVERY Bash call; a bad regex there breaks brief injection for
ALL tools, and nothing verified the edit before it went live. (2) The coupling
filename == first-tag namespace == record-id prefix (all the same <tool> string)
is invisible, and a mismatch fails later with a cryptic store error.

What it does, transactionally (refuses and leaves the tree unchanged on any
failure, and PROVES the edited hook still imports before keeping the edit):
  1. REFUSE if <tool>.md already exists (exit 3, writes nothing).
  2. WRITE <tool>.md: a one-line human header + Router placeholder + a
     `## Records (canonical, machine-read)` section whose json fence is exactly
     {"schema_version": 1, "active": [], "journal": []}. No ## Learnings /
     ## Hook brief (retired sections; the records block is what injects).
  3. REGISTER DETECTION in tool-module-brief.py: APPEND a ("<tool>", re.compile(...))
     entry as the LAST element of PATTERNS (never before an existing host-only
     line that must stay primary; the noisy-token-last convention is preserved by
     appending at the end), built from _host(<domain>) and/or _tok(<token|tool>);
     add a HOST_TOOL entry only when --host is given. Then import the edited hook
     in a SUBPROCESS and confirm the new regex is registered and matches a sample.
     On any failure ROLL BACK the hook edit AND remove the just-written module
     file, then refuse.
  4. SEED the glossary: extend_glossary("<tool>/api", <reason>).
  5. ADD the INDEX line under "Domain-injected modules".
It does NOT write the first record (that stays with /toolupdate or
tool-module-learn.py --record-file) and prints the next step.

TESTABILITY: the module dir and the hook path are env-overridable exactly like
the sibling hooks, so the battery runs the helper against COPIES in a temp dir
and never touches live:
  TOOL_MODULE_DIR         -> module dir (default live tool-modules); also where
                             the glossary sidecar is read/written (via schema).
  TOOL_MODULE_BRIEF_PATH  -> the tool-module-brief.py to edit (default live).

Exit: 0 ok; 2 bad usage/args; 3 module already exists or io error; 4 the edited
hook failed its import/compile check (rolled back).
"""
import argparse
import datetime
import os
import re
import subprocess
import sys

HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
MODULE_DIR = os.environ.get("TOOL_MODULE_DIR") or os.path.expanduser("~/.claude/references/tool-modules")
BRIEF_PATH = os.environ.get("TOOL_MODULE_BRIEF_PATH") or os.path.expanduser("~/.claude/hooks/tool-module-brief.py")
INDEX_PATH = os.path.join(MODULE_DIR, "INDEX.md")
INDEX_SECTION = "## Domain-injected modules"

TOOL_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")   # filename == tag namespace == id prefix


def die(code, msg):
    sys.stderr.write(f"tool-module-new: {msg}\n")
    sys.exit(code)


def _module_body(tool, today):
    """Minimal narrative header + Router placeholder + an EMPTY canonical records
    block. The json fence content is exactly the empty store (design decision B)."""
    return (
        f"# {tool} - Tool Module (scaffold)\n"
        f"\n"
        f"{tool}: durable cross-project knowledge for this tool. "
        f"Scaffolded {today} by tool-module-new.py; fill the narrative in after the first record.\n"
        f"\n"
        f"## Router\n"
        f"\n"
        f"- Project docs first: read `<project>/working-files/tool-stack/{tool}/` before working this tool.\n"
        f"\n"
        f"## Records (canonical, machine-read)\n"
        f"\n"
        f"The injector and manifest read `active[]` from this block; `journal[]` is archived, never "
        f"injected. Do not hand-edit; write via `/toolupdate` or `tool-module-learn.py --record-file`.\n"
        f"\n"
        f"```json\n"
        f'{{"schema_version": 1, "active": [], "journal": []}}\n'
        f"```\n"
    )


def _pattern_line(tool, host, token):
    """Source text of the PATTERNS entry. Always includes a token (recall-biased,
    matching the hook's own philosophy); ORs the host in when --host is given."""
    if host:
        src = f'_host({host!r}) + "|" + _tok({token!r})'
    else:
        src = f'_tok({token!r})'
    return f'    ("{tool}", re.compile({src}, re.I)),'


def _host_tool_line(tool, host):
    return f'    (({host!r},), {tool!r}),'


def _insert_before_list_close(text, varname, new_line):
    """Insert new_line as the last element of the `varname = [ ... ]` list, right
    before the closing bracket line (a line that is exactly `]`). Returns new text.
    Raises ValueError if the list or its close cannot be found."""
    lines = text.split("\n")
    start = None
    for i, ln in enumerate(lines):
        if ln.startswith(f"{varname} = ["):
            start = i
            break
    if start is None:
        raise ValueError(f"could not find `{varname} = [` in the hook")
    for j in range(start + 1, len(lines)):
        if lines[j].rstrip() == "]":
            lines.insert(j, new_line)
            return "\n".join(lines)
    raise ValueError(f"could not find the closing `]` of {varname}")


def _edit_hook(text, tool, host, token):
    """Return the edited hook text: PATTERNS entry appended, plus a HOST_TOOL entry
    when host is set. Idempotent-guarded so a re-run cannot duplicate an entry."""
    if re.search(rf'^\s*\("{re.escape(tool)}",', text, re.M):
        raise ValueError(f"a PATTERNS entry for {tool!r} already exists in the hook")
    text = _insert_before_list_close(text, "PATTERNS", _pattern_line(tool, host, token))
    if host:
        text = _insert_before_list_close(text, "HOST_TOOL", _host_tool_line(tool, host))
    return text


def _import_check(hook_path, tool, sample):
    """Import the edited hook in a SUBPROCESS and confirm (a) it imports at all,
    (b) the new tool is registered in PATTERNS, (c) its compiled regex matches a
    sample. Returns (ok: bool, detail: str)."""
    check = (
        "import importlib.util, sys\n"
        "path, tool, sample = sys.argv[1], sys.argv[2], sys.argv[3]\n"
        "spec = importlib.util.spec_from_file_location('brief_check', path)\n"
        "m = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(m)\n"
        "pats = [(t, p) for t, p in m.PATTERNS if t == tool]\n"
        "if not pats:\n"
        "    sys.stderr.write('tool not registered in PATTERNS'); sys.exit(11)\n"
        "if not any(p.search(sample) for t, p in pats):\n"
        "    sys.stderr.write('new regex does not match the sample'); sys.exit(12)\n"
        "print('ok')\n"
    )
    try:
        r = subprocess.run(
            [sys.executable, "-c", check, hook_path, tool, sample],
            capture_output=True, text=True, timeout=30,
        )
    except Exception as e:
        return False, f"could not run the import check: {e}"
    if r.returncode != 0:
        return False, (r.stderr or r.stdout or f"exit {r.returncode}").strip()
    return True, "ok"


def _add_index_line(index_text, tool, line):
    """Insert `line` as the last bullet under the Domain-injected modules section."""
    if f"[{tool}.md]" in index_text:
        return index_text, False
    lines = index_text.split("\n")
    hdr = next((i for i, l in enumerate(lines) if l.strip() == INDEX_SECTION), None)
    if hdr is None:
        raise ValueError(f"could not find `{INDEX_SECTION}` in INDEX.md")
    end = len(lines)
    for j in range(hdr + 1, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break
    last_bullet = None
    for j in range(hdr + 1, end):
        if lines[j].startswith("- "):
            last_bullet = j
    insert_at = (last_bullet + 1) if last_bullet is not None else hdr + 2
    lines.insert(insert_at, line)
    return "\n".join(lines), True


def main():
    ap = argparse.ArgumentParser(prog="tool-module-new.py",
                                 description="Scaffold a new tool-knowledge module (steps 1-4).")
    ap.add_argument("tool", help="tool slug; becomes filename, tag namespace, and id prefix")
    ap.add_argument("--host", help="primary domain for a web tool (adds _host + a HOST_TOOL entry)")
    ap.add_argument("--token", help="CLI/token surface to match (defaults to the tool name)")
    ap.add_argument("--reason", help="glossary-extension reason for <tool>/api")
    args = ap.parse_args()

    tool = args.tool.strip()
    if not TOOL_RE.match(tool):
        die(2, f"tool must be a lowercase slug [a-z0-9-]: {tool!r}")
    host = (args.host or "").strip() or None
    if host and not re.match(r"^[A-Za-z0-9.-]+$", host):
        die(2, f"--host does not look like a domain: {host!r}")
    token = (args.token or "").strip() or tool
    today = datetime.date.today().isoformat()
    reason = (args.reason or "").strip() or \
        f"catch-all api tag for new module {tool} (scaffolded by tool-module-new.py {today})"

    module_path = os.path.join(MODULE_DIR, f"{tool}.md")

    # (1) REFUSE if the module already exists - write nothing.
    if os.path.exists(module_path):
        die(3, f"{module_path} already exists; refusing (writes nothing)")
    if not os.path.isdir(MODULE_DIR):
        die(3, f"module dir does not exist: {MODULE_DIR}")
    try:
        with open(BRIEF_PATH) as f:
            original_hook = f.read()
    except OSError as e:
        die(3, f"cannot read the hook {BRIEF_PATH}: {e}")

    # Compute the edited hook up front so a bad-edit fails before we write anything.
    try:
        edited_hook = _edit_hook(original_hook, tool, host, token)
    except ValueError as e:
        die(2, str(e))

    # (2) WRITE the module file.
    try:
        with open(module_path, "w") as f:
            f.write(_module_body(tool, today))
    except OSError as e:
        die(3, f"cannot write {module_path}: {e}")

    def _rollback():
        try:
            with open(BRIEF_PATH, "w") as f:
                f.write(original_hook)
        except OSError:
            pass
        try:
            os.unlink(module_path)
        except OSError:
            pass

    # (3) REGISTER DETECTION, then PROVE the edited hook imports + the regex matches.
    try:
        with open(BRIEF_PATH, "w") as f:
            f.write(edited_hook)
    except OSError as e:
        try:
            os.unlink(module_path)
        except OSError:
            pass
        die(3, f"cannot write the hook {BRIEF_PATH}: {e}")

    sample = f"https://{host}/probe" if host else token
    ok, detail = _import_check(BRIEF_PATH, tool, sample)
    if not ok:
        _rollback()
        die(4, f"edited hook failed its import/compile check ({detail}); rolled back, nothing kept")

    # (4) SEED the glossary tag <tool>/api.
    if HOOKS_DIR not in sys.path:
        sys.path.insert(0, HOOKS_DIR)
    try:
        import tool_module_schema as schema
        seeded = schema.extend_glossary(f"{tool}/api", reason)
    except Exception as e:
        _rollback()
        die(3, f"could not seed glossary tag {tool}/api ({e}); rolled back, nothing kept")

    # (5) ADD the INDEX line.
    index_note = ""
    try:
        with open(INDEX_PATH) as f:
            index_text = f.read()
        line = (f"- [{tool}.md]({tool}.md) - {tool} (scaffolded {today} by tool-module-new.py; "
                f"summary pending the first record).")
        new_index, added = _add_index_line(index_text, tool, line)
        if added:
            with open(INDEX_PATH, "w") as f:
                f.write(new_index)
        else:
            index_note = " (INDEX already had an entry; left as-is)"
    except (OSError, ValueError) as e:
        index_note = f" (WARNING: could not update INDEX.md: {e}; add the line by hand)"

    # (6) Report. Do NOT write the first record.
    detect = f'_host("{host}") | _tok("{token}")' if host else f'_tok("{token}")'
    print(f"scaffolded [{tool}]")
    print(f"  module:   {module_path}  (empty records block)")
    print(f"  detect:   PATTERNS += ({tool}, {detect})"
          + (f"; HOST_TOOL += {host}" if host else ""))
    print(f"  glossary: {tool}/api " + ("seeded" if seeded else "already present"))
    print(f"  index:    INDEX.md updated{index_note}")
    print(f"next: add the first record with /toolupdate, or "
          f"tool-module-learn.py --record-file REC.json (id '{tool}-...', tag '{tool}/api'). "
          f"An empty block injects nothing until then.")
    sys.exit(0)


if __name__ == "__main__":
    main()
