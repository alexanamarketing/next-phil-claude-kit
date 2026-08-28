---
name: xc
description: Copy provided text to the clipboard. Use when you want to put something directly on the clipboard for pasting elsewhere.
---

# /xc - Copy to Clipboard

Copies the provided text to the system clipboard using the `os_copy` command from `config.yaml`.

## Usage

```
/xc <text to copy>
```

## What It Does

1. Read `os_copy` from `<vault_root>/config.yaml` (e.g. `xclip -selection clipboard` on Linux, `pbcopy` on macOS)
2. Run: `printf '%s' "<text>" | <os_copy>`
3. Confirm: "Copied to clipboard."

## Notes

- For multi-line text, pipe it through a heredoc rather than inline
- If `os_copy` is not set in config, fall back to `xclip -selection clipboard` on Linux or `pbcopy` on macOS based on the detected OS
- The text is copied as-is, with no extra newline appended
