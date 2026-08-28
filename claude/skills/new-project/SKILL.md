---
name: new-project
description: Scaffold a new project under a vault bucket from the template. Run when starting work on a new client, project, or initiative.
---

# /new-project - Scaffold a New Project

Create a valid, fully-stubbed project folder under your vault.

## Usage

```
/new-project <slug> [<bucket>]
```

- slug: short kebab-case name for the project (e.g. `acme-rebrand`)
- bucket: which bucket to place it in (default: `active`). Options: `active`, `inactive`, `potential`, `completed`, `lost`

## What It Does

Runs (to locate `<vault_root>`, read `~/.claude/starter-kit/config.json` first, then the `VAULT_ROOT` env var, else ask):

```bash
python3 <vault_root>/scripts/new_project.py <slug> --bucket <bucket>
```

The script:
1. Copies `<vault_root>/templates/new-project/` into `<vault_root>/<bucket>/<slug>/`
2. Fills in the slug and today's date in stub files
3. Creates all load-bearing stubs: `HANDOFF.md`, `INDEX.md`, `notes.md`, `todo.md`, `archived/notes/INDEX.md`, `archived/todos/INDEX.md`, `archived/decisions.md`, `working-files/INDEX.md`, `deliverables/INDEX.md`
4. Runs `rebuild_indexes.py` so the new folder is registered and the index-enforcer hook won't block it

## After Running

Confirm the script succeeded, then offer to load the new project:

```
Project '<slug>' created in <bucket>/. Load it now? (type /project <slug>)
```

## Help-Mode Teaching Note (T6)

After confirming creation, read `help_mode` from `<vault_root>/config.yaml`. If `on` (or the key is absent), append this note after the confirmation. If `off`, skip silently.

"Every project has the same shape: HANDOFF.md tracks state between sessions, todo.md tracks tasks, notes.md logs history, INDEX.md keeps the directory navigable. You do not edit these directly — /sync maintains them."

## Notes

- If the slug already exists in the target bucket, the script will refuse to overwrite. Choose a different slug or bucket.
- The bucket choice is permanent unless you manually move the folder later.
- Always use the script rather than manually creating the folder structure. Manual creation misses stub files and leaves the INDEX unregistered, which trips the enforcer hook.
