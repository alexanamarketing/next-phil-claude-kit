# The full recipe for a listing video

This is the long version of how a listing video gets made. You never need to read
it. Claude follows it for you. It is here for the times you are curious, or you want
to know exactly what is being sent to the video tool. Say "show me the full recipe"
any time and Claude opens this.

## What a finished video looks like

A listing video is about seven to eight short clips, about five seconds each, joined
into one reel of about forty seconds. Your starter set has seven rooms; an eighth clip
is added only when a listing needs a stand-in room. The clips move outside-in and then
back out, like a walk through the home:

- The first clip is always the front of the house.
- The last clip is always the backyard or pool.
- The clips in the middle are the rooms that sell the home: the living room, the
  kitchen, the dining room, the primary bedroom, the primary bathroom, and the entry
  if the photos have one.

If a home is missing one of those rooms, Claude builds a stand-in from the nearest
starter scene. A home with no dining room might get a second bedroom instead. A home
with no pool might get a covered patio or a nearby park. You decide; Claude suggests.

## The one rule behind every clip: the camera has to move

Every clip names one camera move and sticks to it: a slow push in, a slow pull back,
or a slide across the room. This is the whole reason a clip looks alive instead of
frozen.

If a clip is told to rely on light alone (a soft glow, a change in the light), the
video tool holds the camera still and you get a photo that barely breathes. That is
the number one way a clip comes out wrong. So every scene leads with a real move, and
Claude checks each finished clip to make sure it actually moved before showing it to
you. About one clip in five needs a quick redo. That is normal and not your fault.

## The three things you can change on a scene

Only three knobs change what you see:

- The camera move: push in, pull back, or slide across.
- The direction: toward the door, left to right, and so on.
- The speed: slow or a touch faster.

Everything else is held steady on purpose (see the locked list below). The light and
the time of day come from the photo you pick, not from the scene. So if you want a
brighter or a warmer look, pick a different photo. The tool cannot relight a room or
change day into evening.

## The locked list (the keep-the-room-exactly-as-it-is instructions)

Every clip carries a fixed instruction to change nothing about the room. In full, it
tells the tool: no new objects, no people, no pets, no text overlays, no watermarks,
no color shift, no style transfer, no added plants, no altered architecture, no
morphing, no warping, no distortion, no flickering, no jitter, no lens flares, no CGI
look, no cartoon rendering, no oversaturation, no relighting, no time-of-day change,
no weather change.

Every clip also carries the look line: high-end real estate cinematography,
Architectural Digest feel, smooth steady confident camera, premium listing energy,
crisp detail, shallow depth of field.

You never type any of that. It rides along with every clip automatically.

## The settings behind the scenes

Each clip is made with the same settings: the seedance_2_0 model, sixteen-by-nine
shape, 720p quality, five seconds long, standard mode, no audio. You do not set these;
Claude passes them for you.

## What each clip and each video costs

Cost is measured in credits, and your plan refills them every month.

- One clip is about 22 credits.
- A straight run of your seven starter scenes is about 158 credits. A full eight-clip
  video (when a listing needs a stand-in room) is about 180 credits.
- Every redo is a fresh clip, so it costs about 22 credits again.
- A room you already made and approved this session is reused in the reel at no extra
  charge; the batch cost only covers the new clips.

Claude always shows you the cost and your balance before anything is charged, and
nothing is charged until you say yes. A clip cannot be cancelled once it starts, so the
cost is shown first, every time.

## Where the photos come from

Two ways:

- Give Claude the MLS number. Claude pulls the public listing photos, lays them out as
  a labeled sheet, reads them, and matches each to a room. The public photo web address
  follows a fixed pattern keyed to the MLS number, counting the photos up from the first
  one until there are no more.
- Use your own photos. Drag the photo file from Finder into this window and its location
  appears; then press return. Claude picks it up from there.

## What Claude runs for you (you never type these)

You talk; Claude runs the tool. For reference, these are the commands behind the work:

- Send a clip to be made (it comes back with a job number right away):
  `higgsfield generate create seedance_2_0 --prompt "..." --image-references <photo.jpg> --aspect-ratio 16:9 --resolution 720p --duration 5 --mode std --generate-audio=false --json`
- Check on a clip and get its finished web address: `higgsfield generate get <id> --json`
- Find recent clips if a session was interrupted: `higgsfield generate list --video`
- Check a cost before a batch: `higgsfield generate cost seedance_2_0 --prompt "..."`
- Check what was actually charged after: `higgsfield account transactions`
- Check your balance: `higgsfield account status`

## What Claude does versus what you decide

| Claude does | You decide |
| --- | --- |
| Pulls the photos and matches them to rooms | Which listing, and which photos to use |
| Fills in the settings, the look line, and the locked list | The camera move, direction, and speed on a scene |
| Shows the cost and balance before every charge | Whether to say yes to a charge |
| Checks each clip actually moved | Whether you like a clip or want a redo |
| Names a new scene and saves it for you | The final name for a scene |
| Joins the clips into one video | When the video is ready to send |
