# -*- coding: utf-8 -*-
"""The WhatsApp cards: what they say, and that they draw."""
import io
from datetime import date, timedelta

from PIL import Image

import card_image as ci


def _png_size(png):
    return Image.open(io.BytesIO(png)).size


def _week(core, people):
    """Midweek 14 Oct, with the classroom on."""
    names = dict(zip(core.get_students()["id"], core.get_students()["name"]))
    mid = core.apply_aux(core.build_midweek_slots(core.default_midweek_parts()), True)
    picks = {}
    for i, s in enumerate(mid):
        if s["role"] == "Chairman":
            picks[i] = (people["Kofi Mensah"], None)
        elif s["role"] == "Initial Presentation" and s["hall"] == core.MAIN_HALL:
            picks[i] = (people["Ama Owusu"], people["Efua Osei"])
        elif s["role"] == "Bible Reading" and s["hall"] != core.MAIN_HALL:
            picks[i] = (people["Kojo Mensah"], None)
        elif s["role"] == "Bible Study Conductor":
            picks[i] = (people["Kofi Mensah"], None)
        elif s["role"] == "Reader":
            picks[i] = (people["Nii Tetteh"], None)
    core.save_schedule("2026-10-14", core.MIDWEEK, mid, picks,
                       {"book": "YEREMIA 34-36", "opening_song": "La 76",
                        "aux": True}, names)
    return core.get_schedules()


def test_week_card_says_every_part(core, people):
    core.set_setting("congregation", "Ada Foah")
    spec = ci.week_card_spec(_week(core, people), "2026-10-16")
    assert spec["congregation"] == "Ada Foah"
    assert "Week 2 of October" in spec["subtitle"]
    (mid,) = spec["meetings"]
    assert mid["eyebrow"] == "WEDNESDAY · 14 OCTOBER"
    assert mid["title"] == "Midweek Meeting"
    assert mid["detail"] == "YEREMIA 34-36 · Song 76"      # the sheet's song word
    rows = {(r["part"], r["room"]): r for s in mid["sections"] for r in s["rows"]}
    assert rows[("Chairman", "")]["who"] == "Kofi Mensah"
    assert rows[("4. Initial Presentation (3 min)", "")]["who"] == \
        "Ama Owusu & Efua Osei"
    assert rows[("3. Bible Reading (4 min)", "Aux 1")]["who"] == "Kojo Mensah"
    assert rows[("5. Making Disciples (4 min)", "")]["who"] == ""   # shows —
    # the study's reader is a note under the conductor, not a row of its own
    study = rows[("8. Congregation Bible Study (30 min)", "")]
    assert study["note"] == "Reader: Nii Tetteh"
    # the closing prayer ends Living rather than a section of one row
    assert [s["key"] for s in mid["sections"]] == \
        ["Opening", "Treasures", "Ministry", "Living"]
    assert spec["chip"]

    png = ci.render_card(spec)
    width, height = _png_size(png)
    assert width == 1440 and height > 1200


def test_week_card_headings_follow_the_slip_language(core, people):
    spec = ci.week_card_spec(_week(core, people), "2026-10-16", "Dangme")
    (mid,) = spec["meetings"]
    assert mid["title"] == "Otsi ɔ Mi Kpe"
    assert [s["title"] for s in mid["sections"]][:2] == \
        ["Munyu Nɛ A Kɛ Ma Bli Kpe ɔ Nya", "Juetli Nɛ Ngɛ Mawu Munyu ɔ Mi"]
    parts = [r["part"] for s in mid["sections"] for r in s["rows"]]
    assert "Sɛnɔhilɔ" in parts
    assert "La 76" in mid["detail"]
    assert _png_size(ci.render_card(spec))[0] == 1440


def test_an_assembly_week_and_an_empty_week(core, people):
    core.mark_event_week("2026-10-14", "convention")
    spec = ci.week_card_spec(core.get_schedules(), "2026-10-14")
    assert [m["title"] for m in spec["meetings"]] == ["Convention Week"]
    assert not spec["meetings"][0]["sections"]
    ci.render_card(spec)
    ci.render_card(ci.week_card_spec(core.get_schedules(), "2026-10-14", "Dangme"))

    empty = ci.week_card_spec(core.get_schedules(), "2026-11-04")
    assert empty["meetings"] == [] and empty["empty"]
    ci.render_card(empty)


def test_person_card(core, people):
    rows = _week(core, people)
    items = core.month_assignments_for(rows, people["Efua Osei"], "2026-10")
    spec = ci.person_card_spec("Efua Osei", "Sister", "2026-10", items)
    assert spec["title"] == "Hello, Sister Efua Osei"
    assert spec["subtitle"] == "Your meeting assignments · October 2026"
    assert spec["chip"] == "1 assignment"
    (tile,) = spec["tiles"]
    assert (tile["day"], tile["month"]) == ("14", "OCT")
    assert tile["sub"] == "assisting Ama Owusu"
    assert tile["section"] == "Ministry"          # its colour on the date block

    kofi = core.month_assignments_for(rows, people["Kofi Mensah"], "2026-10", "Dangme")
    ada = ci.person_card_spec("Kofi Mensah", "Brother", "2026-10", kofi, "Dangme")
    assert "Kofi Mensah" in ada["title"]
    assert all("OTSI Ɔ MI KPE" in t["eyebrow"] for t in ada["tiles"])
    width, _ = _png_size(ci.render_card(ada))
    assert width == 1440


def test_long_names_and_titles_wrap_instead_of_running_off(core):
    long = "Kwa Je Lɛŋ Yaka Yiŋsusumɔi Lɛ, Dii Maŋtsɛyeli Lɛ He Nibii Ni Yɔɔ Diɛŋtsɛ"
    spec = {"kind": "week", "congregation": "A Congregation With A Very Long Name Indeed",
            "title": "Meeting assignments", "subtitle": "Week 1", "chip": "",
            "empty": "", "footer": ["a", "b"],
            "meetings": [{"eyebrow": "X", "title": "Midweek Meeting", "detail": long,
                          "sections": [{"key": "Ministry", "title": "Ministry",
                                        "rows": [{"part": long, "room": "Aux 1",
                                                  "who": "Naa Ayeley Quaye & "
                                                         "Theophilus Quarcoo-Mensah",
                                                  "note": ""}]}]}]}
    part, who, _, _ = ci._row_layout(spec["meetings"][0]["sections"][0]["rows"][0],
                                     ci.S(360), ci.S(260))
    assert len(part) > 1
    assert who[0].endswith("&")                   # the pair breaks at "&"
    ci.render_card(spec)
