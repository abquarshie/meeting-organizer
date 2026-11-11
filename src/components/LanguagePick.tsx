"use client";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { setAppLanguage, setLanguage } from "@/actions/settings";
import { LANGUAGES } from "@/lib/constants";
import { languageLabel } from "@/lib/labels";
import { useAct } from "./useAct";

/** The language of the screens: English or Dangme. */
export function AppLanguagePick({ value }: { value: string }) {
  const t = useTranslations();
  const router = useRouter();
  const [busy, act] = useAct();
  const [lang, setLang] = useState(value);
  return (
    <label className="field">
      <span className="eyebrow px-1">{t("lang.app")}</span>
      <select className="input" value={lang} disabled={busy}
        onChange={(e) => { const v = e.target.value; setLang(v); act(() => setAppLanguage(v), () => router.refresh()); }}>
        <option value="en">{t("lang.english")}</option>
        <option value="ada">{t("lang.dangme")}</option>
      </select>
    </label>
  );
}

/** The slip language: for slips, schedule sheets, the S-140 and the messages. */
export function LanguagePick({ value }: { value: string }) {
  const t = useTranslations();
  const [busy, act] = useAct();
  const [lang, setLang] = useState(value);
  return (
    <label className="field">
      <span className="eyebrow px-1">{t("lang.documents")}</span>
      <select className="input" value={lang} disabled={busy}
        onChange={(e) => { const v = e.target.value; setLang(v); act(() => setLanguage(v)); }}>
        {LANGUAGES.map((l) => <option key={l} value={l}>{languageLabel(t, l)}</option>)}
      </select>
    </label>
  );
}
