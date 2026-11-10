"""QA of a finished build. Writes the frame sheets (a frame every 2 s of the FINAL video) and a short report.

    python scripts/qa_video.py VIDEO.mp4 SHOTS.json STOCK_DIR OUT_DIR [--timeline TIMELINE.json]

HARD RULE (fails the run, so nothing is uploaded): no stock clip is used twice in the episode.
  Checked three ways: the picks in the storyboard, the Pixabay ids that were actually downloaded (STOCK_DIR/stock.json),
  and the content of the downloaded files (the same video re-uploaded under another id is caught by its hash).
Information only (never fails): duration, number of shots, where the word times came from, frame count.
Output: OUT_DIR/sheet-01.jpg ... (30 frames each, 6x5, timestamp on every frame), OUT_DIR/qa-report.json, OUT_DIR/qa-report.md
"""
import glob
import hashlib
import json
import os
import subprocess
import sys

STEP = 2.0  # seconds between frames
COLS, ROWS = 6, 5


def duplicates(items):
    """items: [(key, owner)] -> {key: [owners]} for keys that occur more than once."""
    seen = {}
    for k, o in items:
        seen.setdefault(k, []).append(o)
    return {k: v for k, v in seen.items() if len(v) > 1}


def check_unique_stock(shots, stock_dir):
    """Returns a list of human-readable violations of the 'no repeated stock clip' rule."""
    problems = []
    stock = [s for s in shots if s["type"] == "stock"]
    for k, owners in duplicates([(s["pick"], s["id"]) for s in stock]).items():
        problems.append(f"pick pix:{k} is used by several shots: {', '.join(owners)}")
    sj = os.path.join(stock_dir, "stock.json")
    if os.path.exists(sj):
        src = json.load(open(sj, encoding="utf-8"))
        for k, owners in duplicates([(v["pixabay_id"], sid) for sid, v in src.items()]).items():
            problems.append(f"downloaded clip pix:{k} appears for several shots: {', '.join(owners)}")
    hashes = []
    for s in stock:
        p = os.path.join(stock_dir, s["id"] + ".mp4")
        if os.path.exists(p):
            h = hashlib.sha256()
            with open(p, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
            hashes.append((h.hexdigest(), s["id"]))
    for k, owners in duplicates(hashes).items():
        problems.append(f"identical video files for shots: {', '.join(owners)}")
    return problems


def video_duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", path],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def make_sheets(video, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    for old in glob.glob(os.path.join(out_dir, "sheet-*.jpg")):
        os.remove(old)
    vf = (f"fps=1/{STEP:g},scale=320:180,drawtext=text='%{{pts\\:hms}}':x=4:y=4:fontsize=16:fontcolor=yellow:box=1:boxcolor=black@0.6,"
          f"tile={COLS}x{ROWS}")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", video, "-vf", vf, "-q:v", "4", os.path.join(out_dir, "sheet-%02d.jpg")],
                   check=True)
    return sorted(glob.glob(os.path.join(out_dir, "sheet-*.jpg")))


def main(video, shots_path, stock_dir, out_dir, timeline=None):
    data = json.load(open(shots_path, encoding="utf-8"))
    shots = data["shots"]
    problems = check_unique_stock(shots, stock_dir)
    sheets = make_sheets(video, out_dir)
    dur = video_duration(video)
    info = {
        "duration_s": round(dur, 1),
        "duration": f"{int(dur // 60)}:{int(dur % 60):02d}",
        "shots": len(shots),
        "stock_shots": sum(1 for s in shots if s["type"] == "stock"),
        "image_shots": sum(1 for s in shots if s["type"] != "stock"),
        "overlays": sum(1 for s in shots if s.get("overlay")),
        "frames_every_s": STEP,
        "sheets": [os.path.basename(p) for p in sheets],
    }
    if timeline and os.path.exists(timeline):
        info["word_times"] = json.load(open(timeline)).get("words_source", "n/a")
    report = {"passed": not problems, "problems": problems, "info": info}
    json.dump(report, open(os.path.join(out_dir, "qa-report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    lines = ["# QA report", "", f"**{'PASSED' if not problems else 'FAILED'}** - rule: no stock clip repeats in the episode", ""]
    lines += [f"- ❌ {p}" for p in problems] or ["- ✅ every stock clip is unique (picks, downloaded ids, file hashes)"]
    lines += ["", "Info: " + ", ".join(f"{k}={v}" for k, v in info.items() if k != "sheets"),
              f"Frame sheets: {len(sheets)} (a frame every {STEP:g} s)"]
    open(os.path.join(out_dir, "qa-report.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0 if not problems else 1


if __name__ == "__main__":
    a = sys.argv[1:]
    tl = None
    if "--timeline" in a:
        i = a.index("--timeline")
        tl = a[i + 1]
        a = a[:i] + a[i + 2:]
    if len(a) != 4:
        sys.exit(__doc__)
    sys.exit(main(*a, timeline=tl))
