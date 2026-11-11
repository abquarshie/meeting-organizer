"use client";
import { useTranslations } from "next-intl";
import { useEffect } from "react";
import { Icon } from "@/components/icons";

// Shown in place of a page that failed to load (usually the database not answering), with the menu still around it.
export default function PageError({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  const t = useTranslations();
  useEffect(() => { console.error(error); }, [error]);
  return (
    <div className="card mx-auto mt-6 grid max-w-lg gap-3 text-center">
      <div className="mx-auto grid size-12 place-items-center rounded-full bg-warn-soft text-warn [&_svg]:size-6"><Icon name="warning" /></div>
      <h1 className="m-0 text-xl font-bold">{t("err.page_title")}</h1>
      <p className="m-0 text-sm text-muted">{t("err.page_body")}</p>
      <div className="btns justify-center">
        <button type="button" className="btn primary" onClick={() => retry()}>{t("common.try_again")}</button>
        <a className="btn" href="/">{t("common.go_home")}</a>
      </div>
      {error.digest ? <div className="caption mt-0">{t("err.reference")} {error.digest}</div> : null}
    </div>
  );
}
