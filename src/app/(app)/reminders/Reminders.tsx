"use client";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { saveCalendarTime } from "@/actions/settings";
import { Icon } from "@/components/icons";
import { useToast } from "@/components/Toaster";
import { useAct } from "@/components/useAct";

export type Card = { id: number; name: string; wa: string; text: string; lines: string[]; cal: string };

export function ReminderList({ cards }: { cards: Card[] }) {
  const t = useTranslations("rem");
  const toast = useToast();
  const [sent, setSent] = useState<Set<number>>(new Set());
  const copy = async (text: string, what: string) => {
    try {
      await navigator.clipboard.writeText(text);
      toast(t("copied", { what }));
    } catch {
      toast(t("cant_copy"), { tone: "warn" });
    }
  };
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {cards.map((c) => (
        <div key={c.id} className={`card ${sent.has(c.id) ? "opacity-60" : ""}`}>
          <div className="card-head">
            <h2>{c.name}</h2>
          </div>
          <ul className="mt-0 mb-3 grid gap-1 pl-4 text-sm">{c.lines.map((l, i) => <li key={i}>{l}</li>)}</ul>
          <div className="flex flex-wrap gap-2">
            <a className="btn primary" href={c.wa} target="_blank" rel="noopener noreferrer"
              onClick={() => setSent((s) => new Set(s).add(c.id))}>
              <Icon name="check" />{t("whatsapp")}
            </a>
            <button type="button" className="btn" onClick={() => copy(c.text, t("message"))}><Icon name="copy" />{t("copy")}</button>
            <button type="button" className="btn" onClick={() => copy(`${window.location.origin}${c.cal}`, t("cal_link"))}>
              <Icon name="calendar" />{t("cal_link")}
            </button>
            {/* webcal:// makes an iPhone offer "Subscribe" instead of adding the parts once */}
            <button type="button" className="btn" onClick={() => copy(`webcal://${window.location.host}${c.cal}`, t("iphone_link_long"))}>
              <Icon name="calendar" />{t("iphone_link")}
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}

export function CalendarTimes({ midweek }: { midweek: string }) {
  const t = useTranslations("rem");
  const [m, setM] = useState(midweek);
  const [busy, act] = useAct();
  return (
    <form className="form" onSubmit={(e) => { e.preventDefault(); act(() => saveCalendarTime(m)); }}>
      <label className="field max-w-xs"><span>{t("midweek_starts")}</span><input className="input" value={m} onChange={(e) => setM(e.target.value)} placeholder={t("time_ph_evening")} /></label>
      <button className="btn w-fit" disabled={busy}>{t("save_times")}</button>
    </form>
  );
}
