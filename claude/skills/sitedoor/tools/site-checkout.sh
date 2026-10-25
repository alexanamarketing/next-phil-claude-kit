#!/usr/bin/env bash
# site-checkout.sh: find (or set up) this computer's copy of the website code,
# DevNextRealEstate/next-listing-pages, so design and code changes have a place to happen.
#
# Usage:
#   bash site-checkout.sh                 find it; print where it is and its state
#   bash site-checkout.sh --path <dir>    use this folder (it must be a copy of the repo)
#   bash site-checkout.sh --clone         if none is found, copy it from GitHub and install it
#   bash site-checkout.sh --clone --dest <dir>   copy it to <dir> (default ~/Projects/next-listing-pages)
#
# Where it looks, in order: --path, $NEXT_SITE_REPO, the folder it remembered last
# time (~/.claude/starter-kit/site-repo), then a short list of usual folders. It
# never searches the whole disk. A folder counts only when it is a git checkout
# whose origin is DevNextRealEstate/next-listing-pages. The folder it finds is
# remembered for next time.
#
# It never reads, prints or writes an env file or a key. Local runs need
# .env.local, which comes from `npx vercel env pull` under the user's own Vercel
# login (see the repo's AGENTS.md, "Design Changes from Phil's Chat").
#
# Exit codes: 0 ready, 1 not found (re-run with --clone), 2 usage, 3 the copy or
# the install failed. The last line is SITE_REPO=<folder> when it is ready.
set -uo pipefail

REPO_SLUG="DevNextRealEstate/next-listing-pages"
CLONE_URL="${NEXT_SITE_REPO_URL:-https://github.com/$REPO_SLUG.git}"
POINTER="$HOME/.claude/starter-kit/site-repo"
DEST="$HOME/Projects/next-listing-pages"
WANT_CLONE=false
GIVEN=""

usage() { sed -n '5,9p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }

while [ $# -gt 0 ]; do
  case "$1" in
    --clone) WANT_CLONE=true ;;
    --path) [ $# -ge 2 ] || usage; GIVEN="$2"; shift ;;
    --dest) [ $# -ge 2 ] || usage; DEST="$2"; shift ;;
    -h|--help) usage ;;
    *) echo "site-checkout: unknown option $1" >&2; usage ;;
  esac
  shift
done

# A folder counts when it is the top of a git checkout whose origin is the website repo.
is_site_repo() {
  local dir="$1" top url
  [ -n "$dir" ] && [ -d "$dir" ] || return 1
  top="$(git -C "$dir" rev-parse --show-toplevel 2>/dev/null)" || return 1
  [ "$(cd "$top" && pwd -P)" = "$(cd "$dir" && pwd -P)" ] || return 1
  url="$(git -C "$dir" remote get-url origin 2>/dev/null)" || return 1
  url="$(printf '%s' "$url" | tr 'A-Z' 'a-z')"
  case "$url" in
    *devnextrealestate/next-listing-pages|*devnextrealestate/next-listing-pages.git) return 0 ;;
  esac
  return 1
}

remember() {
  mkdir -p "$(dirname "$POINTER")" 2>/dev/null && printf '%s\n' "$1" > "$POINTER" 2>/dev/null
}

install_deps() {
  local dir="$1"
  [ -f "$dir/package.json" ] || return 0
  [ -d "$dir/node_modules" ] && return 0
  if ! command -v npm >/dev/null 2>&1; then
    echo "site-checkout: npm is not installed, so the code's packages were not installed."
    echo "  Run the kit's bootstrap.sh (it installs Node), then run this again."
    return 3
  fi
  echo "site-checkout: installing the code's packages (npm ci, a minute or two)..."
  if ! (cd "$dir" && npm ci --no-audit --no-fund >/dev/null 2>&1); then
    echo "site-checkout: npm ci failed in $dir. Run it there to see why: cd '$dir' && npm ci"
    return 3
  fi
}

report() {
  local dir="$1" branch dirty
  branch="$(git -C "$dir" rev-parse --abbrev-ref HEAD 2>/dev/null)"
  if [ -n "$(git -C "$dir" status --porcelain 2>/dev/null)" ]; then dirty="yes"; else dirty="no"; fi
  echo "site-checkout: the website code is at $dir"
  echo "  branch: $branch; uncommitted changes: $dirty"
  if [ "$dirty" = "yes" ] || [ "$branch" != "main" ]; then
    echo "  Ask the user before switching branches: this may be their work in progress."
  fi
  [ -d "$dir/node_modules" ] || [ ! -f "$dir/package.json" ] || \
    echo "  Packages are not installed yet: run this again with --clone, or npm ci in that folder."
  echo "SITE_REPO=$dir"
}

found=""
if [ -n "$GIVEN" ]; then
  if is_site_repo "$GIVEN"; then
    found="$(cd "$GIVEN" && pwd -P)"
  else
    echo "site-checkout: $GIVEN is not a copy of $REPO_SLUG (no git checkout with that origin)." >&2
    exit 1
  fi
fi

if [ -z "$found" ]; then
  remembered=""
  [ -f "$POINTER" ] && remembered="$(head -1 "$POINTER" 2>/dev/null)"
  for cand in "${NEXT_SITE_REPO:-}" "$remembered" \
      "$HOME/next-listing-pages" "$HOME/Projects/next-listing-pages" \
      "$HOME/projects/next-listing-pages" "$HOME/Developer/next-listing-pages" \
      "$HOME/code/next-listing-pages" "$HOME/Code/next-listing-pages" \
      "$HOME/GitHub/next-listing-pages" "$HOME/Documents/GitHub/next-listing-pages" \
      "$HOME/Documents/next-listing-pages" "$HOME/Desktop/next-listing-pages" \
      "$DEST"; do
    if is_site_repo "$cand"; then
      found="$(cd "$cand" && pwd -P)"
      break
    fi
  done
fi

if [ -n "$found" ]; then
  remember "$found"
  if $WANT_CLONE; then install_deps "$found" || exit 3; fi
  report "$found"
  exit 0
fi

if ! $WANT_CLONE; then
  echo "site-checkout: no copy of the website code found on this computer."
  echo "  If the user has one somewhere else, run: bash $0 --path <that folder>"
  echo "  Otherwise copy it from GitHub with: bash $0 --clone"
  exit 1
fi

if [ -e "$DEST" ]; then
  echo "site-checkout: $DEST already exists but is not a copy of $REPO_SLUG; nothing was changed."
  echo "  Pick another folder with --dest <folder>, or move that one aside first."
  exit 3
fi

mkdir -p "$(dirname "$DEST")" || exit 3
echo "site-checkout: copying $REPO_SLUG to $DEST..."
if [ -z "${NEXT_SITE_REPO_URL:-}" ] && command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  gh repo clone "$REPO_SLUG" "$DEST" >/dev/null 2>&1 || git clone -q "$CLONE_URL" "$DEST"
else
  git clone -q "$CLONE_URL" "$DEST"
fi
if ! is_site_repo "$DEST"; then
  echo "site-checkout: GitHub did not hand over the code. The user signs in to GitHub in Terminal"
  echo "  with the account that has access to $REPO_SLUG ('gh auth login', answering yes to using"
  echo "  it for git), accepts the repository invite if one is waiting, then runs this again."
  exit 3
fi
# The repo's own committed pre-commit hook (the de-hardcode audit).
[ -d "$DEST/scripts/git-hooks" ] && git -C "$DEST" config core.hooksPath scripts/git-hooks
remember "$(cd "$DEST" && pwd -P)"
install_deps "$DEST" || exit 3
report "$(cd "$DEST" && pwd -P)"
exit 0
