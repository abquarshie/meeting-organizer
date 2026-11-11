import "server-only";
import { getTranslations } from "next-intl/server";
import { dateWords } from "./dateWords";
import { hallLabel } from "./labels";
import type { ReminderWords } from "./reminders";

/** The screen locale that matches a slip language: what the participants read. */
export const slipLocale = (language: string) => (language === "Dangme" ? "ada" : "en");

/** The reminder and calendar wording in the slip language. */
export async function reminderWords(language: string): Promise<ReminderWords> {
  const t = await getTranslations({ locale: slipLocale(language) });
  return {
    dates: dateWords(t),
    meeting: t("mt.midweek_lower"),
    halls: { aux_1: hallLabel(t, "aux_1"), aux_2: hallLabel(t, "aux_2") },
    themed: { "Treasures Talk": t("role.treasures_talk"), "Living Part": t("sec.living"), "Student Talk": t("part.talk") },
    aPart: t("part.a_part"), aStudent: t("rem.msg_a_student"),
    hello: (name) => t("rem.msg_hello", { name }),
    intro: (many, congregation) => congregation
      ? t(many ? "rem.msg_intro_many" : "rem.msg_intro_one", { congregation })
      : t(many ? "rem.msg_intro_many_plain" : "rem.msg_intro_one_plain"),
    line: (date, meeting, parts) => t("rem.msg_line", { date, meeting, parts }),
    youHave: (part) => t("rem.msg_you_have", { part }),
    withAssisting: (name) => t("rem.msg_with", { name }),
    assisting: (name, part) => t("rem.msg_assisting", { name, part }),
    thanks: t("rem.msg_thanks"),
    calTitle: (name) => t("cal.title", { name }),
    calAssisting: (name, part) => t("cal.assisting", { name, part }),
    calDescription: (meeting, congregation, part) => t("cal.description", { meeting, congregation, part }),
    kingdomHall: t("cal.kingdom_hall"),
  };
}

/** The assembly and convention week labels in both languages, for the "will show … (in Dangme: …)" preview. */
export async function eventWords(): Promise<Record<string, { en: string; ada: string }>> {
  const [en, ada] = await Promise.all([getTranslations({ locale: "en" }), getTranslations({ locale: "ada" })]);
  return {
    assembly: { en: en("ev.assembly_week"), ada: ada("ev.assembly_week") },
    convention: { en: en("ev.convention_week"), ada: ada("ev.convention_week") },
  };
}
