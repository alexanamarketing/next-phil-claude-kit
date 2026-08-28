#!/usr/bin/env python3
"""PreToolUse hook: block Write of new .md files in indexed directories
unless the INDEX.md has been updated in the same batch.

Fires on: Write
Logic: If a new .md file is being written to a directory that has an INDEX.md,
and that file is not already listed in the INDEX, emit a blocking reminder.
Does NOT block edits to existing files (only truly new files).

Configuration (via vault config.yaml read by lib/hook_config.py):
  sacred_files  - filenames that bypass enforcement (default: INDEX.md, CLAUDE.md, etc.)
  skip_dirs     - directory names to skip (default: .git, node_modules, etc.)
  hook_strictness - 'normal' blocks with exit 2; 'relaxed' warns with exit 0

Override: INDEX_ENFORCER_ENABLED=false  (env var)
"""
import json
import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Load shared config (pyyaml-optional, graceful fallback to defaults)
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent / "lib"))
try:
    import hook_config  # type: ignore
    _HAVE_CONFIG = True
except ImportError:
    _HAVE_CONFIG = False


def _sacred_files():
    if _HAVE_CONFIG:
        return hook_config.sacred_files()
    return {"INDEX.md", "CLAUDE.md", "HANDOFF.md", "notes.md", "todo.md", "README.md"}


def _skip_dirs():
    if _HAVE_CONFIG:
        return hook_config.skip_dirs()
    return {"_inbox", ".firecrawl", ".git", "node_modules", "__pycache__", ".cache"}


def _vault_root(file_path: str = ""):
    if _HAVE_CONFIG:
        return hook_config.vault_root()
    return None


def _strictness(file_path: str = ""):
    if _HAVE_CONFIG:
        return hook_config.strictness()
    return os.environ.get("HOOK_STRICTNESS", "normal").lower()


def _help_mode() -> bool:
    if _HAVE_CONFIG:
        return hook_config.help_mode()
    return True  # default on when config not available


# ---------------------------------------------------------------------------
# Main hook logic
# ---------------------------------------------------------------------------

def main():
    if os.environ.get("INDEX_ENFORCER_ENABLED", "true").lower() == "false":
        sys.exit(0)

    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, Exception):
        sys.exit(0)

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})

    if tool_name != "Write":
        sys.exit(0)

    file_path = tool_input.get("file_path", "")
    if not file_path or not file_path.endswith(".md"):
        sys.exit(0)

    # Initialise config using file_path as search seed
    if _HAVE_CONFIG:
        hook_config.init(file_path)

    path = Path(file_path).resolve()
    sacred = _sacred_files()
    skip = _skip_dirs()
    vault = _vault_root(file_path)
    strict = _strictness(file_path)

    # Only enforce files inside the vault root (if known)
    if vault is not None:
        try:
            path.relative_to(vault)
        except ValueError:
            sys.exit(0)

    # With no vault constraint, don't police scratch files in /tmp.
    # When the vault is known, in-vault files are always enforced (even under /tmp).
    if vault is None and str(path).startswith("/tmp"):
        sys.exit(0)

    # Skip sacred/standard filenames
    if path.name in sacred:
        sys.exit(0)

    # Skip excluded directories
    for part in path.parts:
        if part in skip:
            sys.exit(0)

    # Skip if file already exists (this is an overwrite/update, not a new file)
    if path.exists():
        sys.exit(0)

    # Check if the target directory has an INDEX.md
    target_dir = path.parent
    index_path = target_dir / "INDEX.md"
    if not index_path.exists():
        sys.exit(0)

    fname = path.name

    # Check if the new filename is already listed in the INDEX
    try:
        index_content = index_path.read_text(encoding="utf-8")
    except (OSError, PermissionError):
        if vault is not None:
            # Inside a known vault but INDEX is unreadable — fail closed.
            print(
                f"\nINDEX ENFORCER — blocked (INDEX unreadable)\n"
                f"\n"
                f"  File:  {fname}\n"
                f"  Dir:   {target_dir}\n"
                f"  Index: {index_path}  (could not be read)\n"
                f"\n"
                f"The INDEX.md for this directory exists but could not be read.\n"
                f"Check file permissions and repair the INDEX before writing.\n"
                f"\n"
                f"Override: export INDEX_ENFORCER_ENABLED=false\n",
                file=sys.stderr,
            )
            sys.exit(2)
        sys.exit(0)

    # Use a word-boundary regex so "report.md" in the INDEX does not falsely
    # satisfy a check for a new file named "report.md" that happens to be a
    # substring of "long-report.md" already listed.
    if re.search(r'(?<![A-Za-z0-9._\-])' + re.escape(fname) + r'(?![A-Za-z0-9._\-])', index_content):
        sys.exit(0)

    # -----------------------------------------------------------------------
    # Violation detected: new .md in indexed directory, not listed in INDEX
    # -----------------------------------------------------------------------

    # Relaxed mode: advisory only — let the write proceed.
    # This check happens before help_mode so relaxed always stays exit-0.
    if strict == "relaxed":
        print(
            f"[index-enforcer ADVISORY] {fname} is being created in {target_dir} "
            f"but is not yet in {index_path}. "
            f"Remember to update the INDEX. (hook_strictness: relaxed)",
            file=sys.stderr,
        )
        sys.exit(0)

    # Normal mode: block with a message tailored to help_mode.
    if _help_mode():
        msg = (
            f"\nINDEX ENFORCER — write blocked\n"
            f"\n"
            f"  Trying to create: {fname}\n"
            f"  In directory:     {target_dir}\n"
            f"\n"
            f"This directory has an INDEX.md — a running list of its files so\n"
            f"future sessions (and you, tomorrow) can find what lives here.\n"
            f"The rule is: update INDEX.md before writing a new file.\n"
            f"\n"
            f"Three steps, in order:\n"
            f"  1. Read   {index_path}\n"
            f"  2. Edit   {index_path}  — add an entry for {fname}\n"
            f"  3. Retry  the Write (it will go straight through)\n"
            f"\n"
            f"This becomes second nature after the first time.\n"
            f"\n"
            f"Need to bypass enforcement temporarily?\n"
            f"  export INDEX_ENFORCER_ENABLED=false\n"
        )
    else:
        msg = (
            f"\nINDEX ENFORCER — blocked\n"
            f"\n"
            f"  File:  {fname}\n"
            f"  Dir:   {target_dir}\n"
            f"  Index: {index_path}\n"
            f"\n"
            f"Required order:\n"
            f"  1. Read   {index_path}\n"
            f"  2. Edit   {index_path}  (add entry for {fname})\n"
            f"  3. Write  {file_path}   (retry)\n"
            f"\n"
            f"Override: export INDEX_ENFORCER_ENABLED=false\n"
        )

    print(msg, file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
