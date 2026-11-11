import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { Note, PageHead } from "@/components/ui";
import { MIDWEEK } from "@/lib/constants";
import { eventWeeks, getEvents, getMetas, getPeople, getRows, getSettings, key, meetingRows, savedMeetings, slipLanguage, templateNames } from "@/lib/data";
import { dateWords } from "@/lib/dateWords";
import { fmtDate, monthLabel, relativeWeek, today, weekLabel, weekStart } from "@/lib/dates";
import { hallLabel } from "@/lib/labels";
import { Printing } from "./Printing";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("print"))("title") };
}

export default async function PrintPage({ searchParams }: { searchParams: Promise<{ meeting?: string; month?: string }> }) {
  const [sp, allRows, metas, people, settings, templates, events, t] = await Promise.all([
    searchParams, getRows(), getMetas(), getPeople(), getSettings(), templateNames(), getEvents(), getTranslations(),
  ]);
  const W = dateWords(t);
  const rows = allRows.filter((r) => r.meeting_type === MIDWEEK);
  const meetings = savedMeetings(rows);
  if (!meetings.length) {
    return <><PageHead title={t("print.title")} /><Note>{t("print.none_yet")}</Note></>;
  }
  const partLabel = (r: { part_name: string | null; part_no: number | null; minutes: number | null; hall: string }) => {
    let label = r.part_name ?? "";
    if (r.minutes && !label.toLowerCase().includes("min")) label += ` ${t("part.minutes", { count: r.minutes })}`;
    if (r.part_no) label = `${r.part_no}. ${label}`;
    if (r.hall !== "main_hall") label += ` · ${hallLabel(t, r.hall)}`;
    return label;
  };
  const language = slipLanguage(settings);
  const months = [...new Set(meetings.map((m) => m.date.slice(0, 7)))].sort().reverse();
  const scope = sp.month ? "month" : "meeting";
  const now = today();
  const firstAhead = [...meetings].filter((m) => m.date >= now).sort((a, b) => a.date.localeCompare(b.date))[0] ?? meetings[0];
  const meeting = meetings.find((m) => key(m.date, m.type) === sp.meeting) ?? firstAhead;
  const month = scope === "month" && months.includes(sp.month!) ? sp.month! : meeting.date.slice(0, 7);
  const chosen = (scope === "month" ? meetings.filter((m) => m.date.startsWith(month)) : [meeting])
    .sort((a, b) => a.date.localeCompare(b.date));

  const meta = metas.get(key(meeting.date, meeting.type));
  const summary = scope === "meeting" ? {
    heading: meta?.heading ?? "",
    rows: meetingRows(rows, meeting.date, meeting.type).sort((a, b) => a.sort_order - b.sort_order).map((r) => {
      const needAssistant = r.needs_assistant === 1;
      return {
        part: partLabel(r), person: r.person ?? t("common.unassigned"),
        assistant: needAssistant ? r.assistant ?? t("print.needed") : "",
        gap: [!r.person, needAssistant && !r.assistant] as [boolean, boolean],
      };
    }),
  } : null;
  const chosenRows = chosen.flatMap((m) => meetingRows(rows, m.date, m.type));
  const slipCount = chosenRows.filter((r) => r.student_part === 1 && r.person).length;
  const slipAux = chosenRows.filter((r) => r.student_part === 1 && r.person && r.hall !== "main_hall").length;

  // weeks for the weekly card: every week with a meeting, and assembly/convention weeks
  const weeks = [...new Set([...meetings.map((m) => weekStart(m.date)), ...eventWeeks(events).keys()])].sort();
  const thisWeek = weekStart(now);
  const near = [W.thisWeek, W.lastWeek, W.nextWeek];
  const weekOptions = weeks.map((w) => {
    const rel = relativeWeek(w, thisWeek, W);
    return { value: w, label: weekLabel(w, W) + (near.includes(rel) ? ` · ${rel}` : "") };
  });
  const allMonths = months.map((m) => ({ value: m, label: monthLabel(m, W) }));
  // who has something in each month, for the one-person card
  const perMonth = new Map<string, Map<number, number>>();
  for (const r of rows) {
    const m = r.meeting_date.slice(0, 7);
    let counts = perMonth.get(m);
    if (!counts) perMonth.set(m, counts = new Map());
    for (const id of [r.student_id, r.assistant_id]) if (id !== null) counts.set(id, (counts.get(id) ?? 0) + 1);
  }
  const monthPeople: Record<string, { id: number; label: string }[]> = {};
  for (const m of months) {
    const counts = perMonth.get(m) ?? new Map<number, number>();
    monthPeople[m] = people.filter((p) => counts.has(p.id))
      .map((p) => ({ id: p.id, label: t("print.person_count", { name: p.name, count: counts.get(p.id) ?? 0 }) }));
  }

  return (
    <>
      <PageHead title={t("print.title")} sub={t("print.sub")} />
      <Printing
        scope={scope} language={language}
        meetings={meetings.map((m) => ({ value: key(m.date, m.type), label: fmtDate(m.date, W) }))}
        meeting={key(meeting.date, meeting.type)} months={allMonths} month={month}
        chosen={chosen.map((m) => key(m.date, m.type))} chosenText={chosen.map((m) => fmtDate(m.date, W)).join(", ")}
        summary={summary} editHref={`/schedule?${new URLSearchParams({ date: meeting.date, mode: "edit" })}`}
        slipCount={slipCount} slipAux={slipAux} hasS89={templates.has(`s89_${language}`)} hasS140={templates.has(`s140_${language}`)}
        midweekMonths={months}
        weeks={weekOptions} defaultWeek={weeks.find((w) => w >= thisWeek) ?? weeks[weeks.length - 1]}
        monthPeople={monthPeople} />
    </>
  );
}
