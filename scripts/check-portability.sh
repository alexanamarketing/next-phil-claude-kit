#!/usr/bin/env bash
# check-portability.sh — repo invariant, re-run every build phase.
#
# Proves the kit will run on a fresh Mac and carries none of the original
# author's machine assumptions. Exits nonzero (and prints every offender) on:
#   1. a Python hook whose shebang is not `#!/usr/bin/env python3` (recursive)
#   2. a hardcoded Linux user-home path (/home/<user>) in the shipped payload
#   3. a version-manager python path (pyenv) baked into the payload
#   4. a Linux-only or author-machine token hardcoded in hook code
#      (gio trash, xdg-open, pbcopy/xclip/wl-copy, secret-tool, keyring,
#       brew/apt-get/apt), or an identity leak in any payload file
#   5. a bare /usr/bin/<tool> path (other than /usr/bin/env) in hooks/skills
#
# Patterns are written to NOT match this file itself (it uses regex character
# classes rather than a literal user name), so the raw acceptance greps stay
# clean. Sanctioned exceptions (excluded by path): the OS-detect branches in
# bootstrap.sh / setup.sh, the config-driven os_* values in config.example.yaml,
# hook_config.py's platform defaults, and secret-guard.py's Homebrew PATH fix.
# The plans/ and .git/ trees are meta (never copied by setup.sh).
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fail=0
note() { echo "PORTABILITY FAIL: $1"; fail=1; }

PAYLOAD_PRUNE=( -path "$REPO/.git" -o -path "$REPO/plans" -o -name '__pycache__' -o -name '.pytest_cache' -o -name 'node_modules' )

# ---- 1. hook shebangs (recursive, includes lib/ and any deeper dirs) -------
while IFS= read -r f; do
  first="$(head -1 "$f")"
  if [[ "$first" != "#!/usr/bin/env python3" ]]; then
    note "bad shebang in $f -> $first"
  fi
done < <(find "$REPO/claude/hooks" -name '*.py' 2>/dev/null)

# ---- payload file list (text). This checker names token patterns on purpose,
# and GAP-ANALYSIS may name stripped rule ids; both are excluded from the scan.
payload_files() {
  find "$REPO" \( "${PAYLOAD_PRUNE[@]}" \) -prune -o -type f -print \
    | grep -v "$REPO/scripts/check-portability.sh" \
    | grep -v "$REPO/docs/GAP-ANALYSIS.md"
}

# ---- 2. hardcoded Linux user-home path (regex, self-avoiding) --------------
while IFS= read -r f; do
  note "hardcoded /home/<user> path in $f"
done < <(payload_files | xargs grep -Il -e '/home/[a-z]' 2>/dev/null)

# ---- 3. version-manager python path (a real dot-pyenv directory path, not the
# bare word in install help). The [.] class matches a literal dot but keeps this
# file from containing the acceptance grep's own literal pattern.
while IFS= read -r f; do
  note "pyenv path baked into $f"
done < <(payload_files | xargs grep -Il -e '[.]pyenv' 2>/dev/null)

# ---- 4a. Linux/author OS tokens hardcoded in HOOK code ---------------------
# Sanctioned: hook_config.py (platform defaults) and secret-guard.py (Homebrew PATH).
while IFS= read -r line; do
  note "Linux/machine token in hook code: $line"
done < <(grep -rnE 'gio trash|xdg-open|pbcopy|xclip|wl-copy|secret-tool|keyring|brew |apt-get|apt ' \
           "$REPO/claude/hooks" --include='*.py' --include='*.sh' 2>/dev/null \
           | grep -vE '/hook_config.py:|/secret-guard.py:')

# ---- 4b. identity leaks anywhere in payload --------------------------------
while IFS= read -r f; do
  note "identity leak (agency name) in $f"
done < <(payload_files | xargs grep -Il 'Alexana' 2>/dev/null)

# ---- 5. bare /usr/bin/<tool> (not /usr/bin/env) in hooks + skills ----------
while IFS= read -r line; do
  note "bare /usr/bin path: $line"
done < <(grep -rnE '/usr/bin/[a-z]' "$REPO/claude/hooks" "$REPO/claude/skills" 2>/dev/null \
           | grep -v '/usr/bin/env')

if [[ $fail -eq 0 ]]; then
  echo "check-portability: OK"
fi
exit $fail
