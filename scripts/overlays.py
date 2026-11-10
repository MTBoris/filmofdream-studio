"""Animated overlay templates drawn over the ocean video (transparent PNG frames).

    python scripts/overlays.py preview TEMPLATE DATA.json OUT_DIR [SECONDS]    # frames for a quick look

Templates: ocean-fact, ocean-coords, ocean-map, ocean-timeline, ocean-compare, lower-third, title-card.
Style (exact palette, fonts, margins) comes from design/tokens.json.
Each template is a function draw(t, D, data, ctx) -> RGBA Image (1920x1080); t = seconds since the overlay started,
D = overlay length. A dark scrim under the text, a smooth fade/rise in and fade out, number counters.

Text sizes: data["size"] overrides the token sizes - either an object {"value": 100, "label": 80, "note": 100}
or a list in the template's field order:
  ocean-fact: value, label, note | ocean-coords: coords, label, note | ocean-timeline: date, event (event >= 34 px)
  ocean-map: title, label, note | ocean-compare: label, dims, note | lower-third: text, sub | title-card: card, subtitle
"""
import json
import math
import os
import re
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOK = json.load(open(os.path.join(ROOT, "design", "tokens.json"), encoding="utf-8"))
W, H, FPS = TOK["canvas"]["w"], TOK["canvas"]["h"], TOK["canvas"]["fps"]
MX, MY = TOK["margin"]["x"], TOK["margin"]["y"]
MOT = TOK["motion"]
MINS = TOK.get("min_size", {})
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
    """Pixel sizes for the template's text fields: token defaults, overridden by data["size"] (dict, list or one number).
    A few fields never go below a readable minimum (design/tokens.json min_size, e.g. timeline event text >= 34 px)."""
    out = {n: TOK["size"][n] for n in names}
    sz = data.get("size")
    if isinstance(sz, dict):
        out.update({k: v for k, v in sz.items() if k in out})
    elif isinstance(sz, (list, tuple)):
        out.update(dict(zip(names, sz)))
    elif isinstance(sz, (int, float)):
        out[names[0]] = sz
    return {k: max(v, MINS.get(k, 0)) for k, v in out.items()}


def parse_value(v):
    """'400+' -> ('', 400, '+', 0); '≈26' -> ('≈', 26, '', 0); '2,5 млн' -> ('', 2.5, ' млн', 1); numbers pass through."""
    if isinstance(v, (int, float)):
        return "", v, "", 0 if float(v).is_integer() else 1
    m = re.match(r"^\s*([^\d]*?)(\d[\d\u00a0 ]*(?:[.,]\d+)?)(.*)$", str(v), flags=re.S)
    if not m:
        return str(v), None, "", 0
    num = m.group(2).replace("\u00a0", "").replace(" ", "")
    dec = len(re.split(r"[.,]", num)[1]) if re.search(r"[.,]", num) else 0
    return m.group(1), float(num.replace(",", ".")), m.group(3), dec


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


_glyphs = {}
SUBST = {"\u2032": ["\u2019", "'"], "\u2033": ["\u201d", '"'], "\u2212": ["-"], "\u2248": ["~"]}  # prime, double prime, minus, almost equal


def has_glyph(fnt, ch):
    """True if the font really has the character (a missing one renders as the same box as an unassigned code point)."""
    k = (id(fnt), ch)
    if k not in _glyphs:
        notdef = bytes(fnt.getmask("\U0010ffff"))
        _glyphs[k] = ch.isspace() or bytes(fnt.getmask(ch)) != notdef
    return _glyphs[k]


def fit_glyphs(s, fnt):
    """Replace characters the font lacks (e.g. the minute sign in PT Serif) with the nearest one it has."""
    out = []
    for ch in s:
        if ord(ch) > 0x2000 and not has_glyph(fnt, ch):
            ch = next((c for c in SUBST.get(ch, []) if has_glyph(fnt, c)), ch)
        out.append(ch)
    return "".join(out)


def put_text(img, xy, s, key, px, color, alpha=1.0, anchor="ls", shadow=True):
    if alpha <= 0.004 or not s:
        return
    fnt = font(key, px)
    s = fit_glyphs(s, fnt)
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


def soft_panel(img, box, alpha, radius=26, blur=24):
    """Dark, softly blurred rounded panel under text (local darkening for legibility)."""
    if alpha <= 0.004:
        return
    x0, y0, x1, y1 = [int(v) for v in box]
    pad = blur * 3
    layer = Image.new("RGBA", (x1 - x0 + 2 * pad, y1 - y0 + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle([pad, pad, pad + x1 - x0, pad + y1 - y0], radius=radius, fill=(*C["scrim"], int(215 * alpha)))
    comp(img, layer.filter(ImageFilter.GaussianBlur(blur)), x0 - pad, y0 - pad)


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
        a = 0.88 * np.clip((y - 0.38) / 0.62, 0, 1) ** 1.1 + 0 * x
    elif kind == "veil":
        r = np.sqrt(((x - 0.5) * 1.6) ** 2 + (y - 0.5) ** 2)
        a = 0.50 + 0.30 * np.clip(r / 0.9, 0, 1)
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
    raw = data["value"]
    pre, suf, dec = data.get("prefix", ""), data.get("suffix", ""), int(data.get("decimals", 0))
    if isinstance(raw, list):
        values = raw
    else:
        p2, num, s2, d2 = parse_value(raw)
        pre, suf, dec = p2 + pre, s2 + suf, max(dec, d2)
        values = [num] if num is not None else []
    cnt = clamp01((t - 0.15) / MOT["counter_s"])
    shown = [v * ease_out(cnt) for v in values]
    vtxt = pre + "–".join(fmt_num(v, dec) for v in shown) + suf if values else pre
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


# ---------- ocean-coords ----------
def coords(t, D, data, ctx):
    sz = sizes(data, ("coords", "label", "note"))
    env = envelope(t, D)
    img = scrim_frame("bottom-left", env)
    rise = MOT["rise_px"]
    lines = [data[k] for k in ("lat", "lon") if data.get(k)]
    x, base = MX, H - MY
    if data.get("note"):
        a = appear(t, 0.9) * env
        put_text(img, (x, base + (1 - appear(t, 0.9)) * rise), data["note"], "sans", sz["note"], C["muted"], a)
        base -= sz["note"] + 34
    lh = int(sz["coords"] * 1.18)
    x_text = x + 78
    for i, ln in enumerate(reversed(lines)):  # last line sits on the baseline
        k = len(lines) - 1 - i
        t0 = 0.35 + 0.45 * k
        shown = int(len(ln) * ease_io((t - t0) / 0.9) + 0.5)  # typed in, character by character
        put_text(img, (x_text, base - i * lh), ln[:shown], "serif", sz["coords"], C["text"], env)
    top = base - (len(lines) - 1) * lh
    cy = (top + base) / 2 - cap_h("serif", sz["coords"]) / 2
    pa = appear(t, 0.1) * env
    pulse = (t * 0.9) % 1.0
    layer = blank()
    ld = ImageDraw.Draw(layer)
    cx = x + 26
    rr = 14 + 40 * pulse
    ld.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=(*C["accent"], int(200 * (1 - pulse) * pa)), width=4)
    ld.ellipse([cx - 11, cy - 11, cx + 11, cy + 11], fill=(*C["accent"], int(255 * pa)), outline=(*C["text"], int(255 * pa)), width=3)
    comp(img, layer, 0, 0)
    if data.get("label"):
        yl = top - cap_h("serif", sz["coords"]) - 30 + (1 - appear(t, 0.0)) * rise
        put_text(img, (x_text, yl), data["label"].upper(), "sans_bold", sz["label"], C["accent"], appear(t, 0.0) * env)
    return img


# ---------- ocean-timeline ----------
def timeline(t, D, data, ctx):
    sz = sizes(data, ("date", "event"))
    events = data["events"]
    n = len(events)
    env = envelope(t, D)
    img = scrim_frame("bottom", env)
    half = 190  # half of the widest label, keeps the outer labels inside the margins
    left, right = MX + half, W - MX - half
    step = min(460, (right - left) / max(1, n - 1)) if n > 1 else 0
    x0 = (left + right) / 2 - step * (n - 1) / 2
    y_line = H - MY - 215
    times = []
    for i, e in enumerate(events):
        times.append(e["t"] - ctx.get("start", 0) if e.get("t") is not None else 0.5 + i * (MOT["stagger_s"] + 0.7))
    if n > 1:
        reach = x0
        for i in range(n - 1):
            seg = ease_io((t - times[i + 1] + 0.5) / 0.5)
            reach = max(reach, x0 + step * i + step * seg) if seg > 0 else reach
        layer = blank()
        ImageDraw.Draw(layer).line([(x0, y_line), (reach, y_line)], fill=(*C["muted"], int(220 * env)), width=3)
        comp(img, layer, 0, 0)
    for i, e in enumerate(events):
        a = appear(t, times[i]) * env
        if a <= 0.004:
            continue
        cx = x0 + step * i
        last = i == n - 1 if data.get("highlight", "last") == "last" else e.get("highlight", False)
        col = C["accent"] if last else C["text"]
        lines = wrap(e.get("label", ""), "sans", sz["event"], min(2 * half, step * 0.94) if n > 1 else 560)[:3]
        rise = (1 - appear(t, times[i])) * MOT["rise_px"]
        lw = max([text_w(str(e["date"]), "serif", sz["date"])] + [text_w(ln, "sans", sz["event"]) for ln in lines]) + 70
        top = y_line - 34 - cap_h("serif", sz["date"]) - 26
        bottom = y_line + 20 + sz["event"] * 1.25 * len(lines) + 28
        soft_panel(img, (cx - lw / 2, top + rise, cx + lw / 2, bottom + rise), a * 0.9)  # local darkening under the text
        r = 11 + 4 * (1 - appear(t, times[i], 0.5))
        layer = blank()
        ImageDraw.Draw(layer).ellipse([cx - r, y_line - r, cx + r, y_line + r], fill=(*col, int(255 * a)), outline=(*C["scrim"], int(255 * a)), width=3)
        comp(img, layer, 0, 0)
        put_text(img, (cx, y_line - 34 + rise), str(e["date"]), "serif", sz["date"], col, a, anchor="ms")
        for k, ln in enumerate(lines):
            put_text(img, (cx, y_line + 20 + sz["event"] * (k + 1) * 1.2 + rise), ln, "sans", sz["event"], C["text"], a, anchor="ms")
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
        im = Image.new("RGBA", (self.w * ss, self.h * ss), (*C["panel"], 170))
        d = ImageDraw.Draw(im)
        # graticule every 5/10/20 degrees
        deg_w = self.span_km / 111.0 / max(0.2, math.cos(math.radians(self.lat)))
        stepg = 20 if deg_w > 60 else 10 if deg_w > 28 else 5 if deg_w > 12 else 2 if deg_w > 5 else 1
        lat_c, lon_c = data["center"]
        for k in range(-30, 31):
            lo = math.floor(lon_c / stepg) * stepg + k * stepg
            a, b = self.px(lat_c - 40, lo), self.px(lat_c + 40, lo)
            d.line([(a[0] * ss, a[1] * ss), (b[0] * ss, b[1] * ss)], fill=(*C["grid"], 55), width=2)
            la = math.floor(lat_c / stepg) * stepg + k * stepg
            if abs(la) < 84:
                a, b = self.px(la, lon_c - 90), self.px(la, lon_c + 90)
                d.line([(a[0] * ss, a[1] * ss), (b[0] * ss, b[1] * ss)], fill=(*C["grid"], 55), width=2)
        for poly in (self.land or []):
            pts = [(self.px(la, lo)[0] * ss, self.px(la, lo)[1] * ss) for lo, la in poly]
            d.polygon(pts, fill=(*C["land"], 190), outline=(*C["text"], 230))
        im = im.resize((self.w, self.h), Image.LANCZOS)
        mask = Image.new("L", (self.w, self.h), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, self.w - 1, self.h - 1], radius=26, fill=255)
        out = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        out.paste(im, (0, 0), mask)
        ImageDraw.Draw(out).rounded_rectangle([0, 0, self.w - 1, self.h - 1], radius=26, outline=(*C["text"], 90), width=2)
        return out


def label_box(x, y, dx, dy, anc, w, fh):
    bx0 = {"ls": x + dx, "rs": x + dx - w, "ms": x + dx - w / 2}[anc]
    return (bx0, y + dy - fh, bx0 + w, y + dy + fh * 0.3)


def place_labels(items, card, fh):
    """items: [(x, y, label, width)] in card coordinates. Returns [(dx, dy, anchor)] (None for an empty label): the first position
    (right/left of the dot, then centred below/above) that stays inside `card` and covers no other label or dot."""
    x0, y0, x1, y1 = card
    dots = [(x - 14, y - 14, x + 14, y + 14) for x, y, _, _ in items]
    labels, out = [], []
    # candidate offsets from the dot, nearest first (right-up is preferred on ties)
    options = sorted([(dx, dy, "ls" if dx > 0 else "rs" if dx < 0 else "ms") for dx in (20, -20, 0, 150, -150, 260, -260)
                      for dy in (-16, 38, -34, 62, -70, 100, -100)], key=lambda o: (math.hypot(o[0] * 0.6, o[1]), -o[0]))

    def clash(box, others):
        return any(not (box[2] < o[0] - 4 or box[0] > o[2] + 4 or box[3] < o[1] - 4 or box[1] > o[3] + 4) for o in others)

    for i, (x, y, label, w) in enumerate(items):
        if not label:
            out.append(None)
            continue
        others = labels + [d for j, d in enumerate(dots) if j != i]
        pick = None
        for dx, dy, anc in options:
            box = label_box(x, y, dx, dy, anc, w, fh)
            if box[0] >= x0 and box[2] <= x1 and box[1] >= y0 and box[3] <= y1 and not clash(box, others):
                pick = (dx, dy, anc)
                break
        if pick is None:
            pick = options[0]
        labels.append(label_box(x, y, *pick[:2], pick[2], w, fh))
        out.append(pick)
    return out


def ocean_map(t, D, data, ctx):
    sz = sizes(data, ("title", "label", "note"))
    if not (isinstance(data.get("size"), dict) and "label" in data["size"]) and not isinstance(data.get("size"), (list, tuple)):
        sz["label"] = min(sz["label"], 36)  # pin labels sit on a small card: smaller than the generic label size
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
    offsets = ctx.setdefault("_label_offsets", {}).get(key)
    if offsets is None:  # label positions are decided once (zoom 1) so that they never jump during the animation
        items = []
        for m in pts:
            x1, y1 = mb.px(m["lat"], m["lon"])
            items.append((x1 + px0, y1 + py0, m.get("label", ""), text_w(m.get("label", ""), "sans_bold", sz["label"])))
        offsets = ctx["_label_offsets"][key] = place_labels(items, (px0 + 10, py0 + 10, px0 + pw - 10, py0 + ph - 10), sz["label"])
    for i, m in enumerate(pts):
        mx, my = mb.px(m["lat"], m["lon"])
        mx, my = (mx - pw / 2) * zoom + pw / 2 + px0, (my - ph / 2) * zoom + ph / 2 + py0
        if not (px0 + 14 < mx < px0 + pw - 14 and py0 + 14 < my < py0 + ph - 14):
            continue  # outside the card
        ma = appear(t, 0.8 + 0.25 * i) * env
        main = i == 0 and bool(data.get("marker"))
        col = C["accent"] if main else C["text"]
        pulse = (t * 0.9) % 1.0
        layer = blank()
        ld = ImageDraw.Draw(layer)
        if main:
            rr = 12 + 46 * pulse
            ld.ellipse([mx - rr, my - rr, mx + rr, my + rr], outline=(*col, int(200 * (1 - pulse) * ma)), width=4)
        ld.ellipse([mx - 9, my - 9, mx + 9, my + 9], fill=(*col, int(255 * ma)), outline=(*C["text"], int(255 * ma)), width=3)
        comp(img, layer, 0, 0)
        if m.get("label") and offsets[i]:
            dx, dy, anchor = offsets[i]
            put_text(img, (mx + dx, my + dy), m["label"], "sans_bold", sz["label"], C["text"], ma, anchor=anchor)
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


# ---------- ocean-compare ----------
def compare(t, D, data, ctx):
    """Two shapes drawn to the same scale (e.g. pumice raft 463 x 55 km vs island 25 x 5 km)."""
    sz = sizes(data, ("label", "dims", "note"))
    env = envelope(t, D)
    img = scrim_frame("bottom", env)
    a_, b_ = data["a"], data["b"]
    unit = data.get("unit", a_.get("unit", ""))
    max_w = float(data.get("max_px", 1500))
    pxk = max_w / max(a_["w"], b_["w"])
    rise = MOT["rise_px"]
    bottom = H - MY
    if data.get("note"):
        put_text(img, (MX, bottom + (1 - appear(t, 1.2)) * rise), data["note"], "sans", sz["note"], C["muted"], appear(t, 1.2) * env)
        bottom -= sz["note"] + 34
    blocks = [(b_, 0.9, C["text"]), (a_, 0.2, C["accent"])]  # drawn bottom-up: b at the bottom, a above it
    for blk, t0, col in blocks:
        rw, rh = blk["w"] * pxk, max(10.0, blk["h"] * pxk)
        grow = ease_out((t - t0) / 1.1)
        al = appear(t, t0, 0.5) * env
        top = bottom - rh
        layer = blank()
        ld = ImageDraw.Draw(layer)
        ld.rectangle([MX, top, MX + rw * grow, bottom], fill=(*col, int(110 * al)), outline=(*col, int(255 * al)), width=3)
        comp(img, layer, 0, 0)
        dims = f"{fmt_num(blk['w'])} × {fmt_num(blk['h'])}{NBSP}{blk.get('unit', unit)}".strip()
        yb = top - 16 + (1 - appear(t, t0)) * rise
        put_text(img, (MX, yb), blk["label"], "sans_bold", sz["label"], col, al)
        put_text(img, (MX + text_w(blk["label"], "sans_bold", sz["label"]) + 28, yb), dims, "serif", sz["dims"], C["text"], al)
        bottom = top - 16 - sz["label"] - 34
    return img


# ---------- lower-third ----------
def lower_third(t, D, data, ctx):
    sz = sizes(data, ("text", "sub"))
    env = envelope(t, D)
    img = blank()
    a = appear(t, 0.0) * env
    slide = (1 - appear(t, 0.0)) * 40
    lines = wrap(data["text"], "sans_bold", sz["text"], 1300)[:2]
    sub = data.get("sub")
    h = sz["text"] * 1.25 * len(lines) + (sz["sub"] * 1.4 if sub else 0)
    wmax = max([text_w(ln, "sans_bold", sz["text"]) for ln in lines] + ([text_w(sub, "sans", sz["sub"])] if sub else [0]))
    bottom = H - MY
    top = bottom - h
    x = MX - slide
    soft_panel(img, (x - 26, top - 24, x + 36 + wmax + 40, bottom + 22), a)
    layer = blank()
    ImageDraw.Draw(layer).rectangle([x, top + 4, x + 6, bottom - 4], fill=(*C["accent"], int(255 * a)))
    comp(img, layer, 0, 0)
    for k, ln in enumerate(lines):
        put_text(img, (x + 28, top + sz["text"] * 1.12 * (k + 1) + k * sz["text"] * 0.13), ln, "sans_bold", sz["text"], C["text"], a)
    if sub:
        put_text(img, (x + 28, bottom - 6), sub, "sans", sz["sub"], C["muted"], appear(t, 0.2) * env)
    return img


# ---------- title-card ----------
def title_card(t, D, data, ctx):
    sz = sizes(data, ("card", "subtitle"))
    env = envelope(t, D)
    img = scrim_frame("veil", env)
    lines = wrap(data["title"], "serif", sz["card"], W - 2 * MX - 220)[:3]
    lh = sz["card"] * 1.15
    sub = data.get("subtitle")
    block = lh * len(lines) + (sz["subtitle"] * 1.6 + 30 if sub else 0)
    top = (H - block) / 2
    rise = (1 - appear(t, 0.15)) * MOT["rise_px"]
    # accent rule grows from the centre
    rw = 160 * ease_out((t - 0.0) / 0.9)
    layer = blank()
    ImageDraw.Draw(layer).line([(W / 2 - rw / 2, top - 44), (W / 2 + rw / 2, top - 44)], fill=(*C["accent"], int(255 * env)), width=5)
    comp(img, layer, 0, 0)
    for k, ln in enumerate(lines):
        put_text(img, (W / 2, top + lh * (k + 1) - 14 + rise), ln, "serif", sz["card"], C["text"], appear(t, 0.15) * env, anchor="ms")
    if sub:
        put_text(img, (W / 2, top + lh * len(lines) + sz["subtitle"] * 1.05 + 34 + rise), sub, "sans", sz["subtitle"], C["muted"], appear(t, 0.5) * env, anchor="ms")
    return img


TEMPLATES = {"ocean-fact": fact, "ocean-coords": coords, "ocean-timeline": timeline, "ocean-map": ocean_map,
             "ocean-compare": compare, "lower-third": lower_third, "title-card": title_card}


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
