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


def test_exact_palette_v1():
    assert ov.TOK["color"]["deep"].lower() == "#101d2b" and ov.TOK["color"]["panel"].lower() == "#213e50"
    assert ov.TOK["color"]["muted"].lower() == "#e6d6b8" and ov.TOK["color"]["accent"].lower() == "#d3a35b"
    assert ov.TOK["color"]["text"].lower() == "#e8eef1"
    assert set(v.lower() for v in ov.TOK["color"].values()) <= {"#101d2b", "#213e50", "#e6d6b8", "#d3a35b", "#e8eef1"}


def test_timeline_event_text_is_never_smaller_than_34px():
    assert ov.sizes({}, ("date", "event"))["event"] >= 34
    assert ov.sizes({"size": {"event": 20}}, ("date", "event"))["event"] == 34
    assert ov.sizes({"size": [90, 24]}, ("date", "event"))["event"] == 34


def test_timeline_has_a_local_dark_panel_under_the_text():
    data = {"events": [{"date": "1974", "label": "Франция убирает остров с карт", "t": 0.2}]}
    img = ov.timeline(2.0, 8, data, {"start": 0})
    # just above the bottom scrim region and just under the label the panel adds darkness around the text block
    px = img.getpixel((ov.W // 2 - 300, ov.H - ov.MY - 150))
    assert px[3] > 120


def test_parse_value_forms():
    assert ov.parse_value("400+") == ("", 400.0, "+", 0)
    assert ov.parse_value("≈26") == ("≈", 26.0, "", 0)
    assert ov.parse_value("2,5 млн") == ("", 2.5, " млн", 1)
    assert ov.parse_value(1400) == ("", 1400, "", 0)
    assert ov.parse_value("без цифр")[1] is None


def test_fact_string_values_count_up_and_keep_prefix_suffix():
    early = bright_pixels(ov.fact(0.5, 6, {"value": "≈26", "unit": "км"}, {}))
    late = bright_pixels(ov.fact(4.0, 6, {"value": "≈26", "unit": "км"}, {}))
    assert 0 < early < late
    assert bright_pixels(ov.fact(4.0, 6, {"value": "400+", "unit": "км", "label": "до"}, {})) > 3000


def test_missing_glyphs_are_replaced_not_drawn_as_boxes():
    f = ov.font("serif", 60)
    assert not ov.has_glyph(f, "′")          # PT Serif has no prime sign
    assert ov.fit_glyphs("19°13′ ю. ш.", f) == "19°13’ ю. ш."
    assert ov.fit_glyphs("≈26 км", f) == "≈26 км"


def test_coords_types_in_and_pulses():
    data = {"lat": "19°13′ ю. ш.", "lon": "159°55′ в. д.", "label": "Положение"}
    early = bright_pixels(ov.coords(0.6, 8, data, {}))
    late = bright_pixels(ov.coords(4.0, 8, data, {}))
    assert 0 < early < late


def test_compare_draws_both_shapes_to_the_same_scale():
    data = {"a": {"label": "Плот", "w": 463, "h": 55}, "b": {"label": "Остров", "w": 25, "h": 5}, "unit": "км"}
    assert bright_pixels(ov.compare(0.9, 8, data, {})) < bright_pixels(ov.compare(5.0, 8, data, {}))
    arr = np.asarray(ov.compare(5.0, 8, data, {})).astype(int)
    outline = (arr[..., 3] == 255) & (abs(arr[..., 0] - ov.C["accent"][0]) < 3) & (abs(arr[..., 1] - ov.C["accent"][1]) < 3)
    xs = np.where(outline.any(axis=0))[0]
    assert xs.max() - xs.min() > 1400          # the 463 km raft spans ~1500 px (the island, 25 km, only ~80 px)
    ys = np.where(outline.any(axis=1))[0]
    assert (ys.max() - ys.min()) < 400


def test_lower_third_and_title_card():
    lt = ov.lower_third(2.0, 6, {"text": "Плот пемзы вулкана Гавр · NASA · 2012"}, {})
    assert bright_pixels(lt) > 2000 and opaque_pixels(ov.lower_third(0.0, 6, {"text": "x"}, {})) == 0
    tc = ov.title_card(2.5, 6, {"title": "Остров, которого нет", "subtitle": "Film of Dream"}, {})
    assert bright_pixels(tc) > 8000 and opaque_pixels(ov.title_card(0.0, 6, {"title": "x"}, {})) == 0


def test_all_seven_templates_registered():
    assert set(ov.TEMPLATES) == {"ocean-fact", "ocean-coords", "ocean-timeline", "ocean-map", "ocean-compare", "lower-third", "title-card"}


def test_map_labels_do_not_overlap_each_other():
    items = [(240, 310, "остров Сэнди", 290), (110, 363, "Честерфилд", 260), (552, 382, "Новая Каледония", 380)]
    card = (10, 10, 800, 800)
    res = ov.place_labels(items, card, 34)
    boxes = [ov.label_box(x, y, dx, dy, anc, w, 34) for (x, y, _, w), (dx, dy, anc) in zip(items, res)]
    for i in range(3):
        for j in range(i + 1, 3):
            a, b = boxes[i], boxes[j]
            assert a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1], (i, j, boxes)
    assert all(b[0] >= card[0] and b[2] <= card[2] for b in boxes)       # every label stays inside the card


def test_map_with_three_labelled_points_renders(monkeypatch):
    data = {"center": [-20.8, 162.4], "span_km": 1100, "marker": {"lat": -19.22, "lon": 159.93, "label": "остров Сэнди"},
            "points": [{"lat": -19.87, "lon": 158.32, "label": "Честерфилд"}, {"lat": -20.1, "lon": 164.0, "label": "Новая Каледония"}]}
    ctx = {}
    assert bright_pixels(ov.ocean_map(3.0, 8, data, ctx)) > 1500
    assert len(next(iter(ctx["_label_offsets"].values()))) == 3
