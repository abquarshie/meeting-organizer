import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";
import { MarkEventWeek } from "@/components/MarkEventWeek";
import { Icon } from "@/components/icons";
import { Bar, Note, PageHead, Stat } from "@/components/ui";
import { MAIN_HALL, MIDWEEK } from "@/lib/constants";
import {
  eventFor, fillCounts, getEvents, getMeetingList, getMetas, getRows, getSettings, getWorkbook, key, meetingRows,
  savedMeetings, setting, workbookStatus,
} from "@/lib/data";
import { dateWords } from "@/lib/dateWords";
import { addDays, fmtDate, lastDayOfMonth, monthLabel, today } from "@/lib/dates";
import { eventWords } from "@/lib/docWords";
import { eventWeekLabel } from "@/lib/labels";
import { getAppLocale } from "@/lib/locale";
import { CreateWeeks } from "./CreateWeeks";
import { MonthPick } from "./MonthPick";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("month"))("title") };
}

type Line = { date: string; pct: number | null; open: number | null; aux: string; heading: string; href?: string };

export default async function MonthPage({ searchParams }: { searchParams: Promise<{ m?: string }> }) {
  const [{ m }, saved, metas, settings, workbook, events, t, locale, words] = await Promise.all([
    searchParams, getMeetingList(), getMetas(), getSettings(), getWorkbook(), getEvents(), getTranslations(),
    getAppLocale(), eventWords(),
  ]);
  const W = dateWords(t);
  const thisMonth = today().slice(0, 7);
  const months = new Set([thisMonth, ...saved.map((x) => x.date.slice(0, 7)),
    ...workbook.weeks.filter((w) => w.start).map((w) => w.start!.slice(0, 7))]);
  const list = [...months].sort().reverse();
  const month = m && months.has(m) ? m : thisMonth;
  // the month plus a week either side, for workbook weeks that start in the month before
  const rows = await getRows({ from: addDays(`${month}-01`, -7), to: addDays(lastDayOfMonth(month), 7) });

  const lines: Line[] = [];
  for (const mt of savedMeetings(rows).filter((x) => x.date.startsWith(month))) {
    const r = meetingRows(rows, mt.date, mt.type);
    const meta = metas.get(key(mt.date, mt.type));
    const c = fillCounts(r);
    lines.push({
      date: mt.date, pct: Math.round((100 * c.filled) / Math.max(c.needed, 1)), open: c.needed - c.filled,
      aux: r.some((x) => x.hall !== MAIN_HALL) ? t("common.yes") : "", heading: meta?.heading ?? "",
      href: `/schedule?${new URLSearchParams({ date: mt.date, type: mt.type, mode: "edit" })}`,
    });
  }
  const toCreate: { date: string; label: string }[] = [];
  for (const w of workbookStatus(workbook.weeks, rows, settings, events)) {
    if (!w.meeting.startsWith(month) || w.status === "saved") continue;
    if (w.status === "no meeting") {
      lines.push({ date: w.meeting, pct: null, open: null, aux: "", heading: `${w.label} · ${eventWeekLabel(t, eventFor(events, w.meeting))}` });
      continue;
    }
    toCreate.push({ date: w.meeting, label: w.label });
    lines.push({ date: w.meeting, pct: null, open: null, aux: "", heading: t("month.not_created", { date: w.label }),
      href: `/schedule?${new URLSearchParams({ date: w.meeting, type: MIDWEEK })}` });
  }
  // assemblies and conventions that line up with no workbook week
  const shown = new Set(lines.map((l) => l.date));
  for (const e of events) {
    if (e.start > lastDayOfMonth(month) || e.end < `${month}-01` || shown.has(e.start)) continue;
    const label = eventWeekLabel(t, e.kind);
    lines.push({ date: e.start, pct: null, open: null, aux: "",
      heading: e.start === e.end ? label : t("month.until", { label, date: fmtDate(e.end, W) }) });
  }
  lines.sort((a, b) => a.date.localeCompare(b.date));
  const totalOpen = lines.reduce((n, l) => n + (l.open ?? 0), 0);

  return (
    <>
      <PageHead title={t("month.title")} sub={t("month.sub")}>
        <div className="btns">
          <MonthPick months={list.map((x) => ({ value: x, label: monthLabel(x, W) }))} value={month} label={t("month.pick")} />
          <Link className="btn" href={`/print?month=${month}`}><Icon name="print" /> {t("month.print")}</Link>
        </div>
      </PageHead>
      <div className="stack">
        <div className="grid grid-cols-3 gap-2.5 md:gap-4">
          <Stat label={t("month.stat_meetings")} value={lines.filter((l) => l.pct !== null).length} icon="calendar" sub={monthLabel(month, W)} />
          <Stat label={t("month.stat_open")} value={totalOpen} icon="clock" tone={totalOpen ? "warn" : "ok"} sub={totalOpen ? t("month.stat_open_sub_left") : t("month.stat_open_sub_done")} />
          <Stat label={t("month.stat_not_created")} value={toCreate.length} icon="add" tone={toCreate.length ? "warn" : undefined} sub={t("month.stat_not_created_sub")} />
        </div>
        {lines.length ? (
          <div className="card">
            <div className="table-wrap">
              <table className="table">
                <thead><tr><th>{t("month.col_date")}</th><th>{t("month.col_filled")}</th><th className="r">{t("month.col_open")}</th><th>{t("month.aux_col")}</th><th>{t("month.col_heading")}</th></tr></thead>
                <tbody>
                  {lines.map((l, i) => (
                    <tr key={i}>
                      <td className="whitespace-nowrap">{l.href ? <Link href={l.href}>{fmtDate(l.date, W)}</Link> : fmtDate(l.date, W)}</td>
                      <td className="min-w-28">{l.pct === null ? "" : <div className="flex items-center gap-2"><Bar pct={l.pct} label={t("common.filled")} /><span className="num text-xs text-muted">{l.pct}%</span></div>}</td>
                      <td className="r">{l.open === null ? "" : <span className={`pill ${l.open ? "warn" : "ok"}`}>{l.open ? t("home.open_count", { count: l.open }) : t("common.filled")}</span>}</td>
                      <td>{l.aux}</td>
                      <td>{l.heading}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : <Note>{t("month.nothing")}</Note>}

        {toCreate.length ? (
          <div className="card grid gap-3">
            <h2 className="section-title mb-0">{t("month.weeks_without")}</h2>
            <CreateWeeks weeks={toCreate} auxDefault={setting(settings, "use_aux", "1") === "1"} />
            <details className="rounded-xl border border-line px-3 py-2">
              <summary className="cursor-pointer text-sm font-semibold">{t("month.is_event")}</summary>
              <div className="mt-3"><MarkEventWeek defaultDay={toCreate[0].date} words={words} locale={locale} /></div>
            </details>
          </div>
        ) : null}

      </div>
    </>
  );
}
