import json
import pytest
import narrate_azure as na


def write_narration(tmp_path, text):
    (tmp_path / "narration.txt").write_text(text, encoding="utf-8")
    return str(tmp_path)


def test_parse_scenes_pauses_comments(tmp_path):
    ep = write_narration(tmp_path, "# comment\n@scene one\nПервая строка.\nВторая строка. //\n\n@scene two\nТретья.\n")
    items, lines = na.parse(ep)
    assert [i["type"] for i in items] == ["scene", "line", "line", "para", "scene", "line"]
    assert [l["idx"] for l in lines] == [0, 1, 2]
    assert lines[1]["dramatic"] and not lines[0]["dramatic"]
    assert lines[1]["text"] == "Вторая строка."


def test_ru2ipa_places_stress():
    assert "ˈ" in na.ru2ipa("+острова")
    # the same word with different stress must sound different
    assert na.ru2ipa("+острова") != na.ru2ipa("остров+а")
    assert na.ru2ipa("зам+ок") != na.ru2ipa("з+амок")


def test_to_ssml_marked_word_becomes_phoneme_unmarked_stays_plain():
    ssml = na.to_ssml("На +острова приплыли.")
    assert '<phoneme alphabet="ipa"' in ssml and ">острова</phoneme>" in ssml
    assert "+" not in ssml
    assert "<phoneme" not in na.to_ssml("Обычная строка без пометок.")


def test_to_ssml_escapes_xml():
    assert "&amp;" in na.to_ssml("Tom & Jerry")


def test_homograph_guard_stops_on_unmarked(capsys):
    lines = [{"idx": 0, "text": "Это были острова в океане."}]
    with pytest.raises(SystemExit):
        na.check_homographs(lines)
    assert "острова" in capsys.readouterr().out


def test_homograph_guard_passes_when_marked():
    na.check_homographs([{"idx": 0, "text": "Это были +острова в океане."}])
    na.check_homographs([{"idx": 0, "text": "Это были остров+а в океане."}])


def test_pilot_narration_passes_guard():
    _, lines = na.parse("episodes/001-sandy-island")
    na.check_homographs(lines)
    assert len(lines) > 50


def test_data_files_are_valid():
    for p in ("voices/homographs.json", "voices/pronunciations.json"):
        json.load(open(p, encoding="utf-8"))
    for w, marked in na.LEX.items():
        assert marked.count("+") == 1, f"pronunciations.json: {w}"
        assert marked.replace("+", "") == w


def test_estimated_word_times_fill_the_line():
    ws = na.estimate_words("Раз два три", 10.0, 3.0)
    assert [w["w"] for w in ws] == ["Раз", "два", "три"]
    assert ws[0]["start"] == 10.0 and ws[-1]["end"] == 13.0


def test_azure_word_times_are_shifted_by_trimmed_lead_and_line_start():
    ws = na.line_words("Раз два", [("Раз", 0.30, 0.2), ("два", 0.55, 0.3)], line_start=5.0, lead_trim=0.26, dur=1.0)
    assert ws[0]["start"] == 5.04 and ws[1]["start"] == 5.29
    assert na.line_words("Раз два", [("Раз", 0.0, 0.2)], 5.0, 0.5, 1.0)[0]["start"] == 5.0  # never before the line
