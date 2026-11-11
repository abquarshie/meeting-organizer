"use client";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { removeEventWeek, removeTemplate, saveMeetingDay, savePrinting, saveRotation } from "@/actions/settings";
import { Icon } from "@/components/icons";
import { MarkEventWeek, type EventWords } from "@/components/MarkEventWeek";
import { download, pyUpload } from "@/components/py";
import { Note } from "@/components/ui";
import { useAct } from "@/components/useAct";
import { WEEKDAYS } from "@/lib/constants";
import { dayLabel, languageLabel } from "@/lib/labels";
import { toCSV } from "@/lib/text";

const FORMS = {
  s89: { accept: "application/pdf,.pdf" },
  s140: { accept: ".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document" },
} as const;

function TemplateRow({ kind, language, fileName }: { kind: "s89" | "s140"; language: string; fileName?: string }) {
  const t = useTranslations();
  const router = useRouter();
  const [busy, act] = useAct();
  const [file, setFile] = useState<File | null>(null);
  const [round, setRound] = useState(0);
  const lang = languageLabel(t, language);
  return (
    <div className="grid gap-2 rounded-xl border border-line p-3">
      <div className="flex items-center gap-3">
        <span className="flex-1 text-sm">{lang}: {fileName ? <b>{fileName}</b> : <span className="text-muted">{t(`admin.${kind}_none`)}</span>}</span>
        {fileName ? (
          <button type="button" className="btn small danger" disabled={busy} onClick={() => act(() => removeTemplate(`${kind}_${language}`))}>{t("common.remove")}</button>
        ) : null}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <input key={round} type="file" accept={FORMS[kind].accept} aria-label={`${t(`admin.${kind}_label`)} (${lang})`} className="input min-w-0 flex-1"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        <button type="button" className="btn" disabled={busy || !file}
          onClick={() => file && act(() => pyUpload("template_upload", file, { kind, lang: language }), () => { setFile(null); setRound(round + 1); router.refresh(); })}>
          <Icon name="upload" /> {t("common.upload")}
        </button>
      </div>
    </div>
  );
}

export function Templates({ languages, stored }: { languages: string[]; stored: Record<string, string> }) {
  const t = useTranslations("admin");
  return (
    <>
      {(["s89", "s140"] as const).map((kind) => (
        <div key={kind} className="card grid gap-3">
          <h2 className="section-title mb-0">{t(`${kind}_title`)}</h2>
          <div className="caption mt-0">{t(`${kind}_hint`)}</div>
          {languages.map((l) => <TemplateRow key={l} kind={kind} language={l} fileName={stored[`${kind}_${l}`] || (`${kind}_${l}` in stored ? t("uploaded_file") : undefined)} />)}
        </div>
      ))}
    </>
  );
}

export function Backup() {
  const t = useTranslations("admin");
  const router = useRouter();
  const [busy, act] = useAct();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<{ ok: boolean; text: string } | null>(null);
  const [sure, setSure] = useState(false);
  const [round, setRound] = useState(0);
  const choose = async (f: File | null) => {
    setFile(f); setSure(false); setPreview(null);
    if (!f) return;
    try {
      const data = JSON.parse(await f.text());
      if (!data || typeof data !== "object" || Array.isArray(data)) throw new Error(t("not_backup"));
      setPreview({ ok: true, text: t("backup_summary", { date: data._created ?? t("unknown_date"), people: (data.students ?? []).length, rows: (data.schedules ?? []).length }) });
    } catch (e) {
      setPreview({ ok: false, text: t("cant_restore", { reason: (e as Error).message }) });
    }
  };
  return (
    <div className="card grid gap-3">
      <h2 className="section-title mb-0">{t("backup_file")}</h2>
      <button type="button" className="btn primary w-fit" disabled={busy} onClick={() => act(() => download("backup", {}), () => router.refresh())}>
        <Icon name="download" /> {t("download_backup")}
      </button>
      <div className="caption mt-0">{t("backup_hint")}</div>
      <label className="field"><span>{t("restore")}</span>
        <input key={round} type="file" accept=".json,application/json" className="input" onChange={(e) => void choose(e.target.files?.[0] ?? null)} />
      </label>
      {preview ? <Note tone={preview.ok ? undefined : "error"}>{preview.text}</Note> : null}
      {preview?.ok && file ? (
        <>
          <label className="check"><input type="checkbox" checked={sure} onChange={(e) => setSure(e.target.checked)} /> {t("restore_sure")}</label>
          <button type="button" className="btn danger w-fit" disabled={busy || !sure}
            onClick={() => act(() => pyUpload("restore", file), () => { setFile(null); setPreview(null); setSure(false); setRound(round + 1); router.refresh(); })}>
            {t("restore_btn")}
          </button>
        </>
      ) : null}
    </div>
  );
}

export function Settings({ congregation, ownerName, useAux, convert, midweek, gap, events, words, locale }: {
  congregation: string; ownerName: string; useAux: boolean; convert: boolean; midweek: string; gap: number;
  events: { id: number; text: string }[]; words: EventWords; locale: string;
}) {
  const t = useTranslations();
  const router = useRouter();
  const [busy, act] = useAct();
  const [p, setP] = useState({ congregation, ownerName, useAux, convert });
  const [day, setDay] = useState(midweek);
  const [rest, setRest] = useState(gap);
  return (
    <>
      <form className="card form" onSubmit={(e) => { e.preventDefault(); act(() => savePrinting(p), () => router.refresh()); }}>
        <h2 className="section-title mb-0">{t("admin.printing")}</h2>
        <label className="field"><span>{t("admin.congregation")}</span>
          <input className="input" value={p.congregation} onChange={(e) => setP({ ...p, congregation: e.target.value })} />
          <span className="msg hint">{t("admin.congregation_hint")}</span>
        </label>
        <label className="field"><span>{t("admin.your_name")}</span>
          <input className="input" value={p.ownerName} onChange={(e) => setP({ ...p, ownerName: e.target.value })} />
          <span className="msg hint">{t("admin.your_name_hint")}</span>
        </label>
        <label className="check"><input type="checkbox" checked={p.useAux} onChange={(e) => setP({ ...p, useAux: e.target.checked })} />
          {t("admin.aux_default")}</label>
        <label className="check"><input type="checkbox" checked={p.convert} onChange={(e) => setP({ ...p, convert: e.target.checked })} />
          {t("admin.convert")}</label>
        <button className="btn w-fit" disabled={busy}>{t("admin.save_printing")}</button>
      </form>
      <form className="card form" onSubmit={(e) => { e.preventDefault(); act(() => saveMeetingDay(day)); }}>
        <h2 className="section-title mb-0">{t("admin.days")}</h2>
        <div className="caption mt-0">{t("admin.days_hint")}</div>
        <label className="field max-w-sm"><span>{t("admin.midweek_day")}</span>
          <select className="input" value={day} onChange={(e) => setDay(e.target.value)}>
            {WEEKDAYS.map((d) => <option key={d} value={d}>{dayLabel(t, d)}</option>)}
          </select>
        </label>
        <button className="btn w-fit" disabled={busy}>{t("admin.save_days")}</button>
      </form>
      <form className="card form" onSubmit={(e) => { e.preventDefault(); act(() => saveRotation(rest)); }}>
        <h2 className="section-title mb-0">{t("admin.rotation")}</h2>
        <label className="field max-w-sm"><span>{t("admin.rotation_days")}</span>
          <input type="number" className="input" min={1} max={90} value={rest} onChange={(e) => setRest(Number(e.target.value))} />
        </label>
        <div className="caption mt-0">{t("admin.rotation_hint")}</div>
        <button className="btn w-fit" disabled={busy}>{t("admin.save_rotation")}</button>
      </form>
      <div className="card grid gap-3">
        <h2 className="section-title mb-0">{t("admin.events")}</h2>
        <div className="caption mt-0">{t("admin.events_hint")}</div>
        {events.length ? events.map((e) => (
          <div key={e.id} className="flex items-center gap-3 text-sm">
            <span className="flex-1">{e.text}</span>
            <button type="button" className="btn small" disabled={busy} onClick={() => act(() => removeEventWeek(e.id))}>{t("common.remove")}</button>
          </div>
        )) : <div className="empty">{t("admin.events_none")}</div>}
        <MarkEventWeek words={words} locale={locale} />
      </div>
    </>
  );
}

export function ChangeLog({ log }: { log: { id: number; ts: string; action: string; details: string }[] }) {
  const t = useTranslations("admin");
  if (!log.length) return <Note>{t("log_empty")}</Note>;
  const head = [t("col_when"), t("col_what"), t("col_details")];
  return (
    <div className="card grid gap-3">
      <div className="table-wrap max-h-[65vh] overflow-y-auto">
        <table className="table">
          <thead><tr>{head.map((h) => <th key={h}>{h}</th>)}</tr></thead>
          <tbody>{log.map((l) => (
            <tr key={l.id}><td className="whitespace-nowrap">{l.ts}</td><td>{l.action}</td><td className="break-words">{l.details}</td></tr>
          ))}</tbody>
        </table>
      </div>
      <button type="button" className="btn w-fit" onClick={() => {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(new Blob([toCSV(head, log.map((l) => [l.ts, l.action, l.details]))], { type: "text/csv;charset=utf-8" }));
        a.download = "change_log.csv";
        a.click();
        setTimeout(() => URL.revokeObjectURL(a.href), 10_000);
      }}><Icon name="download" /> {t("download_log")}</button>
    </div>
  );
}
