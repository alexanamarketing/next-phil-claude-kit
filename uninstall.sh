#!/usr/bin/env bash
# uninstall.sh — Claude Code Starter Kit uninstaller
#
# Usage:
#   ./uninstall.sh                    interactive (removes kit files, confirms first)
#   ./uninstall.sh --yes              skip confirmation prompts
#   ./uninstall.sh --dry-run          print every action, change nothing
#   ./uninstall.sh --restore PATH     restore ~/.claude from a backup tarball
#   ./uninstall.sh -h|--help          show this help
#
# What it removes (kit-managed only):
#   - Hook files: the safety hooks (block-secrets, command-guard, secret-guard,
#                 index-enforcer, file-naming-check, claude-md-hygiene), the git
#                 hooks (auto-stage, auto-commit), Helper Mode (helper-mode.py),
#                 the tool-module engine (tool-module-*, tool_module_*,
#                 toolupdate_apply), the writing-lint stack, pre-compact.sh, and
#                 hooks/lib/hook_config.py
#   - Skill directories: project, new-project, sync, archive-docs, doctor,
#                        markdown, help, explain, unslop, helper, toolupdate, util/
#   - Pointer directory: ~/.claude/starter-kit/
#   - Hook registrations from ~/.claude/settings.json whose command basename
#     matches a kit hook (other hooks and all other settings are preserved)
#
# The vault (your projects) is NEVER touched.

set -euo pipefail

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
DRY_RUN=false
YES=false
RESTORE_PATH=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --yes|-y)
      YES=true
      shift
      ;;
    --restore)
      if [[ $# -lt 2 ]] || [[ -z "${2:-}" ]]; then
        echo "Error: --restore requires a path argument" >&2
        exit 1
      fi
      RESTORE_PATH="$2"
      shift 2
      ;;
    -h|--help)
      sed -n '2,19p' "${BASH_SOURCE[0]}"
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
RESET='\033[0m'

log()        { echo -e "$*"; }
log_ok()     { echo -e "${GREEN}  [ok]${RESET} $*"; }
log_warn()   { echo -e "${YELLOW}  [warn]${RESET} $*"; }
log_err()    { echo -e "${RED}  [error]${RESET} $*" >&2; }
log_dry()    { echo -e "${YELLOW}  [dry-run]${RESET} would: $*"; }

# Run a command or, in dry-run mode, print what would run.
run() {
  if $DRY_RUN; then
    printf '  [dry-run] would:'
    printf ' %q' "$@"
    printf '\n'
  else
    "$@"
  fi
}

# Ask a yes/no question. Returns 0 for yes, 1 for no.
ask() {
  local prompt="$1"
  if $YES; then
    log "  (auto-yes) $prompt"
    return 0
  fi
  read -r -p "  $prompt [y/N] " reply
  [[ "$reply" =~ ^[Yy]$ ]]
}

# ---------------------------------------------------------------------------
# Kit-managed file inventory
# ---------------------------------------------------------------------------
KIT_HOOKS=(
  block-secrets.py
  block-secrets-allow.txt
  command-guard.py
  secret-guard.py
  index-enforcer.py
  file-naming-check.py
  claude-md-hygiene.py
  auto-stage.sh
  auto-commit.sh
  helper-mode.py
  pre-compact.sh
  tool-module-brief.py
  tool-module-learn.py
  tool-module-new.py
  tool_module_store.py
  tool_module_schema.py
  toolupdate_apply.py
  writing-lint
  writing-lint-posttooluse.py
)
KIT_HOOK_LIB=(
  hook_config.py
)
KIT_SKILLS=(
  project
  new-project
  listing-video
  sync
  archive-docs
  doctor
  markdown
  help
  explain
  unslop
  helper
  toolupdate
  util
)

CLAUDE_DIR="$HOME/.claude"

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------
log ""
log "${BOLD}Claude Code Starter Kit — uninstaller${RESET}"
log "======================================="
if $DRY_RUN; then
  log "${YELLOW}DRY-RUN MODE: no files will be changed${RESET}"
fi
log ""

# ---------------------------------------------------------------------------
# --restore mode: extract a backup tarball over ~/.claude
# ---------------------------------------------------------------------------
if [[ -n "$RESTORE_PATH" ]]; then
  if [[ ! -f "$RESTORE_PATH" ]]; then
    log_err "Restore archive not found: $RESTORE_PATH"
    exit 1
  fi
  log "${BOLD}Restore mode: $RESTORE_PATH${RESET}"
  log ""
  log_warn "This will OVERWRITE ~/.claude with the contents of the backup."
  if ! ask "Proceed with restore from $RESTORE_PATH?"; then
    log "  Aborted."
    exit 0
  fi

  # Backup the current state before overwriting
  TIMESTAMP=$(date +%Y%m%d_%H%M%S)
  PRE_RESTORE_BACKUP="$HOME/.claude-backup-$TIMESTAMP.tar.gz"
  if [ -d "$CLAUDE_DIR" ]; then
    if $DRY_RUN; then
      log_dry "tar -C '$HOME' -czf '$PRE_RESTORE_BACKUP' .claude"
    else
      tar -C "$HOME" -czf "$PRE_RESTORE_BACKUP" .claude 2>/dev/null || true
      log_ok "Current ~/.claude backed up to $PRE_RESTORE_BACKUP"
      log "  Rollback: tar -xzf '$PRE_RESTORE_BACKUP' -C '$HOME'"
    fi
  fi

  if $DRY_RUN; then
    log_dry "tar -xzf '$RESTORE_PATH' -C '$HOME'"
    log_ok "[dry-run] Restore complete"
  else
    tar -xzf "$RESTORE_PATH" -C "$HOME"
    log_ok "Restored ~/.claude from $RESTORE_PATH"
    log ""
    log "${GREEN}${BOLD}Restore complete${RESET}"
  fi
  exit 0
fi

# ---------------------------------------------------------------------------
# Read vault root from pointer file (for the vault-intact note at the end)
# ---------------------------------------------------------------------------
VAULT_ROOT=""
POINTER_FILE="$CLAUDE_DIR/starter-kit/config.json"
if [ -f "$POINTER_FILE" ]; then
  VAULT_ROOT=$(python3 -c "
import json, sys
try:
    d = json.load(open(sys.argv[1]))
    print(d.get('vault_root', ''))
except Exception:
    print('')
" "$POINTER_FILE" 2>/dev/null || true)
fi

# ---------------------------------------------------------------------------
# Step 1: Back up current ~/.claude
# ---------------------------------------------------------------------------
log "${BOLD}Step 1: Backing up ~/.claude${RESET}"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_PATH="$HOME/.claude-backup-$TIMESTAMP.tar.gz"

if [ ! -d "$CLAUDE_DIR" ]; then
  log_warn "~/.claude does not exist — nothing to back up or remove."
  exit 0
fi

if $DRY_RUN; then
  log_dry "tar -C '$HOME' -czf '$BACKUP_PATH' .claude  (rotate: keep 3 newest)"
else
  tar -C "$HOME" -czf "$BACKUP_PATH" .claude 2>/dev/null || true
  log_ok "Backed up ~/.claude to $BACKUP_PATH"
  log "  Rollback: tar -xzf '$BACKUP_PATH' -C '$HOME'"
  # Keep only 3 most recent backups
  ls -t "$HOME"/.claude-backup-*.tar.gz 2>/dev/null | tail -n +4 | xargs -r rm -f
  log_ok "Backup rotation: keeping 3 newest ~/.claude-backup-*.tar.gz"
fi

log ""

# ---------------------------------------------------------------------------
# Step 2: Confirm destructive action
# ---------------------------------------------------------------------------
log "${BOLD}Step 2: Confirm uninstall${RESET}"
log ""
log "  Will remove:"
for _h in "${KIT_HOOKS[@]}"; do
  log "    $CLAUDE_DIR/hooks/$_h"
done
for _l in "${KIT_HOOK_LIB[@]}"; do
  log "    $CLAUDE_DIR/hooks/lib/$_l"
done
for _s in "${KIT_SKILLS[@]}"; do
  log "    $CLAUDE_DIR/skills/$_s/"
done
log "    $CLAUDE_DIR/starter-kit/"
log "    Kit hook entries in $CLAUDE_DIR/settings.json"
log ""
log "  Will NOT touch:"
log "    All other files in ~/.claude (MEMORY.md, projects/, etc.)"
if [[ -n "$VAULT_ROOT" ]]; then
  log "    Vault at $VAULT_ROOT"
else
  log "    Your vault (pointer file absent — path unknown)"
fi
log ""

if ! ask "Remove all kit-managed files listed above?"; then
  log "  Aborted. No changes made."
  exit 0
fi

log ""

# ---------------------------------------------------------------------------
# Step 3: Remove kit hook files
# ---------------------------------------------------------------------------
log "${BOLD}Step 3: Removing kit hook files${RESET}"

for _h in "${KIT_HOOKS[@]}"; do
  _path="$CLAUDE_DIR/hooks/$_h"
  if [ -f "$_path" ]; then
    run rm -f "$_path"
    $DRY_RUN || log_ok "Removed $_path"
  else
    log "    (not present: $_path)"
  fi
done

for _l in "${KIT_HOOK_LIB[@]}"; do
  _path="$CLAUDE_DIR/hooks/lib/$_l"
  if [ -f "$_path" ]; then
    run rm -f "$_path"
    $DRY_RUN || log_ok "Removed $_path"
  else
    log "    (not present: $_path)"
  fi
done

log ""

# ---------------------------------------------------------------------------
# Step 4: Remove kit skill directories
# ---------------------------------------------------------------------------
log "${BOLD}Step 4: Removing kit skill directories${RESET}"

for _s in "${KIT_SKILLS[@]}"; do
  _path="$CLAUDE_DIR/skills/$_s"
  if [ -d "$_path" ]; then
    run rm -rf "$_path"
    $DRY_RUN || log_ok "Removed $_path/"
  else
    log "    (not present: $_path/)"
  fi
done

log ""

# ---------------------------------------------------------------------------
# Step 5: Remove pointer directory
# ---------------------------------------------------------------------------
log "${BOLD}Step 5: Removing pointer directory${RESET}"

if [ -d "$CLAUDE_DIR/starter-kit" ]; then
  run rm -rf "$CLAUDE_DIR/starter-kit"
  $DRY_RUN || log_ok "Removed $CLAUDE_DIR/starter-kit/"
else
  log "    (not present: $CLAUDE_DIR/starter-kit/)"
fi

log ""

# ---------------------------------------------------------------------------
# Step 6: Remove kit hook registrations from settings.json
# ---------------------------------------------------------------------------
log "${BOLD}Step 6: Pruning kit hooks from settings.json${RESET}"

SETTINGS_PATH="$CLAUDE_DIR/settings.json"
if [ -f "$SETTINGS_PATH" ]; then
  if $DRY_RUN; then
    log_dry "python3: remove kit hook registrations from $SETTINGS_PATH by command basename"
  else
    python3 - "$SETTINGS_PATH" <<'PYEOF'
import json, sys, os

settings_path = sys.argv[1]
kit_basenames = {
    'block-secrets.py',
    'command-guard.py',
    'secret-guard.py',
    'index-enforcer.py',
    'file-naming-check.py',
    'claude-md-hygiene.py',
    'auto-stage.sh',
    'auto-commit.sh',
    'helper-mode.py',
    'pre-compact.sh',
    'tool-module-brief.py',
    'writing-lint-posttooluse.py',
}

def cmd_basename(cmd):
    first_token = cmd.split()[0] if cmd else ''
    return os.path.basename(first_token)

try:
    with open(settings_path) as f:
        settings = json.load(f)
except json.JSONDecodeError as e:
    print(f"  [warn] settings.json is malformed, cannot prune hooks: {e}", file=sys.stderr)
    sys.exit(0)

hooks = settings.get('hooks', {})
changed = False

for event_type in list(hooks.keys()):
    entries = hooks[event_type]
    new_entries = []
    for entry in entries:
        filtered_hooks = [
            h for h in entry.get('hooks', [])
            if cmd_basename(h.get('command', '')) not in kit_basenames
        ]
        if len(filtered_hooks) == len(entry.get('hooks', [])):
            # No kit hooks in this entry — keep as-is
            new_entries.append(entry)
        elif filtered_hooks:
            # Partial: keep entry but with kit hooks stripped out
            new_entry = dict(entry)
            new_entry['hooks'] = filtered_hooks
            new_entries.append(new_entry)
            changed = True
        else:
            # Every hook in this entry was a kit hook — drop the entry entirely
            changed = True

    if new_entries != entries:
        hooks[event_type] = new_entries
        changed = True

    # Remove empty event type keys
    if not hooks.get(event_type):
        del hooks[event_type]
        changed = True

if changed:
    settings['hooks'] = hooks
    with open(settings_path, 'w') as f:
        json.dump(settings, f, indent=2)
        f.write('\n')
    print("  [ok] Kit hook registrations removed from settings.json")
else:
    print("  [ok] No kit hook registrations found in settings.json")
PYEOF
  fi
else
  log "    (settings.json not present — nothing to prune)"
fi

log ""

# ---------------------------------------------------------------------------
# Step 7: CLAUDE.md — restore pre-kit version if a prior backup contains one
# ---------------------------------------------------------------------------
log "${BOLD}Step 7: CLAUDE.md${RESET}"

CLAUDE_MD="$CLAUDE_DIR/CLAUDE.md"
if [ -f "$CLAUDE_MD" ]; then
  # Look for the most recent backup made BEFORE this uninstall run.
  # The backup we just created is the newest; sed -n '2p' picks the prior one.
  PRIOR_BACKUP=$(ls -t "$HOME"/.claude-backup-*.tar.gz 2>/dev/null | sed -n '2p' || true)
  if [ -n "$PRIOR_BACKUP" ]; then
    if $DRY_RUN; then
      log_dry "check $PRIOR_BACKUP for .claude/CLAUDE.md — restore if found, else remove"
    else
      if tar -tzf "$PRIOR_BACKUP" .claude/CLAUDE.md &>/dev/null 2>&1; then
        # A CLAUDE.md existed before the kit was installed — restore it
        if tar -xzf "$PRIOR_BACKUP" -C "$HOME" .claude/CLAUDE.md 2>/dev/null; then
          log_ok "CLAUDE.md restored from pre-kit backup: $PRIOR_BACKUP"
        else
          log_warn "Could not extract CLAUDE.md from $PRIOR_BACKUP — removing kit version"
          rm -f "$CLAUDE_MD"
          log_warn "  Restore manually: tar -xzf '$PRIOR_BACKUP' -C '$HOME' .claude/CLAUDE.md"
        fi
      else
        # Kit installed CLAUDE.md fresh (no prior version) — just remove it
        rm -f "$CLAUDE_MD"
        log_ok "Kit CLAUDE.md removed (no prior CLAUDE.md in backup to restore)"
        log "  Full backup: tar -xzf '$BACKUP_PATH' -C '$HOME' .claude/CLAUDE.md"
      fi
    fi
  else
    # No prior backup found
    run rm -f "$CLAUDE_MD"
    if $DRY_RUN; then
      log_dry "No prior backup found — remove $CLAUDE_MD"
    else
      log_warn "CLAUDE.md removed. Backup from this run: $BACKUP_PATH"
      log_warn "  Restore manually: tar -xzf '$BACKUP_PATH' -C '$HOME' .claude/CLAUDE.md"
    fi
  fi
else
  log "    (CLAUDE.md not present — nothing to restore)"
fi

log ""

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
log "======================================"
if $DRY_RUN; then
  log "${YELLOW}${BOLD}Dry run complete — no files were changed${RESET}"
else
  log "${GREEN}${BOLD}Uninstall complete${RESET}"
fi
log "======================================"
log ""
if [[ -n "$VAULT_ROOT" ]]; then
  log "  Your vault at ${BOLD}$VAULT_ROOT${RESET} is untouched."
  log "  To remove it manually: rm -rf '$VAULT_ROOT'"
else
  log "  The vault was not touched (pointer file was absent or unreadable)."
  log "  Remove your vault manually if desired."
fi
log ""
if ! $DRY_RUN; then
  log "  Backup from this run: $BACKUP_PATH"
  log "  Full rollback:        tar -xzf '$BACKUP_PATH' -C '$HOME'"
fi
log ""
