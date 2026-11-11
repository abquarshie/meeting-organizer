"use server";
import { getTranslations } from "next-intl/server";
import { attempt, logChange, needId, ok, Refusal, setSetting } from "@/lib/action";
import { LANGUAGES, SAME_ROLE_GAP_DAYS, WEEKDAYS } from "@/lib/constants";
import { prisma } from "@/lib/db";
import { isLocale } from "@/lib/locale";
import { nfc } from "@/lib/text";
import { parseTime } from "@/lib/reminders";

/** The language of the screens: "en" or "ada" (Dangme). */
export async function setAppLanguage(locale: string) {
  return attempt(async () => {
    if (!isLocale(locale)) throw new Refusal((await getTranslations("admin"))("unknown_language"));
    await setSetting("app_language", locale);
    // the message is read after the switch, so it is already in the new language
    const t = await getTranslations({ locale });
    return ok(t("admin.app_language_saved", { language: t(locale === "ada" ? "lang.dangme" : "lang.english") }));
  });
}

/** The language of slips, sheets, the S-140 and the messages: "English" or "Dangme". */
export async function setLanguage(language: string) {
  return attempt(async () => {
    const t = await getTranslations();
    if (!(LANGUAGES as readonly string[]).includes(language)) throw new Refusal(t("admin.unknown_language"));
    await setSetting("slip_language", language);
    return ok(t("admin.language_saved", { language: t(language === "Dangme" ? "lang.dangme" : "lang.english") }));
  });
}

export async function savePrinting(input: { congregation: string; ownerName: string; useAux: boolean; convert: boolean }) {
  return attempt(async () => {
    await prisma.$transaction(async (tx) => {
      await setSetting("congregation", nfc(input.congregation), tx);
      await setSetting("owner_name", nfc(input.ownerName).slice(0, 60), tx);
      await setSetting("use_aux", input.useAux ? "1" : "0", tx);
      await setSetting("letter_convert", input.convert ? "1" : "0", tx);
    });
    return ok((await getTranslations("common"))("saved"));
  });
}

export async function saveMeetingDay(midweek: string) {
  return attempt(async () => {
    const t = await getTranslations();
    if (!WEEKDAYS.includes(midweek)) throw new Refusal(t("admin.pick_day"));
    await setSetting("midweek_day", midweek);
    await logChange(t("log.days_changed"), midweek);
    return ok(t("common.saved"));
  });
}

export async function saveRotation(days: number) {
  return attempt(async () => {
    const t = await getTranslations();
    const n = Math.round(Number(days));
    if (!Number.isFinite(n) || n < 1 || n > 90) throw new Refusal(t("admin.rotation_range", { default: SAME_ROLE_GAP_DAYS }));
    await setSetting("same_role_gap_days", String(n));
    await logChange(t("log.rotation_changed"), t("log.days", { count: n }));
    return ok(t("common.saved"));
  });
}

export async function removeEventWeek(id: number) {
  return attempt(async () => {
    const t = await getTranslations();
    await prisma.no_meeting_periods.deleteMany({ where: { id: await needId(id) } });
    await logChange(t("log.event_removed"), `id ${id}`);
    return ok(t("common.removed"));
  });
}

export async function removeTemplate(name: string) {
  return attempt(async () => {
    const t = await getTranslations();
    if (!/^(s89|s140)_(English|Dangme)$/.test(name)) throw new Refusal(t("admin.unknown_form"));
    await prisma.templates.deleteMany({ where: { name } });
    await logChange(t("log.form_removed"), name);
    return ok(t("common.removed"));
  });
}

/** The meeting start time the calendar feeds use, e.g. "18:30" or "6:30pm". Empty makes them all-day entries. */
export async function saveCalendarTime(midweek: string) {
  return attempt(async () => {
    const t = await getTranslations();
    const m = nfc(midweek).slice(0, 20);
    if (m && !parseTime(m)) throw new Refusal(t("rem.time_format", { meeting: t("mt.midweek_lower") }));
    await setSetting("midweek_time", m);
    await logChange(t("log.times_changed"), m || "—");
    return ok(t("rem.times_saved"));
  });
}
