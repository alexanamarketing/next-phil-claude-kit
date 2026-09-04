#!/usr/bin/env bash
set -euo pipefail
E="$(cd "$(dirname "$0")" && pwd)"
CREDITS="${1:-1000}"; STATIC_ON="${2:-}"
SB="$E/sandbox"; rm -rf "$SB"; mkdir -p "$SB/vault"
printf 'os_open: echo\nhelp_mode: on\n' > "$SB/vault/config.yaml"
echo "$CREDITS" > "$SB/credits"
rm -f "$SB/mock-higgs.log"; mkdir -p "$SB/jobs"
cat > "$SB/env.sh" <<ENV
export PATH="$E:\$PATH"
export VAULT_ROOT="$SB/vault"
export MOCK_HIGGS_LOG="$SB/mock-higgs.log"
export MOCK_HIGGS_CREDITS_FILE="$SB/credits"
export MOCK_HIGGS_JOBS_DIR="$SB/jobs"
export MOCK_HIGGS_CLIP_MOVING="$E/moving.mp4"
export MOCK_HIGGS_CLIP_STATIC="$E/static.mp4"
export MOCK_HIGGS_STATIC_ON="$STATIC_ON"
ENV
echo "sandbox ready: $SB (credits=$CREDITS static_on='$STATIC_ON')"
