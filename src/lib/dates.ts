// Dates are stored as ISO text (YYYY-MM-DD), as the Python side writes them. These helpers work on that text in UTC,
// so a server's time zone never shifts a day. The month and day names come from the message files (DateWords), since
// browsers have no Dangme date names; see lib/dateWords.ts for getting them on the server and in the browser.

export type DateWords = {
  months: string[]; // January … December
  shortMonths: string[]; // Jan … Dec
  days: string[]; // Monday … Sunday
  shortDays: string[]; // Mon … Sun
  today: string; tomorrow: string; inDays: (n: number) => string;
  thisWeek: string; lastWeek: string; nextWeek: string; weeksAgo: (n: number) => string; inWeeks: (n: number) => string;
  weekOf: (n: number, month: string, dates: string) => string; noDates: string;
};

export function isISODate(s: unknown): s is string {
  if (typeof s !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(s)) return false;
  return toISO(parse(s)) === s;
}

export function parse(iso: string): Date {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d));
}

export function toISO(d: Date): string {
  return d.toISOString().slice(0, 10);
}

export function today(): string {
  return toISO(new Date());
}

export function addDays(iso: string, n: number): string {
  const d = parse(iso);
  d.setUTCDate(d.getUTCDate() + n);
  return toISO(d);
}

export function daysBetween(a: string, b: string): number {
  return Math.round((parse(b).getTime() - parse(a).getTime()) / 86_400_000);
}

/** 0 = Monday … 6 = Sunday, as Python's weekday(). */
export function weekday(iso: string): number {
  return (parse(iso).getUTCDay() + 6) % 7;
}

/** The Monday of the meeting week this day falls in. */
export function weekStart(iso: string): string {
  return addDays(iso, -weekday(iso));
}

const short = (d: Date, W: DateWords) => W.shortMonths[d.getUTCMonth()];
const dayName = (d: Date, W: DateWords) => W.days[(d.getUTCDay() + 6) % 7];

/** "21 October 2026", or "21 Oct" when short. */
export function fmtDate(iso: string | null | undefined, W: DateWords, isShort = false): string {
  if (!iso || !isISODate(iso)) return iso ?? "";
  const d = parse(iso);
  return isShort ? `${d.getUTCDate()} ${short(d, W)}` : `${d.getUTCDate()} ${W.months[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
}

/** "Wednesday 21 October". */
export function longDate(iso: string, W: DateWords): string {
  const d = parse(iso);
  return `${dayName(d, W)} ${d.getUTCDate()} ${W.months[d.getUTCMonth()]}`;
}

/** "Wed 21 Oct". */
export function shortDay(iso: string, W: DateWords): string {
  const d = parse(iso);
  return `${W.shortDays[(d.getUTCDay() + 6) % 7]} ${d.getUTCDate()} ${short(d, W)}`;
}

/** The day of the month and the short month, for a date box. */
export function dayAndMonth(iso: string, W: DateWords): [string, string] {
  const d = parse(iso);
  return [String(d.getUTCDate()), short(d, W)];
}

/** "2026-10" -> "October 2026". */
export function monthLabel(ym: string, W: DateWords): string {
  const [y, m] = ym.split("-").map(Number);
  return `${W.months[m - 1]} ${y}`;
}

export function lastDayOfMonth(ym: string): string {
  const [y, m] = ym.split("-").map(Number);
  return toISO(new Date(Date.UTC(y, m, 0)));
}

/** "Week 2 of October (5–11 Oct)", as utils.week_label. */
export function weekLabel(iso: string, W: DateWords): string {
  const mon = weekStart(iso);
  const sun = addDays(mon, 6);
  const m = parse(mon), s = parse(sun);
  const n = Math.floor((m.getUTCDate() - 1) / 7) + 1;
  const span = m.getUTCMonth() === s.getUTCMonth()
    ? `${m.getUTCDate()}–${s.getUTCDate()} ${short(s, W)}`
    : `${m.getUTCDate()} ${short(m, W)} – ${s.getUTCDate()} ${short(s, W)}`;
  return W.weekOf(n, W.months[m.getUTCMonth()], span);
}

/** "this week", "last week", "next week", "3 weeks ago", "in 2 weeks". */
export function relativeWeek(other: string, meeting: string, W: DateWords): string {
  const n = Math.round(daysBetween(weekStart(meeting), weekStart(other)) / 7);
  if (n === 0) return W.thisWeek;
  if (n === -1) return W.lastWeek;
  if (n === 1) return W.nextWeek;
  return n < 0 ? W.weeksAgo(-n) : W.inWeeks(n);
}

/** "in 3 days", "today", "tomorrow". */
export function daysAway(iso: string, W: DateWords): string {
  const n = daysBetween(today(), iso);
  return n === 0 ? W.today : n === 1 ? W.tomorrow : W.inDays(n);
}

/** "14–20 Sep 2026" for a workbook week's dates, as workbook.week_dates_text. */
export function weekDatesText(start: string | undefined, end: string | undefined, W: DateWords): string {
  if (!start || !end) return W.noDates;
  const s = parse(start), e = parse(end);
  return s.getUTCMonth() === e.getUTCMonth()
    ? `${s.getUTCDate()}–${e.getUTCDate()} ${short(e, W)} ${e.getUTCFullYear()}`
    : `${s.getUTCDate()} ${short(s, W)}–${e.getUTCDate()} ${short(e, W)} ${e.getUTCFullYear()}`;
}

/** Collapse consecutive days into ranges: "3–9 Oct, 20 Oct". */
export function awaySummary(dates: string[], W: DateWords): string {
  const days = [...dates].sort();
  const out: string[] = [];
  let start: string | null = null, prev: string | null = null;
  for (const d of [...days, null]) {
    if (start === null) { start = prev = d; continue; }
    if (d !== null && prev !== null && daysBetween(prev, d) === 1) { prev = d; continue; }
    out.push(start === prev ? fmtDate(start, W, true) : `${fmtDate(start, W, true)}–${fmtDate(prev, W, true)}`);
    start = prev = d;
  }
  return out.join(", ");
}
