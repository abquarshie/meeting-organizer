import "server-only";
import { cache } from "react";
import { prisma } from "./db";

// The app's two languages. "ada" is the ISO 639-3 code for Dangme. The screens use these codes; the printed documents
// use the slip language (constants.LANGUAGES: "English" or "Dangme"), which is a separate setting.
export const LOCALES = ["en", "ada"] as const;
export type Locale = (typeof LOCALES)[number];
export const isLocale = (v: unknown): v is Locale => (LOCALES as readonly unknown[]).includes(v);

/** The screen language, from the app_language setting. English when it isn't set or the database can't be read, so
 *  the sign-in and error pages always render. */
export const getAppLocale = cache(async (): Promise<Locale> => {
  try {
    const row = await prisma.settings.findUnique({ where: { key: "app_language" } });
    return isLocale(row?.value) ? row.value : "en";
  } catch {
    return "en";
  }
});
