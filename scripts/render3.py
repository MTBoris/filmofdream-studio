"""Render a resolved storyboard v2 (scripts/sb2.py resolve -> shots.json) into the final video.

    python scripts/render3.py SHOTS.json STOCK_DIR ASSETS_DIR NARRATION_WAV TIMELINE_JSON OUT_MP4 [--sheet SHEET.jpg]

stock           -> STOCK_DIR/<shot id>.mp4, looped/cropped to 1920x1080
image/external  -> ASSETS_DIR/<asset_id>.png, Ken Burns (push-in / pull-out / pan-left / pan-right / none);
                   a label from the asset (e.g. РЕКОНСТРУКЦИЯ) is stamped in the top-left safe corner
overlay         -> rendered by scripts/overlays.py (templates, PR 4); until a template exists it is skipped with a warning
Timing comes from the resolved shots (absolute seconds), so it follows the narration.
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render2  # noqa: E402

FPS, XF = render2.FPS, render2.XF
SAFE_X, SAFE_Y = 90, 65  # design margins, px


def run(cmd):
    subprocess.run(cmd, check=True)


def label_png(text, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(19.2, 10.8), dpi=100)
    fig.patch.set_alpha(0)
    fig.text(SAFE_X / 1920, 1 - SAFE_Y / 1080, text, fontsize=22, color="white", weight="bold", ha="left", va="top",
             bbox=dict(boxstyle="round,pad=0.5", fc="#000000", ec="none", alpha=0.55))
    fig.savefig(path, dpi=100, transparent=True)
    plt.close(fig)


def kenburns_filter(motion, nf):
    base = "scale=3840:2160:force_original_aspect_ratio=increase,crop=3840:2160,"
    if motion == "pull-out":
        z, x = f"max(1.08-0.08*on/{nf},1.0)", "iw/2-(iw/zoom/2)"
    elif motion == "pan-right":
        z, x = "1.08", f"(iw-iw/zoom)*on/{nf}"
    elif motion == "pan-left":
        z, x = "1.08", f"(iw-iw/zoom)*(1-on/{nf})"
    elif motion == "none":
        z, x = "1.0", "iw/2-(iw/zoom/2)"
    else:  # push-in
        z, x = f"min(1+0.08*on/{nf},1.08)", "iw/2-(iw/zoom/2)"
    return base + f"zoompan=z='{z}':x='{x}':y='ih/2-(ih/zoom/2)':d={nf}:s=1920x1080:fps={FPS},format=yuv420p"


def shot_clip(s, k, nshots, stock_dir, assets_dir, assets, clips_dir):
    d = s["dur"] + (XF if k < nshots - 1 else 0)
    nf = int(round(d * FPS))
    clip = os.path.join(clips_dir, f"{k:03d}.mp4")
    enc = ["-an", "-frames:v", str(nf), "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", clip]
    if s["type"] == "stock":
        src = os.path.join(stock_dir, s["id"] + ".mp4")
        if not os.path.exists(src):
            raise SystemExit(f"missing stock clip for shot {s['id']}: {src}")
        vf = ("scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=30,"
              "eq=saturation=0.92:contrast=1.04,format=yuv420p")
        run(["ffmpeg", "-loglevel", "error", "-y", "-stream_loop", "-1", "-i", src, "-vf", vf, *enc])
        return clip, d
    png = os.path.join(assets_dir, s["asset_id"] + ".png")
    if not os.path.exists(png):
        raise SystemExit(f"missing image for shot {s['id']}: {png}")
    label = s.get("label") or (assets.get(s["asset_id"]) or {}).get("label")
    if label:
        lp = os.path.join(clips_dir, f"label{k:03d}.png")
        label_png(label, lp)
        fc = f"[0:v]{kenburns_filter(s.get('motion', 'push-in'), nf)}[b];[b][1:v]overlay=0:0:format=auto,format=yuv420p[v]"
        run(["ffmpeg", "-loglevel", "error", "-y", "-loop", "1", "-i", png, "-i", lp, "-filter_complex", fc, "-map", "[v]", *enc])
    else:
        run(["ffmpeg", "-loglevel", "error", "-y", "-loop", "1", "-i", png, "-vf", kenburns_filter(s.get("motion", "push-in"), nf), *enc])
    return clip, d


def main(shots_path, stock_dir, assets_dir, narration, tl_path, out, sheet=None):
    data = json.load(open(shots_path, encoding="utf-8"))
    shots, assets = data["shots"], data.get("assets") or {}
    total = json.load(open(tl_path))["duration"]
    clips_dir = "clips"
    os.makedirs(clips_dir, exist_ok=True)
    clips = []
    for k, s in enumerate(shots):
        clips.append(shot_clip(s, k, len(shots), stock_dir, assets_dir, assets, clips_dir))
        if s.get("overlay"):
            print(f"WARN: shot {s['id']}: overlay template {s['overlay']['template']!r} is not rendered yet", flush=True)
        print(f"shot {k:02d} {s['id']} {s['type']} {s['dur']:.1f}s", flush=True)
    if sheet:
        from PIL import Image
        thumbs = []
        for c, _ in clips:
            p = c.replace(".mp4", ".jpg")
            run(["ffmpeg", "-loglevel", "error", "-y", "-ss", "1", "-i", c, "-frames:v", "1", "-vf", "scale=384:216", p])
            thumbs.append(p)
        cols = 6
        rows = -(-len(thumbs) // cols)
        im = Image.new("RGB", (cols * 384, rows * 216))
        for i, p in enumerate(thumbs):
            im.paste(Image.open(p), ((i % cols) * 384, (i // cols) * 216))
        im.save(sheet, quality=82)
    render2.assemble(clips, narration, total, out)


if __name__ == "__main__":
    a = sys.argv[1:]
    sheet = None
    if "--sheet" in a:
        i = a.index("--sheet")
        sheet = a[i + 1]
        a = a[:i] + a[i + 2:]
    main(*a, sheet=sheet)
