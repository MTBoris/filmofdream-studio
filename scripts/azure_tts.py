"""Azure Neural TTS via REST. python scripts/azure_tts.py VOICE RATE TEXTFILE OUT.wav"""
import os, sys, urllib.request
from xml.sax.saxutils import escape

voice, rate, textfile, out = sys.argv[1:5]
text = open(textfile, encoding="utf-8").read().strip()
paras = [p.strip() for p in text.split("\n\n") if p.strip()]
body = "".join(f"<p>{escape(p)}</p>" for p in paras)
ssml = (f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="ru-RU">'
        f'<voice name="{voice}"><prosody rate="{rate}">{body}</prosody></voice></speak>')
req = urllib.request.Request(
    f"https://{os.environ['AZURE_SPEECH_REGION']}.tts.speech.microsoft.com/cognitiveservices/v1",
    data=ssml.encode("utf-8"), method="POST",
    headers={"Ocp-Apim-Subscription-Key": os.environ["AZURE_SPEECH_KEY"],
             "Content-Type": "application/ssml+xml",
             "X-Microsoft-OutputFormat": "riff-48khz-16bit-mono-pcm",
             "User-Agent": "filmofdream-studio"})
with urllib.request.urlopen(req) as r:
    open(out, "wb").write(r.read())
print("ok", out)
