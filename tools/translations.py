# -*- coding: utf-8 -*-
"""The Dangme translation spreadsheet: make it from the message files, and read a filled-in one back.

    python3 tools/translations.py export dangme-translations.xlsx
    python3 tools/translations.py import dangme-translations.xlsx

export writes one tab per screen (from api/messages/notes.json) with Key / English / Dangme / Notes, plus two tabs holding
this repository's guides (README.md and docs/setup.en.md), a paragraph per row. import writes the Dangme column into
api/messages/ada.json and builds README.ada.md and docs/setup.ada.md, with any paragraph not yet translated left in
English. Needs openpyxl (pip install openpyxl).
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MESSAGES = ROOT / "api" / "messages"
GUIDES = {"guide.readme": ("README.md", "README.ada.md"), "guide.setup": ("docs/setup.en.md", "docs/setup.ada.md")}
GUIDE_TABS = {"guide.readme": "Guide - README", "guide.setup": "Guide - setup"}
NOT_YET = ("> Wording not translated yet is shown in English. To translate it, see "
           "[docs/translating.md](docs/translating.md).")


def _flat(tree, prefix=""):
    out = {}
    for key, value in tree.items():
        if isinstance(value, dict):
            out.update(_flat(value, f"{prefix}{key}."))
        else:
            out[f"{prefix}{key}"] = value
    return out


def _nest(flat, like):
    """flat values put back in the shape (and key order) of `like`."""
    def walk(tree, prefix):
        return {k: walk(v, f"{prefix}{k}.") if isinstance(v, dict) else flat.get(f"{prefix}{k}", "")
                for k, v in tree.items()}
    return walk(like, "")


def _load(name):
    return json.loads((MESSAGES / name).read_text(encoding="utf-8"))


def _blocks(text):
    """A guide's translatable pieces, in order: (kind, text). kind is "fixed" for what stays as it is (blank lines,
    code, table rules) and "text" for a line to translate. A line's leading markup (#, -, 1., |) is kept apart."""
    out, code = [], False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            code = not code
            out.append(("fixed", line))
        elif code or not line.strip() or re.fullmatch(r"\s*\|?[\s:|-]+\|?\s*", line):
            out.append(("fixed", line))
        else:
            out.append(("text", line))
    return out


def _guide_rows(key):
    source = (ROOT / GUIDES[key][0]).read_text(encoding="utf-8")
    n = 0
    for kind, line in _blocks(source):
        if kind == "text":
            n += 1
            yield f"{key}.{n:03d}", line


def export(path):
    import openpyxl
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    en, ada, notes = _flat(_load("en.json")), _flat(_load("ada.json")), _load("notes.json")
    book = openpyxl.Workbook()
    head_fill, head_font = PatternFill("solid", fgColor="3A1650"), Font(bold=True, color="FFFFFF")
    todo, done = PatternFill("solid", fgColor="FFF4D6"), PatternFill("solid", fgColor="E3F1E6")
    wrap, line = Alignment(wrap_text=True, vertical="top"), Side(style="thin", color="D9D9D9")

    start = book.active
    start.title = "Start here"
    for i, text in enumerate([
            "Meeting Organizer: Dangme wording",
            "Fill in the yellow Dangme column on each tab. Leave a cell empty if you are unsure: the app shows the "
            "English until it is filled. Green cells are already filled in; change them if they are wrong.",
            "Words in curly brackets, like {name} or {count}, are filled in by the app. Keep them exactly as they "
            "are, but move them to wherever they belong in the Dangme sentence.",
            "Keep symbols such as · — • * and emoji where they make sense. A * on both sides makes words bold in "
            "WhatsApp. On the guide tabs, keep the # - 1. | ` and [link](address) markings as they are.",
            "The Workbook keywords tab is not a translation: copy the exact words printed in the Dangme workbook.",
            "Send the file back, or read it in yourself: python3 tools/translations.py import <this file>"], 1):
        cell = start.cell(row=i, column=1, value=text)
        cell.font, cell.alignment = Font(bold=i == 1, size=16 if i == 1 else 11), wrap
    start.column_dimensions["A"].width = 110

    def tab(title, about, rows):
        sheet = book.create_sheet(title[:31])
        sheet.cell(row=1, column=1, value=about).font = Font(italic=True, color="555555")
        for j, name in enumerate(["Key", "English", "Dangme", "Notes"], 1):
            cell = sheet.cell(row=2, column=j, value=name)
            cell.font, cell.fill = head_font, head_fill
        for i, (key, english, dangme, note) in enumerate(rows, 3):
            sheet.cell(row=i, column=1, value=key).font = Font(name="Consolas", size=9, color="777777")
            sheet.cell(row=i, column=2, value=english).alignment = wrap
            cell = sheet.cell(row=i, column=3, value=dangme or None)
            cell.fill, cell.alignment = (done if dangme else todo), wrap
            sheet.cell(row=i, column=4, value=note).alignment = wrap
            for j in range(1, 5):
                sheet.cell(row=i, column=j).border = Border(bottom=line)
        for col, width in zip("ABCD", (24, 60, 60, 45)):
            sheet.column_dimensions[col].width = width
        sheet.freeze_panes = "C3"

    placed = set()
    for group in notes["groups"]:
        keys = [k for k in en if k.split(".", 1)[0] in group["prefixes"]]
        placed.update(keys)
        tab(group["name"], group["about"],
            [(k, en[k], ada.get(k, ""), " ".join(x for x in (notes["sources"].get(k), notes["notes"].get(k)) if x))
             for k in keys])
    rest = [k for k in en if k not in placed]
    if rest:
        tab("Other", "Wording not in any other tab.", [(k, en[k], ada.get(k, ""), notes["notes"].get(k, ""))
                                                       for k in rest])

    old = _guide_translations()
    for key, title in GUIDE_TABS.items():
        tab(title, f"{GUIDES[key][0]}, a line per row. The Dangme page is {GUIDES[key][1]}.",
            [(k, text, old.get(k, ""), "") for k, text in _guide_rows(key)])
    book.save(path)
    print(f"Wrote {path}: {len(en)} messages, {sum(1 for v in ada.values() if v)} in Dangme.")


def _localise(text, target):
    """The links in a Dangme guide: to the Dangme pages, and the language link back to English."""
    text = text.replace("[Dangme](README.ada.md)", "[English](README.md)")
    text = text.replace("[Dangme](setup.ada.md)", "[English](setup.en.md)")
    text = text.replace("](docs/setup.en.md)", "](docs/setup.ada.md)")
    if target.startswith("docs/"):
        text = text.replace("](docs/", "](")
    return text


def _guide_translations():
    """What is already translated in the Dangme guides, by row key, so a new export keeps it."""
    out = {}
    for key, (source, target) in GUIDES.items():
        target = ROOT / target
        if not target.exists():
            continue
        english = [line for kind, line in _blocks((ROOT / source).read_text(encoding="utf-8")) if kind == "text"]
        dangme = [line for kind, line in _blocks(target.read_text(encoding="utf-8")) if kind == "text"
                  and line != NOT_YET]
        if len(dangme) == len(english):
            for n, (e, d) in enumerate(zip(english, dangme), 1):
                if d != _localise(e, GUIDES[key][1]):
                    out[f"{key}.{n:03d}"] = d
    return out


def _write_guides(rows):
    for key, (source, target) in GUIDES.items():
        n, lines, missing = 0, [], 0
        for kind, line in _blocks((ROOT / source).read_text(encoding="utf-8")):
            if kind == "text":
                n += 1
                done = rows.get(f"{key}.{n:03d}", "")
                missing += not done
                lines.append(done or line)
            else:
                lines.append(line)
        if missing:
            # under the title and its one-line summary
            at = next((i + 1 for i, l in enumerate(lines) if l.startswith("> ")), 1)
            lines[at:at] = ["", NOT_YET]
        text = "\n".join(lines) + "\n"
        text = _localise(text, target)
        (ROOT / target).write_text(text, encoding="utf-8")
        print(f"Wrote {target}: {n - missing} of {n} lines in Dangme.")


def import_(path):
    import openpyxl

    en_tree = _load("en.json")
    en = _flat(en_tree)
    ada = _flat(_load("ada.json"))
    guides, unknown = {}, []
    for sheet in openpyxl.load_workbook(path, data_only=True).worksheets[1:]:
        for key, _english, dangme, *_ in sheet.iter_rows(min_row=3, values_only=True):
            if not key:
                continue
            value = unicodedata.normalize("NFC", str(dangme).strip()) if dangme is not None else ""
            if key.startswith("guide."):
                guides[key] = value
            elif key in en:
                ada[key] = value
            else:
                unknown.append(key)
    (MESSAGES / "ada.json").write_text(json.dumps(_nest(ada, en_tree), ensure_ascii=False, indent=2) + "\n",
                                       encoding="utf-8")
    print(f"Wrote api/messages/ada.json: {sum(1 for k in en if ada.get(k))} of {len(en)} in Dangme.")
    if unknown:
        print("Skipped keys the app no longer has:", ", ".join(unknown))
    _write_guides(guides)
    print("Now run: npm run check:messages")


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("export", "import"):
        sys.exit(__doc__)
    (export if sys.argv[1] == "export" else import_)(sys.argv[2])
