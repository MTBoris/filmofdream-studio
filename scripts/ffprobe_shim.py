#!/usr/bin/env python3
"""Minimal ffprobe replacement for CI when only an ffmpeg binary is available (pip package imageio-ffmpeg).

Supports what this repo calls: -show_entries format=duration | stream=codec_type:format=duration, -of json | default=nw=1:nk=1.
It parses `ffmpeg -i FILE` output (Duration line and Stream lines).
"""
import json
import re
import subprocess
import sys


def probe(path, ffmpeg="ffmpeg"):
    err = subprocess.run([ffmpeg, "-hide_banner", "-i", path], capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", err)
    if not m:
        sys.stderr.write(err)
        sys.exit(1)
    dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    streams = [{"codec_type": t.lower()} for t in re.findall(r"Stream #\d+:\d+.*?: (Video|Audio|Subtitle|Data):", err)]
    return dur, streams


def main(argv):
    path = argv[-1]
    entries = argv[argv.index("-show_entries") + 1] if "-show_entries" in argv else "format=duration"
    fmt = argv[argv.index("-of") + 1] if "-of" in argv else "default"
    dur, streams = probe(path)
    if fmt == "json":
        out = {"format": {"duration": f"{dur:.6f}"}}
        if "stream" in entries:
            out["streams"] = streams
        print(json.dumps(out))
    else:
        print(f"{dur:.6f}")


if __name__ == "__main__":
    main(sys.argv[1:])
