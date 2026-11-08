"""Transcribe each wav with faster-whisper and compare with the source text."""
import glob, json, re, difflib, subprocess
import numpy as np
from faster_whisper import WhisperModel
src = " ".join(l.strip() for l in open("bench/hook_chunks.txt", encoding="utf-8") if l.strip())
norm = lambda s: re.sub(r"[^а-яё ]", " ", s.lower().replace("ё", "е")).split()
m = WhisperModel("medium", device="cpu", compute_type="int8")
for w in sorted(glob.glob("out/*.wav")):
    pcm = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", w, "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], capture_output=True, check=True).stdout
    segs, _ = m.transcribe(np.frombuffer(pcm, dtype=np.float32), language="ru", beam_size=5)
    hyp = " ".join(s.text for s in segs)
    a, b = norm(src), norm(hyp)
    sm = difflib.SequenceMatcher(a=a, b=b)
    diffs = [(" ".join(a[i1:i2]), " ".join(b[j1:j2])) for t, i1, i2, j1, j2 in sm.get_opcodes() if t != "equal"]
    j = w[:-4] + ".json"
    try: r = json.load(open(j))
    except Exception: r = {"name": w}
    r.update({"word_match": round(sm.ratio(), 3), "diffs": diffs[:15], "transcript": hyp})
    json.dump(r, open(j, "w"), ensure_ascii=False, indent=1)
    print(r["name"], r["word_match"], diffs[:8])
