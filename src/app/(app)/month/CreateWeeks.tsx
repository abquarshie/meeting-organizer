"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { dateWords } from "@/lib/dateWords";
import { Icon } from "@/components/icons";
import { py } from "@/components/py";
import { useAct } from "@/components/useAct";
import { MIDWEEK } from "@/lib/constants";
import { fmtDate } from "@/lib/dates";

export function CreateWeeks({ weeks, auxDefault }: { weeks: { date: string; label: string }[]; auxDefault: boolean }) {
  const t = useTranslations();
  const W = dateWords(t);
  const router = useRouter();
  const [busy, act] = useAct();
  const [aux, setAux] = useState(auxDefault);
  const [group, setGroup] = useState("");
  return (
    <>
      {weeks.length > 1 ? (
        <div className="grid gap-3 rounded-xl border border-line p-3">
          <div className="text-sm">{t("month.create_intro", { count: weeks.length })}</div>
          <label className="check"><input type="checkbox" checked={aux} onChange={(e) => setAux(e.target.checked)} /> {t("month.aux")}</label>
          {aux ? <label className="field max-w-xs"><span>{t("month.aux_group")}</span>
            <input className="input" placeholder={t("month.group_ph")} value={group} onChange={(e) => setGroup(e.target.value)} /></label> : null}
          <button type="button" className="btn primary w-fit" disabled={busy}
            onClick={() => act(() => py("create_month", { weeks, aux, group }), () => router.refresh())}>
            <Icon name="sparkle" /> {t("month.create_all", { count: weeks.length })}
          </button>
        </div>
      ) : null}
      <div className="btns">
        {weeks.map((w) => (
          <Link key={w.date} className="btn" href={`/schedule?${new URLSearchParams({ date: w.date, type: MIDWEEK })}`}>
            <Icon name="add" /> {t("month.create_one", { date: fmtDate(w.date, W, true) })}
          </Link>
        ))}
      </div>
    </>
  );
}
