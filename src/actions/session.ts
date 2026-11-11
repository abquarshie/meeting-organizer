"use server";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { endSession, passwordMatches, signInConfigured, startSession } from "@/lib/auth";
import { cleared, failed, lockedFor, MAX_TRIES } from "@/lib/lockout";

export async function signInAction(_: string | null, form: FormData): Promise<string | null> {
  const t = await getTranslations("signin");
  let wait: number;
  try {
    wait = await lockedFor();
  } catch (e) {
    console.error(e);
    return t("unavailable");
  }
  if (wait > 0) return t("locked_seconds", { seconds: Math.ceil(wait / 1000) });
  if (!signInConfigured()) return t("not_set_up");
  if (!passwordMatches(String(form.get("password") ?? ""))) {
    await new Promise((r) => setTimeout(r, 600)); // slows down anyone guessing the password
    const n = await failed().catch((e) => { console.error(e); return 0; });
    if (n >= MAX_TRIES) return t("locked_minute");
    return t("tries_left", { message: t("wrong"), count: Math.max(MAX_TRIES - n, 1) });
  }
  await cleared().catch((e) => console.error(e));
  await startSession();
  const next = String(form.get("next") ?? "");
  redirect(next.startsWith("/") && !next.startsWith("//") ? next : "/");
}

export async function signOutAction() {
  await endSession();
  redirect("/login");
}
