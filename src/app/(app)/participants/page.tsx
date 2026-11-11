import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { PageHead } from "@/components/ui";
import { assignmentStats, familyNames, getPeople } from "@/lib/data";
import { prisma } from "@/lib/db";
import { People } from "./People";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("people"))("title") };
}

export default async function ParticipantsPage({ searchParams }: { searchParams: Promise<{ tab?: string; id?: string }> }) {
  const [sp, people, { used, last }, away, t] = await Promise.all([
    searchParams, getPeople(), assignmentStats(), prisma.unavailable.findMany({ orderBy: { meeting_date: "asc" } }), getTranslations("people"),
  ]);
  const awayBy: Record<number, string[]> = {};
  for (const a of away) (awayBy[a.student_id] ??= []).push(a.meeting_date);
  return (
    <>
      <PageHead title={t("title")} sub={t("sub")} />
      <People people={people} families={familyNames(people)} tab={sp.tab ?? (people.length ? "list" : "add")}
        selected={Number(sp.id) || people[0]?.id || 0} last={Object.fromEntries(last)} used={Object.fromEntries(used)} away={awayBy} />
    </>
  );
}
