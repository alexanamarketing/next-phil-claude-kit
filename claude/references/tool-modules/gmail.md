# gmail - Tool Module

Gmail - your email. Claude's growing notes on composing, filtering, labeling, and finding messages.

## Records (canonical, machine-read)

Claude's memory of this tool. It fills itself in as you work: at the end of a
session, `/toolupdate` saves anything durable Claude learned about gmail here,
and Claude reads it back the next time you touch gmail. You never edit this by
hand. It starts empty, which is fine.

```json
{
  "schema_version": 1,
  "active": [],
  "journal": []
}
```
