---
name: listing-video
description: Make a listing walkthrough video from the photos, one clip at a time, with the cost shown before anything runs. Say "make a listing video", "listing walkthrough video", or "video from the listing photos" to start it, or type /listing-video.
---

# /listing-video - Make a listing walkthrough video

This walks the user from a photo to a finished listing video in plain English. The
user talks; you run the tool for them. You show the cost before every charge, you
check that every clip actually moved, and you save each good scene into a library the
user owns.

The user is a real-estate broker, not a developer. Keep to the five words in the
vocabulary below and say "the instructions I give the video tool" instead of "prompt".
Never print a raw command error at the user; every failure branch has a plain sentence
and a next step. Never invent a cost or a balance; read it from the account.

## The words to use (define these once in the opener, then use only these)

Tell the user, in the opener, that five words cover the whole job: **photo, clip,
scene, video, credits**. A photo is a still image of a room. A clip is one short
moving shot made from one photo. A scene is a saved recipe for one kind of shot (the
standard kitchen, and so on). A video is the clips joined into one reel. Credits are
what the tool spends, and the plan refills them every month. Use these words and no
jargon. The first time you make a clip, say plainly that a clip is one short shot and a
video is all the clips joined together, so the two do not blur.

## Before anything: find the library and the balance

Do this first, every time, quietly, before you say anything to the user.

Find the vault the kit's way: read `~/.claude/starter-kit/config.json`, then the
`VAULT_ROOT` environment variable, and only if neither is set, ask the user where
their vault folder is. Also read `<vault_root>/config.yaml` for `os_open` (the command
that opens a file on this machine) so you can open clips and the finished video later.

Set `TOOLS` to this skill's `tools/` folder and `SEED` to its `seed-scenes/` folder.

- If `<vault_root>/listing-videos/` does not exist, this is the first run. Run
  `python3 <TOOLS>/library.py init --vault-root <vault_root>`. It copies the seven
  starter scenes into the user's own folder and writes the catalog. Say one plain line:
  "I set up a folder for your scenes and videos." Do not lecture about the folder.
- If it does exist, run `python3 <TOOLS>/library.py check --vault-root <vault_root>`.
  If the only problem is that the catalog is stale, run the same command again with
  `--heal` and say nothing. If a scene file is actually gone, say one plain line naming
  the scene that is missing. (`library.py check` compares the scenes on disk against the
  catalog; `--heal` rebuilds the catalog and never deletes a scene.)

Then look for unfinished work. Run
`python3 <TOOLS>/library.py resume --vault-root <vault_root> --json`. If it lists an
unfinished video (a `reel.json` whose status is not `stitched`), surface it before
anything new: "Last time we made 5 of 8 clips for 4136 Palace Station. Want to pick
that up, or start something new?" If the user picks it up, jump to the casting section
and continue from the clips already made in that `reel.json`.

Read the balance with `higgsfield account status --json`. Turn credits into clips
(one clip is about 22.5 credits, so clips = floor(credits / 22.5)) and state it as
"about NN clips left". If the tool says the user is not signed in, do not try to fix it
silently: say "Higgsfield says you are not signed in. Tell me and I will walk you
through it," and stop there until they answer.

## Opener and trust contract (say this every time, before anything happens)

Give the user the plain map in a few sentences, not a numbered list:

- We test one clip first, about 22 credits, so you can see it and tune it.
- Then we make the whole video: a straight run of the seven starter scenes is about 158
  credits, and a full eight-clip reel (when a listing needs an extra room) is about 180.
- Nothing is charged until you say yes. A clip cannot be cancelled once it starts, so
  I always show you the cost first.
- About 1 in 5 clips needs a quick redo, and that is normal, not your fault.

Define the five words here (photo, clip, scene, video, credits). Then offer the
quick-vs-learn choice up front: we can make the whole video from your starter scenes
(about 158 credits for the seven rooms, up to about 180 if a room needs a stand-in), or
make one clip first (about 22 credits) so you see how it works.
The first time, recommend one clip first.

Fast path: if the library already holds scenes beyond the seven starters (the user has
been here before), skip the teaching. Say "welcome back" and offer to go straight to
pick scenes, cast the listing, and stitch.

## The money card (fill this in before EVERY charge)

Before anything that spends credits, show this same card, filled in. Same shape every
time so it becomes familiar:

```
Money card
  Making: <one clip of the kitchen | the whole video, 8 clips | a redo of the kitchen>
  Cost: about <N> credits  (a clip usually runs about 22 credits)
  Balance now: about <N> credits (about <NN> clips left)
  Balance after: about <N> credits (about <NN> clips left)
  This session so far: <X> clips, about <Y> credits
  Saying yes: <yes makes one clip and nothing else | yes starts all 8 clips>
```

For a batch (the whole video), list each planned clip and then the TOTAL before the
batch starts, not just the per-clip number. After any charge, reconcile quietly with
`higgsfield account transactions --size 20 --json`; only speak up if the billed amount
differs from the estimate in a way that matters, and say it plainly. Every redo is a
**fresh charge**, so show the money card again and say so each time the user asks for
another try.

The first time a paid command runs in a session, add one line: "the app may ask
permission to run the command; that is a safety check, not another charge." This is so
the two yes prompts (yours, then Claude Code's) do not make the user think they are
being billed twice.

## Photos in

Ask for the MLS number first, because the user knows those. With the MLS number, pull
the public listing photos using the web-address pattern in `references/recipe.md`
(count the photos up from the first one until there are no more), lay them out as one
labeled sheet, read it, and match each photo to a room.

If the pull returns nothing or fails (a wrong or off-market MLS number, or the photo
host is down), do not push on and never invent a photo. Say so plainly: "I could not
pull the photos for that MLS number. Want to double-check the number, or drag your own
photos in instead?" Then use the drag-in path below.

For the user's own photos, tell them the exact trick: "drag the photo file from Finder
into this window and its location appears, then press return." Pick the file up from
there.

Say once, plainly: the light and the time of day come from the photo you pick, so for a
brighter or warmer look, pick a different photo. The tool cannot relight a room or turn
day into evening.

## One clip first, from the room's starter scene

Do not tune from scratch. Open with the room's starter scene. For the kitchen, say
"here is the standard kitchen scene, want to change anything before we run it?" and show
its plain title and move.

Offer ONLY the three knobs that actually change what the user sees:

- the camera move: **push in**, **pull back**, or **slide across**
- the direction (toward the door, left to right, and so on)
- the speed (slow, or a touch faster)

Collapse everything else to one sentence: "plus the standard keep-the-room-exactly-as-
it-is instructions; say 'show me the full recipe' if you are curious." If they ask,
open `references/recipe.md`.

Show the money card, get a yes, then submit the clip and do not wait in one long call.
Submit it async (leave off any wait flag): run
`higgsfield generate create seedance_2_0 --prompt "<the scene instructions>" --image-references <photo.jpg> --aspect-ratio 16:9 --resolution 720p --duration 5 --mode std --generate-audio=false --json`.
It returns a job number right away. Narrate the wait: "this usually takes about two
minutes; I will open it when it is done. You will see command text scroll,
you do not need to read it." Poll in short steps with `higgsfield generate get <id> --json` until
it has a result, then download the finished clip into the listing's output folder.

## Motion check and save

Before you open any clip, check that it moved. Run
`python3 <TOOLS>/motion_check.py <clip.mp4> --json`. It reports moved or static (it
compares the first and last frame; a real camera move scores well above the threshold,
a held shot scores near zero).

- If it is static (the clip **did not move**), say "that one did not move, it happens,
  not your fault," and offer a redo with a stronger camera move. State the redo as a
  fresh charge and show the money card again.
- If it moved, open it with the machine's `os_open` command so the user can watch it.
  On the first clip, add a warmth beat: "you made that; two minutes ago it was a
  photo."

When the user likes a clip, PROPOSE a plain name: "I will call this 'kitchen slow
glide', change it if you like." Save it through the library, never with a file write:
`python3 <TOOLS>/library.py save --vault-root <vault_root> --name "<plain name>" --card <path-to-card>`.
If that exits 3, the name is already taken; do not replace it silently. Ask the user:
overwrite the old one, keep both, or pick a new name. Then run save again with
`--overwrite` or `--keep-both`, or with the new name. On the first save, add the
ownership beat: "that is your first scene; next time just say its name."

## Cast the listing

When the user wants the whole video, cast it. Run
`python3 <TOOLS>/library.py list --vault-root <vault_root>` to see their scenes, then
say something like "here are your 7 scenes, this listing has photos for 6, here is my
match, change any." For a room the listing does not have, build a stand-in from the
nearest starter scene, the way `references/recipe.md` explains (a home with no dining
room might get a second bedroom). The front of the house is always first and the
backyard is always last.

Reuse what the user already paid for. If the one-clip test already made and approved a
clip for one of these rooms this session (it is in this listing's `output/<slug>/`
folder and passed the motion check), REUSE that clip in the reel. Do not regenerate it
and do not charge for it again. On the batch money card, list that room as "already
made, no charge" so the total only covers the new clips.

Write the plan to `output/<listing-slug>/reel.json` (the shape is in
`references/scene-card-format.md`) BEFORE you generate anything, so the work survives if
the session stops. Show ONE batch money card with every planned clip itemized and the
total, get a yes, then submit every clip async. If you are resuming a reel, the batch
money card and the itemized list cover ONLY the clips not yet made, never the ones
already paid for, so the total is the cost to finish, not to start over. Before you
submit, check the batch total against the balance: if the balance cannot cover every
planned clip (the "Balance after" line would drop below zero), do not start a batch that
will run out partway and leave failed clips. Say so plainly and offer a shorter reel
(fewer scenes) or a top-up first, then re-show the card. As each clip lands, give a
progress line ("kitchen is done, 3 of 8"), run the motion check on it, and queue any
redo with its own money card. Update `reel.json` as clips land, so `resume` can find the
work next time.

## If the credits run out partway through

If the balance cannot cover the next clip, stop gently. Never show a raw error. Tell
the user, in plain words, that they are **out of credits** for now, then:

- what is already made and saved, by scene name, with the clip files
- what is still missing
- the ways forward: top up the account, stitch the clips they already have into a
  shorter video now, or wait for the monthly reset if the reset date is known

The `reel.json` keeps the partial state, so next time the resume check finds it and
offers to finish.

## Stitch, open, and the watermark check

Before you join, drop any clip that is still marked "did not move" (a redo the user
declined or could not fund), so a static clip never lands in the finished video. Tell
the user which room you left out and why, in one plain line.

Join the clips with `python3 <TOOLS>/stitch.py --out <reel.mp4> <clip1> <clip2> ...`,
in shot order, in the listing's output folder. The join is a clean hard cut between
clips. This is the house standard and matches the real listing reels, so present it
that way, never as a downgrade.

If stitch exits 3, ffmpeg (the small free tool that joins clips) is not installed. Do
not make the user type anything. Say "I need a small free tool to join clips, want me
to set it up?" and, with their yes, run `brew install ffmpeg` yourself. If Homebrew
itself is missing, offer to install that first, the same way, then install ffmpeg.

Open the finished reel with `os_open`. On the first finished video, add a warmth beat:
"you made that, a whole walkthrough from a folder of photos." Then the soft line: "give
it a quick look for any watermark before you send it to a client." That is a reminder,
not a gate; do not block on it.

## Wrap

Close with a short summary: credits used this session, the balance left stated as clips
(about NN clips left), and the reset date if it is known. Tell the user how to start
next time: "just say 'make a listing video' or type /listing-video." Remind them to run
/sync to save the session. Mark the `reel.json` status `stitched`.

Offer the saved look starting at the SECOND video, not the first: "start from the same
look as last time?" Save it to `house-style.md` and call it "your saved look", never a
per-agent setting.

## When the user asks how something works

If the user asks "explain this" or "how does this work", answer using the rules in the
kit's `/explain` skill: read `~/.claude/skills/explain/SKILL.md` and answer that way
(lead with one plain sentence, expand every technical word once, keep the fix attached
to each problem). Remind them they can type /explain any time. Do not build a second
explainer here; `/explain` cannot be triggered from inside this skill, so you apply its
rules directly.
