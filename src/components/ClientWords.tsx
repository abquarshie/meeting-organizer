"use client";
import { useTranslations } from "next-intl";
import { useEffect } from "react";
import { setPyWords } from "./py";

/** Hands the browser-side messages (a timeout, an upload that didn't get through…) to py.ts in the app language. */
export function ClientWords() {
  const t = useTranslations("err");
  const p = useTranslations("print");
  const s = useTranslations("signin");
  useEffect(() => {
    setPyWords({
      timeout: t("timeout"), signIn: s("again"), noAnswer: (code) => t("no_answer", { code }),
      unreachable: t("unreachable"), tooBig: t("too_big"), downloaded: (file) => p("downloaded", { file }),
    });
  }, [t, p, s]);
  return null;
}
