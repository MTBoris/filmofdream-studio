"""Assemble video from a storyboard: stock clips + code graphics, cross-dissolves, narration, ducked music.

python scripts/render2.py STORYBOARD.json FRAMES_DIR STOCK_DIR NARRATION_WAV TIMELINE_JSON OUT_MP4 [--sheet SHEET.jpg]
"""
import json, os, subprocess, sys

FPS, XF = 30, 0.5
MUSIC = ["music/ghost-1.mp3", "music/ghost-2.mp3", "music/light-awash-kevin-macleod.mp3"]


def run(cmd):
    subprocess.run(cmd, check=True)


def caption_png(text, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import patheffects as pe
    fig = plt.figure(figsize=(19.2, 10.8), dpi=100)
    fig.patch.set_alpha(0)
    fig.text(0.05, 0.08, text, fontsize=46, color="white", weight="bold", ha="left", va="center",
             path_effects=[pe.withStroke(linewidth=7, foreground="#000000b0")])
    fig.savefig(path, dpi=100, transparent=True)
    plt.close(fig)


def build_shots(sb, tl):
    scenes, total = tl["scenes"], tl["duration"]
    shots = []
    for i, sc in enumerate(scenes):
        start = 0 if i == 0 else sc["start"]
        end = scenes[i + 1]["start"] if i + 1 < len(scenes) else total
        lst = sb[sc["scene"]]
        per = (end - start) / len(lst)
        for n, s in enumerate(lst):
            shots.append(dict(s, scene=sc["scene"], n=n, dur=per))
    return shots, total


def main(sb_path, frames_dir, stock_dir, narration, tl_path, out, sheet=None):
    sb = json.load(open(sb_path, encoding="utf-8"))
    tl = json.load(open(tl_path))
    shots, total = build_shots(sb, tl)
    os.makedirs("clips", exist_ok=True)
    clips = []
    for k, s in enumerate(shots):
        d = s["dur"] + (XF if k < len(shots) - 1 else 0)
        nf = int(round(d * FPS))
        clip = f"clips/{k:03d}.mp4"
        stock = os.path.join(stock_dir, f"{s['scene']}_{s['n']}.mp4")
        if "stock" in s and os.path.exists(stock):
            vf = ("scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=30,"
                  "eq=saturation=0.92:contrast=1.04,format=yuv420p")
            cmd = ["ffmpeg", "-loglevel", "error", "-y", "-stream_loop", "-1", "-i", stock]
            if s.get("caption"):
                cp = f"clips/cap{k:03d}.png"; caption_png(s["caption"], cp)
                cmd += ["-i", cp, "-filter_complex", f"[0:v]{vf}[b];[b][1:v]overlay=0:0:format=auto,format=yuv420p[v]", "-map", "[v]"]
            else:
                cmd += ["-vf", vf]
            cmd += ["-an", "-frames:v", str(nf), "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", clip]
        else:
            g = s.get("graphic") or f"{s['scene']}_00"
            png = os.path.join(frames_dir, g + ".png")
            z = f"min(1+0.06*on/{nf},1.06)" if k % 2 == 0 else f"max(1.06-0.06*on/{nf},1.0)"
            cmd = ["ffmpeg", "-loglevel", "error", "-y", "-loop", "1", "-i", png, "-vf",
                   f"scale=3840:2160,zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={nf}:s=1920x1080:fps={FPS},format=yuv420p",
                   "-frames:v", str(nf), "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", clip]
        run(cmd)
        clips.append((clip, d))
        print(f"shot {k:02d} {s['scene']}/{s['n']} {'stock' if 'stock' in s else 'graphic'} {s['dur']:.1f}s", flush=True)
    if sheet:
        from PIL import Image
        thumbs = []
        for c, _ in clips:
            p = c.replace(".mp4", ".jpg")
            run(["ffmpeg", "-loglevel", "error", "-y", "-ss", "1", "-i", c, "-frames:v", "1", "-vf", "scale=384:216", p])
            thumbs.append(p)
        cols = 6; rows = -(-len(thumbs) // cols)
        im = Image.new("RGB", (cols * 384, rows * 216))
        for i, p in enumerate(thumbs):
            im.paste(Image.open(p), ((i % cols) * 384, (i // cols) * 216))
        im.save(sheet, quality=82)
    inputs, fl, last, t = [], [], "0:v", clips[0][1]
    for c, _ in clips:
        inputs += ["-i", c]
    for n in range(1, len(clips)):
        off = t - XF
        fl.append(f"[{last}][{n}:v]xfade=transition=fade:duration={XF}:offset={off:.3f}[v{n}]")
        last, t = f"v{n}", off + clips[n][1]
    run(["ffmpeg", "-loglevel", "error", "-y", *inputs, "-filter_complex", ";".join(fl), "-map", f"[{last}]",
         "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "video_only.mp4"])
    mus_in = []
    for m in MUSIC:
        mus_in += ["-i", m]
    n = len(MUSIC)
    graph = ("".join(f"[{i + 1}:a]aresample=48000,aformat=channel_layouts=stereo[m{i}];" for i in range(n))
             + "".join(f"[m{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1[mus];"
             f"[mus]atrim=0:{total:.2f},afade=t=in:d=3,afade=t=out:st={total - 6:.2f}:d=6,volume=0.16[bed];"
             "[0:a]aresample=48000,aformat=channel_layouts=stereo,asplit=2[voice][sc];"
             "[bed][sc]sidechaincompress=threshold=0.02:ratio=6:attack=30:release=600[ducked];"
             "[voice][ducked]amix=inputs=2:normalize=0,alimiter=limit=0.95[a]")
    run(["ffmpeg", "-loglevel", "error", "-y", "-i", narration, *mus_in, "-filter_complex", graph, "-map", "[a]",
         "-c:a", "aac", "-b:a", "192k", "audio.m4a"])
    run(["ffmpeg", "-loglevel", "error", "-y", "-i", "video_only.mp4", "-i", "audio.m4a", "-c", "copy", "-shortest",
         "-movflags", "+faststart", out])
    print("done", out)


if __name__ == "__main__":
    a = sys.argv[1:]
    sheet = None
    if "--sheet" in a:
        i = a.index("--sheet"); sheet = a[i + 1]; a = a[:i] + a[i + 2:]
    main(*a, sheet=sheet)
