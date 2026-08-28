#!/usr/bin/env bash
# check-hook-roster.sh — a WHITELIST diff, not a partial blocklist.
#
# Holds the exact intended set of hook code files and asserts that the actual
# contents of claude/hooks/ (recursive, code files only) EQUALS it. Any extra file
# (an excluded power-user / non-realtor hook that slipped in) OR any missing file
# (a dropped kit hook) is a failure. This is what guarantees none of the ~18
# excluded power-user / non-realtor hooks
# (next-project-guards, todo-intake-guard, reddit-guard, the web-build set, ...)
# and none of the dropped baseline pieces (markdown-rules.py, markdown-location.py,
# hot-doc-hygiene.py, frontmatter-guard.py) ever ship.
#
# Code files = *.py, *.sh, and the extensionless writing-lint CLI. Data sidecars
# (block-secrets-allow.txt) and runtime state are not code and are excluded.
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOKS="$REPO/claude/hooks"

# The intended roster (relative to claude/hooks/). Keep alphabetized.
ALLOWLIST=$(cat <<'EOF'
auto-commit.sh
auto-stage.sh
block-secrets.py
claude-md-hygiene.py
command-guard.py
file-naming-check.py
helper-mode.py
index-enforcer.py
lib/hook_config.py
pre-compact.sh
secret-guard.py
tool-module-brief.py
tool-module-learn.py
tool-module-new.py
tool_module_schema.py
tool_module_store.py
toolupdate_apply.py
writing-lint
writing-lint-posttooluse.py
EOF
)

# Actual code files under claude/hooks (recursive), excluding runtime state.
ACTUAL=$(find "$HOOKS" -type f \
    \( -name '*.py' -o -name '*.sh' -o -name 'writing-lint' \) \
    -not -path '*/state/*' -not -path '*/__pycache__/*' \
    | sed "s|$HOOKS/||" | sort)

WANT=$(printf '%s\n' "$ALLOWLIST" | sort)

extra=$(comm -13 <(printf '%s\n' "$WANT") <(printf '%s\n' "$ACTUAL"))
missing=$(comm -23 <(printf '%s\n' "$WANT") <(printf '%s\n' "$ACTUAL"))

fail=0
if [ -n "$extra" ]; then
  echo "HOOK ROSTER FAIL: unexpected hook file(s) present (not in the allowlist):"
  printf '  + %s\n' $extra
  fail=1
fi
if [ -n "$missing" ]; then
  echo "HOOK ROSTER FAIL: expected hook file(s) missing:"
  printf '  - %s\n' $missing
  fail=1
fi
[ $fail -eq 0 ] && echo "check-hook-roster: OK ($(printf '%s\n' "$WANT" | grep -c .) files)"
exit $fail
