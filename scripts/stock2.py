"""Pixabay stock for storyboard v2: 3 candidates per shot -> candidate sheet -> pick -> download.

    python scripts/stock2.py candidates STORYBOARD.json OUTDIR   # candidates.json, pool.json, sheet-NN.jpg
    python scripts/stock2.py fetch STORYBOARD.json STOCKDIR      # downloads the picked clips + stock.json (sources)

A clip is never used twice in an episode: candidates are unique across all shots, picks must be unique
(sb2.validate_structure), and if there are not enough unique clips the shortage is REPORTED, never repeated silently.
The search results are cached in OUTDIR/pool.json (metadata only), so re-runs do not hit the Pixabay API again.
Pixabay content: free for commercial use, no attribution required.
"""
import json
import os
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


def query_words(q):
    return [w[:5] for w in q.lower().split() if len(w) > 2 and w not in STOP]


def rendition(h):
    """Best usable file: 'large' if >=1920 wide, else 'medium' if >=1280, else None."""
    v = h["videos"].get("large") or {}
    if v.get("url") and (v.get("width") or 0) >= 1920:
        return "large", v
    v = h["videos"].get("medium") or {}
    if v.get("url") and (v.get("width") or 0) >= 1280:
        return "medium", v
    return None


def filter_hits(hits, query):
    words = query_words(query)
    return [h for h in hits if good(h, words) and rendition(h)]


def assign_candidates(shots, pool, taken=(), n=N_CANDIDATES):
    """shots: [{"id", "query", "queries"?}]. pool: {query: [hits]}. Returns ({shot_id: [hits]}, [shortage messages]).
    No clip is a candidate for two shots (so the picks can never collide), and `taken` ids (already picked) are skipped."""
    used = set(taken)
    out, short = {}, []
    for s in shots:
        got = []
        for q in [s["query"]] + list(s.get("queries") or []):
            for h in filter_hits(pool.get(q, []), q):
                if h["id"] not in used and h["id"] not in {g["id"] for g in got}:
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


def preview_frames(h, cache_dir):
    """3 frames (15%, 50%, 85%) from the smallest rendition; returns PNG paths."""
    from PIL import Image  # noqa: F401
    v = h["videos"].get("tiny") or h["videos"].get("small") or h["videos"].get("medium") or {}
    mp4 = os.path.join(cache_dir, f"{h['id']}.mp4")
    if not os.path.exists(mp4):
        with urllib.request.urlopen(urllib.request.Request(v["url"], headers=UA), timeout=90) as r:
            open(mp4, "wb").write(r.read())
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
            d.text((8, y + 6), f"{shot['id']}   «{shot['query']}»   {shot.get('note', '')}"[:150], font=font(18), fill=(255, 220, 90))
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
    cands, short = assign_candidates(todo, pool, taken=picked)
    rows = [(s, cands[s["id"]]) for s in todo]
    sheets = make_sheets(rows, outdir, cache_dir)
    summary = {sid: [{"pick": f"pix:{h['id']}", "page": h["page"], "duration": h["duration"], "tags": h["tags"]} for h in hs]
               for sid, hs in cands.items()}
    json.dump({"candidates": summary, "shortage": short}, open(os.path.join(outdir, "candidates.json"), "w", encoding="utf-8"),
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
        r = rendition(h)
        if not r:
            sys.exit(f"{s['id']}: pix:{pid} has no 1280+ wide rendition")
        path = os.path.join(stockdir, s["id"] + ".mp4")
        with urllib.request.urlopen(urllib.request.Request(r[1]["url"], headers=UA), timeout=180) as resp:
            open(path, "wb").write(resp.read())
        sources[s["id"]] = {"query": s["query"], "pixabay_id": pid, "page": h["page"], "duration": h["duration"], "tags": h["tags"],
                            "rendition": r[0]}
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
