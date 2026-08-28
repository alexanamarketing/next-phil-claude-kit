# Tool Modules

Claude's memory of the tools you use. Each file here is one tool. As you work,
Claude notices durable facts and gotchas about a tool (how a search works, a step
that always trips people up) and saves them here at the end of a session with
`/toolupdate`. The next time you touch that tool, Claude reads its notes back so it
does not re-learn the same thing. The notes start empty and fill in over time. You
never edit these by hand.

## Domain-injected modules

- [gmail.md](gmail.md) - Gmail, your email.
- [google-docs-drive.md](google-docs-drive.md) - Google Docs, Sheets, and Drive.
- [flexmls.md](flexmls.md) - FlexMLS, the MLS listing portal.
- [gohighlevel.md](gohighlevel.md) - GoHighLevel, your client CRM.
- [canva.md](canva.md) - Canva, your design tool.

## Adding a new tool module

When you start using a tool that is not listed here, Claude can scaffold a new
module for it with `tool-module-new.py <tool>` (this adds the file, wires up
detection, and seeds the glossary). Then the first `/toolupdate` that touches the
tool fills in the first note.
