import pytest
import stock2


def hit(i, tags="ocean, waves, sea", dur=20, w=1920, typ="film"):
    return {"id": i, "tags": tags, "duration": dur, "page": f"p{i}", "type": typ,
            "videos": {"large": {"url": f"u{i}", "width": w, "height": 1080}, "medium": {"url": f"m{i}", "width": 1280, "height": 720}}}


def test_filter_requires_all_query_words_in_tags_and_rejects_fake():
    pool = [hit(1), hit(2, tags="ocean, ai generated"), hit(3, tags="beach, sand"), hit(4, dur=3), hit(5, typ="animation"),
            hit(6, w=640)]
    pool[5]["videos"]["medium"]["width"] = 640
    ids = [h["id"] for h in stock2.filter_hits(pool, "ocean waves")]
    assert ids == [1]


def test_assign_candidates_are_unique_across_shots():
    pool = {"ocean": [hit(i) for i in range(1, 8)]}
    shots = [{"id": "s1", "query": "ocean"}, {"id": "s2", "query": "ocean"}]
    out, short = stock2.assign_candidates(shots, pool)
    ids1, ids2 = [h["id"] for h in out["s1"]], [h["id"] for h in out["s2"]]
    assert len(ids1) == 3 and len(ids2) == 3 and not set(ids1) & set(ids2)
    assert short == [] or all("s" in m for m in short)
    assert len(short) == 0


def test_shortage_is_reported_not_repeated():
    pool = {"ocean": [hit(i) for i in range(1, 5)]}  # 4 clips for 2 shots x 3
    out, short = stock2.assign_candidates([{"id": "s1", "query": "ocean"}, {"id": "s2", "query": "ocean"}], pool)
    assert len(out["s1"]) == 3 and len(out["s2"]) == 1
    assert len(short) == 1 and "s2" in short[0]
    assert not {h["id"] for h in out["s1"]} & {h["id"] for h in out["s2"]}


def test_alternative_queries_and_taken_ids():
    pool = {"a": [hit(1), hit(2)], "b": [hit(3, tags="ocean, sea waves"), hit(4, tags="ocean, sea waves")]}
    out, short = stock2.assign_candidates([{"id": "s", "query": "ocean", "queries": ["ocean"]}], {"ocean": pool["a"]}, taken={1})
    assert [h["id"] for h in out["s"]] == [2]
    out, short = stock2.assign_candidates([{"id": "s", "query": "ocean", "queries": ["sea waves"]}],
                                          {"ocean": [hit(1)], "sea waves": [hit(3, tags="sea, waves"), hit(4, tags="sea, waves")]})
    assert [h["id"] for h in out["s"]] == [1, 3, 4] and not short


def test_rendition_prefers_large_1920():
    assert stock2.rendition(hit(1))[0] == "large"
    h = hit(1, w=1280)
    assert stock2.rendition(h)[0] == "medium"


def test_open_water_drops_land_rocks_islands_and_boats():
    pool = [hit(1), hit(2, tags="ocean, waves, rocks"), hit(3, tags="ocean, waves, island"), hit(4, tags="ocean, waves, boat"),
            hit(5, tags="ocean, waves, coastline"), hit(6, tags="ocean, waves, sailing"), hit(7, tags="ocean, waves, sunset")]
    assert [h["id"] for h in stock2.filter_hits(pool, "ocean waves")] == [1, 7]


def test_research_ship_shots_may_have_vessels_but_never_land():
    pool = [hit(1, tags="research, ship, ocean"), hit(2, tags="research, ship, ocean, island")]
    assert stock2.filter_hits(pool, "research ship ocean") == []             # default: open water only
    assert [h["id"] for h in stock2.filter_hits(pool, "research ship ocean", allow_vessels=True)] == [1]
    assert stock2.vessels_allowed({"query": "research ship at sea"}) and stock2.vessels_allowed({"query": "x", "vessels": True})
    assert not stock2.vessels_allowed({"query": "ocean waves"})


def test_assign_uses_vessel_rule_per_shot():
    pool = {"research ship": [hit(i, tags="research, ship") for i in range(1, 4)], "ocean waves": [hit(i, tags="ocean, waves, boat") for i in range(10, 13)]}
    out, short = stock2.assign_candidates([{"id": "a", "query": "research ship"}, {"id": "b", "query": "ocean waves"}], pool)
    assert len(out["a"]) == 3 and out["b"] == [] and len(short) == 1


def test_jungle_palm_forest_beach_coast_tags_are_dropped():
    bad = ["jungle", "palm", "palms", "tree", "forest", "beach", "coast", "rain-forest", "rainforest", "palm tree", "rain forest"]
    pool = [hit(i, tags=f"ocean, waves, {t}") for i, t in enumerate(bad, start=100)] + [hit(1)]
    assert [h["id"] for h in stock2.filter_hits(pool, "ocean waves")] == [1]


def test_blocklisted_clip_is_never_a_candidate():
    assert 136684 in stock2.blocklist()
    pool = [hit(136684, tags="ocean, rain, seaview, philippines, stormy weather, rainy days, nature"), hit(2, tags="ocean, rain, stormy weather")]
    assert [h["id"] for h in stock2.filter_hits(pool, "ocean rain")] == [2]


def test_only_16_9_files_are_used():
    ok = hit(1)
    wide = hit(2)
    wide["videos"]["large"] = {"url": "u", "width": 1920, "height": 800}            # 2.4:1 - comes with bars / needs a crop
    wide["videos"]["medium"] = {"url": "m", "width": 1280, "height": 534}
    square = hit(3)
    square["videos"]["large"] = {"url": "u", "width": 1920, "height": 1440}
    square["videos"]["medium"] = {"url": "m", "width": 1280, "height": 960}
    vertical = hit(4)
    vertical["videos"]["large"] = {"url": "u", "width": 1920, "height": 3414}
    vertical["videos"]["medium"] = {"url": "m", "width": 1280, "height": 2276}
    assert [h["id"] for h in stock2.filter_hits([ok, wide, square, vertical], "ocean waves")] == [1]
    assert stock2.aspect_ok({"width": 1920, "height": 1080}) and stock2.aspect_ok({"width": 1280, "height": 720})
    assert not stock2.aspect_ok({"width": 1920, "height": 1000}) and not stock2.aspect_ok({})


def test_assign_candidates_accept_callback_skips_and_refills():
    pool = {"ocean": [hit(i) for i in range(1, 7)]}
    out, short = stock2.assign_candidates([{"id": "s", "query": "ocean"}], pool, accept=lambda h: h["id"] not in (1, 2))
    assert [h["id"] for h in out["s"]] == [3, 4, 5] and not short


import shutil  # noqa: E402
import subprocess  # noqa: E402


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_black_bars_are_detected_on_pixels(tmp_path):
    plain = str(tmp_path / "plain.mp4")
    barred = str(tmp_path / "barred.mp4")
    pillar = str(tmp_path / "pillar.mp4")
    src = "testsrc2=size=1920x1080:rate=10:duration=3"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", src, "-pix_fmt", "yuv420p", plain], check=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", src, "-vf", "scale=1920:800,pad=1920:1080:0:140:black",
                    "-pix_fmt", "yuv420p", barred], check=True)                    # 16:9 file with letterboxed picture inside
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", src, "-vf", "scale=1200:1080,pad=1920:1080:360:0:black",
                    "-pix_fmt", "yuv420p", pillar], check=True)
    assert stock2.black_bars(plain) is False
    assert stock2.black_bars(barred) is True
    assert stock2.black_bars(pillar) is True


def test_relaxed_fills_shots_that_strict_matching_leaves_empty():
    pool = {"ocean waves": [hit(i, tags="ocean, waves, sea") for i in range(1, 7)]}
    shots = [{"id": "a", "query": "ocean waves"}, {"id": "b", "query": "stormy horizon"}]
    strict, short = stock2.assign_candidates(shots, pool)
    assert strict["b"] == [] and short
    out, short = stock2.assign_candidates(shots, pool, relaxed=True)
    ids = [h["id"] for h in out["a"]] + [h["id"] for h in out["b"]]
    assert len(out["b"]) == 1 and len(ids) == len(set(ids)) and not short
