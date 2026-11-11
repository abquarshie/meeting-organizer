# -*- coding: utf-8 -*-
"""Reading workbook PDFs into weeks, parts and dates."""
from datetime import date
from pathlib import Path

import pytest

from conftest import form


def test_english_weeks_parts_and_wrapped_titles(core, english_workbook):
    weeks, empty, _ = core.parse_brochure(english_workbook)
    assert list(weeks) == ["SEPTEMBER 14–20", "SEPTEMBER 21–27"]
    assert not empty
    first = weeks["SEPTEMBER 14–20"]
    assert [p["part_no"] for p in first["parts"]] == list(range(1, 11))
    assert first["gaps"] == []
    titles = {p["part_no"]: p["title"] for p in first["parts"]}
    assert titles[8] == "Keep Your Marriage Strong by Showing Loyalty to Each Other"
    roles = {p["part_no"]: p["role"] for p in first["parts"]}
    assert roles[3] == "Bible Reading" and roles[10] == "Bible Study Conductor"
    assert {p["section"] for p in first["parts"] if 4 <= p["part_no"] <= 7} == {"Ministry"}
    assert first["songs"] == ["76", "100"]


def test_dangme_weeks_split_pages_and_skipped_week(core, dangme_workbook):
    weeks, _, _ = core.parse_brochure(dangme_workbook)
    assert list(weeks) == ["SEPTEMBER 7–13", "SEPTEMBER 14–20", "OCTOBER 5–11"]
    parts = weeks["SEPTEMBER 14–20"]["parts"]
    assert len(parts) == 9                    # continued on the next page
    # the Dangme headings place the sections
    assert parts[0]["section"] == "Treasures"
    assert parts[3]["section"] == "Ministry"
    assert parts[-1]["role"] == "Bible Study Conductor"
    assert weeks["SEPTEMBER 14–20"]["songs"][0] == "76"       # "La 76"

    first, sure = core.guess_first_monday(weeks, "mwb_DG_202609.pdf")
    assert (first, sure) == (date(2026, 9, 7), True)
    core.assign_dates(weeks, first)
    assert core.week_for_date(weeks, "2026-09-10") == "SEPTEMBER 7–13"
    assert core.week_for_date(weeks, "2026-09-17") == "SEPTEMBER 14–20"
    assert core.week_for_date(weeks, "2026-10-01") is None  # the skipped week
    assert core.week_for_date(weeks, "2026-10-08") == "OCTOBER 5–11"


def test_gaps_are_reported(core):
    text = "\n".join(["1. Talk (10 min.)", "2. Gems (10 min.)", "3. Bible Reading (4 min.)",
                      "4. Starting a Conversation (3 min.)", "7. Living Part (15 min.)",
                      "8. Another Part", "9. Congregation Bible Study (30 min.)"])
    from workbook import _parse_week
    parts, _, gaps = _parse_week(text)
    assert gaps == [5, 6]
    assert [p["part_no"] for p in parts] == [1, 2, 3, 4, 7, 8, 9]


def test_workbook_is_stored(core, english_workbook):
    weeks, _, _ = core.parse_brochure(english_workbook)
    first, _ = core.guess_first_monday(weeks, "mwb_E_202609.pdf")
    core.save_workbook(core.assign_dates(weeks, first), "mwb_E_202609.pdf")
    stored, name = core.load_workbook()
    assert name == "mwb_E_202609.pdf"
    assert stored["SEPTEMBER 21–27"]["start"] == "2026-09-21"


def test_more_heading_shapes_are_recognised(core):
    from workbook import _heading
    # an en dash, an em dash, a figure dash and a minus sign all read the same
    for dash in "-\u2010\u2012\u2013\u2014\u2212":
        assert _heading(f"SEPTEMBER 14{dash}20")["label"] == "SEPTEMBER 14–20"
    # a leading bullet from a PDF export
    assert _heading("• SEPTEMBER 14-20")["day"] == 14
    # title case on a short line
    assert _heading("Sɛptɛmba 7-13")["label"] == "Sɛptɛmba 7–13"
    # but not an ordinary sentence that happens to contain a range
    assert _heading("Discuss the material on pages 4-6 with the householder") is None
    assert _heading("4. Starting a Conversation (3 min.)") is None


def test_heading_with_scripture_and_page_number(core):
    """SEPTEMBER 7-13  |  YEREMIA 32-33                    2  — the exact shape
    printed on the real workbook: a book/chapter reading after the date,
    and a right-aligned page number sharing the same line."""
    from workbook import _heading
    h = _heading("SEPTEMBER 7-13  |  YEREMIA 32-33                          2")
    assert h["label"] == "SEPTEMBER 7–13"
    assert h["book"] == "YEREMIA 32-33"          # page number stripped

    h2 = _heading("SEPTEMBER 21-27  |  YEREMIA 34-36")   # no trailing page number
    assert h2["book"] == "YEREMIA 34-36"

    h3 = _heading("SEPTEMBER 7-13")                        # nothing after the date
    assert h3["book"] == ""


def test_dangme_minutes_are_read(core):
    """The Dangme workbook writes '(Hɛngm. 10)', not '(10 min.)'."""
    from workbook import _parse_week
    text = ("1. Moo Kase Ní\n(Hɛngm. 10)\n"
            "2. Ngmami ɔ Mi Junehi (Hɛngm. 10)\n"
            "3. Baiblo Kanemi (Hɛngm. 4)\n"
            "4. Moo Je Ní Sɛɛmi Sisi (Hɛngm. 3)\n"
            "5. Kpale Ya Slaa Nihi Nɛ O Kɛ Mɛ Sɛɛ Ní ɔ (Hɛngm. 4)\n"
            "6. Moo Pee Nihi Kaseli (Hɛngm. 5)\n"
            "7. Asafo ɔ Mi Hiami Níhi (Hɛngm. 15)\n"
            "8. Asafo Baiblo Mi Ní Kasemi (Hɛngm. 30)\n")
    parts, _, gaps = _parse_week(text)
    assert gaps == []
    assert [p["minutes"] for p in parts] == [10, 10, 4, 3, 4, 5, 15, 30]
    sections = [p["section"] for p in parts]
    assert sections == (["Treasures"] * 3 + ["Ministry"] * 3 + ["Living"] * 2)
    assert parts[-1]["role"] == "Bible Study Conductor"


def test_a_week_can_be_renamed(core, english_workbook):
    weeks, _, _ = core.parse_brochure(english_workbook)
    core.save_workbook(core.assign_dates(weeks, date(2026, 9, 14)), "en.pdf")
    stored, name = core.load_workbook()
    old = "SEPTEMBER 14–20"
    renamed = {("DEUTERONOMY 24-26" if l == old else l): w for l, w in stored.items()}
    core.save_workbook(renamed, name)
    after, _ = core.load_workbook()
    assert "DEUTERONOMY 24-26" in after and old not in after
    assert after["DEUTERONOMY 24-26"]["start"] == stored[old]["start"]   # dates kept


DANGME_WEEK = """NOVEMBER 9-15  YEREMIA 51-52                     4

JUETLI NƐ NGƐ
MAWU MUNYU Ɔ MI

1. Moo Kase Ní Kɛ Je Zedekia Sane ɔ Mi (Hɛngm. 10)
2. Ngmami ɔ Mi Junehi (Hɛngm. 10)
3. Baiblo Kanemi (Hɛngm. 4)

MOO BƆ FIƐƐMI
NÍ TSUMI Ɔ HE MƆDE

4. Moo Je Ní Sɛɛmi Sisi (Hɛngm. 3)
5. Kpale Ya Slaa Nihi Nɛ O Kɛ Mɛ Sɛɛ Ní ɔ (Hɛngm. 4)
6. Mɛni O Ma De? (Hɛngm. 4)
7. Moo Pee Nihi Kaseli (Hɛngm. 5)
8. Tsɔɔ Níhi Nɛ O Heɔ Yeɔ Mi (Hɛngm. 5)
9. Munyu Tumi (Hɛngm. 5)

KRISTOFOHI
A SI HIMI

10. Yemi Kɛ Buamihi Nɛ Wa Haa (Hɛngm. 15)
11. Asafo Baiblo Mi Ní Kasemi (Hɛngm. 30)
"""


def test_dangme_titles_get_the_right_roles(core):
    """Role drives who is eligible and how rotation is tracked. Without the
    Dangme words every ministry part would collapse to Initial Presentation."""
    from workbook import _parse_week
    parts, _, gaps = _parse_week(DANGME_WEEK)
    assert gaps == []
    roles = {p["part_no"]: p["role"] for p in parts}
    assert roles == {
        1: "Treasures Talk", 2: "Spiritual Gems", 3: "Bible Reading",
        4: "Initial Presentation",      # Moo Je Ní Sɛɛmi Sisi
        5: "Initial Presentation",      # following up
        6: "Initial Presentation",      # Mɛni O Ma De?
        7: "Making Disciples",          # Moo Pee Nihi Kaseli
        8: "Explaining Beliefs",        # Tsɔɔ Níhi Nɛ O Heɔ Yeɔ Mi
        9: "Student Talk",              # Munyu Tumi
        10: "Living Part", 11: "Bible Study Conductor",
    }


def test_dangme_section_headings_are_read_not_guessed(core):
    """With the Dangme headings recognised, sections come from the page, even
    when the heading wraps over two lines as it is printed."""
    from workbook import _parse_week, HEADING_RES
    assert HEADING_RES["Treasures"].search("JUETLI NƐ NGƐ MAWU MUNYU Ɔ MI")
    assert HEADING_RES["Ministry"].search("MOO BƆ FIƐƐMI NÍ TSUMI Ɔ HE MƆDE")
    assert HEADING_RES["Living"].search("KRISTOFOHI A SI HIMI")
    parts, _, _ = _parse_week(DANGME_WEEK)
    sections = {p["part_no"]: p["section"] for p in parts}
    # part 9 is a 5-minute part AFTER the ministry section: guessing from
    # numbers and durations alone could not place it reliably
    assert sections[9] == "Ministry" and sections[10] == "Living"


def test_section_heading_split_over_two_lines(core):
    """The printed heading wraps: "KRISTOFOHI" / "A SI HIMI". Missing it is
    worse than finding no headings at all, because everything after it falls
    into the previous section."""
    from workbook import _parse_week
    wrapped = DANGME_WEEK
    parts, _, _ = _parse_week(wrapped)
    sections = {p["part_no"]: p["section"] for p in parts}
    roles = {p["part_no"]: p["role"] for p in parts}
    assert sections[10] == "Living" and sections[11] == "Living"
    assert roles[11] == "Bible Study Conductor"
    # the English heading wraps too
    wrapped_en = "APPLY YOURSELF TO\nTHE FIELD MINISTRY"
    from workbook import HEADING_RES
    assert HEADING_RES["Ministry"].search(wrapped_en)


def test_page_number_before_or_after_the_date(core):
    """The page number shares the date line and swaps side with the page, so
    week 1 parsed and week 2 did not."""
    from workbook import _heading
    right = _heading("SEPTEMBER 7-13  |  YEREMIA 32-33            2")
    left = _heading("4   SEPTEMBER 14-20  |  YEREMIA 34-36")
    assert right["label"] == "SEPTEMBER 7–13" and right["book"] == "YEREMIA 32-33"
    assert left["label"] == "SEPTEMBER 14–20" and left["book"] == "YEREMIA 34-36"
    assert _heading("12  NOVEMBER 16 -22  KƆMƆ YEMI 1 -2")["label"] == "NOVEMBER 16–22"
    assert _heading("SEPTEMBER 28-OCTOBER 4")["label"] == "SEPTEMBER 28–OCTOBER 4"
    # numbered part lines and ordinary prose must still be rejected
    assert _heading("4. Starting a Conversation (3 min.)") is None
    assert _heading("5. Kpale Ya Slaa Nihi (Hɛngm. 4)") is None
    assert _heading("Discuss the material on pages 4-6 with the householder") is None


def test_the_real_dangme_workbook_parses_completely(core):
    """The printed Dangme workbook, end to end: every week, every part, its songs
    and its reading — and the back-cover continuation is not a week of its own."""
    weeks, empty, _ = core.parse_brochure(form("mwb_DG_202611.pdf"))
    assert list(weeks) == [
        "NOVEMBER 2–8", "NOVEMBER 9–15", "NOVEMBER 16–22", "NOVEMBER 23–29",
        "NOVEMBER 30–DECEMBER 6", "DECEMBER 7–13", "DECEMBER 14–20", "DECEMBER 21–27",
        "DECEMBER 28–JANUARY 3"]
    assert not empty
    assert not [w for w in weeks.values() if w["gaps"]]

    first = weeks["NOVEMBER 2–8"]
    assert first["book"] == "YEREMIA 49-50"
    assert first["songs"] == ["44", "1", "33"]
    titles = {p["part_no"]: p["title"] for p in first["parts"]}
    assert titles[2] == "Ngmami ɔ Mi Junehi"
    assert titles[3] == "Baiblo Kanemi"
    roles = {p["part_no"]: p["role"] for p in first["parts"]}
    assert roles[3] == "Bible Reading" and roles[8] == "Bible Study Conductor"
    assert roles[6] == "Making Disciples"

    for label, w in weeks.items():
        assert len(w["songs"]) == 3, label
        assert w["book"], label
        assert w["parts"][-1]["role"] == "Bible Study Conductor", label
    assert core.guess_first_monday(weeks, "mwb_DG_202611.pdf") == (date(2026, 11, 2), True)


def test_past_weeks_are_dropped_but_still_anchor_the_dates(core, english_workbook):
    """Dates are assigned from the first week's heading, so the past weeks have
    to be dated before they are dropped — otherwise the remaining weeks land on
    the wrong days."""
    weeks, _, _ = core.parse_brochure(english_workbook)
    dated = core.assign_dates(dict(weeks), date(2026, 9, 14))
    assert dated["SEPTEMBER 21–27"]["start"] == "2026-09-21"

    # mid-week: the week we are in is kept, the one before it is not
    kept, dropped = core.drop_past_weeks(dated, date(2026, 9, 17))
    assert dropped == []                                  # both weeks still running
    kept, dropped = core.drop_past_weeks(dated, date(2026, 9, 23))
    assert list(kept) == ["SEPTEMBER 21–27"]
    assert dropped == ["SEPTEMBER 14–20"]
    assert kept["SEPTEMBER 21–27"]["start"] == "2026-09-21"   # dates unchanged

    # the last day of a week still counts as current
    kept, _ = core.drop_past_weeks(dated, date(2026, 9, 20))
    assert "SEPTEMBER 14–20" in kept

    # an entirely past workbook is kept whole rather than emptied
    kept, dropped = core.drop_past_weeks(dated, date(2027, 1, 1))
    assert len(kept) == 2 and dropped == []
