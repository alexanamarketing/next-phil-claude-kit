# End-to-end harness for the listing-video skill

A no-network, no-credit harness for driving the listing-video skill through its whole
flow. It mocks the Higgsfield CLI (logging every call and decrementing a credit ledger)
and ships sample clips, so an agent can walk SKILL.md as if serving the user while every
paid call, money card, motion check, and stitch is exercised for real, without spending a
credit.

Files:
- `higgsfield` - the mock CLI (put its dir first on PATH). Logs every call; `generate
  create` decrements the ledger by 22.5 and returns a moving clip, or a static clip for
  call numbers listed in `MOCK_HIGGS_STATIC_ON`.
- `reset-scenario.sh <credits> <static_on_csv>` - builds a fresh sandbox (clean vault,
  credit ledger, jobs dir, call log) and writes `sandbox/env.sh`.
- `moving.mp4` / `static.mp4` / `photo.jpg` - fixtures.
- `e2e-report.md` - the 2026-09-04 run report (6 scenarios, money-safety proof).

Run a scenario:

    bash tests/e2e/reset-scenario.sh 1000 ""     # fresh sandbox, 1000 credits, no forced static clip
    source tests/e2e/sandbox/env.sh              # sets PATH (the mock), VAULT_ROOT, MOCK_HIGGS_*

Then walk `claude/skills/listing-video/SKILL.md` from the top, running the commands it
specifies (the mock `higgsfield` for account/generate, `tools/*.py` for the rest) and
playing the user. Every `generate create` in `sandbox/mock-higgs.log` must be preceded by
a rendered money card. Prefix each shell command with `source tests/e2e/sandbox/env.sh &&`
because env does not persist between separate shells.

Scenario knobs:
- credits (arg 1): starting balance. Use about 50 to exercise the out-of-credits path.
- static_on (arg 2): comma list of `generate create` call numbers that return a static
  clip (exercises the motion-check redo path), for example `1` or `4`.

The `sandbox/` directory is regenerated on every run and is not committed.
