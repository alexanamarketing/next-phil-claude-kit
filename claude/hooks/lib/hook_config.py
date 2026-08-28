#!/usr/bin/env python3
"""lib/hook_config.py — shared config reader for Claude Code hooks.

Locates the vault config.yaml and exposes the values hooks need.
Safe defaults ensure hooks never crash when config is absent.

Usage in a hook script:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent / "lib"))
    import hook_config

    # Optional: call init() with the file path being operated on
    # so the vault root can be found by walking up the directory tree.
    hook_config.init(file_path)

    vault = hook_config.vault_root()
    sacred = hook_config.sacred_files()
    skip = hook_config.skip_dirs()
    strict = hook_config.strictness()
"""
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Set

# ---------------------------------------------------------------------------
# Defaults (applied when config is absent or a key is missing)
# ---------------------------------------------------------------------------

_PLATFORM_DEFAULTS = {
    "darwin": {
        "os_open": "open",
        "os_copy": "pbcopy",
        "os_trash": "trash",
    },
}
_LINUX_DEFAULTS = {
    "os_open": "xdg-open",
    "os_copy": "xclip -selection clipboard",
    "os_trash": "gio trash",
}

_DEFAULTS: Dict[str, Any] = {
    "vault_root": str(Path.home() / "vault"),
    "sacred_files": [
        "INDEX.md", "CLAUDE.md", "HANDOFF.md",
        "notes.md", "todo.md", "README.md",
    ],
    "skip_dirs": [
        "_inbox", ".firecrawl", ".git",
        "node_modules", "__pycache__", ".cache",
    ],
    "hook_strictness": "normal",
    "help_mode": "on",
    **(_PLATFORM_DEFAULTS.get(sys.platform, _LINUX_DEFAULTS)),
}

# ---------------------------------------------------------------------------
# Minimal YAML fallback parser (stdlib only)
# ---------------------------------------------------------------------------

def _parse_minimal_yaml(text: str) -> Dict[str, Any]:
    """Parse a minimal subset of YAML sufficient for config.yaml.

    Handles:
    - Simple scalar: key: value
    - List under key:  (indented lines starting with '- ')
    - Nested dict under key: (indented lines with 'key: value')

    Does NOT handle: multi-document, anchors, block scalars, inline
    lists/dicts, or quoted multi-word values with colons.
    """
    result: Dict[str, Any] = {}
    current_key: Optional[str] = None
    current_collection: Any = None   # list or dict being built
    current_is_list: Optional[bool] = None

    def _flush() -> None:
        if current_key is not None and current_collection is not None:
            result[current_key] = current_collection

    for raw_line in text.splitlines():
        # Strip trailing whitespace, preserve leading
        line = raw_line.rstrip()
        stripped = line.lstrip()

        # Skip blank lines and comments
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(line) - len(stripped)

        if indent == 0:
            # Flush any in-progress collection
            _flush()
            current_key = None
            current_collection = None
            current_is_list = None

            if ":" not in stripped:
                continue

            key, sep, val = stripped.partition(":")
            key = key.strip()
            if not key:
                continue
            val = val.strip()
            # Strip inline YAML comments
            if " #" in val:
                val = val[: val.index(" #")].strip()
            # Strip surrounding single/double quotes from scalar values
            if len(val) >= 2 and (
                (val[0] == '"' and val[-1] == '"')
                or (val[0] == "'" and val[-1] == "'")
            ):
                val = val[1:-1]

            if val:
                result[key] = val
            else:
                current_key = key
        else:
            if current_key is None:
                continue

            if stripped.startswith("- "):
                # List item
                if current_is_list is False:
                    # Was building a dict; treat this as a new list
                    current_collection = []
                elif current_collection is None:
                    current_collection = []
                current_is_list = True
                item = stripped[2:].strip()
                # Strip inline comment
                if " #" in item:
                    item = item[: item.index(" #")].strip()
                current_collection.append(item)  # type: ignore[union-attr]
            elif ":" in stripped:
                # Dict entry
                if current_is_list is True:
                    # Was building a list; ignore malformed input
                    continue
                if current_collection is None:
                    current_collection = {}
                current_is_list = False
                k, _, v = stripped.partition(":")
                v = v.strip()
                if " #" in v:
                    v = v[: v.index(" #")].strip()
                current_collection[k.strip()] = v  # type: ignore[index]

    _flush()
    return result


# ---------------------------------------------------------------------------
# YAML loader (pyyaml preferred, fallback to minimal parser)
# ---------------------------------------------------------------------------

try:
    import yaml as _yaml  # type: ignore
    _HAS_PYYAML = True
except ImportError:
    _yaml = None  # type: ignore
    _HAS_PYYAML = False


def _load_yaml(path: Path) -> Dict[str, Any]:
    """Load a YAML file, using pyyaml if available, else the minimal parser."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, PermissionError):
        return {}
    if _HAS_PYYAML:
        try:
            data = _yaml.safe_load(text)
            return data if isinstance(data, dict) else {}
        except Exception:
            pass  # fall through to minimal parser
    return _parse_minimal_yaml(text)


# ---------------------------------------------------------------------------
# Pointer file reader (stdlib json only — never requires pyyaml)
# ---------------------------------------------------------------------------

def _read_pointer_file() -> Optional[Path]:
    """Read vault_root from the installer pointer file.

    The pointer file is written by setup.sh to:
      ~/.claude/starter-kit/config.json
    with the shape: {"vault_root": "<absolute path>"}

    Returns the resolved vault root Path if the file exists and the path
    is a real directory; returns None on any error or absence.
    """
    pointer = Path.home() / ".claude" / "starter-kit" / "config.json"
    if not pointer.exists():
        return None
    try:
        data = json.loads(pointer.read_text(encoding="utf-8"))
        vr = data.get("vault_root")
        if vr:
            resolved = Path(vr).expanduser().resolve()
            if resolved.is_dir():
                return resolved
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Config location
# ---------------------------------------------------------------------------

def _find_config(start: Optional[str] = None) -> Optional[Path]:
    """Find config.yaml using environment, file-walk, pointer file, or give up.

    Search order (highest to lowest precedence):
    1. HOOK_VAULT_ROOT / VAULT_ROOT env vars  (explicit override)
    2. Walk up from *start* path looking for config.yaml  (file's own vault)
    3. Walk up looking for an 'active/' directory that signals vault root
    4. ~/.claude/starter-kit/config.json pointer file  (installer default)
    5. Return None (caller uses defaults)

    Env first so an explicit override always wins.  File-walk second so that
    editing a file in vault-B is enforced by vault-B's config, not vault-A's
    config from the pointer file.  Pointer last as a sensible default.
    """
    # 1. Environment variables (explicit override — highest precedence)
    for env_var in ("HOOK_VAULT_ROOT", "VAULT_ROOT"):
        vault_env = os.environ.get(env_var)
        if vault_env:
            vr = Path(vault_env).expanduser().resolve()
            cfg = vr / "config.yaml"
            if cfg.exists():
                return cfg

    # 2. Walk up from the operated file path looking for config.yaml
    if start:
        here = Path(start).expanduser().resolve()
        if not here.is_dir():
            here = here.parent
        for p in [here, *here.parents]:
            cfg = p / "config.yaml"
            if cfg.exists():
                return cfg
            if p == p.parent:
                break

        # 3. Second pass: walk up looking for active/ marker
        here = Path(start).expanduser().resolve()
        if not here.is_dir():
            here = here.parent
        for p in [here, *here.parents]:
            if (p / "active").is_dir():
                cfg = p / "config.yaml"
                if cfg.exists():
                    return cfg
                # vault root found but no config yet — remember root, stop walk
                return None
            if p == p.parent:
                break

    # 4. Pointer file (installer default — lowest precedence)
    ptr = _read_pointer_file()
    if ptr:
        cfg = ptr / "config.yaml"
        if cfg.exists():
            return cfg

    return None


# ---------------------------------------------------------------------------
# Module-level state (lazy-loaded once per process)
# ---------------------------------------------------------------------------

_initialized: bool = False
_config: Dict[str, Any] = {}
_config_path: Optional[Path] = None
_vault_root_override: Optional[Path] = None


def _ensure_loaded(start: Optional[str] = None) -> None:
    global _initialized, _config, _config_path, _vault_root_override
    if _initialized:
        return
    _initialized = True

    cfg_path = _find_config(start)
    if cfg_path:
        _config_path = cfg_path
        _config = _load_yaml(cfg_path)
        # If vault_root not in config, infer from config.yaml location
        if "vault_root" not in _config:
            _config["vault_root"] = str(cfg_path.parent)

    # Fallback vault_root resolution (same priority as _find_config):
    # env vars > pointer file > built-in default.
    if "vault_root" not in _config:
        for env_var in ("HOOK_VAULT_ROOT", "VAULT_ROOT"):
            vault_env = os.environ.get(env_var)
            if vault_env:
                _config["vault_root"] = vault_env
                break

    if "vault_root" not in _config:
        ptr = _read_pointer_file()
        if ptr:
            _config["vault_root"] = str(ptr)


def init(start: Optional[str] = None) -> None:
    """Explicitly initialise config using *start* as the search seed.

    Call at the top of a hook's main() passing the file_path from tool_input.
    Subsequent calls are no-ops (config is loaded only once per process).
    """
    _ensure_loaded(start)


# ---------------------------------------------------------------------------
# Public accessors
# ---------------------------------------------------------------------------

def vault_root() -> Path:
    """Return the absolute vault root path."""
    _ensure_loaded()
    raw = _config.get("vault_root", _DEFAULTS["vault_root"])
    if not isinstance(raw, str) or not raw.strip():
        raw = _DEFAULTS["vault_root"]
    return Path(raw).expanduser().resolve()


def sacred_files() -> Set[str]:
    """Return the set of filename stems that should bypass index enforcement."""
    _ensure_loaded()
    val = _config.get("sacred_files", _DEFAULTS["sacred_files"])
    if isinstance(val, list):
        return set(val)
    if isinstance(val, str) and val.strip():
        return {val}
    return set(_DEFAULTS["sacred_files"])


def skip_dirs() -> Set[str]:
    """Return the set of directory names to skip during vault traversal."""
    _ensure_loaded()
    val = _config.get("skip_dirs", _DEFAULTS["skip_dirs"])
    if isinstance(val, list):
        return set(val)
    if isinstance(val, str) and val.strip():
        return {val}
    return set(_DEFAULTS["skip_dirs"])


def strictness() -> str:
    """Return hook strictness: 'normal' (block on violations) or 'relaxed' (warn only)."""
    _ensure_loaded()
    val = _config.get("hook_strictness", _DEFAULTS["hook_strictness"])
    if not isinstance(val, str) or not val.strip():
        return "normal"
    return "relaxed" if val.strip().lower() == "relaxed" else "normal"


def help_mode() -> bool:
    """Return True if help mode is enabled (the default).

    Help mode makes hook violation messages more instructional and
    encouraging instead of terse. Set help_mode: off in config.yaml
    to switch to brief procedural output.

    Returns False only when config.yaml has one of these values
    (case-insensitive):  off  false  0  no
    Returns True for any other value, and when the key is absent.
    """
    _ensure_loaded()
    val = _config.get("help_mode", _DEFAULTS["help_mode"])
    if val is None or (isinstance(val, str) and not val.strip()):
        return True  # default on when key is present but empty
    return str(val).strip().lower() not in ("off", "false", "0", "no")


def os_open() -> str:
    """Return the platform file-open command (e.g. 'xdg-open' or 'open')."""
    _ensure_loaded()
    return str(_config.get("os_open", _DEFAULTS.get("os_open", "xdg-open")))


def os_copy() -> str:
    """Return the clipboard-copy command (e.g. 'xclip -selection clipboard')."""
    _ensure_loaded()
    return str(_config.get("os_copy", _DEFAULTS.get("os_copy", "xclip -selection clipboard")))


def os_trash() -> str:
    """Return the safe-delete command (e.g. 'gio trash' or 'trash')."""
    _ensure_loaded()
    return str(_config.get("os_trash", _DEFAULTS.get("os_trash", "gio trash")))


def raw() -> Dict[str, Any]:
    """Return the full parsed config dict (for scripts that need arbitrary keys)."""
    _ensure_loaded()
    return dict(_config)
