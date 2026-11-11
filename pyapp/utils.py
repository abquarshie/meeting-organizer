# -*- coding: utf-8 -*-
"""Small text, date and part-slot helpers."""
from datetime import date, datetime, timedelta
import unicodedata

from constants import (
    ASSISTANT_ROLES,
    AUX_HALL,
    AVAILABLE,
    CONFLICT,
    MAIN_HALL,
    MIDWEEK,
    NEVER_BAND,
    PRIVILEGES,
    RESTING,
    STUDENT_ROLES,
    THIS_WEEK,
)
from i18n import part_title as _title, t as _t


# =============================================================================
# SMALL HELPERS
# =============================================================================
def nfc(text):
    return unicodedata.normalize("NFC", text or "").strip()


def fmt_date(iso, short=False):
    try:
        d = datetime.strptime(str(iso), "%Y-%m-%d").date()
    except ValueError:
        return str(iso)
    return f"{d.day} {d:%b}" if short else f"{d.day} {d:%B %Y}"


def month_label(ym):
    """'2026-10' -> 'October 2026'."""
    return datetime.strptime(ym, "%Y-%m").strftime("%B %Y")


def parse_privileges(value):
    """Turn the stored comma string into a clean list."""
    result = []
    for item in (value or "").split(","):
        item = item.strip()
        if item in PRIVILEGES and item not in result:
            result.append(item)
    return result


# Dangme part titles, from the printed workbook (lower case, after workbook.repair_dangme has put back the letters
# its fonts scramble). Checked before the English keywords because a Dangme title matches none of them and would
# otherwise fall through to the section default, making every ministry part the same role. The longer phrases come
# first: "asafo baiblo mi ní kasemi" (the Bible study) also holds "baiblo".
DANGME_ROLE_WORDS = [
    ("asafo baiblo mi ní kasemi", "Bible Study Conductor"),
    ("baiblo kanemi", "Bible Reading"),
    ("ngmami ɔ mi junehi", "Spiritual Gems"),
    ("je ní sɛɛmi sisi", "Initial Presentation"),       # Moo Je Ní Sɛɛmi Sisi: starting a conversation
    ("kpale ya slaa", "Initial Presentation"),          # following up
    ("mɛni o ma de", "Initial Presentation"),           # What Will You Say?
    ("pee nihi kaseli", "Making Disciples"),
    ("tsɔɔ níhi nɛ o heɔ yeɔ mi", "Explaining Beliefs"),
]
# A bare "Munyu Tumi" (Talk) in the ministry section is a student talk.
DANGME_TALK = "munyu tumi"


# English words infer_role() keys on, kept beside the Dangme list so a caller can
# ask whether a title actually named a part type or merely fell through.
EN_ROLE_WORDS = (
    "chairman", "prayer", "reader", "bible study",
    "conductor", "bible reading", "gems", "treasures", "living", "disciple",
    "explaining", "belief", "presentation", "conversation", "following up", "talk",
)


def role_matched(title):
    """True when the title names a part type rather than taking the default."""
    t = nfc(title or "").lower()
    if t.strip(" .:") == DANGME_TALK:
        return True
    if any(word in t for word, _ in DANGME_ROLE_WORDS):
        return True
    return any(word in t for word in EN_ROLE_WORDS)


def infer_role(title, section=None):
    t = nfc(title or "").lower()
    for word, role in DANGME_ROLE_WORDS:
        if word in t:
            return role
    if section == "Ministry" and t.strip(" .:") == DANGME_TALK:   # a student talk
        return "Student Talk"
    if "chairman" in t:
        return "Chairman"
    if "prayer" in t:
        return "Prayer"
    if "reader" in t:
        return "Reader"
    if "bible study" in t or "conductor" in t:
        return "Bible Study Conductor"
    if "bible reading" in t:
        return "Bible Reading"
    if "gems" in t:
        return "Spiritual Gems"
    if "treasures" in t:
        return "Treasures Talk"
    if "living" in t:
        return "Living Part"
    if "disciple" in t:
        return "Making Disciples"
    if "explaining" in t or "belief" in t:
        return "Explaining Beliefs"
    if "presentation" in t or "conversation" in t or "following up" in t:
        return "Initial Presentation"
    if section == "Ministry":
        return "Student Talk" if "talk" in t else "Initial Presentation"
    if section == "Living":
        return "Living Part"
    return "Living Part"


def default_section(role, meeting_type=MIDWEEK):
    if role in ("Chairman", "Aux Classroom Counselor"):
        return "Opening"
    if role in ("Treasures Talk", "Spiritual Gems", "Bible Reading"):
        return "Treasures"
    if role in STUDENT_ROLES:
        return "Ministry"
    return "Living"


def make_slot(title, role, section, part_no=None, minutes=None, hall=MAIN_HALL):
    return {
        "hall": hall or MAIN_HALL,
        "part_no": part_no,
        "title": nfc(title),
        "role": role,
        "section": section,
        "minutes": minutes,
        "student_part": role in STUDENT_ROLES,
        "needs_assistant": role in ASSISTANT_ROLES,
    }


# ---------------------------------------------------------------------------
# Calendar weeks. A meeting week runs Monday to Sunday, as the workbook does,
# so "this week", "last week" and "next week" are fixed periods rather than
# "within 7 days": the Sunday before a Wednesday meeting is last week, the
# Sunday after it is later this week.
# ---------------------------------------------------------------------------
def as_date(value):
    """A date from a date or an ISO string (None if it isn't one)."""
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError:
        return None


def week_start(day):
    """The Monday of the meeting week this day falls in."""
    day = as_date(day)
    return day - timedelta(days=day.weekday())


def weeks_apart(earlier, later):
    """Whole meeting weeks from one date's week to another's (0 = same week)."""
    return (week_start(later) - week_start(earlier)).days // 7


def week_label(day):
    """A fixed name for the meeting week, e.g. "Week 2 of October (5–11 Oct)".

    The week belongs to the month its Monday is in, so the week of
    28 September – 4 October is Week 5 of September; the dates printed beside
    it remove any doubt.
    """
    monday = week_start(day)
    sunday = monday + timedelta(days=6)
    number = (monday.day - 1) // 7 + 1
    span = (f"{monday.day}–{sunday.day} {sunday:%b}" if monday.month == sunday.month
            else f"{monday.day} {monday:%b} – {sunday.day} {sunday:%b}")
    return f"Week {number} of {monday:%B} ({span})"


def relative_week(other, meeting_date, locale="en"):
    """How another date's week relates to this meeting's week, in words:
    "this week", "last week", "next week", "3 weeks ago", "in 2 weeks"."""
    n = weeks_apart(meeting_date, other)
    if n == 0:
        return _t("date.this_week", locale)
    if n == -1:
        return _t("date.last_week", locale)
    if n == 1:
        return _t("date.next_week", locale)
    return _t("date.weeks_ago", locale, count=-n) if n < 0 else _t("date.in_weeks", locale, count=n)


def recency(last_date, meeting_date=None, locale="en"):
    """(marker, wording) for when someone last had a part, in meeting weeks
    before the meeting being scheduled.

    Counted from that meeting rather than from today: working on Week 3 of
    October, "last week" means Week 2 of October whenever you open it.
    """
    then = as_date(last_date) if last_date else None
    now = as_date(meeting_date) if meeting_date else date.today()
    if then is None or now is None:
        return NEVER_BAND[0], _t("rot.never", locale)
    if then > now:
        return CONFLICT[0], conflict_wording(then, now, locale)
    weeks = weeks_apart(then, now)
    if weeks == 0:
        return THIS_WEEK[0], _t("rot.resting", locale)
    if weeks == 1:
        return RESTING, _t("date.last_week", locale)
    return AVAILABLE, (_t("date.weeks_ago", locale, count=weeks) if weeks <= 4
                       else _t("rot.over_month", locale))


def conflict_wording(when, meeting_date, locale="en"):
    """How far after this meeting another assignment falls, with its date.

    Orange on its own only says "later"; whether that is this weekend or a
    month away changes whether it matters, so the wording spells it out.
    """
    when = as_date(when)
    span = (_t("sched.later_this_week", locale) if weeks_apart(meeting_date, when) == 0
            else relative_week(when, meeting_date, locale))
    return f"{_t('rot.conflict', locale)} {span} ({fmt_date(when.isoformat(), short=True)})"


def slot_label(slot, hall_names=None, locale="en"):
    """hall_names lets printed output name the room in the slip language;
    the interface passes its locale for the room names and the minutes."""
    label = _title(slot["title"], locale)
    if slot.get("minutes") and "min" not in label.lower() and "hɛngm" not in label.lower():
        label += " " + _t("part.minutes", locale, count=slot["minutes"])
    label = f"{slot['part_no']}. {label}" if slot.get("part_no") else label
    hall = slot.get("hall") or MAIN_HALL
    if hall != MAIN_HALL:
        names = hall_names or {"aux_1": _t("hall.aux1", locale), "aux_2": _t("hall.aux2", locale)}
        label += f" · {names.get(hall, hall)}"
    return label


def slot_match_key(slot):
    """Used to carry names across when the parts list is swapped."""
    hall = slot.get("hall") or MAIN_HALL
    if slot.get("part_no"):
        return (hall, slot["role"], slot["part_no"])
    return (hall, slot["role"], slot["title"].lower())


def apply_aux(slots, aux_on):
    """Add (or strip) the auxiliary-classroom counselor and a second slot per student part."""
    base = [s for s in slots
            if s.get("hall", MAIN_HALL) == MAIN_HALL and s["role"] != "Aux Classroom Counselor"]
    if not aux_on:
        return base
    out = []
    for s in base:
        out.append(s)
        if s["role"] == "Chairman":
            out.append(make_slot("Auxiliary Classroom Counselor",
                                 "Aux Classroom Counselor", s["section"]))
        if s["student_part"]:
            out.append(make_slot(s["title"], s["role"], s["section"],
                                 s["part_no"], s.get("minutes"), hall=AUX_HALL))
    return out


def fill_progress(slots, picks):
    """(filled, needed) for the parts on the page, counted slot by slot.

    picks holds (person, assistant) under each slot's index.
    """
    needed = filled = 0
    for i, slot in enumerate(slots):
        sid, aid = picks.get(i, (None, None))
        needed += 1
        filled += int(sid is not None)
        if slot["needs_assistant"]:
            needed += 1
            filled += int(aid is not None)
    return filled, needed

