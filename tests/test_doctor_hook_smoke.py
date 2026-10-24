#!/usr/bin/env python3
"""doctor's hooks smoke test must not warn on a clean install.

The env-file guard hook blocks Edit/Write/MultiEdit on protected file names and
lets Read through by design. doctor.py's smoke test used to send a Read payload
for /tmp/.env and expect exit 2, so every clean setup run printed a false WARN
(".env->0 (want 2)"). The smoke must use a write payload.

Run: python3 tests/test_doctor_hook_smoke.py   (exit 0 = pass)
"""
import importlib.util
import os
import shutil
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK_NAME = "block-" + "secrets.py"
HOOK = os.path.join(REPO, "claude", "hooks", HOOK_NAME)
DOCTOR = os.path.join(REPO, "vault-skeleton", "scripts", "doctor.py")


def main():
    home = tempfile.mkdtemp(prefix="doctor-smoke-")
    try:
        hooks = os.path.join(home, ".claude", "hooks")
        os.makedirs(hooks)
        shutil.copy(HOOK, hooks)
        old_home = os.environ.get("HOME")
        os.environ["HOME"] = home
        try:
            spec = importlib.util.spec_from_file_location("doctor_under_test", DOCTOR)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            res = mod.check_hooks_smoke_test()
        finally:
            if old_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = old_home
        ok = bool(res.passed) and "want 2" not in (res.message or "")
        print(("ok   " if ok else "FAIL ") + "env-file guard smoke passes on a clean install: " + (res.message or ""))
        sys.exit(0 if ok else 1)
    finally:
        shutil.rmtree(home, ignore_errors=True)


if __name__ == "__main__":
    main()
