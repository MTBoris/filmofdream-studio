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


def search_id(i):
    url = "https://pixabay.com/api/videos/?" + urllib.parse.urlencode({"key": key, "id": i})
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (filmofdream-studio)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r).get("hits", [])


for scene, shots in sb.items():
    if scene.startswith("_"):
        continue
    for n, shot in enumerate(shots):
        if "stock" not in shot:
            continue
        hits = search(shot["stock"]); time.sleep(0.7)
        pick = None
        BAD = ("ai generated", "ai-generated", "fantasy", "3d", "render", "animation", "cgi", "futuristic", "sci-fi", "generated")
        hits = [h for h in hits if h.get("type", "film") == "film" and not any(b in h.get("tags", "").lower() for b in BAD)]
        words = [w[:5] for w in shot["stock"].lower().split() if len(w) > 2 and w not in ("old", "the", "and", "with")]
        hits = [h for h in hits if all(w in h.get("tags", "").lower() for w in words)]
        if shot.get("pixabay_id"):
            hits = [h for h in search_id(shot["pixabay_id"])] + hits
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
