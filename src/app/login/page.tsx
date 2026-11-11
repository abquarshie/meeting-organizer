import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { LoginForm } from "./LoginForm";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("signin"))("title") };
}

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ next?: string }> }) {
  const { next } = await searchParams;
  const t = await getTranslations();
  return (
    <main className="grid min-h-dvh md:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
      <section className="hero hidden rounded-none! md:flex md:flex-col md:justify-between md:p-12!">
        <div className="flex items-center gap-3 text-lg font-semibold">
          <img src="/icon.svg" alt="" className="size-10 rounded-xl ring-1 ring-white/20" />{t("app.name")}
        </div>
        <div className="max-w-md">
          <h2 className="m-0 text-3xl leading-tight font-semibold tracking-tight">{t("signin.hero_title")}</h2>
          <p className="mt-3 mb-0 text-white/75">{t("signin.hero_body")}</p>
        </div>
        <div />
      </section>
      <section className="grid place-items-center bg-[radial-gradient(ellipse_at_top,var(--brand-soft),transparent_60%)] px-4 py-10 md:bg-none">
        <div className="w-full max-w-sm">
          <div className="mb-8 flex items-center gap-3 md:hidden">
            <img src="/icon.svg" alt="" className="size-10 rounded-xl" />
            <span className="text-lg font-semibold">{t("app.name")}</span>
          </div>
          <h1 className="m-0 text-2xl font-semibold tracking-tight">{t("signin.welcome")}</h1>
          <p className="mt-1.5 mb-6 text-sm text-muted">{t("signin.sub")}</p>
          <LoginForm next={next ?? ""} />
        </div>
      </section>
    </main>
  );
}
