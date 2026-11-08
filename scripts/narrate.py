"""Narrate an episode with the channel voice (Qwen3-TTS voice clone) and check every line with Whisper.

Usage:
  python scripts/narrate.py tts   EPISODE_DIR SHARD NSHARDS   -> out/lines/<idx>.wav + out/shard-<SHARD>.json
  python scripts/narrate.py merge EPISODE_DIR                 -> out/narration.wav (48 kHz) + out/timeline.json + out/qa.json
"""
import glob, json, os, re, subprocess, sys, time, difflib

VOICE = os.environ.get("VOICE", "voices/v4-storyteller.mp3")
REF_TEXT_FILE = "voices/ref_text.txt"
MAX_TRIES = 3
PASS_RATIO = 0.82


def parse(ep):
    """Return a list of items: {"type": "scene"|"line"|"para", ...}."""
    items = []
    for raw in open(os.path.join(ep, "narration.txt"), encoding="utf-8"):
        s = raw.rstrip("\n")
        if s.startswith("#"):
            continue
        if s.startswith("@scene"):
            items.append({"type": "scene", "name": s.split(None, 1)[1].strip()})
        elif not s.strip():
            items.append({"type": "para"})
        else:
            dramatic = s.rstrip().endswith("//")
            text = s.rstrip().rstrip("/").strip()
            items.append({"type": "line", "text": text, "dramatic": dramatic})
    lines = [i for i in items if i["type"] == "line"]
    for n, l in enumerate(lines):
        l["idx"] = n
    return items, lines


def norm_words(s):
    from num2words import num2words
    s = s.lower().replace("ё", "е")
    s = re.sub(r"\d+", lambda m: " " + num2words(int(m.group()), lang="ru") + " ", s)
    s = s.replace("google", "гугл")
    return re.sub(r"[^а-я ]", " ", s).split()


def similarity(src, hyp):
    a, b = norm_words(src), norm_words(hyp)
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    diffs = [(" ".join(a[i1:i2]), " ".join(b[j1:j2])) for t, i1, i2, j1, j2 in sm.get_opcodes() if t != "equal"]
    return sm.ratio(), diffs


def tts(ep, shard, nshards):
    import numpy as np, soundfile as sf, torch
    from qwen_tts import Qwen3TTSModel
    from faster_whisper import WhisperModel

    _, lines = parse(ep)
    per = -(-len(lines) // nshards)
    mine = lines[shard * per:(shard + 1) * per]
    os.makedirs("out/lines", exist_ok=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", VOICE, "-ac", "1", "-ar", "24000", "ref.wav"], check=True)
    model = Qwen3TTSModel.from_pretrained("Qwen/Qwen3-TTS-12Hz-1.7B-Base", device_map="cpu", dtype=torch.float32)
    ref_text = " ".join(l.strip() for l in open(REF_TEXT_FILE, encoding="utf-8") if l.strip())
    prompt = model.create_voice_clone_prompt(ref_audio="ref.wav", ref_text=ref_text)
    asr = WhisperModel("medium", device="cpu", compute_type="int8")

    report = []
    t0 = time.time()
    for l in mine:
        best = None
        for attempt in range(1, MAX_TRIES + 1):
            wavs, sr = model.generate_voice_clone(text=l["text"], language="Russian", voice_clone_prompt=prompt)
            audio = np.asarray(wavs[0], dtype=np.float32)
            a16 = np.interp(np.arange(0, len(audio), sr / 16000), np.arange(len(audio)), audio).astype(np.float32)
            segs, _ = asr.transcribe(a16, language="ru", beam_size=5)
            hyp = " ".join(s.text for s in segs).strip()
            ratio, diffs = similarity(l["text"], hyp)
            if best is None or ratio > best["ratio"]:
                best = {"audio": audio, "sr": sr, "ratio": ratio, "diffs": diffs, "hyp": hyp, "attempt": attempt}
            if ratio >= PASS_RATIO:
                break
        sf.write(f"out/lines/{l['idx']:04d}.wav", best["audio"], best["sr"])
        rec = {"idx": l["idx"], "text": l["text"], "ratio": round(best["ratio"], 3), "attempts": attempt,
               "heard": best["hyp"], "diffs": best["diffs"][:8]}
        report.append(rec)
        print(f"[{l['idx']:03d}] {rec['ratio']:.2f} x{attempt} {l['text'][:60]}", flush=True)
    json.dump({"shard": shard, "seconds": round(time.time() - t0), "lines": report},
              open(f"out/shard-{shard}.json", "w"), ensure_ascii=False, indent=1)


def merge(ep):
    import numpy as np, soundfile as sf
    items, lines = parse(ep)
    sr = sf.info("out/lines/0000.wav").samplerate
    gap = lambda ms: np.zeros(int(sr * ms / 1000), dtype=np.float32)
    out, t, timeline = [gap(600)], 0.6, []
    for i, it in enumerate(items):
        if it["type"] == "scene":
            timeline.append({"scene": it["name"], "start": round(t, 2)})
        elif it["type"] == "para":
            out.append(gap(350)); t += 0.35
        else:
            a, _ = sf.read(f"out/lines/{it['idx']:04d}.wav", dtype="float32")
            # trim leading/trailing near-silence produced by the model
            nz = np.where(np.abs(a) > 0.01)[0]
            if len(nz):
                a = a[max(0, nz[0] - int(0.05 * sr)): nz[-1] + int(0.12 * sr)]
            out.append(a); t += len(a) / sr
            ms = 1000 if it["dramatic"] else 320
            out.append(gap(ms)); t += ms / 1000
    out.append(gap(1500)); t += 1.5
    audio = np.concatenate(out)
    sf.write("out/narration_raw.wav", audio, sr)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", "out/narration_raw.wav", "-af",
                    "highpass=f=70,loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", "48000", "-ac", "1", "out/narration.wav"], check=True)
    json.dump({"duration": round(t, 2), "scenes": timeline}, open("out/timeline.json", "w"), ensure_ascii=False, indent=1)
    rep = []
    for f in sorted(glob.glob("out/shard-*.json")):
        rep += json.load(open(f))["lines"]
    rep.sort(key=lambda r: r["idx"])
    problems = [r for r in rep if r["ratio"] < PASS_RATIO]
    json.dump({"lines": len(rep), "problems": problems, "all": rep}, open("out/qa.json", "w"), ensure_ascii=False, indent=1)
    print(f"duration {t/60:.1f} min, lines {len(rep)}, problems {len(problems)}")
    for p in problems:
        print(" ", p["idx"], p["ratio"], p["diffs"])


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "tts":
        tts(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))
    else:
        merge(sys.argv[2])
