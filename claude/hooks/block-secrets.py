#!/usr/bin/env python3
"""
Stop Claude from WRITING to files that hold real secrets.

Read is always allowed: Claude may need to look at an env file to tell you
which setting is missing, and it never repeats a value back (CLAUDE.md rule).
Edit, Write and MultiEdit are blocked on an exact set of secret-file names,
matched on the file name or its folder, never on a word that merely appears
somewhere in the path (so `api-key-form.tsx` or `secrets-panel.tsx` are fine).
The hook reads `tool_name` from the payload to tell Read from Edit/Write; a
payload with no tool_name is treated as a write.

Blocked for Edit/Write/MultiEdit:
  .env and .env.<anything>, except .env.example / .env.sample / .env.template
  .envrc .npmrc .pypirc .netrc .git-credentials
  *.pem *.key *.p12 *.pfx *.jks *.keystore
  id_rsa id_ed25519 id_ecdsa id_dsa (exact names)
  any name ending in .env (prod.env, staging.env, app.env)
  credentials, credentials.<anything>, *credentials*.json/.yml/.yaml/.toml
  secrets.<anything>, *secrets*.json/.yml/.yaml/.toml/.env
  service-account*.json
  anything under ~/.ssh/ or ~/.aws/, and ~/.claude/.credentials.json

Exit codes: 0=allow, 2=block (stderr fed to Claude)
"""
import json
import os
import sys

READ_TOOLS = {'Read'}

ENV_ALLOWED_SUFFIXES = ('.example', '.sample', '.template')

EXACT_NAMES = {
    '.env', '.envrc', '.npmrc', '.pypirc', '.netrc', '.git-credentials',
    'id_rsa', 'id_ed25519', 'id_ecdsa', 'id_dsa',
    'credentials', 'credentials.json', 'secrets.json', 'secrets.yml', 'secrets.yaml',
}

KEY_SUFFIXES = ('.pem', '.key', '.p12', '.pfx', '.jks', '.keystore')

# Config-file extensions that turn a name containing "credentials" or "secrets"
# into a secret store. Source files (realtor_secrets.ts, secrets-panel.tsx) and
# docs (credentials-guide.md) are not in this list, so they stay writable.
CREDENTIALS_EXTS = ('.json', '.yml', '.yaml', '.toml')
SECRETS_EXTS = CREDENTIALS_EXTS + ('.env',)

# Explicit path-substring allowlist (sidecar file, one entry per line, '#' comments).
# For a file that matches a blocked name but holds no secret value. Keep narrow;
# never list a real .env or credential store.
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
    except Exception:
        return False
    return False


def under(path, folder):
    folder = os.path.normcase(os.path.abspath(os.path.expanduser(folder)))
    return path == folder or path.startswith(folder + os.sep)


def blocked_reason(file_path):
    """Returns why the path is a secret file, or None when it is not one."""
    full = os.path.normcase(os.path.abspath(os.path.expanduser(file_path)))
    name = os.path.basename(full).lower()

    if name.startswith('.env.'):
        if name.endswith(ENV_ALLOWED_SUFFIXES):
            return None
        return 'an env file'
    if name in EXACT_NAMES:
        return 'a secret file name'
    if name.endswith('.env'):
        return 'an env file'
    if name.startswith('credentials.') or ('credentials' in name and name.endswith(CREDENTIALS_EXTS)):
        return 'a credentials file'
    if name.startswith('secrets.') or ('secrets' in name and name.endswith(SECRETS_EXTS)):
        return 'a secrets file'
    if name.endswith(KEY_SUFFIXES):
        return 'a key or certificate file'
    if name.startswith('service-account') and name.endswith('.json'):
        return 'a service account key'
    if under(full, '~/.ssh') or under(full, '~/.aws'):
        return 'a file in your SSH or AWS key folder'
    if full == os.path.normcase(os.path.abspath(os.path.expanduser('~/.claude/.credentials.json'))):
        return "Claude's own login file"
    return None


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # Allow if can't parse

    if data.get('tool_name') in READ_TOOLS:
        sys.exit(0)  # Reading is allowed; values are never repeated back

    tool_input = data.get('tool_input', {}) or {}
    file_path = tool_input.get('file_path', '') or tool_input.get('path', '')
    if not file_path or not isinstance(file_path, str):
        sys.exit(0)

    reason = blocked_reason(file_path)
    if reason is None:
        sys.exit(0)

    if is_allowlisted(file_path.lower()):
        sys.exit(0)

    print(f"BLOCKED: writing to '{os.path.basename(file_path)}' denied ({reason}).", file=sys.stderr)
    print("Secret files are changed by you, not by Claude. To give an app a key, put it in a "
          "Vercel environment variable, or ask Claude to copy it from your Keychain into "
          ".env.local with a Bash command that never prints it.", file=sys.stderr)
    sys.exit(2)


if __name__ == '__main__':
    main()
