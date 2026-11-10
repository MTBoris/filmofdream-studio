import math

import numpy as np
import pytest
import overlays as ov


@pytest.fixture(autouse=True)
def no_network_land(monkeypatch):
    monkeypatch.setattr(ov, "land_polygons", lambda bbox: [])


def opaque_pixels(img, thr=40):
    return int((np.asarray(img.getchannel("A")) > thr).sum())


def bright_pixels(img):
    """Text pixels: opaque and light (the scrim and the map card are dark)."""
    a = np.asarray(img).astype(int)
    return int(((a[..., 3] > 200) & (a[..., :3].sum(axis=2) > 450)).sum())


def test_fmt_num_russian_style():
    assert ov.fmt_num(1400) == "1 400"
    assert ov.fmt_num(2.5, 1) == "2,5"
    assert ov.fmt_num(463) == "463"


def test_sizes_dict_list_number():
    assert ov.sizes({}, ("value", "label", "note"))["value"] == ov.TOK["size"]["value"]
    assert ov.sizes({"size": [100, 80, 100]}, ("value", "label", "note")) == {"value": 100, "label": 80, "note": 100}
    assert ov.sizes({"size": {"label": 70}}, ("value", "label", "note"))["label"] == 70
    assert ov.sizes({"size": 120}, ("value", "label"))["value"] == 120


def test_envelope_fades_in_and_out():
    assert ov.envelope(0, 5) == 0 and ov.envelope(5, 5) == 0
    assert ov.envelope(2.5, 5) == 1


def test_mercator_scale_and_nice_km():
    x0, y0 = ov.merc(0, 0)
    x1, _ = ov.merc(0, 1)
    assert math.isclose((x1 - x0) / 1000, 111.32, abs_tol=0.1)
    assert ov.nice_km(180) == 200 and ov.nice_km(4) == 5 and ov.nice_km(9999) == 5000


def test_fact_is_transparent_at_start_and_draws_at_midpoint():
    data = {"value": 1400, "unit": "м", "label": "глубина", "note": "эхолот"}
    assert opaque_pixels(ov.fact(0.0, 6, data, {})) == 0
    assert bright_pixels(ov.fact(3.0, 6, data, {})) > 5000


def test_fact_counter_counts_up():
    data = {"value": 1400, "unit": "м"}
    early = bright_pixels(ov.fact(0.6, 6, data, {}))
    late = bright_pixels(ov.fact(4.0, 6, data, {}))
    assert 0 < early < late


def test_text_stays_inside_margins():
    img = ov.fact(3.0, 6, {"value": 1400, "unit": "м", "label": "глубина под килем", "note": "эхолот"}, {})
    # text is drawn on top of the scrim: look only at bright pixels
    bright = [(x, y) for y in range(0, ov.H, 4) for x in range(0, ov.W, 4)
              if img.getpixel((x, y))[3] > 200 and sum(img.getpixel((x, y))[:3]) > 450]
    assert bright and min(x for x, _ in bright) >= ov.MX - 6 and max(y for _, y in bright) <= ov.H - ov.MY + 6


def test_timeline_events_appear_in_sequence():
    data = {"events": [{"date": "1974", "label": "Франция", "t": 1.0}, {"date": "1985", "label": "Австралия", "t": 4.0}]}
    ctx = {"start": 0.0}
    a = bright_pixels(ov.timeline(2.0, 8, data, ctx))
    b = bright_pixels(ov.timeline(6.0, 8, data, ctx))
    assert 0 < a < b


def test_timeline_cue_times_are_relative_to_overlay_start():
    data = {"events": [{"date": "1974", "label": "x", "t": 11.0}]}
    # overlay starts at 10 s: the event at absolute 11 s must be invisible at local t=0.3 and visible at 2.5
    assert bright_pixels(ov.timeline(0.3, 8, data, {"start": 10.0})) < bright_pixels(ov.timeline(2.5, 8, data, {"start": 10.0}))


def test_map_draws_marker_card_and_skips_points_outside():
    data = {"title": "Коралловое море", "center": [-20.8, 162.4], "span_km": 1100,
            "marker": {"lat": -19.22, "lon": 159.93, "label": "остров Сэнди"},
            "points": [{"lat": 40.0, "lon": 10.0, "label": "далеко"}]}
    ctx = {}
    img = ov.ocean_map(3.0, 8, data, ctx)
    assert opaque_pixels(img) > 100000
    mb = next(iter(ctx["_maps"].values()))
    x, y = mb.px(-19.22, 159.93)
    assert 0 < x < mb.w and 0 < y < mb.h
    assert mb.px(40.0, 10.0)[0] < 0 or mb.px(40.0, 10.0)[0] > mb.w


def test_render_writes_frames_and_rejects_unknown_template(tmp_path):
    n = ov.render({"template": "ocean-fact", "data": {"value": 10, "unit": "м"}, "start": 5.0, "end": 5.4}, str(tmp_path))
    assert n == 12 and len(list(tmp_path.glob("*.png"))) == 12
    with pytest.raises(KeyError):
        ov.render({"template": "nope", "start": 0, "end": 1}, str(tmp_path / "x"))


def test_fonts_exist_and_have_cyrillic():
    f = ov.font("serif", 40)
    assert f.getlength("Глубина") > 100
    ov.font("sans", 30)
    ov.font("sans_bold", 30)
