import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { signOutAction } from "@/actions/session";
import { AppLanguagePick, LanguagePick } from "@/components/LanguagePick";
import { Icon } from "@/components/icons";
import { PageHead, Tabs } from "@/components/ui";
import { LANGUAGES } from "@/lib/constants";
import { gapDays, getEvents, getSettings, setting, templateNames } from "@/lib/data";
import { dateWords } from "@/lib/dateWords";
import { weekLabel } from "@/lib/dates";
import { prisma } from "@/lib/db";
import { eventWords } from "@/lib/docWords";
import { eventWeekLabel } from "@/lib/labels";
import { getAppLocale } from "@/lib/locale";
import { Backup, ChangeLog, Settings, Templates } from "./Admin";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("admin");
  return { title: t("title") };
}

const TABS = [["data", "admin.tab_data"], ["settings", "admin.tab_settings"], ["log", "admin.tab_log"]] as const;

export default async function AdminPage({ searchParams }: { searchParams: Promise<{ tab?: string }> }) {
  const t = await getTranslations();
  const W = dateWords(t);
  const sp = await searchParams;
  const tab = TABS.some(([k]) => k === sp.tab) ? sp.tab! : "data";
  const [settings, locale] = await Promise.all([getSettings(), getAppLocale()]);
  let body;
  if (tab === "settings") {
    const [events, words] = await Promise.all([getEvents(), eventWords()]);
    body = (
      <Settings congregation={setting(settings, "congregation")} ownerName={setting(settings, "owner_name")}
        useAux={setting(settings, "use_aux", "1") === "1"} convert={setting(settings, "letter_convert", "0") === "1"}
        midweek={setting(settings, "midweek_day", "Wednesday")} gap={gapDays(settings)}
        events={events.map((e) => ({ id: e.id, text: `${weekLabel(e.start, W)} — ${eventWeekLabel(t, e.kind)}` }))}
        words={words} locale={locale} />
    );
  } else if (tab === "log") {
    const log = await prisma.audit_log.findMany({ orderBy: { id: "desc" }, take: 500 });
    body = <ChangeLog log={log.map((l) => ({ id: l.id, ts: (l.ts ?? "").replace("T", " "), action: l.action ?? "", details: l.details ?? "" }))} />;
  } else {
    const names = await templateNames();
    body = (
      <>
        <Templates languages={[...LANGUAGES]} stored={Object.fromEntries(names)} />
        <Backup />
      </>
    );
  }
  return (
    <>
      <PageHead title={t("admin.title")} sub={t("admin.sub")} />
      <Tabs label={t("common.sections")} current={`/admin?tab=${tab}`} tabs={TABS.map(([k, l]) => ({ href: `/admin?tab=${k}`, label: t(l) }))} />
      <div className="stack">
        {body}
        {/* the sidebar holds these on a computer; a phone has only the tab bar */}
        <div className="card grid gap-3 md:hidden">
          <AppLanguagePick value={locale} />
          <LanguagePick value={setting(settings, "slip_language", "English")} />
          <form action={signOutAction} className="flex items-center gap-3">
            <span className="flex-1 text-sm text-muted">{t("nav.signed_in")}</span>
            <button className="btn small"><Icon name="logout" /> {t("nav.sign_out")}</button>
          </form>
        </div>
      </div>
    </>
  );
}
