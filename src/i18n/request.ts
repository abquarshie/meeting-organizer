import { getRequestConfig } from "next-intl/server";
import en from "../../messages/en.json";
import ada from "../../messages/ada.json";
import { getAppLocale, isLocale } from "@/lib/locale";

type Tree = { [k: string]: string | Tree };

/** English with every Dangme string that has been filled in laid over it, so a string still being translated shows in
 *  English rather than as an empty space. */
function overlay(base: Tree, over: Tree): Tree {
  const out: Tree = { ...base };
  for (const [k, v] of Object.entries(over)) {
    const b = base[k];
    if (typeof v === "string") { if (v.trim()) out[k] = v; }
    else if (b && typeof b === "object") out[k] = overlay(b, v);
  }
  return out;
}

const DANGME = overlay(en as Tree, ada as Tree);

// A caller can ask for a language explicitly (getTranslations({ locale })): the messages and calendar feeds are written
// in the slip language, whatever the screens are set to.
export default getRequestConfig(async ({ locale: asked }) => {
  const locale = isLocale(asked) ? asked : await getAppLocale();
  return {
    locale,
    messages: locale === "ada" ? DANGME : en,
    timeZone: "UTC", // Ghana is on UTC, and the stored dates are plain ISO days
  };
});
