# -*- coding: utf-8 -*-
"""The Python function the pages call: sign-in, the editor, saving and every document, end to end."""
import base64
import hashlib
import hmac
import json
import time

import pytest

import db

_ORIGINAL_POOL = db._pool
import importlib.util  # noqa: E402
from pathlib import Path  # noqa: E402

# loaded by path: "index" is too generic a name to import from tests
_spec = importlib.util.spec_from_file_location(
    "api_py", Path(__file__).resolve().parent.parent / "api" / "index.py")
api = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(api)   # replaces db._pool with one connection per request

db._pool = _ORIGINAL_POOL       # the other tests clear the cached pool between tests


SECRET = "test-secret"


def _cookie(expires_in=3600, secret=SECRET):
    body = base64.urlsafe_b64encode(json.dumps({"e": time.time() + expires_in}).encode()).rstrip(b"=").decode()
    sig = base64.urlsafe_b64encode(
        hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest()).rstrip(b"=").decode()
    return f"{api.COOKIE}={body}.{sig}"


@pytest.fixture
def call(core, monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", SECRET)
    monkeypatch.setattr(api, "_schema_checked", False)

    def go(op, method="GET", body=None, raw=None, cookie=None, **params):
        query = "&".join(f"{k}={v}" for k, v in {"op": op, **params}.items())
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        status, ctype, out, headers = api.handle(method, f"/api/py?{query}",
                                                 {"cookie": cookie or _cookie()}, data)
        return status, ctype, (json.loads(out) if ctype == "application/json" else out), headers
    return go


def _suggest(call, editor, day):
    status, _, out, _ = call("suggest", "POST", {"date": day, "slots": editor["slots"],
                                                 "picks": editor["picks"]})
    assert status == 200, out
    picks = [dict(p) for p in editor["picks"]]
    for i, (sid, aid) in out["picks"].items():
        picks[int(i)] = {"sid": sid, "aid": aid}
    return picks


def test_sign_in_is_required(call):
    assert call("ping", cookie="nothing")[0] == 401
    assert call("ping", cookie=_cookie(secret="another"))[0] == 401
    assert call("ping", cookie=_cookie(expires_in=-10))[0] == 401
    status, _, out, _ = call("ping")
    assert status == 200 and out["ok"]


def test_a_meeting_is_edited_saved_and_printed(call, people):
    status, _, editor, _ = call("editor", "POST", {"date": "2026-11-04"})
    assert status == 200 and editor["event"] is None and not editor["saved"]
    assert editor["slots"] and len(editor["picks"]) == len(editor["slots"])
    assert "Week 1 of November" in editor["weekLabel"]

    picks = _suggest(call, editor, "2026-11-04")
    assert any(p["sid"] for p in picks)

    status, _, saved, _ = call("save", "POST", {"date": "2026-11-04", "slots": editor["slots"],
                                                "picks": picks, "aux": editor["aux"],
                                                "meta": {"heading": "NOVEMBER 2–8", "opening_song": "Song 44"}})
    assert status == 200, saved
    assert "4 November 2026" in saved["message"]

    meeting = "2026-11-04|Midweek Meeting"
    status, ctype, pdf, headers = call("sheet", meetings=meeting, lang="Dangme")
    assert status == 200 and ctype == "application/pdf" and pdf.startswith(b"%PDF")
    assert "attachment" in headers["Content-Disposition"]

    status, ctype, png, _ = call("card", week="2026-11-04", lang="Dangme", inline=1)
    assert status == 200 and ctype == "image/png"
    status, _, text, _ = call("message_text", week="2026-11-04", lang="English")
    assert status == 200 and text["text"].startswith("*Meeting assignments")

    status, ctype, csv, _ = call("csv")
    assert status == 200 and b"Midweek Meeting" in csv

    # without the official forms uploaded, slips and the S-140 say so
    status, _, out, _ = call("slips", meetings=meeting, lang="Dangme")
    assert status == 400 and out["error"]
    status, _, out, _ = call("s140", month="2026-11", lang="Dangme")
    assert status == 400 and out["error"]

    status, _, undone, _ = call("undo", "POST", {"date": "2026-11-04"})
    assert status == 200


def test_the_dangme_forms_upload_and_fill(call, people):
    from conftest import form

    s89, s140 = form("S-89_DG.pdf"), form("S-140_DG.docx")
    assert call("template_upload", "POST", raw=s89, kind="s89", lang="Dangme", name="S-89.pdf")[0] == 200
    assert call("template_upload", "POST", raw=s140, kind="s140", lang="Dangme", name="S-140.docx")[0] == 200

    editor = call("editor", "POST", {"date": "2026-11-04"})[2]
    picks = _suggest(call, editor, "2026-11-04")
    assert call("save", "POST", {"date": "2026-11-04", "slots": editor["slots"], "picks": picks,
                                 "aux": False, "meta": {"heading": "NOVEMBER 2–8"}})[0] == 200

    status, ctype, pdf, _ = call("slips", meetings="2026-11-04|Midweek Meeting", lang="Dangme")
    assert status == 200 and ctype == "application/pdf"
    status, ctype, docx, headers = call("s140", month="2026-11", lang="Dangme")
    assert status == 200 and docx[:2] == b"PK"
    assert "November" in headers["Content-Disposition"]


def test_the_dangme_workbook_uploads(call):
    from conftest import form

    status, _, out, _ = call("workbook_upload", "POST", raw=form("mwb_DG_202611.pdf"), name="mwb_DG_202611.pdf", skipPast=0)
    assert status == 200, out
    status, _, editor, _ = call("editor", "POST", {"date": "2026-11-11"})
    assert status == 200, editor
    assert editor["workbook"]["matched"] == "NOVEMBER 9–15"
    assert editor["meta"]["book"] == "YEREMIA 51-52"


def test_an_assembly_week_and_the_app_language(call, core):
    assert call("mark_event", "POST", {"day": "2026-11-18", "kind": "assembly"})[0] == 200
    editor = call("editor", "POST", {"date": "2026-11-18"})[2]
    assert editor["event"] == "Assembly Week"

    core.set_setting("app_language", "ada")
    status, _, out, _ = call("nothing_here", "POST", {})
    assert status == 404 and out["error"]


def test_the_wsgi_app_answers_like_the_handler(call, people):
    import io
    from wsgiref.util import setup_testing_defaults

    environ = {"REQUEST_METHOD": "GET", "PATH_INFO": "/api/py", "QUERY_STRING": "op=ping",
               "HTTP_COOKIE": _cookie(), "wsgi.input": io.BytesIO(b"")}
    setup_testing_defaults(environ)
    seen = {}
    body = b"".join(api.app(environ, lambda status, headers: seen.update(status=status, headers=dict(headers))))
    assert seen["status"] == "200 OK" and json.loads(body)["ok"]

    environ = {"REQUEST_METHOD": "POST", "PATH_INFO": "/api/py", "QUERY_STRING": "op=editor",
               "HTTP_COOKIE": _cookie(), "CONTENT_LENGTH": "22", "wsgi.input": io.BytesIO(b'{"date": "2026-11-04"}')}
    setup_testing_defaults(environ)
    body = b"".join(api.app(environ, lambda status, headers: seen.update(status=status)))
    assert seen["status"] == "200 OK" and json.loads(body)["slots"]
