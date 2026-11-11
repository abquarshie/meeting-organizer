# -*- coding: utf-8 -*-
"""Postgres storage: participants, schedules, settings."""
from contextlib import contextmanager
from datetime import date, datetime, timedelta
import json
import os
from pathlib import Path
import re
import threading

import pandas as pd
import psycopg
import streamlit as st

from constants import (
    EVENT_KINDS,
    GROUPS,
    MAIN_HALL,
    MIDWEEK,
    REMOVED_ROLES,
    SAME_ROLE_GAP_DAYS,
    STUDENT_ROLES,
    TRANSLATIONS,
)
from i18n import t as _t, ui
from utils import (
    default_section,
    fmt_date,
    infer_role,
    make_slot,
    nfc,
    parse_privileges,
    slot_label,
    slot_match_key,
    week_start,
)

# =============================================================================
# DATABASE
# =============================================================================
# Postgres, so the data outlives the container. The SQL below is written with
# SQLite's "?" placeholders and translated on the way out, which keeps every
# query readable and the port reviewable. No query contains a literal "?" or
# "%", which is what makes that translation safe.


def dsn():
    """Connection string, from the app's secrets or the environment."""
    env = os.environ.get("MEETING_DSN")
    if env:
        return env
    try:
        return st.secrets["database"]["url"]
    except Exception:
        raise RuntimeError("No database configured. Set DATABASE_URL (or MEETING_DSN for the tests).")


def schema():
    """Schema to work in. Tests point each test at its own."""
    return os.environ.get("MEETING_SCHEMA", "public")


def _sql(text):
    return text.replace("?", "%s")


class _Conn:
    """The small part of the sqlite3 connection API this app uses."""

    def __init__(self, raw):
        self._raw = raw
        self.total_changes = 0

    def execute(self, sql, params=()):
        cur = self._raw.cursor()
        cur.execute(_sql(sql), tuple(params))
        self.total_changes += max(cur.rowcount, 0)
        return cur

    def executemany(self, sql, seq):
        cur = self._raw.cursor()
        rows = [tuple(p) for p in seq]
        if rows:
            cur.executemany(_sql(sql), rows)
            self.total_changes += max(cur.rowcount, 0)
        return cur


# Fail fast and say why. Without these, a wrong password or host makes every
# page wait the full default (30s) before showing an error, which looks like
# the app failing to start rather than a setting being wrong.
CONNECT_TIMEOUT = 8     # seconds to reach the server
POOL_TIMEOUT = 10       # seconds to wait for a free connection


@st.cache_resource(show_spinner=False)
def _pool(url, schema_name):
    from psycopg_pool import ConnectionPool

    # Connect once directly first. The pool retries in the background and only
    # ever reports "couldn't get a connection after N sec", which hides the
    # reason — a wrong password, an unknown host, a missing database. A plain
    # connect surfaces the actual message from the server.
    try:
        psycopg.connect(url, connect_timeout=CONNECT_TIMEOUT).close()
    except Exception as exc:
        raise RuntimeError(f"{str(exc).strip() or exc.__class__.__name__}") from exc
    return ConnectionPool(
        url, min_size=1, max_size=5, open=True, timeout=POOL_TIMEOUT,
        # Neon suspends its compute when idle and terminates the connections.
        # check runs a liveness test before handing one out, so a suspended
        # database costs one reconnect instead of an AdminShutdown crash.
        check=ConnectionPool.check_connection,
        max_idle=60,        # recycle before Neon gets to them
        max_lifetime=600,
        # prepare_threshold=None turns off automatic server-side prepared
        # statements. psycopg enables them after a query repeats, which breaks
        # against a transaction-pooling proxy such as Neon's "-pooler" endpoint,
        # and only once the app has been up a while. The app has its own pool,
        # so nothing is lost by switching them off.
        kwargs={"options": f"-c search_path={schema_name}",
                "connect_timeout": CONNECT_TIMEOUT,
                "prepare_threshold": None},
    )


_local = threading.local()


def _live_connection(pool):
    """A connection proven alive, or a fresh one.

    The pool's own check is not enough here: a connection can be handed out
    healthy and be dead by the next use, and a suspended Neon compute kills
    every connection at once. Proving it before the request starts costs one
    cheap round trip and turns a crash into a reconnect.
    """
    last = None
    for _ in range(3):
        try:
            raw = pool.getconn(timeout=POOL_TIMEOUT)
        except Exception as exc:
            last = exc
            continue
        try:
            raw.execute("SELECT 1")
            return raw
        except psycopg.Error as exc:       # dead: let the pool bin it, try again
            last = exc
            try:
                raw.close()
            except Exception:
                pass
            try:
                pool.putconn(raw)
            except Exception:
                pass
    raise last if last else RuntimeError("no database connection")


@contextmanager
def get_conn():
    """A connection from the pool, reused by nested calls.

    Reentrancy matters: save_schedule() opens a connection and then calls
    log_change(), which wants one too. With a pool, letting that take a second
    connection deadlocks once every pooled connection is held by a caller
    waiting for another. Joining the outer transaction also means a change and
    its log entry commit or roll back together.
    """
    existing = getattr(_local, "conn", None)
    if existing is not None:
        yield existing
        return
    pool = _pool(dsn(), schema())
    raw = _live_connection(pool)
    conn = _Conn(raw)
    _local.conn = conn
    try:
        yield conn
        raw.commit()
    except BaseException:
        try:
            raw.rollback()
        except Exception:
            pass
        raise
    finally:
        _local.conn = None
        try:
            pool.putconn(raw)
        except Exception:
            pass


def read_df(sql, params=()):
    """A DataFrame from one query, without handing pandas the raw driver."""
    with get_conn() as conn:
        cur = conn.execute(sql, params)
        cols = [c.name for c in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)


def log_change(action, details=""):
    """A line in the change log. The action is written in the app language at the time of the change."""
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO audit_log (ts, action, details) VALUES (?, ?, ?)",
            (datetime.now().isoformat(timespec="seconds"), action, details),
        )


def get_log(limit=500):
    return read_df("SELECT ts, action, details FROM audit_log ORDER BY id DESC LIMIT ?", (limit,))


def qcols(names):
    """Quote a column list for interpolation."""
    return ", ".join(f'"{n}"' for n in names)


def table_columns(conn, table):
    return [r[0] for r in conn.execute(
        """SELECT column_name FROM information_schema.columns
            WHERE table_schema = ? AND table_name = ?
            ORDER BY ordinal_position""", (schema(), table)).fetchall()]


def _add_missing_columns(conn, table, columns):
    for name, ddl in columns.items():
        conn.execute(f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS "{name}" {ddl}')


def resync_identities():
    """Move each id sequence past the largest id, after rows are restored with
    their own ids (a backup or a Sheets load)."""
    with get_conn() as conn:
        for table in ("students", "schedules", "audit_log", "snapshots", "no_meeting_periods"):
            conn.execute(
                f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                f"COALESCE((SELECT MAX(id) FROM {table}), 0) + 1, false)")


@st.cache_resource(show_spinner=False)
def _schema_ready(schema_name, fingerprint):
    """init_db() is ~30 statements. Over a network that is seconds, so it runs
    once per process — but keyed on what init_db() actually says.

    Streamlit reruns the script when the code changes without restarting the
    process, so a cache keyed on the schema name alone survives a deploy and
    the new migrations never run: the app then queries a column that was never
    added. Hashing init_db's own source means adding a table or a column
    invalidates this automatically, with nothing to remember to bump.
    """
    init_db()
    return True


def schema_fingerprint():
    import hashlib
    import inspect
    try:
        source = inspect.getsource(init_db)
    except OSError:                                  # pragma: no cover
        return "unknown"
    return hashlib.sha1(source.encode("utf-8")).hexdigest()[:12]


def ensure_db():
    _schema_ready(schema(), schema_fingerprint())


def is_retired(role, meeting_type, part_name):
    """Rows the app doesn't keep: the roles of the weekend meeting and any other part it doesn't schedule (a
    backup from the Meeting Scheduler can hold them), and anything that isn't a midweek meeting."""
    return role in REMOVED_ROLES or (meeting_type is not None and meeting_type != MIDWEEK)


SCHEMA_SQL = Path(__file__).resolve().parent.parent / "db" / "schema.sql"
# The columns a restored or undone row may set: anything else in it (the Meeting Scheduler's weekend and talk
# columns, say) is left out rather than failing the insert.
_SCHEDULE_COLUMNS = {
    "id", "meeting_date", "meeting_type", "part_name", "assigned_person", "part_no", "minutes", "section", "role",
    "student_part", "needs_assistant", "student_id", "assistant_id", "assistant_name", "sort_order", "hall",
}
_MEETING_COLUMNS = {"meeting_date", "meeting_type", "heading", "opening_song", "middle_song", "closing_song", "aux",
                    "book", "aux_group"}


def init_db():
    """Create the tables from db/schema.sql (the same file `npm run db:setup` runs), then tidy what older data can
    hold."""
    sql = "\n".join(line for line in SCHEMA_SQL.read_text(encoding="utf-8").splitlines()
                    if not line.strip().startswith("--"))
    with get_conn() as conn:
        conn.execute(f"CREATE SCHEMA IF NOT EXISTS {schema()}")
        for statement in sql.split(";"):
            if statement.strip():
                conn.execute(statement)
        conn.execute("UPDATE schedules SET hall = 'main_hall' WHERE hall IS NULL")
        conn.execute("UPDATE students SET active = 1 WHERE active IS NULL")
        conn.execute("UPDATE no_meeting_periods SET kind = 'assembly' WHERE kind IS NULL")
        # roles not scheduled here, and any meeting that isn't a midweek meeting, go, with the privileges
        conn.execute("DELETE FROM schedules WHERE meeting_type IS DISTINCT FROM ?", (MIDWEEK,))
        conn.execute("DELETE FROM meetings WHERE meeting_type IS DISTINCT FROM ?", (MIDWEEK,))
        for role in REMOVED_ROLES:
            conn.execute("DELETE FROM schedules WHERE role = ?", (role,))
            for sid, privileges in conn.execute(
                    "SELECT id, privileges FROM students WHERE privileges LIKE ?",
                    (f"%{role}%",)).fetchall():
                conn.execute("UPDATE students SET privileges = ? WHERE id = ?",
                             (", ".join(parse_privileges(privileges)), sid))


@st.cache_data(show_spinner=False)
def _all_settings(schema_name):
    with get_conn() as conn:
        return dict(conn.execute("SELECT key, value FROM settings").fetchall())


def get_setting(key, default=""):
    """Settings are read many times per page (wording, meeting days, flags), so
    fetch the table once and serve every lookup from it."""
    value = _all_settings(schema()).get(key)
    return default if value is None else value


def _forget_settings():
    _all_settings.clear()




def set_setting(key, value):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
    _forget_settings()


def same_role_gap_days():
    """Days before someone may take the same part again (Admin → Settings).
    Falls back to the built-in default until a congregation sets its own."""
    try:
        return int(get_setting("same_role_gap_days", str(SAME_ROLE_GAP_DAYS)))
    except (TypeError, ValueError):
        return SAME_ROLE_GAP_DAYS


@st.cache_data(show_spinner=False)
def _students(schema_name):
    df = read_df(
        "SELECT id, name, gender, privileges, active, family, groups, "
        "suspended, suspended_until FROM students ORDER BY lower(name)")
    def text(v):
        return v if isinstance(v, str) else ""

    df["privilege_list"] = df["privileges"].apply(lambda v: parse_privileges(text(v)))
    df["group_list"] = df["groups"].apply(
        lambda v: [g.strip() for g in text(v).split(",") if g.strip() in GROUPS])
    df["family"] = pd.Series([nfc(text(v)) or None for v in df["family"]],
                             index=df.index, dtype=object)
    return df


def get_students(active_only=False):
    """Every page opens with this, so it is fetched once per change rather
    than once per rerun — cleared by _forget_students() on every write."""
    df = _students(schema())
    return df[df["active"] == 1] if active_only else df


def _forget_students():
    _students.clear()


def family_names(students):
    return sorted({f for f in students["family"] if f}, key=str.lower)


def same_family(fam, a, b):
    return bool(a is not None and b is not None and fam.get(a) and fam.get(a) == fam.get(b))


def add_student(name, gender, privileges, family=None, groups=()):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO students (name, gender, privileges, active, family, groups)
               VALUES (?, ?, ?, 1, ?, ?)""",
            (apply_letter_substitutes(nfc(name)), gender, ", ".join(privileges),
             family, ", ".join(groups)),
        )
    _forget_students()
    log_change(ui("log.person_added"), nfc(name))


def update_student(student_id, name, gender, privileges, active, family=None, groups=()):
    with get_conn() as conn:
        conn.execute(
            """UPDATE students SET name = ?, gender = ?, privileges = ?, active = ?,
                   family = ?, groups = ? WHERE id = ?""",
            (apply_letter_substitutes(nfc(name)), gender, ", ".join(privileges),
             int(active), family, ", ".join(groups), student_id),
        )
        # keep the name snapshot on old schedules in step with the rename
        conn.execute("UPDATE schedules SET assigned_person = ? WHERE student_id = ?",
                     (apply_letter_substitutes(nfc(name)), student_id))
        conn.execute("UPDATE schedules SET assistant_name = ? WHERE assistant_id = ?",
                     (apply_letter_substitutes(nfc(name)), student_id))
    _forget_students()
    _forget_schedules()
    log_change(ui("log.person_edited"), nfc(name))


def student_usage_count(student_id):
    with get_conn() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM schedules WHERE student_id = ? OR assistant_id = ?",
            (student_id, student_id),
        ).fetchone()[0]


def delete_student(student_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM students WHERE id = ?", (student_id,))
    _forget_students()
    log_change(ui("log.person_deleted"), f"id {student_id}")


@st.cache_data(show_spinner=False)
def _schedules(schema_name):
    df = read_df(
            """
            SELECT sc.id, sc.meeting_date, sc.meeting_type, sc.part_no, sc.part_name,
                   sc.minutes, sc.section, sc.role, sc.student_part, sc.needs_assistant,
                   sc.student_id, sc.assistant_id, sc.sort_order,
                   COALESCE(sc.hall, 'main_hall') AS hall,
                   COALESCE(s.name, sc.assigned_person) AS person,
                   COALESCE(a.name, sc.assistant_name) AS assistant
              FROM schedules sc
              LEFT JOIN students s ON s.id = sc.student_id
              LEFT JOIN students a ON a.id = sc.assistant_id
             ORDER BY sc.meeting_date DESC, sc.meeting_type, sc.sort_order, sc.id
            """)
    # NaN is truthy, so turn missing names into None for simple `or` checks.
    for col in ("person", "assistant"):
        df[col] = df[col].astype(object).where(df[col].notna(), None)
    return df


def get_schedules():
    """Every page that shows a meeting opens with this join, so it is run once
    per change rather than once per rerun — cleared by _forget_schedules()."""
    return _schedules(schema())


def save_template(name, file_name, raw):
    """Store a blank form (the official S-89) so printing is one click."""
    import base64
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO templates (name, file_name, data) VALUES (?, ?, ?) "
            "ON CONFLICT(name) DO UPDATE SET file_name = excluded.file_name, "
            "data = excluded.data",
            (name, file_name, base64.b64encode(raw).decode("ascii")))
    _forget_templates()
    log_change(ui("log.form_saved"), f"{name}: {file_name}")


def delete_template(name):
    with get_conn() as conn:
        conn.execute("DELETE FROM templates WHERE name = ?", (name,))
    _forget_templates()
    log_change(ui("log.form_removed"), name)


@st.cache_data(show_spinner=False)
def _templates(schema_name):
    with get_conn() as conn:
        rows = conn.execute("SELECT name, file_name, data FROM templates").fetchall()
    return {name: (file_name, data) for name, file_name, data in rows}


def _forget_templates():
    _templates.clear()


def load_template(name):
    """(bytes, file name) for a stored blank form, or (None, "")."""
    import base64
    entry = _templates(schema()).get(name)
    if not entry:
        return None, ""
    file_name, data = entry
    try:
        return base64.b64decode(data), file_name
    except Exception:
        return None, ""




BACKUP_REMINDER_DAYS = 14


def days_since_backup():
    """Whole days since a backup file was downloaded, or None if never."""
    stamp = get_setting("last_export", "")
    if not stamp:
        return None
    try:
        return (date.today() - datetime.strptime(stamp, "%Y-%m-%d").date()).days
    except ValueError:
        return None


def backup_overdue():
    """(overdue, days) — the database is the only copy until one is taken."""
    days = days_since_backup()
    if days is None:
        return True, None
    return days >= BACKUP_REMINDER_DAYS, days


@st.cache_data(ttl=60, show_spinner=False)
def status_text():
    """What the sidebar says about storage. Checked once a minute rather than
    on every rerun: every click in the app used to cost a round trip here."""
    try:
        with get_conn() as conn:
            conn.execute("SELECT 1")
    except Exception as exc:
        return "error", f"Database unreachable: {str(exc)[:120]}"
    return "success", "Database connected."


def fill_counts(rows):
    """(filled, needed) for a set of schedule rows: a part plus, where the part
    calls for one, its assistant."""
    needed = len(rows) + int((rows["needs_assistant"] == 1).sum())
    filled = int(rows["person"].notna().sum()) + int(
        ((rows["needs_assistant"] == 1) & rows["assistant"].notna()).sum())
    return filled, needed




def saved_meetings(schedules_df):
    """[(date, type), ...] newest first."""
    if schedules_df.empty:
        return []
    pairs = schedules_df[["meeting_date", "meeting_type"]].drop_duplicates()
    return list(pairs.itertuples(index=False, name=None))


def meeting_label(pair):
    return f"{fmt_date(pair[0])} · {pair[1]}"


def meeting_rows(schedules_df, meeting_date, meeting_type):
    """The saved rows of one meeting."""
    df = schedules_df
    return df[(df["meeting_date"] == str(meeting_date))
              & (df["meeting_type"] == meeting_type)]


def load_schedule(meeting_date, meeting_type, schedules_df=None):
    df = get_schedules() if schedules_df is None else schedules_df
    rows = meeting_rows(df, meeting_date, meeting_type)
    slots, picks = [], {}
    for _, r in rows.iterrows():
        role = r["role"] or infer_role(r["part_name"])
        part_no = int(r["part_no"]) if pd.notna(r["part_no"]) else None
        minutes = int(r["minutes"]) if pd.notna(r["minutes"]) else None
        section = r["section"] or default_section(role, meeting_type)
        slot = make_slot(r["part_name"], role, section, part_no, minutes, r["hall"])
        slots.append(slot)
        sid = int(r["student_id"]) if pd.notna(r["student_id"]) else None
        aid = int(r["assistant_id"]) if pd.notna(r["assistant_id"]) else None
        picks[slot_match_key(slot)] = (sid, aid)
    return slots, picks


_META_KEYS = ["heading", "opening_song", "middle_song", "closing_song", "aux", "book", "aux_group"]


@st.cache_data(show_spinner=False)
def _meetings(schema_name):
    """{(date, type): row} for every meeting, in one query.

    Pages ask for one meeting's details at a time, often in a loop over every
    weekend ever saved; one round trip to the database each made the printing
    page slow. Cleared by _forget_schedules() on every write.
    """
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT meeting_date, meeting_type, {', '.join(_META_KEYS)} "
            "FROM meetings").fetchall()
    return {(str(r[0]), r[1]): tuple(r[2:]) for r in rows}


def get_meeting_meta(meeting_date, meeting_type):
    row = _meetings(schema()).get((str(meeting_date), meeting_type))
    keys = _META_KEYS
    meta = dict(zip(keys, row)) if row else {k: "" for k in keys}
    if not row:
        meta["aux"] = None
    for k in ("heading", "opening_song", "middle_song", "closing_song", "book", "aux_group"):
        meta[k] = meta.get(k) or ""
    return meta


MAX_SNAPSHOTS = 40  # keep the history small enough to sync and restore cheaply


def _take_snapshot(conn, meeting_date, meeting_type, reason):
    """Store what's currently saved for this meeting so a save can be undone.

    Called inside an open connection, before the rows are replaced. Saving a
    meeting that has nothing stored yet records an empty snapshot, so undoing
    a first save removes it again rather than leaving it half-there.
    """
    sched_cols = table_columns(conn, "schedules")
    meet_cols = table_columns(conn, "meetings")
    rows = conn.execute(
        f"SELECT {qcols(sched_cols)} FROM schedules "
        "WHERE meeting_date = ? AND meeting_type = ? ORDER BY sort_order, id",
        (str(meeting_date), meeting_type)).fetchall()
    meeting = conn.execute(
        f"SELECT {qcols(meet_cols)} FROM meetings "
        "WHERE meeting_date = ? AND meeting_type = ?",
        (str(meeting_date), meeting_type)).fetchone()
    data = {
        "schedules": [dict(zip(sched_cols, r)) for r in rows],
        "meeting": dict(zip(meet_cols, meeting)) if meeting else None,
    }
    conn.execute(
        """INSERT INTO snapshots (ts, reason, meeting_date, meeting_type, data)
           VALUES (?, ?, ?, ?, ?)""",
        (datetime.now().isoformat(timespec="seconds"), reason,
         str(meeting_date), meeting_type, json.dumps(data, ensure_ascii=False)))
    conn.execute(
        "DELETE FROM snapshots WHERE id NOT IN "
        "(SELECT id FROM snapshots ORDER BY id DESC LIMIT ?)", (MAX_SNAPSHOTS,))


def last_snapshot(meeting_date, meeting_type):
    """The most recent undo point for this meeting: {id, ts, reason, rows, assigned}.

    Counted in the database: the schedule page asks on every rerun, and the
    snapshot itself is a full copy of the meeting that only Undo needs.
    """
    with get_conn() as conn:
        row = conn.execute(
            '''SELECT id, ts, reason,
                      json_array_length(data::json -> 'schedules'),
                      (SELECT COUNT(*) FROM json_array_elements(data::json -> 'schedules') r
                        WHERE r ->> 'student_id' IS NOT NULL)
                 FROM snapshots
                WHERE meeting_date = ? AND meeting_type = ?
                ORDER BY id DESC LIMIT 1''',
            (str(meeting_date), meeting_type)).fetchone()
    if not row:
        return None
    return {"id": row[0], "ts": row[1], "reason": row[2], "rows": row[3], "assigned": row[4]}


def undo_last(meeting_date, meeting_type):
    """Put back what was stored before the last save or delete.

    The current state is snapshotted first, so undo can itself be undone.
    Returns the number of assignment rows restored, or None when there is
    nothing to undo.
    """
    with get_conn() as conn:
        row = conn.execute(
            """SELECT id, data FROM snapshots
               WHERE meeting_date = ? AND meeting_type = ?
               ORDER BY id DESC LIMIT 1""",
            (str(meeting_date), meeting_type)).fetchone()
        if not row:
            return None
        snap_id, data = row[0], json.loads(row[1])
        _take_snapshot(conn, meeting_date, meeting_type, "before undo")
        conn.execute("DELETE FROM snapshots WHERE id = ?", (snap_id,))
        conn.execute("DELETE FROM schedules WHERE meeting_date = ? AND meeting_type = ?",
                     (str(meeting_date), meeting_type))
        conn.execute("DELETE FROM meetings WHERE meeting_date = ? AND meeting_type = ?",
                     (str(meeting_date), meeting_type))
        for r in data["schedules"]:
            if is_retired(r.get("role"), r.get("meeting_type"), r.get("part_name")):
                continue                             # saved before it was removed
            keep = {k: v for k, v in r.items() if k in _SCHEDULE_COLUMNS}
            conn.execute(
                f"INSERT INTO schedules ({qcols(keep)}) "
                f"VALUES ({', '.join('?' for _ in keep)})", list(keep.values()))
        if data["meeting"]:
            keep = {k: v for k, v in data["meeting"].items() if k in _MEETING_COLUMNS}
            conn.execute(
                f"INSERT INTO meetings ({qcols(keep)}) "
                f"VALUES ({', '.join('?' for _ in keep)})", list(keep.values()))
    restored = sum(1 for r in data["schedules"]
                   if not is_retired(r.get("role"), r.get("meeting_type"),
                                     r.get("part_name")))
    _forget_schedules()
    log_change(ui("log.save_undone"), ui("log.rows_back", date=meeting_date, meeting=ui("mt.midweek"),
                                         count=restored))
    return restored


def _whole_number(value, what, part):
    """A value bound for an INTEGER column, as an int or None.

    Postgres refuses text there, and Streamlit then hides the message that
    says which value it was. A number that arrived as text ("4", "4.0") or as
    a float is converted; anything else stops the save with the part named.
    """
    if value is None or isinstance(value, bool):
        return None if value is None else int(value)
    try:
        if value != value:                      # NaN
            return None
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    if text == "":
        return None
    try:
        number = float(text)
    except ValueError:
        number = None
    if number is None or number != int(number):
        raise ValueError(ui("check.whole_number", part=part, field=what, value=repr(value)))
    return int(number)


def save_schedule(meeting_date, meeting_type, slots, picks, meta, names):
    """Replace everything stored for this date + meeting type."""
    rows = []
    for order, slot in enumerate(slots):
        sid, aid = picks.get(order, (None, None))
        part = slot_label(slot)
        part_no = _whole_number(slot["part_no"], ui("check.part_number"), part)
        minutes = _whole_number(slot.get("minutes"), ui("wb.minutes").lower(), part)
        sid = _whole_number(sid, "id", part)
        aid = _whole_number(aid, "id", part)
        rows.append((
            str(meeting_date), meeting_type, part_no, slot["title"],
            minutes, slot["section"], slot["role"],
            int(slot["student_part"]), int(slot["needs_assistant"]),
            sid, names.get(sid), aid, names.get(aid), order,
            slot.get("hall") or MAIN_HALL,
        ))
    with get_conn() as conn:
        _take_snapshot(conn, meeting_date, meeting_type, "before save")
        conn.execute("DELETE FROM schedules WHERE meeting_date = ? AND meeting_type = ?",
                     (str(meeting_date), meeting_type))
        conn.executemany(
            """INSERT INTO schedules (meeting_date, meeting_type, part_no, part_name,
                   minutes, section, role, student_part, needs_assistant, student_id,
                   assigned_person, assistant_id, assistant_name, sort_order, hall)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        conn.execute(
            """INSERT INTO meetings (meeting_date, meeting_type, heading, opening_song,
                   middle_song, closing_song, aux, book, aux_group)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(meeting_date, meeting_type) DO UPDATE SET
                   heading = excluded.heading, opening_song = excluded.opening_song,
                   middle_song = excluded.middle_song, closing_song = excluded.closing_song,
                   aux = excluded.aux, book = excluded.book, aux_group = excluded.aux_group""",
            (str(meeting_date), meeting_type, meta.get("heading", ""),
             meta.get("opening_song", ""), meta.get("middle_song", ""),
             meta.get("closing_song", ""), int(bool(meta.get("aux"))),
             meta.get("book", ""), meta.get("aux_group", "")),
        )
    _forget_schedules()
    log_change(ui("log.schedule_saved"), f"{meeting_date}: "
               f"{sum(1 for v in picks.values() if isinstance(v, tuple) and v[0])}")


def delete_schedule(meeting_date, meeting_type):
    with get_conn() as conn:
        _take_snapshot(conn, meeting_date, meeting_type, "before delete")
        conn.execute("DELETE FROM schedules WHERE meeting_date = ? AND meeting_type = ?",
                     (str(meeting_date), meeting_type))
        conn.execute("DELETE FROM meetings WHERE meeting_date = ? AND meeting_type = ?",
                     (str(meeting_date), meeting_type))
    _forget_schedules()
    log_change(ui("log.schedule_deleted"), str(meeting_date))




# ---------------------------------------------------------------------------
# Who had what, and when — always relative to one meeting.
#
# Every lookup below takes the meeting being scheduled and looks strictly
# before it ("last time") or strictly after it ("next time"). The meeting
# itself is never its own neighbour: saving a week and saving it again must not
# make everyone on it look as if they had the same part "0 days ago". And a
# later week never hides an earlier one: editing Week 3 with Week 4 already
# saved, "last time" is still Week 2.
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def _assignment_rows(schema_name):
    """[(person, date, role, part_name, assisted)] for every saved assignment,
    in one query. Cleared by _forget_schedules() on every write."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT student_id, meeting_date, role, part_name, 0 FROM schedules
                WHERE student_id IS NOT NULL
               UNION ALL
               SELECT assistant_id, meeting_date, role, part_name, 1 FROM schedules
                WHERE assistant_id IS NOT NULL""").fetchall()
    return [(pid, str(when), role, part_name, assisted)
            for pid, when, role, part_name, assisted in rows]


def _key(meeting_date):
    """One cache entry per meeting, whether it arrives as a date or a string."""
    return str(meeting_date) if meeting_date else ""


def _nearest(meeting_date, keep, after=False):
    """{person: (date, row)} for the closest assignment before (or after)
    meeting_date among the rows `keep` accepts. With no meeting_date, the
    latest overall."""
    cutoff = str(meeting_date) if meeting_date else ""
    out = {}
    for row in _assignment_rows(schema()):
        pid, when = row[0], row[1]
        if not keep(row):
            continue
        if cutoff and (when <= cutoff if after else when >= cutoff):
            continue
        best = out.get(pid)
        if best is None or (when < best[0] if after else when > best[0]):
            out[pid] = (when, row)
    return out


@st.cache_data(show_spinner=False, max_entries=512)
def _lookup(schema_name, meeting_date, kind, role=None, after=False):
    """_nearest() for one meeting and one kind of assignment, remembered.

    The schedule page asks this once per part for the dropdown labels, and
    twice more per pick for the checks, on every click; each answer walked
    every assignment ever saved. Cleared by _forget_schedules().
    """
    keep = {"role": _is_own_part(role), "student": _is_student_part,
            "any": lambda r: True}[kind]
    return _nearest(meeting_date, keep, after)


def _is_own_part(role):
    return lambda row: row[4] == 0 and row[2] == role


def _is_student_part(row):
    return row[2] in STUDENT_ROLES


def last_role_dates(role, meeting_date=None):
    """person -> latest date before this meeting they had this same part
    (either hall). Without a meeting, the latest date overall."""
    return {p: d for p, (d, _) in
            _lookup(schema(), _key(meeting_date), "role", role).items()}


def next_role_dates(role, meeting_date):
    """person -> earliest date after this meeting they have this same part."""
    return {p: d for p, (d, _) in
            _lookup(schema(), _key(meeting_date), "role", role, True).items()}


def last_student_part_dates(meeting_date=None):
    """person -> latest date before this meeting they had any field-ministry
    part or assisted on one.

    The ministry parts are separate roles, so "not the same part twice" lets
    someone take a different one each week. Turn-taking needs them counted
    together.
    """
    return {p: d for p, (d, _) in
            _lookup(schema(), _key(meeting_date), "student").items()}


def next_student_part_dates(meeting_date):
    return {p: d for p, (d, _) in
            _lookup(schema(), _key(meeting_date), "student", None, True).items()}


def last_assignment_dates(meeting_date=None, exclude_date=None):
    """person -> latest date before this meeting they had any part or assisted.

    exclude_date is the old name for meeting_date; "" means no meeting, the
    latest date overall (the participants list).
    """
    meeting_date = meeting_date if meeting_date is not None else exclude_date
    return {p: d for p, (d, _) in
            _lookup(schema(), _key(meeting_date), "any").items()}




def last_assignment_details(meeting_date):
    """person -> (date, role or part, assisted) for their latest assignment before this
    meeting.

    "Bible Reading, 3 weeks ago" says more than a date on its own when you are
    deciding who to give a part to.
    """
    out = {}
    for pid, (when, row) in _lookup(schema(), _key(meeting_date), "any").items():
        _, _, role, part_name, assisted = row
        out[pid] = (when, (role or part_name or "").strip(), bool(assisted))
    return out


def next_assignment_details(meeting_date):
    """person -> (date, role or part, assisted) for their first assignment after this meeting."""
    out = {}
    for pid, (when, row) in _lookup(schema(), _key(meeting_date), "any",
                                     None, True).items():
        _, _, role, part_name, assisted = row
        out[pid] = (when, (role or part_name or "").strip(), bool(assisted))
    return out


def _forget_schedules():
    """Call after anything that changes the schedules table."""
    _schedules.clear()
    _assignment_rows.clear()
    _lookup.clear()
    _meetings.clear()


def role_history(student_id, limit=8):
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT meeting_date,
                      CASE WHEN assistant_id = ? AND COALESCE(student_id, -1) != ?
                           THEN part_name || ' (assistant)' ELSE part_name END,
                      hall
                 FROM schedules
                WHERE student_id = ? OR assistant_id = ?
                ORDER BY meeting_date DESC LIMIT ?""",
            (student_id, student_id, student_id, student_id, limit),
        ).fetchall()
    return rows


def is_suspended(row, on_date):
    """Suspended with no end date, or the end date hasn't passed yet."""
    if not row.get("suspended") or pd.isna(row.get("suspended")):
        return False
    until = row.get("suspended_until")
    if not isinstance(until, str) or not until:
        return True
    return str(on_date) <= until


def get_suspended(students, on_date):
    return {int(r["id"]) for r in students.to_dict("records") if is_suspended(r, on_date)}


def suspension_text(row, today=None):
    today = today or date.today().isoformat()
    if not is_suspended(row, today):
        return ""
    until = row.get("suspended_until")
    return (ui("people.suspended_until", date=fmt_date(until)) if isinstance(until, str) and until
            else ui("people.status_suspended"))


def set_suspension(student_id, suspended, until=None):
    with get_conn() as conn:
        conn.execute(
            "UPDATE students SET suspended = ?, suspended_until = ? WHERE id = ?",
            (int(suspended), until if suspended else None, student_id),
        )
    _forget_students()
    log_change(ui("log.suspension_set" if suspended else "log.suspension_lifted"),
               f"id {student_id}" + (" " + ui("log.until", date=until) if until else ""))


def upcoming_assignments(student_id, until=None):
    today = date.today().isoformat()
    query = """SELECT meeting_date, meeting_type, part_name FROM schedules
                WHERE (student_id = ? OR assistant_id = ?) AND meeting_date >= ?"""
    params = [student_id, student_id, today]
    if until:
        query += " AND meeting_date <= ?"
        params.append(until)
    with get_conn() as conn:
        return conn.execute(query + " ORDER BY meeting_date", params).fetchall()


@st.cache_data(show_spinner=False)
def _unavailable(schema_name):
    """[(person, date)] for every away day, in one query. The schedule page
    asks on every rerun; cleared by set_unavailable() and a restore."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT student_id, meeting_date FROM unavailable "
            "ORDER BY meeting_date").fetchall()
    return [(sid, str(d)) for sid, d in rows]


def _forget_unavailable():
    _unavailable.clear()


def get_unavailable_between(start, end):
    """Everyone away on any date in the range."""
    start, end = str(start), str(end)
    return {sid for sid, d in _unavailable(schema()) if start <= d <= end}


def get_unavailable(meeting_date):
    return get_unavailable_between(meeting_date, meeting_date)


def unavailable_dates(student_id):
    return [d for sid, d in _unavailable(schema()) if sid == student_id]


def away_summary(dates):
    """Collapse consecutive days into ranges: '3–9 Oct, 20 Oct'."""
    days = sorted(datetime.strptime(d, "%Y-%m-%d").date() for d in dates)
    ranges, start, prev = [], None, None
    for d in days + [None]:
        if start is None:
            start = prev = d
        elif d is not None and (d - prev).days == 1:
            prev = d
        else:
            ranges.append(fmt_date(start.isoformat(), short=True) if start == prev else
                          f"{fmt_date(start.isoformat(), short=True)}–"
                          f"{fmt_date(prev.isoformat(), short=True)}")
            start = prev = d
    return ", ".join(ranges)


def set_unavailable(student_id, dates):
    with get_conn() as conn:
        conn.execute("DELETE FROM unavailable WHERE student_id = ?", (student_id,))
        conn.executemany(
            "INSERT INTO unavailable (student_id, meeting_date) VALUES (?, ?)",
            [(student_id, str(d)) for d in dates],
        )
    _forget_unavailable()
    log_change(ui("log.away_changed"), f"id {student_id}: " + ui("log.days", count=len(dates)))


# =============================================================================
# NO-MEETING WEEKS (assemblies, conventions)
# =============================================================================
@st.cache_data(show_spinner=False)
def _no_meeting_periods(schema_name):
    with get_conn() as conn:
        return conn.execute(
            "SELECT id, start_date, end_date, note, kind FROM no_meeting_periods "
            "ORDER BY start_date").fetchall()


def _forget_no_meeting():
    _no_meeting_periods.clear()


def get_no_meeting_periods():
    """[(id, start, end, note, kind), ...], soonest first. kind is
    "assembly" or "convention"."""
    return _no_meeting_periods(schema())


def is_no_meeting(meeting_date):
    """True if this date falls in an assembly or convention week."""
    return event_for(meeting_date) is not None


def event_for(meeting_date):
    """"assembly" or "convention" if this date falls in such a week, else None."""
    d = str(meeting_date)
    for _, start, end, _, kind in get_no_meeting_periods():
        if start <= d <= end:
            return kind if kind in EVENT_KINDS else "assembly"
    return None


def event_text(kind, language="English"):
    """"Assembly Week", "Convention Week", in one slip language ("English" or "Dangme")."""
    strings = TRANSLATIONS.get(language, TRANSLATIONS["English"])
    return strings[f"event_{kind if kind in EVENT_KINDS else 'assembly'}"]


def event_label(meeting_date, language="English"):
    """The label for an assembly or convention week, in that language; else
    None. Printouts and messages use the slip language."""
    kind = event_for(meeting_date)
    return event_text(kind, language) if kind else None


def event_weeks():
    """{Monday (ISO): kind} for every week marked as an assembly or
    convention, whatever its recorded range."""
    out = {}
    for _, start, end, _, kind in get_no_meeting_periods():
        day = datetime.strptime(start, "%Y-%m-%d").date()
        last = datetime.strptime(end, "%Y-%m-%d").date()
        while day <= last:
            out.setdefault(week_start(day).isoformat(),
                           kind if kind in EVENT_KINDS else "assembly")
            day += timedelta(days=7 - day.weekday())
    return out


def meetings_in_week(day):
    """[(date, type)] saved for the Monday–Sunday week holding this day."""
    monday = week_start(day)
    sunday = (monday + timedelta(days=6)).isoformat()
    return sorted((d, t) for d, t in saved_meetings(get_schedules())
                  if monday.isoformat() <= d <= sunday)


def mark_event_week(day, kind):
    """Mark the week holding this day as an assembly or convention week.

    The whole Monday–Sunday week is recorded (replacing any earlier record
    for it), and every meeting already saved in that week is deleted — there
    is no regular meeting that week. Each deletion is snapshotted first, so
    any of them can be undone from the schedule page. Returns the meetings
    that were cleared.
    """
    if kind not in EVENT_KINDS:
        raise ValueError(ui("event.unknown", kind=kind))
    monday = week_start(day)
    sunday = monday + timedelta(days=6)
    cleared = meetings_in_week(monday)
    for meeting_date, meeting_type in cleared:
        delete_schedule(meeting_date, meeting_type)
    with get_conn() as conn:
        conn.execute("DELETE FROM no_meeting_periods WHERE start_date >= ? "
                     "AND end_date <= ?", (monday.isoformat(), sunday.isoformat()))
        conn.execute(
            "INSERT INTO no_meeting_periods (start_date, end_date, note, kind) "
            "VALUES (?, ?, ?, ?)",
            (monday.isoformat(), sunday.isoformat(), _t(f"ev.{kind}", "en"), kind))
    _forget_no_meeting()
    log_change(ui("event.marked", kind=ui(f"ev.{kind}")),
               f"{monday} – {sunday}" + (ui("month.cleared", count=len(cleared)) if cleared else ""))
    return cleared




def delete_no_meeting_period(period_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM no_meeting_periods WHERE id = ?", (period_id,))
    _forget_no_meeting()
    log_change(ui("log.event_removed"), f"id {period_id}")


# Typists substitute 3 ) N for ɛ ɔ ŋ when the keyboard lacks them (Admin → Settings turns the conversion on).
LETTER_SUBSTITUTES = {"3": "ɛ", ")": "ɔ", "N": "ŋ"}


def apply_letter_substitutes(text):
    if not get_setting("letter_convert", "0") == "1":
        return text
    out = []
    for ch in text or "":
        # only convert a capital N between letters, so real initials survive
        if ch == "N":
            out.append(ch)
        else:
            out.append(LETTER_SUBSTITUTES.get(ch, ch))
    result = "".join(out)
    # standalone N -> ŋ only when clearly mid-word (letter on both sides)
    result = re.sub(r"(?<=[A-Za-zɛɔŋ])N(?=[a-zɛɔŋ])", "ŋ", result)
    return result
