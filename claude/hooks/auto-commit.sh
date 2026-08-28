#!/bin/bash
# Stop hook: silently commit the user's work at the end of every Claude turn.
#
# auto-stage.sh only STAGES edited files (git add). Staging alone leaves history
# empty, and a single `git reset --hard` would then wipe the user's work with no
# way back. This hook commits the staged changes so every turn's work lands in
# git history with zero action from a non-technical user. It is NOT a manual
# /sync step (which they would not reliably run). The user never types git.
#
# Commits the configured vault repo (the user's documents). Only commits when
# there is something to commit; otherwise it does nothing. Always exits 0, never
# blocks or interrupts a turn.
LOG="$HOME/.claude/logs/auto-commit.log"
mkdir -p "$(dirname "$LOG")" 2>/dev/null

HOOKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VAULT="$(python3 -c "import sys; sys.path.insert(0, '$HOOKDIR/lib'); import hook_config; print(hook_config.vault_root())" 2>/dev/null)"

[ -z "$VAULT" ] && exit 0
[ -d "$VAULT/.git" ] || exit 0

# Stage anything the edit hook missed, then commit only if something is staged.
git -C "$VAULT" add -A 2>>"$LOG"
if ! git -C "$VAULT" diff --cached --quiet 2>/dev/null; then
  if ! git -C "$VAULT" commit -q -m "Claude auto-save $(date '+%Y-%m-%d %H:%M')" 2>>"$LOG"; then
    echo "$(date -Iseconds) auto-commit FAILED in $VAULT" >> "$LOG"
  fi
fi
exit 0
