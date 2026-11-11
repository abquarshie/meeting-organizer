import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { PageHead } from "@/components/ui";
import { MIDWEEK } from "@/lib/constants";
import { isISODate, today } from "@/lib/dates";
import { getMeetingList } from "@/lib/data";
import { Editor } from "./Editor";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("sched"))("title") };
}

export default async function SchedulePage({ searchParams }: {
  searchParams: Promise<{ date?: string; mode?: string }>;
}) {
  const [sp, all, t] = await Promise.all([searchParams, getMeetingList(), getTranslations("sched")]);
  const saved = all.filter((m) => m.type === MIDWEEK);
  const date = isISODate(sp.date) ? sp.date : today();
  return (
    <>
      <PageHead title={t("title")} sub={t("sub")} />
      <Editor key={date} date={date} mode={sp.mode === "edit" ? "edit" : "new"} saved={saved} />
    </>
  );
}
