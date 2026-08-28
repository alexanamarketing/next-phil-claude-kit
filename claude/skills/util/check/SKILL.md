---
name: check
description: Verify a claim made earlier in the session with a small verification table. Use when you want to confirm a fact, file path, command output, or earlier assertion before acting on it.
---

# /check - Verify Earlier Claims

Run a quick verification pass on something asserted earlier in this session.

## What to Do

1. Identify what claim or fact needs verification (from `$ARGUMENTS` or recent context)
2. Run the minimal commands needed to confirm or refute it (file exists, grep for a pattern, run a command and check output, read the relevant lines)
3. Report the result as a small table:

```
Claim                              | Result  | Evidence
-----------------------------------|---------|-----------------------------
File exists at path/to/file.md     | PASS    | ls returned the file
Config has vault_root set          | PASS    | grep found "vault_root:" line
Script outputs "done" on success   | FAIL    | actual output was "error: ..."
```

4. If a claim failed, note what the actual state is and what the fix would be.

## When to Use

- Before acting on an assumption about file contents or structure
- After running a command that might have silently failed
- When you said "X is set up" and want to prove it
- Any time something feels uncertain and verification takes under a minute
