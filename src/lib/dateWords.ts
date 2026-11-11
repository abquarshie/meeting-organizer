import type { DateWords } from "./dates";

type T = (key: string, values?: Record<string, string | number>) => string;
const MONTH_KEYS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"];
const DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];

/** The date words in the app language, from a translator for the whole message tree (useTranslations() or
 *  getTranslations()). A short list left empty in Dangme falls back to the first three letters of the full name. */
export function dateWords(t: T): DateWords {
  const months = MONTH_KEYS.map((k) => t(`mname.${k}`));
  const days = DAY_KEYS.map((k) => t(`day.${k}`));
  const split = (s: string, n: number) => { const p = s.trim().split(/\s+/).filter(Boolean); return p.length === n ? p : null; };
  return {
    months, days,
    shortMonths: split(t("mname.short"), 12) ?? months.map((m) => m.slice(0, 3)),
    shortDays: split(t("day.short"), 7) ?? days.map((d) => d.slice(0, 3)),
    today: t("date.today"), tomorrow: t("date.tomorrow"), inDays: (count) => t("date.in_days", { count }),
    thisWeek: t("date.this_week"), lastWeek: t("date.last_week"), nextWeek: t("date.next_week"),
    weeksAgo: (count) => t("date.weeks_ago", { count }), inWeeks: (count) => t("date.in_weeks", { count }),
    weekOf: (n, month, dates) => t("date.week_of", { n, month, dates }), noDates: t("wb.no_dates"),
  };
}
