#!/bin/bash
# Auto-stage files modified by Claude Code.
# Input: JSON on stdin with tool_input.file_path
# Stages the file into ITS OWN owning git repo (git rev-parse --show-toplevel),
# so the user never has to think about git. Files in no repo at all are skipped.
# Staging failures are logged, never silently swallowed.
LOG="$HOME/.claude/logs/auto-stage.log"
mkdir -p "$(dirname "$LOG")" 2>/dev/null
FILE_PATH=$(cat | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('file_path',''))" 2>/dev/null)
if [ -n "$FILE_PATH" ] && [ -f "$FILE_PATH" ]; then
  TOP=$(cd "$(dirname "$FILE_PATH")" && git rev-parse --show-toplevel 2>/dev/null)
  if [ -n "$TOP" ]; then
    if ! git -C "$TOP" add "$FILE_PATH" 2>>"$LOG"; then
      echo "$(date -Iseconds) auto-stage FAILED: repo=$TOP file=$FILE_PATH" >> "$LOG"
    fi
  fi
fi
exit 0
