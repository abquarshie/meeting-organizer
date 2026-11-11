import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { Note, PageHead } from "@/components/ui";
import { CATEGORIES, MAIN_HALL, ROLES } from "@/lib/constants";
import { getPeople, getRows, suspendedUntil } from "@/lib/data";
import { dateWords } from "@/lib/dateWords";
import { addDays, fmtDate, isISODate, today } from "@/lib/dates";
import { categoryLabel, groupLabel, hallLabel, roleLabel } from "@/lib/labels";
import { CsvButton, Filters, PersonPick } from "./Controls";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("rep");
  return { title: t("title") };
}

const SPANS = ["3", "6", "12", "custom"] as const;

type SP = { span?: string; from?: string; to?: string; future?: string; all?: string; cat?: string; person?: string };

export default async function ReportsPage({ searchParams }: { searchParams: Promise<SP> }) {
  const t = await getTranslations();
  const W = dateWords(t);
  const [sp, people] = await Promise.all([searchParams, getPeople()]);
  const head = <PageHead title={t("rep.title")} sub={t("rep.sub")} />;
  if (!people.length) return <>{head}<Note>{t("people.none")}</Note></>;

  const now = today();
  const span = (SPANS as readonly string[]).includes(sp.span ?? "") ? sp.span! : "6";
  let start: string, end: string;
  if (span === "custom") {
    start = isISODate(sp.from) ? sp.from : addDays(now, -182);
    end = isISODate(sp.to) ? sp.to : now;
  } else {
    start = addDays(now, -Math.round(Number(span) * 30.4));
    end = now;
  }
  const future = sp.future === "1";
  if (future) end = "9999-12-31";
  const activeOnly = sp.all !== "1";
  const cats = sp.cat ? sp.cat.split(",").filter((c) => (CATEGORIES as readonly string[]).includes(c)) : [...CATEGORIES];

  const personId = Number(sp.person) || people[0].id;
  const [period, personRows] = await Promise.all([getRows({ from: start, to: end }), getRows({ person: personId })]);
  const chosen = people.filter((p) => (!activeOnly || p.active) && cats.includes(p.gender));
  const report = chosen.map((p) => {
    const own = period.filter((r) => r.student_id === p.id);
    const assisting = period.filter((r) => r.assistant_id === p.id);
    const dates = [...own, ...assisting].map((r) => r.meeting_date).sort();
    const roles: Record<string, number> = {};
    for (const r of own) if (r.role) roles[r.role] = (roles[r.role] ?? 0) + 1;
    const until = suspendedUntil(p, now);
    return {
      name: p.name, category: categoryLabel(t, p.gender), group: p.groups.map((g) => groupLabel(t, g)).join(", ") || t("people.adult"),
      status: !p.active ? t("people.status_inactive")
        : until === null ? t("people.status_active")
        : until ? t("people.suspended_until", { date: fmtDate(until, W) }) : t("people.status_suspended"),
      parts: own.length, assisting: assisting.length, total: own.length + assisting.length,
      last: dates.length ? fmtDate(dates[dates.length - 1], W) : "", roles,
    };
  }).sort((a, b) => a.total - b.total || a.name.localeCompare(b.name));
  const roleCols = ROLES.filter((r) => report.some((x) => x.roles[r]));
  const none = report.filter((r) => r.total === 0);

  const header = [
    t("rep.col_name"), t("rep.col_category"), t("rep.col_group"), t("rep.col_status"), t("rep.col_parts"),
    t("rep.col_assisting"), t("rep.col_total"), t("rep.col_last"), ...roleCols.map((r) => roleLabel(t, r)),
  ];
  const csvRows = report.map((r) => [r.name, r.category, r.group, r.status, r.parts, r.assisting, r.total, r.last, ...roleCols.map((c) => r.roles[c] ?? 0)]);

  const name = new Map(people.map((p) => [p.id, p.name]));
  const history = personRows // newest first already
    .slice(0, 100)
    .map((r) => {
      const helping = r.assistant_id === personId && r.student_id !== personId;
      const other = helping ? name.get(r.student_id ?? -1) : r.assistant_id ? name.get(r.assistant_id) : undefined;
      const part = r.part_name ?? "";
      return {
        date: r.meeting_date,
        part: other ? `${part} (${t(helping ? "rep.assisting" : "rep.assisted", { name: other })})` : part,
        room: hallLabel(t, r.hall || MAIN_HALL),
      };
    });

  return (
    <>
      {head}
      <div className="stack">
        <Filters span={span} from={start} to={span === "custom" ? end : now} future={future} activeOnly={activeOnly} cats={cats}
          caption={future ? t("rep.range_open", { start: fmtDate(start, W) }) : t("rep.range", { start: fmtDate(start, W), end: fmtDate(end, W) })} />
        {!report.length ? <Note>{t("rep.no_match")}</Note> : (
          <div className="card grid gap-3">
            {none.length ? <Note tone="warn">{t("rep.left_out", { count: none.length, names: none.map((r) => r.name).join(", ") })}</Note> : null}
            <div className="table-wrap max-h-[65vh] overflow-y-auto">
              <table className="table">
                <thead><tr>{header.map((h, i) => <th key={h} className={i >= 4 && i !== 7 ? "r" : ""}>{h}</th>)}</tr></thead>
                <tbody>{report.map((r) => (
                  <tr key={r.name}>
                    <td className="whitespace-nowrap font-medium">{r.name}</td><td>{r.category}</td><td>{r.group}</td><td className="whitespace-nowrap">{r.status}</td>
                    <td className="r num">{r.parts}</td><td className="r num">{r.assisting}</td><td className="r num font-semibold">{r.total}</td>
                    <td className="whitespace-nowrap">{r.last}</td>
                    {roleCols.map((c) => <td key={c} className="r num">{r.roles[c] ?? 0}</td>)}
                  </tr>
                ))}</tbody>
              </table>
            </div>
            <CsvButton header={header} rows={csvRows} name={`assignment_report_${start}_${future ? "9999-12-31" : end}.csv`} />
          </div>
        )}
        <div className="card grid gap-3">
          <h2 className="section-title mb-0">{t("rep.history")}</h2>
          <PersonPick people={people.map((p) => ({ id: p.id, name: p.name }))} value={personId} />
          {!history.length ? <div className="empty">{t("rep.no_history")}</div> : (
            <div className="table-wrap max-h-[60vh] overflow-y-auto">
              <table className="table">
                <thead><tr><th>{t("rep.col_date")}</th><th>{t("rep.col_part")}</th><th>{t("rep.col_room")}</th></tr></thead>
                <tbody>{history.map((h, i) => <tr key={i}><td className="whitespace-nowrap">{fmtDate(h.date, W)}</td><td>{h.part}</td><td>{h.room}</td></tr>)}</tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
