---
name: helper
description: Turn Helper Mode on or off and check its status. Helper Mode makes Claude explain technical terms in plain English, harder during your first week.
disable-model-invocation: true
---

# /helper - Plain-English Helper Mode

Helper Mode makes Claude explain technical words in plain English as you go, so you
are never lost in developer jargon. It is ON by default. For your first week it
explains every technical term every time it comes up (you will not remember a word
from one explanation). After the week, it explains each term the first time it comes
up in a conversation. You can turn it on or off any time.

The state lives in `~/.claude/helper-mode.json`. A hook reads it on every turn and
quietly tells Claude how much to explain. You never edit that file by hand; use the
commands below.

## What the user typed

Look at what followed `/helper`:

- `/helper` or `/helper status` -> run `python3 ~/.claude/hooks/helper-mode.py status`
  and show the result. It says whether Helper Mode is on, and if you are still in
  the learning week, how many days are left.
- `/helper on` -> run `python3 ~/.claude/hooks/helper-mode.py on`. Turns it on and
  starts the learning week today if it was not already running.
- `/helper off` -> run `python3 ~/.claude/hooks/helper-mode.py off`. Answers go back
  to normal.
- `/helper reset` -> run `python3 ~/.claude/hooks/helper-mode.py reset`. Restarts the
  learning week from today (use this if you feel you need the extra explaining
  again).
- `/helper window N` -> run `python3 ~/.claude/hooks/helper-mode.py window N`, where
  N is a number of days. Sets how long the learning week lasts (default 7).

## After running

Print the command's one-line output to the user in plain English. Do not add jargon.
If they turned it off, remind them they can turn it back on with `/helper on`.
