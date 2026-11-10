import json
import os
import subprocess
import pytest
import qa_video


def shot(i, pick, typ="stock"):
    return {"id": i, "type": typ, "pick": pick}


def test_duplicate_pick_is_reported(tmp_path):
    p = qa_video.check_unique_stock([shot("a", 1), shot("b", 2), shot("c", 1)], str(tmp_path))
    assert len(p) == 1 and "pix:1" in p[0] and "a, c" in p[0]


def test_unique_picks_pass_and_images_are_ignored(tmp_path):
    shots = [shot("a", 1), shot("b", 2), {"id": "img", "type": "image", "asset_id": "x"}, {"id": "img2", "type": "image", "asset_id": "x"}]
    assert qa_video.check_unique_stock(shots, str(tmp_path)) == []


def test_downloaded_duplicate_ids_and_identical_files(tmp_path):
    (tmp_path / "stock.json").write_text(json.dumps({"a": {"pixabay_id": 5}, "b": {"pixabay_id": 5}, "c": {"pixabay_id": 6}}))
    (tmp_path / "a.mp4").write_bytes(b"same-bytes")
    (tmp_path / "b.mp4").write_bytes(b"other")
    (tmp_path / "c.mp4").write_bytes(b"same-bytes")  # same video under a different Pixabay id
    p = qa_video.check_unique_stock([shot("a", 5), shot("b", 7), shot("c", 6)], str(tmp_path))
    assert any("downloaded clip pix:5" in x for x in p)
    assert any("identical video files" in x and "a, c" in x for x in p)


@pytest.mark.skipif(subprocess.run(["which", "ffmpeg"], capture_output=True).returncode != 0, reason="ffmpeg not installed")
def test_sheets_every_two_seconds_and_exit_codes(tmp_path):
    video = str(tmp_path / "v.mp4")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=10:duration=70",
                    "-pix_fmt", "yuv420p", video], check=True)
    stock = tmp_path / "stock"
    stock.mkdir()
    ok = tmp_path / "ok.json"
    ok.write_text(json.dumps({"shots": [shot("a", 1), shot("b", 2)]}))
    out = str(tmp_path / "qa")
    assert qa_video.main(video, str(ok), str(stock), out) == 0
    rep = json.load(open(os.path.join(out, "qa-report.json")))
    assert rep["passed"] and rep["info"]["duration"] == "1:10"
    assert len(rep["info"]["sheets"]) == 2           # 70 s / 2 s = 35 frames -> 30 + 5
    assert os.path.exists(os.path.join(out, "sheet-02.jpg")) and os.path.exists(os.path.join(out, "qa-report.md"))
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"shots": [shot("a", 1), shot("b", 1)]}))
    assert qa_video.main(video, str(bad), str(stock), out) == 1
    assert not json.load(open(os.path.join(out, "qa-report.json")))["passed"]
