import json
import os
import subprocess
import pytest
import render2


def storyboard(*scene_lists):
    return {name: shots for name, shots in scene_lists}


def test_build_shots_splits_scene_time_and_covers_total():
    tl = {"duration": 30.0, "scenes": [{"scene": "a", "start": 0.6}, {"scene": "b", "start": 12.0}]}
    sb = storyboard(("a", [{"graphic": "x"}, {"graphic": "y"}]), ("b", [{"graphic": "z"}]))
    shots, total = render2.build_shots(sb, tl)
    assert total == 30.0
    assert [s["scene"] for s in shots] == ["a", "a", "b"]
    assert sum(s["dur"] for s in shots) == pytest.approx(30.0)
    assert shots[0]["dur"] == pytest.approx(6.0)  # first scene starts at 0, not at 0.6


def test_build_shots_missing_scene_is_an_error():
    tl = {"duration": 10.0, "scenes": [{"scene": "ghost", "start": 0}]}
    with pytest.raises(KeyError):
        render2.build_shots({"a": [{"graphic": "x"}]}, tl)


def test_fill_meta_chapters(tmp_path):
    meta = {"description": "Intro\n{CHAPTERS}\nEnd", "chapters": [["a", "Start"], ["b", "Second"]]}
    tl = {"duration": 100, "scenes": [{"scene": "a", "start": 0.6}, {"scene": "b", "start": 75.2}]}
    (tmp_path / "m.json").write_text(json.dumps(meta), encoding="utf-8")
    (tmp_path / "t.json").write_text(json.dumps(tl), encoding="utf-8")
    subprocess.run(["python3", "scripts/fill_meta.py", tmp_path / "m.json", tmp_path / "t.json", tmp_path / "o.json"],
                   check=True, capture_output=True)
    desc = json.load(open(tmp_path / "o.json", encoding="utf-8"))["description"]
    assert "00:00 Start" in desc and "01:15 Second" in desc and "{CHAPTERS}" not in desc


def test_pilot_storyboard_matches_narration_scenes():
    sb = json.load(open("episodes/001-sandy-island/storyboard.json", encoding="utf-8"))
    scenes = [l.split(None, 1)[1].strip() for l in open("episodes/001-sandy-island/narration.txt", encoding="utf-8")
              if l.startswith("@scene")]
    assert set(k for k in sb if not k.startswith("_")) == set(scenes)
    meta = json.load(open("episodes/001-sandy-island/meta.json", encoding="utf-8"))
    assert all(c[0] in scenes for c in meta["chapters"])


@pytest.mark.skipif(subprocess.run(["which", "ffmpeg"], capture_output=True).returncode != 0, reason="ffmpeg not installed")
def test_render_smoke(tmp_path, monkeypatch):
    """Tiny end-to-end render: 2 scenes of generated stills + fake narration -> mp4 with video and audio."""
    from PIL import Image
    monkeypatch.chdir(tmp_path)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    monkeypatch.setattr(render2, "MUSIC", [os.path.join(root, "music", "ghost-1.mp3")])
    os.makedirs("frames"); os.makedirs("stock")
    for name, color in (("g1", "navy"), ("g2", "darkred")):
        Image.new("RGB", (1920, 1080), color).save(f"frames/{name}.png")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=220:duration=8",
                    "-ar", "48000", "-ac", "1", "narr.wav"], check=True)
    json.dump({"s1": [{"graphic": "g1"}], "s2": [{"graphic": "g2"}]}, open("sb.json", "w"))
    json.dump({"duration": 8.0, "scenes": [{"scene": "s1", "start": 0.0}, {"scene": "s2", "start": 4.0}]}, open("tl.json", "w"))
    render2.main("sb.json", "frames", "stock", "narr.wav", "tl.json", "out.mp4", sheet="sheet.jpg")
    info = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type:format=duration", "-of", "json", "out.mp4"],
                          capture_output=True, text=True, check=True).stdout
    info = json.loads(info)
    assert sorted(s["codec_type"] for s in info["streams"]) == ["audio", "video"]
    assert float(info["format"]["duration"]) == pytest.approx(8.0, abs=1.0)
    assert os.path.exists("sheet.jpg")
