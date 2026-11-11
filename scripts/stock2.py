"""Pixabay stock for storyboard v2: 3 candidates per shot -> candidate sheet -> pick -> download.

    python scripts/stock2.py candidates STORYBOARD.json OUTDIR   # candidates.json, pool.json, sheet-NN.jpg
    python scripts/stock2.py fetch STORYBOARD.json STOCKDIR      # downloads the picked clips + stock.json (sources)

Also dropped: clips on config/stock_blocklist.json, clips that are not 16:9, and clips whose picture has black bars
(checked on the pixels of the preview video, and again on the full clip when it is downloaded).
OPEN WATER ONLY: candidates tagged with land, rocks, coast, beach, islands, boats/ships (and similar) are dropped,
except in "research ship" shots (query contains "research ship", or "vessels": true). The sheet says which rule applies.
A clip is never used twice in an episode: candidates are unique across all shots, picks must be unique
(sb2.validate_structure), and if there are not enough unique clips the shortage is REPORTED, never repeated silently.
The search results are cached in OUTDIR/pool.json (metadata only), so re-runs do not hit the Pixabay API again.
Pixabay content: free for commercial use, no attribution required.
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sb2  # noqa: E402

N_CANDIDATES = 3
UA = {"User-Agent": "Mozilla/5.0 (filmofdream-studio)"}
BAD = ("ai generated", "ai-generated", "fantasy", "3d", "render", "animation", "cgi", "futuristic", "sci-fi", "generated")
STOP = ("old", "the", "and", "with")
# Open water only: a candidate whose tags mention land, coast, islands or vessels is dropped.
LAND_WORDS = {"land", "rock", "rocks", "rocky", "cliff", "cliffs", "coast", "coastal", "coastline", "shore", "shoreline", "beach",
              "beaches", "island", "islands", "isle", "bay", "harbor", "harbour", "port", "pier", "dock", "jetty", "lighthouse",
              "mountain", "mountains", "hill", "hills", "forest", "tree", "trees", "palm", "sand", "dune", "village", "town",
              "city", "building", "buildings", "house", "bridge", "resort", "cape", "peninsula", "lagoon", "seaside",
              "jungle", "palms", "palm tree", "rainforest", "rain-forest", "rain forest", "coconut", "tropical forest", "woods"}
VESSEL_WORDS = {"boat", "boats", "ship", "ships", "yacht", "yachts", "sailboat", "sailboats", "sailing", "motorboat", "speedboat",
                "ferry", "cruise", "kayak", "canoe", "fishing", "vessel", "cargo", "tanker", "liner", "catamaran", "surfing",
                "surfer", "swimmer", "swimming", "diver", "diving"}
BLOCKLIST_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "stock_blocklist.json")
ASPECT = 16 / 9
ASPECT_TOL = 0.03   # clips that are not 16:9 (within 3 %) are dropped: they come with bars or need a heavy crop


def blocklist():
    try:
        return {int(k): v for k, v in json.load(open(BLOCKLIST_PATH, encoding="utf-8")).get("ids", {}).items()}
    except (OSError, ValueError):
        return {}


OPEN_WATER_NOTE = "Only open water: no land, rocks, coast, islands, boats (except 'research ship' shots); 16:9 only, no black bars"


def key():
    return os.environ["PIXABAY_API_KEY"]


def api(params):
    url = "https://pixabay.com/api/videos/?" + urllib.parse.urlencode(dict(params, key=key()))
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
            return json.load(r).get("hits", [])
    except urllib.error.HTTPError as e:
        print("Pixabay error", e.code, e.read()[:200])
        raise


def slim(h):
    """Keep only what we need (this is what the pool cache stores)."""
    vids = {k: {"url": v.get("url"), "width": v.get("width"), "height": v.get("height")} for k, v in (h.get("videos") or {}).items()}
    return {"id": h["id"], "tags": h.get("tags", ""), "duration": h.get("duration", 0), "page": h.get("pageURL"),
            "type": h.get("type", "film"), "user": h.get("user"), "videos": vids}


def search(q):
    hits = [slim(h) for h in api({"q": q, "per_page": 50, "safesearch": "true", "order": "popular"})]
    time.sleep(0.7)
    return hits


def good(h, words):
    tags = h.get("tags", "").lower()
    return (h.get("type", "film") == "film" and not any(b in tags for b in BAD) and all(w in tags for w in words)
            and h.get("duration", 0) >= 5)


def tag_words(h):
    """Single words and whole comma-separated tags ("palm tree", "rain-forest")."""
    tags = [t.strip() for t in h.get("tags", "").lower().split(",") if t.strip()]
    return set(tags) | {w for t in tags for w in t.split()}


def vessels_allowed(shot):
    """Boats/ships are allowed only in 'research ship' shots (or with "vessels": true in the storyboard)."""
    return bool(shot.get("vessels")) or "research ship" in " ".join([shot.get("query", "")] + list(shot.get("queries") or [])).lower()


def open_water(h, allow_vessels=False):
    w = tag_words(h)
    return not (w & LAND_WORDS) and (allow_vessels or not (w & VESSEL_WORDS))


def query_words(q):
    return [w[:5] for w in q.lower().split() if len(w) > 2 and w not in STOP]


def aspect_ok(v):
    w, h = v.get("width") or 0, v.get("height") or 0
    return bool(w and h) and abs(w / h - ASPECT) <= ASPECT * ASPECT_TOL


def rendition(h):
    """Best usable 16:9 file: 'large' if >=1920 wide, else 'medium' if >=1280, else None."""
    v = h["videos"].get("large") or {}
    if v.get("url") and (v.get("width") or 0) >= 1920 and aspect_ok(v):
        return "large", v
    v = h["videos"].get("medium") or {}
    if v.get("url") and (v.get("width") or 0) >= 1280 and aspect_ok(v):
        return "medium", v
    return None


def filter_hits(hits, query, allow_vessels=False):
    words = query_words(query)
    blocked = blocklist()
    return [h for h in hits if h["id"] not in blocked and good(h, words) and rendition(h) and open_water(h, allow_vessels)]


def assign_candidates(shots, pool, taken=(), n=N_CANDIDATES, accept=None):
    """shots: [{"id", "query", "queries"?}]. pool: {query: [hits]}. Returns ({shot_id: [hits]}, [shortage messages]).
    No clip is a candidate for two shots (so the picks can never collide), and `taken` ids (already picked) are skipped."""
    used = set(taken)
    out, short = {}, []
    for s in shots:
        got = []
        allow = vessels_allowed(s)
        for q in [s["query"]] + list(s.get("queries") or []):
            for h in filter_hits(pool.get(q, []), q, allow):
                if h["id"] not in used and h["id"] not in {g["id"] for g in got} and (accept is None or accept(h)):
                    got.append(h)
                    if len(got) == n:
                        break
            if len(got) == n:
                break
        for h in got:
            used.add(h["id"])
        out[s["id"]] = got
        if len(got) < n:
            short.append(f"{s['id']} ({s['query']!r}): only {len(got)} unique clip(s) instead of {n}")
    return out, short


def stock_shots(sb):
    out = []
    for sc in sb["scenes"]:
        for k, s in enumerate(sc["shots"]):
            if s.get("type") == "stock":
                out.append(dict(s, id=s.get("id") or f"{sc['scene']}-{k + 1}", scene=sc["scene"]))
    return out


def font(size):
    from PIL import ImageFont
    import matplotlib
    p = os.path.join(matplotlib.get_data_path(), "fonts", "ttf", "DejaVuSans-Bold.ttf")
    try:
        return ImageFont.truetype(p, size)
    except OSError:
        return ImageFont.load_default()


def black_bars(mp4, seconds=8, limit=18):
    """True if the picture itself has black bars (letterbox / pillarbox), even when the file is 16:9.
    ffmpeg cropdetect keeps the largest non-black area seen over the first seconds; bars = it is clearly smaller than the frame."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-t", str(seconds), "-i", mp4, "-vf", f"cropdetect=limit={limit}:round=2:reset=0", "-f", "null", "-"],
                       capture_output=True, text=True)
    full = re.search(r"Stream #0.*?Video:.*?, (\d{2,5})x(\d{2,5})", r.stderr)
    crops = re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", r.stderr)
    if not full or not crops:
        return False
    fw, fh = int(full.group(1)), int(full.group(2))
    cw, ch = int(crops[-1][0]), int(crops[-1][1])
    return cw < fw * 0.96 or ch < fh * 0.96


def preview_mp4(h, cache_dir):
    v = h["videos"].get("tiny") or h["videos"].get("small") or h["videos"].get("medium") or {}
    mp4 = os.path.join(cache_dir, f"{h['id']}.mp4")
    if not os.path.exists(mp4):
        with urllib.request.urlopen(urllib.request.Request(v["url"], headers=UA), timeout=90) as r:
            open(mp4, "wb").write(r.read())
    return mp4


def preview_frames(h, cache_dir):
    """3 frames (15%, 50%, 85%) from the smallest rendition; returns PNG paths."""
    from PIL import Image  # noqa: F401
    mp4 = preview_mp4(h, cache_dir)
    paths = []
    for i, f in enumerate((0.15, 0.5, 0.85)):
        p = os.path.join(cache_dir, f"{h['id']}_{i}.png")
        if not os.path.exists(p):
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{h['duration'] * f:.2f}", "-i", mp4, "-frames:v", "1",
                            "-vf", "scale=213:120:force_original_aspect_ratio=increase,crop=213:120", p], check=True)
        paths.append(p)
    return paths


def make_sheets(rows, outdir, cache_dir, per_page=5):
    """rows: [(shot, [hits])]. One row per shot: header, then 3 candidates x 3 frames. Returns sheet paths."""
    from PIL import Image, ImageDraw
    W, FW, FH, HEAD, LAB = 1920, 213, 120, 34, 26
    row_h = HEAD + LAB + FH + 8
    paths = []
    for page, i in enumerate(range(0, len(rows), per_page), 1):
        chunk = rows[i:i + per_page]
        im = Image.new("RGB", (W, row_h * len(chunk)), (18, 20, 24))
        d = ImageDraw.Draw(im)
        for r, (shot, hits) in enumerate(chunk):
            y = r * row_h
            rule = "research ship: boats allowed" if vessels_allowed(shot) else "open water only"
            d.text((8, y + 6), f"{shot['id']}   «{shot['query']}»   [{rule}]   {shot.get('note', '')}"[:150], font=font(18), fill=(255, 220, 90))
            for c, h in enumerate(hits):
                x0 = c * (W // N_CANDIDATES) + 6
                d.text((x0, y + HEAD + 3), f"pix:{h['id']} · {h['duration']}s · {h['tags']}"[:64], font=font(14), fill=(220, 220, 220))
                for j, p in enumerate(preview_frames(h, cache_dir)):
                    im.paste(Image.open(p).convert("RGB"), (x0 + j * (FW + 2), y + HEAD + LAB))
            if not hits:
                d.text((8, y + HEAD + LAB + 40), "NO CANDIDATES", font=font(28), fill=(255, 90, 90))
        p = os.path.join(outdir, f"sheet-{page:02d}.jpg")
        im.save(p, quality=85)
        paths.append(p)
    return paths


def cmd_candidates(sb_path, outdir):
    sb = sb2.load(sb_path)
    errs, _ = sb2.validate_structure(sb)
    if errs:
        sys.exit("STORYBOARD ERROR:\n" + "\n".join(errs))
    os.makedirs(outdir, exist_ok=True)
    cache_dir = os.path.join(outdir, "previews")
    os.makedirs(cache_dir, exist_ok=True)
    pool_path = os.path.join(outdir, "pool.json")
    pool = json.load(open(pool_path, encoding="utf-8")) if os.path.exists(pool_path) else {}
    shots = stock_shots(sb)
    picked = {sb2.pick_id(s.get("pick")) for s in shots if sb2.pick_id(s.get("pick"))}
    for s in shots:
        for q in [s["query"]] + list(s.get("queries") or []):
            if q not in pool:
                pool[q] = search(q)
                print(f"searched {q!r}: {len(pool[q])} hits", flush=True)
    json.dump(pool, open(pool_path, "w", encoding="utf-8"), ensure_ascii=False)
    todo = [s for s in shots if not sb2.pick_id(s.get("pick"))]
    bars_path = os.path.join(outdir, "bars.json")
    bars = json.load(open(bars_path, encoding="utf-8")) if os.path.exists(bars_path) else {}

    def no_bars(h):  # looks at the real pixels of the preview video (cached per clip)
        k = str(h["id"])
        if k not in bars:
            bars[k] = black_bars(preview_mp4(h, cache_dir))
            if bars[k]:
                print(f"dropped pix:{h['id']}: black bars", flush=True)
        return not bars[k]

    cands, short = assign_candidates(todo, pool, taken=picked, accept=no_bars)
    json.dump(bars, open(bars_path, "w"))
    rows = [(s, cands[s["id"]]) for s in todo]
    sheets = make_sheets(rows, outdir, cache_dir)
    summary = {sid: [{"pick": f"pix:{h['id']}", "page": h["page"], "duration": h["duration"], "tags": h["tags"]} for h in hs]
               for sid, hs in cands.items()}
    json.dump({"rule": OPEN_WATER_NOTE, "candidates": summary, "shortage": short}, open(os.path.join(outdir, "candidates.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"{len(todo)} shots need a pick; sheets: {', '.join(sheets)}")
    if short:
        print("NOT ENOUGH UNIQUE CLIPS (nothing was repeated; add 'queries' alternatives or change the query):")
        for m in short:
            print("  -", m)


def cmd_fetch(sb_path, stockdir):
    sb = sb2.load(sb_path)
    errs, _ = sb2.validate_structure(sb)
    mp = sb2.missing_picks(sb)
    if mp:
        errs.append("no clip chosen (pick) for stock shots: " + ", ".join(mp))
    if errs:
        sys.exit("STORYBOARD ERROR:\n" + "\n".join(dict.fromkeys(errs)))
    os.makedirs(stockdir, exist_ok=True)
    sources = {}
    for s in stock_shots(sb):
        pid = sb2.pick_id(s["pick"])
        hits = [slim(h) for h in api({"id": pid})]
        if not hits:
            sys.exit(f"{s['id']}: Pixabay has no clip {pid}")
        h = hits[0]
        if pid in blocklist():
            sys.exit(f"{s['id']}: pix:{pid} is on the blocklist ({blocklist()[pid]}) - pick another clip")
        r = rendition(h)
        if not r:
            sys.exit(f"{s['id']}: pix:{pid} has no 1280+ wide rendition")
        if not open_water(h, vessels_allowed(s)):
            print(f"WARN: {s['id']}: pix:{pid} is tagged with land/coast/boat words ({h['tags']}); the storyboard asks for open water")
        path = os.path.join(stockdir, s["id"] + ".mp4")
        with urllib.request.urlopen(urllib.request.Request(r[1]["url"], headers=UA), timeout=180) as resp:
            open(path, "wb").write(resp.read())
        sources[s["id"]] = {"query": s["query"], "pixabay_id": pid, "page": h["page"], "duration": h["duration"], "tags": h["tags"],
                            "rendition": r[0]}
        if black_bars(path):
            sys.exit(f"{s['id']}: pix:{pid} has black bars (letterbox) - pick another clip")
        print(s["id"], "->", h["page"], flush=True)
        time.sleep(0.5)
    json.dump(sources, open(os.path.join(stockdir, "stock.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def cmd_autopick(sb_path, candidates_json, out_path):
    """PREVIEW ONLY: take the first candidate for every shot without a pick. Real episodes are picked by ChatGPT."""
    sb = sb2.load(sb_path)
    cands = json.load(open(candidates_json, encoding="utf-8"))["candidates"]
    for sc in sb["scenes"]:
        for k, s in enumerate(sc["shots"]):
            sid = s.get("id") or f"{sc['scene']}-{k + 1}"
            if s.get("type") == "stock" and not sb2.pick_id(s.get("pick")):
                if not cands.get(sid):
                    sys.exit(f"no candidate for {sid}")
                s["pick"] = cands[sid][0]["pick"]
    json.dump(sb, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("auto-picked (preview only) ->", out_path)


if __name__ == "__main__":
    if sys.argv[1:2] == ["autopick"] and len(sys.argv) == 5:
        cmd_autopick(*sys.argv[2:])
    elif len(sys.argv) != 4 or sys.argv[1] not in ("candidates", "fetch"):
        sys.exit(__doc__)
    else:
        {"candidates": cmd_candidates, "fetch": cmd_fetch}[sys.argv[1]](sys.argv[2], sys.argv[3])
