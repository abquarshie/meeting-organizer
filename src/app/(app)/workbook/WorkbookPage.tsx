"use client";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { Confirm } from "@/components/Sheet";
import { Icon } from "@/components/icons";
import { py, pyUpload } from "@/components/py";
import { Note } from "@/components/ui";
import { useAct } from "@/components/useAct";
import { ROLES } from "@/lib/constants";
import type { WorkbookPart, WorkbookWeek } from "@/lib/data";
import { dateWords } from "@/lib/dateWords";
import { today, weekDatesText } from "@/lib/dates";
import { roleLabel, sectionLabel } from "@/lib/labels";

const SECTIONS = ["Treasures", "Ministry", "Living"];

type Upload = {
  message: string; dropped: string[]; empty: string[]; broken: { week: string; title: string }[];
  guessed: { week: string; no: number; title: string }[]; notEnglish: boolean;
};

export function WorkbookPage({ weeks, file, skipPast: savedSkip, datesSure }: {
  weeks: WorkbookWeek[]; file: string; skipPast: boolean; datesSure: boolean;
}) {
  const t = useTranslations("wb");
  const c = useTranslations("common");
  const router = useRouter();
  const [busy, act] = useAct();
  const [skipPast, setSkipPast] = useState(savedSkip);
  const [pdf, setPdf] = useState<File | null>(null);
  const [report, setReport] = useState<Upload | null>(null);
  const [removing, setRemoving] = useState(false);
  const done = () => router.refresh();

  const upload = () => pdf && act(async () => {
    const r = await pyUpload<Upload>("workbook_upload", pdf, { skipPast: skipPast ? "1" : "0" });
    if (r.ok) setReport(r);
    return r;
  }, () => { setPdf(null); done(); });

  return (
    <div className="stack">
      <div className="card grid gap-3">
        <div className="text-sm">{t("intro")}</div>
        {weeks.length ? (
          <div className="note flex flex-wrap items-center gap-3">
            <span className="flex-1">{t.rich("in_use", { file: file || t("uploaded"), count: weeks.length, b: (x) => <b>{x}</b> })}</span>
            <button type="button" className="btn small danger" onClick={() => setRemoving(true)}><Icon name="trash" /> {c("remove")}</button>
          </div>
        ) : null}
        <label className="check"><input type="checkbox" checked={skipPast} onChange={(e) => setSkipPast(e.target.checked)} />
          {t("from_current")}</label>
        <span className="msg hint -mt-2">{t("from_current_hint")}</span>
        <input type="file" accept="application/pdf,.pdf" className="input" onChange={(e) => setPdf(e.target.files?.[0] ?? null)} />
        <button type="button" className="btn primary w-fit" disabled={busy || !pdf} onClick={upload}><Icon name="upload" /> {t("read")}</button>
        {report ? <UploadReport r={report} /> : null}
      </div>
      {weeks.length ? (
        <>
          <WeekDates key={`${file}|${weeks[0].start}`} weeks={weeks} skipPast={skipPast} datesSure={datesSure} done={done} />
          <WeeksFound weeks={weeks} />
          <ReviewWeek weeks={weeks} done={done} />
        </>
      ) : null}
      <Confirm open={removing} button={c("remove")} onCancel={() => setRemoving(false)}
        message={t("remove_confirm")}
        onConfirm={() => { setRemoving(false); act(() => py("workbook_remove", {}), done); }} />
    </div>
  );
}

function UploadReport({ r }: { r: Upload }) {
  const t = useTranslations("wb");
  return (
    <div className="grid gap-2">
      {r.dropped.length ? <Note>{t("dropped", { count: r.dropped.length, weeks: r.dropped.join(", ") })}</Note> : null}
      {r.empty.length ? <Note tone="warn">{t("empty", { weeks: r.empty.join(", ") })}</Note> : null}
      {r.broken.length ? (
        <Note tone="error">{t("garbled", { count: r.broken.length, example: JSON.stringify(r.broken[0].title.slice(0, 60)) })}</Note>
      ) : null}
      {r.guessed.length ? (
        <Note tone="warn">{t("guessed_roles", { count: r.guessed.length, parts: r.guessed.slice(0, 4).map((g) => `${g.week} ${t("col_no")} ${g.no}`).join(", ") + (r.guessed.length > 4 ? "…" : "") })}</Note>
      ) : null}
      {r.notEnglish ? <Note>{t("not_english")}</Note> : null}
    </div>
  );
}

function WeekDates({ weeks, skipPast, datesSure, done }: { weeks: WorkbookWeek[]; skipPast: boolean; datesSure: boolean; done: () => void }) {
  const t = useTranslations("wb");
  const [busy, act] = useAct();
  const [first, setFirst] = useState(weeks[0].start ?? today());
  return (
    <div className="card grid gap-3">
      <h2 className="section-title mb-0">{t("dates")}</h2>
      {!datesSure ? <Note tone="warn">{t("dates_guessed")}</Note> : null}
      <div className="flex flex-wrap items-end gap-2">
        <label className="field"><span>{t("first_week", { week: weeks[0].label })}</span>
          <input type="date" className="input" value={first} onChange={(e) => setFirst(e.target.value)} />
          <span className="msg hint">{t("first_week_hint")}</span>
        </label>
        <button type="button" className="btn mb-6" disabled={busy || !first} onClick={() => act(() => py("workbook_dates", { first, skipPast }), done)}>{t("apply_dates")}</button>
      </div>
    </div>
  );
}

function WeeksFound({ weeks }: { weeks: WorkbookWeek[] }) {
  const t = useTranslations();
  const W = dateWords(t);
  const unnamed = weeks.map((w) => w.label).filter((l) => /^Week \d+( \(\d+\))?$/.test(l));
  return (
    <div className="card grid gap-3">
      <h2 className="section-title mb-0">{t("wb.found_title")}</h2>
      <div className="table-wrap">
        <table className="table">
          <thead><tr><th>{t("wb.col_week")}</th><th>{t("wb.col_reading")}</th><th>{t("wb.col_dates")}</th><th className="r">{t("wb.col_parts")}</th><th>{t("wb.col_numbers")}</th><th>{t("wb.col_missing")}</th></tr></thead>
          <tbody>{weeks.map((w) => (
            <tr key={w.label}>
              <td className="whitespace-nowrap">{w.label}</td><td>{w.book ?? ""}</td><td className="whitespace-nowrap">{weekDatesText(w.start, w.end, W)}</td>
              <td className="r num">{w.parts.length}</td><td>{w.parts.map((p) => p.part_no).join(", ")}</td>
              <td className={w.gaps?.length ? "font-semibold text-warn" : ""}>{w.gaps?.join(", ") || "—"}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
      {unnamed.length ? (
        <Note tone="warn">{t("wb.unnamed", { weeks: unnamed.join(", ") })}</Note>
      ) : null}
      {weeks.some((w) => w.gaps?.length) ? <Note tone="warn">{t("wb.missing_numbers")}</Note> : null}
    </div>
  );
}

type EditRow = { part_no: string; title: string; minutes: string; section: string; role: string };
const toRow = (p: WorkbookPart): EditRow => ({
  part_no: p.part_no ? String(p.part_no) : "", title: p.title, minutes: p.minutes ? String(p.minutes) : "", section: p.section, role: p.role,
});

function ReviewWeek({ weeks, done }: { weeks: WorkbookWeek[]; done: () => void }) {
  const t = useTranslations();
  const [busy, act] = useAct();
  const [label, setLabel] = useState(weeks[0].label);
  const week = weeks.find((w) => w.label === label) ?? weeks[0];
  const [heading, setHeading] = useState(week.label);
  const [rows, setRows] = useState<EditRow[]>(week.parts.map(toRow));
  useEffect(() => { setHeading(week.label); setRows(week.parts.map(toRow)); }, [week]);
  const set = (i: number, patch: Partial<EditRow>) => setRows(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  const newHeading = heading.trim().normalize("NFC");
  return (
    <div className="card grid gap-3">
      <h2 className="section-title mb-0">{t("wb.review")}</h2>
      <label className="field"><span>{t("wb.week")}</span>
        <select className="input" value={week.label} onChange={(e) => setLabel(e.target.value)}>
          {weeks.map((w) => <option key={w.label}>{w.label}</option>)}
        </select>
      </label>
      <div className="flex flex-wrap items-end gap-2">
        <label className="field min-w-56 flex-1"><span>{t("wb.heading")}</span>
          <input className="input" value={heading} onChange={(e) => setHeading(e.target.value)} />
          <span className="msg hint">{t("wb.heading_hint")}</span>
        </label>
        <button type="button" className="btn mb-6" disabled={busy || !newHeading || newHeading === week.label}
          onClick={() => act(() => py("workbook_rename", { week: week.label, label: newHeading }), () => { setLabel(newHeading); done(); })}>{t("wb.rename")}</button>
      </div>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div className="grid content-start gap-2">
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th className="w-16">{t("wb.col_no")}</th><th>{t("wb.col_title")}</th><th className="w-16">{t("wb.col_min")}</th><th>{t("wb.col_section")}</th><th>{t("wb.col_role")}</th><th className="w-10" /></tr></thead>
              <tbody>{rows.map((r, i) => (
                <tr key={i}>
                  <td><input className="input cell-input" inputMode="numeric" aria-label={t("wb.col_no")} value={r.part_no} onChange={(e) => set(i, { part_no: e.target.value })} /></td>
                  <td><input className="input cell-input min-w-48" aria-label={t("wb.col_title")} value={r.title} onChange={(e) => set(i, { title: e.target.value })} /></td>
                  <td><input className="input cell-input" inputMode="numeric" aria-label={t("wb.minutes")} value={r.minutes} onChange={(e) => set(i, { minutes: e.target.value })} /></td>
                  <td><select className="input cell-input" aria-label={t("wb.col_section")} value={r.section} onChange={(e) => set(i, { section: e.target.value })}>
                    <option value="">—</option>{SECTIONS.map((s) => <option key={s} value={s}>{sectionLabel(t, s)}</option>)}</select></td>
                  <td><select className="input cell-input" aria-label={t("wb.col_role")} value={r.role} onChange={(e) => set(i, { role: e.target.value })}>
                    <option value="">—</option>{ROLES.map((s) => <option key={s} value={s}>{roleLabel(t, s)}</option>)}</select></td>
                  <td><button type="button" className="btn ghost small" aria-label={t("wb.remove_part")} onClick={() => setRows(rows.filter((_, j) => j !== i))}><Icon name="close" /></button></td>
                </tr>
              ))}</tbody>
            </table>
          </div>
          <div className="btns">
            <button type="button" className="btn" onClick={() => setRows([...rows, { part_no: "", title: "", minutes: "", section: "", role: "" }])}><Icon name="add" /> {t("wb.add_part")}</button>
            <button type="button" className="btn primary" disabled={busy} onClick={() => act(() => py("workbook_week", { week: week.label, parts: rows }), done)}>
              <Icon name="save" /> {t("wb.save_week")}
            </button>
          </div>
          <div className="caption mt-0">{t("wb.rows_left_out")}</div>
        </div>
        <label className="field"><span>{t("wb.text")}</span>
          <textarea className="input min-h-[420px] font-mono text-xs" readOnly value={week.text ?? ""} />
        </label>
      </div>
    </div>
  );
}
