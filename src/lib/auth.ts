import "server-only";
import { timingSafeEqual } from "node:crypto";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { cache } from "react";
import { COOKIE, makeToken, readToken, SESSION_DAYS } from "./session";

// One person uses this app, so sign-in is a single password (APP_PASSWORD) and nothing else: no names, no roles.

export function signInConfigured(): boolean {
  return Boolean(process.env.APP_PASSWORD);
}

/** True when the password matches APP_PASSWORD. Spaces pasted around it are forgiven. */
export function passwordMatches(given: string): boolean {
  const expected = process.env.APP_PASSWORD;
  if (!expected) return false;
  const a = Buffer.from(given.trim().normalize("NFC")), b = Buffer.from(expected.trim().normalize("NFC"));
  return a.length === b.length && timingSafeEqual(a, b);
}

export async function startSession(): Promise<void> {
  (await cookies()).set(COOKIE, makeToken(), {
    httpOnly: true, sameSite: "lax", secure: process.env.NODE_ENV === "production", path: "/",
    maxAge: SESSION_DAYS * 86400,
  });
}

export async function endSession(): Promise<void> {
  (await cookies()).delete(COOKIE);
}

/** Whether the sign-in cookie is valid. */
export const isSignedIn = cache(async (): Promise<boolean> => readToken((await cookies()).get(COOKIE)?.value));

export async function requireSignIn(): Promise<void> {
  if (!(await isSignedIn())) redirect("/login");
}
