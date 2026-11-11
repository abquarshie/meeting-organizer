"use client";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Icon } from "@/components/icons";
import { download, pyGet, pyUrl } from "@/components/py";
import { useToast } from "@/components/Toaster";
import { Note } from "@/components/ui";
import { useAct } from "@/components/useAct";
import { dateWords } from "@/lib/dateWords";
import { monthLabel } from "@/lib/dates";
import { languageLabel } from "@/lib/labels";

type Opt = { value: string; label: string };

export function Printing(props: {
  scope: "meeting" | "month"; language: string; meetings: Opt[]; meeting: string; months: Opt[]; month: string;
  chosen: string[]; chosenText: string; editHref: string;
  summary: null | { heading: string; rows: { part: string; person: string; assistant: string; gap: [boolean, boolean] }[] };
  slipCount: number; slipAux: number; hasS89: boolean; hasS140: boolean;
  midweekMonths: string[];
  weeks: Opt[]; defaultWeek: string; monthPeople: Record<string, { id: number; label: string }[]>;
}) {
  const t = useTranslations();
  const router = useRouter();
  const path = usePathname();
  const [tab, setTab] = useState("print");
  const { scope, summary } = props;
  return (
    <div className="stack">
      <div className="card grid gap-3">
        <div className="seg w-fit" role="group" aria-label={t("print.scope")}>
          <button type="button" aria-pressed={scope === "meeting"} onClick={() => router.replace(`${path}?meeting=${encodeURIComponent(props.meeting)}`)}>{t("print.one_meeting")}</button>
          <button type="button" aria-pressed={scope === "month"} onClick={() => router.replace(`${path}?month=${props.month}`)}>{t("print.whole_month")}</button>
        </div>
        {scope === "meeting" ? (
          <select className="input" aria-label={t("print.meeting")} value={props.meeting} onChange={(e) => router.replace(`${path}?meeting=${encodeURIComponent(e.target.value)}`)}>
            {props.meetings.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
          </select>
        ) : (
          <>
            <select className="input" aria-label={t("print.month")} value={props.month} onChange={(e) => router.replace(`${path}?month=${e.target.value}`)}>
              {props.months.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
            </select>
            <div className="caption mt-0">{props.chosenText}</div>
          </>
        )}
      </div>

      {summary ? (
        <div className="card">
          {summary.heading ? <div className="mb-1 text-sm text-muted">{summary.heading}</div> : null}
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>{t("print.col_part")}</th><th>{t("print.col_assigned")}</th><th>{t("print.col_assistant")}</th></tr></thead>
              <tbody>{summary.rows.map((r, i) => {
                const show = (v: string, gap: boolean) => (gap ? <span className="pill warn">{v}</span> : v);
                return <tr key={i}><td>{r.part}</td><td className="font-medium">{show(r.person, r.gap[0])}</td><td>{show(r.assistant, r.gap[1])}</td></tr>;
              })}</tbody>
            </table>
          </div>
          <Link className="btn mt-3" href={props.editHref}><Icon name="edit" /> {t("print.edit")}</Link>
        </div>
      ) : null}

      <nav className="tabs mb-0" aria-label={t("common.sections")}>
        {[["print", "print.tab_sheets"], ["export", "print.tab_export"], ["messages", "print.tab_messages"]].map(([k, l]) => (
          <button key={k} type="button" aria-current={tab === k ? "page" : undefined} onClick={() => setTab(k)}>{t(l)}</button>
        ))}
      </nav>
      {tab === "print" ? <SlipsAndSheets {...props} /> : tab === "export" ? <Export {...props} /> : <Messages {...props} />}
    </div>
  );
}

function SlipsAndSheets(p: Parameters<typeof Printing>[0]) {
  const t = useTranslations();
  const [busy, act] = useAct();
  const [twoUp, setTwoUp] = useState(true);
  const stem = p.scope === "month" ? p.month : p.chosen[0]?.split("|")[0];
  const language = languageLabel(t, p.language);
  return (
    <>
      <div className="card grid gap-3">
        <h2 className="section-title mb-0">{t("print.slips")}</h2>
        {!p.slipCount ? <div className="empty">{t("print.no_slips")}</div>
          : !p.hasS89 ? <Note tone="error">{t("print.no_s89", { language })}</Note> : (
            <>
              {p.slipAux ? <div className="caption mt-0">{t("print.slip_rooms", { main: p.slipCount - p.slipAux, aux: p.slipAux })}</div> : null}
              <button type="button" className="btn primary w-fit" disabled={busy}
                onClick={() => act(() => download("slips", { meetings: p.chosen.join(","), lang: p.language, stem }))}>
                <Icon name="download" /> {t("print.download_slips", { count: p.slipCount, language })}
              </button>
            </>
          )}
      </div>
      <div className="card grid gap-3">
        <h2 className="section-title mb-0">{t("print.printable")}</h2>
        {p.chosen.length > 1 ? (
          <label className="check"><input type="checkbox" checked={twoUp} onChange={(e) => setTwoUp(e.target.checked)} /> {t("print.two_up")}</label>
        ) : null}
        <div className="btns">
          <button type="button" className="btn" disabled={busy || !p.chosen.length}
            onClick={() => act(() => download("sheet", { meetings: p.chosen.join(","), lang: p.language, compact: twoUp && p.chosen.length > 1 ? 1 : 0, stem }))}>
            <Icon name="print" /> {t("print.midweek_sheet", { count: p.chosen.length })}
          </button>
        </div>
      </div>
    </>
  );
}

function Export(p: Parameters<typeof Printing>[0]) {
  const t = useTranslations();
  const W = dateWords(t);
  const [busy, act] = useAct();
  const [month, setMonth] = useState(p.midweekMonths.includes(p.month) ? p.month : p.midweekMonths[0]);
  return (
    <>
      <div className="card grid gap-3">
        <h2 className="section-title mb-0">S-140</h2>
        {!p.midweekMonths.length ? <div className="empty">{t("print.s140_need_midweek")}</div>
          : !p.hasS140 ? <Note tone="warn">{t("print.no_s140", { language: languageLabel(t, p.language) })}</Note> : (
            <div className="flex flex-wrap items-end gap-2">
              <label className="field"><span>{t("print.month")}</span>
                <select className="input" value={month} onChange={(e) => setMonth(e.target.value)}>
                  {p.midweekMonths.map((m) => <option key={m} value={m}>{monthLabel(m, W)}</option>)}
                </select>
              </label>
              <button type="button" className="btn primary" disabled={busy}
                onClick={() => act(() => download("s140", { month, lang: p.language }))}><Icon name="download" /> {t("print.s140_for", { month: monthLabel(month, W) })}</button>
            </div>
          )}
      </div>
      <div className="card grid gap-3">
        <h2 className="section-title mb-0">{t("print.spreadsheet")}</h2>
        <button type="button" className="btn w-fit" disabled={busy} onClick={() => act(() => download("csv", {}))}><Icon name="download" /> {t("print.csv")}</button>
      </div>
    </>
  );
}

function Card({ params, stem }: { params: Record<string, string | number>; stem: string }) {
  const t = useTranslations();
  const toast = useToast();
  const [busy, act] = useAct();
  const [text, setText] = useState<string | null>(null);
  const src = pyUrl("card", { ...params, inline: 1 });
  useEffect(() => { setText(null); }, [src]);
  const copy = async () => {
    try {
      const blob = fetch(src).then((r) => r.blob());
      await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
      toast(t("print.copied"));
    } catch {
      toast(t("print.cant_copy"), { tone: "warn" });
    }
  };
  return (
    <div className="grid gap-4 md:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={src} alt={t("print.card_alt", { name: stem })} className="w-full rounded-xl border border-line bg-subtle" />
      <div className="grid content-start gap-2">
        <button type="button" className="btn primary" disabled={busy} onClick={() => act(() => download("card", params))}><Icon name="download" /> {t("print.download_image")}</button>
        <button type="button" className="btn" onClick={copy}><Icon name="copy" /> {t("print.copy_image")}</button>
        <div className="caption mt-0">{t("print.share_hint")}</div>
        <details className="rounded-xl border border-line px-3 py-2" onToggle={(e) => {
          if ((e.target as HTMLDetailsElement).open && text === null) {
            void pyGet<{ text: string }>("message_text", params).then((r) => setText(r.ok ? r.text : r.error));
          }
        }}>
          <summary className="cursor-pointer text-sm font-semibold">{t("print.text_version")}</summary>
          <pre className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap text-xs">{text ?? t("common.loading")}</pre>
        </details>
      </div>
    </div>
  );
}

function Messages(p: Parameters<typeof Printing>[0]) {
  const t = useTranslations();
  const W = dateWords(t);
  const [week, setWeek] = useState(p.defaultWeek);
  const months = Object.keys(p.monthPeople).sort().reverse();
  const [month, setMonth] = useState(months.includes(p.month) ? p.month : months[0]);
  const people = p.monthPeople[month] ?? [];
  const [person, setPerson] = useState<number | null>(null);
  const chosen = people.find((x) => x.id === person) ?? people[0];
  return (
    <>
      <div className="card grid gap-3">
        <h2 className="section-title mb-0">{t("print.weekly")}</h2>
        <div className="caption mt-0">{t("print.weekly_hint")}</div>
        <select className="input" aria-label={t("print.week")} value={week} onChange={(e) => setWeek(e.target.value)}>
          {p.weeks.map((w) => <option key={w.value} value={w.value}>{w.label}</option>)}
        </select>
        <Card params={{ week, lang: p.language }} stem={`assignments_${week}`} />
      </div>
      <div className="card grid gap-3">
        <h2 className="section-title mb-0">{t("print.person_month")}</h2>
        <div className="caption mt-0">{t("print.person_month_hint")}</div>
        <div className="row2">
          <select className="input" aria-label={t("print.month")} value={month} onChange={(e) => { setMonth(e.target.value); setPerson(null); }}>
            {months.map((m) => <option key={m} value={m}>{monthLabel(m, W)}</option>)}
          </select>
          {people.length ? (
            <select className="input" aria-label={t("print.participant")} value={chosen?.id} onChange={(e) => setPerson(Number(e.target.value))}>
              {people.map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}
            </select>
          ) : null}
        </div>
        {chosen ? <Card params={{ kind: "person", person: chosen.id, month, lang: p.language }} stem={chosen.label} />
          : <div className="empty">{t("print.nobody")}</div>}
      </div>
    </>
  );
}
