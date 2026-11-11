# Translating the app into Dangme
> Add or change Dangme wording on the screens, the printed documents and these guides.

## Before you start

- Every word the app shows or prints lives in `api/messages/en.json` (English) and `api/messages/ada.json` (Dangme), under
  the same keys. `ada` is the language code for Dangme.
- An empty Dangme entry shows the English, so the app works while the translation is still being filled in.
- Words in curly brackets, like `{name}` or `{count}`, are filled in by the app. Keep them exactly as they are, but
  move them to wherever they belong in the Dangme sentence.
- For the spreadsheet route you need Python 3 with `openpyxl` (`pip install openpyxl`).

## Steps

### With the spreadsheet (easiest)

1. Make a fresh spreadsheet from the current wording:
   `python3 tools/translations.py export dangme-translations.xlsx`
2. Fill in the yellow **Dangme** column on each tab. Green cells are already filled in; change them if they are
   wrong. The two **Guide** tabs hold this repository's guides, a paragraph per row.
3. Read it back in:
   `python3 tools/translations.py import dangme-translations.xlsx`
   This updates `api/messages/ada.json`, `README.ada.md` and `docs/setup.ada.md`.
4. Check it: `npm run check:messages`
5. Commit and push. Vercel publishes the new wording.

### Directly in the file

1. Open `api/messages/ada.json` and find the key (search `api/messages/en.json` for the English to find it).
2. Type the Dangme between the quotes. Use “ ” for quotation marks, not `'`.
3. Run `npm run check:messages`, then commit and push.

### The workbook keywords

The `kw.*` entries are not translations: they are the exact words printed in the Dangme workbook (section headings,
part titles, the song word and the minutes abbreviation), so the app can read the workbook PDF. Copy them from the
workbook as printed.

## Check it worked

- `npm run check:messages` ends with “All messages are fine.” and says how many are translated.
- With **App language** set to Dangme, the screens show the new wording; with **Slip language** set to Dangme, the
  printouts do.

## If something goes wrong

- **“placeholders differ”.** A `{…}` word was changed, dropped or added. Make it match the English exactly.
- **“not in en.json”.** A key was mistyped or added only in Dangme. Keys come from `en.json`; add new ones there.
- **A Dangme letter prints as a box.** The printouts use DejaVu Sans, which has ɛ ɔ ŋ and the accents. Check the
  letter is a real Dangme letter, not a look-alike from another alphabet.
