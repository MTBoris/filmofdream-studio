"""Animated overlay templates drawn over the ocean video (transparent PNG frames).

    python scripts/overlays.py preview TEMPLATE DATA.json OUT_DIR [SECONDS]    # frames for a quick look

Templates: ocean-fact, ocean-map, ocean-timeline (more in the next PRs). Style comes from design/tokens.json.
Each template is a function draw(t, D, data, ctx) -> RGBA Image (1920x1080); t = seconds since the overlay started,
D = overlay length. A dark scrim under the text, a smooth fade/rise in and fade out, number counters.

Text sizes: data["size"] overrides the token sizes - either an object {"value": 100, "label": 80, "note": 100}
or a list in the template's field order (ocean-fact: value, label, note; ocean-timeline: date, event; ocean-map: title, label, note).
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOK = json.load(open(os.path.join(ROOT, "design", "tokens.json"), encoding="utf-8"))
W, H, FPS = TOK["canvas"]["w"], TOK["canvas"]["h"], TOK["canvas"]["fps"]
MX, MY = TOK["margin"]["x"], TOK["margin"]["y"]
MOT = TOK["motion"]
NBSP = " "


def rgb(hexstr):
    h = hexstr.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


C = {k: rgb(v) for k, v in TOK["color"].items()}
_fonts = {}


def font(key, px):
    k = (key, int(px))
    if k not in _fonts:
        _fonts[k] = ImageFont.truetype(os.path.join(ROOT, TOK["font"][key]), int(px))
    return _fonts[k]


# ---------- motion helpers ----------
def clamp01(x):
    return max(0.0, min(1.0, x))


def ease_out(x):
    return 1 - (1 - clamp01(x)) ** 3


def ease_io(x):
    x = clamp01(x)
    return x * x * (3 - 2 * x)


def appear(t, t0, dur=None):
    return ease_out((t - t0) / (dur or MOT["in"]))


def envelope(t, D):
    """0->1 over the fade-in, 1->0 over the fade-out at the end."""
    return clamp01(t / MOT["in"]) * clamp01((D - t) / MOT["out"])


def fmt_num(v, decimals=0):
    s = f"{v:,.{decimals}f}".replace(",", NBSP)
    return s.replace(".", ",")


def sizes(data, names):
    """Pixel sizes for the template's text fields: token defaults, overridden by data["size"] (dict, list or one number)."""
    out = {n: TOK["size"][n] for n in names}
    sz = data.get("size")
    if isinstance(sz, dict):
        out.update({k: v for k, v in sz.items() if k in out})
    elif isinstance(sz, (list, tuple)):
        out.update(dict(zip(names, sz)))
    elif isinstance(sz, (int, float)):
        out[names[0]] = sz
    return out


# ---------- drawing helpers ----------
def blank():
    return Image.new("RGBA", (W, H), (0, 0, 0, 0))


def comp(img, layer, x, y):
    """alpha-composite `layer` onto `img` at (x, y), clipping at the edges."""
    x0, y0 = max(0, -x), max(0, -y)
    x1, y1 = min(layer.width, W - x), min(layer.height, H - y)
    if x1 <= x0 or y1 <= y0:
        return
    img.alpha_composite(layer.crop((x0, y0, x1, y1)), (x + x0, y + y0))


def put_text(img, xy, s, key, px, color, alpha=1.0, anchor="ls", shadow=True):
    if alpha <= 0.004 or not s:
        return
    fnt = font(key, px)
    xy = (int(round(xy[0])), int(round(xy[1])))
    x0, y0, x1, y1 = ImageDraw.Draw(img).textbbox(xy, s, font=fnt, anchor=anchor)
    pad = 22
    w, h = x1 - x0 + 2 * pad, y1 - y0 + 2 * pad
    ox, oy = xy[0] - x0 + pad, xy[1] - y0 + pad
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if shadow:
        sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(sh).text((ox, oy + 3), s, font=fnt, fill=(0, 0, 0, int(170 * alpha)), anchor=anchor)
        layer.alpha_composite(sh.filter(ImageFilter.GaussianBlur(7)))
    ImageDraw.Draw(layer).text((ox, oy), s, font=fnt, fill=(*color, int(255 * alpha)), anchor=anchor)
    comp(img, layer, int(x0 - pad), int(y0 - pad))


def text_w(s, key, px):
    return font(key, px).getlength(s)


def cap_h(key, px):
    b = font(key, px).getbbox("0", anchor="ls")
    return -b[1]


_scrims = {}


def scrim_alpha(kind):
    """Static darkening mask (H, W) in 0..1 for the layout; cached."""
    if kind in _scrims:
        return _scrims[kind]
    y = np.linspace(0, 1, H)[:, None]
    x = np.linspace(0, 1, W)[None, :]
    if kind == "bottom-left":
        a = np.maximum(0.80 * np.clip((0.62 - x) / 0.62, 0, 1) ** 1.4 * np.clip((y - 0.18) / 0.82, 0, 1) ** 0.8,
                       0.55 * np.clip((y - 0.62) / 0.38, 0, 1) ** 1.3)
    elif kind == "bottom":
        a = 0.82 * np.clip((y - 0.45) / 0.55, 0, 1) ** 1.2 + 0 * x
    elif kind == "right":
        a = 0.62 * np.clip((x - 0.38) / 0.62, 0, 1) ** 1.3 + 0 * y
    else:
        a = 0 * x + 0 * y
    _scrims[kind] = np.clip(a, 0, 1)
    return _scrims[kind]


def scrim_frame(kind, strength):
    arr = np.zeros((H, W, 4), np.uint8)
    arr[..., :3] = C["scrim"]
    arr[..., 3] = (scrim_alpha(kind) * clamp01(strength) * 255).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


# ---------- ocean-fact ----------
def fact(t, D, data, ctx):
    sz = sizes(data, ("value", "label", "note"))
    env = envelope(t, D)
    img = scrim_frame("bottom-left", env)
    rise = MOT["rise_px"]
    values = data["value"] if isinstance(data["value"], list) else [data["value"]]
    dec = int(data.get("decimals", 0))
    cnt = clamp01((t - 0.15) / MOT["counter_s"])
    shown = [v * ease_out(cnt) for v in values]
    sep = "–"
    vtxt = sep.join(fmt_num(v, dec) for v in shown) + data.get("suffix", "")
    unit = data.get("unit", "")
    x, base = MX, H - MY
    if data.get("note"):
        a = appear(t, 0.45) * env
        put_text(img, (x, base + (1 - appear(t, 0.45)) * rise), data["note"], "sans", sz["note"], C["muted"], a)
        base -= sz["note"] + 34
    a = appear(t, 0.15) * env
    yv = base + (1 - appear(t, 0.15)) * rise
    put_text(img, (x, yv), vtxt, "serif", sz["value"], C["text"], a)
    if unit:
        put_text(img, (x + text_w(vtxt, "serif", sz["value"]) + sz["value"] * 0.14, yv), unit, "serif", int(sz["value"] * 0.5), C["accent"], a)
    if data.get("label"):
        a = appear(t, 0.0) * env
        yl = base - cap_h("serif", sz["value"]) - 30 + (1 - appear(t, 0.0)) * rise
        put_text(img, (x, yl), data["label"].upper(), "sans_bold", sz["label"], C["accent"], a)
    return img


# ---------- ocean-timeline ----------
def timeline(t, D, data, ctx):
    sz = sizes(data, ("date", "event"))
    events = data["events"]
    n = len(events)
    env = envelope(t, D)
    img = scrim_frame("bottom", env)
    half = 170  # half of the widest label, keeps the outer labels inside the margins
    left, right = MX + half, W - MX - half
    step = min(430, (right - left) / max(1, n - 1)) if n > 1 else 0
    x0 = (left + right) / 2 - step * (n - 1) / 2
    y_line = H - MY - 190
    times = []
    for i, e in enumerate(events):
        times.append(e["t"] - ctx.get("start", 0) if e.get("t") is not None else 0.5 + i * (MOT["stagger_s"] + 0.7))
    d = ImageDraw.Draw(img)
    if n > 1:
        reach = x0
        for i in range(n - 1):
            seg = ease_io((t - times[i + 1] + 0.5) / 0.5)
            reach = max(reach, x0 + step * i + step * seg) if seg > 0 else reach
        layer = blank()
        ImageDraw.Draw(layer).line([(x0, y_line), (reach, y_line)], fill=(*C["muted"], int(200 * env)), width=3)
        comp(img, layer, 0, 0)
    for i, e in enumerate(events):
        a = appear(t, times[i]) * env
        if a <= 0.004:
            continue
        cx = x0 + step * i
        last = i == n - 1 if data.get("highlight", "last") == "last" else e.get("highlight", False)
        col = C["accent"] if last else C["text"]
        r = 11 + 4 * (1 - appear(t, times[i], 0.5))
        layer = blank()
        ImageDraw.Draw(layer).ellipse([cx - r, y_line - r, cx + r, y_line + r], fill=(*col, int(255 * a)), outline=(*C["scrim"], int(255 * a)), width=3)
        comp(img, layer, 0, 0)
        rise = (1 - appear(t, times[i])) * MOT["rise_px"]
        put_text(img, (cx, y_line - 34 + rise), str(e["date"]), "serif", sz["date"], col, a, anchor="ms")
        lines = wrap(e.get("label", ""), "sans", sz["event"], min(2 * half, step * 0.94) if n > 1 else 520)
        for k, ln in enumerate(lines[:3]):
            put_text(img, (cx, y_line + 20 + sz["event"] * (k + 1) * 1.15 + rise), ln, "sans", sz["event"], C["muted"] if not last else C["text"], a, anchor="ms")
    del d
    return img


def wrap(s, key, px, width):
    out, cur = [], ""
    for w in s.split():
        trial = (cur + " " + w).strip()
        if cur and text_w(trial, key, px) > width:
            out.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        out.append(cur)
    return out


# ---------- ocean-map ----------
R_EARTH = 6378137.0


def merc(lat, lon):
    x = math.radians(lon) * R_EARTH
    y = math.log(math.tan(math.pi / 4 + math.radians(max(-85, min(85, lat))) / 2)) * R_EARTH
    return x, y


def nice_km(target):
    for v in (5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000):
        if v >= target:
            return v
    return 5000


def land_polygons(bbox):
    """Land polygons (lists of (lon, lat)) inside bbox=(lon0, lat0, lon1, lat1) from Natural Earth via cartopy. [] if unavailable."""
    try:
        import cartopy.io.shapereader as shpreader
        from shapely.geometry import box
        path = shpreader.natural_earth(resolution="50m", category="physical", name="land")
        region = box(*bbox)
        polys = []
        for g in shpreader.Reader(path).geometries():
            if not g.intersects(region):
                continue
            for p in (g.geoms if hasattr(g, "geoms") else [g]):
                if p.intersects(region):
                    polys.append(list(p.exterior.coords))
        return polys
    except Exception as e:  # noqa: BLE001
        print("WARN: no land data for ocean-map:", type(e).__name__, str(e)[:100], flush=True)
        return []


class MapBase:
    """Static semi-transparent map card (PIL). Mercator around `center`, `span_km` wide."""

    def __init__(self, data, size=(800, 800)):
        self.w, self.h = size
        lat, lon = data["center"]
        self.span_km = float(data.get("span_km", 800))
        cx, cy = merc(lat, lon)
        half = self.span_km * 1000 / math.cos(math.radians(lat)) / 2  # projected metres for span_km of real distance
        self.x0, self.y1, self.m_per_px = cx - half, cy + half * self.h / self.w, 2 * half / self.w
        self.lat = lat
        self.km_per_px = self.m_per_px * math.cos(math.radians(lat)) / 1000
        self.land = data.get("_land")
        self.img = self._draw(data)

    def px(self, lat, lon):
        x, y = merc(lat, lon)
        return (x - self.x0) / self.m_per_px, (self.y1 - y) / self.m_per_px

    def _draw(self, data):
        ss = 2
        im = Image.new("RGBA", (self.w * ss, self.h * ss), (*C["deep"], 150))
        d = ImageDraw.Draw(im)
        # graticule every 5/10/20 degrees
        deg_w = self.span_km / 111.0 / max(0.2, math.cos(math.radians(self.lat)))
        stepg = 20 if deg_w > 60 else 10 if deg_w > 28 else 5 if deg_w > 12 else 2 if deg_w > 5 else 1
        lat_c, lon_c = data["center"]
        for k in range(-30, 31):
            lo = math.floor(lon_c / stepg) * stepg + k * stepg
            a, b = self.px(lat_c - 40, lo), self.px(lat_c + 40, lo)
            d.line([(a[0] * ss, a[1] * ss), (b[0] * ss, b[1] * ss)], fill=(*C["grid"], 70), width=2)
            la = math.floor(lat_c / stepg) * stepg + k * stepg
            if abs(la) < 84:
                a, b = self.px(la, lon_c - 90), self.px(la, lon_c + 90)
                d.line([(a[0] * ss, a[1] * ss), (b[0] * ss, b[1] * ss)], fill=(*C["grid"], 70), width=2)
        for poly in (self.land or []):
            pts = [(self.px(la, lo)[0] * ss, self.px(la, lo)[1] * ss) for lo, la in poly]
            d.polygon(pts, fill=(*C["land"], 175), outline=(*C["text"], 220))
        im = im.resize((self.w, self.h), Image.LANCZOS)
        mask = Image.new("L", (self.w, self.h), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, self.w - 1, self.h - 1], radius=26, fill=255)
        out = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        out.paste(im, (0, 0), mask)
        ImageDraw.Draw(out).rounded_rectangle([0, 0, self.w - 1, self.h - 1], radius=26, outline=(*C["text"], 90), width=2)
        return out


def ocean_map(t, D, data, ctx):
    sz = sizes(data, ("title", "label", "note"))
    env = envelope(t, D)
    img = scrim_frame("right", env)
    base = ctx.setdefault("_maps", {})
    key = json.dumps({k: v for k, v in data.items() if k != "size"}, sort_keys=True, ensure_ascii=False)
    if key not in base:
        lat, lon = data["center"]
        span_deg = float(data.get("span_km", 800)) / 111.0
        d2 = dict(data, _land=land_polygons((lon - span_deg, lat - span_deg, lon + span_deg, lat + span_deg)))
        base[key] = MapBase(d2)
    mb = base[key]
    pw, ph = mb.w, mb.h
    px0 = W - MX - pw
    py0 = (H - ph) // 2 + 20
    a = appear(t, 0.1, 0.9) * env
    zoom = 1.0 + 0.04 * clamp01(t / max(D, 0.1))
    card = mb.img
    if zoom > 1.0005:
        cw, chh = int(pw / zoom), int(ph / zoom)
        card = card.crop(((pw - cw) // 2, (ph - chh) // 2, (pw - cw) // 2 + cw, (ph - chh) // 2 + chh)).resize((pw, ph), Image.BILINEAR)
    card = card.copy()
    card.putalpha(card.getchannel("A").point(lambda v: int(v * a)))
    scale_in = 0.97 + 0.03 * appear(t, 0.1, 0.9)
    if scale_in < 0.9995:
        card = card.resize((int(pw * scale_in), int(ph * scale_in)), Image.BILINEAR)
    cx, cy = px0 + pw // 2, py0 + ph // 2
    comp(img, card, int(cx - card.width / 2), int(cy - card.height / 2))
    pts = ([data["marker"]] if data.get("marker") else []) + list(data.get("points", []))
    for i, m in enumerate(pts):
        mx, my = mb.px(m["lat"], m["lon"])
        mx, my = (mx - pw / 2) * zoom + pw / 2 + px0, (my - ph / 2) * zoom + ph / 2 + py0
        if not (px0 + 14 < mx < px0 + pw - 14 and py0 + 14 < my < py0 + ph - 14):
            continue  # outside the card
        ma = appear(t, 0.8 + 0.25 * i) * env
        main = i == 0 and bool(data.get("marker"))
        col = C["alert"] if main else C["accent"]
        pulse = (t * 0.9) % 1.0
        layer = blank()
        ld = ImageDraw.Draw(layer)
        if main:
            rr = 12 + 46 * pulse
            ld.ellipse([mx - rr, my - rr, mx + rr, my + rr], outline=(*col, int(200 * (1 - pulse) * ma)), width=4)
        ld.ellipse([mx - 9, my - 9, mx + 9, my + 9], fill=(*col, int(255 * ma)), outline=(*C["text"], int(255 * ma)), width=3)
        comp(img, layer, 0, 0)
        if m.get("label"):
            if mx + 30 + text_w(m["label"], "sans_bold", sz["label"]) > px0 + pw - 10:
                put_text(img, (mx - 20, my - 16), m["label"], "sans_bold", sz["label"], C["text"], ma, anchor="rs")
            else:
                put_text(img, (mx + 20, my - 16), m["label"], "sans_bold", sz["label"], C["text"], ma)
    if data.get("title"):
        put_text(img, (px0 + 4, py0 - 26 + (1 - appear(t, 0.0)) * MOT["rise_px"]), data["title"], "serif", sz["title"], C["text"], appear(t, 0.0) * env)
    # scale bar
    km = nice_km(mb.km_per_px * pw * 0.22) if not data.get("scale_km") else data["scale_km"]
    bar = km / mb.km_per_px * zoom
    sx, sy = px0 + 28, py0 + ph - 34
    sa = appear(t, 0.5) * env
    layer = blank()
    ld = ImageDraw.Draw(layer)
    for dx in (0, bar):
        ld.line([(sx + dx, sy - 9), (sx + dx, sy + 9)], fill=(*C["text"], int(255 * sa)), width=3)
    ld.line([(sx, sy), (sx + bar, sy)], fill=(*C["text"], int(255 * sa)), width=3)
    comp(img, layer, 0, 0)
    put_text(img, (sx + bar + 14, sy + 9), f"{fmt_num(km)}{NBSP}км", "sans_bold", 26, C["text"], sa)
    if data.get("note"):
        put_text(img, (px0 + pw, py0 + ph + 44), data["note"], "sans", sz["note"], C["muted"], appear(t, 0.6) * env, anchor="rs")
    return img


TEMPLATES = {"ocean-fact": fact, "ocean-timeline": timeline, "ocean-map": ocean_map}


def render(overlay, out_dir, fps=FPS):
    """Write RGBA frames 0000.png.. for the overlay window; returns the frame count."""
    name = overlay["template"]
    if name not in TEMPLATES:
        raise KeyError(f"unknown overlay template {name!r} (have: {', '.join(TEMPLATES)})")
    os.makedirs(out_dir, exist_ok=True)
    D = overlay["end"] - overlay["start"]
    n = max(1, int(round(D * fps)))
    ctx = {"start": overlay["start"]}
    for i in range(n):
        TEMPLATES[name](i / fps, D, overlay.get("data") or {}, ctx).save(os.path.join(out_dir, f"{i:04d}.png"), compress_level=1)
    return n


def main(argv):
    if len(argv) < 4 or argv[0] != "preview":
        print(__doc__)
        return 2
    data = json.load(open(argv[2], encoding="utf-8"))
    secs = float(argv[4]) if len(argv) > 4 else 6.0
    n = render({"template": argv[1], "data": data, "start": 0.0, "end": secs}, argv[3])
    print(n, "frames ->", argv[3])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
