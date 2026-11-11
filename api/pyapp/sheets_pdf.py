# -*- coding: utf-8 -*-
"""Printable schedule sheets and the data the S-140 filler needs."""
from datetime import date, datetime, timedelta
import io
from pathlib import Path
import re
from xml.sax.saxutils import escape as xml_escape

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.fonts import addMapping
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
import streamlit as st

from constants import (
    APP_DIR,
    AUX_HALL,
    HALLS,
    MAIN_HALL,
    MIDWEEK,
    ROLE_LABELS,
    SECTION_COLORS,
    SPECIAL_CHARS,
    STUDENT_ROLES,
    TRANSLATIONS,
    WORDS,
)
from db import (
    meeting_rows,
    event_for,
    event_label,
    event_text,
    event_weeks,
    get_meeting_meta,
    get_setting,
)
from i18n import doc, locale_for, part_title, section_label, t as _t
from utils import fmt_date, week_start
from workbook import meeting_day

# =============================================================================
# PDF OUTPUT
# =============================================================================
FONT_DIR = APP_DIR / "fonts"
FONT_CANDIDATES = [
    (APP_DIR / "DejaVuSans.ttf", APP_DIR / "DejaVuSans-Bold.ttf"),
    (FONT_DIR / "DejaVuSans.ttf", FONT_DIR / "DejaVuSans-Bold.ttf"),
    (FONT_DIR / "NotoSans-Regular.ttf", FONT_DIR / "NotoSans-Bold.ttf"),
    (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
     Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")),
    (Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"), None),
    (Path("/Library/Fonts/Arial Unicode.ttf"), None),
    (Path("C:/Windows/Fonts/arial.ttf"), Path("C:/Windows/Fonts/arialbd.ttf")),
]


def _load_font(name, path):
    """Register a TTF only if it has ɛ, ɔ and ŋ."""
    if not path or not path.exists():
        return False
    try:
        font = TTFont(name, str(path))
    except Exception:
        return False
    if not all(ord(c) in font.face.charToGlyph for c in SPECIAL_CHARS):
        return False
    pdfmetrics.registerFont(font)
    return True


@st.cache_resource
def register_fonts():
    """Returns (regular, bold, has_special_letters)."""
    for regular, bold in FONT_CANDIDATES:
        if _load_font("SlipFont", regular):
            bold_name = "SlipFont-Bold" if _load_font("SlipFont-Bold", bold) else "SlipFont"
            addMapping("SlipFont", 0, 0, "SlipFont")
            addMapping("SlipFont", 1, 0, bold_name)
            addMapping("SlipFont", 0, 1, "SlipFont")
            addMapping("SlipFont", 1, 1, bold_name)
            return "SlipFont", bold_name, True
    return "Helvetica", "Helvetica-Bold", False


def section_titles(language):
    """The section headings in a slip language, as the printed workbook has them (messages, "sec." keys)."""
    locale = locale_for(language)
    return {name: section_label(name, locale) for name in ("Opening", "Treasures", "Ministry", "Living", "Closing")}


ACCENT = colors.HexColor("#5A4569")          # the app's muted plum
MUTED = colors.HexColor("#6B7683")
RULE = colors.HexColor("#D7DBE0")


def _lang_name(lang):
    """The slip language ("English" or "Dangme") of a TRANSLATIONS entry."""
    return (lang or {}).get("_language", "English")


# Compact mode never shrinks the type. Two ordinary weeks fit on one A4 at full
# size once the banner stops repeating and the row padding tightens. A week
# with an auxiliary classroom will not: its paired names wrap in the two narrow
# name columns, which makes it about a third taller. Those weeks print one to a
# page rather than being reduced to fit.
COMPACT_ROW_PAD = 1.5
COMPACT_PER_PAGE = 2          # ordinary weeks per sheet; classroom weeks get one


def _sheet_styles(regular, bold, compact=False):
    """One place for the look of the midweek sheet. compact tightens the
    spacing so two weeks share an A4; it never shrinks the type."""
    line = 12 * 0.98 if compact else 12

    def style(name, size, leading, font=regular, **kw):
        return ParagraphStyle(name, fontName=font, fontSize=size, leading=leading, **kw)

    return {
        "title": style("T", 16, 19, bold),
        "cong": style("C", 11, 19, bold, alignment=TA_RIGHT, textColor=MUTED),
        "when": style("W", 11.5, 15, bold, textColor=ACCENT,
                      spaceBefore=5 if compact else 10, spaceAfter=2 if compact else 3),
        "section": style("S", 12, 16, bold),
        "part": style("P", 9, line, leftIndent=11, firstLineIndent=-11),
        "name": style("N", 9, line),
        "label": style("L", 8, line, bold, alignment=TA_RIGHT, textColor=MUTED),
        "_compact": compact,
    }


def clean_value(value):
    """'' for None, NaN and blanks. NaN is truthy, so `or` alone is not enough."""
    if value is None or value != value:
        return ""
    return str(value).strip()


UNFILLED = "\u2014"          # an em dash: nobody assigned yet


def _people(person, assistant):
    """The name, or a dash when the part has nobody.

    A blank cell reads as a fault in the sheet rather than as a part still to
    be filled, and these go up on a noticeboard.
    """
    person, assistant = clean_value(person), clean_value(assistant)
    if person and assistant:
        return f"{person} & {assistant}"
    return person or UNFILLED


def midweek_widths(width):
    """Column widths for the midweek sheet: part, role label, name.

    One set for every week now that the classroom has its own section rather
    than a second name column — which is what used to squeeze the part title
    into a fifth of the page.
    """
    return [width * 0.54, width * 0.13, width * 0.33]


def _song_text(value, words):
    """"Song 74" is stored from an English workbook and "La 74" from a Dangme one;
    print whichever word matches the sheet."""
    text = clean_value(value)
    if not text:
        return ""
    found = re.search(r"\d+", text)
    return f"{words['song']} {found.group()}" if found else text


def _has_minutes(title):
    low = title.lower()
    return "min" in low or "hɛngm" in low


def _part_text(part_name, minutes, language="English"):
    """The part as the sheet prints it, e.g. "Bible Reading (4 min.)". The app's own fixed titles are put into
    the slip language; a workbook's titles are printed as the workbook has them."""
    title = part_title(clean_value(part_name), locale_for(language))
    try:
        mins = int(float(minutes))
    except (TypeError, ValueError):
        mins = None
    if mins and not _has_minutes(title):
        title += " " + doc("doc.minutes", language, count=mins)
    return title


def _banner(meeting_name, congregation, width, st_):
    return Table(
        [[Paragraph(xml_escape(meeting_name), st_["title"]),
          Paragraph(xml_escape(congregation), st_["cong"])]],
        colWidths=[width * 0.62, width * 0.38],
        style=[("LEFTPADDING", (0, 0), (-1, -1), 0),
               ("RIGHTPADDING", (0, 0), (-1, -1), 0),
               ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
               ("LINEBELOW", (0, 0), (-1, -1), 1.4, ACCENT)])


def _midweek_block(rows, meta, lang, st_, width, titles, hall_names,
                   role_labels, words):
    """The running order: sections in their workbook colours, songs in place.

    The auxiliary classroom has its own short section at the end rather than a
    second name column beside every student part. The parallel columns put two
    names side by side with nothing on the row saying which room each belonged
    to, and were narrow enough that paired names wrapped. It costs a little
    height, which is affordable now that a classroom week has its own sheet.
    """
    tight = st_.get("_compact")
    row_pad = COMPACT_ROW_PAD if tight else 2.5
    data, style = [], [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), row_pad),
        ("BOTTOMPADDING", (0, 0), (-1, -1), row_pad),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]

    def row(part="", label="", name="", colour=None):
        left = Paragraph(
            (f'<font color="{colour}">\u25cf</font> ' if colour and part else "")
            + xml_escape(part), st_["part"]) if part else ""
        data.append([
            left,
            Paragraph(xml_escape(label), st_["label"]) if label else "",
            Paragraph(xml_escape(name), st_["name"]) if name else ""])

    def section(title, colour):
        data.append([Paragraph(
            f'<font color="{colour}">\u25a0</font>&nbsp;&nbsp;'
            f'<font color="{colour}">{xml_escape(title)}</font>',
            st_["section"]), "", ""])
        i = len(data) - 1
        style.extend([("SPAN", (0, i), (-1, i)),
                      ("TOPPADDING", (0, i), (-1, i), 5 if tight else 10)])

    by_section = {}
    for r in rows.itertuples():
        by_section.setdefault(r.section or "", []).append(r)
    opening = by_section.get("Opening", [])
    closing = by_section.get("Closing", [])
    open_prayer = next((r for r in opening if r.role == "Prayer"), None)
    close_prayer = next((r for r in closing if r.role == "Prayer"), None)
    counselor = next((r for r in opening
                      if r.role == "Aux Classroom Counselor"), None)
    song_colour = SECTION_COLORS.get("Living", "#8A94A0")

    if meta.get("opening_song") or open_prayer is not None:
        row(_song_text(meta.get("opening_song"), words),
            role_labels.get("Prayer", ""),
            (clean_value(open_prayer.person) or UNFILLED)
            if open_prayer is not None else "",
            colour=song_colour)
    for r in opening:
        # the counselor belongs with the classroom's own section below
        if r.role not in ("Prayer", "Aux Classroom Counselor"):
            row("", role_labels.get(r.role, ""), clean_value(r.person) or UNFILLED)

    # the classroom's parts are gathered up front so its section can sit with
    # the field ministry, where those parts belong, rather than at the very end
    classroom = sorted((r for r in rows.itertuples() if r.hall != MAIN_HALL),
                       key=lambda x: int(x.sort_order or 0))

    def classroom_section():
        title = hall_names.get(AUX_HALL, "")
        group = clean_value(meta.get("aux_group"))
        if group:
            title = f"{title} \u2013 {words['group']} {group}"
        colour = SECTION_COLORS.get("Ministry", "#8A94A0")
        section(title, colour)
        if counselor is not None:
            row("", role_labels.get("Aux Classroom Counselor", ""),
                clean_value(counselor.person) or UNFILLED)
        for r in classroom:
            row(_part_text(r.part_name, r.minutes, _lang_name(lang)), "",
                _people(r.person, r.assistant), colour=colour)

    shown = False
    for name in ("Treasures", "Ministry", "Living"):
        members = by_section.get(name)
        if not members:
            continue
        colour = SECTION_COLORS.get(name, "#8A94A0")
        section(titles.get(name, name), colour)
        if name == "Living" and meta.get("middle_song"):
            row(_song_text(meta["middle_song"], words), colour=song_colour)
        for r in members:
            if r.hall != MAIN_HALL:
                continue
            row("" if r.role == "Reader" else _part_text(r.part_name, r.minutes, _lang_name(lang)),
                role_labels.get(r.role, ""), _people(r.person, r.assistant),
                colour=colour)
        if name == "Ministry" and classroom and not shown:
            classroom_section()
            shown = True

    if meta.get("closing_song") or close_prayer is not None:
        row(_song_text(meta.get("closing_song"), words),
            role_labels.get("Prayer", ""),
            (clean_value(close_prayer.person) or UNFILLED)
            if close_prayer is not None else "",
            colour=song_colour)

    if counselor is not None and not classroom:
        row("", role_labels.get("Aux Classroom Counselor", ""),
            clean_value(counselor.person) or UNFILLED)
    elif classroom and not shown:          # no ministry section on this week
        classroom_section()

    table = Table(data, colWidths=midweek_widths(width))
    table.setStyle(TableStyle(style))
    return table


def generate_schedule_pdf(meetings, schedules_df, lang=None, compact=False):
    """The printable schedule: a sheet per midweek meeting (its running order). lang is a TRANSLATIONS entry; None
    means English. compact puts two weeks on one A4."""
    midweek = sorted(m for m in meetings if m[1] == MIDWEEK)
    return _midweek_pdf(midweek, schedules_df, lang, compact)


def _midweek_pdf(meetings, schedules_df, lang=None, compact=False):
    """A sheet per midweek meeting: its running order, section by section."""
    lang = lang or TRANSLATIONS["English"]
    name = _lang_name(lang)
    titles = section_titles(name)
    role_labels = ROLE_LABELS[name]
    words = WORDS[name]
    hall_names = {h: lang.get(h, h) for h in HALLS}

    regular, bold, _ = register_fonts()
    buffer = io.BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=36, leftMargin=36,
                                 topMargin=36, bottomMargin=36)
    st_ = _sheet_styles(regular, bold, compact)
    width = A4[0] - 72
    congregation = get_setting("congregation", "")
    story = []

    def uses_classroom(meeting_date, meeting_type):
        rows = meeting_rows(schedules_df, meeting_date, meeting_type)
        return bool((rows["hall"] != MAIN_HALL).any())

    def sheets(items):
        """Meetings grouped into printed sheets.

        Without compact, one per sheet as before. With it, ordinary midweek
        weeks pair up and a classroom week takes a sheet of its own — at full
        size either way, because shrinking one to fit costs more than the page.
        """
        if not compact:
            # a sheet each unless two-up is asked for: that is what the
            # checkbox is choosing between
            return [[m] for m in items]
        out, current = [], []
        for m in items:
            if m[1] == MIDWEEK and uses_classroom(*m):
                if current:
                    out.append(current)
                    current = []
                out.append([m])
                continue
            current.append(m)
            if len(current) == COMPACT_PER_PAGE:
                out.append(current)
                current = []
        if current:
            out.append(current)
        return out

    event_style = ParagraphStyle("E", parent=st_["section"], fontSize=13, leading=17,
                                 textColor=ACCENT)
    midweek_name = lang.get("midweek_meeting", MIDWEEK)
    def with_events(groups, events):
        """An assembly or convention week is a line, not a sheet: it rides on
        the sheet before it (or the first one, when it comes first)."""
        if not groups:
            return [events] if events else []
        for day, kind in events:
            target = next((g for g in reversed(groups) if g[0][0] < day), groups[0])
            target.append((day, kind))
            target.sort()
        return groups

    everything = with_event_days(meetings, MIDWEEK)
    held = [m for m in everything if not m[1].startswith(EVENT)]
    events = [m for m in everything if m[1].startswith(EVENT)]
    for page_number, page_meetings in enumerate(with_events(sheets(held), events)):
        if page_number:
            story.append(PageBreak())
        banner_shown = None      # each sheet is headed by the meeting name
        for meeting_date, meeting_type in page_meetings:
            if meeting_type.startswith(EVENT):
                # an assembly or convention week: its date and label in its place
                block = []
                if midweek_name != banner_shown:
                    block.append(_banner(midweek_name, congregation, width, st_))
                    banner_shown = midweek_name
                block += [Paragraph(xml_escape(fmt_date(meeting_date)), st_["when"]),
                          Paragraph(xml_escape(event_text(meeting_type[len(EVENT):], name)),
                                    event_style),
                          Spacer(1, 10 if compact else 18)]
                story.append(KeepTogether(block))
                continue
            rows = meeting_rows(schedules_df, meeting_date, meeting_type)
            if rows.empty:
                continue
            meta = get_meeting_meta(meeting_date, meeting_type)
            meeting_name = midweek_name
            # the meeting name and congregation head the sheet once, not once per
            # week; a document with both kinds gets one banner for each kind
            block = []
            if meeting_name != banner_shown:
                block.append(_banner(meeting_name, congregation, width, st_))
                banner_shown = meeting_name
            heading = clean_value(meta.get("book")) or clean_value(meta.get("heading"))
            when = fmt_date(meeting_date)
            block.append(Paragraph(
                xml_escape(when) + (f"&nbsp;&nbsp;|&nbsp;&nbsp;{xml_escape(heading)}"
                                    if heading else ""), st_["when"]))
            block.append(_midweek_block(rows, meta, lang, st_, width,
                                        titles, hall_names, role_labels,
                                        words))
            block.append(Spacer(1, 10 if compact else 18))
            story.append(KeepTogether(block))

    # two versions of a week look identical on a noticeboard otherwise
    story.append(Paragraph(
        xml_escape(doc("doc.prepared", name, date=fmt_date(date.today().isoformat()))),
        ParagraphStyle("Made", fontName=regular, fontSize=7, leading=9,
                       textColor=MUTED, alignment=TA_RIGHT)))
    document.build(story)
    return buffer.getvalue()


EVENT = "event:"     # the meeting type given to an assembly/convention week


def event_days(months, meeting_type):
    """[(date, kind)] for the day this meeting would have fallen in every
    assembly or convention week, within these months ("YYYY-MM")."""
    offset = timedelta(days=meeting_day(meeting_type))
    out = []
    for monday, kind in event_weeks().items():
        day = (datetime.strptime(monday, "%Y-%m-%d").date() + offset).isoformat()
        if day[:7] in months:
            out.append((day, kind))
    return sorted(out)


def with_event_days(meetings, meeting_type):
    """The meetings plus, in date order, this meeting's day in every
    assembly or convention week falling in the same months — as
    (date, "event:assembly") — so the week reads as its label rather than
    simply missing. A meeting saved inside such a week is left out."""
    meetings = [m for m in meetings if not event_for(m[0])]
    months = {d[:7] for d, _ in meetings}
    meetings += [(day, EVENT + kind) for day, kind in event_days(months, meeting_type)]
    return sorted(meetings)


def build_s140_data(meetings, schedules_df, congregation, months=None, language="English"):
    """Shape saved midweek meetings like the S-140 filler's data.json.

    With months ("YYYY-MM"), every assembly or convention week in them is
    added in its place as a week holding just its date and label."""
    weeks, skipped = [], []
    events = dict(event_days(set(months), MIDWEEK)) if months else {}
    meetings = sorted([m for m in meetings if not (events and event_for(m[0]))]
                      + [(d, EVENT + k) for d, k in events.items()])
    for meeting_date, meeting_type in meetings:
        if meeting_type.startswith(EVENT):
            weeks.append({"heading": fmt_date(meeting_date).upper(),
                          "event": event_text(meeting_type[len(EVENT):], language),
                          "aux": False})
            continue
        rows = meeting_rows(schedules_df, meeting_date, meeting_type)
        meta = get_meeting_meta(meeting_date, meeting_type)
        week = {
            "heading": meta.get("heading") or fmt_date(meeting_date).upper(),
            "chairman": "", "opening_prayer": "", "closing_prayer": "",
            "opening_song": meta.get("opening_song") or "",
            "middle_song": meta.get("middle_song") or "",
            "closing_song": meta.get("closing_song") or "",
            "treasures": [], "ministry": [], "living": [],
        }
        reader = ""
        main_items = {}
        aux_week = bool(meta.get("aux")) or (rows["hall"] != MAIN_HALL).any()
        for _, r in rows.iterrows():
            title = re.sub(r"\s*\(\s*(\d+\s*min\.?|hɛngm\.?\s*\d+)\s*\)\s*$", "",
                           part_title(r["part_name"] or "", locale_for(language)), flags=re.IGNORECASE)
            item = {"title": title,
                    "min": str(int(r["minutes"])) if pd.notna(r["minutes"]) else "",
                    "name": r["person"] or ""}
            role, section = r["role"], r["section"]
            if r["hall"] != MAIN_HALL:
                target = main_items.get((role, r["part_no"]))
                if target is not None:
                    target["name2"] = item["name"]
                    if r["assistant"]:
                        target["assistant2"] = r["assistant"]
                continue
            if role in STUDENT_ROLES:
                main_items[(role, r["part_no"])] = item
            if role == "Aux Classroom Counselor":
                week["aux_counselor"] = item["name"]
            elif role == "Chairman":
                week["chairman"] = item["name"]
            elif role == "Prayer":
                key = "closing_prayer" if section == "Closing" else "opening_prayer"
                week[key] = item["name"]
            elif role == "Reader":
                reader = item["name"]
            elif role == "Bible Study Conductor":
                week["cbs"] = item
            elif section == "Treasures":
                week["treasures"].append(item)
            elif section == "Ministry":
                if r["assistant"]:
                    item["assistant"] = r["assistant"]
                week["ministry"].append(item)
            elif section == "Living":
                week["living"].append(item)
        if "cbs" in week and reader:
            week["cbs"]["name"] = f"{week['cbs']['name']}/{reader}"
        if "cbs" not in week or len(week["treasures"]) != 3:
            skipped.append(meeting_date)
            continue
        week["aux"] = bool(aux_week)
        week["aux_group"] = clean_value(meta.get("aux_group"))
        weeks.append(week)
    if all("event" in w for w in weeks):
        weeks = []          # nothing saved: an S-140 of only labels isn't a schedule
    any_aux = any(w["aux"] for w in weeks)
    # "aux" keeps the auxiliary-classroom column (its caption and width)
    return {"congregation": congregation, "weeks": weeks, "aux": any_aux, "language": language}, skipped


# =============================================================================
# MESSAGES (the share cards and the WhatsApp text), in the slip language
# =============================================================================
def week_label_in(day, locale="en"):
    """"Week 2 of October (5–11 Oct)", in a locale, as utils.week_label gives it in English."""
    monday = week_start(day)
    sunday = monday + timedelta(days=6)
    number = (monday.day - 1) // 7 + 1
    span = (f"{monday.day}–{sunday.day} {sunday:%b}" if monday.month == sunday.month
            else f"{monday.day} {monday:%b} – {sunday.day} {sunday:%b}")
    return _t("date.week_of", locale, n=number, month=_month_name(monday.month, locale), dates=span)


_MONTH_KEYS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
_DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _month_name(month, locale="en"):
    return _t(f"mname.{_MONTH_KEYS[month - 1]}", locale)


def month_name_in(ym, locale="en"):
    """'2026-10' -> 'October 2026', in a locale."""
    d = datetime.strptime(ym, "%Y-%m")
    return f"{_month_name(d.month, locale)} {d.year}"


def _part_title(r, language="English"):
    """How a schedule row's part reads in a message: "5. Making Disciples (4 min)", "Chairman"."""
    locale = locale_for(language)
    title = part_title(clean_value(r.part_name) or clean_value(r.role), locale)
    minutes = int(r.minutes) if pd.notna(r.minutes) else None
    if minutes and not _has_minutes(title):
        title += " " + _t("part.minutes", locale, count=minutes)
    if pd.notna(r.part_no):
        title = f"{int(r.part_no)}. {title}"
    return title


def assignments_between(schedules_df, student_id, start, end, language="English"):
    """One person's parts from start to end (ISO dates, both included), in
    meeting order.

    Matched on the participant's id, not the printed name, so two people
    with the same name are never merged. Parts where they assist count too:
    the assistant needs to prepare as much as the student.
    """
    dates = schedules_df["meeting_date"].astype(str)
    rows = schedules_df[(dates >= str(start)) & (dates <= str(end))
                        & ((schedules_df["student_id"] == student_id)
                           | (schedules_df["assistant_id"] == student_id))]
    rows = rows.sort_values(["meeting_date", "meeting_type", "sort_order"])
    out = []
    for r in rows.itertuples():
        as_assistant = r.assistant_id == student_id and r.student_id != student_id
        hall = r.hall if isinstance(r.hall, str) else MAIN_HALL
        out.append({
            "meeting_date": str(r.meeting_date),
            "meeting_type": r.meeting_type,
            "part": _part_title(r, language),
            "hall": hall,
            "as_assistant": as_assistant,
            "partner": clean_value(r.person if as_assistant else r.assistant),
            "section": clean_value(getattr(r, "section", "")),
        })
    return out


def month_assignments_for(schedules_df, student_id, month, language="English"):
    """One person's parts in a month ("YYYY-MM"), in meeting order."""
    return assignments_between(schedules_df, student_id, f"{month}-01",
                               f"{month}-31", language)


def _meeting_heading(meeting_date, language="English"):
    """*Wednesday 14 October* · Midweek meeting — WhatsApp shows *text* bold.

    No calendar emoji: it pictures a fixed date ("JUL 17" on an iPhone) that
    sits misleadingly beside the real one.
    """
    locale = locale_for(language)
    d = datetime.strptime(meeting_date, "%Y-%m-%d").date()
    day = _t(f"day.{_DAY_KEYS[d.weekday()]}", locale)
    return f"*{day} {d.day} {_month_name(d.month, locale)}* · {_t('mt.midweek_lower', locale)}"


def _assignment_lines(items, language="English"):
    """One person's assignments, grouped under each meeting's heading."""
    lang = TRANSLATIONS.get(language, TRANSLATIONS["English"])
    lines, current = [], None
    for item in items:
        key = item["meeting_date"]
        if key != current:
            current = key
            lines += ["", _meeting_heading(key, language)]
        line = f"• {item['part']}"
        if item["hall"] != MAIN_HALL:
            line += f" · {lang.get(item['hall'], item['hall'])}"
        if item["as_assistant"]:
            line += (" " + doc("msg.assisting", language, name=item["partner"]) if item["partner"]
                     else " " + doc("msg.as_assistant", language))
        elif item["partner"]:
            line += " " + doc("msg.with_assisting", language, name=item["partner"])
        lines.append(line)
    return lines


def _personal_message(person, gender, period, items, language="English"):
    """Hello …, the assignments for the period, and a request to say early if
    one can't be taken. Copy-paste only — nothing is sent on the app's behalf."""
    title = doc("cat.sister" if gender == "Sister" else "cat.brother", language)
    if not items:
        return doc("msg.month_none", language, title=title, name=person, month=period)
    count = len(items)
    return "\n".join(
        [doc("msg.month_hello", language, title=title, name=person, month=period)]
        + _assignment_lines(items, language)
        + ["", doc("msg.month_count_one", language) if count == 1
           else doc("msg.month_count_many", language, count=count)])


def whatsapp_month_text(person, gender, month, items, language="English"):
    """A month of one person's assignments as a WhatsApp message, in the slip language."""
    return _personal_message(person, gender, month_name_in(month, locale_for(language)), items, language)


def week_overview_text(schedules_df, week_of, language="English"):
    """Every assignment in the meeting week (Monday to Sunday), as the one message sent for that week, in the slip
    language. A part nobody has yet shows "—"."""
    locale = locale_for(language)
    lang = TRANSLATIONS.get(language, TRANSLATIONS["English"])
    monday = week_start(week_of)
    lines = [doc("msg.week_title", language, week=week_label_in(week_of, locale))]
    special = event_label(monday, language)   # in the slip language
    if special:              # an assembly or convention week: no meetings to list
        return "\n".join(lines + ["", special])
    dates = schedules_df["meeting_date"].astype(str)
    rows = schedules_df[(dates >= monday.isoformat())
                        & (dates <= (monday + timedelta(days=6)).isoformat())
                        & (schedules_df["meeting_type"] == MIDWEEK)]
    rows = rows.sort_values(["meeting_date", "sort_order"])
    for meeting_date, meeting in rows.groupby("meeting_date", sort=False):
        lines += ["", _meeting_heading(str(meeting_date), language)]
        for r in meeting.itertuples():
            hall = r.hall if isinstance(r.hall, str) else MAIN_HALL
            part = _part_title(r, language)
            if hall != MAIN_HALL:
                part += f" · {lang.get(hall, hall)}"
            who = clean_value(r.person) or UNFILLED
            if clean_value(r.assistant):
                who += f" & {clean_value(r.assistant)}"
            lines.append(f"• {part}: {who}")
    if len(lines) == 1:
        lines.append(doc("doc.no_meetings_week", language))
    return "\n".join(lines)
