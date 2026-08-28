#!/usr/bin/env python3
"""doctor.py — verify the Claude starter kit installation.

Prints a human-readable pass/fail report with the exact fix for each
failure. Exits 0 even when failures are found; the report summarises
the count of failures at the end.

Usage:
    python3 doctor.py
    python3 doctor.py --vault-root ~/MyVault
    python3 doctor.py --json   # machine-readable output
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


class CheckResult(NamedTuple):
    name: str
    passed: bool
    message: str       # one-line status description
    fix: str           # exact command or step to resolve a failure
    fatal: bool = True # False = non-fatal (optional plugin, claude login)


# ---------------------------------------------------------------------------
# Vault root detection
# ---------------------------------------------------------------------------

def _find_vault_root(cli_arg: Optional[str] = None) -> Optional[Path]:
    """Return the vault root path or None if it cannot be determined."""
    if cli_arg:
        return Path(cli_arg).expanduser().resolve()

    for env_var in ("VAULT_ROOT", "HOOK_VAULT_ROOT"):
        env = os.environ.get(env_var)
        if env:
            return Path(env).expanduser().resolve()

    # Walk up from this script looking for active/ marker
    here = Path(__file__).resolve().parent
    for p in [here, *here.parents]:
        if (p / "active").is_dir():
            return p
        if p == p.parent:
            break

    # Fallback: parent of scripts/
    return here.parent if (here.parent / "active").is_dir() else None


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def check_python() -> CheckResult:
    """Python 3.8+ is required."""
    ver = sys.version_info
    if ver >= (3, 8):
        return CheckResult(
            name="Python version",
            passed=True,
            message=f"Python {ver.major}.{ver.minor}.{ver.micro}",
            fix="",
        )
    return CheckResult(
        name="Python version",
        passed=False,
        message=f"Python {ver.major}.{ver.minor} found (3.8+ required)",
        fix="Install Python 3.8+ via your package manager or pyenv:\n"
            "  curl https://pyenv.run | bash && pyenv install 3.11.0 && pyenv global 3.11.0",
    )


def check_pyyaml() -> CheckResult:
    """pyyaml is optional but recommended (hooks work without it)."""
    try:
        import yaml  # noqa: F401
        return CheckResult(
            name="pyyaml",
            passed=True,
            message="pyyaml is installed",
            fix="",
        )
    except ImportError:
        return CheckResult(
            name="pyyaml",
            passed=False,
            message="pyyaml not installed (hooks use fallback parser — install for reliability)",
            fix="pip install pyyaml\n  # or: pip3 install pyyaml",
            fatal=False,
        )


def check_node() -> CheckResult:
    """Node.js is required for the Claude Code CLI."""
    node = shutil.which("node")
    if not node:
        return CheckResult(
            name="Node.js",
            passed=False,
            message="node not found on PATH",
            fix="Install Node.js via nvm (recommended):\n"
                "  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash\n"
                "  source ~/.bashrc && nvm install --lts",
        )
    try:
        result = subprocess.run(
            ["node", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        version = result.stdout.strip()
        try:
            major = int(version.lstrip("v").split(".")[0])
        except (ValueError, IndexError):
            major = 0
        if major > 0 and major < 18:
            return CheckResult(
                name="Node.js",
                passed=False,
                message=f"Node.js {version} found; 18+ required (Claude Code CLI requirement)",
                fix="Upgrade Node.js via nvm:\n"
                    "  nvm install --lts\n"
                    "  nvm use --lts\n"
                    "  nvm alias default node",
            )
        return CheckResult(
            name="Node.js",
            passed=True,
            message=f"Node.js {version}",
            fix="",
        )
    except Exception as e:
        return CheckResult(
            name="Node.js",
            passed=False,
            message=f"node found but could not run: {e}",
            fix="Reinstall Node.js via nvm: https://github.com/nvm-sh/nvm",
        )


def check_npm() -> CheckResult:
    """npm is required (ships with Node.js) for installing the Claude Code CLI."""
    npm = shutil.which("npm")
    if not npm:
        return CheckResult(
            name="npm",
            passed=False,
            message="npm not found on PATH",
            fix="npm ships with Node.js — reinstall via nvm:\n"
                "  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash\n"
                "  source ~/.bashrc && nvm install --lts",
        )
    try:
        result = subprocess.run(
            ["npm", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        version = result.stdout.strip()
        return CheckResult(
            name="npm",
            passed=True,
            message=f"npm {version}",
            fix="",
        )
    except Exception as e:
        return CheckResult(
            name="npm",
            passed=False,
            message=f"npm found but could not run: {e}",
            fix="npm ships with Node.js — reinstall via nvm: https://github.com/nvm-sh/nvm",
        )


def check_claude_cli() -> CheckResult:
    """The claude CLI must be on PATH."""
    claude = shutil.which("claude")
    if not claude:
        return CheckResult(
            name="Claude CLI",
            passed=False,
            message="claude not found on PATH",
            fix="Install Claude Code CLI:\n"
                "  npm install -g @anthropic-ai/claude-code\n"
                "Then verify: claude --version",
        )
    try:
        result = subprocess.run(
            ["claude", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        version = (result.stdout + result.stderr).strip().splitlines()[0] if result.stdout or result.stderr else "unknown"
        return CheckResult(
            name="Claude CLI",
            passed=True,
            message=f"claude CLI found: {version}",
            fix="",
        )
    except Exception as e:
        return CheckResult(
            name="Claude CLI",
            passed=False,
            message=f"claude found but could not run: {e}",
            fix="Reinstall: npm install -g @anthropic-ai/claude-code",
        )


def check_claude_login() -> CheckResult:
    """Best-effort check for Claude CLI login status (non-fatal)."""
    # Look for credentials/auth in known locations
    auth_paths = [
        Path.home() / ".claude" / ".credentials.json",
        Path.home() / ".config" / "claude" / "auth.json",
        Path.home() / ".claude" / "auth.json",
    ]
    for ap in auth_paths:
        if ap.exists() and ap.stat().st_size > 10:
            return CheckResult(
                name="Claude login",
                passed=True,
                message=f"Auth file found: {ap}",
                fix="",
                fatal=False,
            )

    # Secondary: probe the CLI for an explicit "not authenticated" signal only.
    # Avoid matching "auth" or "login" anywhere — both appear in normal config output
    # and produce false positives (e.g. "auth_token: ...", "login_method: ...").
    try:
        result = subprocess.run(
            ["claude", "config", "list"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        output = (result.stdout + result.stderr).lower()
        if "not authenticated" in output or "not logged in" in output:
            return CheckResult(
                name="Claude login",
                passed=False,
                message="Claude CLI is not logged in",
                fix="Run: claude login",
                fatal=False,
            )
    except Exception:
        pass

    return CheckResult(
        name="Claude login",
        passed=False,
        message="Could not determine login status (auth file not found)",
        fix="Run: claude login\n  If already logged in, this is a false alarm.",
        fatal=False,
    )


def check_claude_payload() -> CheckResult:
    """The ~/.claude payload (skills/ and hooks/) must exist."""
    claude_dir = Path.home() / ".claude"
    missing = []

    for sub in ("skills", "hooks"):
        if not (claude_dir / sub).is_dir():
            missing.append(sub)

    if not claude_dir.is_dir():
        return CheckResult(
            name="~/.claude payload",
            passed=False,
            message="~/.claude directory does not exist",
            fix="Run setup.sh to install the payload:\n  bash setup.sh",
        )

    if missing:
        return CheckResult(
            name="~/.claude payload",
            passed=False,
            message=f"Missing in ~/.claude: {', '.join(f'{m}/' for m in missing)}",
            fix="Re-run setup.sh or manually copy the claude/ directory:\n"
                "  cp -r claude/skills ~/.claude/skills\n"
                "  cp -r claude/hooks ~/.claude/hooks",
        )

    return CheckResult(
        name="~/.claude payload",
        passed=True,
        message=f"~/.claude/skills/ and ~/.claude/hooks/ present",
        fix="",
    )


def check_settings_json() -> CheckResult:
    """settings.json must contain the hook registrations."""
    settings_path = Path.home() / ".claude" / "settings.json"
    if not settings_path.exists():
        return CheckResult(
            name="settings.json hooks",
            passed=False,
            message="~/.claude/settings.json not found",
            fix="Run setup.sh — it merges settings.fragment.json into settings.json:\n"
                "  bash setup.sh",
        )

    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return CheckResult(
            name="settings.json hooks",
            passed=False,
            message=f"Could not parse ~/.claude/settings.json: {e}",
            fix="Validate the file with: python3 -m json.tool ~/.claude/settings.json",
        )

    # Look for hook script filenames in the settings
    hooks_to_find = [
        "block-secrets.py",
        "index-enforcer.py",
        "file-naming-check.py",
        "pre-compact.sh",
    ]
    settings_text = json.dumps(data)
    missing_hooks = [h for h in hooks_to_find if h not in settings_text]

    if missing_hooks:
        return CheckResult(
            name="settings.json hooks",
            passed=False,
            message=f"Hooks not registered in settings.json: {', '.join(missing_hooks)}",
            fix="Run setup.sh to merge hook registrations:\n"
                "  bash setup.sh\n"
                "Or manually merge claude/settings.fragment.json into ~/.claude/settings.json",
        )

    return CheckResult(
        name="settings.json hooks",
        passed=True,
        message=f"All {len(hooks_to_find)} hooks registered in settings.json",
        fix="",
    )


def check_config_yaml(vault_root: Optional[Path]) -> CheckResult:
    """A config.yaml must exist at the vault root with a valid vault_root field."""
    if vault_root is None:
        return CheckResult(
            name="config.yaml",
            passed=False,
            message="Vault root could not be determined",
            fix="Pass --vault-root or set the VAULT_ROOT environment variable:\n"
                "  export VAULT_ROOT=~/MyVault",
        )

    config_path = vault_root / "config.yaml"
    if not config_path.exists():
        return CheckResult(
            name="config.yaml",
            passed=False,
            message=f"config.yaml not found at {vault_root}",
            fix="Run setup.sh — it creates config.yaml from config.example.yaml:\n"
                "  bash setup.sh\n"
                "Or copy manually: cp config.example.yaml <vault_root>/config.yaml\n"
                "Then edit vault_root to your vault path.",
        )

    # Try to parse it
    try:
        text = config_path.read_text(encoding="utf-8")
        # Check for vault_root key
        has_vr = any(
            line.strip().startswith("vault_root:") and len(line.split(":", 1)) > 1 and line.split(":", 1)[1].strip()
            for line in text.splitlines()
        )
        if not has_vr:
            return CheckResult(
                name="config.yaml",
                passed=False,
                message=f"config.yaml at {config_path} is missing vault_root",
                fix=f"Edit {config_path} and set:\n  vault_root: {vault_root}",
            )
    except OSError as e:
        return CheckResult(
            name="config.yaml",
            passed=False,
            message=f"Could not read {config_path}: {e}",
            fix="Check file permissions: ls -la {config_path}",
        )

    # Check that the vault_root in the config points to a real directory
    if not vault_root.is_dir():
        return CheckResult(
            name="config.yaml",
            passed=False,
            message=f"vault_root path {vault_root} does not exist",
            fix=f"Create it: mkdir -p {vault_root}\n"
                f"Or update vault_root in {config_path}",
        )

    return CheckResult(
        name="config.yaml",
        passed=True,
        message=f"config.yaml valid, vault_root = {vault_root}",
        fix="",
    )


def check_vault_skeleton(vault_root: Optional[Path]) -> CheckResult:
    """The vault must have the expected bucket directories."""
    if vault_root is None:
        return CheckResult(
            name="Vault skeleton",
            passed=False,
            message="Vault root not set — cannot check skeleton",
            fix="Set vault root: python3 doctor.py --vault-root ~/MyVault",
        )

    buckets = ["active", "inactive", "potential", "completed", "lost"]
    missing = [b for b in buckets if not (vault_root / b).is_dir()]

    if missing:
        return CheckResult(
            name="Vault skeleton",
            passed=False,
            message=f"Missing bucket directories: {', '.join(missing)}",
            fix="Run setup.sh to instantiate the vault skeleton, or create manually:\n"
                + "\n".join(f"  mkdir -p {vault_root}/{b}" for b in missing),
        )

    return CheckResult(
        name="Vault skeleton",
        passed=True,
        message=f"All bucket directories present under {vault_root}",
        fix="",
    )


def check_system_project(vault_root: Optional[Path]) -> CheckResult:
    """The system meta-project must exist under the vault root."""
    if vault_root is None:
        return CheckResult(
            name="system project",
            passed=False,
            message="Vault root not set — cannot check system project",
            fix="Set vault root: python3 doctor.py --vault-root ~/MyVault",
        )

    system_dir = vault_root / "system"
    if not system_dir.is_dir():
        return CheckResult(
            name="system project",
            passed=False,
            message=f"system/ not found at {vault_root}",
            fix="Run setup.sh — it copies vault-skeleton/system/ to your vault.\n"
                "Or copy manually: cp -r <repo>/vault-skeleton/system " + str(vault_root),
        )

    # Check for load-bearing files
    required = ["ABOUT.md", "CLAUDE.md", "HANDOFF.md"]
    missing = [f for f in required if not (system_dir / f).exists()]
    if missing:
        return CheckResult(
            name="system project",
            passed=False,
            message=f"system/ exists but missing: {', '.join(missing)}",
            fix="Re-copy from the repo: cp -r <repo>/vault-skeleton/system/* " + str(system_dir),
        )

    return CheckResult(
        name="system project",
        passed=True,
        message=f"system/ project present at {system_dir}",
        fix="",
    )


def check_config_settings(vault_root: Optional[Path]) -> CheckResult:
    """Light config.yaml validation: hook_strictness, help_mode, and shortcut target dirs."""
    if vault_root is None:
        return CheckResult(
            name="config.yaml settings",
            passed=True,
            message="Vault root not set — skipping config settings check",
            fix="",
            fatal=False,
        )

    config_path = vault_root / "config.yaml"
    if not config_path.exists():
        # check_config_yaml already reports this; skip silently
        return CheckResult(
            name="config.yaml settings",
            passed=True,
            message="config.yaml not found — skipped (see config.yaml check above)",
            fix="",
            fatal=False,
        )

    try:
        text = config_path.read_text(encoding="utf-8")
    except OSError as e:
        return CheckResult(
            name="config.yaml settings",
            passed=False,
            message=f"Could not read config.yaml: {e}",
            fix="Check file permissions.",
            fatal=False,
        )

    warnings: List[str] = []
    in_shortcuts = False

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(line) - len(line.lstrip())

        if indent == 0:
            in_shortcuts = stripped.startswith("shortcuts:")

            if stripped.startswith("hook_strictness:"):
                val = stripped.split(":", 1)[1].strip().strip("\"'")
                if " #" in val:
                    val = val[: val.index(" #")].strip()
                if val and val not in ("normal", "relaxed"):
                    warnings.append(
                        f"hook_strictness: '{val}' is not valid (expected normal|relaxed)"
                    )

            if stripped.startswith("help_mode:"):
                val = stripped.split(":", 1)[1].strip().strip("\"'")
                if " #" in val:
                    val = val[: val.index(" #")].strip()
                if val and val not in ("on", "off"):
                    warnings.append(
                        f"help_mode: '{val}' is not valid (expected on|off)"
                    )

        elif in_shortcuts and ":" in stripped and not stripped.startswith("-"):
            # shortcut entry:  name: "bucket/project-slug"
            key, _, val = stripped.partition(":")
            val = val.strip().strip("\"'")
            if " #" in val:
                val = val[: val.index(" #")].strip()
            if not val:
                continue  # home: "" — reserved empty shortcut is OK
            target = Path(val).expanduser() if val.startswith("/") else vault_root / val
            if not target.is_dir():
                warnings.append(
                    f"shortcut '{key.strip()}' → '{val}' does not exist"
                )

    if warnings:
        return CheckResult(
            name="config.yaml settings",
            passed=False,
            message=f"config.yaml has {len(warnings)} issue(s):\n"
                    + "\n".join(f"  - {w}" for w in warnings),
            fix=f"Edit {config_path} to fix the issues listed above.",
            fatal=False,
        )

    return CheckResult(
        name="config.yaml settings",
        passed=True,
        message="hook_strictness, help_mode, and shortcuts look valid",
        fix="",
        fatal=False,
    )


def check_vault_root_match(vault_root: Optional[Path]) -> CheckResult:
    """vault_root in config.yaml must be a real directory and match --vault-root."""
    if vault_root is None:
        return CheckResult(
            name="vault_root consistency",
            passed=False,
            message="Vault root could not be determined — skipping consistency check",
            fix="Pass --vault-root or set the VAULT_ROOT environment variable:\n"
                "  export VAULT_ROOT=~/MyVault",
        )

    config_path = vault_root / "config.yaml"
    if not config_path.exists():
        # check_config_yaml already reports this; skip redundant failure here
        return CheckResult(
            name="vault_root consistency",
            passed=False,
            message=f"config.yaml not found at {vault_root} — cannot check vault_root field",
            fix="Run setup.sh or see the config.yaml check above for details.",
        )

    try:
        text = config_path.read_text(encoding="utf-8")
    except OSError as e:
        return CheckResult(
            name="vault_root consistency",
            passed=False,
            message=f"Could not read {config_path}: {e}",
            fix="Check file permissions.",
        )

    # Extract vault_root value from config.yaml
    configured_vr: Optional[str] = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("vault_root:"):
            _, _, val = stripped.partition(":")
            val = val.strip().strip("\"'")
            # Strip inline YAML comments
            if " #" in val:
                val = val[: val.index(" #")].strip()
            if val:
                configured_vr = val
                break

    if not configured_vr:
        return CheckResult(
            name="vault_root consistency",
            passed=False,
            message=f"vault_root key not set in {config_path}",
            fix=f"Edit {config_path} and add:\n  vault_root: {vault_root}",
        )

    resolved = Path(configured_vr).expanduser().resolve()

    if not resolved.is_dir():
        return CheckResult(
            name="vault_root consistency",
            passed=False,
            message=f"vault_root in config.yaml ({configured_vr!r}) is not a real directory",
            fix=f"Create the directory:\n  mkdir -p {resolved}\n"
                f"Or update vault_root in {config_path}",
        )

    if resolved != vault_root:
        return CheckResult(
            name="vault_root consistency",
            passed=False,
            message=(
                f"vault_root mismatch: config.yaml says {resolved}, "
                f"but doctor is checking {vault_root}"
            ),
            fix=f"Update vault_root in {config_path}:\n"
                f"  vault_root: {vault_root}\n"
                f"Or re-run setup.sh targeting the correct vault:\n"
                f"  bash setup.sh --vault-root {vault_root}",
        )

    return CheckResult(
        name="vault_root consistency",
        passed=True,
        message=f"vault_root in config.yaml matches checked vault: {resolved}",
        fix="",
    )


def check_pointer_file(vault_root: Optional[Path]) -> CheckResult:
    """~/.claude/starter-kit/config.json must exist and point to this vault."""
    pointer = Path.home() / ".claude" / "starter-kit" / "config.json"

    if not pointer.exists():
        return CheckResult(
            name="pointer file",
            passed=False,
            message=f"Pointer file not found: {pointer}",
            fix="Re-run setup.sh — it writes this file automatically:\n"
                "  bash setup.sh\n"
                "Without it, hooks cannot locate the vault when editing files\n"
                "outside the vault directory tree.",
            fatal=False,
        )

    try:
        data = json.loads(pointer.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return CheckResult(
            name="pointer file",
            passed=False,
            message=f"Could not parse pointer file {pointer}: {e}",
            fix="Re-run setup.sh to recreate it:\n  bash setup.sh",
            fatal=False,
        )

    ptr_vr = data.get("vault_root")
    if not ptr_vr:
        return CheckResult(
            name="pointer file",
            passed=False,
            message=f"Pointer file {pointer} is missing the vault_root key",
            fix="Re-run setup.sh to recreate it:\n  bash setup.sh",
            fatal=False,
        )

    ptr_resolved = Path(ptr_vr).expanduser().resolve()

    if vault_root and ptr_resolved != vault_root:
        return CheckResult(
            name="pointer file",
            passed=False,
            message=(
                f"Pointer file vault_root ({ptr_resolved}) does not match "
                f"vault being checked ({vault_root})"
            ),
            fix="Re-run setup.sh pointing at the correct vault:\n"
                f"  bash setup.sh --vault-root {vault_root}",
            fatal=False,
        )

    return CheckResult(
        name="pointer file",
        passed=True,
        message=f"Pointer file OK: {pointer} → {ptr_resolved}",
        fix="",
        fatal=False,
    )


def check_os_commands(vault_root: Optional[Path]) -> CheckResult:
    """The configured os_open, os_copy, os_trash base commands must exist on PATH."""
    # Platform defaults (mirrors hook_config.py)
    _platform_defaults = {
        "darwin": {"os_open": "open", "os_copy": "pbcopy", "os_trash": "trash"},
    }
    _linux_defaults = {
        "os_open": "xdg-open",
        "os_copy": "xclip",
        "os_trash": "gio",
    }
    cmds: Dict[str, str] = dict(
        _platform_defaults.get(sys.platform, _linux_defaults)
    )

    # Override with values from config.yaml if present
    if vault_root:
        config_path = vault_root / "config.yaml"
        if config_path.exists():
            try:
                text = config_path.read_text(encoding="utf-8")
                for line in text.splitlines():
                    stripped = line.strip()
                    for key in ("os_open", "os_copy", "os_trash"):
                        if stripped.startswith(f"{key}:"):
                            _, _, val = stripped.partition(":")
                            val = val.strip().strip("\"'")
                            if " #" in val:
                                val = val[: val.index(" #")].strip()
                            if val:
                                # Store only the base command (first word)
                                cmds[key] = val.split()[0]
            except OSError:
                pass

    missing: List[tuple] = []
    for key, base_cmd in cmds.items():
        if not shutil.which(base_cmd):
            missing.append((key, base_cmd))

    if missing:
        fix_lines = []
        for key, base_cmd in missing:
            if base_cmd == "trash":
                fix_lines.append(
                    f"  {key} ({base_cmd}): brew install trash  # macOS only"
                )
            elif base_cmd in ("xclip",):
                fix_lines.append(
                    f"  {key} ({base_cmd}): sudo apt-get install xclip\n"
                    f"    Wayland alternative: set os_copy: wl-copy in config.yaml"
                )
            elif base_cmd == "pbcopy":
                fix_lines.append(
                    f"  {key} ({base_cmd}): built-in on macOS — check your PATH"
                )
            else:
                fix_lines.append(
                    f"  {key} ({base_cmd}): install via your package manager"
                )
        missing_summary = ", ".join(f"{k} ({b})" for k, b in missing)
        config_hint = (
            f"\nOr update the values in {vault_root / 'config.yaml'}"
            if vault_root
            else ""
        )
        return CheckResult(
            name="OS commands",
            passed=False,
            message=f"Base commands not found on PATH: {missing_summary}",
            fix="Install the missing command(s):\n"
                + "\n".join(fix_lines)
                + config_hint,
            fatal=False,
        )

    return CheckResult(
        name="OS commands",
        passed=True,
        message="All OS commands (os_open, os_copy, os_trash) found on PATH",
        fix="",
        fatal=False,
    )


def _find_vault_root_for_smoke_test() -> Optional[Path]:
    """Return vault root exactly as index-enforcer sees it (pointer file has highest priority)."""
    pointer = Path.home() / ".claude" / "starter-kit" / "config.json"
    if pointer.exists():
        try:
            data = json.loads(pointer.read_text(encoding="utf-8"))
            vr = data.get("vault_root")
            if vr:
                resolved = Path(vr).expanduser().resolve()
                if resolved.is_dir():
                    return resolved
        except Exception:
            pass
    for env_var in ("HOOK_VAULT_ROOT", "VAULT_ROOT"):
        env_val = os.environ.get(env_var)
        if env_val:
            resolved = Path(env_val).expanduser().resolve()
            if resolved.is_dir():
                return resolved
    return None


def _run_hook_subprocess(
    hooks_dir: Path,
    hook_name: str,
    payload: dict,
    extra_env: Optional[dict] = None,
) -> "tuple[Optional[subprocess.CompletedProcess], Optional[str]]":
    """Run a hook script with a JSON payload on stdin. Returns (result, error_str)."""
    hook = hooks_dir / hook_name
    cmd = (
        ["bash", str(hook)]
        if hook_name.endswith(".sh")
        else [sys.executable, str(hook)]
    )
    env = None
    if extra_env:
        env = dict(os.environ)
        env.update(extra_env)
    try:
        r = subprocess.run(
            cmd,
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )
        return r, None
    except Exception as e:
        return None, str(e)


def check_hooks_smoke_test() -> CheckResult:
    """Smoke-test each installed hook by piping mock payloads and checking exit codes/output.

    Proves hooks actually FIRE, not just that they are registered in settings.json.
    Non-fatal: failures are reported as warnings, not errors.
    """
    hooks_dir = Path.home() / ".claude" / "hooks"
    if not hooks_dir.is_dir():
        return CheckResult(
            name="hooks smoke test",
            passed=False,
            message="~/.claude/hooks/ directory not found",
            fix="Run setup.sh to install hooks:\n  bash setup.sh",
            fatal=False,
        )

    results: List[tuple] = []  # (hook_name, passed, detail)

    # block-secrets: exits 2 for a .env path, exits 0 for notes.md
    if (hooks_dir / "block-secrets.py").exists():
        r1, e1 = _run_hook_subprocess(
            hooks_dir, "block-secrets.py",
            {"tool_name": "Read", "tool_input": {"file_path": "/tmp/.env"}},
        )
        r2, e2 = _run_hook_subprocess(
            hooks_dir, "block-secrets.py",
            {"tool_name": "Read", "tool_input": {"file_path": "/tmp/notes.md"}},
        )
        if e1 or e2:
            results.append(("block-secrets", False, e1 or e2))
        elif r1.returncode == 2 and r2.returncode == 0:
            results.append(("block-secrets", True, "exits 2 for .env, exits 0 for notes.md"))
        else:
            results.append(("block-secrets", False,
                            f".env→{r1.returncode} (want 2), notes.md→{r2.returncode} (want 0)"))

    # file-naming-check: emits deny JSON for FINAL, exits 0 clean for v1
    if (hooks_dir / "file-naming-check.py").exists():
        r1, e1 = _run_hook_subprocess(
            hooks_dir, "file-naming-check.py",
            {"tool_name": "Write", "tool_input": {"file_path": "/tmp/report-FINAL.md"}},
        )
        r2, e2 = _run_hook_subprocess(
            hooks_dir, "file-naming-check.py",
            {"tool_name": "Write", "tool_input": {"file_path": "/tmp/report-v1.md"}},
        )
        if e1 or e2:
            results.append(("file-naming-check", False, e1 or e2))
        else:
            final_denied = '"permissionDecision": "deny"' in r1.stdout
            v1_allowed = (
                r2.returncode == 0
                and '"permissionDecision": "deny"' not in r2.stdout
            )
            if final_denied and v1_allowed:
                results.append(("file-naming-check", True, "denies FINAL name, allows v1"))
            else:
                results.append(("file-naming-check", False,
                                f"FINAL denied={final_denied}, v1 allowed={v1_allowed}"))

    # pre-compact.sh: exits 0
    if (hooks_dir / "pre-compact.sh").exists():
        r, e = _run_hook_subprocess(hooks_dir, "pre-compact.sh", {})
        if e:
            results.append(("pre-compact.sh", False, e))
        elif r.returncode == 0:
            results.append(("pre-compact.sh", True, "exits 0"))
        else:
            results.append(("pre-compact.sh", False,
                            f"exit={r.returncode}: {r.stderr[:100].strip()}"))

    # index-enforcer: exits 2 for a new unlisted .md in an indexed directory.
    # index-enforcer reads the vault root from hook_config (pointer file wins).
    # We create a temp subdir INSIDE the live vault so the path is recognized.
    if (hooks_dir / "index-enforcer.py").exists():
        vault = _find_vault_root_for_smoke_test()
        if vault is None:
            results.append(("index-enforcer", False,
                            "vault root not found — cannot create in-vault test fixture"))
        else:
            test_base = vault / "active" if (vault / "active").is_dir() else vault
            try:
                with tempfile.TemporaryDirectory(
                    prefix="doctor-smoke-", dir=test_base
                ) as tmpdir:
                    tmp_path = Path(tmpdir)
                    (tmp_path / "INDEX.md").write_text(
                        "---\nfolder: test\n---\n\n# test\n\n"
                        "<!-- AUTO-GENERATED-BELOW: do not edit manually;"
                        " run rebuild_indexes.py -->\n",
                        encoding="utf-8",
                    )
                    probe = tmp_path / "smoke-test-probe.md"
                    payload = {"tool_name": "Write", "tool_input": {"file_path": str(probe)}}
                    r, e = _run_hook_subprocess(hooks_dir, "index-enforcer.py", payload)
                # In 'normal' strictness the hook BLOCKS (exit 2); in the kit's
                # default 'relaxed' strictness it ADVISES (exit 0 with an
                # "[index-enforcer ADVISORY]" note). Both are correct behaviour;
                # only silence on an unlisted file would be a failure.
                out = ((r.stdout or "") + (r.stderr or "")) if r else ""
                if e:
                    results.append(("index-enforcer", False, e))
                elif r.returncode == 2:
                    results.append(("index-enforcer", True,
                                    "blocks unlisted .md in indexed dir (normal mode)"))
                elif r.returncode == 0 and "index-enforcer" in out.lower():
                    results.append(("index-enforcer", True,
                                    "advises on unlisted .md in indexed dir (relaxed mode)"))
                else:
                    results.append(("index-enforcer", False,
                                    f"neither blocked nor advised (exit {r.returncode}); "
                                    f"out: {out[:150].strip()!r}"))
            except Exception as ex:
                results.append(("index-enforcer", False, f"test fixture error: {ex}"))

    # helper-mode: with an ON state it emits the plain-English directive (POSITIVE
    # output, not just exit 0). Uses a temp state file so the result is deterministic.
    if (hooks_dir / "helper-mode.py").exists():
        import tempfile as _tf
        _sd = _tf.mkdtemp(prefix="doctor-helper-")
        _sf = os.path.join(_sd, "helper-mode.json")
        with open(_sf, "w") as _f:
            _f.write('{"on": true, "started": "%s", "window_days": 7}'
                     % __import__("datetime").date.today().isoformat())
        r, e = _run_hook_subprocess(hooks_dir, "helper-mode.py", {"prompt": "hi"},
                                    extra_env={"HELPER_MODE_STATE": _sf})
        if e:
            results.append(("helper-mode", False, e))
        elif r.returncode == 0 and "HELPER MODE" in r.stdout:
            results.append(("helper-mode", True, "ON state emits the HELPER MODE directive"))
        else:
            results.append(("helper-mode", False,
                            f"exit={r.returncode if r else '?'}, HELPER MODE in output="
                            f"{'yes' if r and 'HELPER MODE' in r.stdout else 'no'}"))

    # tool-module-brief: a Bash command touching a seed tool's surface injects that
    # tool's brief ONCE (POSITIVE output naming the tool). Fresh marker dir so it fires.
    if (hooks_dir / "tool-module-brief.py").exists():
        import tempfile as _tf
        _md = _tf.mkdtemp(prefix="doctor-tmb-")
        payload = {"session_id": "doctor", "tool_name": "Bash",
                   "tool_input": {"command": "open https://flexmls.com/search"},
                   "cwd": "/tmp"}
        r, e = _run_hook_subprocess(hooks_dir, "tool-module-brief.py", payload,
                                    extra_env={"TOOL_MODULE_MARKER_DIR": _md})
        if e:
            results.append(("tool-module-brief", False, e))
        elif r.returncode == 0 and "flexmls" in r.stdout.lower():
            results.append(("tool-module-brief", True, "injects the flexmls brief on a matching command"))
        else:
            results.append(("tool-module-brief", False,
                            f"exit={r.returncode if r else '?'}, named the tool="
                            f"{'yes' if r and 'flexmls' in r.stdout.lower() else 'no'}"))

    # command-guard: blocks a chmod 777 (a universal danger class), allows a plain ls.
    if (hooks_dir / "command-guard.py").exists():
        rb, eb = _run_hook_subprocess(hooks_dir, "command-guard.py",
                                      {"tool_input": {"command": "chmod 777 x"}, "cwd": "/tmp"})
        ra, ea = _run_hook_subprocess(hooks_dir, "command-guard.py",
                                      {"tool_input": {"command": "ls -la"}, "cwd": "/tmp"})
        if eb or ea:
            results.append(("command-guard", False, eb or ea))
        elif rb.returncode == 2 and ra.returncode == 0:
            results.append(("command-guard", True, "blocks chmod 777, allows ls"))
        else:
            results.append(("command-guard", False,
                            f"chmod777 exit={rb.returncode}, ls exit={ra.returncode}"))

    # secret-guard: fails OPEN (exit 0) on a commit when gitleaks is unavailable.
    if (hooks_dir / "secret-guard.py").exists():
        r, e = _run_hook_subprocess(hooks_dir, "secret-guard.py",
                                    {"tool_input": {"command": "git -C /tmp commit -m x"}, "cwd": "/tmp"},
                                    extra_env={"PATH": "/usr/bin:/bin"})
        if e:
            results.append(("secret-guard", False, e))
        elif r.returncode == 0:
            results.append(("secret-guard", True, "runs; fails open (exit 0) without gitleaks"))
        else:
            results.append(("secret-guard", False, f"exit={r.returncode} (expected 0)"))

    # auto-commit.sh: proves it commits staged work — but against a THROWAWAY vault,
    # never the user's real one. auto-commit.sh resolves the vault from
    # hook_config.vault_root(), which honours HOOK_VAULT_ROOT first (only when that
    # dir carries its own config.yaml), so we point it at a temp git repo with its
    # own config.yaml. Without this redirect the smoke test would `git add -A` and
    # COMMIT the user's real vault every time /doctor runs.
    if (hooks_dir / "auto-commit.sh").exists():
        _acd = tempfile.mkdtemp(prefix="doctor-autocommit-")
        try:
            _ac = Path(_acd)
            (_ac / "config.yaml").write_text(f"vault_root: {_acd}\n", encoding="utf-8")
            _giterr = None
            for _args in (
                ["git", "-C", _acd, "init", "-q"],
                ["git", "-C", _acd, "config", "user.name", "Doctor Smoke"],
                ["git", "-C", _acd, "config", "user.email", "doctor@localhost"],
            ):
                _gr = subprocess.run(_args, capture_output=True, text=True)
                if _gr.returncode != 0:
                    _giterr = _gr.stderr.strip()
                    break
            # a dirty file so there is something to commit
            (_ac / "probe.md").write_text("smoke\n", encoding="utf-8")
            if _giterr:
                results.append(("auto-commit.sh", False, f"temp git setup failed: {_giterr}"))
            else:
                r, e = _run_hook_subprocess(
                    hooks_dir, "auto-commit.sh", {},
                    extra_env={"HOOK_VAULT_ROOT": _acd, "VAULT_ROOT": _acd},
                )
                _log = subprocess.run(
                    ["git", "-C", _acd, "log", "--oneline"],
                    capture_output=True, text=True,
                )
                committed = bool(_log.stdout.strip())
                if e:
                    results.append(("auto-commit.sh", False, e))
                elif r.returncode == 0 and committed:
                    results.append(("auto-commit.sh", True,
                                    "commits a throwaway vault (real vault untouched)"))
                else:
                    results.append(("auto-commit.sh", False,
                                    f"exit={r.returncode}, made a commit={'yes' if committed else 'no'}"))
        finally:
            shutil.rmtree(_acd, ignore_errors=True)

    # Remaining hooks: accept a mock payload without crashing (exit 0).
    for hook_name, payload in [
        ("claude-md-hygiene.py", {"tool_name": "Write",
                                  "tool_input": {"file_path": "/tmp/CLAUDE.md", "content": "# x\n"}}),
        ("auto-stage.sh", {"tool_input": {"file_path": "/tmp/doctor-nonexistent.md"}}),
        ("writing-lint-posttooluse.py", {"tool_name": "Edit",
                                         "tool_input": {"file_path": "/tmp/x.md", "new_string": "hello"}}),
    ]:
        if (hooks_dir / hook_name).exists():
            r, e = _run_hook_subprocess(hooks_dir, hook_name, payload)
            short = hook_name.replace(".py", "").replace(".sh", "")
            if e:
                results.append((short, False, e))
            elif r.returncode in (0, 2):
                results.append((short, True, f"accepts a mock payload (exit {r.returncode})"))
            else:
                results.append((short, False, f"exit={r.returncode}: {r.stderr[:80].strip()}"))

    if not results:
        return CheckResult(
            name="hooks smoke test",
            passed=False,
            message="No testable hooks found in ~/.claude/hooks/",
            fix="Run setup.sh to install hooks:\n  bash setup.sh",
            fatal=False,
        )

    pass_count = sum(1 for _, p, _ in results if p)
    detail = "\n".join(
        f"    {'PASS' if p else 'FAIL'}  {n}: {d}"
        for n, p, d in results
    )
    summary = f"{pass_count}/{len(results)} hooks passed smoke test:\n{detail}"

    if any(not p for _, p, _ in results):
        return CheckResult(
            name="hooks smoke test",
            passed=False,
            message=summary,
            fix="Reinstall failing hooks:\n"
                "  bash setup.sh\n"
                "Or check ~/.claude/hooks/ for issues.",
            fatal=False,
        )

    return CheckResult(
        name="hooks smoke test",
        passed=True,
        message=summary,
        fix="",
        fatal=False,
    )


def check_mattpocock() -> CheckResult:
    """Non-fatal: check if the mattpocock-skills plugin is installed."""
    # Ask the CLI whether the plugin is installed.
    try:
        result = subprocess.run(
            ["claude", "plugins", "list"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        output = (result.stdout + result.stderr).lower()
        if "mattpocock" in output:
            return CheckResult(
                name="mattpocock-skills plugin",
                passed=True,
                message="mattpocock-skills plugin is installed",
                fix="",
                fatal=False,
            )
    except Exception:
        pass

    # Fall back to the plugin cache directory.
    cache = Path.home() / ".claude" / "plugins" / "cache" / "mattpocock"
    if cache.is_dir():
        return CheckResult(
            name="mattpocock-skills plugin",
            passed=True,
            message="mattpocock-skills plugin found in the plugin cache",
            fix="",
            fatal=False,
        )

    return CheckResult(
        name="mattpocock-skills plugin",
        passed=False,
        message="mattpocock-skills plugin not detected (non-fatal, optional)",
        fix="Install it once you are online:\n"
            "  claude plugins marketplace add mattpocock/skills\n"
            "  claude plugins install mattpocock-skills@mattpocock",
        fatal=False,
    )


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------

PASS = "✓"  # ✓
FAIL = "✗"  # ✗
WARN = "⚠"  # ⚠


def _render_text(results: List[CheckResult]) -> None:
    """Print a human-readable pass/fail report."""
    print()
    print("=" * 60)
    print("  Claude Starter Kit — Installation Doctor")
    print("=" * 60)

    fatal_failures = 0
    nonfatal_failures = 0

    for r in results:
        if r.passed:
            icon = PASS
            label = "PASS"
        elif r.fatal:
            icon = FAIL
            label = "FAIL"
            fatal_failures += 1
        else:
            icon = WARN
            label = "WARN"
            nonfatal_failures += 1

        print(f"\n  {icon} [{label}] {r.name}")
        print(f"       {r.message}")
        if not r.passed and r.fix:
            print("       Fix:")
            for line in r.fix.splitlines():
                print(f"         {line}")

    print()
    print("=" * 60)
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    print(
        f"  Results: {passed}/{total} passed"
        + (f", {fatal_failures} fatal failure(s)" if fatal_failures else "")
        + (f", {nonfatal_failures} warning(s)" if nonfatal_failures else "")
    )
    if fatal_failures == 0 and nonfatal_failures == 0:
        print("  All checks passed. You're ready to go!")
    elif fatal_failures == 0:
        print("  Core install looks good. Address warnings when convenient.")
    else:
        print("  Fix the FAIL items above, then re-run: python3 scripts/doctor.py")
    print("=" * 60)
    print()


def _render_json(results: List[CheckResult]) -> None:
    """Print JSON output for machine consumption."""
    out = {
        "summary": {
            "total": len(results),
            "passed": sum(1 for r in results if r.passed),
            "failed_fatal": sum(1 for r in results if not r.passed and r.fatal),
            "failed_nonfatal": sum(1 for r in results if not r.passed and not r.fatal),
        },
        "checks": [
            {
                "name": r.name,
                "passed": r.passed,
                "fatal": r.fatal,
                "message": r.message,
                "fix": r.fix,
            }
            for r in results
        ],
    }
    print(json.dumps(out, indent=2))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify the Claude starter kit installation.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exit code: 0 by default (this is a report, not a gate).\n"
            "With --strict: exits 1 if any fatal check failed."
        ),
    )
    parser.add_argument(
        "--vault-root",
        metavar="PATH",
        help="Vault root path (default: auto-detected from cwd or VAULT_ROOT env)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON instead of human-readable text",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help=(
            "Exit 1 if any fatal check failed. "
            "Non-fatal warnings (login, optional plugin, OS commands, pointer file) "
            "do not trigger a non-zero exit. "
            "Used by setup.sh to gate its success banner."
        ),
    )
    args = parser.parse_args()

    vault_root = _find_vault_root(args.vault_root)

    results: List[CheckResult] = [
        check_python(),
        check_pyyaml(),
        check_node(),
        check_npm(),
        check_claude_cli(),
        check_claude_login(),
        check_claude_payload(),
        check_settings_json(),
        check_config_yaml(vault_root),
        check_config_settings(vault_root),
        check_vault_root_match(vault_root),
        check_pointer_file(vault_root),
        check_vault_skeleton(vault_root),
        check_system_project(vault_root),
        check_os_commands(vault_root),
        check_mattpocock(),
        check_hooks_smoke_test(),
    ]

    if args.json:
        _render_json(results)
    else:
        _render_text(results)

    # With --strict: exit 1 if any fatal check failed.
    # Non-fatal warnings (fatal=False) never cause a non-zero exit.
    if args.strict:
        fatal_failures = sum(1 for r in results if not r.passed and r.fatal)
        if fatal_failures > 0:
            sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
