import "server-only";
import { revalidatePath } from "next/cache";
import { getTranslations } from "next-intl/server";
import { requireSignIn } from "./auth";
import { prisma, type Tx } from "./db";

export type Result = { ok: true; message: string } | { ok: false; error: string };

export class Refusal extends Error {}

/** Server actions can be called with anything, so ids from the page are checked before they reach a query. */
export async function needId(id: unknown): Promise<number> {
  if (typeof id !== "number" || !Number.isSafeInteger(id) || id <= 0) {
    throw new Refusal((await getTranslations("people"))("not_found"));
  }
  return id;
}

/** A list of strings from the page, or an empty list. */
export function strings(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((v): v is string => typeof v === "string") : [];
}

export function ok(message: string): Result {
  revalidatePath("/", "layout"); // every page reads the same data, so all of them refresh
  return { ok: true, message };
}

/** Runs a server action's work once the sign-in is checked, turning a refusal or a database error into a message. */
export async function attempt(work: () => Promise<Result>): Promise<Result> {
  try {
    await requireSignIn();
    return await work();
  } catch (e) {
    if (e instanceof Refusal) return { ok: false, error: e.message };
    const digest = (e as { digest?: string })?.digest;
    if (typeof digest === "string" && digest.startsWith("NEXT_REDIRECT")) throw e; // signed out: let it redirect
    console.error(e);
    return { ok: false, error: (await getTranslations("err"))("not_saved") };
  }
}

/** A line in the change log, in the same table and format as db.log_change. The action is written in the app
 *  language at the time of the change. */
export async function logChange(action: string, details = "", tx: Tx | typeof prisma = prisma) {
  const ts = new Date().toISOString().slice(0, 19); // isoformat(timespec="seconds"), server time (UTC)
  await tx.audit_log.create({ data: { ts, action, details } });
}

export async function convertOn(tx: Tx | typeof prisma = prisma): Promise<boolean> {
  const row = await tx.settings.findUnique({ where: { key: "letter_convert" } });
  return row?.value === "1";
}

export async function setSetting(k: string, value: string, tx: Tx | typeof prisma = prisma) {
  await tx.settings.upsert({ where: { key: k }, create: { key: k, value }, update: { value } });
}
