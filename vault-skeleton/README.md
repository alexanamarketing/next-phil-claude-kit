# My Vault

This is your project vault. It holds all your projects, organized by status, plus shared templates, scripts, and docs.

Everything here is plain markdown. No proprietary format, no database, no sync service required. The AI reads it; you edit it; scripts maintain the indexes.

## Bucket Meaning

Projects live in one of five folders based on where they are in their lifecycle:

- `active/` - currently in progress; loaded regularly
- `inactive/` - stalled or waiting on someone else; not actively worked
- `potential/` - pre-contract or not yet started; worth tracking
- `completed/` - finished; kept for reference
- `lost/` - did not move forward; kept as a reference and case study

Move a project folder from one bucket to another when its status changes. Run `scripts/rebuild_indexes.py` after moving to update the index.

## Special Folders

- `system/` - the meta project. Load it with `/project system` to give the AI your identity and workflow preferences.
- `templates/new-project/` - the template used by `/new-project` and `scripts/new_project.py` to scaffold new projects.
- `scripts/` - maintenance scripts (rebuild indexes, create projects, run doctor).
- `docs/` - shared reference docs including the markdown style guide.

## How to Make a Project

Option 1 (recommended): use the Claude Code skill from any session:

    /new-project

Option 2: run the script directly:

    python3 scripts/new_project.py

Both ask you for a project slug and bucket, then copy the template, fill in the date, and update the index.

## How to Load a Project

From any Claude Code session:

    /project

This lists active projects and lets you pick one. Or jump straight to one by slug:

    /project my-project-slug

Load the meta project to give the AI your identity context:

    /project system

## Projects

| Project | Bucket | Status | Last Updated |
|---------|--------|--------|--------------|
| (no projects yet) | | | |

<!-- Add rows here as you create projects. /sync updates the last-updated column. -->
