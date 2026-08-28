---
project: [project-slug]
client: "[Client Name (Company)]"
types: [type1, type2]
phase: "[freeform - e.g. discovery, setup, build, active, maintenance, wrap-up]"
priority: [high|medium|low]
invoice_status: [current|pending|overdue|n/a]
monthly_value: [number, omit if not retainer]
last_updated: [YYYY-MM-DD]
latest_update: "[one-line summary of last session's work]"
session_notes: "[more detailed session context]"
waiting_on: [null or "description"]
waiting_since: [YYYY-MM-DD or null]
next_follow_up: [YYYY-MM-DD or null]
tags: [client/[slug], type/[kind]]
---

# Todo - [PROJECT NAME]

<!--
  Schema notes:
  - project: folder slug (must match folder name under active/)
  - status: derived from folder location (active/, inactive/, etc.) - do not include as field
  - types: freeform labels for this project (e.g. website, research, design, development, writing)
  - phase: freeform string describing current project phase
  - monthly_value: for retainer clients only. For fixed-price, use contract_value and payment_terms instead
  - latest_update / session_notes: updated by /sync each session
  - invoice_status, tags: optional, include when relevant
  - Agent loading: read frontmatter, Last reviewed, Active Now, and Waiting / Verify by default. Stop before Backlog unless the user asks for planning or cleanup.
-->

Last reviewed: [YYYY-MM-DD]
Default agent read: frontmatter, Last reviewed, Active Now, Waiting / Verify

## Active Now
<!-- prefer 3 items, max 5; move overflow to Backlog -->

- [ ] [Concrete next action] {due:YYYY-MM-DD}

## Waiting / Verify

- [ ] [Waiting] [What is blocked]. Owner: [name/tool/client]. Check: [YYYY-MM-DD]
- [ ] [Verify] [What needs checking]. Check: [YYYY-MM-DD]

## Backlog

- [ ] [Stored task or idea with enough context to recover later]

## Someday

- [ ] [Future idea or potential upsell]

## Completed

- [x] YYYY-MM-DD [Completed task description]
