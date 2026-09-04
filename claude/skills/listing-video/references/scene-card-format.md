# How a scene card is written

A scene card is one saved recipe for one kind of shot: the standard kitchen, your
favorite living-room glide, and so on. The seed cards that ship with this skill use
this exact shape, and every card Claude saves for you uses it too. You never write one
by hand; Claude fills it in and saves it. This is here so the format is written down in
one place.

## The fields on a card

A card is a small text file with a header block and an instructions block.

Header fields:

- title: the name in plain words, the way you would say it out loud (for example
  "Kitchen, slide across past the island"). Never the tool's jargon.
- room: which room this scene is for (kitchen, living room, front exterior, and so on).
- place: where the clip sits in the video. One of: opener, middle, closer.
- move: the camera move. One of: push in, pull back, slide across.
- direction: which way the move goes (toward the door, left to right, and so on).
- speed: slow, or a touch faster.
- photo notes: a plain line on which photo works best for this scene.

Instructions block:

- instructions: the full text sent to the video tool. It leads with the camera move,
  closes with "continuous [move] throughout the entire shot" and "preserve every
  detail identically", then carries the look line and the locked keep-the-room-exactly-
  as-it-is list. This is the part that makes the clip; the header is for you to read.
- locked: a note that the look line and the keep-the-room list are baked into the
  instructions and are not meant to be edited. These are the same on every card.

## The catalog line

The catalog (the file named INDEX.md in your scenes folder) lists every card, one line
each, so you can see what you have at a glance:

`title | room | move | file`

For example: `Kitchen, slide across past the island | kitchen | slide across | kitchen.md`

## The reel file (reel.json)

When Claude makes a whole video for one listing, it writes a small progress file next
to the clips, named reel.json, so the work is never lost if a session is interrupted.
It holds:

- listing: the listing slug and the address or MLS number.
- clips: the planned clips in shot order, each with its scene name, the photo it came
  from, the job number, the downloaded clip file, and its motion result (moved or
  static).
- reel: the path to the finished joined video, once it exists.
- credits: the estimate and the amount actually charged.
- status: where the video is. One of: casting (planning the shots), generating (clips
  being made), stitched (the final video is joined and done).

If a session stops partway, Claude reads this file next time and offers to pick the
video back up from where it left off.
