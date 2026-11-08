"""Assemble the video: scene frames (Ken Burns + cross-dissolves) + narration + ducked music.

python scripts/render.py FRAMES_DIR NARRATION_WAV TIMELINE_JSON OUT_MP4
"""
import json, os, subprocess, sys

FPS = 30
XF = 0.6  # cross-dissolve seconds
MUSIC = ["music/ghost-1.mp3", "music/ghost-2.mp3", "music/light-awash-kevin-macleod.mp3"]


def run(cmd):
    print(" ".join(cmd[:6]), "...", flush=True)
    subprocess.run(cmd, check=True)


def main(frames_dir, narration, timeline_path, out):
    frames = json.load(open(os.path.join(frames_dir, "frames.json")))
    tl = json.load(open(timeline_path))
    total = tl["duration"]
    scenes = tl["scenes"]
    shots = []  # (png, duration)
    for i, sc in enumerate(scenes):
        start = 0 if i == 0 else sc["start"]
        end = scenes[i + 1]["start"] if i + 1 < len(scenes) else total
        imgs = frames[sc["scene"]]
        per = (end - start) / len(imgs)
        for p in imgs:
            shots.append((p, per))
    os.makedirs("clips", exist_ok=True)
    clips = []
    for n, (png, dur) in enumerate(shots):
        d = dur + (XF if n < len(shots) - 1 else 0)
        nf = int(round(d * FPS))
        zin = n % 2 == 0
        z = "min(1+0.07*on/{nf},1.07)".format(nf=nf) if zin else "max(1.07-0.07*on/{nf},1.0)".format(nf=nf)
        clip = f"clips/{n:03d}.mp4"
        run(["ffmpeg", "-loglevel", "error", "-y", "-loop", "1", "-i", png, "-vf",
             f"scale=3840:2160,zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={nf}:s=1920x1080:fps={FPS},format=yuv420p",
             "-frames:v", str(nf), "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", clip])
        clips.append((clip, d))
    # chain cross-dissolves
    inputs, fl, last, t = [], [], "0:v", clips[0][1]
    for c, _ in clips:
        inputs += ["-i", c]
    for n in range(1, len(clips)):
        off = t - XF
        lab = f"v{n}"
        fl.append(f"[{last}][{n}:v]xfade=transition=fade:duration={XF}:offset={off:.3f}[{lab}]")
        last, t = lab, off + clips[n][1]
    run(["ffmpeg", "-loglevel", "error", "-y", *inputs, "-filter_complex", ";".join(fl), "-map", f"[{last}]",
         "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "video_only.mp4"])
    # music bed: concat tracks, trim, quiet, duck under voice
    mus_in = []
    for m in MUSIC:
        mus_in += ["-i", m]
    n = len(MUSIC)
    graph = (
        "".join(f"[{i + 1}:a]aresample=48000,aformat=channel_layouts=stereo[m{i}];" for i in range(n))
        + "".join(f"[m{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1[mus];"
        f"[mus]atrim=0:{total:.2f},afade=t=in:d=3,afade=t=out:st={total - 6:.2f}:d=6,volume=0.16[bed];"
        "[0:a]aresample=48000,aformat=channel_layouts=stereo,asplit=2[voice][sc];"
        "[bed][sc]sidechaincompress=threshold=0.02:ratio=6:attack=30:release=600[ducked];"
        "[voice][ducked]amix=inputs=2:normalize=0,alimiter=limit=0.95[a]"
    )
    run(["ffmpeg", "-loglevel", "error", "-y", "-i", narration, *mus_in, "-filter_complex", graph, "-map", "[a]",
         "-c:a", "aac", "-b:a", "192k", "audio.m4a"])
    run(["ffmpeg", "-loglevel", "error", "-y", "-i", "video_only.mp4", "-i", "audio.m4a", "-c:v", "copy", "-c:a", "copy",
         "-shortest", "-movflags", "+faststart", out])
    print("done", out)


if __name__ == "__main__":
    main(*sys.argv[1:5])
