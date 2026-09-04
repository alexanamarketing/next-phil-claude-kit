#!/usr/bin/env python3
"""DONE 4 proof: stitch.py joins real clips with hard cuts, and its no-ffmpeg
path is a friendly sentence, never a stack trace.

Generates three tiny clips with ffmpeg (one at a different size, to prove the
scale/pad path), joins them, and asserts the output is one 1280x720 h264 stream
about 3 seconds long. Then proves the missing-ffmpeg path exits 3 with a plain
sentence and the missing-input path exits 2, both without a traceback.

No Higgsfield call anywhere; every fixture is generated locally with ffmpeg.

Run: python3 tests/test_stitch.py   (exit 0 = pass)
"""
import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STITCH = os.path.join(REPO, "claude", "skills", "listing-video", "tools", "stitch.py")


def make_clip(ffmpeg, path, size):
    subprocess.run(
        [ffmpeg, "-y", "-loglevel", "error", "-f", "lavfi",
         "-i", "testsrc=duration=1:size=%s:rate=10" % size,
         "-c:v", "libx264", "-pix_fmt", "yuv420p", path],
        check=True)


def probe(ffprobe, path, field):
    r = subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=%s" % field, "-of", "csv=p=0", path],
        capture_output=True, text=True)
    return r.stdout.strip()


def duration(ffprobe, path):
    r = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", path],
        capture_output=True, text=True)
    return float(r.stdout.strip())


def main():
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        print("SKIP: ffmpeg not installed")
        return 0

    tmp = tempfile.mkdtemp(prefix="stitch-test-")
    c1 = os.path.join(tmp, "c1.mp4")
    c2 = os.path.join(tmp, "c2.mp4")
    c3 = os.path.join(tmp, "c3.mp4")
    make_clip(ffmpeg, c1, "320x240")
    make_clip(ffmpeg, c2, "640x360")   # different size -> exercises scale/pad
    make_clip(ffmpeg, c3, "320x240")
    out = os.path.join(tmp, "reel.mp4")

    # --- 1. real join --------------------------------------------------------
    r = subprocess.run([sys.executable, STITCH, "--out", out, c1, c2, c3],
                       capture_output=True, text=True)
    assert r.returncode == 0, "stitch failed: rc=%s err=%s" % (r.returncode, r.stderr)
    assert os.path.isfile(out), "no output file produced"
    assert probe(ffprobe, out, "width") == "1280", "width not 1280: %r" % probe(ffprobe, out, "width")
    assert probe(ffprobe, out, "height") == "720", "height not 720"
    assert probe(ffprobe, out, "codec_name") == "h264", "codec not h264"
    d = duration(ffprobe, out)
    assert abs(d - 3.0) <= 0.3, "duration %.3f not ~3.0" % d
    assert '"ok": true' in r.stdout, "success JSON not printed: %r" % r.stdout
    print("PASS: three clips (mixed sizes) joined into one 1280x720 h264 clip ~3.0s")

    # --- 2. no ffmpeg -> friendly sentence, exit 3, no traceback -------------
    env = dict(os.environ)
    env["PATH"] = "/nonexistent"
    r = subprocess.run([sys.executable, STITCH, "--out", out, c1, c2],
                       capture_output=True, text=True, env=env)
    assert r.returncode == 3, "no-ffmpeg exit not 3: %s" % r.returncode
    assert "ffmpeg" in r.stdout, "no-ffmpeg message missing the word ffmpeg: %r" % r.stdout
    assert "Traceback" not in (r.stdout + r.stderr), "traceback leaked on no-ffmpeg"
    print("PASS: missing ffmpeg -> plain sentence, exit 3, no traceback")

    # --- 3. missing input -> exit 2, no traceback ---------------------------
    r = subprocess.run([sys.executable, STITCH, "--out", out, c1,
                        os.path.join(tmp, "gone.mp4")],
                       capture_output=True, text=True)
    assert r.returncode == 2, "missing-input exit not 2: %s" % r.returncode
    assert "Traceback" not in (r.stdout + r.stderr), "traceback leaked on missing input"
    print("PASS: missing input -> plain sentence, exit 2, no traceback")

    print("ALL STITCH ASSERTIONS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
