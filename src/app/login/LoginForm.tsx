"use client";
import { useTranslations } from "next-intl";
import { useActionState } from "react";
import { signInAction } from "@/actions/session";

export function LoginForm({ next }: { next: string }) {
  const t = useTranslations("signin");
  const [error, act, busy] = useActionState(signInAction, null);
  return (
    <form action={act} className="form">
      <input type="hidden" name="next" value={next} />
      <label className="field"><span>{t("password")}</span>
        <input className="input" name="password" type="password" autoComplete="current-password" required autoFocus />
      </label>
      {error ? <div className="msg error">{error}</div> : null}
      <button className="btn primary mt-1 w-full" disabled={busy}>{busy ? t("busy") : t("button")}</button>
    </form>
  );
}
