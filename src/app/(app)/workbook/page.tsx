import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { PageHead } from "@/components/ui";
import { getSettings, getWorkbook, setting } from "@/lib/data";
import { WorkbookPage } from "./WorkbookPage";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("wb");
  return { title: t("title") };
}

export default async function Page() {
  const t = await getTranslations("wb");
  const [{ weeks, file }, settings] = await Promise.all([getWorkbook(), getSettings()]);
  return (
    <>
      <PageHead title={t("title")} sub={t("sub")} />
      <WorkbookPage weeks={weeks} file={file} skipPast={setting(settings, "skip_past_weeks", "1") === "1"}
        datesSure={setting(settings, "workbook_dates_sure", "0") === "1"} />
    </>
  );
}
