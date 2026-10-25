# Claude Code Operating Contract

This file is the global boot cheatsheet. Claude auto-loads it at the start of every session.
It applies to every project in your vault. Project-specific rules live in each project's own CLAUDE.md.

## Quick Rules

These apply everywhere, always.

- INDEX-before-write: before creating any new .md file in a directory that has an INDEX.md, read the INDEX, add an entry for the new file, then write the file. The index-enforcer hook will block the write if you skip this.
- Run /sync before /clear: end-of-session doc updates (notes, HANDOFF, todo) must happen before compacting context. Work that is not synced will be lost.
- Never commit secrets or .env files to git. Check every staged file before committing. If you see a credential in a file, do not repeat it in your response.
- Keys the user pastes (an API key, a token): just use them, no lectures about rotating them. Store the key in the macOS Keychain, and get it to an app as a Vercel environment variable or with a Bash command that copies it from the Keychain into `.env.local` without printing it. Never commit a key, and never echo it back in a reply or a file. Claude may read env files to find a missing setting but cannot edit them (the block-secrets hook); a push is scanned only for the commits that are leaving the machine (the secret-guard hook), and a fake test value that trips it goes in the repo's `.gitleaks.toml` allowlist (template: `~/.claude/references/gitleaks-allowlist-template.toml`).
- Filenames: lowercase-kebab-case.md. Versions: v1, v2, v3 (never FINAL, DONE, COMPLETE).
- No em dashes in prose. Use commas, periods, or parentheses instead.
- Delete files with the configured trash command (os_trash in config.yaml), never a permanent recursive delete.
- Plain English by default: the user is a real-estate agent, not a developer. Lead with the point in one sentence, and explain any technical term in ordinary words. Helper Mode (below) enforces this; the user can also type `/explain` for a plain-English rewrite.
- At session wrap, if you learned a durable fact about a tool (Gmail, FlexMLS, GoHighLevel, Canva, and the rest), run `/toolupdate` so Claude remembers it next time.

## Agent Output Discipline

Context is a budget. Spend it on work, not dumps.

- Long or unbounded command output goes to a file first, then read only the slice you need. Never pipe a large dump straight into the conversation.
- Prefer compact output flags when a CLI offers them: `--json` with selected fields, `--plain`, `--quiet`. Ask for the fields you need, not everything.
- Truncate by default. Fetch full output only when the task actually requires it.
- Make empty results explicit ("0 results", never silent blank output), and on failure report the cause plus the next command or file to check.
- Any script or CLI written for this vault must run without interactive prompts, exit 0 on success and nonzero on failure, print counts on success ("Rebuilt 12 indexes"), and end with the likely next command.

## Session Checklist / Shortcuts

### Starting a session

1. Run `/project` to load a project (or `/project system` to set up your workspace identity).
2. Check the top pending tasks shown by the loader.
3. If HANDOFF.md says "Fill out ABOUT.md first," do that before any other work.

### Common commands

- `/project [shortcut]` — load a project by shortcut or browse a numbered list
- `/project system` — load the system meta-project (your workspace identity + workflow notes)
- `/new-project` — scaffold a new project from the template
- `/sync` — end-of-session doc maintenance (notes, HANDOFF, todo). Run before /clear.
- `/archive-docs` — trim notes.md and todo.md when they get long (threshold: ~1000 lines)
- `/doctor` — verify the installation (python, node, Claude CLI, hooks, config, vault skeleton)
- `/markdown` — on-demand markdown style reference

### Typical workflow

1. Start: `/project <name>` to load context
2. Work (read HANDOFF.md for current state, check todo.md for next tasks)
3. Sync: `/sync` before any `/clear` or session end
4. Archive: `/archive-docs` when notes.md or todo.md get unwieldy

### Utility shortcuts

- `/xc` — copy the last output to clipboard (uses os_copy from config.yaml)
- `/open` — open the last file with the system viewer (uses os_open from config.yaml)
- `/check` — verify a claim or output made earlier in the session
- `/tip` — display a workflow tip
- `/explain` — say the last answer again in plain English, no jargon
- `/helper` — turn plain-English Helper Mode on or off, or check it (on by default)

## Helper Mode and tool memory

Two things run quietly in the background for a non-technical user:

- Helper Mode makes Claude explain technical terms in plain English. It is on by
  default, and for the first week it re-explains terms every time so they stick.
  Toggle or check it with `/helper`.
- Tool memory: Claude keeps notes on the tools you use (in
  `~/.claude/references/tool-modules/`). It fills these in as you work and reads
  them back automatically. Save new notes at session wrap with `/toolupdate`.

Your work also saves itself: every edit is committed to a private version history
in your vault automatically. You never type a git command.

## Markdown House Style

Type `/markdown` any time for the house style, or read the full guide: `<vault-root>/docs/MARKDOWN-STYLE-GUIDE.md`

<!-- kit-block:sitedoor v2 -->
## Agent websites: content, design and code

- Content on an agent's site (the record: name, bio, title, phone, testimonials, past sales, service areas, social links, license, office address, website and legal links, headshot, logos, partner details; and the homepage draft: SEO, hero, about text, sections) goes through the `sitedoor` skill first, using your own editor token from the Keychain. It shows the change first, writes only after you say yes, logs it in the MLS log and can undo it. Before applying, say where it will show: record fields on the agent's portfolio page in about five minutes, a new testimonial first on that agent's listing pages, a past sale on the homepage only with a photo and in the top 24 by price, and homepage draft fields in the draft only, live with Anthony's next publish.
- Design and everything else on the site (layout, styling, colours, fonts, spacing, new or reworked sections, a different look for one agent, any page of properties.nextrealestate.team or an agent site) is a code change you make yourself in the user's copy of the website code. Never tell the user it is out of reach or needs Anthony. Find or set up that copy with `bash ~/.claude/skills/sitedoor/tools/site-checkout.sh` (add `--clone` to copy it from GitHub when none is found), run `git fetch origin` there and read the current rules with `git show origin/main:AGENTS.md` (section "Design Changes from Phil's Chat"), then follow them: a new branch, the change, `bash scripts/gate.sh`, push the branch, show the user the Vercel preview link, and merge to main only after the user says yes. Never skip a check (`--no-verify`, force-push), never run `npx convex dev` or `npx convex deploy`, and never put a draft agent site live.
- The editor refuses only publishing or unpublishing a site, fields that would break things (the sign-in email, domains, GoHighLevel ids and forms, tracking pixels, MLS data, record ids), Phil's and Jim's own records, open houses, listings, and deleting an agent, a site or a whole record. Those refusals, anything a repo check or guard stops that fixing the change cannot pass, and backend changes under `convex/` (they need a deploy key the user does not hold) are the only edge cases: make them as a pull request on GitHub in DevNextRealEstate/next-listing-pages; Anthony reviews and merges it. Do not work around a refusal: do not offer a deploy key, `npx convex` or a change to the door's code, and never use a deploy key or `npx convex` for agent data.
<!-- /kit-block:sitedoor -->
