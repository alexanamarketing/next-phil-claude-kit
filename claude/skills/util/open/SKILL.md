---
name: open
description: Open the last-mentioned file or a specified path using the system file opener. Use when you want to view a file outside the terminal.
---

# /open - Open a File

Opens a file with the system's default application using the `os_open` command from `config.yaml`.

## Usage

```
/open [path]
```

- With a path: opens that file
- Without a path: opens the last file path mentioned in the conversation

## What It Does

1. Read `os_open` from `<vault_root>/config.yaml` (e.g. `xdg-open` on Linux, `open` on macOS)
2. Resolve the file path (explicit argument, or last path mentioned in context)
3. Run: `<os_open> <path>`
4. Confirm: "Opened <path>"

## Notes

- Use this for files (documents, HTML, images). For URLs, open them directly in a browser instead — `os_open` on some systems routes URLs to unexpected applications.
- If `os_open` is not set in config, fall back to `xdg-open` on Linux or `open` on macOS.
- If the path does not exist, report the error rather than silently failing.
