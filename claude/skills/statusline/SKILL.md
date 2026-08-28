---
name: statusline
description: /statusline switches the little bar at the bottom of the Claude window between simple (the default, plain-English) and technical (developer details). /statusline technical turns on the developer bar; /statusline simple goes back; bare /statusline reports the current mode and explains the two options.
disable-model-invocation: true
---

# /statusline - Status Bar Detail Toggle

The bar at the bottom of the Claude window has two looks. The setting is
`status_detail` in `<vault_root>/config.yaml`, right next to `help_mode`, and is
written the exact same way `/help on|off` writes `help_mode`. Absent means
`simple`.

- **simple** (default): the everyday bar. It shows the project you are in,
  whether Helper Mode is on, and a `/help` nudge. This is the one for a
  non-technical user.
- **technical**: a developer bar. It shows context-window usage, the model name,
  the session cost, and, when you are in a git repo, the branch with a count of
  changed files and the lines added and removed. Turn this on if you are a
  developer who wants those numbers.

## Step 0: Read Config

Read `<vault_root>/config.yaml` (to locate `<vault_root>`, read
`~/.claude/starter-kit/config.json` first, then the `VAULT_ROOT` env var, else
ask). Get the current `status_detail` value (treat an absent key as `simple`).

## /statusline technical or /statusline simple

Edit the `status_detail` line in `<vault_root>/config.yaml` to the new value
(`technical` or `simple`). If the `status_detail` key is absent, insert a line
`status_detail: <value>` immediately after the `help_mode` line. Confirm with
exactly one line:

```
Status line is now [simple/technical].
```

The bar updates on its next refresh. Do NOT print anything else after toggling.

## bare /statusline

Report the current mode and explain the two options in plain English:

```
Status line: [simple/technical]  (change with /statusline simple or /statusline technical)

Two options:
  simple     - the everyday bar (default). Shows the project you are in, whether
               Helper Mode is on, and a reminder that /help lists your commands.
  technical  - a developer bar for a technical user. Shows context-window usage,
               the model, the session cost, and your git branch and changes.

Most people want simple. Type /statusline technical only if you are a developer
who wants those numbers; /statusline simple brings the plain bar back.
```
