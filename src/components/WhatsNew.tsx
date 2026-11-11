"use client";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import { dateWords } from "@/lib/dateWords";
import { fmtDate } from "@/lib/dates";
import { NEWS, type News } from "@/lib/whats-new";

const SEEN = "whats-new-seen";
const MAX = 4;

/**
 * "What's new" on launch: when the app has changed since this device last looked, a pop-up lists the updates once.
 * What this device has seen is remembered in the browser, so each phone or computer is told once.
 */
export function WhatsNew() {
  const ref = useRef<HTMLDialogElement>(null);
  const [show, setShow] = useState<News[]>([]);
  const latest = NEWS[0]?.id ?? 0;
  const t = useTranslations();
  const locale = useLocale();
  const W = dateWords(t);
  const text = (n: News) => (locale === "ada" && n.ada?.title ? n.ada : n.en);

  useEffect(() => {
    let seen: number | null = null;
    try {
      const v = window.localStorage.getItem(SEEN);
      seen = v === null ? null : Number(v) || 0;
    } catch {
      return; // storage blocked: don't nag on every page
    }
    // a device that has never looked is shown just the latest update
    const fresh = seen === null ? NEWS.slice(0, 1) : NEWS.filter((n) => n.id > seen!).slice(0, MAX);
    if (fresh.length) setShow(fresh);
  }, []);

  useEffect(() => {
    if (show.length && ref.current && !ref.current.open) ref.current.showModal();
  }, [show]);

  const done = () => {
    try { window.localStorage.setItem(SEEN, String(latest)); } catch { /* nothing to do */ }
    if (ref.current?.open) ref.current.close();
    setShow([]);
  };

  if (!show.length) return null;
  return (
    <dialog ref={ref} className="sheet" aria-label={t("whatsnew.title")} onClose={done}
      onClick={(e) => { if (e.target === ref.current) done(); }}>
      <div className="sheet-body">
        <div className="sheet-head"><h2 className="m-0 text-lg font-bold">{t("whatsnew.title")}</h2></div>
        <div className="grid gap-4">
          {show.map((n) => (
            <section key={n.id} className="grid gap-1.5">
              <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                <h3 className="m-0 text-[15px] font-semibold">{text(n).title}</h3>
                <span className="text-xs text-muted">{fmtDate(n.date, W)}</span>
              </div>
              <ul className="m-0 grid list-disc gap-1 pl-5 text-sm">
                {text(n).items.map((it) => <li key={it}>{it}</li>)}
              </ul>
            </section>
          ))}
        </div>
        <button type="button" className="btn primary mt-5 w-full" onClick={done} autoFocus>{t("common.got_it")}</button>
      </div>
    </dialog>
  );
}

