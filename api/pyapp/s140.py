# -*- coding: utf-8 -*-
"""Fill a blank S-140 midweek-meeting template (.docx) from schedule data.

Adapted from the midweek-meeting-schedule filler. `data` uses the same shape as that script's data.json, plus the
slip language, whose words (song, minutes, group, the meeting's name) are written where the blank had its own:

{
  "congregation": "...", "aux": true if any week uses the classroom, "language": "English" or "Dangme",
  "weeks": [{
    "heading": "...", "chairman": "...", "opening_song": "...", "opening_prayer": "...",
    "treasures": [{"title", "min", "name"} x3],
    "ministry": [{"title", "min", "name", "assistant"?, "name2"?, "assistant2"?}, ...],
    "middle_song": "...",
    "living": [{"title", "min", "name"}, ...],
    "cbs": {"title", "min", "name"},
    "closing_song": "...", "closing_prayer": "..."
  }]
}
"""
import copy
import io
import re

import docx
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from i18n import doc, ui

NB = "\u00a0"  # spacer the template uses before "(Min. X)"
# The blank is published per language. The English and the Dangme blanks both mark their date row [DATE]; the
# congregation is [CONGREGATION] on the English one and [ASAFO Ɔ BIƐ] on the Dangme one. Only these markers are
# searched for; every other placeholder is replaced by position, and the two blanks have the same rows.
DATE_MARKERS = ("[DATE]", "[DEETI]")
CONG_MARKERS = ("[ASAFO", "[CONGREGATION")
BLOCK_LEN = 24  # rows per week block, date row inclusive
OFF = dict(group=1, opening_song=3, treasures_hdr=6, treasures=7,
           ministry_hdr=11, ministry=12, middle_song=18, living=19,
           cbs=21, closing_song=23)
N_MINISTRY, N_LIVING = 4, 2


class S140Error(Exception):
    pass


def _txt(el):
    return "".join(n.text or "" for n in el.iter(qn("w:t")))


def _set_text(tc, text):
    ps = tc.findall(qn("w:p"))
    p = ps[0]
    for e in ps[1:]:
        tc.remove(e)
    runs = p.findall(qn("w:r"))
    if text == "":
        for r in runs:
            p.remove(r)
        return
    if not runs:
        r = OxmlElement("w:r")
        p.append(r)
        runs = [r]
    first = runs[0]
    for r in runs[1:]:
        p.remove(r)
    for child in list(first):
        if child.tag != qn("w:rPr"):
            first.remove(child)
    t = OxmlElement("w:t")
    t.set(qn("xml:space"), "preserve")
    t.text = text
    first.append(t)


def _run_props(tc):
    """The run formatting of a cell, to reuse on one that has none.

    The rows at the top of the blank are empty — no runs, so nothing to inherit
    from — and text written there would come out in Word's default font instead
    of the form's.
    """
    for run in tc.iter(qn("w:r")):
        props = run.find(qn("w:rPr"))
        if props is not None:
            return copy.deepcopy(props)
    return None


def _set_styled(tc, text, props):
    _set_text(tc, text)
    if props is None:
        return
    for run in tc.iter(qn("w:r")):
        if run.find(qn("w:rPr")) is None:
            run.insert(0, copy.deepcopy(props))


def _cells(tr):
    return tr.findall(qn("w:tc"))


def _S(tr, idx, text):
    cs = _cells(tr)
    if idx < len(cs):
        _set_text(cs[idx], text or "")


def _song(value, word):
    """"Song 74" or "La 74", in the template's language.

    Setting a cell replaces everything in it, including the template's own
    "Song"/"La", so the word has to be written back with the number.
    """
    text = str(value or "").strip()
    if not text:
        return ""
    found = re.search(r"\d+", text)
    if not found:
        return text
    return f"{word} {found.group()}"


def _is_date_row(tr):
    text = _txt(tr)
    return any(marker in text for marker in DATE_MARKERS)


def _repeat_table(doc, tbl, extra, blocks):
    """Append `extra` more week blocks by copying the ones already there.

    The published blank is one week to a sheet. Copying its rows lets a whole
    month come out of the one template, with a page break before each new week
    so they do not run together.
    """
    rows = tbl.findall(qn("w:tr"))
    per_block = len(rows) // max(blocks, 1)
    template_rows = rows[-per_block:] if per_block else rows
    for _ in range(extra):
        for tr in template_rows:
            tbl.append(copy.deepcopy(tr))


def _part(n, item, minutes="Min."):
    m = str(item.get("min", "") or "").strip()
    title = item["title"].strip()
    return "%d. %s%s(%s %s)" % (n, title, NB, minutes, m) if m else "%d. %s" % (n, title)


def check_s140_template(template_bytes):
    """Raise S140Error unless this is the blank S-140, so a wrong file is
    refused when it is chosen rather than when someone tries to export."""
    try:
        document = docx.Document(io.BytesIO(template_bytes))
    except Exception as exc:
        raise S140Error(ui("err.s140_word", reason=str(exc)[:120])) from exc
    if not document.tables:
        raise S140Error(ui("err.s140_no_table"))
    trs = document.tables[0]._tbl.findall(qn("w:tr"))
    weeks = sum(1 for tr in trs if _is_date_row(tr))
    if not weeks:
        raise S140Error(ui("err.s140_no_date"))
    return weeks


def fill_s140(template_bytes, data):
    """Return the filled template as bytes.

    When no week in the month uses the auxiliary classroom, its column
    caption is cleared and the column narrowed to give names more room.
    """
    weeks = data["weeks"]
    keep_aux_column = bool(data.get("aux"))
    language = data.get("language") or "English"
    song_word = doc("doc.song", language)
    minutes_word = doc("doc.s140_minutes", language)
    document = docx.Document(io.BytesIO(template_bytes))
    if not document.tables:
        raise S140Error(ui("err.s140_no_table"))
    tbl = document.tables[0]._tbl
    trs = tbl.findall(qn("w:tr"))

    date_rows = [i for i, tr in enumerate(trs) if _is_date_row(tr)]
    head_rows = [i for i, tr in enumerate(trs)
                 if any(m in _txt(tr) for m in CONG_MARKERS)]
    if not date_rows:
        raise S140Error(ui("err.s140_no_date"))
    if len(weeks) > len(date_rows):
        # the published blank holds a single week, so it is repeated as many
        # times as the month needs rather than refusing the export
        _repeat_table(document, tbl, len(weeks) - len(date_rows), len(date_rows))
        trs = tbl.findall(qn("w:tr"))
        date_rows = [i for i, tr in enumerate(trs) if _is_date_row(tr)]
        head_rows = [i for i, tr in enumerate(trs)
                     if any(m in _txt(tr) for m in CONG_MARKERS)]
    if len(weeks) > len(date_rows):                     # pragma: no cover
        raise S140Error(ui("err.s140_blocks", blocks=len(date_rows), weeks=len(weeks)))

    cong = data.get("congregation")
    if cong:
        for i in head_rows:
            _S(trs[i], 0, cong)

    drop = []
    for wi, w in enumerate(weeks):
        b = date_rows[wi]
        blk = {k: trs[b + v] for k, v in OFF.items()}
        _S(trs[b], 0, w.get("heading", ""))
        _S(trs[b], 2, w.get("event") or w.get("chairman", ""))

        # The meeting and congregation head the whole document, once, on the
        # blank row above the first week's date. The date cell's formatting is
        # copied rather than the label's: the label is 8pt and grey, the date
        # is bold at the table's own size.
        if wi == 0 and b >= 2:
            date_props = _run_props(_cells(trs[b])[0]) if _cells(trs[b]) else None
            meeting_name = data.get("meeting_name") or doc("doc.midweek_title", language)
            top = _cells(trs[b - 2])
            if len(top) >= 2:
                _set_styled(top[0], meeting_name, date_props)
                _set_styled(top[1], cong or "", date_props)
            elif top:
                _set_styled(top[0], meeting_name, date_props)

        if w.get("event"):
            # an assembly or convention week: the date row holds its label, and
            # the rest of the week's block goes
            if len(_cells(trs[b])) >= 2:
                _S(trs[b], 1, "")
            drop += trs[b + 1:b + BLOCK_LEN]
            continue

        # The counselor line. On the published blank this row is
        # [blank | "Tsu Wayo ɔ Mi Ga Wolɔ:" | name], so the name goes in the third cell
        # — writing it to the second replaced the form's own label.
        group_cells = _cells(blk["group"])
        counselor_cells = len(group_cells)
        if w.get("aux"):
            if counselor_cells >= 3:
                _S(blk["group"], 2, w.get("aux_counselor", ""))
                # the group sits on the counselor's line, in the cell the form
                # leaves free there, and in the label's own font
                group = str(w.get("aux_group") or "").strip()
                if group:
                    # the room is already named by the label beside it
                    word = doc("doc.group", language)
                    _set_styled(group_cells[0], f"{word} {group}",
                                _run_props(group_cells[1]))
            else:
                _S(blk["group"], 1, w.get("aux_counselor", ""))
        elif counselor_cells >= 3:
            # no classroom this week: take the label and the name away
            _S(blk["group"], 1, "")
            _S(blk["group"], 2, "")
        else:
            _S(blk["group"], 0, "")
            _S(blk["group"], 1, "")
            _S(blk["group"], 2, "")

        _S(blk["opening_song"], 1, _song(w.get("opening_song"), song_word))
        _S(blk["opening_song"], 3, w.get("opening_prayer", ""))

        if not keep_aux_column:
            for key in ("treasures_hdr", "ministry_hdr"):
                _S(blk[key], 1, "")

        n = 1
        for k, item in enumerate(w["treasures"][:3]):
            tr = trs[b + OFF["treasures"] + k]
            _S(tr, 1, _part(n, item, minutes_word))
            if len(_cells(tr)) >= 5:
                _S(tr, 3, item.get("name2", ""))
                _S(tr, 4, item.get("name", ""))
            else:
                _S(tr, 2, item.get("name", ""))
            n += 1

        ministry = w.get("ministry", [])
        slots = [trs[b + OFF["ministry"] + k] for k in range(N_MINISTRY)]
        while len(slots) < len(ministry):
            clone = copy.deepcopy(slots[-1])
            slots[-1].addnext(clone)
            slots.append(clone)
        for k, item in enumerate(ministry):
            tr = slots[k]
            _S(tr, 1, _part(n, item, minutes_word))
            names = item.get("name", "")
            if item.get("assistant"):
                names = "%s/%s" % (names, item["assistant"])
            aux_names = item.get("name2", "")
            if aux_names and item.get("assistant2"):
                aux_names = "%s/%s" % (aux_names, item["assistant2"])
            _S(tr, 3, aux_names)  # Tsu Wayo ɔ = auxiliary classroom
            _S(tr, 4, names)      # Asa a Nɔ = main hall
            n += 1
        drop += slots[len(ministry):]

        _S(blk["middle_song"], 1, _song(w.get("middle_song"), song_word))
        living = w.get("living", [])
        slots = [trs[b + OFF["living"] + k] for k in range(N_LIVING)]
        while len(slots) < len(living):
            clone = copy.deepcopy(slots[-1])
            slots[-1].addnext(clone)
            slots.append(clone)
        for k, item in enumerate(living):
            tr = slots[k]
            _S(tr, 1, _part(n, item, minutes_word))
            _S(tr, 2, "")
            _S(tr, 3, item.get("name", ""))
            n += 1
        drop += slots[len(living):]

        cbs = w["cbs"]
        _S(blk["cbs"], 1, _part(n, cbs, minutes_word))
        _S(blk["cbs"], 3, cbs.get("name", ""))

        _S(blk["closing_song"], 1, _song(w.get("closing_song"), song_word))
        _S(blk["closing_song"], 3, w.get("closing_prayer", ""))

    for wi in range(len(weeks), len(date_rows)):
        b = date_rows[wi]
        start = b - 2 if (b - 2) in head_rows else b - 1
        drop += trs[start:b + BLOCK_LEN]

    for tr in drop:
        if tr.getparent() is not None:
            tr.getparent().remove(tr)

    for tr in tbl.findall(qn("w:tr")):
        cs = _cells(tr)
        if cs and re.fullmatch(r"\d{1,2}:\d{2}", _txt(cs[0]).strip() or "x"):
            _set_text(cs[0], "")

    # give the name columns room
    grid = tbl.find(qn("w:tblGrid"))
    cols = grid.findall(qn("w:gridCol"))
    w_ = [int(c.get(qn("w:w"))) for c in cols]
    shift = min(600, max(0, w_[0] - 20))
    w_[0] -= shift
    w_[2] += shift
    shift2 = 0 if keep_aux_column else min(900, max(0, w_[-2] - 1400))
    w_[-2] -= shift2
    w_[-1] += shift2
    for c, v in zip(cols, w_):
        c.set(qn("w:w"), str(v))
    for tr in tbl.findall(qn("w:tr")):
        start = 0
        for tc in _cells(tr):
            pr = tc.find(qn("w:tcPr"))
            gs = pr.find(qn("w:gridSpan")) if pr is not None else None
            span = int(gs.get(qn("w:val"))) if gs is not None else 1
            tcw = pr.find(qn("w:tcW")) if pr is not None else None
            if tcw is not None and tcw.get(qn("w:type")) == "dxa":
                tcw.set(qn("w:w"), str(sum(w_[start:start + span])))
            start += span

    cur = tbl
    while cong:
        rows = cur.findall(qn("w:tr"))
        idx = [i for i, tr in enumerate(rows) if _txt(tr).strip().startswith(cong)]
        if len(idx) < 2:
            break
        split = idx[1]
        nxt = copy.deepcopy(cur)
        for tr in nxt.findall(qn("w:tr"))[:split]:
            nxt.remove(tr)
        for tr in rows[split:]:
            cur.remove(tr)
        pb = OxmlElement("w:p")
        r = OxmlElement("w:r")
        br = OxmlElement("w:br")
        br.set(qn("w:type"), "page")
        r.append(br)
        pb.append(r)
        cur.addnext(nxt)
        cur.addnext(pb)
        cur = nxt

    out = io.BytesIO()
    document.save(out)
    return out.getvalue()
