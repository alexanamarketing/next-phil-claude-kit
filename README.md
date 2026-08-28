# Your Claude Code setup

This is a ready-made setup for Claude Code, tuned for a real-estate agent who is not
a developer. It gives Claude a tidy place to keep your projects, a set of quiet
safety nets so nothing goes wrong, and a plain-English Helper Mode so you are never
lost in technical words.

You do not need to understand the parts below to use it. Install it once, then just
open Claude and work.

A few plain-English terms used here:
- "Claude Code" is the app you type into to work with Claude on your Mac.
- "Terminal" is the plain text window on your Mac where you run the two install
  commands. You open it once for setup and rarely after that.
- "Vault" is just the folder where all your projects and notes live.

## What you get

- A home for your work. Projects live in one vault folder, each with its own notes,
  so you (and Claude) can always find things.
- Quiet safety nets. Claude will refuse to run a dangerous command, will not open
  files that hold passwords, and will not let a password get saved into your history.
- Automatic saving. Every change is saved to a private version history in your vault.
  You never type a save command; it just happens.
- Helper Mode. Claude explains technical words in plain English as it goes. It is on
  by default, and for your first week it re-explains words every time so they stick.
- Tool memory. As you work with your tools (Gmail, FlexMLS, GoHighLevel, Canva),
  Claude quietly builds up notes about them and reads them back next time.

## Install it (one time)

You will run two commands in the Terminal. On a Mac, open Terminal from
Applications > Utilities > Terminal.

1. Get the basics in place (git, Node, the Claude app). In the Terminal, go to this
   folder and run:

   ```
   ./bootstrap.sh
   ```

   Say yes to each step. If it offers to install `gitleaks` (a tool that double-checks
   nothing secret gets saved), yes is a good choice, but it is optional.

2. Log in to Claude, then install the setup:

   ```
   claude login
   ./setup.sh
   ```

   It will ask where your vault folder should live. The default (`~/vault`) is fine.

That is it. One Mac note: the "move to Trash" command works best with a small extra
tool. If setup mentions it, run `brew install trash` once. It is optional and nothing
breaks without it.

## The daily loop

1. Open Claude Code.
2. Type `/project` and pick what you are working on (or `/new-project` to start a new
   one).
3. Do the work. Ask Claude for whatever you need.
4. When you are done for now, type `/sync`. This saves your notes so the next session
   picks up where you left off.

That is the whole rhythm: `/project`, work, `/sync`.

## What do I type (cheat-sheet)

Six commands cover almost everything:

- `/project` - open or continue a project to work on (or `/project system` the first
  time, to set up your profile).
- `/new-project` - start a new project.
- `/sync` - save your progress at the end of a session. Do this before you close.
- `/helper` - turn plain-English Helper Mode on or off, or check it.
- `/explain` - if an answer had jargon, get it again in plain words.
- `/help` - a reminder of what these commands do and how to use them day to day.

When you first install, this same list shows up each time you open a project, so it is
easy to learn. Once you know it, type `/help off` to hide it. `/help on` brings it
back, and `/help` shows the full list any time.

One thing that trips people up: `/helper` and `/help` are different.
/helper explains the words; /help lists the commands.

## Helper Mode (plain English)

Helper Mode makes Claude explain technical words in plain English as you go, so you
are never lost. It is ON from the day you install. For your first week it explains
every technical word every time it comes up, because a word rarely sticks after one
explanation. After that week it explains each word the first time it appears in a
conversation.

- `/helper` - see whether it is on and how many days are left in your learning week.
- `/helper off` - turn it off (answers go back to normal).
- `/helper on` - turn it back on.
- `/helper reset` - start the learning week over (if you want the extra explaining
  again).

You can also type `/explain` at any time to have the last answer rewritten in plain
English.

## The bar at the bottom of your screen

While you work, a small line sits at the bottom of the Claude window. It is just a
quiet reminder, not something you click. It shows three things:

- the project you are in (the folder you are working in, or "home" when you are not
  inside a project yet),
- whether Helper Mode is on or off, so you always know if plain-English explanations
  are running,
- a nudge that typing `/help` lists your commands.

There is nothing to set up and nothing to press. If you ever forget where you are or
whether Helper Mode is on, glance at that bar.

## What the safety nets do for you

These run quietly. You will only notice them if they stop something risky:

- Dangerous commands are blocked. If a command would delete a lot of files or run an
  unknown installer from the internet, Claude refuses and tells you why.
- Password files are protected. Claude will not open files that hold passwords or
  keys, and it will not let a password get saved into your project history.
- Your work saves itself. Every change is committed to a private version history in
  your vault, automatically. You never type a save command.

## Getting unstuck

- `/help` - a short reminder of the commands.
- `/explain` - plain-English rewrite of the last answer.
- `/doctor` - checks that everything is installed correctly and tells you what to fix
  if not.

## Removing it

If you ever want to remove the setup, run `./uninstall.sh`. It only removes the parts
this kit installed and never touches your own project files. Add `--dry-run` first to
see what it would do without changing anything.
