"""Thumbnail made by code (1280x720): a frame from a stock clip + a white bird silhouette on a dry branch + a big title.

    python scripts/thumbnail.py SPEC.json SOURCE OUT.jpg

SOURCE is a video (the frame is taken at spec["t"] seconds) or an image. SPEC (episodes/NNN/thumbnail.json):
    {"shot": "red_water-1", "t": 4.0, "text": ["ПТИЦЫ", "ИЗ КАМНЯ?"], "bird": "left"}
"shot" says which stock shot of the build gives the background (the workflow passes stock/<shot>.mp4).
Fonts and palette come from design/tokens.json. No people, no logos: the picture is a stock frame plus shapes drawn here.
"""
import json
import math
import os
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOK = json.load(open(os.path.join(ROOT, "design", "tokens.json"), encoding="utf-8"))
W, H = 1280, 720


def rgb(hexstr):
    h = hexstr.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


C = {k: rgb(v) for k, v in TOK["color"].items()}


def font(key, px):
    return ImageFont.truetype(os.path.join(ROOT, TOK["font"][key]), int(px))


def frame(source, t):
    if source.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
        return Image.open(source).convert("RGB")
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "f.png")
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{t:.2f}", "-i", source, "-frames:v", "1", p], check=True)
        return Image.open(p).convert("RGB")


def cover(im, w=W, h=H):
    s = max(w / im.width, h / im.height)
    im = im.resize((math.ceil(im.width * s), math.ceil(im.height * s)), Image.LANCZOS)
    x, y = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((x, y, x + w, y + h))


def grade(im):
    """Warmer, more saturated, a little darker so the white bird and the title stand out."""
    im = ImageEnhance.Color(im).enhance(1.25)
    im = ImageEnhance.Contrast(im).enhance(1.08)
    warm = Image.new("RGB", im.size, (190, 70, 20))
    im = Image.blend(im, warm, 0.12)
    return ImageEnhance.Brightness(im).enhance(0.92)


def gradient(side="right", strength=0.78):
    """Dark gradient (palette 'deep') under the title side."""
    g = Image.new("L", (W, 1))
    for x in range(W):
        f = x / (W - 1) if side == "right" else 1 - x / (W - 1)
        g.putpixel((x, 0), int(255 * strength * max(0.0, min(1.0, (f - 0.25) / 0.6)) ** 1.3))
    g = g.resize((W, H))
    dark = Image.new("RGBA", (W, H), (*C["deep"], 0))
    dark.putalpha(g)
    return dark


def vignette(strength=0.45):
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).ellipse([-W * 0.15, -H * 0.25, W * 1.15, H * 1.25], fill=255)
    m = m.filter(ImageFilter.GaussianBlur(120))
    a = m.point(lambda v: int((255 - v) * strength))
    v = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    v.putalpha(a)
    return v


def bezier(p0, p1, p2, p3, n=24):
    out = []
    for i in range(n + 1):
        t = i / n
        a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t ** 2, t ** 3
        out.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return out


def bird_layer(cx, cy, scale, color=(250, 248, 242)):
    """A perched bird (side view, facing right) on a dry branch. (cx, cy) = where the feet hold the branch."""
    ss = 4
    L = Image.new("RGBA", (W * ss, H * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(L)
    f = scale * ss

    def P(x, y):
        return (cx * ss + x * f, cy * ss + y * f)

    def B(x, y):  # the bird sits 20 units lower than the drawing grid, so the feet are short and grip the branch
        return P(x, y + 20)

    col = (*color, 255)
    # dry branch: a long tapering limb from the left edge with two thin twigs
    limb_top = bezier(P(-260, 40), P(-120, 10), P(40, 4), P(190, -30))
    limb_bot = bezier(P(195, -24), P(40, 16), P(-120, 26), P(-260, 66))
    d.polygon(limb_top + limb_bot, fill=col)
    for a0, a1, a2, a3, w in (((-150, 18), (-170, -30), (-200, -60), (-215, -95), 5), ((110, -6), (135, -30), (150, -60), (146, -92), 4)):
        d.line(bezier(P(*a0), P(*a1), P(*a2), P(*a3)), fill=col, width=int(w * f), joint="curve")
    # feet
    for fx in (-6, 10):
        d.line([B(fx, -40), B(fx - 2, -12)], fill=col, width=int(4 * f))
        d.line([B(fx - 4, -12), B(fx + 9, -8)], fill=col, width=int(3 * f))
    # tail (long, pointing down-left)
    d.polygon([B(-38, -60), B(-118, 10), B(-128, 4), B(-104, -14), B(-50, -82)], fill=col)
    # body
    body = bezier(B(-50, -80), B(-40, -138), B(40, -150), B(56, -104), 30) + bezier(B(56, -104), B(66, -66), B(22, -30), B(-12, -34), 30) \
        + bezier(B(-12, -34), B(-40, -38), B(-56, -54), B(-50, -80), 20)
    d.polygon(body, fill=col)
    # head and beak
    hx, hy, r = 48, -138, 27
    d.ellipse([B(hx - r, hy - r), B(hx + r, hy + r)], fill=col)
    d.polygon([B(hx + 20, hy - 10), B(hx + 52, hy + 2), B(hx + 20, hy + 9)], fill=col)
    # folded wing: a slightly darker shape so the silhouette reads as a bird, not a blob
    wing = bezier(B(34, -112), B(10, -130), B(-40, -112), B(-96, -44), 30) + bezier(B(-96, -44), B(-50, -50), B(10, -60), B(34, -112), 30)
    d.polygon(wing, fill=(226, 219, 207, 255))
    # eye
    er = 4.2
    d.ellipse([B(hx + 8 - er, hy - 6 - er), B(hx + 8 + er, hy - 6 + er)], fill=(*C["deep"], 255))
    return L.resize((W, H), Image.LANCZOS)


def glow(layer, radius=18, alpha=0.55, color=(0, 0, 0)):
    a = layer.getchannel("A").filter(ImageFilter.GaussianBlur(radius)).point(lambda v: int(v * alpha))
    g = Image.new("RGBA", layer.size, (*color, 0))
    g.putalpha(a)
    return g


def title(img, lines, side="right"):
    """Big title, PT Serif Bold, each line fitted to the column width; the last line in the accent colour."""
    col_w = 600
    x1 = W - 56 if side == "right" else 56 + col_w
    sizes = []
    for s in lines:
        px = 170
        while px > 60 and font("serif", px).getlength(s) > col_w:
            px -= 4
        sizes.append(px)
    gap = 6
    total = sum(sizes) + gap * (len(lines) - 1)
    y = (H - total) // 2 + 10
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for i, (s, px) in enumerate(zip(lines, sizes)):
        fill = C["accent"] if i == len(lines) - 1 else C["text"]
        y += px
        d.text((x1, y), s, font=font("serif", px), fill=(*fill, 255), anchor="rs", stroke_width=max(2, px // 40), stroke_fill=(*C["deep"], 255))
        y += gap
    img.alpha_composite(glow(layer, 14, 0.85))
    img.alpha_composite(layer)


def make(spec, source, out):
    bg = grade(cover(frame(source, float(spec.get("t", 2.0)))))
    img = bg.convert("RGBA")
    side = "left" if spec.get("bird", "left") == "right" else "right"   # the title goes opposite the bird
    img.alpha_composite(vignette())
    img.alpha_composite(gradient(side))
    if spec.get("bird", "left"):
        bx = 300 if spec.get("bird", "left") == "left" else W - 300
        b = bird_layer(bx, 470, float(spec.get("bird_scale", 1.55)))
        img.alpha_composite(glow(b, 22, 0.6))
        img.alpha_composite(b)
    text = spec.get("text") or []
    title(img, text if isinstance(text, list) else [text], side)
    img.convert("RGB").save(out, quality=92)
    print("thumbnail ->", out)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    make(json.load(open(sys.argv[1], encoding="utf-8")), sys.argv[2], sys.argv[3])
