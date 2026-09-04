#!/usr/bin/env python3
"""DONE 5 proof: motion_check.py flags a moving clip as moved and a static clip
as no-motion, and its no-ffmpeg path is a friendly sentence.

Generates a MOVING fixture (testsrc, whose pattern and counter change every
frame) and a STATIC fixture (a flat gray frame held for a second), and asserts
the checker calls each correctly by exit code and JSON. Then proves the
missing-ffmpeg path exits 3 with a plain sentence and no traceback.

No Higgsfield call anywhere; every fixture is generated locally with ffmpeg.

Run: python3 tests/test_motion_check.py   (exit 0 = pass)
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOTION = os.path.join(REPO, "claude", "skills", "listing-video", "tools", "motion_check.py")


def make(ffmpeg, path, src):
    subprocess.run(
        [ffmpeg, "-y", "-loglevel", "error", "-f", "lavfi", "-i", src,
         "-c:v", "libx264", "-pix_fmt", "yuv420p", path],
        check=True)


def run(clip, extra=None, env=None):
    if extra is None:
        cmd = [sys.executable, MOTION, clip, "--json"]
    else:
        cmd = [sys.executable, MOTION, clip] + extra
    return subprocess.run(cmd, capture_output=True, text=True, env=env)


def main():
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("SKIP: ffmpeg not installed")
        return 0

    tmp = tempfile.mkdtemp(prefix="motion-test-")
    moving = os.path.join(tmp, "moving.mp4")
    static = os.path.join(tmp, "static.mp4")
    make(ffmpeg, moving, "testsrc=duration=1:size=320x240:rate=10")
    make(ffmpeg, static, "color=c=gray:size=320x240:duration=1:rate=10")

    # --- 1. moving clip -> exit 0, moved true --------------------------------
    r = run(moving)
    assert r.returncode == 0, "moving clip exit not 0: %s (%s)" % (r.returncode, r.stdout)
    assert json.loads(r.stdout)["moved"] is True, "moving clip not flagged moved: %r" % r.stdout
    print("PASS: moving clip -> moved true, exit 0")

    # --- 2. static clip -> exit 1, moved false -------------------------------
    r = run(static)
    assert r.returncode == 1, "static clip exit not 1: %s (%s)" % (r.returncode, r.stdout)
    assert json.loads(r.stdout)["moved"] is False, "static clip not flagged static: %r" % r.stdout
    print("PASS: static clip -> moved false, exit 1")

    # --- 3. plain (non-JSON) static run says 'did not move', no traceback ----
    r = run(static, extra=[])
    assert r.returncode == 1, "static plain exit not 1"
    assert "did not move" in r.stdout, "static plain message missing 'did not move': %r" % r.stdout
    assert "Traceback" not in (r.stdout + r.stderr), "traceback leaked"
    print("PASS: static plain run -> 'did not move' sentence, exit 1")

    # --- 4. no ffmpeg -> friendly sentence, exit 3, no traceback -------------
    env = dict(os.environ)
    env["PATH"] = "/nonexistent"
    r = run(moving, env=env)
    assert r.returncode == 3, "no-ffmpeg exit not 3: %s" % r.returncode
    assert "ffmpeg" in r.stdout, "no-ffmpeg message missing the word ffmpeg: %r" % r.stdout
    assert "Traceback" not in (r.stdout + r.stderr), "traceback leaked on no-ffmpeg"
    print("PASS: missing ffmpeg -> plain sentence, exit 3, no traceback")

    print("ALL MOTION-CHECK ASSERTIONS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
