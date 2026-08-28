#!/usr/bin/env python3
"""
Block Claude from reading/editing sensitive files.
Exit codes: 0=allow, 1=error, 2=block (stderr fed to Claude)
"""
import json
import sys
import os

# Patterns to block
BLOCKED_PATTERNS = [
    '.env',
    'credentials',
    'secrets',
    'api-key',
    'api_key',
    '.pem',
    '.key',
]

# Exceptions (allowed even if they match blocked patterns)
ALLOWED_EXCEPTIONS = [
    '.env.example',
    '.env.template',
    '.env.sample',
]

# Explicit path-substring allowlist (sidecar file, one entry per line, '#' comments).
# For SOURCE files that falsely match a blocked pattern (e.g. realtor_secrets.ts defines
# functions, holds no secret values). Keep narrow; never list .env/credential stores.
ALLOWLIST_FILE = os.path.expanduser('~/.claude/hooks/block-secrets-allow.txt')


def is_allowlisted(file_path_lower):
    try:
        with open(ALLOWLIST_FILE) as f:
            for line in f:
                entry = line.strip().lower()
                if not entry or entry.startswith('#'):
                    continue
                if entry in file_path_lower:
                    return True
    except FileNotFoundError:
        return False
    except Exception:
        return False
    return False


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)  # Allow if can't parse

    tool_input = data.get('tool_input', {})

    # Get file path from different tool input formats
    file_path = tool_input.get('file_path', '') or tool_input.get('path', '')

    if not file_path:
        sys.exit(0)  # Allow if no file path

    # Normalize path
    file_path_lower = file_path.lower()
    basename = os.path.basename(file_path_lower)

    # Check exceptions first
    for exception in ALLOWED_EXCEPTIONS:
        if basename.endswith(exception):
            sys.exit(0)  # Allow

    # Explicit allowlist (narrow source-file exemptions)
    if is_allowlisted(file_path_lower):
        sys.exit(0)  # Allow

    # Check blocked patterns
    for pattern in BLOCKED_PATTERNS:
        if pattern in file_path_lower:
            print(f"BLOCKED: Access to '{os.path.basename(file_path)}' denied (matches '{pattern}')", file=sys.stderr)
            print("If you genuinely need to open this file, do it yourself outside Claude.", file=sys.stderr)
            sys.exit(2)  # Block and feed stderr to Claude

    sys.exit(0)  # Allow

if __name__ == '__main__':
    main()
