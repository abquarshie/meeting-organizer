import { getTranslations } from "next-intl/server";
import { signOutAction } from "@/actions/session";
import { ClientWords } from "@/components/ClientWords";
import { Icon } from "@/components/icons";
import { AppLanguagePick, LanguagePick } from "@/components/LanguagePick";
import { SideNav, TabBar, type NavItem } from "@/components/Nav";
import { WhatsNew } from "@/components/WhatsNew";
import { requireSignIn } from "@/lib/auth";
import { LANGUAGES } from "@/lib/constants";
import { prisma } from "@/lib/db";
import { getAppLocale } from "@/lib/locale";

export const dynamic = "force-dynamic"; // always the latest schedules

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  await requireSignIn();
  // the frame must render even when the database is down, so the page's own error screen shows inside it
  const [settings, locale, t] = await Promise.all([
    prisma.settings.findMany({ where: { key: { in: ["slip_language", "owner_name"] } } })
      .catch((e) => { console.error(e); return []; }),
    getAppLocale(), getTranslations(),
  ]);
  const get = (k: string) => settings.find((s) => s.key === k)?.value ?? "";
  const language = (LANGUAGES as readonly string[]).includes(get("slip_language")) ? get("slip_language") : LANGUAGES[0];
  const owner = get("owner_name");
  const initials = owner.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]!.toUpperCase()).join("") || "✓";
  const items: NavItem[] = [
    { href: "/", label: t("nav.home"), icon: "home", phone: true },
    { href: "/month", label: t("nav.month"), short: t("nav.month_short"), icon: "calendar", phone: true },
    { href: "/schedule", label: t("nav.schedule"), short: t("nav.schedule_short"), icon: "edit", phone: true },
    { href: "/print", label: t("nav.print"), short: t("nav.print_short"), icon: "print", phone: true },
    { href: "/reminders", label: t("nav.reminders"), icon: "clock" },
    { href: "/participants", label: t("nav.participants"), short: t("nav.participants_short"), icon: "people", phone: true },
    { href: "/workbook", label: t("nav.workbook"), icon: "book" },
    { href: "/reports", label: t("nav.reports"), icon: "chart" },
    { href: "/admin", label: t("nav.admin"), icon: "settings" },
  ];
  return (
    <div className="min-h-dvh md:grid md:grid-cols-[256px_minmax(0,1fr)]">
      <aside className="sticky top-0 hidden h-dvh flex-col border-r border-line bg-surface px-3 py-5 md:flex">
        <a className="mb-6 flex items-center gap-2.5 px-2 text-[15px] font-semibold tracking-tight text-ink no-underline" href="/">
          <img src="/icon.svg" alt="" className="size-8 rounded-lg shadow-soft" />
          <span className="leading-tight">{t("app.name")}<span className="block text-xs font-normal text-muted">{t("app.tagline")}</span></span>
        </a>
        <div className="eyebrow mb-2 px-3">{t("nav.menu")}</div>
        <SideNav items={items} label={t("nav.main")} />
        <div className="mt-auto grid gap-4 pt-4">
          <AppLanguagePick value={locale} />
          <LanguagePick value={language} />
          <div className="flex items-center gap-2.5 rounded-xl border border-line bg-subtle/60 p-2">
            <span className="avatar">{initials}</span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-semibold">{owner || t("app.name")}</span>
              <span className="block text-xs text-muted">{t("nav.signed_in")}</span>
            </span>
            <form action={signOutAction}>
              <button className="btn ghost small text-muted!" type="submit" title={t("nav.sign_out")} aria-label={t("nav.sign_out")}><Icon name="logout" /></button>
            </form>
          </div>
        </div>
      </aside>
      <div className="min-w-0">
        <header className="sticky top-0 z-30 flex items-center gap-2.5 border-b border-line bg-surface/90 px-4 py-2.5 backdrop-blur md:hidden">
          <a href="/" className="flex items-center gap-2 text-[15px] font-semibold text-ink no-underline">
            <img src="/icon.svg" alt="" className="size-7 rounded-lg" />{t("app.name")}
          </a>
          <span className="avatar ml-auto size-8! text-xs">{initials}</span>
          <form action={signOutAction}>
            <button className="btn ghost small text-muted!" type="submit" aria-label={t("nav.sign_out")}><Icon name="logout" /></button>
          </form>
        </header>
        <main className="mx-auto w-full max-w-6xl px-4 pt-5 pb-28 md:px-10 md:pt-10 md:pb-16">{children}</main>
      </div>
      <TabBar items={items} label={t("nav.main")} more={t("nav.more")} />
      <WhatsNew />
      <ClientWords />
    </div>
  );
}
