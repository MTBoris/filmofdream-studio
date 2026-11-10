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
