"""Prepare the image assets of a storyboard v2 for rendering.

    python scripts/assets.py EPISODE_DIR STORYBOARD.json OUTDIR

* "image"          -> EPISODE_DIR/assets/<asset_id>.(png|jpg|jpeg|webp)   (made by ChatGPT, handed over via Boris/Claude)
* "external-image" -> downloaded from assets[asset_id].url, or - if only .page is given - the large image is found on that
                      NASA Earth Observatory page. The credit text in the storyboard is printed into the video description.
Every image is converted to OUTDIR/<asset_id>.png (16:9 crop is done by the renderer) and must be at least 1280 px wide.
No logos are added. Writes OUTDIR/assets.json (what was used, source, credit).
"""
import glob
import json
import os
import re
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sb2  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (filmofdream-studio)"}
MIN_WIDTH = 1280
EXTS = ("png", "jpg", "jpeg", "webp")
ALLOWED_HOSTS = ("earthobservatory.nasa.gov", "eoimages.gsfc.nasa.gov", "images.nasa.gov", "images-assets.nasa.gov",
                 "science.nasa.gov", "assets.science.nasa.gov", "www.nasa.gov")


def host_ok(url):
    m = re.match(r"https://([^/]+)/", url)
    return bool(m) and m.group(1) in ALLOWED_HOSTS


def find_large_image(html, page_url):
    """Pick the full-size picture on a NASA Earth Observatory image page. Prefers *_lrg, never thumbnails."""
    urls = re.findall(r"""(?:href|src|content)=["']((?:https?:)?//[^"']*eoimages\.gsfc\.nasa\.gov/images/imagerecords/[^"']+?\.(?:jpg|jpeg|png))["']""", html, flags=re.I)
    urls = [("https:" + u) if u.startswith("//") else u for u in urls]
    m = re.search(r"/images/(\d+)", page_url)
    if m:
        urls = [u for u in urls if f"/{m.group(1)}/" in u] or urls
    urls = [u for u in dict.fromkeys(urls) if not re.search(r"_(tmb|th|thumb)\b|_th\.", u, flags=re.I)]
    if not urls:   # the Earth Observatory moved to science.nasa.gov: og:image / any NASA image, no thumbnails or logos
        urls = re.findall(r"""(?:href|src|content)=["']((?:https?:)?//(?:assets\.science|science|www)\.nasa\.gov/[^"']+?\.(?:jpg|jpeg|png))(?:\?[^"']*)?["']""", html, flags=re.I)
        urls = [("https:" + u) if u.startswith("//") else u for u in urls]
        urls = [u for u in dict.fromkeys(urls) if not re.search(r"logo|icon|favicon|sprite|thumb|_tmb|\d{2,3}x\d{2,3}\.", u, flags=re.I)]
        print("fallback image candidates:", urls)
    if not urls:
        return None
    return sorted(urls, key=lambda u: (0 if "_lrg" in u else 1 if "_web" not in u else 2, -len(u)))[0]


def fetch(url, timeout=120):
    if not host_ok(url):
        raise sb2.StoryboardError(f"external image host not allowed: {url}")
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def local_image(ep_dir, asset_id):
    for ext in EXTS:
        p = os.path.join(ep_dir, "assets", f"{asset_id}.{ext}")
        if os.path.exists(p):
            return p
    hits = [p for p in glob.glob(os.path.join(ep_dir, "assets", asset_id + ".*")) if p.rsplit(".", 1)[-1].lower() in EXTS]
    return hits[0] if hits else None


def main(ep_dir, sb_path, outdir):
    from PIL import Image
    import io
    sb = sb2.load(sb_path)
    os.makedirs(outdir, exist_ok=True)
    used, problems = {}, []
    for sc in sb["scenes"]:
        for s in sc["shots"]:
            if s.get("type") not in ("image", "external-image"):
                continue
            aid = s["asset_id"]
            if aid in used:
                continue
            info = sb2.asset_info(sb, aid) or {}
            data, source = None, None
            if s["type"] == "external-image":
                url = info.get("url")
                if not url:
                    html = fetch(info["page"]).decode("utf-8", "replace")
                    title = re.search(r"<title>(.*?)</title>", html, flags=re.S | re.I)
                    print(f"{aid}: page title: {title.group(1).strip() if title else '?'}")
                    url = find_large_image(html, info["page"])
                    if not url:
                        problems.append(f"{aid}: no large image found on {info['page']}")
                        continue
                data, source = fetch(url), url
            else:
                p = local_image(ep_dir, aid)
                if not p:
                    problems.append(f"{aid}: file {ep_dir}/assets/{aid}.(png|jpg|webp) not found (ChatGPT image missing)")
                    continue
                data, source = open(p, "rb").read(), os.path.relpath(p)
            im = Image.open(io.BytesIO(data)).convert("RGB")
            if im.width < MIN_WIDTH:
                problems.append(f"{aid}: image is only {im.width}px wide (need {MIN_WIDTH}+)")
                continue
            im.save(os.path.join(outdir, aid + ".png"))
            used[aid] = {"source": source, "size": [im.width, im.height], "type": s["type"],
                         "credit": info.get("credit"), "label": info.get("label")}
            print(f"{aid}: {im.width}x{im.height} <- {source}")
    json.dump(used, open(os.path.join(outdir, "assets.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if problems:
        sys.exit("ASSET PROBLEMS:\n" + "\n".join(problems))


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
