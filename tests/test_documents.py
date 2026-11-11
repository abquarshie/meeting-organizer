# -*- coding: utf-8 -*-
"""Slips, printable schedules and the S-140."""
import io
from pathlib import Path

from conftest import form

import pytest

import docx
import pypdf


def _text(pdf_bytes):
    return "\n".join(p.extract_text() for p in pypdf.PdfReader(io.BytesIO(pdf_bytes)).pages)


def _full_week(core, people, aux=True):
    weeks = {"W": {"parts": core.default_midweek_parts()}}
    slots = core.apply_aux(core.build_midweek_slots(weeks["W"]["parts"]), aux)
    names = dict(zip(core.get_students()["id"], core.get_students()["name"]))
    picks = {}
    for i, s in enumerate(slots):
        if s["role"] == "Aux Classroom Counselor":
            picks[i] = (people["Kofi Mensah"], None)
        elif s["student_part"]:
            aux_slot = s["hall"] == core.AUX_HALL
            picks[i] = (people["Efua Osei" if aux_slot else "Ama Owusu"],
                        people["Ama Owusu" if aux_slot else "Efua Osei"]
                        if s["needs_assistant"] else None)
        else:
            picks[i] = (people["Kofi Mensah"], None)
    core.save_schedule("2026-09-16", core.MIDWEEK, slots, picks,
                       {"heading": "SEPTEMBER 14–20", "aux": aux,
                        "opening_song": "Song 1"}, names)


def test_schedule_pdf_names_the_classroom(core, people):
    _full_week(core, people)
    text = _text(core.generate_schedule_pdf([("2026-09-16", core.MIDWEEK)], core.get_schedules()))
    assert "Auxiliary classroom" in text and "Midweek Meeting" in text


def test_schedule_pdf_in_dangme(core, people):
    """Section headings switch language; the scripture reading, when saved,
    replaces the week label on the blue heading line."""
    _full_week(core, people)
    core.save_schedule("2026-09-16", core.MIDWEEK,
                       core.apply_aux(core.build_midweek_slots(
                           core.default_midweek_parts()), True),
                       {}, {"heading": "SEPTEMBER 14–20", "book": "YEREMIA 32-33",
                            "aux": True}, {})
    text_en = _text(core.generate_schedule_pdf(
        [("2026-09-16", core.MIDWEEK)], core.get_schedules()))
    assert "Treasures From God" in text_en
    assert "YEREMIA 32-33" in text_en          # the book line, not the week label
    assert "SEPTEMBER 14" not in text_en

    text_ada = _text(core.generate_schedule_pdf(
        [("2026-09-16", core.MIDWEEK)], core.get_schedules(), core.TRANSLATIONS["Dangme"]))
    assert "Mawu Munyu" in text_ada
    assert "Treasures From God" not in text_ada
    assert "YEREMIA 32-33" in text_ada          # the reading itself is language-neutral


def test_s140_fills_both_halls(core, people, s140_template):
    _full_week(core, people)
    data, skipped = core.build_s140_data([("2026-09-16", core.MIDWEEK)],
                                         core.get_schedules(), "TEST CONG")
    assert not skipped and data["aux"]
    week = data["weeks"][0]
    assert week["treasures"][2]["name2"] == "Efua Osei"
    assert week["aux_counselor"] == "Kofi Mensah"
    doc = docx.Document(io.BytesIO(core.fill_s140(s140_template, data)))
    cells = [c.text for r in doc.tables[0].rows for c in r.cells]
    assert "Efua Osei/Ama Owusu" in cells and "Ama Owusu/Efua Osei" in cells
    assert not any("0:00" == c for c in cells)


def test_a_second_auxiliary_classroom_flows_through(core):
    """The app only offers one auxiliary classroom, but nothing downstream
    should silently drop a second one if a schedule ever carries it."""
    slots = core.build_midweek_slots(core.default_midweek_parts())
    reading = next(s for s in slots if s["role"] == "Bible Reading")
    slots = slots + [
        {**reading, "hall": "aux_1"},
        {**reading, "hall": "aux_2"},
    ]
    picks = {len(slots) - 2: (None, None), len(slots) - 1: (None, None)}
    core.add_student("Adjeley Ayi", "Sister", ["Bible Reading"])
    core.add_student("Naa Koshie", "Sister", ["Bible Reading"])
    ids = dict(zip(core.get_students()["name"], core.get_students()["id"]))
    names = {v: k for k, v in ids.items()}
    picks = {len(slots) - 2: (ids["Adjeley Ayi"], None),
             len(slots) - 1: (ids["Naa Koshie"], None)}
    core.save_schedule("2026-09-16", core.MIDWEEK, slots, picks, {"aux": True}, names)

    rows = core.get_schedules()
    assert set(rows["hall"]) == {"main_hall", "aux_1", "aux_2"}

    # the slip data carries the third room through
    slip_rows = core.slip_rows_for(rows)
    assert {r["hall"] for r in slip_rows} >= {"aux_1", "aux_2"}

    # the part label names the room it is in
    label = core.slot_label({**reading, "hall": "aux_2"})
    assert "Auxiliary classroom 2" in label

    # and the S-140 pairing treats it as a classroom, not a duplicate main-hall part
    data, skipped = core.build_s140_data([("2026-09-16", core.MIDWEEK)], rows,
                                         "TEST CONG")
    assert not skipped and data["aux"]
    titles = [i["title"] for i in data["weeks"][0]["treasures"]]
    assert titles.count("Bible Reading") == 1      # not repeated once per classroom


def test_printed_schedule_is_fully_dangme(core, people):
    """Everything on a Dangme sheet is Dangme, whatever language the app is in."""
    _full_week(core, people)
    rows = core.get_schedules()
    text = _text(core.generate_schedule_pdf(
        [("2026-09-16", core.MIDWEEK)], rows, core.TRANSLATIONS["Dangme"]))
    flat = " ".join(text.split())

    # section headings, meeting name and room label all in Dangme
    assert "Mawu Munyu" in flat and "Kristofohi A Si Himi" in flat
    assert "Otsi ɔ Mi Kpe" in flat
    assert "Tsu wayo 1" in flat                    # the auxiliary classroom

    for english in ("Treasures From God", "Living as Christians",
                    "Midweek Meeting", "Auxiliary classroom"):
        assert english not in flat, f"{english!r} still on the Dangme sheet"


def test_interface_labels_stay_english(core):
    """slot_label without hall names is the interface version."""
    slot = core.make_slot("Bible Reading", "Bible Reading", "Treasures",
                          3, 4, core.AUX_HALL)
    assert "Auxiliary classroom 1" in core.slot_label(slot)
    rooms = {h: core.TRANSLATIONS["Dangme"][h] for h in core.HALLS}
    assert "Tsu wayo 1" in core.slot_label(slot, rooms)


def test_auxiliary_classroom_group_is_printed(core, people):
    """Which group is using the classroom is stored per week and printed
    beside the counselor."""
    slots = core.apply_aux(core.build_midweek_slots(core.default_midweek_parts()), True)
    names = dict(zip(core.get_students()["id"], core.get_students()["name"]))
    counselor = next(i for i, s in enumerate(slots)
                     if s["role"] == "Aux Classroom Counselor")
    core.save_schedule("2026-09-16", core.MIDWEEK, slots,
                       {counselor: (people["Kofi Mensah"], None)},
                       {"aux": True, "aux_group": "1"}, names)
    assert core.get_meeting_meta("2026-09-16", core.MIDWEEK)["aux_group"] == "1"

    text = _text(core.generate_schedule_pdf([("2026-09-16", core.MIDWEEK)],
                                            core.get_schedules()))
    assert "Auxiliary classroom 1" in text and "Group 1" in text

    ada = _text(core.generate_schedule_pdf([("2026-09-16", core.MIDWEEK)],
                                           core.get_schedules(),
                                           core.TRANSLATIONS["Dangme"]))
    assert "Tsu wayo 1" in ada and "1" in ada

    # no group entered: the room is still named, with nothing after it
    core.save_schedule("2026-09-16", core.MIDWEEK, slots,
                       {counselor: (people["Kofi Mensah"], None)},
                       {"aux": True, "aux_group": ""}, names)
    plain = _text(core.generate_schedule_pdf([("2026-09-16", core.MIDWEEK)],
                                             core.get_schedules()))
    assert "Auxiliary classroom 1" in plain and "Group" not in plain


def _s89():
    return form("S-89_DG.pdf")


def test_official_s89_is_filled_not_redrawn(core):
    """Printing on the real Dangme form gets its exact wording, so the app never has
    to carry a hand-typed copy of it."""
    blank = _s89()
    rows = [
        {"person": "Ɛfua Ɔsei", "assistant": "Naa Ŋmɛnɛ", "part_no": 4,
         "part_name": "x", "meeting_date": "2026-09-23", "hall": "aux_1"},
        {"person": "Samuel Oquaye", "assistant": None, "part_no": 5,
         "part_name": "x", "meeting_date": "2026-09-23", "hall": "aux_2"},
        {"person": "Vera Akitah", "assistant": None, "part_no": 3,
         "part_name": "x", "meeting_date": "2026-09-23", "hall": core.MAIN_HALL},
    ]
    text = _text(core.fill_s89(blank, rows))
    assert "Tsu wayo 1" in text and "Tsu wayo 2" in text   # the form's room list
    # our values, Dangme characters intact
    assert "Ɛfua Ɔsei" in text and "Naa Ŋmɛnɛ" in text
    assert "23 September 2026" in text
    assert text.count("X") == 3                  # one room ticked per filled slip

    # four slips to a page: three rows plus a blank still fills one sheet
    assert _pages(core.fill_s89(blank, rows)) == 1
    assert _pages(core.fill_s89(blank, rows * 2)) == 2


def test_slips_need_the_official_blank(core):
    """The app does not draw its own imitation of the form: without the blank
    it says so, rather than printing something that only looks official."""
    blank = _s89()
    rows = [{"person": "Kofi Mensah", "assistant": None, "part_no": 3,
             "part_name": "x", "meeting_date": "2026-09-23", "hall": core.MAIN_HALL}]
    with pytest.raises(core.S89Error) as raised:
        core.slips_pdf(rows, core.TRANSLATIONS["Dangme"], "Dangme")
    assert "Admin" in str(raised.value)          # says where to put it

    core.save_template("s89_Dangme", "S-89.pdf", blank)
    official = _text(core.slips_pdf(rows, core.TRANSLATIONS["Dangme"], "Dangme"))
    assert "Kofi Mensah" in official and "Tsu wayo 1" in official


def test_midweek_column_widths(core):
    """One column set for every week. The part title needs the room the
    classroom's old second name column used to take."""
    page = 523.0
    widths = core.midweek_widths(page)
    assert len(widths) == 3
    assert abs(sum(widths) - page) < 1.0            # the full text width, no more
    assert widths[0] > page * 0.5                   # the title has room
    assert widths[-1] > widths[1]                   # names wider than their labels


def test_songs_print_in_the_sheet_language(core, people):
    """A Dangme workbook stores "La 74" and an English one "Song 74"; the sheet
    prints whichever word matches it."""
    slots = core.build_midweek_slots(core.default_midweek_parts())
    names = dict(zip(core.get_students()["id"], core.get_students()["name"]))
    core.save_schedule("2026-09-16", core.MIDWEEK, slots, {},
                       {"opening_song": "Song 74", "closing_song": "La 134"}, names)
    rows = core.get_schedules()
    english = _text(core.generate_schedule_pdf([("2026-09-16", core.MIDWEEK)], rows))
    assert "Song 74" in english and "Song 134" in english
    assert "La 1" not in english and "La 7" not in english
    ada = _text(core.generate_schedule_pdf([("2026-09-16", core.MIDWEEK)], rows,
                                           core.TRANSLATIONS["Dangme"]))
    assert "La 74" in ada and "La 134" in ada
    assert "Song" not in ada


def test_s89_edge_cases(core):
    """Zero rows, one row, and a wrong file — the three ways the uploader and
    the print button can be used that are not the happy path."""
    import io

    import pypdf

    blank = _s89()

    # no assignments at all still prints one sheet of blanks, not zero pages
    empty = core.fill_s89(blank, [])
    assert len(pypdf.PdfReader(io.BytesIO(empty)).pages) == 1

    one = core.fill_s89(blank, [{"person": "Kofi Mensah", "assistant": None,
                                 "part_no": 3, "part_name": "x",
                                 "meeting_date": "2026-09-23",
                                 "hall": core.MAIN_HALL}])
    assert len(pypdf.PdfReader(io.BytesIO(one)).pages) == 1
    assert "Kofi Mensah" in _text(one)

    # checking a template does not render it
    assert core.check_s89_template(blank) == 4
    with pytest.raises(core.S89Error):
        core.check_s89_template(b"not a pdf at all")
    with pytest.raises(core.S89Error):
        core.check_s89_template(b"%PDF-1.4\n%%EOF\n")


def _midweek_week(core, date_iso, aux, people):
    slots = core.apply_aux(core.build_midweek_slots(core.default_midweek_parts()), aux)
    names = dict(zip(core.get_students()["id"], core.get_students()["name"]))
    picks = {i: (people["Kofi Mensah"],
                 people["Ama Owusu"] if s["needs_assistant"] else None)
             for i, s in enumerate(slots)}
    core.save_schedule(date_iso, core.MIDWEEK, slots, picks,
                       {"aux": aux, "aux_group": "1" if aux else "",
                        "opening_song": "Song 74", "middle_song": "Song 142",
                        "closing_song": "Song 134"}, names)


def _pages(pdf_bytes):
    import io

    import pypdf

    return len(pypdf.PdfReader(io.BytesIO(pdf_bytes)).pages)


def test_two_ordinary_weeks_share_a_sheet_at_full_size(core, people):
    """Compact pairs ordinary weeks without shrinking anything; a classroom
    week is too tall to pair, so it keeps its own sheet rather than being
    reduced to fit."""
    _midweek_week(core, "2026-09-09", False, people)
    _midweek_week(core, "2026-09-16", False, people)
    rows = core.get_schedules()
    both = [("2026-09-09", core.MIDWEEK), ("2026-09-16", core.MIDWEEK)]
    assert _pages(core.generate_schedule_pdf(both, rows, compact=True)) == 1
    assert _pages(core.generate_schedule_pdf(both, rows)) == 2      # off by default

    # the type is the same size either way
    one = core.generate_schedule_pdf([both[0]], rows)
    assert "Treasures From God" in _text(one)
    paired = _text(core.generate_schedule_pdf(both, rows, compact=True))
    assert paired.count("Treasures From God") == 2


def test_classroom_weeks_keep_their_own_sheet(core, people):
    _midweek_week(core, "2026-09-09", True, people)
    _midweek_week(core, "2026-09-16", True, people)
    rows = core.get_schedules()
    both = [("2026-09-09", core.MIDWEEK), ("2026-09-16", core.MIDWEEK)]
    assert _pages(core.generate_schedule_pdf(both, rows, compact=True)) == 2

    # mixed: an ordinary week cannot pair across a classroom week, because the
    # weeks have to stay in date order
    _midweek_week(core, "2026-09-23", False, people)
    _midweek_week(core, "2026-09-30", False, people)
    rows = core.get_schedules()
    mixed = [("2026-09-09", core.MIDWEEK), ("2026-09-16", core.MIDWEEK),
             ("2026-09-23", core.MIDWEEK), ("2026-09-30", core.MIDWEEK)]
    assert _pages(core.generate_schedule_pdf(mixed, rows, compact=True)) == 3


def test_classroom_has_its_own_section(core, people):
    """The classroom's parts are listed under a heading naming the room and
    group, not paired anonymously beside the main hall's names."""
    _midweek_week(core, "2026-09-16", True, people)
    rows = core.get_schedules()
    text = _text(core.generate_schedule_pdf([("2026-09-16", core.MIDWEEK)], rows))
    assert "Auxiliary classroom 1" in text and "Group 1" in text
    # the classroom's parts belong with the field ministry, so its heading sits
    # between that section and Living as Christians
    assert (text.index("Apply Yourself") < text.index("Auxiliary classroom 1")
            < text.index("Living as Christians"))

    ada = " ".join(_text(core.generate_schedule_pdf([("2026-09-16", core.MIDWEEK)], rows,
                                                    core.TRANSLATIONS["Dangme"])).split())
    assert "Tsu wayo 1" in ada
    assert ada.count("Tsu Wayo ɔ Mi Ga Wolɔ") == 1   # the counselor, listed once


def _s140():
    return form("S-140_DG.docx")


def _cell_rows(out):
    from docx.oxml.ns import qn

    def txt(el):
        return "".join(n.text or "" for n in el.iter(qn("w:t")))
    trs = docx.Document(io.BytesIO(out)).tables[0]._tbl.findall(qn("w:tr"))
    return trs, [[txt(c) for c in tr.findall(qn("w:tc"))] for tr in trs]


def test_the_dangme_s140_blank_fills(core, people):
    """The published Dangme blank fills a month of weeks, with the song and
    minutes words in Dangme whatever the stored text was."""
    blank = _s140()
    names = dict(zip(core.get_students()["id"], core.get_students()["name"]))
    dates = ["2026-09-09", "2026-09-16", "2026-09-23"]
    for d in dates:
        slots = core.build_midweek_slots(core.default_midweek_parts())
        picks = {i: (people["Kofi Mensah"],
                     people["Ama Owusu"] if s["needs_assistant"] else None)
                 for i, s in enumerate(slots)}
        core.save_schedule(d, core.MIDWEEK, slots, picks,
                           {"heading": f"WEEK OF {d}", "opening_song": "Song 74",
                            "middle_song": "Song 142", "closing_song": "Song 134"},
                           names)
    data, skipped = core.build_s140_data([(d, core.MIDWEEK) for d in dates],
                                         core.get_schedules(), "Asafo", language="Dangme")
    assert not skipped and len(data["weeks"]) == 3

    assert core.check_s140_template(blank) >= 1
    _, rows = _cell_rows(core.fill_s140(blank, data))
    text = "\n".join(c for r in rows for c in r)
    for d in dates:
        assert f"WEEK OF {d}" in text           # a block per week, each with its heading
    assert "[DATE]" not in text and "[Biɛ]" not in text and "[Munyuyi]" not in text
    assert "La 74" in text and "Song 74" not in text
    assert "Hɛngm." in text and "Kofi Mensah" in text


def test_s140_template_check_rejects_the_wrong_file(core):
    with pytest.raises(core.S140Error):
        core.check_s140_template(b"not a docx")
    with pytest.raises(core.S140Error):
        core.check_s140_template(_s89())      # a PDF


def test_s140_fills_the_classroom_column(core, people):
    """The blank has a classroom / main hall pair of name columns. The classroom's
    people belong in the first, and the counselor beside the form's own label."""
    blank = _s140()
    for n in ("Main Student", "Main Helper", "Aux Student", "Aux Helper",
              "Counselor Man"):
        core.add_student(n, "Brother", core.PRIVILEGES)
    ids = dict(zip(core.get_students()["name"], core.get_students()["id"]))
    names = {v: k for k, v in ids.items()}
    slots = core.apply_aux(core.build_midweek_slots(core.default_midweek_parts()),
                           True)
    picks = {}
    for i, s in enumerate(slots):
        if s["role"] == "Aux Classroom Counselor":
            picks[i] = (ids["Counselor Man"], None)
        elif s["student_part"]:
            aux = s["hall"] != core.MAIN_HALL
            picks[i] = (ids["Aux Student" if aux else "Main Student"],
                        ids["Aux Helper" if aux else "Main Helper"]
                        if s["needs_assistant"] else None)
        else:
            picks[i] = (people["Kofi Mensah"], None)
    core.save_schedule("2026-09-16", core.MIDWEEK, slots, picks,
                       {"heading": "SEPTEMBER 14-20", "aux": True, "aux_group": "1",
                        "opening_song": "La 74"}, names)
    data, skipped = core.build_s140_data([("2026-09-16", core.MIDWEEK)],
                                         core.get_schedules(), "Asafo", language="Dangme")
    assert not skipped and data["aux"]

    _, rows = _cell_rows(core.fill_s140(blank, data))
    # the counselor sits beside the label, which survives
    assert any("Tsu Wayo ɔ Mi Ga Wolɔ:" in r and "Counselor Man" in r for r in rows), rows
    # classroom names in the classroom column, main hall in the main hall's
    paired = [r for r in rows if any(c.startswith("Aux Student") for c in r)]
    assert paired, rows
    for r in paired:
        aux = next(k for k, c in enumerate(r) if c.startswith("Aux Student"))
        assert r[aux + 1].startswith("Main Student")


def test_unfilled_parts_print_a_dash(core, people):
    """An empty cell on a noticeboard reads as a fault in the sheet; a dash
    reads as a part still to be filled."""
    slots = core.build_midweek_slots(core.default_midweek_parts())
    names = dict(zip(core.get_students()["id"], core.get_students()["name"]))
    chairman = next(i for i, s in enumerate(slots) if s["role"] == "Chairman")
    core.save_schedule("2026-09-16", core.MIDWEEK, slots,
                       {chairman: (people["Kofi Mensah"], None)}, {}, names)
    text = _text(core.generate_schedule_pdf([("2026-09-16", core.MIDWEEK)],
                                            core.get_schedules()))
    assert "Kofi Mensah" in text
    assert "\u2014" in text                      # the unfilled parts


def _week_of_meetings(core, people):
    """Week 2 of October 2026: the midweek meeting on Wed 14, plus the
    Wednesday before (7 Oct) and after (21 Oct)."""
    names = dict(zip(core.get_students()["id"], core.get_students()["name"]))
    mid = core.build_midweek_slots(core.default_midweek_parts())
    ministry = next(i for i, s in enumerate(mid) if s["role"] == "Initial Presentation")
    core.save_schedule("2026-10-14", core.MIDWEEK, mid,
                       {0: (people["Kofi Mensah"], None),
                        ministry: (people["Esi Mensah"], people["Ama Owusu"])},
                       {}, names)
    for day in ("2026-10-07", "2026-10-21"):
        core.save_schedule(day, core.MIDWEEK, mid, {0: (people["Yaw Adjei"], None)},
                           {}, names)
    return core.get_schedules()


def test_the_week_is_one_message_with_every_part(core, people):
    """One message for the whole Monday–Sunday week: every part and who has it,
    assistants included, gaps marked. The weeks either side stay out."""
    rows = _week_of_meetings(core, people)
    text = core.week_overview_text(rows, "2026-10-16")        # any day in it
    assert text.startswith("*Meeting assignments — Week 2 of October (12–18 Oct)*")
    assert "• Chairman: Kofi Mensah" in text
    assert ": Esi Mensah & Ama Owusu" in text
    assert "• Opening Prayer: —" in text                 # nobody yet
    assert "Wednesday 14 October" in text
    assert "Yaw Adjei" not in text
    assert core.week_overview_text(rows, "2026-11-04").endswith(
        "No meetings are scheduled that week.")


def test_an_assembly_week_shows_on_the_midweek_sheet_and_the_s140(core, people, s140_template):
    """An assembly or convention week is on the midweek printouts too, in its
    place, rather than simply missing."""
    _full_week(core, people)                                  # Wed 16 September
    core.mark_event_week("2026-09-23", "assembly")            # the week after
    rows = core.get_schedules()
    text = _text(core.generate_schedule_pdf([("2026-09-16", core.MIDWEEK)], rows))
    flat = text.replace("\n", " ")
    assert "Assembly Week" in flat
    assert flat.index("16 September") < flat.index("23 September") < flat.index("Assembly Week")

    data, skipped = core.build_s140_data([("2026-09-16", core.MIDWEEK)], rows, "TEST CONG",
                                         ["2026-09"], "English")
    assert not skipped and [w.get("event") for w in data["weeks"]] == [None, "Assembly Week"]
    doc = docx.Document(io.BytesIO(core.fill_s140(s140_template, data)))
    cells = [c.text for r in doc.tables[0].rows for c in r.cells]
    assert "Assembly Week" in cells
    assert "Efua Osei/Ama Owusu" in cells                     # the saved week is whole
    # the assembly week is just its date row: one week's parts, not two
    assert sum("Bible Reading" in c for c in cells) == 1

    # a month with only the assembly week has nothing to fill
    data, _ = core.build_s140_data([], rows, "TEST CONG", ["2026-09"], "English")
    assert data["weeks"] == []
