"""Write storyboard.json from a compact scene plan + the real narration timeline (Claude Code's storyboard tool).

    python scripts/sb_plan.py PLAN.json TIMELINE.json OUT_STORYBOARD.json

PLAN: {"stock_profile": "...", "max_shot": 8, "fallback": [queries...], "picks": {shot_id: "pix:123"},
       "scenes": {name: {"queries": [q1, q2, ...], "overlays": [{"template", "data", "cue", "nth"?}, ...]}}}
For every narration scene the real length is split into n = ceil(len / max_shot) shots of equal length (the last one "rest").
Each overlay is put on the shot that contains the moment its cue is spoken; if two overlays land in one shot, the
scene gets one more shot until every shot has at most one overlay. Shot k uses query k (cycling); the other scene
queries and the plan's fallback queries become its alternatives.
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sb2  # noqa: E402


def split(w0, w1, n, pins=None):
    """n+1 boundaries from w0 to w1; pinned boundaries {index: time} stay, the rest are spread evenly between them."""
    anchors = sorted({0: w0, n: w1, **{i: t for i, t in (pins or {}).items() if 0 < i < n}}.items())
    bounds = [0.0] * (n + 1)
    for (i0, t0), (i1, t1) in zip(anchors, anchors[1:]):
        for i in range(i0, i1 + 1):
            bounds[i] = t0 + (t1 - t0) * (i - i0) / (i1 - i0)
    return bounds


def place(bounds, times):
    """shot index for each cue time."""
    out = []
    for t in times:
        t = min(max(t, bounds[0]), bounds[-1] - 1e-6)  # a cue may start a few ms before the scene boundary
        out.append(next(i for i in range(len(bounds) - 1) if bounds[i] <= t < bounds[i + 1]))
    return out


MIN_VISIBLE = 3.0   # an overlay must stay on screen at least this long before its shot ends
MIN_SHOT = 2.5


def scene_shots(name, w0, w1, spec, words, max_shot, fallback):
    ovs = spec.get("overlays") or []
    times = [sb2.find_cue(words, name, o["cue"], int(o.get("nth", 1))) for o in ovs]
    ends = []   # when the overlay must still be visible (last event cue of a timeline + 1.2 s, else cue + MIN_VISIBLE)
    for o, t in zip(ovs, times):
        ev = [sb2.find_cue(words, name, e["cue"], int(e.get("nth", 1))) for e in (o.get("data") or {}).get("events", []) if e.get("cue")]
        ends.append(min(w1, max([t + MIN_VISIBLE] + [x + 1.2 for x in ev])))
    n = max(1, math.ceil((w1 - w0) / max_shot - 1e-6))
    pins, accepted = {}, set()
    for _ in range(60):
        bounds = split(w0, w1, n, pins)
        ks = place(bounds, times)
        if len(set(ks)) != len(ks):
            n, pins = n + 1, {}
            continue
        fix = None
        for i, (k, t, e) in enumerate(zip(ks, times, ends)):
            if bounds[k + 1] < e and k + 1 < n and i not in accepted:          # overlay would be cut: start the next shot just before the cue
                if t - 0.6 - bounds[k] >= MIN_SHOT and k + 1 not in ks and (k + 1) not in pins:
                    fix = (k + 1, t - 0.6)
                elif (k + 1) not in pins and e - bounds[k] <= max_shot + 0.5:   # or stretch this shot until the overlay is done
                    fix = (k + 1, e)
                trial = split(w0, w1, n, {**pins, fix[0]: fix[1]}) if fix else None
                if not fix or min(b - a for a, b in zip(trial, trial[1:])) < MIN_SHOT:
                    accepted.add(i)   # cannot be fixed without a too-short shot: keep the shorter overlay
                    fix = None
                    continue
                break
        if fix:
            pins[fix[0]] = fix[1]
            continue
        if max(b - a for a, b in zip(bounds, bounds[1:])) > max_shot + 0.5:
            n, pins = n + 1, {}
            continue
        break
    qs = spec["queries"]
    shots = []
    for k in range(n):
        q = qs[k % len(qs)]
        alts = [x for x in qs if x != q] + [x for x in fallback if x not in qs]
        d = round(bounds[k + 1] - bounds[k], 2)
        shot = {"id": f"{name}-{k + 1:02d}", "type": "stock", "query": q, "queries": alts, "dur": d if k < n - 1 else "rest"}
        for o, kk in zip(ovs, ks):
            if kk == k:
                shot["overlay"] = {key: v for key, v in o.items()}
        shots.append(shot)
    return shots


def main(plan_path, tl_path, out_path):
    plan = json.load(open(plan_path, encoding="utf-8"))
    tl = json.load(open(tl_path, encoding="utf-8"))
    win = sb2.scene_windows(tl)
    words = tl.get("words") or []
    max_shot = float(plan.get("max_shot", 8))
    scenes = []
    for name, (w0, w1) in win.items():
        spec = plan["scenes"][name]
        shots = scene_shots(name, w0, w1, spec, words, max_shot, plan.get("fallback", []))
        for sh in shots:   # clips chosen after looking at the candidate sheets
            if sh["id"] in (plan.get("picks") or {}):
                sh["pick"] = plan["picks"][sh["id"]]
        scenes.append({"scene": name, "duration": round(w1 - w0, 2), "shots": shots})
    sb = {"version": 2, "stock_profile": plan.get("stock_profile", "open-water"), "assets": plan.get("assets", {}), "scenes": scenes}
    json.dump(sb, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    n = sum(len(s["shots"]) for s in scenes)
    longest = max(s["dur"] for sc in scenes for s in sc["shots"] if s["dur"] != "rest")
    print(f"{len(scenes)} scenes, {n} shots, longest fixed shot {longest:.2f}s -> {out_path}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
