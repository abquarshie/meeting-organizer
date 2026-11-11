import Link from "next/link";
import { getTranslations } from "next-intl/server";

export default async function NotFound() {
  const t = await getTranslations();
  return (
    <main className="grid min-h-dvh place-items-center px-4">
      <div className="card grid w-full max-w-sm gap-3 text-center">
        <img src="/icon.svg" alt="" className="mx-auto size-10" />
        <h1 className="m-0 text-xl font-bold">{t("err.not_found_title")}</h1>
        <p className="m-0 text-sm text-muted">{t("err.not_found_body")}</p>
        <Link className="btn primary" href="/">{t("common.go_home")}</Link>
      </div>
    </main>
  );
}
