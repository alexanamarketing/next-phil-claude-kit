<!-- writing-lint-disable: em-dash -- internal e2e test report; money cards and transcript quote the skill verbatim -->
<!-- writing-lint-disable: response-wrapper -- transcript quotes in-character dialogue -->
# listing-video skill: end-to-end test report

Tester acts as the Claude serving the user (Phil) AND audits the skill. Mock Higgsfield
CLI on PATH; no network, no real credits. One fixture photo (`photo.jpg`) stands in for
every pulled MLS/room photo because the sandbox has no network to pull real listing
photos (a harness limit, not a skill fault; noted where it bears on a step).

Skill under test: `~/Projects/next-phil-claude-kit/claude/skills/listing-video/SKILL.md`

Credit math used everywhere: one clip = 22.5 credits; clips-left = floor(credits / 22.5).
The skill and cards say "about 22 credits" per clip; the mock bills 22.5. Cards are
rendered below exactly as the on-screen money card would read.

---

## Scenario 1 — First-run happy path

Reset: `reset 1000 ""`.

### Preflight (quiet, before speaking)
- Vault found via `VAULT_ROOT` env (no `~/.claude/starter-kit/config.json`; the skill's
  documented fallback order held).
- `config.yaml` read; `os_open: echo`.
- `listing-videos/` absent -> first run -> `library.py init`:
  `Set up your scene library ... (copied 7 new scene(s); 7 in total).`
  Scenes on disk: backyard, dining-room, front-of-the-house, kitchen, living-room,
  primary-bathroom, primary-bedroom = **7 seeds copied (verified)**.
- `library.py resume --json` -> `[]` (no unfinished work).
- `higgsfield account status --json` -> `{"credits": 1000}` -> **about 44 clips left**.

### Turn 1 — Opener (Claude)
Delivered the plain map: test one clip first (~22 credits) to see and tune; then the
whole video (~180 credits for a full reel); nothing charged until you say yes; a clip
can't be cancelled once it starts so the cost shows first; about 1 in 5 clips needs a
quick redo, not your fault. Defined the five words (photo, clip, scene, video, credits).
Offered quick-vs-learn; recommended one clip first.

**Phil:** "Let's do the one clip first."

### Turn 2 — Photos in (Claude)
"What's the MLS number?"

**Phil:** "7040686."

Claude would pull the public photos for MLS 7040686 via the `references/recipe.md` URL
pattern and lay them out as a labeled sheet. No network in the sandbox, so `photo.jpg`
stands in as the kitchen photo. (AUDIT: the MLS-photo path is untestable offline; flagged
in findings, not a pass/fail here.)

### Turn 3 — Kitchen starter scene (Claude)
"Here's the standard kitchen scene: *Kitchen, slide across past the island* — the camera
slides left to right past the island. Want to change the move, the direction, or the
speed before we run it? Plus the standard keep-the-room-exactly-as-it-is instructions;
say 'show me the full recipe' if you're curious."

**Phil:** "Keep it as-is."

### Turn 4 — Money card (rendered before the charge)
```
Money card
  Making: one clip of the kitchen
  Cost: about 22 credits  (a clip usually runs about 22 credits)
  Balance now: about 1000 credits (about 44 clips left)
  Balance after: about 978 credits (about 43 clips left)
  This session so far: 0 clips, about 0 credits
  Saying yes: yes makes one clip and nothing else
```
Plus first-charge note: "the app may ask permission to run the command; that's a safety
check, not another charge."

**Phil:** "Yes."

### Turn 5 — Make the clip (Claude)
Submitted async: `higgsfield generate create seedance_2_0 --prompt "<kitchen instructions>" --image-references photo.jpg --aspect-ratio 16:9 --resolution 720p --duration 5 --mode std --generate-audio=false --json` -> `{"id":"job001","status":"queued"}`. Narrated the ~2 min wait; polled `generate get job001 --json` -> completed, downloaded to `output/7040686/kitchen.mp4`. **create #1.**

### Turn 6 — Motion check + open (Claude)
`motion_check.py kitchen.mp4 --json` -> `{"moved": true, "score": 9.181}` (exit 0). Opened with `os_open` (echo). Warmth beat: "you made that; two minutes ago it was a photo. A clip is one short shot; a video is all the clips joined together."

**Phil:** "Love it."

### Turn 7 — Name + save (Claude)
"I'll call this 'kitchen slow glide', change it if you like."
**Phil:** "That's good."
`library.py save --name "kitchen slow glide" --card <card>` -> `Saved "kitchen slow glide" as kitchen-slow-glide.md.` (exit 0). Ownership beat: "that's your first scene; next time just say its name." Library now holds 8 cards.

### Turn 8 — Phil wants the whole video; cast + batch card (Claude)
**Phil:** "Great, make the whole video."
`library.py list` shows the 8 scenes. Cast the 7 room scenes onto the listing, front first, backyard last:
front-of-the-house, living-room, kitchen, dining-room, primary-bedroom, primary-bathroom, backyard.
Wrote `output/7040686/reel.json` (status `casting`, 7 planned clips, estimate 157.5) BEFORE generating.

```
Money card (batch — the whole video)
  Making: the whole video, 7 clips
    1 front of the house   about 22 credits
    2 living room          about 22 credits
    3 kitchen              about 22 credits
    4 dining room          about 22 credits
    5 primary bedroom      about 22 credits
    6 primary bathroom     about 22 credits
    7 backyard             about 22 credits
  Cost: about 158 credits total  (7 clips x ~22.5)
  Balance now: about 978 credits (about 43 clips left)
  Balance after: about 820 credits (about 36 clips left)
  This session so far: 1 clip, about 22 credits
  Saying yes: yes starts all 7 clips
```
Balance check: 977.5 - 157.5 = 820 >= 0, batch is funded. 
**Phil:** "Yes, go."

### Turn 9 — Stitch, open, watermark, wrap (Claude)
No static clip to drop (all 7 moved). `stitch.py --out reel.mp4 <7 clips in shot order>` -> `{"ok": true, "clips": 7, "seconds": 14.0}`, real 210KB `reel.mp4` produced. Opened with `os_open`. Warmth beat: "you made that, a whole walkthrough from a folder of photos." Soft line: "give it a quick look for any watermark before you send it to a client." (reminder, not a gate). Reconciled `account transactions` (8 tx, sum -180; batch billed 157.5 = estimate). `reel.json` -> status `stitched`.
Wrap: credits used this session ~180, balance 820 (about 36 clips left), reset date unknown. "Next time just say 'make a listing video' or type /listing-video. Run /sync to save the session."

### Scenario 1 result: **PASS**

| criterion | evidence |
| --- | --- |
| init copied 7 seeds | `copied 7 new scene(s); 7 in total`; 7 card files on disk |
| balance shown as clips | 1000 credits -> "about 44 clips left" |
| money card before EACH paid clip | test card (turn 4) precedes create #1; batch card (turn 8) precedes creates #2-#8 |
| motion check ran on each | `motion_check.py` run on kitchen + all 7 batch clips (all moved) |
| real stitched mp4 | `reel.mp4` 210542 bytes, 7 clips, 14.0s, exit 0 |
| watermark line appeared | "give it a quick look for any watermark before you send it to a client" |
| wrap shows credits used + clips left | ~180 used, 820 left (about 36 clips) |

Creates in log: **8**, all preceded by a money card + yes. No uncarded create.

**Finding (minor):** the kitchen test clip (create #1, saved as a scene) is NOT reused in
the reel; the batch regenerates the kitchen as create #4. A real broker pays ~22 credits
twice for the same room. SKILL.md "Cast the listing" (lines 170-191) never says to reuse
an already-made-and-approved clip that matches a cast slot. Not a money-safety breach (the
batch card itemizes and discloses the kitchen), but a credit-efficiency gap worth a line.

**Ambiguity (minor):** SKILL.md line 74 / opener says "the whole video, about 180 credits
for a full eight-clip reel" and the recipe fixes a video at 8 clips, but the shipped
library has 7 room scenes, so a straight cast yields a 7-clip reel. The 8th clip only
appears if a listing needs a stand-in room. The "eight-clip" framing in the money math can
mislead; the itemized batch card saved it here because it lists the real count.

---

## Scenario 2 — Static-clip redo

Reset: `reset 1000 "1"` (first create returns a static clip).
Preflight: init (7 seeds), resume `[]`, balance `{"credits":1000}` -> about 44 clips.

### Turn 1 — one-clip test money card (Claude)
```
Money card
  Making: one clip of the kitchen
  Cost: about 22 credits
  Balance now: about 1000 credits (about 44 clips left)
  Balance after: about 978 credits (about 43 clips left)
  This session so far: 0 clips, about 0 credits
  Saying yes: yes makes one clip and nothing else
```
**Phil:** "Yes." -> **create #1** (`job001`), downloaded to `kitchen-take1.mp4`.

### Turn 2 — motion check catches static (Claude)
`motion_check.py kitchen-take1.mp4 --json` -> `{"moved": false, "score": 0.0}` (exit 1).
Claude did NOT open it as a success and did NOT save it. Said: "that one did not move, it
happens, not your fault. Want me to redo it with a stronger camera move? That's a fresh
clip, about 22 credits."

### Turn 3 — redo money card (fresh charge)
```
Money card
  Making: a redo of the kitchen
  Cost: about 22 credits  (every redo is a fresh clip)
  Balance now: about 978 credits (about 43 clips left)
  Balance after: about 955 credits (about 42 clips left)
  This session so far: 1 clip, about 22 credits
  Saying yes: yes makes one clip and nothing else
```
**Phil:** "Yes, redo it." -> **create #2** (`job002`), `kitchen-take2.mp4`.

### Turn 4 — redo passes (Claude)
`motion_check.py kitchen-take2.mp4 --json` -> `{"moved": true, "score": 9.181}` (exit 0).
Opened take 2 with `os_open`; warmth beat. Balance 955 (about 42 clips).

### Scenario 2 result: **PASS**

| criterion | evidence |
| --- | --- |
| static clip flagged, not user's fault | `moved:false score 0.0`; "did not move ... not your fault" |
| static clip NOT opened as success | only take 2 opened; take 1 never sent to os_open |
| static clip NOT saved | scenes dir holds 7 seeds only (no static card written) |
| redo offered as a fresh charge | redo money card rendered, "every redo is a fresh clip" |
| redo (create #2) moving + passes | score 9.181, exit 0 |

Creates in log: **2** (create #1 carded by turn-1 card; create #2 carded by turn-3 redo
card). No uncarded create.

---

## Scenario 3 — Name collision

Reset: `reset 1000 ""`. Init (7 seeds). No paid clips in this scenario (0 creates).

- First save "kitchen slow glide" -> `Saved "kitchen slow glide" as kitchen-slow-glide.md.` (exit 0).
- Second save, same name -> exit **3**:
  `You already have a scene with that name: "Kitchen, slide across past the island".
  Tell me to overwrite it, keep both, or use a new name.`
  Nothing written. Claude relays the three choices to Phil.
- **Phil:** "Keep both." -> `save ... --keep-both` -> `Saved "kitchen slow glide" as kitchen-slow-glide-2.md.` (exit 0).

Verify on disk:
- `kitchen-slow-glide.md` = original (contains "left to right"), **intact/undestroyed**.
- `kitchen-slow-glide-2.md` = the second card (contains "right to left").
- Catalog (INDEX.md) lists both files.

### Scenario 3 result: **PASS**

| criterion | evidence |
| --- | --- |
| duplicate save exits 3 | `exit=3`, plain sentence, nothing written |
| skill offers overwrite / keep both / new name | message names all three; skill relays them |
| keep-both writes a second card | `kitchen-slow-glide-2.md` created |
| first card not destroyed | original still present with its original text |
| both catalogued | two `kitchen-slow` rows in INDEX.md |

Creates in log: **0** (no money-safety surface; trivially clean).

**Finding (minor):** the collision message reports the stored card's `title:` field
("Kitchen, slide across past the island"), not the plain name the user just typed
("kitchen slow glide"). If a saved card's title differs from the name the user speaks, the
message can read as a different scene than they meant. `library.py cmd_save` (line 189)
uses `read_field(..., "title")`; echoing the user's typed `--name` (or the slug) would be
clearer. Cosmetic, not a data-safety issue.

---

## Scenario 4 — Out-of-credits batch

Reset: `reset 50 ""`. Init (7 seeds), resume `[]`, balance `{"credits":50}` -> **about 2 clips left**.

**Phil:** "Make the whole video."
Claude casts the 7 room scenes, then runs the pre-batch funding check BEFORE any create:
- batch cost = 7 x 22.5 = 157.5
- balance now = 50 (2 clips); balance after = 50 - 157.5 = **-107.5 (negative)** -> NOT FUNDED.

Claude refuses to start and shows the shortfall plainly, e.g.:
```
Money card (batch — the whole video)
  Making: the whole video, 7 clips
  Cost: about 158 credits total
  Balance now: about 50 credits (about 2 clips left)
  Balance after: would be about -108 credits  <-- can't cover it
```
"You have enough for about 2 clips right now, not the whole 7-clip reel. Two ways
forward: I can make a shorter reel (pick your 2 must-have rooms, say front and kitchen),
or you can top up the account and we do the full video. Which do you want?"

**Path taken: REFUSE-BEFORE-START (the preferred branch).** No `generate create` was
issued. The mock log shows only `account status` and **zero creates**.

### Scenario 4 result: **PASS**

| criterion | evidence |
| --- | --- |
| pre-batch balance check refuses an unfundable batch | balance-after -107.5 < 0 -> not started |
| offer shorter reel or top-up before any create | both offered (2-clip reel / top-up) |
| zero creates for the refused batch | `grep -c "generate create"` = **0**; log holds only `account status` |

Creates in log: **0**. Money-safety: no charge attempted against an underfunded balance.

---

## Scenario 5 — Resume a partial reel

Reset: `reset 1000 ""`. Planted a prior partial session at
`output/4136-palace-station/reel.json`: 8 planned clips, first 3 (`front-of-the-house`,
`living-room`, `kitchen`) marked made with real clip files on disk, `status: generating`,
`credits.charged: 67.5`.

### Fresh preflight (skill start)
- `library.py check` -> `Your scene library and its list agree.`
- `library.py resume --json` ->
  `[{"listing":{...,"mls":"4136 Palace Station"},"status":"generating","made":3,"planned":8,...}]`
- Claude surfaces it: "Last time we made 3 of 8 clips for 4136 Palace Station. Want to
  pick that up, or start something new?"

**Phil:** "Pick it up."

### Resume batch money card (remaining ONLY — the fix under test)
5 clips remain (dining-room, primary-bedroom, primary-bathroom, second-bedroom [stand-in
from the primary-bedroom scene], backyard).
```
Money card (batch — finish the video)
  Making: the 5 clips left to finish 4136 Palace Station
    4 dining room       about 22 credits
    5 primary bedroom   about 22 credits
    6 primary bathroom  about 22 credits
    7 second bedroom    about 22 credits
    8 backyard          about 22 credits
  Cost: about 113 credits total  (5 clips x ~22.5) -- the cost to FINISH, not to start over
  Balance now: about 1000 credits (about 44 clips left)
  Balance after: about 888 credits (about 39 clips left)
  Saying yes: yes starts the 5 remaining clips
```
The 3 already-paid clips are NOT re-charged and NOT itemized.
**Phil:** "Yes."

Generated the 5 remaining (jobs 001-005 in this fresh session's mock), all moved. Balance
1000 -> **887.5** (dropped 112.5, i.e. 5 clips, not 8). reel.json now shows **8 of 8 made**.

### Scenario 5 result: **PASS**

| criterion | evidence |
| --- | --- |
| preflight resume surfaces the unfinished reel | resume `--json` returns made 3 / planned 8 |
| offers to pick it up | "made 3 of 8 ... pick that up, or start something new?" |
| batch money card covers ONLY remaining clips | card lists 5, cost ~113; balance fell 112.5 not 180 |
| creates issued = remaining only | `grep -c "generate create"` = **5**, not 8 |

Creates in log: **5**, all under the single resume-batch card. The specific fix (resume
card charges the cost-to-finish, not the whole reel) **holds**.

---

## Scenario 6 — Drop static before join

Reset: `reset 1000 "4"` (the 4th create returns static). Init (7 seeds).
Cast a 5-clip reel: front-of-the-house, living-room, kitchen, dining-room, backyard.
One batch money card (5 clips, ~113 credits). **Phil: yes.**

Batch results (motion check per clip):
- front-of-the-house `moved`, living-room `moved`, kitchen `moved`,
  **dining-room `static` (score 0.0)**, backyard `moved`.

Claude: "the dining-room clip did not move; want a redo (fresh ~22 credits)?"
**Phil:** "No, skip it."

### Stitch (drops the still-static clip)
`stitch.py --out reel.mp4 front living kitchen backyard` (dining-room excluded) ->
`{"ok": true, "clips": 4, "seconds": 8.0}`. Final reel = 4 clips, 8.0s, verified by
ffprobe. Dining-room clip file stays on disk but is NOT in the joined video.
Claude to Phil: "I left the dining room out of the final video because that clip did not
move and you passed on the redo. The reel is the other 4 rooms."

### Scenario 6 result: **PASS**

| criterion | evidence |
| --- | --- |
| static clip dropped before joining | stitch args exclude dining-room; final `clips: 4` |
| not in the final mp4 | reel = 4 clips / 8.0s (dining-room's 5th would make 5/10s) |
| Phil told which room was left out and why | "left the dining room out ... did not move ... passed on the redo" |

Creates in log: **5**, all under the single 5-clip batch card. The declined redo added no
create. Money-safety clean.

---

## Money-safety assertion — creates vs money cards (all scenarios)

| scenario | creates in log | carded-by | uncarded creates |
| --- | --- | --- | --- |
| 1 first-run happy path | 8 | #1 test card; #2-#8 batch card | 0 |
| 2 static redo | 2 | #1 test card; #2 redo card | 0 |
| 3 name collision | 0 | (no charges) | 0 |
| 4 out-of-credits batch | 0 | refused before any create | 0 |
| 5 resume | 5 | resume-batch card (remaining 5 only) | 0 |
| 6 drop-static | 5 | 5-clip batch card | 0 |
| **total** | **20** | | **0** |

**Every one of the 20 `generate create` calls was preceded in the transcript by a rendered
money card and a Phil "yes". Zero uncarded charges. No BLOCKER on money safety.**

## Overall verdict: **PASS** (6 of 6 scenarios)

All six scenarios passed. The skill's money-safety spine held under every path: per-clip
cards, batch cards with itemized totals, redo-as-fresh-charge cards, a pre-batch funding
refusal that issued zero creates, and a resume card that charged only the cost-to-finish.
Motion check caught every static clip; static clips were never opened as a success, never
saved, and never joined into a finished reel. Real stitched mp4s were produced (7-clip and
4-clip). library.py behaved: 7 seeds copied, exit-3 collision with non-destructive
keep-both, catalog kept in step.

## Findings (ranked)

**BLOCKER:** none.

**MAJOR:** none.

**MINOR:**
1. Kitchen test clip re-generated, not reused. SKILL.md "Cast the listing" (lines 170-191)
   never says to reuse an already-made, motion-passed, saved clip that matches a cast slot,
   so the happy path pays for the kitchen twice (create #1 and create #4 in scenario 1).
   Disclosed by the batch card, so not a money-safety breach, but a real credit waste for a
   broker who just approved that exact kitchen clip.
2. "Eight-clip reel" framing vs 7 shipped scenes. SKILL.md opener (line 74) and
   `references/recipe.md` fix a video at 8 clips and ~180 credits, but the shipped library
   has 7 room scenes, so a straight cast yields 7 clips (~158). The 8th only appears when a
   stand-in room is added. The itemized batch card shows the true count and saved the money
   math here, but the round "180 / eight-clip" language can set a wrong expectation.

**POLISH:**
3. Collision message shows the card's `title:` field, not the name the user typed.
   `library.py cmd_save` (line 189) prints `read_field(dest,"title")`; when a saved card's
   title differs from the plain name the user speaks, the "you already have a scene with
   that name: <title>" line can name a different-sounding scene. Echo the typed `--name`
   or the slug for clarity.
4. `library.py resume` returns `listing` as whatever shape reel.json stored (here a dict).
   The non-`--json` branch would print the dict repr; `scene-card-format.md` is vague on
   whether `listing` is a string or an object. Claude uses `--json` and composes the
   sentence, so no user-facing break, but the shape should be pinned in the format doc.

**AMBIGUITY hit while walking the skill:**
5. MLS photo pull is untestable offline (no network in the sandbox); `photo.jpg` stood in
   for every room photo. Not a skill defect, but the skill has no stated fallback for "the
   MLS photo pull failed / returned nothing," which a real run will hit; worth a plain
   branch ("I couldn't pull the photos for that MLS number, want to drag them in instead?").
