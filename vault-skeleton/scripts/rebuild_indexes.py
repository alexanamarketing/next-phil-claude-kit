#!/usr/bin/env python3
"""rebuild_indexes.py — regenerate INDEX.md files across the vault."""
import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Set, Tuple

try:
    import yaml
except ImportError:
    yaml = None

# Vault root: env var takes precedence; fallback to parent of scripts/ directory.
# When running from inside the vault (scripts/rebuild_indexes.py), __file__.parent.parent
# is the vault root. Set VAULT_ROOT or HOOK_VAULT_ROOT to override.
VAULT_ROOT = Path(
    os.environ.get("VAULT_ROOT")
    or os.environ.get("HOOK_VAULT_ROOT")
    or Path(__file__).parent.parent
)
AUTO_MARKER = "<!-- AUTO-GENERATED-BELOW: do not edit manually; run rebuild_indexes.py -->"


def load_exclusions() -> List[str]:
    cfg = Path(__file__).parent / "config" / "md-cleanup-exclusions.txt"
    if not cfg.exists():
        return []
    out = []
    for line in cfg.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(line)
    return out


def is_excluded(folder: Path, exclusions: List[str]) -> bool:
    name = folder.name
    return any(name.startswith(pfx) for pfx in exclusions)


def md_files_in(folder: Path) -> List[Path]:
    return sorted([
        p for p in folder.iterdir()
        if p.is_file() and not p.is_symlink() and p.suffix == ".md" and p.name != "INDEX.md"
    ])


def subfolders_in(folder: Path, exclusions: List[str]) -> List[Path]:
    return sorted([
        p for p in folder.iterdir()
        if p.is_dir()
        and not p.is_symlink()
        and not p.name.startswith(".")
        and not is_excluded(p, exclusions)
    ])


def walk_bottom_up(root: Path, exclusions: List[str]):
    all_dirs = []
    for dirpath, dirnames, _ in os.walk(root, topdown=True, followlinks=False):
        dirnames[:] = [
            d for d in dirnames
            if not d.startswith(".")
            and not any(d.startswith(p) for p in exclusions)
            and not (Path(dirpath) / d).is_symlink()
        ]
        all_dirs.append(Path(dirpath))
    all_dirs.sort(key=lambda p: -len(p.parts))
    yield from all_dirs


def extract_description(md_file: Path) -> str:
    try:
        text = md_file.read_text(encoding="utf-8")
    except Exception:
        return "unreadable"

    if text.startswith("---\n") and yaml:
        end = text.find("\n---\n", 4)
        if end > 0:
            try:
                meta = yaml.safe_load(text[4:end])
                if isinstance(meta, dict) and meta.get("description"):
                    return str(meta["description"]).strip()
            except Exception:
                pass

    body_start = 0
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end > 0:
            body_start = end + 5

    for line in text[body_start:].splitlines():
        if line.startswith("# "):
            return line[2:].strip()

    return "no description"


def get_subfolder_purpose(subfolder: Path) -> str:
    """Extract purpose/description from a subfolder's INDEX.md."""
    index_path = subfolder / "INDEX.md"
    if not index_path.exists():
        return ""
    try:
        text = index_path.read_text(encoding="utf-8")
    except Exception:
        return ""

    body_start = 0
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end > 0:
            body_start = end + 5

    for line in text[body_start:].splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("<!--"):
            continue
        if stripped == "Purpose: (curate this line)":
            return ""
        if stripped.startswith("Purpose: "):
            val = stripped[9:]
            if val.startswith("[") and val.endswith("]"):
                return ""
            return val
        if not stripped.startswith("-") and not stripped.startswith("|"):
            return stripped
    return ""


def relative_to_vault(folder: Path) -> str:
    try:
        return str(folder.relative_to(VAULT_ROOT))
    except ValueError:
        return str(folder)


def write_index(folder: Path, exclusions: List[str]) -> str:
    """Write or update INDEX.md for folder. Returns 'wrote', 'skipped-marker', or 'skipped-empty'."""
    files = md_files_in(folder)

    subs_with_content = []
    for s in subfolders_in(folder, exclusions):
        if (s / "INDEX.md").exists():
            subs_with_content.append(s)
            continue
        try:
            has_md = any(p.is_file() and p.suffix == ".md" for p in s.iterdir())
        except (PermissionError, OSError):
            has_md = False
        if has_md:
            subs_with_content.append(s)

    if not files and not subs_with_content:
        return "skipped-empty"

    index_path = folder / "INDEX.md"
    existing_curated = ""
    if index_path.exists():
        existing = index_path.read_text(encoding="utf-8")
        if AUTO_MARKER in existing:
            existing_curated = existing.split(AUTO_MARKER)[0].rstrip() + "\n"
        else:
            print(f"warning: missing marker in {index_path}, skipping", file=sys.stderr)
            return "skipped-marker"

    if not existing_curated:
        rel = relative_to_vault(folder)
        existing_curated = (
            f"---\n"
            f"folder: {rel}\n"
            f"updated: {datetime.now().strftime('%Y-%m-%d')}\n"
            f"---\n\n"
            f"# {rel}\n\n"
            f"## Contents\n"
        )

    auto_lines = [
        AUTO_MARKER,
        "",
    ]
    if subs_with_content:
        sub_entries = []
        for s in subs_with_content:
            sub_files = [
                p for p in s.iterdir()
                if p.is_file() and p.suffix == ".md" and p.name != "INDEX.md"
            ]
            sub_subdirs = [
                p for p in s.iterdir()
                if p.is_dir() and not p.name.startswith(".")
            ]
            if not sub_files and not sub_subdirs:
                continue
            purpose = get_subfolder_purpose(s)
            if purpose:
                sub_entries.append(f"- [{s.name}/]({s.name}/INDEX.md) - {purpose}")
            elif sub_files:
                sub_entries.append(f"- [{s.name}/]({s.name}/INDEX.md) - {len(sub_files)} files")
            else:
                sub_entries.append(f"- [{s.name}/]({s.name}/INDEX.md) - {len(sub_subdirs)} subfolders")
        if sub_entries:
            auto_lines.append("### Subfolders")
            auto_lines.append("")
            auto_lines.extend(sub_entries)
            auto_lines.append("")
    if files:
        auto_lines.append("### Files")
        auto_lines.append("")
        for f in files:
            desc = extract_description(f)
            auto_lines.append(f"- [{f.name}]({f.name}) - {desc}")
        auto_lines.append("")

    index_path.write_text(existing_curated + "\n".join(auto_lines) + "\n", encoding="utf-8")
    return "wrote"


def parse_index_entries(index_path: Path) -> Tuple[Set[str], Set[str]]:
    """Parse an INDEX.md and return (listed_files, listed_subfolders) from the auto section."""
    try:
        text = index_path.read_text(encoding="utf-8")
    except Exception:
        return set(), set()

    if AUTO_MARKER not in text:
        return set(), set()

    auto_section = text.split(AUTO_MARKER, 1)[1]
    listed_files: Set[str] = set()
    listed_subs: Set[str] = set()

    for match in re.finditer(r"\[.*?\]\(([^)]+)\)", auto_section):
        target = match.group(1)
        if target.endswith("/INDEX.md"):
            listed_subs.add(target.replace("/INDEX.md", ""))
        elif target.endswith(".md"):
            listed_files.add(target)

    return listed_files, listed_subs


def check_index(folder: Path, exclusions: List[str]) -> List[str]:
    """Check a single folder for INDEX staleness. Returns list of issue strings."""
    issues = []
    files = md_files_in(folder)
    subs = subfolders_in(folder, exclusions)

    subs_with_content = []
    for s in subs:
        if (s / "INDEX.md").exists():
            subs_with_content.append(s)
            continue
        try:
            has_md = any(p.is_file() and p.suffix == ".md" for p in s.iterdir())
        except (PermissionError, OSError):
            has_md = False
        if has_md:
            subs_with_content.append(s)

    # Mirror the secondary filter write_index() applies: skip subfolders that have
    # only an INDEX.md (no other .md files, no sub-subdirectories).  write_index()
    # does not list those in the parent INDEX, so check_index() must not expect them
    # either — otherwise a freshly created project always reports UNLISTED drift for
    # its empty scaffold dirs (case-study/, deliverables/, docs/, etc.).
    listable_subs: List[Path] = []
    for s in subs_with_content:
        try:
            sub_files = [
                p for p in s.iterdir()
                if p.is_file() and p.suffix == ".md" and p.name != "INDEX.md"
            ]
            sub_subdirs = [
                p for p in s.iterdir()
                if p.is_dir() and not p.name.startswith(".")
            ]
        except (PermissionError, OSError):
            listable_subs.append(s)
            continue
        if sub_files or sub_subdirs:
            listable_subs.append(s)

    if not files and not listable_subs:
        return []

    index_path = folder / "INDEX.md"
    if not index_path.exists():
        issues.append(f"MISSING INDEX: {folder} (has {len(files)} files, {len(listable_subs)} subfolders)")
        return issues

    try:
        text = index_path.read_text(encoding="utf-8")
    except Exception:
        issues.append(f"UNREADABLE: {index_path}")
        return issues

    if AUTO_MARKER not in text:
        return []

    listed_files, listed_subs = parse_index_entries(index_path)
    actual_files = {f.name for f in files}
    actual_subs = {s.name for s in listable_subs}

    unlisted_files = actual_files - listed_files
    phantom_files = listed_files - actual_files
    unlisted_subs = actual_subs - listed_subs
    phantom_subs = listed_subs - actual_subs

    rel = relative_to_vault(folder)
    for f in sorted(unlisted_files):
        issues.append(f"  UNLISTED file: {rel}/{f}")
    for f in sorted(phantom_files):
        issues.append(f"  PHANTOM file: {rel}/{f} (listed but missing from disk)")
    for s in sorted(unlisted_subs):
        issues.append(f"  UNLISTED subfolder: {rel}/{s}/")
    for s in sorted(phantom_subs):
        issues.append(f"  PHANTOM subfolder: {rel}/{s}/ (listed but missing from disk)")

    return issues


def main():
    parser = argparse.ArgumentParser(description="Rebuild INDEX.md files")
    parser.add_argument("--project", help="Project name under active/")
    parser.add_argument("--all", action="store_true", help="All active/ projects")
    parser.add_argument("--all-buckets", action="store_true", help="All buckets (active, inactive, completed, potential, lost)")
    parser.add_argument("--path", help="Specific folder path")
    parser.add_argument("--check", action="store_true", help="Dry-run, report diffs")
    args = parser.parse_args()

    exclusions = load_exclusions()

    targets: List[Path] = []
    if args.path:
        targets.append(Path(args.path))
    elif args.project:
        targets.append(VAULT_ROOT / "active" / args.project)
    elif args.all_buckets:
        for bucket in ("active", "inactive", "completed", "potential", "lost"):
            bucket_path = VAULT_ROOT / bucket
            if bucket_path.is_dir():
                targets.append(bucket_path)
    elif args.all:
        targets.append(VAULT_ROOT / "active")
    else:
        parser.print_help()
        sys.exit(1)


    if args.check:
        found_issues = False
        for t in targets:
            for folder in walk_bottom_up(t, exclusions):
                issues = check_index(folder, exclusions)
                if issues:
                    found_issues = True
                    for issue in issues:
                        print(issue, file=sys.stderr)
        if found_issues:
            print("\nINDEX drift detected. Run without --check to regenerate.", file=sys.stderr)
            sys.exit(1)
        else:
            print("All INDEXes up to date.", file=sys.stderr)
            sys.exit(0)

    wrote = 0
    skipped_marker = 0
    for t in targets:
        for folder in walk_bottom_up(t, exclusions):
            result = write_index(folder, exclusions)
            if result == "wrote":
                wrote += 1
            elif result == "skipped-marker":
                skipped_marker += 1
    target_desc = str(targets[0]) if len(targets) == 1 else f"{len(targets)} target(s)"
    skip_part = f" ({skipped_marker} skipped: missing marker)" if skipped_marker else ""
    print(f"Rebuilt {wrote} INDEX.md files under {target_desc}{skip_part}.")


if __name__ == "__main__":
    main()
