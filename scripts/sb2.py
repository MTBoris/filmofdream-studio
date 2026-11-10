"""Storyboard v2: validate a storyboard (ChatGPT format) and resolve it to timed shots.

    python scripts/sb2.py check   STORYBOARD.json [TIMELINE.json] [--picks]
    python scripts/sb2.py resolve STORYBOARD.json TIMELINE.json OUT_SHOTS.json

Format (see docs/STORYBOARD.md):
  {"version": 2, "assets": {asset_id: {...}}, "scenes": [{"scene": name, "duration": 12.3, "shots": [shot, ...]}]}
  shot types: "stock" (Pixabay, needs "query"; "pick" chosen from candidates), "image" (ChatGPT picture, asset_id),
  "external-image" (real photo from a URL, asset_id declared in "assets" with url/page/credit).
  "dur": seconds, or "rest" on the last shot of a scene (takes what is left).
  "overlay": {"template": ..., "data": {...}, "cue": "words from the narration", "nth": 1, "at": seconds, "dur": seconds}

The scene time comes from the narration timeline, so re-recording the voice does not break the build:
the sum of the shot durations may differ from the real scene length by TOL seconds (it is then stretched to fit).
"""
import json
import re
import sys

TOL = 1.5          # allowed difference between the sum of shot durations and the real scene length, seconds
MIN_SHOT = 1.0     # a "rest" shot must keep at least this much
OVERLAY_DELAY = 0.4  # overlay without cue/at appears this long after its shot starts
TYPES = ("stock", "image", "external-image")
MOTIONS = ("push-in", "pull-out", "pan-left", "pan-right", "none")


class StoryboardError(Exception):
    pass


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def norm_word(s):
    """Lower-case, ё→е, only letters/digits (stress marks and punctuation removed)."""
    return re.sub(r"[^0-9a-zа-я]", "", s.lower().replace("ё", "е"))


def norm_words(text):
    return [w for w in (norm_word(x) for x in re.split(r"\s+", text)) if w]


def pick_id(pick):
    """'pix:123' | 123 | '123' -> 123 ; None/'' -> None."""
    if pick in (None, ""):
        return None
    m = re.fullmatch(r"(?:pix:)?(\d+)", str(pick).strip())
    if not m:
        raise StoryboardError(f"bad pick {pick!r} (use \"pix:123\")")
    return int(m.group(1))


def asset_info(sb, asset_id):
    return (sb.get("assets") or {}).get(asset_id)


def find_cue(words, scene, cue, nth=1):
    """Start time of the nth occurrence of the phrase `cue` among the words of `scene`."""
    target = norm_words(cue)
    if not target:
        raise StoryboardError(f"empty cue in scene {scene}")
    seq = [(norm_word(w["w"]), w["start"]) for w in words if w.get("scene") == scene]
    seq = [(w, t) for w, t in seq if w]
    found = 0
    for i in range(len(seq) - len(target) + 1):
        if [w for w, _ in seq[i:i + len(target)]] == target:
            found += 1
            if found == nth:
                return seq[i][1]
    heard = " ".join(w for w, _ in seq[:25])
    raise StoryboardError(f"scene {scene}: cue {cue!r} (occurrence {nth}) not found in the narration words. Scene starts: {heard} ...")


def scene_windows(tl):
    sc, total = tl["scenes"], tl["duration"]
    out = {}
    for i, s in enumerate(sc):
        start = 0.0 if i == 0 else s["start"]
        end = sc[i + 1]["start"] if i + 1 < len(sc) else total
        out[s["scene"]] = (start, end)
    return out


def validate_structure(sb):
    """Checks that do not need the timeline. Returns (errors, warnings)."""
    errs, warns = [], []
    if not isinstance(sb.get("scenes"), list) or not sb["scenes"]:
        hint = " (this looks like the old v1 format: scene -> shots; v2 needs {\"version\": 2, \"scenes\": [...]})" if isinstance(sb, dict) else ""
        return ["storyboard has no 'scenes' list" + hint], warns
    seen_scenes, seen_ids = set(), set()
    for sc in sb["scenes"]:
        name = sc.get("scene")
        if not name:
            errs.append("a scene without 'scene' name"); continue
        if name in seen_scenes:
            errs.append(f"scene {name}: listed twice")
        seen_scenes.add(name)
        shots = sc.get("shots") or []
        if not shots:
            errs.append(f"scene {name}: no shots")
        for k, s in enumerate(shots):
            sid = s.get("id") or f"{name}-{k + 1}"
            where = f"scene {name}, shot {sid}"
            if sid in seen_ids:
                errs.append(f"{where}: duplicate shot id")
            seen_ids.add(sid)
            t = s.get("type")
            if t not in TYPES:
                errs.append(f"{where}: type must be one of {TYPES}, got {t!r}")
                continue
            d = s.get("dur")
            if d == "rest":
                if k != len(shots) - 1:
                    errs.append(f"{where}: 'rest' is allowed only on the last shot of a scene")
            elif not isinstance(d, (int, float)) or d <= 0:
                errs.append(f"{where}: dur must be a positive number or 'rest'")
            if t == "stock":
                if not s.get("query"):
                    errs.append(f"{where}: stock shot needs 'query'")
                try:
                    pick_id(s.get("pick"))
                except StoryboardError as e:
                    errs.append(f"{where}: {e}")
            else:
                aid = s.get("asset_id")
                if not aid:
                    errs.append(f"{where}: {t} shot needs 'asset_id'")
                elif t == "external-image":
                    a = asset_info(sb, aid)
                    if not a or not (a.get("url") or a.get("page")) or not a.get("credit"):
                        errs.append(f"{where}: external-image asset {aid!r} must be declared in 'assets' with url/page and credit")
                if s.get("motion", "push-in") not in MOTIONS:
                    errs.append(f"{where}: motion must be one of {MOTIONS}")
            ov = s.get("overlay")
            if ov is not None:
                if not ov.get("template"):
                    errs.append(f"{where}: overlay needs 'template'")
                if "data" in ov and not isinstance(ov["data"], dict):
                    errs.append(f"{where}: overlay.data must be an object")
    picks = {}
    for sc in sb["scenes"]:
        for k, s in enumerate(sc.get("shots") or []):
            if s.get("type") == "stock":
                try:
                    p = pick_id(s.get("pick"))
                except StoryboardError:
                    continue
                if p is not None:
                    sid = s.get("id") or f"{sc['scene']}-{k + 1}"
                    if p in picks:
                        errs.append(f"stock clip pix:{p} is used twice ({picks[p]} and {sid}): no clip may repeat in an episode")
                    picks[p] = sid
    return errs, warns


def missing_picks(sb):
    """Stock shots that have no pick yet (the build must stop)."""
    out = []
    for sc in sb["scenes"]:
        for k, s in enumerate(sc.get("shots") or []):
            if s.get("type") == "stock" and pick_id(s.get("pick")) is None:
                out.append(s.get("id") or f"{sc['scene']}-{k + 1}")
    return out


def resolve(sb, tl, require_picks=True):
    """Return (shots, warnings): a flat list of shots with absolute start/end times and overlay start times."""
    errs, warns = validate_structure(sb)
    if require_picks:
        mp = missing_picks(sb)
        if mp:
            errs.append("no clip chosen (pick) for stock shots: " + ", ".join(mp))
    win = scene_windows(tl)
    by_name = {sc["scene"]: sc for sc in sb["scenes"] if sc.get("scene")}
    for name in win:
        if name not in by_name:
            errs.append(f"scene {name} is in the narration but not in the storyboard")
    for name in by_name:
        if name not in win:
            errs.append(f"scene {name} is in the storyboard but not in the narration")
    if errs:
        raise StoryboardError("\n".join(errs))

    words = tl.get("words") or []
    if words and tl.get("words_source") not in (None, "azure"):
        warns.append(f"word times are {tl.get('words_source')}, not exact Azure boundaries: overlay sync may be off")
    shots = []
    for name, (w0, w1) in win.items():
        sc = by_name[name]
        real = w1 - w0
        if isinstance(sc.get("duration"), (int, float)) and abs(sc["duration"] - real) > TOL:
            warns.append(f"scene {name}: storyboard says {sc['duration']:.1f}s, narration is {real:.1f}s")
        items = sc["shots"]
        fixed = sum(s["dur"] for s in items if s["dur"] != "rest")
        has_rest = any(s["dur"] == "rest" for s in items)
        if has_rest:
            rest = real - fixed
            if rest < MIN_SHOT:
                errs.append(f"scene {name}: only {rest:.1f}s left for the 'rest' shot (scene is {real:.1f}s, other shots {fixed:.1f}s)")
                continue
            durs = [rest if s["dur"] == "rest" else s["dur"] for s in items]
        else:
            if abs(fixed - real) > TOL:
                errs.append(f"scene {name}: shots add up to {fixed:.1f}s but the narration scene is {real:.1f}s (allowed ±{TOL}s)")
                continue
            durs = [s["dur"] * real / fixed for s in items]  # stretch to fit exactly
        t = w0
        for k, (s, d) in enumerate(zip(items, durs)):
            sid = s.get("id") or f"{name}-{k + 1}"
            shot = dict(s, id=sid, scene=name, n=k, start=round(t, 3), end=round(t + d, 3), dur=round(d, 3))
            if s["type"] == "stock":
                shot["pick"] = pick_id(s.get("pick"))
            ov = s.get("overlay")
            if ov:
                try:
                    if ov.get("cue"):
                        if not words:
                            raise StoryboardError(f"scene {name}, shot {sid}: overlay has a cue but the timeline has no word times (re-run the narration)")
                        at = find_cue(words, name, ov["cue"], int(ov.get("nth", 1)))
                        if at < shot["start"] - TOL or at > shot["end"]:
                            raise StoryboardError(
                                f"scene {name}, shot {sid}: cue {ov['cue']!r} is spoken at {at:.1f}s but the shot is {shot['start']:.1f}–{shot['end']:.1f}s")
                        at = min(max(at, shot["start"]), shot["end"] - 0.5)
                    else:
                        at = shot["start"] + float(ov.get("at", OVERLAY_DELAY))
                    oend = min(shot["end"], at + float(ov["dur"])) if ov.get("dur") else shot["end"]
                    shot["overlay"] = dict(ov, start=round(at, 3), end=round(oend, 3))
                except StoryboardError as e:
                    errs.append(str(e))
            shots.append(shot)
            t += d
    if errs:
        raise StoryboardError("\n".join(errs))
    return shots, warns


def main(argv):
    if len(argv) < 2 or argv[0] not in ("check", "resolve"):
        print(__doc__); return 2
    sb = load(argv[1])
    try:
        if argv[0] == "check":
            errs, warns = validate_structure(sb)
            if len(argv) > 2 and not argv[2].startswith("--"):
                tl = load(argv[2])
                try:
                    _, w2 = resolve(sb, tl, require_picks="--picks" in argv)
                    warns += w2
                except StoryboardError as e:
                    errs += str(e).split("\n")
            elif "--picks" in argv:
                errs += [f"no pick for {i}" for i in missing_picks(sb)]
            errs = list(dict.fromkeys(errs))
            for w in warns:
                print("WARN:", w)
            for e in errs:
                print("ERROR:", e)
            print("storyboard OK" if not errs else f"{len(errs)} problem(s)")
            return 1 if errs else 0
        shots, warns = resolve(sb, load(argv[2]))
        for w in warns:
            print("WARN:", w)
        json.dump({"shots": shots, "assets": sb.get("assets") or {}}, open(argv[3], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"{len(shots)} shots -> {argv[3]}")
        return 0
    except StoryboardError as e:
        print("STORYBOARD ERROR:\n" + str(e))
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
