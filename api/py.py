# -*- coding: utf-8 -*-
"""The Python half of the Next.js app, as one Vercel function at /api/py.

The scheduling rules (who may take a part, rotation, suggestions, the checks
before a save, undo) and every document (S-89 slips, the S-140, schedule
sheets, share cards, backups) live in the Python modules in pyapp/. This file
only puts them behind HTTP: `/api/py?op=<name>`, JSON in and out, or a file
for downloads.

The browser calls it directly, carrying the sign-in cookie the Next.js app
set; it is checked here with the same SESSION_SECRET. Messages are in the app
language (English or Dangme); documents are in the slip language.
"""
import base64
from datetime import date, timedelta
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler
from http.cookies import SimpleCookie
import json
import os
import re
from pathlib import Path
import sys
import time
import traceback
from urllib.parse import parse_qs, quote, urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pyapp"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import st_shim  # noqa: E402  (must come before the app's modules)

# The direct (unpooled) Neon endpoint when there is one: this function opens a plain connection per request (below),
# which needs no PgBouncer in front, and PgBouncer's transaction mode is what breaks prepared statements and startup
# options. Vercel's Neon integration sets DATABASE_URL_UNPOOLED; otherwise "-pooler" is dropped from the host name.
if not os.environ.get("MEETING_DSN"):
    _url = os.environ.get("DATABASE_URL_UNPOOLED") or os.environ.get("DATABASE_URL", "")
    if _url:
        os.environ["MEETING_DSN"] = _url.replace("-pooler.", ".", 1)

import pandas as pd  # noqa: E402

from backup import backup_bytes, import_all  # noqa: E402
from card_image import person_card_spec, render_card, week_card_spec  # noqa: E402
from constants import LANGUAGES, MAIN_HALL, MIDWEEK, SISTER_ROLES, TRANSLATIONS  # noqa: E402
import db  # noqa: E402
from i18n import app_locale, t as _t, ui  # noqa: E402
import psycopg  # noqa: E402
from parts import build_midweek_slots, default_midweek_parts  # noqa: E402
from picking import (assignment_issues, create_week, eligible_ids,  # noqa: E402
                     ordered_options, person_label_factory, suggest_assignments)
from s140 import S140Error, check_s140_template, fill_s140  # noqa: E402
from sheets_pdf import (build_s140_data, generate_schedule_pdf,  # noqa: E402
                        month_assignments_for, month_name_in, week_label_in,
                        week_overview_text, whatsapp_month_text)
from slips import S89Error, check_s89_template, slip_rows_for, slips_pdf  # noqa: E402
from utils import (apply_aux, fmt_date, make_slot, nfc,  # noqa: E402
                   slot_label, slot_match_key, weeks_apart)
import workbook as wb  # noqa: E402

COOKIE = "mo_session"


class _PerRequestPool:
    """Stands in for db._pool's psycopg_pool.ConnectionPool inside this function.

    A serverless instance is frozen between requests, and a background-threaded pool frozen with it wakes up holding
    connections Neon has already closed and worker threads mid-wait, so getconn can stall for its full timeout. A fresh
    connection per request costs one connect and can't go stale. db.get_conn only calls getconn and putconn.
    """

    def __init__(self, url, schema_name):
        self.url = url
        self.kwargs = {"connect_timeout": db.CONNECT_TIMEOUT, "prepare_threshold": None}
        if schema_name != "public":  # the tests' own schemas; public is already the default search path
            self.kwargs["options"] = f"-c search_path={schema_name}"

    def getconn(self, timeout=None):
        return psycopg.connect(self.url, **self.kwargs)

    def putconn(self, conn):
        try:
            conn.close()
        except Exception:
            pass


db._pool = lambda url, schema_name: _PerRequestPool(url, schema_name)


class Refused(Exception):
    """A request that can't be done, with the reason to show."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


# ----------------------------------------------------------------- sign-in
def signed_in(cookie_header):
    """True for a valid sign-in cookie. Mirrors src/lib/session.ts: the cookie is a base64url JSON payload holding
    only its expiry ({"e": seconds}), a dot, and its HMAC-SHA256 signature made with SESSION_SECRET."""
    secret = os.environ.get("SESSION_SECRET", "")
    if not secret or not cookie_header:
        return False
    jar = SimpleCookie()
    try:
        jar.load(cookie_header)
    except Exception:
        return False
    morsel = jar.get(COOKIE)
    if not morsel or "." not in morsel.value:
        return False
    body, sig = morsel.value.rsplit(".", 1)
    want = base64.urlsafe_b64encode(
        hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest()).rstrip(b"=").decode()
    if not hmac.compare_digest(want, sig):
        return False
    try:
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except Exception:
        return False
    return isinstance(payload, dict) and isinstance(payload.get("e"), (int, float)) and payload["e"] >= time.time()


# ----------------------------------------------------------------- helpers
def _int(value):
    if value is None or value == "":
        return None
    return int(value)


def _students():
    return db.get_students()


def _clean_slot(raw):
    """A slot as the client sent it back, rebuilt with make_slot's fields."""
    return make_slot(raw.get("title") or "", raw.get("role") or "", raw.get("section") or "",
                     _int(raw.get("part_no")), _int(raw.get("minutes")),
                     raw.get("hall") or MAIN_HALL)


def _picks_dict(slots, picks):
    """{index: (person, assistant)} for the slots on the page."""
    return {i: (_int(p.get("sid")), _int(p.get("aid"))) for i, (_, p) in enumerate(zip(slots, picks))}


def _context(meeting_date, students):
    away = db.get_unavailable(meeting_date)
    suspended = db.get_suspended(students, meeting_date)
    return away, suspended


def _issues(meeting_date, slots, picks_dict, students):
    _, suspended = _context(meeting_date, students)
    return assignment_issues(slots, picks_dict, students, meeting_date, MIDWEEK, suspended)


def _snapshot(meeting_date):
    snap = db.last_snapshot(meeting_date, MIDWEEK)
    if not snap:
        return None
    if snap["reason"] == "before delete":
        note = ui("sched.undo_before_delete")
    else:
        note = ui("sched.undo_what", count=snap["assigned"], time=snap["ts"][11:16])
    return {"note": note, "reason": snap["reason"]}


def _date(text):
    """A short date for a message, e.g. 14 Oct."""
    return fmt_date(text, short=True)


# ------------------------------------------------------------ the editor
def op_editor(q):
    """Everything the Create or edit page needs for one meeting."""
    meeting_date = q["date"]
    loc = app_locale()
    students = _students()
    today = date.today().isoformat()
    n = weeks_apart(today, meeting_date)
    relative = {0: "date.this_week", -1: "date.last_week", 1: "date.next_week"}.get(n)
    head = {"weekLabel": week_label_in(meeting_date, loc), "relative": _t(relative, loc) if relative else ""}
    special = db.event_label(meeting_date, "Dangme" if loc == "ada" else "English")
    if special:
        other = db.event_label(meeting_date, "English" if loc == "ada" else "Dangme")
        return {**head, "event": special, "eventOther": other if other != special else ""}

    schedules_df = db.get_schedules()
    saved_slots, saved_picks = db.load_schedule(meeting_date, MIDWEEK, schedules_df)
    meta = db.get_meeting_meta(meeting_date, MIDWEEK)
    slots = saved_slots or build_midweek_slots(default_midweek_parts())

    workbook_info = None
    brochure, _ = wb.load_workbook()
    if brochure:
        matched = wb.week_for_date(brochure, meeting_date)
        wb_parts = brochure[matched]["parts"] if matched else []
        saved_numbered = [(s["part_no"], s["title"]) for s in saved_slots
                          if s.get("part_no") and s.get("hall", MAIN_HALL) == MAIN_HALL]
        wb_numbered = [(p["part_no"], p["title"]) for p in wb_parts]
        differs = bool(saved_slots and matched and saved_numbered != wb_numbered)
        use = q.get("useWorkbook")
        use = (not saved_slots) if use is None else bool(use)
        week = q.get("week") if use and q.get("week") in brochure else matched
        if use and week:
            slots = build_midweek_slots(brochure[week]["parts"])
            songs = brochure[week].get("songs", [])
            if not saved_slots:
                song = _t("doc.song", loc)
                meta = {**meta, "heading": week, "book": brochure[week].get("book", ""),
                        "opening_song": f"{song} {songs[0]}" if len(songs) > 0 else "",
                        "middle_song": f"{song} {songs[1]}" if len(songs) > 1 else "",
                        "closing_song": f"{song} {songs[2]}" if len(songs) > 2 else ""}
        shown = brochure.get(week) if week else None
        workbook_info = {
            "weeks": [{"label": l, "dates": wb.week_dates_text(w)} for l, w in brochure.items()],
            "matched": matched, "differs": differs, "use": use, "week": week,
            "savedCount": len(saved_numbered), "workbookCount": len(wb_numbered),
            "parts": wb.parts_summary(shown["parts"]) if shown else [],
            "gaps": shown.get("gaps", []) if shown else [],
            "text": shown.get("text", "") if shown else "",
        }

    aux_default = db.get_setting("use_aux", "1") == "1"
    if q.get("aux") is not None:
        aux_on = bool(q["aux"])
    else:
        aux_on = bool(meta.get("aux")) if meta.get("aux") is not None else aux_default
    slots = apply_aux(slots, aux_on)

    # what is saved for each slot, matched by part number/role and hall
    picks = []
    for slot in slots:
        sid, aid = saved_picks.get(slot_match_key(slot), (None, None))
        picks.append({"sid": sid, "aid": aid})

    away, suspended = _context(meeting_date, students)
    blocked = away | suspended
    last_dates = db.last_assignment_dates(meeting_date)
    last_details = db.last_assignment_details(meeting_date)
    next_details = db.next_assignment_details(meeting_date)
    names = dict(zip(students["id"], students["name"]))

    people = {int(r["id"]): {"name": r["name"], "gender": r["gender"], "family": r["family"],
                             "active": int(r["active"] or 0) == 1}
              for r in students.to_dict("records")}
    general = person_label_factory(students, last_dates, away, suspended=suspended,
                                   details=last_details, meeting_date=meeting_date,
                                   upcoming=next_details, locale=loc)
    options = []
    for slot, pick in zip(slots, picks):
        role_dates = db.last_role_dates(slot["role"], meeting_date)
        eligible = eligible_ids(slot["role"], students, away, suspended)
        ordered = ordered_options(eligible, role_dates, keep=pick["sid"])[1:]
        label = person_label_factory(students, last_dates, away, role_dates,
                                     suspended=suspended, details=last_details,
                                     meeting_date=meeting_date, role=slot["role"],
                                     upcoming=next_details, locale=loc)
        options.append({"ids": [int(p) for p in ordered],
                        "labels": {int(p): label(p) for p in ordered},
                        "eligible": [int(p) for p in eligible],
                        "mixed": slot["role"] in SISTER_ROLES and bool(slot["student_part"])})
    # assistants: anyone active and free, least recently used first; the page
    # narrows this to the student's category or family
    active_free = [int(p) for p in students[students["active"] == 1]["id"] if p not in blocked]
    assistant_order = ordered_options(active_free, last_dates)[1:]
    for pick in picks:            # a saved assistant stays offered
        if pick["aid"] is not None and pick["aid"] not in assistant_order:
            assistant_order.append(pick["aid"])
    assistant_labels = {int(p): general(p) for p in assistant_order}

    unavailable = sorted({names[p] for p in blocked if p in names}
                         | {r["name"] for r in students.to_dict("records") if r["active"] != 1})
    labels = []
    for slot in slots:
        text = slot_label(slot, locale=loc)
        if aux_on and slot["student_part"] and slot["hall"] == MAIN_HALL:
            text += " · " + _t("hall.main", loc)
        labels.append(text)

    issues = assignment_issues(slots, _picks_dict(slots, picks), students,
                               meeting_date, MIDWEEK, suspended, loc)
    return {
        **head, "event": None, "saved": bool(saved_slots), "slots": slots, "slotLabels": labels,
        "picks": picks, "meta": {k: meta.get(k) for k in (
            "heading", "book", "opening_song", "middle_song", "closing_song", "aux_group")},
        "workbook": workbook_info, "aux": aux_on,
        "people": people, "options": options, "assistantOrder": [int(p) for p in assistant_order],
        "assistantLabels": assistant_labels, "unavailable": unavailable,
        "snapshot": _snapshot(meeting_date), "issues": issues,
        "activeCount": int((students["active"] == 1).sum()),
    }


def op_check(q):
    students = _students()
    slots = [_clean_slot(s) for s in q["slots"]]
    return {"issues": _issues(q["date"], slots, _picks_dict(slots, q["picks"]), students)}


def op_suggest(q):
    """Fill the empty slots; anyone already chosen stays and is reserved."""
    meeting_date = q["date"]
    students = _students()
    slots = [_clean_slot(s) for s in q["slots"]]
    taken = {i: (_int(p.get("sid")), _int(p.get("aid")))
             for i, p in enumerate(q["picks"]) if _int(p.get("sid")) is not None}
    away, suspended = _context(meeting_date, students)
    picks = suggest_assignments(slots, students, away | suspended, meeting_date, skip=taken)
    return {"picks": {str(i): [v[0], v[1]] for i, v in picks.items() if v is not None}}


def op_save(q):
    meeting_date = q["date"]
    students = _students()
    slots = [_clean_slot(s) for s in q["slots"]]
    picks = {}
    for i, (slot, p) in enumerate(zip(slots, q["picks"])):
        picks[i] = (_int(p.get("sid")), _int(p.get("aid")) if slot["needs_assistant"] else None)
    issues = assignment_issues(slots, picks, students, meeting_date, MIDWEEK,
                               _context(meeting_date, students)[1])
    errors = [x["text"] for x in issues if x["level"] == "error"]
    if errors:
        raise Refused(ui("sched.not_saved", reason=" ".join(errors)))
    meta_in = q.get("meta") or {}
    meta = {k: nfc(str(meta_in.get(k) or "")) for k in (
        "heading", "book", "opening_song", "middle_song", "closing_song", "aux_group")}
    meta["aux"] = bool(q.get("aux"))
    if not meta["aux"]:
        meta["aux_group"] = ""
    names = dict(zip(students["id"], students["name"]))
    try:
        db.save_schedule(meeting_date, MIDWEEK, slots, picks, meta, names)
    except ValueError as exc:
        raise Refused(ui("sched.not_saved", reason=str(exc)))
    warnings = sum(1 for x in issues if x["level"] == "warning")
    return {"message": ui("sched.saved", meeting=ui("mt.midweek_lower"), date=fmt_date(meeting_date))
            + (" " + ui("sched.saved_check") if warnings else "")}


def op_undo(q):
    restored = db.undo_last(q["date"], MIDWEEK)
    if restored is None:
        raise Refused(ui("sched.nothing_to_undo"))
    return {"message": ui("sched.undone")}


def op_delete(q):
    db.delete_schedule(q["date"], MIDWEEK)
    return {"message": ui("sched.deleted")}


def op_create_month(q):
    """Create and fill several workbook weeks in one go (Month overview)."""
    students = _students()
    brochure, _ = wb.load_workbook()
    made = []
    for item in q["weeks"]:
        week = brochure.get(item["label"])
        if not week:
            continue
        filled, total = create_week(item["date"], item["label"], week, students,
                                    bool(q.get("aux")), nfc(q.get("group") or ""))
        made.append(f"{_date(item['date'])} ({filled}/{total})")
    if not made:
        raise Refused(ui("month.gone"))
    return {"message": ui("month.created", count=len(made), cleared="") + " " + ", ".join(made)}


# ------------------------------------------------------- assembly weeks
def op_week_preview(q):
    day = q["day"]
    loc = app_locale()
    return {"label": week_label_in(day, loc),
            "saved": [{"date": d, "type": t, "text": _date(d)} for d, t in db.meetings_in_week(day)]}


def op_mark_event(q):
    if q.get("kind") not in ("assembly", "convention"):
        raise Refused(ui("event.unknown", kind=q.get("kind")))
    cleared = db.mark_event_week(q["day"], q["kind"])
    return {"message": ui("event.marked", kind=ui(f"ev.{q['kind']}"))
            + (ui("month.cleared", count=len(cleared)) if cleared else "")}


# ------------------------------------------------------------- workbook
def op_workbook_upload(q, body):
    if not body:
        raise Refused(ui("wb.choose_pdf"))
    name = q.get("name") or "workbook.pdf"
    skip_past = q.get("skipPast", "1") == "1"
    weeks, empty, _raw = wb.parse_brochure(body)
    if not weeks:
        raise Refused(ui("wb.no_parts_at_all"))
    first, sure = wb.guess_first_monday(weeks, name)
    dated = wb.assign_dates(dict(weeks), first)
    dropped = []
    if skip_past:
        dated, dropped = wb.drop_past_weeks(dated)
    wb.save_workbook(dated, name)
    db.set_setting("skip_past_weeks", "1" if skip_past else "0")
    db.set_setting("workbook_dates_sure", "1" if sure else "0")
    broken = wb.unreadable_parts(weeks)
    guessed = wb.guessed_roles(weeks)
    return {
        "message": ui("wb.found", count=len(weeks)),
        "dropped": dropped, "empty": empty,
        "broken": [{"week": l, "title": t} for l, t in broken],
        "guessed": [{"week": l, "no": n, "title": t} for l, n, t in guessed],
        # the Dangme workbook prints its week headings in English too, so this is only for another language
        "notEnglish": not any(w.get("month") in wb.ENGLISH_MONTHS for w in weeks.values()),
    }


def op_workbook_dates(q):
    stored, file_name = wb.load_workbook()
    if not stored:
        raise Refused(ui("wb.none_stored"))
    skip_past = bool(q.get("skipPast", True))
    dated = wb.assign_dates(stored, date.fromisoformat(q["first"]))
    if skip_past:
        dated, _ = wb.drop_past_weeks(dated)
    wb.save_workbook(dated, file_name)
    db.set_setting("skip_past_weeks", "1" if skip_past else "0")
    db.set_setting("workbook_dates_sure", "1")
    return {"message": ui("wb.dates_updated")}


def op_workbook_rename(q):
    stored, file_name = wb.load_workbook()
    label = nfc(q.get("label") or "")
    if not label or q["week"] not in stored:
        raise Refused(ui("wb.type_heading"))
    if label in stored:
        raise Refused(ui("wb.heading_taken", name=label))
    wb.save_workbook({(label if l == q["week"] else l): w for l, w in stored.items()}, file_name)
    return {"message": ui("wb.renamed", name=label)}


def op_workbook_week(q):
    stored, file_name = wb.load_workbook()
    week = q["week"]
    if week not in stored:
        raise Refused(ui("wb.week_gone"))
    parts = []
    for r in q["parts"]:
        if not nfc(r.get("title") or "") or not r.get("section") or not r.get("role"):
            continue
        parts.append(make_slot(r["title"], r["role"], r["section"], _int(r.get("part_no")),
                               _int(r.get("minutes"))))
    parts.sort(key=lambda p: p["part_no"] or 99)
    numbers = [p["part_no"] for p in parts if p["part_no"]]
    top = max(numbers) if numbers else 0
    stored[week]["parts"] = parts
    stored[week]["gaps"] = [n for n in range(1, top + 1) if n not in numbers]
    wb.save_workbook(stored, file_name)
    return {"message": ui("wb.week_saved")}


def op_workbook_remove(q):
    wb.save_workbook({}, "")
    return {"message": ui("wb.removed")}


# ------------------------------------------------------------ templates
def op_template_upload(q, body):
    kind, language = q.get("kind"), q.get("lang")
    if kind not in ("s89", "s140") or language not in LANGUAGES or not body:
        raise Refused(ui("admin.choose_file"))
    name = q.get("name") or f"{kind}.{'pdf' if kind == 's89' else 'docx'}"
    try:
        if kind == "s89":
            n = check_s89_template(body)
            note = ui("admin.slips_per_page", count=n)
        else:
            n = check_s140_template(body)
            note = ui("admin.week_blocks", count=n)
    except (S89Error, S140Error) as exc:
        raise Refused(str(exc))
    db.save_template(f"{kind}_{language}", name, body)
    return {"message": ui("admin.form_saved", language=ui(f"lang.{language.lower()}"),
                          form="S-89" if kind == "s89" else "S-140", detail=note)}


# ---------------------------------------------------------- backup
def op_restore(q, body):
    try:
        data = json.loads((body or b"").decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError(ui("admin.not_backup"))
        counts = import_all(data)
    except (ValueError, UnicodeDecodeError) as exc:
        raise Refused(ui("admin.cant_restore", reason=str(exc)))
    return {"message": ui("admin.restored", people=counts.get("students", 0), rows=counts.get("schedules", 0))}


# ------------------------------------------------------------ documents
def _meetings_param(q):
    out = []
    for item in (q.get("meetings") or "").split(","):
        if "|" in item:
            d, t = item.split("|", 1)
            if t == MIDWEEK:
                out.append((d, t))
    return sorted(set(out))


def _lang(q):
    """The slip language asked for, else the one chosen in the sidebar, as (name, TRANSLATIONS entry)."""
    saved = db.get_setting("slip_language", "")
    language = q.get("lang") if q.get("lang") in LANGUAGES else saved if saved in LANGUAGES else LANGUAGES[0]
    return language, TRANSLATIONS[language]


def _rows_for(meetings):
    df = db.get_schedules()
    wanted = set(meetings)
    mask = pd.Series([(d, k) in wanted for d, k in zip(df["meeting_date"], df["meeting_type"])],
                     index=df.index, dtype=bool)
    return df, df[mask]


PDF, DOCX, PNG = ("application/pdf",
                  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                  "image/png")


def doc_slips(q):
    language, t = _lang(q)
    meetings = _meetings_param(q)
    _, rows = _rows_for(meetings)
    slip_rows = slip_rows_for(rows)
    if not slip_rows:
        raise Refused(ui("print.no_slips"))
    try:
        data = slips_pdf(slip_rows, t, language)
    except S89Error as exc:
        raise Refused(str(exc))
    stem = q.get("stem") or (meetings[0][0] if meetings else "slips")
    return data, PDF, f"S89_slips_{stem}_{language}.pdf"


def doc_sheet(q):
    _, t = _lang(q)
    meetings = _meetings_param(q)
    if not meetings:
        raise Refused(ui("print.no_meeting"))
    df = db.get_schedules()
    data = generate_schedule_pdf(meetings, df, t, compact=q.get("compact") == "1")
    return data, PDF, f"midweek_schedule_{q.get('stem') or meetings[0][0]}.pdf"


def doc_s140(q):
    language, t = _lang(q)
    month = q.get("month") or ""
    template, _ = db.load_template(f"s140_{language}")
    if not template:
        raise Refused(ui("print.no_s140", language=ui(f"lang.{language.lower()}")))
    df = db.get_schedules()
    meetings = sorted(m for m in db.saved_meetings(df) if m[1] == MIDWEEK and m[0].startswith(month))
    data, skipped = build_s140_data(meetings, df, db.get_setting("congregation"), [month], language)
    data["meeting_name"] = _t("doc.midweek_title", "ada" if language == "Dangme" else "en")
    if not data["weeks"]:
        raise Refused(ui("print.s140_nothing"))
    try:
        out = fill_s140(template, data)
    except (S140Error, KeyError, IndexError) as exc:
        raise Refused(ui("print.s140_failed", reason=str(exc)))
    return out, DOCX, f"{month_name_in(month)}.docx"


def doc_csv(q):
    df = db.get_schedules()
    data = df[["meeting_date", "meeting_type", "part_no", "part_name", "minutes", "section",
               "role", "hall", "person", "assistant"]].to_csv(index=False).encode("utf-8-sig")
    return data, "text/csv; charset=utf-8", "meeting_schedule.csv"


def _person(q):
    students = _students()
    row = students[students["id"] == _int(q.get("person"))]
    if row.empty:
        raise Refused(ui("print.choose_participant"))
    return row.iloc[0]


def doc_card(q):
    language, _ = _lang(q)
    df = db.get_schedules()
    if q.get("kind") == "person":
        person, month = _person(q), q.get("month") or ""
        items = month_assignments_for(df, int(person["id"]), month, language)
        spec = person_card_spec(person["name"], person["gender"], month, items, language)
        stem = "_".join(str(person["name"]).split()) + f"_{month}"
    else:
        week = q.get("week") or ""
        spec = week_card_spec(df, week, language)
        stem = f"assignments_{week}"
    return render_card(spec), PNG, f"{stem}.png"


def op_message_text(q):
    language, _ = _lang(q)
    df = db.get_schedules()
    if q.get("kind") == "person":
        person, month = _person(q), q.get("month") or ""
        items = month_assignments_for(df, int(person["id"]), month, language)
        return {"text": whatsapp_month_text(person["name"], person["gender"], month, items, language)}
    return {"text": week_overview_text(df, q.get("week") or "", language)}


def op_ping(q):
    """Open /api/py?op=ping while signed in to see whether this function reaches the database, and how fast."""
    started = time.monotonic()
    with db.get_conn() as conn:
        conn.execute("SELECT 1")
    return {"ok": True, "database_ms": round((time.monotonic() - started) * 1000),
            "host": urlparse(db.dsn()).hostname or ""}


def doc_backup(q):
    return backup_bytes(), "application/json", f"meeting_organizer_backup_{date.today()}.json"


JSON_OPS = {
    "editor": op_editor, "check": op_check, "suggest": op_suggest, "save": op_save,
    "undo": op_undo, "delete": op_delete, "create_month": op_create_month,
    "week_preview": op_week_preview, "mark_event": op_mark_event,
    "workbook_dates": op_workbook_dates, "workbook_rename": op_workbook_rename,
    "workbook_week": op_workbook_week, "workbook_remove": op_workbook_remove,
    "message_text": op_message_text, "ping": op_ping,
}
BODY_OPS = {"workbook_upload": op_workbook_upload, "template_upload": op_template_upload,
            "restore": op_restore}
DOCS = {"slips": doc_slips, "sheet": doc_sheet, "s140": doc_s140, "csv": doc_csv,
        "card": doc_card, "backup": doc_backup}
# GET requests are only for reading: documents, and a few read-only JSON ops
GET_JSON = {"message_text", "week_preview", "ping"}

_schema_checked = False


def _ensure_schema():
    """Create the tables on the first request of a fresh instance, in case the database is newer than the last
    deploy (the build normally does it: npm run db:setup)."""
    global _schema_checked
    if not _schema_checked:
        db.init_db()
        _schema_checked = True


def handle(method, path, headers, body):
    """(status, content type, bytes, extra headers) for one request."""
    url = urlparse(path)
    q = {k: v[-1] for k, v in parse_qs(url.query).items()}
    op = q.get("op", "")
    if not signed_in(headers.get("cookie") or headers.get("Cookie")):
        return 401, "application/json", json.dumps({"error": _t("signin.again", "en")}).encode(), {}
    st_shim.new_request()
    try:
        _ensure_schema()
        payload = None
        if method == "POST" and op in JSON_OPS and op not in BODY_OPS:
            payload = json.loads((body or b"{}").decode("utf-8"))
        if method == "GET" and op in DOCS:
            data, ctype, file_name = DOCS[op](q)
            disposition = "inline" if ctype == PNG and q.get("inline") == "1" else "attachment"
            return 200, ctype, data, {
                "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(file_name)}",
                "Cache-Control": "no-store"}
        if method == "GET" and op in GET_JSON:
            result = JSON_OPS[op](q)
        elif method == "POST" and op in BODY_OPS:
            result = BODY_OPS[op](q, body)
        elif method == "POST" and op in JSON_OPS:
            result = JSON_OPS[op](payload)
        else:
            raise Refused(ui("err.unknown_request"), 404)
    except Refused as exc:
        return exc.status, "application/json", json.dumps({"error": str(exc)}).encode(), {}
    except Exception as exc:
        traceback.print_exc()
        try:
            message = ui("err.generic_detail", detail=str(exc)[:200])
        except Exception:
            message = _t("err.generic_detail", "en", detail=str(exc)[:200])
        return 500, "application/json", json.dumps({"error": message}).encode(), {}
    return 200, "application/json", json.dumps(result, default=_json_default,
                                               ensure_ascii=False).encode("utf-8"), {
        "Cache-Control": "no-store"}


def _json_default(value):
    if hasattr(value, "item"):           # numpy numbers from pandas
        return value.item()
    if isinstance(value, (set, frozenset)):
        return sorted(value)
    if isinstance(value, (date,)):
        return value.isoformat()
    if value != value:                   # NaN
        return None
    raise TypeError(_t("err.cant_send", "en", file=type(value).__name__))


class handler(BaseHTTPRequestHandler):
    """Vercel's Python runtime calls this class for /api/py."""

    def _respond(self, method):
        length = int(self.headers.get("content-length") or 0)
        body = self.rfile.read(length) if length else b""
        status, ctype, data, extra = handle(method, self.path, self.headers, body)
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        for k, v in extra.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self._respond("GET")

    def do_POST(self):
        self._respond("POST")
