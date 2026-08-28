# canva - Tool Module

Canva - your design tool. Notes on designs, your brand kit, templates, and exporting.

## Records (canonical, machine-read)

Claude's memory of this tool. It fills itself in as you work: at the end of a
session, `/toolupdate` saves anything durable Claude learned about canva here,
and Claude reads it back the next time you touch canva. You never edit this by
hand. It starts empty, which is fine.

```json
{
  "schema_version": 1,
  "active": [],
  "journal": []
}
```
