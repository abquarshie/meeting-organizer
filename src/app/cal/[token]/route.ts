import { readCalToken } from "@/lib/calLink";
import { getRows, getSettings, setting, slipLanguage } from "@/lib/data";
import { addDays, today } from "@/lib/dates";
import { prisma } from "@/lib/db";
import { reminderWords } from "@/lib/docWords";
import { getTranslations } from "next-intl/server";
import { calendar, remindersFrom } from "@/lib/reminders";

// A participant's assignments as a calendar feed (no sign-in: the signed link is the key). Phones that subscribe
// re-read it every few hours, so new and changed parts show up on their own. Written in the slip language.
export async function GET(_: Request, { params }: { params: Promise<{ token: string }> }) {
  const id = readCalToken((await params).token);
  const t = await getTranslations("err");
  if (id === null) return new Response(t("cal_bad_link"), { status: 404 });
  try {
    const [person, rows, settings] = await Promise.all([
      prisma.students.findUnique({ where: { id }, select: { name: true } }),
      getRows({ from: addDays(today(), -60), person: id }),
      getSettings(),
    ]);
    if (!person) return new Response(t("not_found_title"), { status: 404 });
    const W = await reminderWords(slipLanguage(settings));
    const mine = remindersFrom(rows, W).find((r) => r.id === id) ?? null;
    const body = calendar(mine, person.name, {
      time: setting(settings, "midweek_time"), congregation: setting(settings, "congregation"),
    }, W);
    return new Response(body, {
      headers: {
        "content-type": "text/calendar; charset=utf-8",
        "content-disposition": `inline; filename="assignments-${id}.ics"`,
        "cache-control": "private, max-age=300",
      },
    });
  } catch (e) {
    console.error(e);
    return new Response(t("cal_unreadable"), { status: 503 });
  }
}
