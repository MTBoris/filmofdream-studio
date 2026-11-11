#!/usr/bin/env bash
# CI helper: install ffmpeg + ffprobe. Ubuntu apt with short timeouts first; on 2026-11-11 the Ubuntu archive was
# unreachable from the runners and apt hung until the job timed out. Fallback: the ffmpeg binary from the PyPI package
# imageio-ffmpeg plus scripts/ffprobe_shim.py (enough for this repo's ffprobe calls).
set -u
if command -v ffmpeg >/dev/null && command -v ffprobe >/dev/null; then ffmpeg -version | head -1; exit 0; fi
timeout 90 sudo apt-get -o Acquire::Retries=1 -o Acquire::http::Timeout=15 update -qq \
  && timeout 240 sudo apt-get -o Acquire::http::Timeout=15 install -y -qq ffmpeg \
  && command -v ffprobe >/dev/null && { ffmpeg -version | head -1; exit 0; }
echo "apt failed; using ffmpeg from the PyPI package imageio-ffmpeg + ffprobe shim"
pip install --quiet imageio-ffmpeg
exe=$(python -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())")
sudo ln -sf "$exe" /usr/local/bin/ffmpeg
sudo install -m 755 "$(dirname "$0")/ffprobe_shim.py" /usr/local/bin/ffprobe
ffmpeg -version | head -1
