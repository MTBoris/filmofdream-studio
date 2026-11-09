"""Fetch Pixabay stock videos for a storyboard. python scripts/stock.py STORYBOARD.json OUTDIR
Writes OUTDIR/<scene>_<n>.mp4 and OUTDIR/stock.json (sources). Pixabay content: free for commercial use, no attribution required."""
import json, os, sys, time, urllib.parse, urllib.request, urllib.error

sb = json.load(open(sys.argv[1], encoding="utf-8")); out = sys.argv[2]
os.makedirs(out, exist_ok=True)
key = os.environ["PIXABAY_API_KEY"]
used, sources = set(), {}


def search(q):
    url = "https://pixabay.com/api/videos/?" + urllib.parse.urlencode({"key": key, "q": q, "per_page": 30, "safesearch": "true", "order": "popular"})
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (filmofdream-studio)"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r).get("hits", [])
    except urllib.error.HTTPError as e:
        print("Pixabay search error", e.code, e.read()[:200]); raise


for scene, shots in sb.items():
    if scene.startswith("_"):
        continue
    for n, shot in enumerate(shots):
        if "stock" not in shot:
            continue
        hits = search(shot["stock"]); time.sleep(0.7)
        pick = None
        for h in hits:
            v = h["videos"].get("large") or {}
            if h["id"] in used or not v.get("url") or v.get("width", 0) < 1920 or h.get("duration", 0) < 5:
                continue
            pick = (h, v); break
        if not pick:
            for h in hits:
                v = h["videos"].get("medium") or {}
                if h["id"] not in used and v.get("url") and v.get("width", 0) >= 1280:
                    pick = (h, v); break
        name = f"{scene}_{n}"
        if not pick:
            print("NO RESULT", name, shot["stock"]); continue
        h, v = pick; used.add(h["id"])
        path = os.path.join(out, name + ".mp4")
        req = urllib.request.Request(v["url"], headers={"User-Agent": "Mozilla/5.0 (filmofdream-studio)"})
        with urllib.request.urlopen(req, timeout=120) as r:
            open(path, "wb").write(r.read())
        sources[name] = {"query": shot["stock"], "pixabay_id": h["id"], "page": h["pageURL"], "duration": h["duration"], "tags": h["tags"]}
        print(name, shot["stock"], "->", h["pageURL"], h["duration"], "s", flush=True)
json.dump(sources, open(os.path.join(out, "stock.json"), "w"), ensure_ascii=False, indent=1)
