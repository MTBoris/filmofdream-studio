"""Narrate an episode with Azure Neural TTS (channel voice: ru-RU-DmitryNeural).

python scripts/narrate_azure.py EPISODE_DIR   -> out/narration.wav (48 kHz) + out/timeline.json + out/ssml_log.txt

Stress control: in narration.txt put "+" before the stressed vowel ("+острова"), or add the word to
voices/pronunciations.json. Such words are sent to Azure as IPA <phoneme> (the only method that worked in tests).
"""
import json, os, re, subprocess, sys, time, urllib.request, io, wave
from xml.sax.saxutils import escape


def parse(ep):
    """Read EPISODE/narration.txt -> (items, lines). Items: {"type": "scene"|"line"|"para", ...}.
    "@scene NAME" starts a scene, a trailing "//" marks a dramatic pause, "#" lines are comments."""
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

VOICE = os.environ.get("VOICE", "ru-RU-DmitryNeural")
RATE = os.environ.get("RATE", "-5%")
LEX = {k: v for k, v in json.load(open("voices/pronunciations.json", encoding="utf-8")).items() if not k.startswith("_")}

VOW = "аоуыэяёюие"
SOFTENING = "яёюие"
CONS = {"б": "b", "в": "v", "г": "ɡ", "д": "d", "ж": "ʐ", "з": "z", "й": "j", "к": "k", "л": "l", "м": "m", "н": "n",
        "п": "p", "р": "r", "с": "s", "т": "t", "ф": "f", "х": "x", "ц": "ts", "ч": "tɕ", "ш": "ʂ", "щ": "ɕː"}
ALWAYS_HARD = set("жшц")
ALWAYS_SOFT = set("чщй")
STRESSED = {"а": "a", "о": "o", "у": "u", "ы": "ɨ", "э": "e", "е": "e", "ё": "o", "и": "i", "ю": "u", "я": "a"}
UNSTRESSED = {"а": "ə", "о": "ə", "у": "u", "ы": "ɨ", "э": "ɪ", "е": "ɪ", "ё": "ɪ", "и": "ɪ", "ю": "u", "я": "ɪ"}


def ru2ipa(marked):
    """'+атласах' -> 'ˈatləsəx'. Approximate Russian G2P, good enough for Azure to place the stress."""
    w = marked.lower()
    stress_pos = w.index("+")
    w = w.replace("+", "")
    out, n = [], len(w)
    first_vowel_seen = False
    for i, ch in enumerate(w):
        nxt = w[i + 1] if i + 1 < n else ""
        if ch in CONS:
            c = CONS[ch]
            if ch not in ALWAYS_HARD and ch not in ALWAYS_SOFT and (nxt and (nxt in SOFTENING or nxt == "ь")):
                c += "ʲ"
            out.append(("C", c, i))
        elif ch in VOW:
            stressed = i == stress_pos
            iot = ch in "яёюе" and (i == 0 or w[i - 1] in VOW or w[i - 1] in "ьъ")
            if iot:
                out.append(("C", "j", i))
            if stressed:
                v = STRESSED[ch]
            elif not first_vowel_seen and i < stress_pos and ch in "ао":
                v = "ɐ"
            else:
                v = UNSTRESSED[ch]
            out.append(("V", v, i, stressed))
            first_vowel_seen = True
    # put the stress mark before the consonant cluster's last consonant preceding the stressed vowel
    res, k = [], None
    for j, t in enumerate(out):
        if t[0] == "V" and t[3]:
            k = j
    for j, t in enumerate(out):
        if k is not None and ((j == k - 1 and out[j][0] == "C") or (j == k and (k == 0 or out[k - 1][0] == "V"))):
            res.append("ˈ")
        res.append(t[1])
    return "".join(res)


WORD = re.compile(r"\+?[А-Яа-яЁё]+(?:\+[А-Яа-яЁё]+)?|[^А-Яа-яЁё+]+|\+")


def to_ssml(text):
    parts = []
    for m in re.finditer(r"[+А-Яа-яЁё]+|[^+А-Яа-яЁё]+", text):
        tok = m.group()
        bare = tok.replace("+", "")
        marked = tok if "+" in tok else LEX.get(bare.lower())
        if marked and "+" in marked and re.search(r"[А-Яа-яЁё]", bare):
            parts.append(f'<phoneme alphabet="ipa" ph="{ru2ipa(marked)}">{escape(bare)}</phoneme>')
        else:
            parts.append(escape(tok.replace("+", "")))
    return "".join(parts)


def build_ssml(inner_ssml):
    return (f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="ru-RU">'
            f'<voice name="{VOICE}"><prosody rate="{RATE}">{inner_ssml}</prosody></voice></speak>')


def synth(inner_ssml):
    ssml = build_ssml(inner_ssml)
    req = urllib.request.Request(
        f"https://{os.environ['AZURE_SPEECH_REGION']}.tts.speech.microsoft.com/cognitiveservices/v1",
        data=ssml.encode("utf-8"), method="POST",
        headers={"Ocp-Apim-Subscription-Key": os.environ["AZURE_SPEECH_KEY"], "Content-Type": "application/ssml+xml",
                 "X-Microsoft-OutputFormat": "riff-48khz-16bit-mono-pcm", "User-Agent": "filmofdream-studio"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except Exception:
            if attempt == 3:
                raise
            import time; time.sleep(3 * (attempt + 1))


def synth_words(inner_ssml):
    """-> (wav_bytes, words, source). words = [(text, offset_s, duration_s)] from Azure word-boundary events
    (Speech SDK). Without the SDK, or if it fails, the plain REST call is used and words is None ("estimated")."""
    try:
        import azure.cognitiveservices.speech as speechsdk
    except ImportError:
        return synth(inner_ssml), None, "estimated"
    for attempt in range(3):
        try:
            cfg = speechsdk.SpeechConfig(subscription=os.environ["AZURE_SPEECH_KEY"], region=os.environ["AZURE_SPEECH_REGION"])
            cfg.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Riff48Khz16BitMonoPcm)
            syn = speechsdk.SpeechSynthesizer(speech_config=cfg, audio_config=None)
            words = []

            def on_word(e):
                if e.boundary_type == speechsdk.SpeechSynthesisBoundaryType.Word:
                    d = e.duration.total_seconds() if hasattr(e.duration, "total_seconds") else e.duration / 1e7
                    words.append((e.text, e.audio_offset / 1e7, d))

            syn.synthesis_word_boundary.connect(on_word)
            res = syn.speak_ssml_async(build_ssml(inner_ssml)).get()
            if res.reason == speechsdk.ResultReason.SynthesizingAudioCompleted and words:
                return res.audio_data, words, "azure"
            print("Speech SDK gave no word boundaries:", res.reason, flush=True)
        except Exception as ex:  # noqa: BLE001
            print("Speech SDK error:", type(ex).__name__, str(ex)[:120], flush=True)
        time.sleep(2 * (attempt + 1))
    return synth(inner_ssml), None, "estimated"


def estimate_words(text, start, dur):
    """Fallback word times: the line duration shared between words by their length."""
    toks = [w for w in re.split(r"\s+", text.replace("+", "")) if re.search(r"\w", w)]
    weights = [len(re.sub(r"\W", "", w)) + 1 for w in toks]
    tot, t, out = sum(weights) or 1, start, []
    for w, k in zip(toks, weights):
        d = dur * k / tot
        out.append({"w": w, "start": round(t, 3), "end": round(t + d, 3)})
        t += d
    return out


def line_words(text, azure_words, line_start, lead_trim, dur):
    """Word list of one line in absolute time (seconds in the final narration)."""
    if not azure_words:
        return estimate_words(text, line_start, dur)
    out = []
    for w, off, d in azure_words:
        a = max(line_start, line_start + off - lead_trim)
        out.append({"w": w, "start": round(a, 3), "end": round(a + d, 3)})
    return out


def check_homographs(lines):
    """Stop the build if a meaning-dependent word is not stress-marked (and not in the pronunciation dictionary)."""
    hom = set(json.load(open("voices/homographs.json", encoding="utf-8"))["words"])
    bad = []
    for l in lines:
        for tok in re.findall(r"[+А-Яа-яЁё]+", l["text"]):
            bare = tok.replace("+", "").lower()
            if bare in hom and "+" not in tok and bare not in LEX:
                bad.append(f"line {l['idx']}: {tok} — {l['text'][:70]}")
    if bad:
        print("UNMARKED HOMOGRAPHS (add + before the stressed vowel):\n" + "\n".join(bad))
        sys.exit(1)


def main(ep):
    import numpy as np
    items, lines = parse(ep)
    check_homographs(lines)
    os.makedirs("out", exist_ok=True)
    sr = 48000
    gap = lambda ms: np.zeros(int(sr * ms / 1000), dtype=np.float32)
    out, t, timeline, log = [gap(600)], 0.6, [], []
    all_words, sources, scene = [], set(), None
    for it in items:
        if it["type"] == "scene":
            scene = it["name"]
            timeline.append({"scene": scene, "start": round(t, 2)})
        elif it["type"] == "para":
            out.append(gap(350)); t += 0.35
        else:
            inner = to_ssml(it["text"])
            if "<phoneme" in inner:
                log.append(inner)
            wav, azure_words, src = synth_words(inner)
            sources.add(src)
            with wave.open(io.BytesIO(wav)) as w:
                a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
            nz = np.where(np.abs(a) > 0.008)[0]
            lead = 0
            if len(nz):
                lead = max(0, nz[0] - int(0.04 * sr))
                a = a[lead: nz[-1] + int(0.10 * sr)]
            for wd in line_words(it["text"], azure_words, t, lead / sr, len(a) / sr):
                all_words.append(dict(wd, scene=scene, line=it["idx"]))
            out.append(a); t += len(a) / sr
            ms = 950 if it["dramatic"] else 300
            out.append(gap(ms)); t += ms / 1000
            print(f"[{it['idx']:03d}] {len(a)/sr:5.1f}s {it['text'][:60]}", flush=True)
    out.append(gap(1500)); t += 1.5
    import soundfile as sf
    sf.write("out/narration_raw.wav", np.concatenate(out), sr)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", "out/narration_raw.wav", "-af",
                    "highpass=f=60,loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", "48000", "-ac", "1", "out/narration.wav"], check=True)
    wsrc = "azure" if sources == {"azure"} else "estimated" if sources == {"estimated"} else "mixed"
    json.dump({"duration": round(t, 2), "scenes": timeline, "words": all_words, "words_source": wsrc},
              open("out/timeline.json", "w"), ensure_ascii=False, indent=1)
    open("out/ssml_log.txt", "w", encoding="utf-8").write("\n".join(log))
    print(f"duration {t/60:.2f} min, lines {len(lines)}, forced-stress lines {len(log)}, word times: {wsrc}")


if __name__ == "__main__":
    main(sys.argv[1])
