# flexmls - Tool Module

FlexMLS - the MLS listing portal. Notes on searching, pulling listings, photos, and exports.

## Records (canonical, machine-read)

Claude's memory of this tool. It fills itself in as you work: at the end of a
session, `/toolupdate` saves anything durable Claude learned about flexmls here,
and Claude reads it back the next time you touch flexmls. You never edit this by
hand. It starts empty, which is fine.

```json
{
  "schema_version": 1,
  "active": [],
  "journal": []
}
```
