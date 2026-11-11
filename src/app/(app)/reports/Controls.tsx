"use client";
import { useTranslations } from "next-intl";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Icon } from "@/components/icons";
import { CATEGORIES } from "@/lib/constants";
import { categoryLabel } from "@/lib/labels";
import { toCSV } from "@/lib/text";

function useParam() {
  const router = useRouter();
  const path = usePathname();
  const params = useSearchParams();
  return (patch: Record<string, string | null>) => {
    const q = new URLSearchParams(params.toString());
    for (const [k, v] of Object.entries(patch)) if (v === null || v === "") q.delete(k); else q.set(k, v);
    router.replace(`${path}?${q.toString()}`, { scroll: false });
  };
}

const LABELS: Record<string, string> = { "3": "last3", "6": "last6", "12": "last12", custom: "custom" };

export function Filters({ span, from, to, future, activeOnly, cats, caption }: {
  span: string; from: string; to: string; future: boolean; activeOnly: boolean; cats: string[]; caption: string;
}) {
  const t = useTranslations();
  const set = useParam();
  return (
    <div className="card grid gap-3 md:grid-cols-[2fr_3fr]">
      <label className="field"><span>{t("rep.period")}</span>
        <select className="input" value={span} onChange={(e) => set({ span: e.target.value, from: null, to: null })}>
          {Object.entries(LABELS).map(([k, l]) => <option key={k} value={k}>{t(`rep.${l}`)}</option>)}
        </select>
      </label>
      <div className="grid gap-2">
        {span === "custom" ? (
          <div className="row2">
            <label className="field"><span>{t("rep.from")}</span><input type="date" className="input" value={from} onChange={(e) => set({ from: e.target.value })} /></label>
            <label className="field"><span>{t("rep.to")}</span><input type="date" className="input" value={to} onChange={(e) => set({ to: e.target.value })} /></label>
          </div>
        ) : null}
        <label className="check"><input type="checkbox" checked={future} onChange={(e) => set({ future: e.target.checked ? "1" : null })} />
          {t("rep.future")}</label>
        <div className="caption mt-0">{caption}</div>
        <label className="check"><input type="checkbox" checked={activeOnly} onChange={(e) => set({ all: e.target.checked ? null : "1" })} />
          {t("rep.active_only")}</label>
        <div className="flex flex-wrap gap-4">
          {CATEGORIES.map((c) => (
            <label key={c} className="check"><input type="checkbox" checked={cats.includes(c)} onChange={() => {
              const next = cats.includes(c) ? cats.filter((x) => x !== c) : [...cats, c];
              set({ cat: next.length === CATEGORIES.length ? null : next.join(",") || "none" });
            }} />{categoryLabel(t, c)}</label>
          ))}
        </div>
      </div>
    </div>
  );
}

export function CsvButton({ header, rows, name }: { header: string[]; rows: (string | number)[][]; name: string }) {
  const t = useTranslations("rep");
  return (
    <button type="button" className="btn w-fit" onClick={() => {
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([toCSV(header, rows)], { type: "text/csv;charset=utf-8" }));
      a.download = name;
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 10_000);
    }}><Icon name="download" /> {t("download")}</button>
  );
}

export function PersonPick({ people, value }: { people: { id: number; name: string }[]; value: number }) {
  const t = useTranslations("people");
  const set = useParam();
  return (
    <select className="input" aria-label={t("participant")} value={value} onChange={(e) => set({ person: e.target.value })}>
      {people.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
    </select>
  );
}
