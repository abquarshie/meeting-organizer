# Meeting Organizer
> Plan the midweek meeting, print the S-89 slips and the S-140, and send reminders, in English or Dangme.

> Wording not translated yet is shown in English. To translate it, see [docs/translating.md](docs/translating.md).

[English](README.md)

## Before you start

Meeting Organizer is a single-user web app for whoever schedules the midweek meeting. It runs on Vercel with its own
Neon Postgres database. It has everything the Meeting Scheduler had for the midweek meeting:

- **Create or edit** a week from the workbook, with **Suggest** filling each part by rotation, and checks for rest
  periods, families, away dates and double bookings.
- **Month overview** with open parts, and several weeks created at once.
- **Slips and printing**: slips on the official S-89, the schedule sheet, the S-140 in Word, a CSV, and WhatsApp
  cards and messages for the week or for one person's month.
- **Reminders** with WhatsApp messages and calendar links, **Participants**, **Reports**, the **Workbook PDF**
  reader, assemblies and conventions, undo, backups and a change log.

Every screen can be in **English or Dangme** (the **App language**), and everything printed or sent can be in
**English or Dangme** (the **Slip language**), chosen separately.

## Steps

1. Follow [docs/setup.en.md](docs/setup.ada.md) to make a new Neon database, deploy to Vercel and sign in.
2. To change or add Dangme wording, see [docs/translating.md](docs/translating.md).
3. To change the code, see [docs/architecture.md](docs/architecture.md).

## Check it worked

`npm run check:messages`, `npm run typecheck`, `npm run build` and `python3 -m pytest tests` all pass. GitHub runs
them on every push (`.github/workflows/check.yml`).

## If something goes wrong

See the last section of [docs/setup.en.md](docs/setup.ada.md).
