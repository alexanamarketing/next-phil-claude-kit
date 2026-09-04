# Build journal - listing-video skill

<!-- state:listing-video-skill -->
State: Phases 1 and 2 built and green (seed content, offline helpers, tests, full suite passing). Phase 3 (the skill) and Phase 4 (reconcile) still open.
Next actor: agent
Next action: build Phase 3 (SKILL.md, /help line, README line, uninstall roster) once a builder picks it up.
Updated: 2026-09-04
<!-- /state -->

Append-only below. New entries go under this line, newest last. Write each phase line here first, then mirror it into the plan doc.

- 2026-09-04 selector: recommended=1 chosen=2 (prose floor forced Tier 2: additive, offline, git-reversible, no live surface touched during build; safety floor = no paid Higgsfield call, no hand-off, no deploy).
- 2026-09-04 P1 done: wrote references/recipe.md and references/scene-card-format.md (Phil-facing, path-stripped), 7 seed cards (front-of-the-house, living-room, kitchen, dining-room, primary-bedroom, primary-bathroom, backyard) each leading with an explicit continuous camera move, and seed-scenes/INDEX.md listing all 7. Titles are plain language, no "dolly" in any title (the word appears only inside the instructions text, the video tool's own vocabulary). In-phase check exits 0: 7 cards, each carries continuous + a move keyword + "throughout the entire shot" + the cinematography line + the negative-prompt markers, each filename is in the INDEX, zero vault paths or agency name, zero em dashes. Note: the writing-lint hook flags sentence-case headings as advisory only; kept sentence case to match the kit's own explain/help skills' plain Helper-Mode voice.
- 2026-09-04 P2 done: wrote three stdlib-only helpers under the skill's tools/ and their standalone-script tests. tools/stitch.py joins clips with hard cuts (scale/pad to 1280x720, setsar 1, fps=30, concat, libx264 -pix_fmt yuv420p -r 30), locates ffmpeg with shutil.which and prints a plain sentence + exit 3 when it is absent (exit 2 on a missing input), and prefixes file: on any colon-bearing path. tools/motion_check.py compares the first and last frame (scaled to 64x36 gray) and reports moved/static with a 3.0 threshold. tools/library.py does init/list/check(--heal)/save(collision -> exit 3, --overwrite, --keep-both)/resume over the user's vault library. All three tests pass on locally generated ffmpeg fixtures; the full seven-script suite loop, check-portability.sh, and check-hook-roster.sh all exit 0; no helper or test touches the Higgsfield CLI (grep = 0). Dead end corrected: test_motion_check's plain-run helper used a falsy `if extra:` guard so `extra=[]` fell through to the --json branch; switched to `if extra is None`.
