import sb2
import sb_plan


def timeline():
    words, t = [], 0.6
    for scene, text in (("a", "раз два три четыре пять шесть семь восемь девять десять " * 3), ("b", "один два три")):
        for w in text.split():
            words.append({"w": w, "start": round(t, 2), "end": round(t + 0.5, 2), "scene": scene})
            t += 0.6
    return {"duration": round(t + 1.5, 2), "scenes": [{"scene": "a", "start": 0.6}, {"scene": "b", "start": 18.6}], "words": words}


def test_plan_gives_short_shots_one_overlay_each_and_a_valid_storyboard(tmp_path):
    import json
    tl = timeline()
    plan = {"stock_profile": "nature-lake", "max_shot": 7.5, "fallback": ["lake"],
            "scenes": {"a": {"queries": ["flamingo", "salt lake"],
                             "overlays": [{"template": "lower-third", "cue": "три четыре", "data": {"text": "x"}},
                                          {"template": "lower-third", "cue": "пять шесть", "nth": 1, "data": {"text": "y"}}]},
                       "b": {"queries": ["savanna"]}}}
    p, t, o = tmp_path / "plan.json", tmp_path / "tl.json", tmp_path / "sb.json"
    p.write_text(json.dumps(plan, ensure_ascii=False))
    t.write_text(json.dumps(tl, ensure_ascii=False))
    sb_plan.main(str(p), str(t), str(o))
    sb = json.loads(o.read_text())
    assert sb["stock_profile"] == "nature-lake"
    for sc in sb["scenes"]:
        assert sc["shots"][-1]["dur"] == "rest"
        assert all(s["dur"] == "rest" or s["dur"] <= 8 for s in sc["shots"])
    a = sb["scenes"][0]["shots"]
    assert sum(1 for s in a if s.get("overlay")) == 2
    assert errs_ok(sb, tl)


def errs_ok(sb, tl):
    errs, _ = sb2.validate_structure(sb)
    assert not errs
    shots, _ = sb2.resolve(sb, tl, require_picks=False)
    assert all(s["dur"] <= 8.0 + 1e-6 for s in shots)
    return True
