import subprocess

import ffprobe_shim


def test_shim_reads_duration_and_streams(tmp_path):
    p = str(tmp_path / "a.mp4")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=black:s=64x36:d=2", "-f", "lavfi", "-i",
                    "anullsrc=r=48000:cl=mono", "-t", "2", "-shortest", "-c:v", "libx264", "-c:a", "aac", p], check=True)
    dur, streams = ffprobe_shim.probe(p)
    assert abs(dur - 2.0) < 0.2
    assert sorted(s["codec_type"] for s in streams) == ["audio", "video"]
