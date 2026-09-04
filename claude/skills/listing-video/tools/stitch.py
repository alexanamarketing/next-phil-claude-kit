#!/usr/bin/env python3
"""Join listing clips into one video with hard cuts (the house standard).

Usage:
    stitch.py --out <reel.mp4> <clip1> <clip2> [<clip3> ...]

Takes two or more clips and joins them end to end into one mp4, in the order
given. Every clip is scaled and padded to 1280x720 so mixed sizes line up, its
pixel aspect ratio is set to square, and its frame rate is normalized to 30 so
clips shot at different rates concatenate cleanly. The join is a plain hard cut
between clips, which matches the look of the reference walkthrough reels; there
is no cross-fade (the build box's ffmpeg has no xfade filter, and clean cuts are
the intended look, not a downgrade).

Exit codes:
    0  success (prints one line of JSON: ok, out, clips, seconds)
    2  a named input file is missing (plain sentence, no traceback)
    3  ffmpeg is not installed (plain sentence with the install hint)

ffmpeg is located with shutil.which, never a hardcoded path, so this runs on any
machine that has ffmpeg on its PATH.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys


def ffmpeg_input(path):
    """Absolute path for ffmpeg. ffmpeg reads the text before the first colon in
    a path as a protocol name, so a path containing a colon is prefixed with
    file: to force it to be read as a plain file."""
    ap = os.path.abspath(path)
    if ":" in ap:
        return "file:" + ap
    return ap


def main():
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--out", required=True, help="path to the finished mp4")
    parser.add_argument("clips", nargs="*", help="two or more clip files, in order")
    args = parser.parse_args()

    if len(args.clips) < 2:
        print("I need at least two clips to join into a video.")
        return 2

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("I could not find ffmpeg, the free tool that joins clips. "
              "On a Mac it installs with: brew install ffmpeg")
        return 3

    for c in args.clips:
        if not os.path.isfile(c):
            print("I could not find this clip: %s" % c)
            return 2

    n = len(args.clips)
    inputs = []
    for c in args.clips:
        inputs += ["-i", ffmpeg_input(c)]

    parts = []
    for i in range(n):
        parts.append(
            "[%d:v]scale=1280:720:force_original_aspect_ratio=decrease,"
            "pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v%d];" % (i, i)
        )
    fc = "".join(parts)
    fc += "".join("[v%d]" % i for i in range(n))
    fc += "concat=n=%d:v=1:a=0[out]" % n

    out = os.path.abspath(args.out)
    cmd = [ffmpeg, "-y", "-loglevel", "error", *inputs,
           "-filter_complex", fc, "-map", "[out]",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30",
           ffmpeg_input(out)]
    result = subprocess.run(cmd)
    if result.returncode != 0 or not os.path.isfile(out):
        print("Something went wrong joining the clips, and the video was not made.")
        return 2

    seconds = None
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        probe = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", ffmpeg_input(out)],
            capture_output=True, text=True)
        try:
            seconds = round(float(probe.stdout.strip()), 2)
        except ValueError:
            seconds = None

    print(json.dumps({"ok": True, "out": out, "clips": n, "seconds": seconds}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
