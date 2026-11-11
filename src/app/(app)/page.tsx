import Link from "next/link";
import { getTranslations } from "next-intl/server";
import { Icon } from "@/components/icons";
import { Bar, Stat } from "@/components/ui";
import { BACKUP_REMINDER_DAYS, LANGUAGES, MIDWEEK, SECTION_COLORS } from "@/lib/constants";
import {
  awayBetween, fillCounts, getEvents, getMetas, getPeople, getRows, getSettings, getWorkbook, isSuspended, key,
  meetingRows, savedMeetings, setting, templateNames, workbookStatus,
} from "@/lib/data";
import { dateWords } from "@/lib/dateWords";
import { addDays, dayAndMonth, daysAway, daysBetween, longDate, today } from "@/lib/dates";
import { prisma } from "@/lib/db";
import { sectionLabel } from "@/lib/labels";
import { remindersFrom } from "@/lib/reminders";

const editHref = (date: string, type: string) =>
  `/schedule?${new URLSearchParams({ date, type, mode: "edit" }).toString()}`;
const createHref = (date: string) => `/schedule?${new URLSearchParams({ date, type: MIDWEEK }).toString()}`;

export default async function Home() {
  const t = await getTranslations();
  const W = dateWords(t);
  const now = today();
  // only this week onwards: everything below is about what is coming up
  const [people, rows, metas, settings, workbook, events, templates, anySaved] = await Promise.all([
    getPeople(), getRows({ from: addDays(now, -7) }), getMetas(), getSettings(), getWorkbook(), getEvents(),
    templateNames(), prisma.schedules.findFirst({ select: { id: true } }),
  ]);

  const hour = new Date().getUTCHours(); // Ghana is on UTC
  const word = t(hour < 12 ? "home.good_morning" : hour < 17 ? "home.good_afternoon" : "home.good_evening");
  const owner = setting(settings, "owner_name");

  // what a new installation still needs before it can print
  const gaps: [string, string][] = [];
  if (!people.length) gaps.push([t("home.todo_people"), "/participants"]);
  if (!setting(settings, "congregation")) gaps.push([t("home.todo_congregation"), "/admin?tab=settings"]);
  if (!workbook.weeks.length) gaps.push([t("home.todo_workbook"), "/workbook"]);
  if (!LANGUAGES.some((l) => templates.has(`s89_${l}`))) gaps.push([t("home.todo_s89"), "/admin"]);
  if (!LANGUAGES.some((l) => templates.has(`s140_${l}`))) gaps.push([t("home.todo_s140"), "/admin"]);

  const upcoming = savedMeetings(rows).filter((m) => m.date >= now).sort((a, b) => a.date.localeCompare(b.date));
  const toCreate = workbookStatus(workbook.weeks, rows, settings, events)
    .filter((w) => w.status === "to create" && w.meeting >= now).sort((a, b) => a.meeting.localeCompare(b.meeting));
  const gap = toCreate[0];

  const soon = upcoming.filter((m) => m.date <= addDays(now, 28));
  const openSoon = soon.reduce((n, m) => { const c = fillCounts(meetingRows(rows, m.date, m.type)); return n + c.needed - c.filled; }, 0);
  const notCreated = toCreate.filter((w) => w.meeting <= addDays(now, 28));
  const away = await awayBetween(now, addDays(now, 6));
  for (const p of people) if (isSuspended(p, now)) away.add(p.id);
  const lastExport = setting(settings, "last_export");
  const backupDays = lastExport ? daysBetween(lastExport, now) : null;

  const next = upcoming[0];
  // everything that wants a hand, newest worry first: a week not created, the backup, reminders, setup gaps
  const attention: { text: string; href: string; tone: "warn" | "bad" | "accent"; icon: "warning" | "calendar" | "shield" | "add" | "clock" }[] = [];
  if (next && gap) attention.push({ text: t("home.todo_week", { date: longDate(gap.meeting, W), week: gap.label }), href: createHref(gap.meeting), tone: "warn", icon: "calendar" });
  if (anySaved && (backupDays === null || backupDays >= BACKUP_REMINDER_DAYS)) {
    attention.push({ text: backupDays === null ? t("home.todo_no_backup") : t("home.todo_old_backup", { days: backupDays }), href: "/admin", tone: "bad", icon: "shield" });
  }
  // the people with a part in the next seven days, for the WhatsApp reminders
  const remindRows = rows.filter((r) => r.meeting_date >= now && r.meeting_date <= addDays(now, 6));
  const toRemind = remindersFrom(remindRows, { themed: {}, aPart: "" }).length;
  if (toRemind) attention.push({ text: t("home.todo_remind", { count: toRemind, people: t(toRemind === 1 ? "home.person" : "home.people") }), href: "/reminders", tone: "accent", icon: "clock" });
  for (const [what, href] of gaps) attention.push({ text: what, href, tone: "accent", icon: "add" });
  const iconTone = { warn: "bg-warn-soft text-warn", bad: "bg-bad-soft text-bad", accent: "bg-brand-soft text-brand-ink" };

  return (
    <>
      <div className="page-head">
        <div className="eyebrow">{longDate(now, W)} {now.slice(0, 4)}</div>
        <h1 className="page-title mt-1">{owner ? `${word}, ${owner}` : word}</h1>
      </div>
      <div className="stack">
        {!people.length ? (
          <div className="hero">
            <div className="text-sm text-white/70">{t("home.getting_started")}</div>
            <h2 className="mt-1 mb-2 text-2xl font-semibold tracking-tight">{t("home.no_people_title")}</h2>
            <p className="mt-0 mb-5 max-w-lg text-sm text-white/75">{t("home.no_people_body")}</p>
            <Link className="btn primary" href="/participants"><Icon name="add" /> {t("home.add_people")}</Link>
          </div>
        ) : next ? (() => {
          const mrows = meetingRows(rows, next.date, next.type);
          const meta = metas.get(key(next.date, next.type));
          const { filled, needed } = fillCounts(mrows);
          const open = needed - filled;
          const detail = meta?.heading;
          return (
            <div className="hero">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-sm text-white/70">{t("home.next_meeting")}</div>
                  <h2 className="mt-1 mb-0 text-2xl font-semibold tracking-tight md:text-3xl">{longDate(next.date, W)}</h2>
                  <div className="mt-1 text-sm text-white/70">{daysAway(next.date, W)}{detail ? ` · ${detail}` : ""}</div>
                </div>
                <span className={`pill ${open ? "bg-white/15! text-white!" : "bg-emerald-400/20! text-emerald-100!"}`}>
                  <Icon name={open ? "clock" : "check"} />{open ? t(open === 1 ? "home.slots_open_one" : "home.slots_open_many", { count: open }) : t("home.all_filled")}
                </span>
              </div>
              <div className="mt-6 grid gap-6 md:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)] md:items-end">
                <div className="grid gap-3">
                  {["Treasures", "Ministry", "Living"].map((section) => {
                    const part = mrows.filter((r) => r.section === section);
                    if (!part.length) return null;
                    const c = fillCounts(part);
                    return (
                      <div key={section} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1.5 text-sm sm:grid-cols-[minmax(0,15rem)_minmax(0,1fr)_2.75rem]">
                        <span className="truncate text-white/85">{sectionLabel(t, section)}</span>
                        <div className="hero-bar max-sm:order-last max-sm:col-span-2"><div style={{ width: `${c.needed ? (100 * c.filled) / c.needed : 0}%`, background: SECTION_COLORS[section] }} /></div>
                        <span className="num text-xs text-white/70">{c.filled}/{c.needed}</span>
                      </div>
                    );
                  })}
                </div>
                <div className="btns md:justify-end">
                  <Link className="btn primary" href={editHref(next.date, next.type)}><Icon name="edit" /> {open ? t("home.fill_open") : t("home.edit_schedule")}</Link>
                  <Link className="btn" href={`/print?meeting=${encodeURIComponent(key(next.date, next.type))}`}><Icon name="print" /> {t("home.print_slips")}</Link>
                </div>
              </div>
            </div>
          );
        })() : (
          <div className="hero">
            <div className="text-sm text-white/70">{gap ? t("home.next_workbook_week") : t("home.no_meetings")}</div>
            <h2 className="mt-1 mb-1 text-2xl font-semibold tracking-tight md:text-3xl">{gap ? longDate(gap.meeting, W) : t("home.first_schedule")}</h2>
            <p className="mt-0 mb-5 text-sm text-white/75">{gap ? t("home.week_no_schedule", { week: gap.label }) : t("home.upload_first")}</p>
            <div className="btns">
              <Link className="btn primary" href={gap ? createHref(gap.meeting) : "/schedule"}><Icon name="add" /> {gap ? t("home.create_week") : t("home.create_schedule")}</Link>
              {gap ? null : <Link className="btn" href="/workbook"><Icon name="upload" /> {t("home.upload_workbook")}</Link>}
            </div>
          </div>
        )}

        {people.length ? (
          <div className="grid grid-cols-3 gap-2.5 md:gap-4">
            {!soon.length && notCreated.length
              ? <Stat label={t("home.stat_not_created")} value={notCreated.length} icon="calendar" tone="warn" sub={t("home.stat_not_created_sub")} />
              : <Stat label={t("home.stat_open")} value={openSoon} icon="clock" tone={openSoon ? "warn" : "ok"}
                  sub={soon.length && notCreated.length ? t("home.stat_open_sub_weeks", { count: notCreated.length }) : t("home.stat_open_sub")} />}
            <Stat label={t("home.stat_active")} value={people.filter((p) => p.active).length} icon="people" sub={t("home.stat_active_sub", { count: people.length })} />
            <Stat label={t("home.stat_away")} value={away.size} icon="away" sub={t("home.stat_away_sub")} />
          </div>
        ) : null}

        <div className={`grid gap-4 md:gap-5 ${attention.length && upcoming.length > 1 ? "lg:grid-cols-[minmax(0,1fr)_minmax(0,1.25fr)]" : ""}`}>
          {attention.length ? (
            <div className="card">
              <div className="card-head"><h2>{t("home.attention")}</h2><span className="pill warn">{attention.length}</span></div>
              <div className="rows">
                {attention.map((a) => (
                  <Link key={a.text} href={a.href} className="row-link">
                    <span className={`row-icon ${iconTone[a.tone]}`}><Icon name={a.icon} /></span>
                    <span className="min-w-0 text-sm">{a.text}</span>
                    <span className="chev"><Icon name="chevron" /></span>
                  </Link>
                ))}
              </div>
            </div>
          ) : null}

          {upcoming.length > 1 ? (
            <div className="card">
              <div className="card-head"><h2>{t("home.coming_up")}</h2><Link className="text-sm font-medium no-underline" href="/month">{t("nav.month")}</Link></div>
              <div className="rows">
                {upcoming.slice(1, 9).map((m) => {
                  const meta = metas.get(key(m.date, m.type));
                  const c = fillCounts(meetingRows(rows, m.date, m.type));
                  const pct = c.needed ? Math.round((100 * c.filled) / c.needed) : 100;
                  const open = c.needed - c.filled;
                  const [day, mon] = dayAndMonth(m.date, W);
                  return (
                    <Link key={key(m.date, m.type)} href={editHref(m.date, m.type)} className="row-link">
                      <span className="datebox"><b>{day}</b><span>{mon}</span></span>
                      <span className="grid min-w-0 flex-1 gap-1.5">
                        <span className="flex min-w-0 items-center gap-2 text-sm">
                          <span className="min-w-0 truncate font-semibold" title={meta?.heading || undefined}>{meta?.heading || longDate(m.date, W)}</span>
                        </span>
                        <Bar pct={pct} label={t("common.filled")} />
                      </span>
                      <span className={`pill flex-none ${open ? "warn" : "ok"}`}>{open ? t("home.open_count", { count: open }) : t("common.filled")}</span>
                      <span className="chev"><Icon name="chevron" /></span>
                    </Link>
                  );
                })}
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </>
  );
}
