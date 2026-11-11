"use client";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { EVENT_KINDS } from "@/lib/constants";
import { today } from "@/lib/dates";
import { eventLabel } from "@/lib/labels";
import { py, pyGet } from "./py";
import { useAct } from "./useAct";

type Preview = { label: string; saved: { date: string; type: string; text: string }[] };
/** The week label in each language: { assembly: { en, ada }, convention: { en, ada } }, from the page. */
export type EventWords = Record<string, { en: string; ada: string }>;

/** Mark a week as a circuit assembly or convention week. Any day in the week will do. Meetings already saved that
 * week are listed, and cleared only once that is ticked (each can be brought back with Undo). */
export function MarkEventWeek({ defaultDay, words, locale }: { defaultDay?: string; words: EventWords; locale: string }) {
  const t = useTranslations();
  const router = useRouter();
  const [busy, act] = useAct();
  const [day, setDay] = useState(defaultDay ?? today());
  const [kind, setKind] = useState<string>("assembly");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [sure, setSure] = useState(false);

  useEffect(() => {
    let live = true;
    setSure(false);
    void pyGet<Preview>("week_preview", { day }).then((r) => { if (live && r.ok) setPreview(r); });
    return () => { live = false; };
  }, [day]);

  const saved = preview?.saved ?? [];
  const here = locale === "ada" ? words[kind].ada : words[kind].en;
  const other = locale === "ada" ? words[kind].en : words[kind].ada;
  return (
    <div className="grid gap-3">
      <div className="row2">
        <label className="field"><span>{t("event.any_day")}</span>
          <input className="input" type="date" value={day} onChange={(e) => e.target.value && setDay(e.target.value)} />
        </label>
        <div className="field"><span>{t("event.kind")}</span>
          <div className="seg w-fit" role="group">
            {EVENT_KINDS.map((k) => <button key={k} type="button" aria-pressed={kind === k} onClick={() => setKind(k)}>{eventLabel(t, k)}</button>)}
          </div>
        </div>
      </div>
      {preview ? <div className="text-sm">{t("event.preview", {
        week: preview.label, label: here, label_other: other,
        language: t(locale === "ada" ? "lang.english" : "lang.dangme"),
      })}</div> : null}
      {saved.length ? (
        <>
          <div className="note warn">{t("event.already_saved", { meetings: saved.map((m) => m.text).join(", ") })}</div>
          <label className="check"><input type="checkbox" checked={sure} onChange={(e) => setSure(e.target.checked)} />
            {t("event.clear_them")}</label>
        </>
      ) : null}
      <button type="button" className="btn primary w-fit" disabled={busy || (saved.length > 0 && !sure)}
        onClick={() => act(() => py("mark_event", { day, kind }), () => router.refresh())}>
        {t("event.mark", { kind: eventLabel(t, kind) })}
      </button>
    </div>
  );
}
