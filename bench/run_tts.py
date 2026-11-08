"""Benchmark one TTS engine on the Sandy Island hook. Writes out/<name>.wav and out/<name>.json."""
import json, os, sys, time, resource
import numpy as np, soundfile as sf

engine, name = sys.argv[1], sys.argv[2]
chunks = [l.strip() for l in open("bench/hook_chunks.txt", encoding="utf-8") if l.strip()]
os.makedirs("out", exist_ok=True)
t0 = time.time()
pieces, sr = [], None

if engine.startswith("qwen"):
    import torch
    from qwen_tts import Qwen3TTSModel
    torch.set_num_threads(os.cpu_count())
    instruct = os.environ.get("INSTRUCT", "")
    dtype = torch.float32
    if engine == "qwen-clone":
        # Design the voice once, then clone it for every chunk so the voice stays identical.
        design = Qwen3TTSModel.from_pretrained("Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign", device_map="cpu", dtype=dtype)
        ref_text = "Добрый вечер. Сегодня я расскажу вам историю, которую долго никто не мог объяснить."
        w, sr = design.generate_voice_design(text=ref_text, language="Russian", instruct=instruct)
        sf.write(f"out/{name}-reference.wav", w[0], sr)
        del design
        model = Qwen3TTSModel.from_pretrained("Qwen/Qwen3-TTS-12Hz-1.7B-Base", device_map="cpu", dtype=dtype)
        prompt = model.create_voice_clone_prompt(ref_audio=f"out/{name}-reference.wav", ref_text=ref_text)
        load_s = time.time() - t0
        for c in chunks:
            wavs, sr = model.generate_voice_clone(text=c, language="Russian", voice_clone_prompt=prompt)
            pieces.append(np.asarray(wavs[0], dtype=np.float32))
    repo = {"qwen-design": "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
            "qwen-custom": "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"}.get(engine)
    if repo:
        model = Qwen3TTSModel.from_pretrained(repo, device_map="cpu", dtype=dtype)
        load_s = time.time() - t0
    for c in (chunks if repo else []):
        if engine == "qwen-design":
            wavs, sr = model.generate_voice_design(text=c, language="Russian", instruct=instruct)
        else:
            wavs, sr = model.generate_custom_voice(text=c, language="Russian", speaker=os.environ.get("SPEAKER", "Ryan"), instruct=instruct)
        pieces.append(np.asarray(wavs[0], dtype=np.float32))
elif engine == "chatterbox":
    import torch
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    model = ChatterboxMultilingualTTS.from_pretrained(device="cpu")
    load_s = time.time() - t0
    sr = model.sr
    for c in chunks:
        wav = model.generate(c, language_id="ru")
        pieces.append(wav.squeeze().cpu().numpy().astype(np.float32))

gen_s = time.time() - t0 - load_s
pause = np.zeros(int(sr * 0.35), dtype=np.float32)
audio = np.concatenate([x for p in pieces for x in (p, pause)])
sf.write(f"out/{name}.wav", audio, sr)
dur = len(audio) / sr
res = {"name": name, "engine": engine, "load_s": round(load_s, 1), "gen_s": round(gen_s, 1),
       "audio_s": round(dur, 1), "realtime_factor": round(gen_s / dur, 2),
       "peak_rss_gb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6, 2),
       "est_minutes_for_9min_video": round(gen_s / dur * 9, 1)}
json.dump(res, open(f"out/{name}.json", "w"), ensure_ascii=False)
print(res)
