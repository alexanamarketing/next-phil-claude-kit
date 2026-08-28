#!/usr/bin/env bash
# setup.sh — Claude Code Starter Kit installer
#
# Usage:
#   ./setup.sh                          interactive (prompts for vault root)
#   ./setup.sh --vault-root ~/myvault   non-interactive vault path
#   ./setup.sh --yes                    skip all confirmation prompts
#   ./setup.sh --dry-run                print every action, change nothing
#   ./setup.sh --dry-run --vault-root ~/myvault --yes
#
# What it does:
#   1. Checks prerequisites (python3 3.8+, pyyaml, node 18+, claude CLI)
#   2. Detects OS and sets default clipboard / open / trash commands
#   3. Instantiates the vault skeleton at your chosen vault root
#   4. Writes config.yaml (vault_root + OS commands filled in, via Python)
#   5. Writes ~/.claude/starter-kit/config.json (pointer file for hooks and skills)
#   6. Backs up ~/.claude, then copies skills/hooks/CLAUDE.md into it
#   7. Merges settings.fragment.json into ~/.claude/settings.json (never overwrites)
#   8. Runs doctor.py to verify the install
#   9. Attempts the recommended mattpocock-skills plugin install (non-fatal)
#  10. Prints a first-steps summary

set -euo pipefail

# ---------------------------------------------------------------------------
# Locate repo root (directory containing this script)
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
VAULT_ROOT_ARG=""
DRY_RUN=false
YES=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --vault-root)
      if [[ $# -lt 2 ]] || [[ -z "${2:-}" ]]; then
        echo "Error: --vault-root requires a non-empty path argument" >&2
        exit 1
      fi
      VAULT_ROOT_ARG="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --yes|-y)
      YES=true
      shift
      ;;
    -h|--help)
      sed -n '2,12p' "${BASH_SOURCE[0]}"
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
log_action() { echo -e "${BOLD}  -->  ${RESET}$*"; }
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

# Expand ~ in a path without eval
expand_path() {
  local p="$1"
  case "$p" in
    "~/"*) echo "$HOME/${p#~/}" ;;
    "~")   echo "$HOME" ;;
    *)     echo "$p" ;;
  esac
}

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------
log ""
log "${BOLD}Claude Code Starter Kit — installer${RESET}"
log "======================================"
if $DRY_RUN; then
  log "${YELLOW}DRY-RUN MODE: no files will be written${RESET}"
  log ""
fi

# ---------------------------------------------------------------------------
# 1. Prerequisite checks
# ---------------------------------------------------------------------------
log ""
log "${BOLD}Step 1 of 8: Checking prerequisites${RESET}"

PREREQS_OK=true

# python3 (3.8+ required)
if ! command -v python3 &>/dev/null; then
  log_err "python3 not found."
  log "  Fix: install Python 3.8+ via your package manager:"
  log "    Ubuntu/Debian:  sudo apt install python3 python3-pip"
  log "    macOS:          brew install python3"
  log "    pyenv:          curl https://pyenv.run | bash && pyenv install 3.11 && pyenv global 3.11"
  PREREQS_OK=false
else
  PYTHON_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
  PYTHON_MAJOR=$(python3 -c 'import sys; print(sys.version_info.major)')
  PYTHON_MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')
  if [ "$PYTHON_MAJOR" -lt 3 ] || { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]; }; then
    log_err "python3 $PYTHON_VER found, but 3.8+ is required."
    log "  Fix:"
    log "    Ubuntu/Debian:  sudo apt install python3 python3-pip"
    log "    macOS:          brew upgrade python3"
    log "    pyenv:          pyenv install 3.11 && pyenv global 3.11"
    PREREQS_OK=false
  else
    log_ok "python3 $PYTHON_VER"
  fi
fi

# pyyaml — best-effort; a failure here must never abort setup
if $PREREQS_OK && ! python3 -c "import yaml" &>/dev/null 2>&1; then
  log_warn "pyyaml not installed. Hooks will use the built-in fallback parser (fine for most uses)."
  if $DRY_RUN; then
    log_dry "python3 -m pip install --user pyyaml  (best-effort, non-fatal)"
  elif python3 -m pip --version &>/dev/null 2>&1; then
    log_action "Installing pyyaml (best-effort)..."
    python3 -m pip install --user pyyaml 2>/dev/null || true
    if python3 -c "import yaml" &>/dev/null 2>&1; then
      log_ok "pyyaml installed"
    else
      log_warn "pyyaml install attempt failed. The starter kit will still work (fallback parser active)."
    fi
  else
    log_warn "pip not found or externally managed — skipping pyyaml. The starter kit will still work."
  fi
else
  $PREREQS_OK && log_ok "pyyaml"
fi

# node (18+ required)
if ! command -v node &>/dev/null; then
  log_err "node not found."
  log "  Fix: install via nvm (recommended):"
  log "    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/HEAD/install.sh | bash"
  log "    # Verify current installer at https://github.com/nvm-sh/nvm"
  log "    source ~/.nvm/nvm.sh && nvm install 20 && nvm use 20"
  PREREQS_OK=false
else
  NODE_VER=$(node --version)
  NODE_MAJOR=$(echo "$NODE_VER" | sed 's/v//' | cut -d. -f1)
  if [ "$NODE_MAJOR" -lt 18 ]; then
    log_err "node $NODE_VER found, but 18+ is required."
    log "  Fix: upgrade via nvm:"
    log "    nvm install 20 && nvm use 20 && nvm alias default 20"
    log "    # See https://github.com/nvm-sh/nvm"
    PREREQS_OK=false
  else
    log_ok "node $NODE_VER"
  fi
fi

# npm
if ! command -v npm &>/dev/null; then
  log_err "npm not found (usually ships with node — reinstall node via nvm)."
  PREREQS_OK=false
else
  log_ok "npm $(npm --version)"
fi

# claude CLI
if ! command -v claude &>/dev/null; then
  log_err "Claude Code CLI not found."
  log "  Fix:"
  log "    npm install -g @anthropic-ai/claude-code"
  log "    claude login"
  log ""
  log "  Then re-run this script."
  PREREQS_OK=false
else
  log_ok "claude CLI ($(claude --version 2>/dev/null || echo 'version unknown'))"
fi

# settings.json validity check — fail early before writing any payload
if $PREREQS_OK && [ -f "$HOME/.claude/settings.json" ]; then
  if ! python3 -m json.tool "$HOME/.claude/settings.json" > /dev/null 2>&1; then
    log_err "~/.claude/settings.json exists but contains invalid JSON."
    log "  Fix or remove $HOME/.claude/settings.json and re-run setup.sh."
    PREREQS_OK=false
  else
    log_ok "~/.claude/settings.json is valid JSON"
  fi
fi

if ! $PREREQS_OK; then
  log ""
  log_err "One or more prerequisites are missing. Fix the errors above and re-run."
  exit 1
fi

# ---------------------------------------------------------------------------
# 2. OS detection
# ---------------------------------------------------------------------------
log ""
log "${BOLD}Step 2 of 8: Detecting OS${RESET}"

OS_OPEN=""
OS_COPY=""
OS_TRASH=""
TRASH_MISSING=false

case "$(uname -s)" in
  Linux*)
    OS_OPEN="xdg-open"
    # Prefer wl-copy on Wayland, fall back to xclip
    if [ -n "${WAYLAND_DISPLAY:-}" ] && command -v wl-copy &>/dev/null; then
      OS_COPY="wl-copy"
    elif command -v xclip &>/dev/null; then
      OS_COPY="xclip -selection clipboard"
    else
      OS_COPY="xclip -selection clipboard"
      log_warn "xclip not found — clipboard commands may fail. Fix: sudo apt install xclip"
    fi
    OS_TRASH="gio trash"
    log_ok "Linux detected: os_open=$OS_OPEN  os_copy='$OS_COPY'  os_trash=$OS_TRASH"
    ;;
  Darwin*)
    OS_OPEN="open"
    OS_COPY="pbcopy"
    OS_TRASH="trash"
    if ! command -v trash &>/dev/null; then
      TRASH_MISSING=true
      log_warn "macOS: 'trash' command not found. Install: brew install trash"
    fi
    log_ok "macOS detected: os_open=$OS_OPEN  os_copy=$OS_COPY  os_trash=$OS_TRASH"
    ;;
  *)
    log_warn "Unrecognised OS ($(uname -s)). Defaulting to Linux commands."
    log_warn "On Windows, use WSL and run this script inside a WSL terminal."
    OS_OPEN="xdg-open"
    OS_COPY="xclip -selection clipboard"
    OS_TRASH="gio trash"
    ;;
esac

# ---------------------------------------------------------------------------
# 3. Vault root
# ---------------------------------------------------------------------------
log ""
log "${BOLD}Step 3 of 8: Vault root${RESET}"

if [ -n "$VAULT_ROOT_ARG" ]; then
  VAULT_ROOT="$(expand_path "$VAULT_ROOT_ARG")"
  log_ok "Using --vault-root: $VAULT_ROOT"
else
  log "  Your vault is the folder that holds your projects (active/, inactive/, etc.)."
  log "  Press Enter to accept the default, or type a custom path."
  read -r -p "  Vault root [~/vault]: " VAULT_ROOT_INPUT
  if [ -z "$VAULT_ROOT_INPUT" ]; then
    VAULT_ROOT="$(expand_path "~/vault")"
  else
    VAULT_ROOT="$(expand_path "$VAULT_ROOT_INPUT")"
  fi
  log_ok "Vault root: $VAULT_ROOT"
fi

# ---------------------------------------------------------------------------
# 4. Instantiate vault skeleton
# ---------------------------------------------------------------------------
log ""
log "${BOLD}Step 4 of 8: Vault skeleton${RESET}"

SKELETON_SRC="$SCRIPT_DIR/vault-skeleton"

if [ -d "$VAULT_ROOT" ] && [ -n "$(ls -A "$VAULT_ROOT" 2>/dev/null)" ]; then
  log_warn "Vault directory already exists and is not empty: $VAULT_ROOT"
  if ! ask "Merge skeleton into existing vault? (existing files will NOT be overwritten)"; then
    log_warn "Skipping vault skeleton copy."
    log_warn "Vault scripts (doctor.py etc.) will NOT be installed; hooks referencing <vault>/scripts will fail."
    log "  To add scripts only:  cp -rn '$SKELETON_SRC/scripts' '$VAULT_ROOT/'"
  else
    if $DRY_RUN; then
      log_dry "cp -rn '$SKELETON_SRC/.' '$VAULT_ROOT/'"
    else
      cp -rn "$SKELETON_SRC/." "$VAULT_ROOT/"
      log_ok "Vault skeleton merged (existing files preserved)"
    fi
  fi
else
  run mkdir -p "$VAULT_ROOT"
  if $DRY_RUN; then
    log_dry "cp -r '$SKELETON_SRC/.' '$VAULT_ROOT/'"
  else
    cp -r "$SKELETON_SRC/." "$VAULT_ROOT/"
    log_ok "Vault skeleton installed at $VAULT_ROOT"
  fi
fi

# Replace [INSTALL-DATE] placeholder in system project files
INSTALL_DATE=$(date +%Y-%m-%d)
SYSTEM_DIR="$VAULT_ROOT/system"
if $DRY_RUN; then
  log_dry "replace [INSTALL-DATE] with $INSTALL_DATE in $SYSTEM_DIR/*.md"
elif [ -d "$SYSTEM_DIR" ]; then
  python3 - "$SYSTEM_DIR" "$INSTALL_DATE" <<'PYEOF'
import sys, os
system_dir, install_date = sys.argv[1], sys.argv[2]
for fname in os.listdir(system_dir):
    if not fname.endswith('.md'):
        continue
    fpath = os.path.join(system_dir, fname)
    with open(fpath) as fh:
        content = fh.read()
    if '[INSTALL-DATE]' not in content:
        continue
    with open(fpath, 'w') as fh:
        fh.write(content.replace('[INSTALL-DATE]', install_date))
PYEOF
  log_ok "[INSTALL-DATE] replaced with $INSTALL_DATE in system/*.md"
fi

# Make the vault git-backed so the user's work is saved automatically and never
# lost. auto-stage.sh stages every edit and the Stop hook auto-commit.sh commits
# it, all invisibly (the user never types a git command). Init only if the vault
# is not already a repo, with a neutral local identity, then make a first commit.
if $DRY_RUN; then
  log_dry "git init '$VAULT_ROOT' (if not already a repo) + neutral identity + initial commit"
elif command -v git >/dev/null 2>&1; then
  if [ ! -d "$VAULT_ROOT/.git" ]; then
    git -C "$VAULT_ROOT" init -q 2>/dev/null || true
    git -C "$VAULT_ROOT" config user.name "Claude Code" 2>/dev/null || true
    git -C "$VAULT_ROOT" config user.email "claude-code@localhost" 2>/dev/null || true
    git -C "$VAULT_ROOT" add -A 2>/dev/null || true
    if ! git -C "$VAULT_ROOT" diff --cached --quiet 2>/dev/null; then
      git -C "$VAULT_ROOT" commit -q -m "Initial vault ($INSTALL_DATE)" 2>/dev/null || true
    fi
    log_ok "Vault is now git-backed (your work saves itself; you never type git)"
  else
    log "  Vault is already a git repo — leaving it as-is"
  fi
else
  log_warn "git not found — skipping vault version history (install git, then re-run to enable it)"
fi

# Copy kit docs into <vault>/docs/ so they are available after the repo is deleted.
# GAP-ANALYSIS.md is intentionally NOT copied: it is build provenance for the
# developer and stays repo-only.
VAULT_DOCS_DIR="$VAULT_ROOT/docs"
for _doc in "ARCHITECTURE.md"; do
  _src="$SCRIPT_DIR/docs/$_doc"
  _dst="$VAULT_DOCS_DIR/$_doc"
  if [ -f "$_src" ]; then
    if $DRY_RUN; then
      log_dry "mkdir -p '$VAULT_DOCS_DIR' && cp '$_src' '$_dst'"
    else
      mkdir -p "$VAULT_DOCS_DIR"
      cp "$_src" "$_dst"
      log_ok "Copied docs/$_doc into vault"
    fi
  fi
done

# ---------------------------------------------------------------------------
# 5. Write config.yaml
# ---------------------------------------------------------------------------
log ""
log "${BOLD}Step 5 of 8: config.yaml${RESET}"

CONFIG_PATH="$VAULT_ROOT/config.yaml"

if [ -f "$CONFIG_PATH" ]; then
  log_warn "config.yaml already exists at $CONFIG_PATH — skipping (not overwriting)."
  log "  To regenerate: delete $CONFIG_PATH and re-run this script."
else
  if $DRY_RUN; then
    log_dry "write config.yaml to $CONFIG_PATH (vault_root=$VAULT_ROOT, os_open=$OS_OPEN, ...)"
  else
    python3 - "$SCRIPT_DIR/config.example.yaml" "$CONFIG_PATH" \
        "$VAULT_ROOT" "$OS_OPEN" "$OS_COPY" "$OS_TRASH" <<'PYEOF'
import sys

src_path = sys.argv[1]
dst_path = sys.argv[2]
vault    = sys.argv[3]
os_open  = sys.argv[4]
os_copy  = sys.argv[5]
os_trash = sys.argv[6]

def yaml_dquote(v):
    """Wrap value in YAML double quotes, escaping backslashes and double quotes."""
    return '"' + v.replace('\\', '\\\\').replace('"', '\\"') + '"'

with open(src_path) as f:
    lines = f.readlines()

out = []
for line in lines:
    stripped = line.lstrip()
    indent   = line[:len(line) - len(stripped)]
    if stripped.startswith('vault_root:'):
        out.append(f'{indent}vault_root: {yaml_dquote(vault)}\n')
    elif stripped.startswith('os_open:'):
        out.append(f'{indent}os_open: {yaml_dquote(os_open)}\n')
    elif stripped.startswith('os_copy:'):
        out.append(f'{indent}os_copy: {yaml_dquote(os_copy)}\n')
    elif stripped.startswith('os_trash:'):
        out.append(f'{indent}os_trash: {yaml_dquote(os_trash)}\n')
    else:
        out.append(line)

with open(dst_path, 'w') as f:
    f.writelines(out)
PYEOF
    log_ok "config.yaml written to $CONFIG_PATH"
  fi
fi

# Pointer file: records the vault root so hooks and skills can locate config.yaml
# on any machine without a hardcoded path or environment variable.
POINTER_DIR="$HOME/.claude/starter-kit"
POINTER_FILE="$POINTER_DIR/config.json"
if $DRY_RUN; then
  log_dry "mkdir -p '$POINTER_DIR' && write {\"vault_root\": \"$VAULT_ROOT\"} to $POINTER_FILE"
else
  mkdir -p "$POINTER_DIR"
  python3 -c "
import json, sys
with open(sys.argv[1], 'w') as fh:
    json.dump({'vault_root': sys.argv[2]}, fh, indent=2)
    fh.write('\n')
" "$POINTER_FILE" "$VAULT_ROOT"
  log_ok "Pointer file written: $POINTER_FILE"
fi

# ---------------------------------------------------------------------------
# 6. Back up and update ~/.claude
# ---------------------------------------------------------------------------
log ""
log "${BOLD}Step 6 of 8: ~/.claude payload${RESET}"

CLAUDE_DIR="$HOME/.claude"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_PATH="$HOME/.claude-backup-$TIMESTAMP.tar.gz"

if [ -d "$CLAUDE_DIR" ]; then
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
fi

# Create ~/.claude structure if absent
run mkdir -p "$CLAUDE_DIR/hooks/lib" "$CLAUDE_DIR/skills"

# CLAUDE.md — skip if already exists (full ~/.claude backup above preserves the original)
CLAUDE_MD_DEST="$CLAUDE_DIR/CLAUDE.md"
if [ -f "$CLAUDE_MD_DEST" ]; then
  log_warn "~/.claude/CLAUDE.md already exists — skipping; delete it and re-run to reinstall the kit version"
else
  if $DRY_RUN; then
    log_dry "copy claude/CLAUDE.md to $CLAUDE_MD_DEST"
  else
    cp "$SCRIPT_DIR/claude/CLAUDE.md" "$CLAUDE_MD_DEST"
    log_ok "CLAUDE.md installed"
  fi
fi

# Warn on reinstall before overwriting kit-managed hooks and skills
if ls "$CLAUDE_DIR/hooks/"*.py "$CLAUDE_DIR/hooks/"*.sh &>/dev/null 2>&1 || \
   [ -d "$CLAUDE_DIR/skills/project" ] || [ -d "$CLAUDE_DIR/skills/sync" ]; then
  log_warn "Overwriting kit hooks/skills in ~/.claude — any manual edits to them will be lost; your full backup above preserves them"
fi

# Copy hooks (including lib/ subdirectory)
if $DRY_RUN; then
  log_dry "cp -r '$SCRIPT_DIR/claude/hooks/.' '$CLAUDE_DIR/hooks/'"
else
  cp -r "$SCRIPT_DIR/claude/hooks/." "$CLAUDE_DIR/hooks/"
  chmod +x "$CLAUDE_DIR/hooks/"*.py "$CLAUDE_DIR/hooks/"*.sh 2>/dev/null || true
  log_ok "Hooks installed to ~/.claude/hooks/"
fi

# Copy skills
if $DRY_RUN; then
  log_dry "cp -r '$SCRIPT_DIR/claude/skills/.' '$CLAUDE_DIR/skills/'"
else
  cp -r "$SCRIPT_DIR/claude/skills/." "$CLAUDE_DIR/skills/"
  log_ok "Skills installed to ~/.claude/skills/"
fi

# Copy references (tool-module seeds, focus config). Merge without overwriting
# (cp -n) so a re-install never wipes the tool notes Claude has already learned.
if [ -d "$SCRIPT_DIR/claude/references" ]; then
  if $DRY_RUN; then
    log_dry "mkdir -p '$CLAUDE_DIR/references' && cp -rn '$SCRIPT_DIR/claude/references/.' '$CLAUDE_DIR/references/'"
  else
    mkdir -p "$CLAUDE_DIR/references"
    cp -rn "$SCRIPT_DIR/claude/references/." "$CLAUDE_DIR/references/"
    log_ok "References installed to ~/.claude/references/ (tool-module seeds preserved on re-install)"
  fi
fi

# Helper Mode default state: ON with a 7-day learning window, stamped install day.
# Skip if a state file already exists (matches the kit's no-overwrite idiom), so a
# re-install never resets a user who has already turned it off or moved past the week.
HELPER_STATE="$CLAUDE_DIR/helper-mode.json"
if [ -e "$HELPER_STATE" ]; then
  log "  Helper Mode state already present — leaving it as-is"
elif $DRY_RUN; then
  log_dry "write default Helper Mode state (on, window_days 7) to $HELPER_STATE"
else
  printf '{\n  "on": true,\n  "started": "%s",\n  "window_days": 7\n}\n' \
    "$(date +%Y-%m-%d)" > "$HELPER_STATE"
  log_ok "Helper Mode ON (plain-English learning week) — state at ~/.claude/helper-mode.json"
fi

# ---------------------------------------------------------------------------
# 7. Merge settings.fragment.json into ~/.claude/settings.json
# ---------------------------------------------------------------------------
log ""
log "${BOLD}Step 7 of 8: settings.json merge${RESET}"

SETTINGS_PATH="$CLAUDE_DIR/settings.json"
FRAGMENT_PATH="$SCRIPT_DIR/claude/settings.fragment.json"

if $DRY_RUN; then
  log_dry "merge $FRAGMENT_PATH into $SETTINGS_PATH (expanding \$HOME -> $HOME, no overwrites)"
else
  python3 - "$SETTINGS_PATH" "$FRAGMENT_PATH" "$HOME" <<'PYEOF'
import json
import sys
import os

settings_path = sys.argv[1]
fragment_path = sys.argv[2]
home = sys.argv[3]

# Load and expand $HOME in fragment
with open(fragment_path) as f:
    frag_text = f.read().replace('$HOME', home)
try:
    fragment = json.loads(frag_text)
except json.JSONDecodeError as e:
    print(f"  [error] Could not parse fragment: {e}", file=sys.stderr)
    sys.exit(1)

# Load existing settings.  If the file exists but is malformed, abort loudly
# rather than silently resetting it to {} — that would destroy the user's settings.
existing = {}
if os.path.exists(settings_path):
    try:
        with open(settings_path) as f:
            content = f.read()
        if content.strip():
            existing = json.loads(content)
            if not isinstance(existing, dict):
                print(f"  [error] {settings_path} exists but is not a JSON object.", file=sys.stderr)
                print(f"  Fix or remove it and re-run setup.sh.", file=sys.stderr)
                sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"  [error] {settings_path} exists but contains malformed JSON: {e}", file=sys.stderr)
        print(f"  Fix or remove {settings_path} and re-run setup.sh.", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"  [error] Cannot read {settings_path}: {e}", file=sys.stderr)
        sys.exit(1)

# Deep-merge hooks: for each event type, append entries whose commands
# are not already present in the existing hooks list.
frag_hooks = fragment.get('hooks', {})
existing_hooks = existing.setdefault('hooks', {})

for event_type, new_entries in frag_hooks.items():
    if event_type not in existing_hooks:
        existing_hooks[event_type] = new_entries
        continue

    # Dedupe by (event_type, command_basename) so $HOME-literal vs expanded paths
    # don't create duplicate entries on re-run.
    def _cmd_key(cmd):
        first = cmd.split()[0] if cmd else ''
        return os.path.basename(first)

    registered = set()
    for entry in existing_hooks[event_type]:
        for h in entry.get('hooks', []):
            registered.add(_cmd_key(h.get('command', '')))

    for entry in new_entries:
        entry_keys = {_cmd_key(h.get('command', '')) for h in entry.get('hooks', [])}
        if not entry_keys.intersection(registered):
            existing_hooks[event_type].append(entry)
            registered.update(entry_keys)

os.makedirs(os.path.dirname(settings_path), exist_ok=True)
with open(settings_path, 'w') as f:
    json.dump(existing, f, indent=2)
    f.write('\n')

print("  [ok] settings.json updated")
PYEOF
fi

# ---------------------------------------------------------------------------
# 8a. Doctor
# ---------------------------------------------------------------------------
log ""
log "${BOLD}Step 8 of 8: Verification (doctor)${RESET}"

DOCTOR_PY="$VAULT_ROOT/scripts/doctor.py"
DOCTOR_STRICT_EXIT=0

if $DRY_RUN; then
  log_dry "python3 '$DOCTOR_PY' --vault-root '$VAULT_ROOT'"
  log_dry "python3 '$DOCTOR_PY' --vault-root '$VAULT_ROOT' --strict  (exit code decides closing banner)"
elif [ -f "$DOCTOR_PY" ]; then
  log ""
  python3 "$DOCTOR_PY" --vault-root "$VAULT_ROOT" || true
  log ""
  python3 "$DOCTOR_PY" --vault-root "$VAULT_ROOT" --strict &>/dev/null || DOCTOR_STRICT_EXIT=$?
else
  log_warn "doctor.py not found at $DOCTOR_PY — skipping verification."
  log "  If the vault skeleton was not installed, the doctor script is missing."
fi

# ---------------------------------------------------------------------------
# 8b. Recommended step 2: Matt Pocock engineering skills plugin (non-fatal)
# ---------------------------------------------------------------------------
# Adds the full mattpocock-skills plugin. Most of it (tdd, diagnosing-bugs) is
# for people who write code; you may never use those, and that is fine. The one
# worth knowing is `grilling`: it stress-tests a decision by asking you one
# sharp question at a time (good for "should I take this listing at that price").
# Command syntax verified against Claude Code 2.1.250:
#   claude plugins marketplace add mattpocock/skills
#   claude plugins install mattpocock-skills@mattpocock
log ""
log "${BOLD}Recommended step 2: engineering skills plugin (grilling, and more)${RESET}"
log "  Adds Matt Pocock's skill pack. The useful one for you is 'grilling' (stress-test"
log "  a decision one question at a time). Installed via the Claude Code plugin marketplace."
log ""

MATTPOCOCK_OK=false

if $DRY_RUN; then
  log_dry "claude plugins marketplace add mattpocock/skills"
  log_dry "claude plugins install mattpocock-skills@mattpocock"
  MATTPOCOCK_OK=true
elif ! command -v claude >/dev/null 2>&1; then
  log_warn "claude CLI not found — skipping the plugin install (non-fatal)."
else
  log_action "Adding the mattpocock marketplace (mattpocock/skills)..."
  if claude plugins marketplace add mattpocock/skills 2>/dev/null; then
    log_action "Installing mattpocock-skills..."
    if claude plugins install mattpocock-skills@mattpocock 2>/dev/null; then
      MATTPOCOCK_OK=true
      log_ok "mattpocock-skills installed"
    else
      log_warn "plugin install step failed."
    fi
  else
    log_warn "Adding the marketplace failed (likely no network)."
  fi

  if ! $MATTPOCOCK_OK; then
    log ""
    log "  Manual install (run these two lines once you are online):"
    log "    claude plugins marketplace add mattpocock/skills"
    log "    claude plugins install mattpocock-skills@mattpocock"
    log ""
    log "  This is non-fatal. The core hooks and skills work without it."
  fi
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
log ""
log "======================================"
if [ "$DOCTOR_STRICT_EXIT" -ne 0 ]; then
  log "${YELLOW}${BOLD}Installation completed with blocking issues (see doctor output above)${RESET}"
else
  log "${GREEN}${BOLD}Installation complete${RESET}"
fi
log "======================================"
log ""
log "  Vault root:     $VAULT_ROOT"
log "  Config:         $VAULT_ROOT/config.yaml"
log "  Pointer:        $POINTER_FILE"
log "  Skills:         $CLAUDE_DIR/skills/"
log "  Hooks:          $CLAUDE_DIR/hooks/"
log "  Settings:       $CLAUDE_DIR/settings.json"
if [ -f "$BACKUP_PATH" ]; then
  log "  ~/.claude backup: $BACKUP_PATH"
fi
log ""
log "${BOLD}First 10 minutes:${RESET}"
log "  1. Start a Claude Code session: run 'claude' in your terminal."
log "  2. Type:  /project system"
log "     Claude will load the system meta-project and prompt you to fill out"
log "     ABOUT.md — do this first so every future session knows how to work with you."
log "  3. Type:  /new-project"
log "     Create your first real project."
log "  4. Work. End each session with /sync before /clear."
log ""
log "  Help mode is on by default. Turn it off any time with '/help off' inside a session."
log ""
log "  Edit $VAULT_ROOT/config.yaml to add shortcuts, adjust strictness, etc."
log ""
if ! $MATTPOCOCK_OK && ! $DRY_RUN; then
  log "${YELLOW}  Action needed: install mattpocock-skills manually (see Recommended step 2 above).${RESET}"
  log ""
fi
if $TRASH_MISSING; then
  log "${YELLOW}  Action needed: install 'trash' for safe delete on macOS: brew install trash${RESET}"
  log ""
fi
