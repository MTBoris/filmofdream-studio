#!/usr/bin/env bash
# CI helper: install ffmpeg + ffprobe from Ubuntu apt with timeouts. On 2026-11-11 the runners' Azure apt mirror failed
# (DNS) and apt hung until the job timed out; if the first try fails, switch to the main Ubuntu archive and try again.
set -u
if command -v ffmpeg >/dev/null && command -v ffprobe >/dev/null; then ffmpeg -version | head -1; exit 0; fi
apt_try() {
  timeout 150 sudo apt-get -o Acquire::Retries=2 -o Acquire::http::Timeout=20 update -qq
  timeout 300 sudo apt-get -o Acquire::Retries=2 -o Acquire::http::Timeout=20 install -y -qq ffmpeg
}
if apt_try && command -v ffprobe >/dev/null; then ffmpeg -version | head -1; exit 0; fi
echo "apt mirror failed; switching to archive.ubuntu.com"
for f in /etc/apt/sources.list /etc/apt/sources.list.d/*.sources /etc/apt/sources.list.d/*.list; do
  [ -f "$f" ] && sudo sed -i -E 's#mirror\+file:/etc/apt/apt-mirrors.txt#http://archive.ubuntu.com/ubuntu/#; s#https?://azure\.archive\.ubuntu\.com/ubuntu/?#http://archive.ubuntu.com/ubuntu/#' "$f"
done
apt_try && ffmpeg -version | head -1
