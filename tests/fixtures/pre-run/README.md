# Pre-run hook copies

Byte copies of `claude/hooks/secret-guard.py` and `claude/hooks/block-secrets.py` as they stood at kit commit 67ceb79 (2026-10-20), before the secrets-hook fix. `tests/test_secret_hooks.py` runs every case against these AND the current hooks, so the before/after flip is proven on any machine, including a fresh Mac. Never edit them.
