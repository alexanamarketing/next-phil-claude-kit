#!/usr/bin/env python3
"""Check that a clip actually moved (the number one failure to catch).

Usage:
    motion_check.py <clip.mp4> [--threshold 3.0] [--json]

Pulls the first frame and the last frame of the clip, shrinks both to a small
fixed size (64x36) in 8-bit gray, and measures the average difference per pixel
between them. A real camera move over five seconds changes almost every pixel and
scores far above the threshold; a clip where the camera was held still and only
the light drifted scores near zero. So a low score means the clip did not move
and should be redone with a stronger camera move.

The default threshold of 3.0 (on a 0 to 255 scale) sits well above the drift of a
held shot and well below the score of any genuine dolly or tracking move, so it
separates the two cleanly.

Exit codes:
    0  the clip moved      (prints: moved, plus the score)
    1  the clip is static  (prints: did not move, plus the score)
    2  an error, including a missing or unreadable clip (plain sentence)
    3  ffmpeg is not installed (plain sentence with the install hint)
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

W, H = 64, 36
FRAME_BYTES = W * H


def ffmpeg_input(path):
    ap = os.path.abspath(path)
    if ":" in ap:
        return "file:" + ap
    return ap


def grab_frame(ffmpeg, clip, at_end):
    """Return the raw gray bytes of the first frame (at_end False) or the last
    frame (at_end True), scaled to WxH, or None on failure."""
    pre = ["-sseof", "-0.2"] if at_end else []
    cmd = [ffmpeg, "-v", "error", *pre, "-i", ffmpeg_input(clip),
           "-vf", "scale=%d:%d" % (W, H), "-frames:v", "1",
           "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0 or not result.stdout:
        return None
    return result.stdout


def main():
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("clip", help="the clip file to check")
    parser.add_argument("--threshold", type=float, default=3.0,
                        help="score below this counts as no motion (default 3.0)")
    parser.add_argument("--json", action="store_true", help="print JSON instead of a sentence")
    args = parser.parse_args()

    if not os.path.isfile(args.clip):
        print("I could not find this clip: %s" % args.clip)
        return 2

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("I could not find ffmpeg, the free tool that reads clips. "
              "On a Mac it installs with: brew install ffmpeg")
        return 3

    first = grab_frame(ffmpeg, args.clip, at_end=False)
    last = grab_frame(ffmpeg, args.clip, at_end=True)
    if not first or not last:
        print("I could not read the frames of this clip, so I cannot check it.")
        return 2

    length = min(len(first), len(last), FRAME_BYTES)
    if length == 0:
        print("I could not read the frames of this clip, so I cannot check it.")
        return 2

    total = 0
    for i in range(length):
        d = first[i] - last[i]
        total += d if d >= 0 else -d
    score = round(total / length, 3)
    moved = score >= args.threshold

    if args.json:
        print(json.dumps({"moved": moved, "score": score}))
    elif moved:
        print("This clip moved (score %.3f)." % score)
    else:
        print("This clip did not move (score %.3f). It happens, not your fault; "
              "a redo with a stronger camera move usually fixes it." % score)

    return 0 if moved else 1


if __name__ == "__main__":
    sys.exit(main())
