#!/usr/bin/env bash
# bootstrap.sh — Claude Code Starter Kit: prerequisite installer
#
# NOTE: Claude Code requires a PAID Anthropic account (Claude Pro or a team plan).
#       Sign up at https://www.anthropic.com before continuing.
#
# This script installs the prerequisites for setup.sh on a brand-new machine.
# It does NOT replace setup.sh — it just gets you to the starting line.
# Each step confirms before running and can be skipped if the tool is already present.
#
# Usage:
#   ./bootstrap.sh            interactive (confirms before each install)
#   ./bootstrap.sh --yes      skip confirmation prompts
#   ./bootstrap.sh --dry-run  print what would be done, change nothing
#
# Steps (each skipped automatically if already present):
#   1. git
#   2. python3 + pip
#   3. nvm + Node 20
#      (verify current nvm installer at https://github.com/nvm-sh/nvm)
#   4. Claude Code CLI (npm install -g @anthropic-ai/claude-code)
#
# After bootstrap completes:
#   1. Open a new terminal (or run: source ~/.nvm/nvm.sh)
#   2. Run: claude login
#   3. Run: ./setup.sh

set -euo pipefail

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
DRY_RUN=false
YES=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=true; shift ;;
    --yes|-y)  YES=true;     shift ;;
    -h|--help)
      sed -n '2,24p' "${BASH_SOURCE[0]}"
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
# OS detection — fail loud on unsupported platforms
# ---------------------------------------------------------------------------
OS_TYPE=""
case "$(uname -s)" in
  Linux*)
    if grep -qi microsoft /proc/version 2>/dev/null; then
      OS_TYPE="wsl"
    else
      OS_TYPE="linux"
    fi
    ;;
  Darwin*)
    OS_TYPE="macos"
    ;;
  *)
    log_err "Unsupported OS: $(uname -s)"
    log "  bootstrap.sh supports Linux (apt), macOS (brew), and WSL."
    log "  On Windows, open a WSL terminal (Ubuntu) and run this script there."
    exit 1
    ;;
esac

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------
log ""
log "${BOLD}Claude Code Starter Kit — prerequisite installer${RESET}"
log "=================================================="
log ""
log "  ${BOLD}NOTE:${RESET} Claude Code requires a paid Anthropic account (Claude Pro or team plan)."
log "  Sign up at https://www.anthropic.com before continuing."
log ""
if $DRY_RUN; then
  log "${YELLOW}DRY-RUN MODE: no changes will be made${RESET}"
  log ""
fi
log "  Detected OS: $OS_TYPE"
log ""

# ---------------------------------------------------------------------------
# Step 1: git
# ---------------------------------------------------------------------------
log "${BOLD}Step 1: git${RESET}"

if command -v git &>/dev/null; then
  log_ok "git already installed: $(git --version)"
else
  if ask "Install git?"; then
    if $DRY_RUN; then
      case "$OS_TYPE" in
        linux|wsl) log_dry "sudo apt-get update && sudo apt-get install -y git" ;;
        macos)     log_dry "brew install git" ;;
      esac
    else
      case "$OS_TYPE" in
        linux|wsl)
          sudo apt-get update -qq && sudo apt-get install -y git || \
            log_warn "apt install git failed — install manually: sudo apt install git"
          ;;
        macos)
          brew install git || log_warn "brew install git failed — install manually."
          ;;
      esac
      command -v git &>/dev/null && log_ok "git installed" || \
        log_warn "git still not found. You may need to restart your shell."
    fi
  else
    log_warn "Skipping git install."
  fi
fi

# ---------------------------------------------------------------------------
# Step 2: python3 + pip
# ---------------------------------------------------------------------------
log ""
log "${BOLD}Step 2: python3 + pip${RESET}"

if command -v python3 &>/dev/null; then
  log_ok "python3 already installed: $(python3 --version)"
else
  if ask "Install python3?"; then
    if $DRY_RUN; then
      case "$OS_TYPE" in
        linux|wsl) log_dry "sudo apt-get install -y python3 python3-pip" ;;
        macos)     log_dry "brew install python3" ;;
      esac
    else
      case "$OS_TYPE" in
        linux|wsl)
          sudo apt-get install -y python3 python3-pip || \
            log_warn "apt install python3 failed — install manually: sudo apt install python3 python3-pip"
          ;;
        macos)
          brew install python3 || log_warn "brew install python3 failed."
          ;;
      esac
      command -v python3 &>/dev/null && log_ok "python3 installed" || \
        log_warn "python3 still not found."
    fi
  else
    log_warn "Skipping python3 install."
  fi
fi

# pip (separate check — python3 may be present but pip missing)
if command -v python3 &>/dev/null && ! python3 -m pip --version &>/dev/null 2>&1; then
  log_warn "pip not found separately from python3."
  if ask "Install pip?"; then
    if $DRY_RUN; then
      case "$OS_TYPE" in
        linux|wsl) log_dry "sudo apt-get install -y python3-pip" ;;
        macos)     log_dry "python3 -m ensurepip --upgrade" ;;
      esac
    else
      case "$OS_TYPE" in
        linux|wsl)
          sudo apt-get install -y python3-pip || log_warn "apt install pip failed."
          ;;
        macos)
          python3 -m ensurepip --upgrade || log_warn "ensurepip failed."
          ;;
      esac
    fi
  else
    log_warn "Skipping pip install."
  fi
fi

# ---------------------------------------------------------------------------
# Step 3: nvm + Node 20
# ---------------------------------------------------------------------------
log ""
log "${BOLD}Step 3: nvm + Node 20${RESET}"
log "  nvm (Node Version Manager) is the recommended way to install and manage Node."
log "  Verify the current installer at: https://github.com/nvm-sh/nvm"
log ""

NVM_DIR="${NVM_DIR:-$HOME/.nvm}"

# Source nvm if it is already installed
if [ -s "$NVM_DIR/nvm.sh" ]; then
  log_ok "nvm already installed"
  # shellcheck source=/dev/null
  source "$NVM_DIR/nvm.sh" 2>/dev/null || true
else
  if ask "Install nvm?"; then
    NVM_INSTALL_URL="https://raw.githubusercontent.com/nvm-sh/nvm/HEAD/install.sh"
    if $DRY_RUN; then
      log_dry "curl -o- $NVM_INSTALL_URL | bash"
    else
      curl -o- "$NVM_INSTALL_URL" | bash || \
        log_warn "nvm install failed — see https://github.com/nvm-sh/nvm"
      if [ -s "$NVM_DIR/nvm.sh" ]; then
        # shellcheck source=/dev/null
        source "$NVM_DIR/nvm.sh" 2>/dev/null || true
        log_ok "nvm installed"
      else
        log_warn "nvm not found after install. You may need to restart your shell, then run: nvm install 20"
      fi
    fi
  else
    log_warn "Skipping nvm install."
  fi
fi

# Node 20 via nvm
if command -v node &>/dev/null; then
  NODE_VER=$(node --version)
  NODE_MAJOR=$(echo "$NODE_VER" | sed 's/v//' | cut -d. -f1)
  if [ "$NODE_MAJOR" -ge 18 ]; then
    log_ok "node $NODE_VER already installed and meets the minimum (18+)"
  else
    log_warn "node $NODE_VER is below the required minimum (18+)."
    if ask "Upgrade to Node 20 via nvm?"; then
      if $DRY_RUN; then
        log_dry "nvm install 20 && nvm use 20 && nvm alias default 20"
      elif [ -s "$NVM_DIR/nvm.sh" ]; then
        source "$NVM_DIR/nvm.sh" 2>/dev/null || true
        nvm install 20 && nvm use 20 && nvm alias default 20 || \
          log_warn "nvm install 20 failed — run manually: nvm install 20"
        command -v node &>/dev/null && log_ok "node $(node --version) installed"
      else
        log_warn "nvm not available. Install nvm first, then run: nvm install 20"
      fi
    fi
  fi
else
  if ask "Install Node 20 via nvm?"; then
    if $DRY_RUN; then
      log_dry "nvm install 20 && nvm use 20 && nvm alias default 20"
    elif [ -s "$NVM_DIR/nvm.sh" ]; then
      source "$NVM_DIR/nvm.sh" 2>/dev/null || true
      nvm install 20 && nvm use 20 && nvm alias default 20 || \
        log_warn "nvm install 20 failed — after sourcing nvm, run: nvm install 20"
      command -v node &>/dev/null && log_ok "node $(node --version) installed"
    else
      log_warn "nvm not found. Install nvm first (Step 3 above), then open a new shell and run: nvm install 20"
    fi
  else
    log_warn "Skipping Node install."
  fi
fi

# ---------------------------------------------------------------------------
# Step 4: Claude Code CLI
# ---------------------------------------------------------------------------
log ""
log "${BOLD}Step 4: Claude Code CLI${RESET}"

if command -v claude &>/dev/null; then
  log_ok "Claude Code already installed: $(claude --version 2>/dev/null || echo 'version unknown')"
else
  if ask "Install Claude Code? (npm install -g @anthropic-ai/claude-code)"; then
    if $DRY_RUN; then
      log_dry "npm install -g @anthropic-ai/claude-code"
    elif command -v npm &>/dev/null; then
      npm install -g @anthropic-ai/claude-code || \
        log_warn "npm install failed — try: npm install -g @anthropic-ai/claude-code"
      command -v claude &>/dev/null && log_ok "Claude Code installed" || \
        log_warn "claude CLI not found after install. You may need to restart your shell."
    else
      log_warn "npm not found. Install Node first (Step 3), then run: npm install -g @anthropic-ai/claude-code"
    fi
  else
    log_warn "Skipping Claude Code install."
  fi
fi

# ---------------------------------------------------------------------------
# Step 5: gitleaks (OPTIONAL, non-fatal)
# ---------------------------------------------------------------------------
# gitleaks is a secret scanner. The secret-guard hook runs it before every git
# commit/push and blocks if a password or key would be committed. If gitleaks is
# not installed the hook simply does nothing (it fails open), so this step is
# optional and never fatal.
log ""
log "${BOLD}Step 5: gitleaks (optional secret scanner)${RESET}"
if command -v gitleaks &>/dev/null; then
  log_ok "gitleaks already installed: $(gitleaks version 2>/dev/null || echo installed)"
else
  if ask "Install gitleaks? (optional; adds a safety net against committing secrets)"; then
    if $DRY_RUN; then
      case "$OS_TYPE" in
        linux|wsl) log_dry "sudo apt-get install -y gitleaks (or download a release binary)" ;;
        macos)     log_dry "brew install gitleaks" ;;
      esac
    else
      case "$OS_TYPE" in
        linux|wsl)
          sudo apt-get install -y gitleaks 2>/dev/null || \
            log_warn "gitleaks not in apt — install a release binary from github.com/gitleaks/gitleaks (optional; the guard fails open without it)"
          ;;
        macos)
          brew install gitleaks || \
            log_warn "brew install gitleaks failed (optional; the guard fails open without it)"
          ;;
      esac
      command -v gitleaks &>/dev/null && log_ok "gitleaks installed" || \
        log_warn "gitleaks not installed — the commit secret-scan is skipped until it is (non-fatal)"
    fi
  else
    log_warn "Skipping gitleaks (the commit secret-scan will be skipped; non-fatal)."
  fi
fi

# ---------------------------------------------------------------------------
# Done — next steps
# ---------------------------------------------------------------------------
log ""
log "======================================"
log "${GREEN}${BOLD}Bootstrap complete${RESET}"
log "======================================"
log ""
log "  Next steps:"
log ""
log "  1. Open a new terminal (or run: source ~/.nvm/nvm.sh) so nvm and node"
log "     are available in your PATH."
log ""
log "  2. Log in to Claude Code:"
log "     ${BOLD}claude login${RESET}"
log ""
log "  3. Run the main installer:"
log "     ${BOLD}./setup.sh${RESET}"
log ""
if [ "$OS_TYPE" = "wsl" ]; then
  log "  WSL note: run this script and all Claude Code sessions inside WSL (Ubuntu),"
  log "  not in PowerShell or Command Prompt. The kit uses Linux utilities"
  log "  (xdg-open, xclip, gio) that only work inside WSL."
  log ""
fi
