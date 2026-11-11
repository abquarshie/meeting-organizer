# -*- coding: utf-8 -*-
"""Fixed lists, roles and slip wording."""
from pathlib import Path

from i18n import doc

# =============================================================================
# CONSTANTS
# =============================================================================
APP_DIR = Path(__file__).resolve().parent
# Storage is Postgres; see db.dsn() and db.schema() for how it is configured.

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

MIDWEEK = "Midweek Meeting"
MEETING_TYPES = [MIDWEEK]

CATEGORIES = ["Brother", "Sister"]
GROUPS = ["Child", "Youth", "New student"]
GROUP_TAGS = {"Child": "child", "Youth": "youth", "New student": "new"}

PRIVILEGES = [
    "Chairman",
    "Prayer",
    "Treasures Talk",
    "Spiritual Gems",
    "Bible Reading",
    "Initial Presentation",
    "Making Disciples",
    "Explaining Beliefs",
    "Student Talk",
    "Living Part",
    "Bible Study Conductor",
    "Reader",
    "Aux Classroom Counselor",
]
# Each part (role) is taken by people holding the privilege of the same name,
# so the two lists are one. Every part is for brothers only, apart from these.
ROLES = PRIVILEGES
SISTER_ROLES = {"Initial Presentation", "Making Disciples", "Explaining Beliefs"}
# Weeks with no regular meetings. Each shows a label wherever the week
# appears, in the language of the page or printout: TRANSLATIONS[language]["event_…"].
EVENT_KINDS = ("assembly", "convention")
EVENT_NAMES = {"assembly": "Circuit Assembly", "convention": "Convention"}

# Roles the app no longer schedules. Saved assignments and privileges naming
# them are cleared at start-up (db.init_db), after a restore, and on undo.
REMOVED_ROLES = ("Watchtower Conductor", "Weekend Chairman", "Public Talk", "Watchtower Reader")
STUDENT_ROLES = {
    "Bible Reading",
    "Initial Presentation",
    "Making Disciples",
    "Explaining Beliefs",
    "Student Talk",
}
ASSISTANT_ROLES = {"Initial Presentation", "Making Disciples", "Explaining Beliefs"}

# Halls, in the order the S-89 prints its tick boxes. The ids double as the
# TRANSLATIONS keys for each hall's printed name, so slips can loop over them.
HALLS = ["main_hall", "aux_1", "aux_2"]
MAIN_HALL, AUX_HALL = HALLS[0], HALLS[1]
HALL_NAMES = {
    "main_hall": "Main hall",
    "aux_1": "Auxiliary classroom 1",
    "aux_2": "Auxiliary classroom 2",
}
SECTIONS = ["Opening", "Treasures", "Ministry", "Living", "Closing"]
SECTION_TITLES = {
    "Opening": "Opening",
    "Treasures": "Treasures From God’s Word",
    "Ministry": "Apply Yourself to the Field Ministry",
    "Living": "Living as Christians",
    "Closing": "Closing",
}

# Colour carries meaning only: these three mark the workbook sections.
SECTION_COLORS = {
    "Treasures": "#5B6770",   # slate, as in the workbook
    "Ministry": "#B7821F",    # ochre
    "Living": "#8E2A2A",      # maroon
    "Opening": "#8A94A0",
    "Closing": "#8A94A0",
}
# The printed wording, per slip language, from the message files (messages/*.json, "doc." keys). Roles printed
# beside the name on the schedule sheet; a role with no entry prints the name alone, as the printed form does.
def _words(language):
    def w(key):
        return doc(f"doc.{key}", language)
    return {
        "chairman": w("chairman"), "opening_prayer": w("opening_prayer"),
        "closing_prayer": w("closing_prayer"), "group": w("group"), "song": w("song"),
        "reader": w("reader"),
    }


def _role_labels(language):
    def w(key):
        return doc(f"doc.{key}", language)
    return {
        "Prayer": w("prayer"), "Chairman": w("chairman"), "Bible Study Conductor": w("conductor"),
        "Reader": w("reader"), "Aux Classroom Counselor": w("aux_counselor"),
    }


# Nobody takes the same part two meetings running: a chairman this week is
# given something else next week. Held to only when somebody else qualifies —
# a small congregation would otherwise leave the part empty. This is only the
# default the first time the app runs — Admin → Settings can change the rest
# period without touching code; see db.same_role_gap_days().
SAME_ROLE_GAP_DAYS = 10

# How recently someone had a part, as a coloured marker (Streamlit's dropdowns
# take plain text, so the colour has to be a character). Counted back from the
# meeting being scheduled — not from today — so reopening an old week reads as
# it did then; see utils.recency().
#
# Two states, because the rotation has exactly one threshold: a turn this week
# or last week means a break, and after that you are available again. The
# exact distance is spelt out in words beside the name. Red is a nudge, not a
# rule; the fallback still fills a part rather than leave it empty.
RESTING = "🔴"
AVAILABLE = "🟢"
# A distinct marker rather than plain green: green elsewhere means "available
# and rested", but nobody has actually rested here — they've simply never
# served. Worth its own look, especially for spotting newer participants.
NEVER_BAND = ("⭐", "no parts yet")
THIS_WEEK = (RESTING, "this week")
# A person already assigned to something *after* this meeting reads as a
# scheduling conflict, not a rotation cooldown — a different problem from
# "had this last week", so it gets its own colour rather than sharing red.
CONFLICT = ("🟠", "already scheduled")

# Letters a font must have for names and Dangme wording to print.
SPECIAL_CHARS = "ɛɔŋƐƆŊ"

# The slip languages: what slips, schedule sheets, the S-140 and the messages are printed in.
LANGUAGES = ["English", "Dangme"]


def _translations(language):
    return {
        "main_hall": doc("hall.main", language),
        "aux_1": doc("hall.aux1", language),
        "aux_2": doc("hall.aux2", language),
        "midweek_meeting": doc("mt.midweek", language),
        "event_assembly": doc("ev.assembly_week", language),
        "event_convention": doc("ev.convention_week", language),
    }


TRANSLATIONS = {language: {**_translations(language), "_language": language} for language in LANGUAGES}
WORDS = {language: _words(language) for language in LANGUAGES}
ROLE_LABELS = {language: _role_labels(language) for language in LANGUAGES}
