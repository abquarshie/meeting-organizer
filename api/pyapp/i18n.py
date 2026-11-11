# -*- coding: utf-8 -*-
"""The app's words, from the same message files the screens use (messages/en.json and messages/ada.json).

Two languages are in play and they are kept apart:
- the app language ("en" or "ada", setting app_language) for what the person using the app reads: messages after a
  save, the checks, the labels in the lists;
- the slip language ("English" or "Dangme", setting slip_language) for what is printed or sent to the participants:
  slips, schedule sheets, the S-140, the share cards and the WhatsApp text.

A Dangme message that is still empty falls back to the English one, so a half-finished translation never shows a
blank. Messages use {name} placeholders only, as in messages/en.json.
"""
from functools import lru_cache
import json
from pathlib import Path
import re
import unicodedata

MESSAGES = Path(__file__).resolve().parent.parent / "messages"
LOCALES = ("en", "ada")
# slip language -> locale
LANGUAGE_LOCALE = {"English": "en", "Dangme": "ada"}


def _flat(tree, prefix=""):
    out = {}
    for key, value in tree.items():
        name = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            out.update(_flat(value, name))
        else:
            out[name] = unicodedata.normalize("NFC", value)
    return out


@lru_cache(maxsize=None)
def messages(locale):
    english = _flat(json.loads((MESSAGES / "en.json").read_text(encoding="utf-8")))
    if locale == "en":
        return english
    own = _flat(json.loads((MESSAGES / f"{locale}.json").read_text(encoding="utf-8")))
    return {k: own.get(k) or v for k, v in english.items()}


_PLACEHOLDER = re.compile(r"\{(\w+)\}")


def fill(text, **values):
    """Put the values into a message's {placeholders}. A placeholder with no value is left as it is."""
    return _PLACEHOLDER.sub(lambda m: str(values[m.group(1)]) if m.group(1) in values else m.group(0), text)


def t(key, locale="en", **values):
    """The message for this key in this locale, with its values filled in. An unknown key comes back as itself."""
    text = messages(locale if locale in LOCALES else "en").get(key, key)
    return fill(text, **values) if values else text


def app_locale():
    """The app language, from settings (English until it is changed)."""
    import db
    locale = db.get_setting("app_language", "en")
    return locale if locale in LOCALES else "en"


def ui(key, **values):
    """A message in the app language."""
    return t(key, app_locale(), **values)


def locale_for(language):
    """The locale of a slip language: "English" -> "en", "Dangme" -> "ada"."""
    return LANGUAGE_LOCALE.get(language, "en")


def doc(key, language, **values):
    """A message in a slip language ("English" or "Dangme")."""
    return t(key, locale_for(language), **values)


# The words for the values stored in the database (always English), as src/lib/labels.ts gives them on screen.
ROLE_KEYS = {
    "Chairman": "role.chairman", "Prayer": "role.prayer", "Treasures Talk": "role.treasures_talk",
    "Spiritual Gems": "role.gems", "Bible Reading": "role.bible_reading", "Initial Presentation": "role.initial",
    "Making Disciples": "role.disciples", "Explaining Beliefs": "role.beliefs", "Student Talk": "role.student_talk",
    "Living Part": "role.living", "Bible Study Conductor": "role.cbs", "Reader": "role.reader",
    "Aux Classroom Counselor": "role.aux_counselor",
}
SECTION_KEYS = {
    "Opening": "sec.opening", "Treasures": "sec.treasures", "Ministry": "sec.ministry", "Living": "sec.living",
    "Closing": "sec.closing",
}
HALL_KEYS = {"main_hall": "hall.main", "aux_1": "hall.aux1", "aux_2": "hall.aux2"}


def role_label(role, locale="en"):
    return t(ROLE_KEYS[role], locale) if role in ROLE_KEYS else (role or "")


def section_label(section, locale="en"):
    return t(SECTION_KEYS[section], locale) if section in SECTION_KEYS else (section or "")


def hall_label(hall, locale="en"):
    return t(HALL_KEYS[hall], locale) if hall in HALL_KEYS else (hall or "")


# The fixed part titles the app itself writes (parts.py); a workbook's own titles are shown as they are.
TITLE_KEYS = {
    "Chairman": "role.chairman", "Opening Prayer": "part.opening_prayer", "Closing Prayer": "part.closing_prayer",
    "Congregation Bible Study Reader": "part.cbs_reader", "Auxiliary Classroom Counselor": "role.aux_counselor",
    "Treasures Talk": "role.treasures_talk", "Spiritual Gems": "role.gems", "Bible Reading": "role.bible_reading",
    "Initial Presentation": "role.initial", "Making Disciples": "role.disciples",
    "Explaining Your Beliefs": "part.explaining_your", "Living Part": "role.living",
    "Congregation Bible Study": "part.cbs",
}


def part_title(title, locale="en"):
    return t(TITLE_KEYS[title], locale) if title in TITLE_KEYS else (title or "")
