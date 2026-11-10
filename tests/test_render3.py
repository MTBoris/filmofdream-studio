import json
import os
import subprocess
import pytest
import render3
import sb2


@pytest.mark.skipif(subprocess.run(["which", "ffmpeg"], capture_output=True).returncode != 0, reason="ffmpeg not installed")
def test_v2_pipeline_smoke(tmp_path, monkeypatch):
    """storyboard v2 -> resolve -> render3: one stock clip, one labelled image, one external image."""
    from PIL import Image
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(render3.render2, "MUSIC", [os.path.join(root, "music", "ghost-1.mp3")])
    os.makedirs("stock"); os.makedirs("assets")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=30:duration=2",
                    "-pix_fmt", "yuv420p", "stock/s1.mp4"], check=True)
    for n, c in (("whaler", "brown"), ("nasa", "teal")):
        Image.new("RGB", (2000, 1200), c).save(f"assets/{n}.png")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=220:duration=9",
                    "-ar", "48000", "-ac", "1", "narr.wav"], check=True)
    sb = {"version": 2, "assets": {"whaler": {"label": "РЕКОНСТРУКЦИЯ"},
                                   "nasa": {"url": "https://eoimages.gsfc.nasa.gov/x.jpg", "credit": "NASA"}},
          "scenes": [{"scene": "a", "shots": [{"id": "s1", "type": "stock", "query": "x", "pick": "pix:1", "dur": 3,
                                               "overlay": {"template": "ocean-fact", "data": {"value": 1400, "unit": "м", "label": "глубина"},
                                                           "at": 0.2, "dur": 1.5}},
                                              {"id": "w", "type": "image", "asset_id": "whaler", "dur": "rest", "motion": "pan-right"}]},
                     {"scene": "b", "shots": [{"id": "n", "type": "external-image", "asset_id": "nasa", "dur": "rest", "motion": "pull-out"}]}]}
    tl = {"duration": 9.0, "scenes": [{"scene": "a", "start": 0}, {"scene": "b", "start": 6.0}], "words": []}
    shots, _ = sb2.resolve(sb, tl)
    json.dump({"shots": shots, "assets": sb["assets"]}, open("shots.json", "w"))
    json.dump(tl, open("tl.json", "w"))
    render3.main("shots.json", "stock", "assets", "narr.wav", "tl.json", "out.mp4", sheet="sheet.jpg")
    info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type:format=duration", "-of", "json",
                                      "out.mp4"], capture_output=True, text=True, check=True).stdout)
    assert sorted(s["codec_type"] for s in info["streams"]) == ["audio", "video"]
    assert float(info["format"]["duration"]) == pytest.approx(9.0, abs=1.0)
    assert os.path.exists("sheet.jpg")
    assert len(os.listdir("clips/ov000")) == 45  # 1.5 s of overlay frames at 30 fps
    # the overlay is really in the video: a frame at 1 s differs from the plain stock frame
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", "1.2", "-i", "clips/000.mp4", "-frames:v", "1", "a.png"], check=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", "2.8", "-i", "clips/000.mp4", "-frames:v", "1", "b.png"], check=True)
    from PIL import Image, ImageChops
    diff = ImageChops.difference(Image.open("a.png").convert("L").crop((90, 780, 700, 1015)),
                                 Image.open("b.png").convert("L").crop((90, 780, 700, 1015)))
    assert diff.getbbox() is not None
