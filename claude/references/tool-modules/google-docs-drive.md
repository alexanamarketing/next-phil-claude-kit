# google-docs-drive - Tool Module

Google Docs and Drive - your documents, spreadsheets, and files. Notes on creating, editing, and sharing.

## Records (canonical, machine-read)

Claude's memory of this tool. It fills itself in as you work: at the end of a
session, `/toolupdate` saves anything durable Claude learned about google-docs-drive here,
and Claude reads it back the next time you touch google-docs-drive. You never edit this by
hand. It starts empty, which is fine.

```json
{
  "schema_version": 1,
  "active": [],
  "journal": []
}
```
