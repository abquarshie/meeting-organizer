import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { Empty, PageHead, Tabs } from "@/components/ui";
import { calPath } from "@/lib/calLink";
import { getRows, getSettings, setting, slipLanguage } from "@/lib/data";
import { dateWords } from "@/lib/dateWords";
import { addDays, longDate, today } from "@/lib/dates";
import { reminderWords } from "@/lib/docWords";
import { reminderText, remindersFrom } from "@/lib/reminders";
import { CalendarTimes, ReminderList, type Card } from "./Reminders";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("rem"))("title") };
}

export default async function RemindersPage({ searchParams }: { searchParams: Promise<{ days?: string }> }) {
  const sp = await searchParams;
  const days = sp.days === "14" ? 14 : 7;
  const now = today();
  const [rows, settings, t] = await Promise.all([
    getRows({ from: now, to: addDays(now, days - 1) }), getSettings(), getTranslations(),
  ]);
  const W = dateWords(t);
  // the messages go to the participants, so they are in the slip language; the cards here are in the app language
  const words = await reminderWords(slipLanguage(settings));
  const congregation = setting(settings, "congregation");
  const list = remindersFrom(rows, words);
  const cards: Card[] = list.map((r) => {
    const text = reminderText(r, congregation, words);
    return {
      id: r.id, name: r.name, text, cal: calPath(r.id),
      wa: `https://wa.me/?text=${encodeURIComponent(text)}`,
      lines: r.duties.map((d) => d.assisting
        ? t("rem.line_assisting", { date: longDate(d.date, W), name: d.with ?? "", part: d.part })
        : t("rem.line", { date: longDate(d.date, W), part: d.part })),
    };
  });

  return (
    <>
      <PageHead title={t("rem.title")} sub={t("rem.sub")} />
      <Tabs label={t("common.sections")} current={`/reminders?days=${days}`}
        tabs={[{ href: "/reminders?days=7", label: t("rem.next7") }, { href: "/reminders?days=14", label: t("rem.next14") }]} />
      <div className="stack">
        {cards.length ? <ReminderList cards={cards} /> : <Empty>{t("rem.none", { days })}</Empty>}
        <details className="card">
          <summary>{t("rem.cal_title")}</summary>
          <p className="mt-0 text-sm text-muted">{t("rem.cal_help")}</p>
          <CalendarTimes midweek={setting(settings, "midweek_time")} />
        </details>
      </div>
    </>
  );
}
