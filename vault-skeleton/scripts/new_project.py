#!/usr/bin/env python3
"""new_project.py — create a new project from the vault template.

Usage:
    python3 new_project.py <slug> [--bucket active] [--vault-root /path/to/vault]

Creates a new project directory at {vault_root}/{bucket}/{slug}/ by copying
the templates/new-project/ template, substituting placeholders, and running
rebuild_indexes.py so the new project is indexed and won't trip the enforcer.

Placeholder substitutions applied to all text files in the template:
    [project-slug]  -> slug argument
    [project-name]  -> slug argument (same, used in folder-structure comments)
    [PROJECT NAME]  -> slug converted to Title Case
    [PROJECT-SLUG]  -> slug (upper variant)
    [YYYY-MM-DD]    -> today's date
    [DATE]          -> today's date

Load-bearing stubs are guaranteed to exist even if the template omits them:
    HANDOFF.md, INDEX.md,
    archived/notes/INDEX.md, archived/todos/INDEX.md, archived/decisions.md
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BINARY_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".pdf", ".zip", ".tar", ".gz", ".bz2",
    ".mp4", ".mp3", ".mov", ".avi",
    ".ttf", ".otf", ".woff", ".woff2",
    ".pyc", ".pyo",
}

TEMPLATE_DIR_NAME = "new-project"


def _find_vault_root(cli_arg: Optional[str] = None) -> Path:
    """Locate the vault root.

    Search order:
    1. --vault-root CLI arg
    2. VAULT_ROOT env var
    3. Walk up from this script's location looking for 'active/' marker
    4. Parent of the scripts/ directory (standard vault layout)
    """
    if cli_arg:
        return Path(cli_arg).expanduser().resolve()

    env = os.environ.get("VAULT_ROOT") or os.environ.get("HOOK_VAULT_ROOT")
    if env:
        return Path(env).expanduser().resolve()

    # Walk up from scripts/ directory
    here = Path(__file__).resolve().parent
    for p in [here, *here.parents]:
        if (p / "active").is_dir():
            return p
        if p == p.parent:
            break

    # Fallback: parent of scripts/ is vault root
    return here.parent


def _slug_to_title(slug: str) -> str:
    """Convert 'my-project-slug' -> 'My Project Slug'."""
    return slug.replace("-", " ").replace("_", " ").title()


def _is_binary(path: Path) -> bool:
    suffix = path.suffix.lower()
    if suffix in BINARY_SUFFIXES:
        return True
    # Heuristic: read first 512 bytes and check for null bytes
    try:
        chunk = path.read_bytes()[:512]
        return b"\x00" in chunk
    except OSError:
        return False


def _apply_substitutions(text: str, slug: str, today: str) -> str:
    """Replace template placeholders with real values."""
    title = _slug_to_title(slug)
    replacements = [
        ("[project-slug]", slug),
        ("[project-name]", slug),
        ("[PROJECT NAME]", title),
        ("[PROJECT-SLUG]", slug.upper()),
        ("[YYYY-MM-DD]", today),
        ("[DATE]", today),
        # Frontmatter enum placeholders — replace with sensible defaults
        ("[YYYY-MM-DD or null]", "null"),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def _write_stub(path: Path, content: str) -> None:
    """Write a stub file only if it does not already exist."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"  + created stub: {path.name}")


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def create_project(
    slug: str,
    bucket: str = "active",
    vault_root: Optional[Path] = None,
) -> Path:
    """Create a new project and return its path."""

    today = date.today().isoformat()
    title = _slug_to_title(slug)

    # Validate slug
    if not re.match(r"^[a-z0-9][a-z0-9_-]*$", slug):
        print(
            f"Error: slug '{slug}' must be lowercase letters, digits, hyphens, "
            "or underscores and must start with a letter or digit.",
            file=sys.stderr,
        )
        sys.exit(1)

    if len(slug) > 100:
        print(
            f"Error: slug is too long ({len(slug)} chars). Maximum length is 100 characters.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Locate vault root and template
    vr = vault_root or _find_vault_root()
    template_dir = vr / "templates" / TEMPLATE_DIR_NAME

    if not template_dir.is_dir():
        print(
            f"Error: template directory not found at {template_dir}\n"
            "Make sure the vault was set up with setup.sh.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Target directory
    target = vr / bucket / slug
    if target.exists():
        print(
            f"Error: project directory already exists: {target}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Copy template
    print(f"Creating project '{slug}' in {bucket}/...")
    shutil.copytree(template_dir, target)

    # Apply substitutions to all text files
    for fpath in target.rglob("*"):
        if not fpath.is_file():
            continue
        if fpath.name == ".gitkeep":
            continue
        if _is_binary(fpath):
            continue
        try:
            original = fpath.read_text(encoding="utf-8")
            replaced = _apply_substitutions(original, slug, today)
            if replaced != original:
                fpath.write_text(replaced, encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            pass

    # Guarantee load-bearing stubs exist
    archived = target / "archived"
    archived.mkdir(exist_ok=True)

    _write_stub(
        archived / "decisions.md",
        f"# Decisions - {title}\n\nStrategic decisions for the {slug} project.\n\n"
        "## Format\n\n"
        "- Date: YYYY-MM-DD\n"
        "- Decision: what was decided\n"
        "- Rationale: why\n"
        "- Outcome: (fill in later)\n",
    )

    todos_dir = archived / "todos"
    todos_dir.mkdir(exist_ok=True)
    _write_stub(
        todos_dir / "INDEX.md",
        "---\nfolder: archived/todos\nupdated: {today}\n---\n\n"
        "# archived/todos\n\n"
        "Completed todo.md snapshots, archived monthly.\n\n"
        "## Contents\n"
        "<!-- AUTO-GENERATED-BELOW: do not edit manually; run rebuild_indexes.py -->\n"
        .format(today=today),
    )

    notes_dir = archived / "notes"
    notes_dir.mkdir(exist_ok=True)
    _write_stub(
        notes_dir / "INDEX.md",
        "---\nfolder: archived/notes\nupdated: {today}\n---\n\n"
        "# archived/notes\n\n"
        "Monthly notes archives for the {slug} project.\n\n"
        "## Contents\n"
        "<!-- AUTO-GENERATED-BELOW: do not edit manually; run rebuild_indexes.py -->\n"
        .format(today=today, slug=slug),
    )

    # Ensure root INDEX.md has the AUTO-GENERATED marker so rebuild_indexes can update it
    root_index = target / "INDEX.md"
    if root_index.exists():
        content = root_index.read_text(encoding="utf-8")
        marker = "<!-- AUTO-GENERATED-BELOW: do not edit manually; run rebuild_indexes.py -->"
        if marker not in content:
            root_index.write_text(content.rstrip() + "\n\n" + marker + "\n", encoding="utf-8")

    print(f"  Template copied and substitutions applied.")

    # Run rebuild_indexes.py on the new project
    rebuild = vr / "scripts" / "rebuild_indexes.py"
    if rebuild.exists():
        print("  Running rebuild_indexes.py...")
        result = subprocess.run(
            [sys.executable, str(rebuild), "--path", str(target)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(
                f"  Warning: rebuild_indexes returned {result.returncode}",
                file=sys.stderr,
            )
            if result.stderr:
                print(f"  {result.stderr.strip()}", file=sys.stderr)
        else:
            print("  INDEX rebuilt.")

        # Also rebuild the parent bucket INDEX so the new project is listed
        result2 = subprocess.run(
            [sys.executable, str(rebuild), "--path", str(target.parent)],
            capture_output=True,
            text=True,
        )
        if result2.returncode != 0:
            print(
                f"  Warning: rebuild_indexes returned {result2.returncode} for bucket index",
                file=sys.stderr,
            )
            if result2.stderr:
                print(f"  {result2.stderr.strip()}", file=sys.stderr)
        else:
            print("  Bucket INDEX rebuilt.")
    else:
        print(f"  Note: rebuild_indexes.py not found at {rebuild} — run it manually.", file=sys.stderr)

    print(f"\nProject created: {target}")
    print(f"Next: /project {slug}  (or open the folder and start working)")
    return target


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a new project from the vault template.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python3 new_project.py acme-corp
  python3 new_project.py acme-corp --bucket potential
  python3 new_project.py acme-corp --vault-root ~/MyVault
""",
    )
    parser.add_argument(
        "slug",
        help="Project slug: lowercase letters, digits, hyphens (e.g. acme-corp)",
    )
    parser.add_argument(
        "--bucket",
        default="active",
        choices=["active", "inactive", "potential", "completed", "lost"],
        help="Bucket to create the project in (default: active)",
    )
    parser.add_argument(
        "--vault-root",
        metavar="PATH",
        help="Override vault root path (default: auto-detected)",
    )

    args = parser.parse_args()
    vault_root = Path(args.vault_root).expanduser().resolve() if args.vault_root else None
    create_project(slug=args.slug, bucket=args.bucket, vault_root=vault_root)


if __name__ == "__main__":
    main()
