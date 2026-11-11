# How Meeting Organizer fits together
> For whoever changes the code: where each part lives and why.

## Before you start

- Node 22 and Python 3.13.
- A Postgres database for the tests (any local one; each test makes and drops its own schema).

## Steps

### The pieces

| Part | Where | What it does |
|---|---|---|
| Screens | `src/app/` (Next.js App Router) | Home, Month overview, Create or edit, Slips and printing, Reminders, Participants, Workbook PDF, Reports, Admin, Sign in |
| Saving from the screens | `src/actions/` | Participants, settings, sign-in. Reads and writes the database through Prisma (`src/lib/db.ts`) |
| The Python service | `api/index.py` | Its own Vercel service (see vercel.json), called by the pages at `/api/py`: the schedule editor, Suggest, saving, undo, the workbook, and every document (slips, sheets, S-140, cards, CSV, backup) |
| Scheduling rules and documents | `api/pyapp/` | `picking.py` (who may take a part, rotation, checks), `db.py`, `workbook.py` (reading the workbook PDF), `sheets_pdf.py`, `slips.py` (S-89), `s140.py`, `card_image.py` (WhatsApp cards) |
| Wording | `api/messages/en.json`, `api/messages/ada.json` | Every string, by key, for both the screens (next-intl) and Python (`api/pyapp/i18n.py`) |
| Tables | `api/db/schema.sql` | The one source of the tables. Run by every build (`tools/setup-db.mjs`) and by Python at start-up. No migrations |
| Look | `src/app/globals.css` | Colour tokens (plum and marigold) and the shared building blocks |
| Translation spreadsheet | `tools/translations.py` | Makes the Dangme spreadsheet from the message files and reads a filled-in one back (see translating.md) |

### Two languages, kept apart

- **App language** (`app_language` setting: `en` or `ada`) is what the screens and their messages are in.
- **Slip language** (`slip_language` setting: `English` or `Dangme`) is what is printed and sent.

In Python, `ui(key)` is the app language and `doc(key, language)` the slip language. The two never mix, so Dangme
screens can print English slips and the other way round.

### One user, midweek only

There is one password (`APP_PASSWORD`) and no user names: the cookie only carries its expiry. The app schedules the
midweek meeting only; weekend roles found in a restored backup are cleared at start-up (`REMOVED_ROLES`).

### Running it on your computer

1. `npm install` and `pip install -r api/requirements.txt`
2. `cp .env.example .env` and fill it in (a separate Neon branch or a local Postgres)
3. `npm run db:setup`
4. `npm run dev:py` in one terminal and `npm run dev` in another, then open http://localhost:3000

## Check it worked

- `npm run check:messages`, `npm run typecheck` and `npm run build` pass.
- `MEETING_DSN=postgresql://user@localhost:5432/db python3 -m pytest tests` passes. Tests that use the published
  forms (the Dangme workbook, S-89 and S-140) run only when copies are in `tests/forms/`, which is never committed.

## If something goes wrong

- **A new column is not there.** Add it to `api/db/schema.sql` with `ADD COLUMN IF NOT EXISTS` and to
  `prisma/schema.prisma`, then `npm run db:setup`.
- **Python cannot import a module.** `st_shim` must be imported before the app's modules (it stands in for
  Streamlit, which the modules were first written for).
