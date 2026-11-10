"""Code-drawn visuals for episode 001 (Sandy Island). Each scene -> list of PNG frames (shown in order).

python scripts/visuals_sandy.py OUTDIR
"""
import os, sys, math, random
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import patches, patheffects as pe
import cartopy.crs as ccrs
import cartopy.feature as cfeature

W, H, DPI = 19.2, 10.8, 100  # 1920x1080
PARCH, INK, OCEAN, OCEAN2, RED, GOLD, WHITE = "#E9D7AE", "#3B2A1A", "#0B1E33", "#123456", "#C8102E", "#E2B55A", "#F4F1EA"
SANDY = (159.93, -19.22)        # lon, lat (approximate position shown on old charts)
CHESTERFIELD = (158.3, -19.5)
BAMPTON = (158.6, -19.1)
NOUMEA = (166.45, -22.27)
HAVRE = (-178.95, -31.1)
plt.rcParams["font.family"] = "DejaVu Sans"
SERIF = "DejaVu Serif"
random.seed(7); np.random.seed(7)
OUT = sys.argv[1] if len(sys.argv) > 1 else "frames"
os.makedirs(OUT, exist_ok=True)
FRAMES = {}


def save(fig, scene):
    FRAMES.setdefault(scene, [])
    path = os.path.join(OUT, f"{scene}_{len(FRAMES[scene]):02d}.png")
    fig.savefig(path, dpi=DPI, facecolor=fig.get_facecolor())
    plt.close(fig)
    FRAMES[scene].append(path)


def canvas(bg=OCEAN):
    fig = plt.figure(figsize=(W, H), dpi=DPI)
    fig.patch.set_facecolor(bg)
    return fig


def paper_texture(ax, alpha=0.18):
    noise = np.random.rand(27, 48) * 0.6 + np.random.rand(27, 48).cumsum(axis=1) % 1 * 0.4
    ax.imshow(noise, extent=[0, 1, 0, 1], transform=ax.transAxes, cmap="copper", alpha=alpha * 0.7, zorder=0.5,
              aspect="auto", interpolation="bicubic")


def sea(ax, light=False):
    y = np.linspace(0, 1, 540)[:, None]
    grad = (0.35 + 0.4 * y) * np.ones((540, 960))
    ax.imshow(grad, extent=[0, 1, 0, 1], cmap="Blues", vmin=0, vmax=1.6 if not light else 1.1, aspect="auto", zorder=0)
    xs = np.linspace(0, 1, 400)
    for k in range(28):
        yy = 0.03 + k * 0.035
        ax.plot(xs, yy + 0.004 * np.sin(xs * 40 + k * 1.7), color="white", alpha=0.07, lw=1.2, zorder=0.1)


def caption(fig, text, y=0.08, size=54, color=WHITE, box=None):
    t = fig.text(0.5, y, text, ha="center", va="center", fontsize=size, color=color, weight="bold",
                 path_effects=[pe.withStroke(linewidth=6, foreground=PARCH if color == INK else "#000000aa")])
    if box:
        t.set_bbox(dict(facecolor=box, edgecolor="none", pad=18))
    return t


def chart(extent, old=True, title=None, grid=True):
    fig = canvas(PARCH if old else OCEAN)
    if old:
        bg = fig.add_axes([0, 0, 1, 1]); bg.axis("off"); bg.set_xlim(0, 1); bg.set_ylim(0, 1)
        paper_texture(bg)
    ax = fig.add_axes([0, 0, 1, 1], projection=ccrs.PlateCarree(central_longitude=180 if extent[0] > 100 or extent[1] < -100 else 0))
    ax.set_extent(extent, crs=ccrs.PlateCarree())
    small = (extent[1] - extent[0]) < 6  # zoomed-in charts: skip real coastlines (Natural Earth still has a sliver there)
    if old:
        ax.set_facecolor("none"); ax.patch.set_alpha(0)
        if not small:
            ax.add_feature(cfeature.LAND.with_scale("50m"), facecolor="#D9C08A", edgecolor=INK, linewidth=1.2)
            ax.add_feature(cfeature.COASTLINE.with_scale("50m"), edgecolor=INK, linewidth=1.2)
        gl_color = "#7A6040"
    else:
        ax.set_facecolor(OCEAN)
        if not small:
            ax.add_feature(cfeature.LAND.with_scale("50m"), facecolor="#2E4A3A", edgecolor="#9FB7C9", linewidth=0.8)
        gl_color = "#3D5A78"
    if grid:
        gl = ax.gridlines(crs=ccrs.PlateCarree(), draw_labels=False, color=gl_color, linestyle="--", linewidth=0.8, alpha=0.7)
    ax.spines["geo"].set_visible(False)
    if title:
        fig.text(0.04, 0.93, title, fontsize=40, color=INK if old else WHITE, family=SERIF, style="italic")
    return fig, ax


def island_shape(ax, lon, lat, color, edge, ls="-", lw=2.5, alpha=1.0, z=5):
    ax.add_patch(patches.Ellipse((lon, lat), 0.26, 0.07, angle=-30, facecolor=color, edgecolor=edge, linestyle=ls,
                                 linewidth=lw, alpha=alpha, transform=ccrs.PlateCarree(), zorder=z))


def label(ax, lon, lat, text, color=INK, size=26, dx=0.15, dy=0.08, serif=True, weight="normal"):
    ax.text(lon + dx, lat + dy, text, fontsize=size, color=color, transform=ccrs.PlateCarree(),
            family=SERIF if serif else "DejaVu Sans", style="italic" if serif else "normal", weight=weight, zorder=9,
            path_effects=[pe.withStroke(linewidth=4, foreground=PARCH if color == INK else "#00000099")])


def ring(ax, lon, lat, r, color=RED, ls="-", lw=5):
    ax.add_patch(patches.Ellipse((lon, lat), 2.4 * r, 1.3 * r, angle=-25, fill=False, edgecolor=color, linewidth=lw,
                                 linestyle=ls, transform=ccrs.PlateCarree(), zorder=8))


# ---------------- scenes ----------------

def s_hook_map():
    ext = [158.6, 161.3, -20.2, -18.2]
    fig, ax = chart(ext, old=True)
    island_shape(ax, *SANDY, "#D9C08A", INK)
    label(ax, SANDY[0] - 0.25, SANDY[1] + 0.12, "Sandy I.", size=34)
    ring(ax, *SANDY, 0.28)
    caption(fig, "Остров на карте: 25 км", y=0.1, color=INK, size=50)
    save(fig, "hook_map")
    fig, ax = chart(ext, old=False)
    island_shape(ax, *SANDY, "none", RED, ls="--", lw=3)
    ax.plot([158.7, SANDY[0] - 0.05], [-19.9, SANDY[1] - 0.02], color=WHITE, lw=3, ls=":", transform=ccrs.PlateCarree())
    caption(fig, "Под килем — 1400 метров воды", y=0.1)
    save(fig, "hook_map")


def s_coral_sea():
    fig, ax = chart([140, 175, -32, -8], old=False, grid=True)
    ax.plot(*SANDY, marker="o", ms=16, color=RED, transform=ccrs.PlateCarree(), zorder=9)
    label(ax, 145, -25, "АВСТРАЛИЯ", color=WHITE, size=34, serif=False, weight="bold")
    label(ax, 163.5, -23.4, "Новая\nКаледония", color=WHITE, size=26, serif=False)
    label(ax, 150.5, -15.5, "Коралловое море", color="#9FC3E0", size=32)
    label(ax, SANDY[0] + 0.3, SANDY[1] + 0.4, "Сэнди", color=WHITE, size=30, serif=False, weight="bold")
    caption(fig, "Ноябрь 2012 года", y=0.9, size=44)
    save(fig, "coral_sea")
    fig = canvas(OCEAN)
    for i, (yr, txt) in enumerate([("1876", "впервые замечен"), ("2012", "всё ещё на картах")]):
        fig.text(0.28 + i * 0.44, 0.58, yr, ha="center", fontsize=120, color=GOLD, weight="bold")
        fig.text(0.28 + i * 0.44, 0.42, txt, ha="center", fontsize=36, color=WHITE)
    fig.text(0.5, 0.5, "→", ha="center", va="center", fontsize=110, color=WHITE)
    caption(fig, "136 лет", y=0.18, size=70, color=RED)
    save(fig, "coral_sea")


def s_locator():
    fig, ax = chart([155, 168, -24, -16], old=True)
    island_shape(ax, *SANDY, "#D9C08A", INK)
    for (lon, lat), name in [(CHESTERFIELD, "о-ва Честерфилд"), (NOUMEA, "Нумеа")]:
        ax.plot(lon, lat, "o", color=INK, ms=8, transform=ccrs.PlateCarree())
        label(ax, lon, lat, name, size=24)
    label(ax, SANDY[0] + 0.2, SANDY[1] + 0.2, "Sandy Island", size=30)
    ax.annotate("", xy=(SANDY[0] + 0.3, SANDY[1] - 0.2), xytext=(NOUMEA[0] - 0.3, NOUMEA[1] + 0.3),
                arrowprops=dict(arrowstyle="<->", color=RED, lw=3), xycoords=ccrs.PlateCarree()._as_mpl_transform(ax),
                textcoords=ccrs.PlateCarree()._as_mpl_transform(ax))
    caption(fig, "≈ 500 км до Новой Каледонии", y=0.1, color=INK, size=44)
    save(fig, "locator")


def s_black_polygon():
    for step in range(2):
        fig = canvas("#1b2a38")
        ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
        sea(ax)
        t = np.linspace(0, 2 * np.pi, 120)
        r = 1 + 0.07 * np.sin(6 * t)
        ax.fill(0.5 + 0.25 * r * np.cos(t) * np.cos(0.5) - 0.06 * r * np.sin(t) * np.sin(0.5),
                0.5 + 0.25 * r * np.cos(t) * np.sin(0.5) + 0.06 * r * np.sin(t) * np.cos(0.5), color="black")
        if step:
            caption(fig, "На карте остров был. Снимка — не было.", y=0.1, size=46)
        else:
            caption(fig, "2012: чёрное пятно вместо снимка", y=0.9, size=40)
        save(fig, "black_polygon")


def ship(ax, x, y, s=1.0, color=INK):
    hull = np.array([[-1, 0], [1, 0], [0.8, -0.25], [-0.8, -0.25]]) * s + [x, y]
    ax.add_patch(patches.Polygon(hull, color=color))
    for mx in (-0.45, 0.05, 0.5):
        ax.plot([x + mx * s, x + mx * s], [y, y + 1.1 * s], color=color, lw=3)
        for k in range(3):
            ax.add_patch(patches.FancyBboxPatch((x + mx * s - 0.2 * s, y + (0.25 + 0.28 * k) * s), 0.4 * s, 0.22 * s,
                                                boxstyle="round,pad=0.01", color=PARCH, ec=color, lw=1.5))


def s_whaler():
    fig = canvas(PARCH)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 16); ax.set_ylim(0, 9); ax.axis("off")
    paper_texture(ax, 0.25)
    for k in range(6):
        xs = np.linspace(0, 16, 300); ax.plot(xs, 2.2 + 0.12 * np.sin(xs * 2 + k) - k * 0.25, color=INK, lw=1, alpha=0.6)
    ship(ax, 8, 2.3, 2.0)
    fig.text(0.5, 0.88, "1876 · китобойное судно «Велосити»", ha="center", fontsize=46, color=INK, family=SERIF, style="italic")
    save(fig, "whaler")
    fig = canvas(PARCH)
    ax = fig.add_axes([0.12, 0.08, 0.76, 0.84]); ax.axis("off"); ax.set_facecolor("#F1E4C3")
    ax.add_patch(patches.Rectangle((0, 0), 1, 1, color="#F1E4C3", transform=ax.transAxes))
    for i in range(14):
        ax.axhline(0.08 + i * 0.065, color="#9DB4C8", lw=1)
    lines = ["Судовой журнал", "", "…замечены песчаные островки", "и буруны.", "", "Курс прежний. Ветер свежий."]
    for i, l in enumerate(lines):
        ax.text(0.06, 0.9 - i * 0.12, l, fontsize=46 if i == 0 else 40, family=SERIF, style="italic", color=INK, transform=ax.transAxes)
    caption(fig, "Мель в открытом океане — смерть для корабля", y=0.05, size=38, color=INK)
    save(fig, "whaler")


def s_chart_1908():
    fig, ax = chart([157, 163, -21.5, -17], old=True, title="Admiralty Chart · 1908")
    island_shape(ax, *SANDY, "#D9C08A", INK)
    label(ax, SANDY[0] + 0.15, SANDY[1] + 0.12, "Sandy I.", size=36)
    for _ in range(40):
        lon, lat = np.random.uniform(157.2, 162.8), np.random.uniform(-21.3, -17.2)
        ax.text(lon, lat, str(np.random.randint(800, 2900)), fontsize=13, color="#6B5537", transform=ccrs.PlateCarree())
    save(fig, "chart_1908")
    fig = canvas(PARCH)
    for i, (x, y, rot, name) in enumerate([(0.2, 0.55, -6, "1908"), (0.45, 0.5, 4, "Times Atlas"), (0.7, 0.55, -3, "National\nGeographic")]):
        ax = fig.add_axes([x - 0.12, y - 0.25, 0.24, 0.5]); ax.axis("off")
        ax.add_patch(patches.Rectangle((0, 0), 1, 1, color="#E1C894", ec=INK, lw=3, transform=ax.transAxes))
        ax.add_patch(patches.Ellipse((0.5, 0.5), 0.35, 0.1, angle=-30, color="#C9AB6E", ec=INK, lw=2, transform=ax.transAxes))
        ax.text(0.5, 0.85, name, ha="center", va="center", fontsize=26, family=SERIF, color=INK, transform=ax.transAxes)
        ax.text(0.5, 0.35, "Sandy I.", ha="center", fontsize=22, family=SERIF, style="italic", color=INK, transform=ax.transAxes)
    caption(fig, "Остров переходил с карты на карту", y=0.1, size=44, color=INK)
    save(fig, "chart_1908")


def s_existence_doubtful():
    fig, ax = chart([158.8, 161, -20, -18.5], old=True)
    island_shape(ax, *SANDY, "#D9C08A", INK)
    label(ax, SANDY[0] + 0.15, SANDY[1] + 0.06, "Sandy I.  (E.D.)", size=40)
    save(fig, "existence_doubtful")
    fig = canvas(PARCH)
    fig.text(0.5, 0.62, "E.D.", ha="center", fontsize=200, family=SERIF, color=RED, weight="bold")
    fig.text(0.5, 0.42, "Existence Doubtful", ha="center", fontsize=60, family=SERIF, style="italic", color=INK)
    fig.text(0.5, 0.28, "«существование сомнительно»", ha="center", fontsize=48, color=INK)
    save(fig, "existence_doubtful")


def s_timeline_removed():
    fig = canvas(OCEAN)
    ax = fig.add_axes([0.05, 0.25, 0.9, 0.5]); ax.set_xlim(1860, 2020); ax.set_ylim(-1, 1); ax.axis("off")
    ax.plot([1865, 2015], [0, 0], color=WHITE, lw=4)
    for yr, txt, c, dx in [(1876, "замечен\nс китобоя", GOLD, 0), (1908, "карта\nАдмиралтейства", GOLD, 0), (1974, "Франция\nубрала", RED, -9), (1985, "Австралия\nубрала", RED, 9)]:
        ax.plot(yr, 0, "o", ms=26, color=c)
        ax.text(yr + dx, 0.25, str(yr), ha="center", fontsize=40, color=c, weight="bold")
        ax.text(yr + dx, -0.35, txt, ha="center", va="top", fontsize=26, color=WHITE)
    caption(fig, "Глубина: 1488–2353 м", y=0.12, size=46)
    save(fig, "timeline_removed")


def s_digital():
    fig, ax = chart([158.8, 161, -20, -18.5], old=True)
    island_shape(ax, *SANDY, "#D9C08A", INK)
    for _ in range(120):
        x, y = np.random.uniform(0.55, 0.98), np.random.uniform(0.05, 0.95)
        fig.patches.append(patches.Rectangle((x, y), 0.012, 0.02, transform=fig.transFigure, color=np.random.choice(["#00E5FF", "#1F7AFF", "#0B1E33"]), alpha=0.8))
    caption(fig, "Бумажная карта → цифровая база", y=0.1, size=44, color=INK)
    save(fig, "digital")
    fig = canvas(OCEAN)
    for i, (t, c, s) in enumerate([("Бумажные карты", "#9FB7C9", "острова НЕТ"), ("Цифровые базы", GOLD, "остров ЕСТЬ")]):
        fig.text(0.27 + i * 0.46, 0.6, t, ha="center", fontsize=54, color=c, weight="bold")
        fig.text(0.27 + i * 0.46, 0.45, s, ha="center", fontsize=60, color=WHITE)
    fig.lines.append(plt.Line2D([0.5, 0.5], [0.25, 0.8], transform=fig.transFigure, color=WHITE, lw=3, ls="--"))
    caption(fig, "Два мира, которые не разговаривали", y=0.12, size=44)
    save(fig, "digital")


def s_voyage():
    fig, ax = chart([146, 166, -28, -12], old=False)
    xs = np.linspace(153.2, SANDY[0], 50); ys = np.linspace(-27.4, SANDY[1], 50) + 1.5 * np.sin(np.linspace(0, math.pi, 50))
    ax.plot(xs, ys, color=GOLD, lw=4, ls="--", transform=ccrs.PlateCarree())
    ax.plot(*SANDY, marker="x", ms=26, mew=6, color=RED, transform=ccrs.PlateCarree())
    label(ax, SANDY[0] + 0.4, SANDY[1] + 0.4, "Сэнди?", color=WHITE, size=32, serif=False, weight="bold")
    caption(fig, "Октябрь 2012 · «Саузерн Сёрвейор»", y=0.9, size=42)
    save(fig, "voyage")
    fig = canvas(OCEAN)
    for i, (t, v, c) in enumerate([("Навигационная карта судна", "острова нет", "#9FB7C9"), ("Научные данные", "остров есть", GOLD)]):
        fig.text(0.5, 0.68 - i * 0.28, f"{t}:", ha="center", fontsize=44, color=c)
        fig.text(0.5, 0.58 - i * 0.28, v, ha="center", fontsize=64, color=WHITE, weight="bold")
    caption(fig, "Кто-то ошибается", y=0.1, size=50, color=RED)
    save(fig, "voyage")


def s_depth_profile():
    fig = canvas(OCEAN)
    ax = fig.add_axes([0.08, 0.15, 0.84, 0.65]); ax.set_facecolor(OCEAN)
    x = np.linspace(0, 60, 400)
    d = -1450 - 120 * np.sin(x / 7) - 60 * np.sin(x / 2.3) - 30 * np.random.rand(400)
    ax.fill_between(x, d, -2200, color="#3A2E22"); ax.plot(x, d, color=GOLD, lw=3)
    ax.axhline(0, color="#9FC3E0", lw=3)
    ax.axvspan(25, 35, color=RED, alpha=0.18); ax.text(30, 80, "«остров» по картам", ha="center", fontsize=30, color=RED)
    ax.annotate("", xy=(30, -1430), xytext=(30, -30), arrowprops=dict(arrowstyle="<->", color=WHITE, lw=3))
    ax.text(31.5, -800, "> 1400 м", fontsize=64, color=WHITE, weight="bold")
    ax.set_ylim(-2200, 300); ax.set_xlim(0, 60); ax.axis("off")
    caption(fig, "Ни отмели, ни рифа, ни песка", y=0.07, size=44)
    save(fig, "depth_profile")


def s_news():
    fig = canvas("#EEEDE9")
    heads = ["Учёные не нашли остров с карты", "Остров-призрак в Коралловом море", "Как остров 136 лет жил на картах"]
    for i, h in enumerate(heads):
        ax = fig.add_axes([0.1 + i * 0.06, 0.62 - i * 0.22, 0.72, 0.2]); ax.axis("off")
        ax.add_patch(patches.Rectangle((0, 0), 1, 1, color="white", ec="#BBBBBB", lw=2, transform=ax.transAxes))
        ax.text(0.03, 0.62, "НОЯБРЬ 2012", fontsize=18, color="#888888", transform=ax.transAxes)
        ax.text(0.03, 0.25, h, fontsize=40, color="#111111", weight="bold", family=SERIF, transform=ax.transAxes)
    save(fig, "news")


def s_polygon_gone():
    for step in range(2):
        fig = canvas("#1b2a38")
        ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
        sea(ax)
        if step == 0:
            t = np.linspace(0, 2 * np.pi, 120)
            ax.fill(0.5 + 0.25 * np.cos(t), 0.5 + 0.06 * np.sin(t), color="black")
            caption(fig, "Было", y=0.9, size=50)
        else:
            caption(fig, "Стало: просто океан", y=0.9, size=50)
            caption(fig, "136 лет закончились за пару недель", y=0.1, size=46, color=GOLD)
        save(fig, "polygon_gone")


def s_agloe():
    fig, ax = chart([-76.5, -73, 41, 43.2], old=True, title="Штат Нью-Йорк · 1930-е")
    ax.add_feature(cfeature.STATES.with_scale("10m"), edgecolor=INK, linewidth=1.5, linestyle=":")
    ax.add_feature(cfeature.RIVERS.with_scale("10m"), edgecolor="#6B8CA8", linewidth=1.5)
    ax.add_feature(cfeature.LAKES.with_scale("10m"), facecolor="#B9C9C9", edgecolor=INK, linewidth=0.8)
    ax.plot(-74.72, 42.1, "o", color=RED, ms=16, transform=ccrs.PlateCarree())
    label(ax, -74.72, 42.1, "Agloe", size=40)
    caption(fig, "Выдуманный городок-ловушка", y=0.1, size=44, color=INK)
    save(fig, "agloe")
    fig = canvas(PARCH)
    ax = fig.add_axes([0.3, 0.3, 0.4, 0.45]); ax.axis("off")
    ax.add_patch(patches.Polygon([[0.1, 0.0], [0.9, 0.0], [0.9, 0.6], [0.5, 0.95], [0.1, 0.6]], color="#C69C6D", ec=INK, lw=4))
    ax.add_patch(patches.Rectangle((0.42, 0), 0.16, 0.3, color=INK))
    ax.text(0.5, 0.48, "AGLOE\nGENERAL STORE", ha="center", va="center", fontsize=24, weight="bold", color=INK)
    caption(fig, "Выдумка стала реальностью", y=0.15, size=48, color=INK)
    save(fig, "agloe")


def s_bermeja():
    fig, ax = chart([-98, -80, 17, 31], old=False)
    ax.plot(-91.37, 22.55, marker="x", ms=30, mew=7, color=RED, transform=ccrs.PlateCarree())
    label(ax, -91.2, 22.8, "Бермеха?", color=WHITE, size=36, serif=False, weight="bold")
    label(ax, -96, 27.5, "Мексиканский залив", color="#9FC3E0", size=30)
    caption(fig, "2009: экспедиция острова не нашла", y=0.1, size=44)
    save(fig, "bermeja")


def s_navigation():
    fig = canvas(PARCH)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 16); ax.set_ylim(0, 9); ax.axis("off"); paper_texture(ax, 0.2)
    ax.add_patch(patches.Circle((5, 4.5), 2.4, fill=False, lw=6, ec=INK))
    for k in range(60):
        a = 2 * math.pi * k / 60; l = 0.35 if k % 5 == 0 else 0.15
        ax.plot([5 + 2.4 * math.cos(a), 5 + (2.4 - l) * math.cos(a)], [4.5 + 2.4 * math.sin(a), 4.5 + (2.4 - l) * math.sin(a)], color=INK, lw=2)
    ax.plot([5, 5 + 1.6 * math.cos(1.2)], [4.5, 4.5 + 1.6 * math.sin(1.2)], color=INK, lw=5)
    ax.plot([5, 5 + 2.1 * math.cos(-0.4)], [4.5, 4.5 + 2.1 * math.sin(-0.4)], color=RED, lw=3)
    ax.text(11.2, 5.4, "1 минута", fontsize=60, color=INK, ha="center", weight="bold")
    ax.text(11.2, 4.4, "ошибки часов", fontsize=40, color=INK, ha="center")
    ax.text(11.2, 2.8, "> 25 км", fontsize=90, color=RED, ha="center", weight="bold")
    save(fig, "navigation")
    fig, ax = chart([157.5, 161, -20.3, -18.3], old=True)
    island_shape(ax, *SANDY, "none", RED, ls="--")
    ax.plot(*BAMPTON, "*", ms=30, color=INK, transform=ccrs.PlateCarree())
    label(ax, BAMPTON[0] - 0.4, BAMPTON[1] + 0.15, "рифы Бамптон", size=30)
    ax.annotate("", xy=(SANDY[0] - 0.1, SANDY[1]), xytext=(BAMPTON[0] + 0.1, BAMPTON[1]), arrowprops=dict(arrowstyle="->", color=RED, lw=3, ls="--"),
                xycoords=ccrs.PlateCarree()._as_mpl_transform(ax), textcoords=ccrs.PlateCarree()._as_mpl_transform(ax))
    caption(fig, "Настоящий риф — не на своём месте?", y=0.1, size=42, color=INK)
    save(fig, "navigation")


def s_pumice():
    fig = canvas("#20384F")
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    sea(ax, light=True)
    n = 2500
    xs = np.random.normal(0.5, 0.22, n); ys = np.random.normal(0.5, 0.07, n) + 0.08 * np.sin(xs * 9)
    ax.scatter(xs, ys, s=np.random.uniform(8, 60, n), color="#BDB7A8", alpha=0.85)
    caption(fig, "Плот из пемзы — камень, который плавает", y=0.1, size=44)
    save(fig, "pumice")


def s_pumice_scale():
    fig = canvas(OCEAN)
    ax = fig.add_axes([0.05, 0.2, 0.9, 0.6]); ax.set_xlim(0, 500); ax.set_ylim(0, 120); ax.axis("off")
    ax.add_patch(patches.Ellipse((250, 70), 463, 55, color="#BDB7A8", alpha=0.9))
    ax.text(250, 70, "плот пемзы 2012 · 463 × 55 км", ha="center", va="center", fontsize=34, color=INK, weight="bold")
    ax.add_patch(patches.Ellipse((40, 15), 25, 5, color=RED))
    ax.text(70, 13, "«остров» Сэнди · 25 × 5 км", fontsize=30, color=WHITE)
    save(fig, "pumice_scale")
    fig, ax = chart([155, 195, -36, -14], old=False)
    ax.plot(*HAVRE, "^", ms=24, color=RED, transform=ccrs.PlateCarree())
    label(ax, HAVRE[0] - 6, HAVRE[1] - 1.5, "вулкан Гавр", color=WHITE, size=30, serif=False)
    label(ax, 172.5, -34.3, "Новая Зеландия", color=WHITE, size=26, serif=False)
    ax.plot(*SANDY, marker="o", ms=14, color=GOLD, transform=ccrs.PlateCarree())
    label(ax, SANDY[0] + 0.3, SANDY[1] + 0.4, "Сэнди", color=GOLD, size=26, serif=False)
    save(fig, "pumice_scale")
    fig = canvas(OCEAN)
    caption(fig, "Каменный остров, который плавал", y=0.55, size=64, color=GOLD)
    caption(fig, "…и уплыл", y=0.4, size=50)
    save(fig, "pumice_scale")


def s_finale():
    fig = canvas("#120B1E")
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    grad = np.linspace(0, 1, 540)[:, None] * np.ones((540, 960))
    ax.imshow(grad, extent=[0, 1, 0.45, 1], cmap="magma", aspect="auto", alpha=0.95)
    ax.imshow(np.linspace(0.2, 0.55, 200)[:, None] * np.ones((200, 960)), extent=[0, 1, 0, 0.45], cmap="bone", aspect="auto")
    ax.add_patch(patches.Circle((0.5, 0.45), 0.07, color="#FFB347", alpha=0.9))
    caption(fig, "Карта — это рассказ о мире", y=0.8, size=56)
    save(fig, "finale")
    fig = canvas(OCEAN)
    caption(fig, "Сколько ещё на картах мест,\nкоторых нет?", y=0.62, size=60)
    caption(fig, "Следующий выпуск: озеро Натрон", y=0.3, size=46, color=GOLD)
    save(fig, "finale")


SCENES = [s_hook_map, s_coral_sea, s_locator, s_black_polygon, s_whaler, s_chart_1908, s_existence_doubtful,
          s_timeline_removed, s_digital, s_voyage, s_depth_profile, s_news, s_polygon_gone, s_agloe, s_bermeja,
          s_navigation, s_pumice, s_pumice_scale, s_finale]

if __name__ == "__main__":
    for f in SCENES:
        f()
        print(f.__name__, "ok", flush=True)
    import json
    json.dump(FRAMES, open(os.path.join(OUT, "frames.json"), "w"), indent=1)
