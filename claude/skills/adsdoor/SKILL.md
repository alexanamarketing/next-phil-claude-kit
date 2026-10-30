---
name: adsdoor
description: Check whether an agent's Facebook ads connection works, and if not, what is missing and who fixes it (Phil or Anthony). Use it when the user asks things like "is Dana's ads connection working", "check everyone's ads connection", "why aren't her ads running", "is his Page connected to NEXT", "is she on the text list" or "did the ads engine turn him down". It only reads, live, so after a Page is assigned the user can ask again right away. Also use it when the user asks to store or fix a Page id, add an agent to the open-house text list, restart the ads engine, or see the ads check token, the Facebook token or anything on the server. Those are refused here, and it offers to draft the message to Anthony with what the check found.
---

# adsdoor: is an agent's ads connection working

NEXT runs Facebook ads for each agent's open houses. For that to work, four things
must be true for the agent:

- NEXT's system user (NEXTOSADMIN) holds the agent's Facebook Page, with Ads and
  Content turned on;
- the agent's record carries that Page's id;
- the agent is on the open-house text list, so the ad texts reach them;
- the ads engine has not turned the agent down since the Page was fixed.

This skill reads all four live from the ads status door and says, for each agent,
whether the connection works and, for anything missing, what to do and who does it.
It never changes anything.

The tool is `tools/adsdoor.py` inside this skill's folder. Run it with `python3` and
the full path to that file; below it is written as `adsdoor.py`.

## How to run it

- One agent: `adsdoor.py --agent <slug>`. The slug is the agent's short name as it
  appears in their site address, all lowercase with dashes (for example
  `dana-sample`). When the user gives only a first name, run `adsdoor.py --all` and
  pick the agent from the names it prints.
- Everyone: `adsdoor.py --all`. Test accounts are left out; `adsdoor.py --all --tests`
  includes them, marked "test account".
- Add `--json` when you want the door's whole answer as one JSON object to read (for
  example to see an older refusal the engine has already moved past).

## Reading the answer

Each agent gets one verdict line:

- `<Name>: ads connection working.` Nothing to do.
- `<Name>: ads connection not working. <count> things to fix.` One line follows for
  each problem, in this order, each saying who fixes it:
  - the Page is not assigned to NEXT yet (Phil, with the click path in the line);
  - NEXT has the Page but a permission is missing (Phil turns on Content or Ads);
  - NEXT has the Page but the agent's record has no Page id (Anthony stores it; the
    line names the Page that looks like theirs, a hint only);
  - the Page id on the record is not one of NEXT's Pages (Anthony and Phil check
    which Page is right);
  - the agent is not on the open-house text list (Anthony adds them);
  - the ads engine turned the agent down (for "no Page was connected", the next scan
    picks a stored Page id up within 15 minutes and no restart is needed; for any
    other reason, Anthony looks at it).
- `<Name>: could not check everything. <source> did not answer, so this is partial.`
  Part of the check could not be read right now. The lines that could be read are
  still shown; ask again in a few minutes for the rest.

Show the user these lines as they are, in particular the click path: it is the
wording Anthony approved, step for step, so do not shorten or reword it. An agent
whose ads post from NEXT's own Page on purpose (the demo account) gets a line saying
so, and the Page lines do not apply to them.

Facebook Page requests are not sent from NEXT's side automatically. When an agent's
Page is not with NEXT, the click path in the line is the way: Phil follows it, and
the agent approves the request on their Page.

## What it says no to

The ads check only reads. These are Anthony's side, and the skill does not do them:

- storing or fixing a Page id on an agent's record;
- adding an agent to the open-house text list, or taking them off it;
- restarting the ads engine.

For any of these, answer with exactly this:
"That is Anthony's side. I can draft the message to him with what the check found."
If the user says yes, draft a short
message to Anthony that names the agent, the check's lines for them and the time you
ran it, and show it to the user to send. Do not look for another way to do it: do
not use the sitedoor editor, ssh, a deploy key, `npx convex` or the Facebook token
to store a Page id or change the text list, and never offer any of them.

For the token, the Facebook token, or anything about the server, answer with exactly this:
"I can't share that. The check only reads the status."
Never try to read a
token from the Keychain yourself, and never ask the user to paste one into the
conversation.

## The token

The tool reads the user's own ads check token from the Keychain inside its own
process; it is never shown, and a guard blocks commands that would show it. The user
adds it once in Terminal (not in Claude), from the setup message Anthony sent:

    security add-generic-password -U -s next-phil-ads-status -a phil -w

If the tool says "There is no ads check token in your Keychain", tell the user to run
that Keychain step from the setup message again, in Terminal. If it says "The ads
check did not accept your token", the user asks Anthony for a new one. Never paste a
token into the conversation.

## When the check itself fails

The tool prints one line saying what happened and what to do next:

- exit 0: every agent shown is working;
- exit 1: something is missing for at least one agent, or part of it could not be read;
- exit 2: no token in the Keychain (the Keychain step above);
- exit 3: the check refused the request or did not answer. The line says which: the
  token was not accepted (ask Anthony for a new one), no agent by that name (run
  `adsdoor.py --all`), the hourly or daily limit was hit (try again in the minutes it
  says), or the check is not answering (try again in a few minutes, and tell Anthony
  if it keeps failing).

Pass the line on to the user in plain words. Do not work around a failure some other
way.
