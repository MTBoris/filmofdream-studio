import copy
import pytest
import sb2

TL = {
    "duration": 40.0,
    "scenes": [{"scene": "a", "start": 0.6}, {"scene": "b", "start": 20.0}],
    "words_source": "azure",
    "words": [
        {"w": "Глубина", "start": 3.0, "end": 3.5, "scene": "a"},
        {"w": "тысяча", "start": 3.6, "end": 4.0, "scene": "a"},
        {"w": "четыреста,", "start": 4.0, "end": 4.6, "scene": "a"},
        {"w": "метров", "start": 4.6, "end": 5.0, "scene": "a"},
        {"w": "метров", "start": 25.0, "end": 25.5, "scene": "b"},
    ],
}


def board():
    return {
        "version": 2,
        "assets": {"nasa": {"url": "https://eoimages.gsfc.nasa.gov/x.jpg", "credit": "NASA image courtesy X"}},
        "scenes": [
            {"scene": "a", "duration": 19.4, "shots": [
                {"id": "a1", "type": "stock", "query": "ocean waves", "dur": 8, "pick": "pix:111",
                 "overlay": {"template": "ocean-fact", "data": {"value": 1400}, "cue": "тысяча четыреста"}},
                {"id": "a2", "type": "image", "asset_id": "whaler", "dur": "rest", "motion": "pan-left"}]},
            {"scene": "b", "shots": [
                {"id": "b1", "type": "external-image", "asset_id": "nasa", "dur": 10},
                {"id": "b2", "type": "stock", "query": "storm sea", "dur": 10, "pick": 222}]},
        ],
    }


def test_resolve_times_and_rest():
    shots, warns = sb2.resolve(board(), TL)
    assert [s["id"] for s in shots] == ["a1", "a2", "b1", "b2"]
    a1, a2, b1, b2 = shots
    assert a1["start"] == 0.0 and a1["end"] == 8.0           # first scene starts at 0, not 0.6
    assert a2["start"] == 8.0 and a2["end"] == 20.0          # 'rest' takes what is left
    assert b1["start"] == 20.0 and b2["end"] == 40.0
    assert a1["pick"] == 111 and b2["pick"] == 222
    assert not warns


def test_overlay_cue_uses_word_time():
    shots, _ = sb2.resolve(board(), TL)
    ov = shots[0]["overlay"]
    assert ov["start"] == 3.6 and ov["end"] == 8.0           # cue ignores punctuation and case


def test_overlay_without_cue_uses_delay():
    b = board()
    del b["scenes"][0]["shots"][0]["overlay"]["cue"]
    shots, _ = sb2.resolve(b, TL)
    assert shots[0]["overlay"]["start"] == pytest.approx(0.4)


def test_cue_not_found_and_cue_outside_shot():
    b = board()
    b["scenes"][0]["shots"][0]["overlay"]["cue"] = "нет такой фразы"
    with pytest.raises(sb2.StoryboardError, match="not found"):
        sb2.resolve(b, TL)
    b = board()
    b["scenes"][0]["shots"][0]["dur"] = 2          # cue is spoken at 3.6 s, shot ends at 2 s
    with pytest.raises(sb2.StoryboardError, match="spoken at"):
        sb2.resolve(b, TL)


def test_duration_tolerance():
    b = board()
    b["scenes"][1]["shots"][0]["dur"] = 9.0         # 9 + 10 = 19 vs real 20 -> within ±1.5, stretched to fit
    shots, _ = sb2.resolve(b, TL)
    assert shots[2]["end"] == pytest.approx(shots[3]["start"]) and shots[3]["end"] == pytest.approx(40.0)
    b["scenes"][1]["shots"][0]["dur"] = 5.0         # 5 + 10 = 15 vs 20 -> error
    with pytest.raises(sb2.StoryboardError, match="add up"):
        sb2.resolve(b, TL)


def test_rest_needs_room_and_must_be_last():
    b = board()
    b["scenes"][0]["shots"][0]["dur"] = 19.5
    with pytest.raises(sb2.StoryboardError, match="left for the 'rest'"):
        sb2.resolve(b, TL)
    b = board()
    b["scenes"][0]["shots"][0]["dur"] = "rest"
    errs, _ = sb2.validate_structure(b)
    assert any("only on the last shot" in e for e in errs)


def test_no_pick_stops_the_build():
    b = board()
    b["scenes"][0]["shots"][0]["pick"] = None
    with pytest.raises(sb2.StoryboardError, match="no clip chosen"):
        sb2.resolve(b, TL)
    assert sb2.missing_picks(b) == ["a1"]
    sb2.resolve(b, TL, require_picks=False)


def test_clip_repeat_is_an_error():
    b = board()
    b["scenes"][1]["shots"][1]["pick"] = "pix:111"
    errs, _ = sb2.validate_structure(b)
    assert any("used twice" in e for e in errs)


def test_scene_mismatch_both_ways():
    b = board()
    b["scenes"].pop()
    with pytest.raises(sb2.StoryboardError, match="not in the storyboard"):
        sb2.resolve(b, TL)
    b = board()
    b["scenes"].append({"scene": "zzz", "shots": [{"id": "z", "type": "image", "asset_id": "q", "dur": 1}]})
    with pytest.raises(sb2.StoryboardError, match="not in the narration"):
        sb2.resolve(b, TL)


def test_external_image_needs_declared_asset_with_credit():
    b = board()
    b["assets"]["nasa"].pop("credit")
    errs, _ = sb2.validate_structure(b)
    assert any("credit" in e for e in errs)


def test_bad_types_and_picks():
    b = board()
    b["scenes"][0]["shots"][0]["type"] = "video"
    b["scenes"][1]["shots"][1]["pick"] = "abc"
    errs, _ = sb2.validate_structure(copy.deepcopy(b))
    assert any("type must be" in e for e in errs) and any("bad pick" in e for e in errs)


def test_scene_duration_mismatch_is_only_a_warning():
    b = board()
    b["scenes"][0]["duration"] = 30
    _, warns = sb2.resolve(b, TL)
    assert any("storyboard says" in w for w in warns)


def test_find_cue_nth():
    words = [{"w": "метров", "start": 1, "scene": "x"}, {"w": "метров", "start": 9, "scene": "x"}]
    assert sb2.find_cue(words, "x", "метров", 2) == 9
