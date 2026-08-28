# gohighlevel - Tool Module

GoHighLevel - your client CRM. Notes on contacts, follow-up workflows, pipelines, and the calendar.

## Records (canonical, machine-read)

Claude's memory of this tool. It fills itself in as you work: at the end of a
session, `/toolupdate` saves anything durable Claude learned about gohighlevel here,
and Claude reads it back the next time you touch gohighlevel. You never edit this by
hand. It starts empty, which is fine.

```json
{
  "schema_version": 1,
  "active": [],
  "journal": []
}
```
