import { createHmac, timingSafeEqual } from "node:crypto";

// The sign-in cookie: base64url(JSON {e: expiry}) + "." + base64url(HMAC-SHA256 of that, SESSION_SECRET).
// api/index.py checks the same cookie with the same secret (signed_in), so keep the two in step.
export const COOKIE = "mo_session";
export const SESSION_DAYS = 30;

function secret(): string {
  const s = process.env.SESSION_SECRET;
  if (!s || s.length < 16) throw new Error("SESSION_SECRET is not set (any long random string, at least 16 characters).");
  return s;
}

const b64 = (b: Buffer) => b.toString("base64url");
const sign = (body: string) => b64(createHmac("sha256", secret()).update(body).digest());

export function makeToken(days = SESSION_DAYS): string {
  const body = b64(Buffer.from(JSON.stringify({ e: Math.floor(Date.now() / 1000) + days * 86400 })));
  return `${body}.${sign(body)}`;
}

/** True when the token is signed with SESSION_SECRET and hasn't expired. */
export function readToken(token: string | undefined): boolean {
  if (!token || token.length > 1000 || !token.includes(".")) return false;
  const [body, sig] = [token.slice(0, token.lastIndexOf(".")), token.slice(token.lastIndexOf(".") + 1)];
  const want = Buffer.from(sign(body)), got = Buffer.from(sig);
  if (want.length !== got.length || !timingSafeEqual(want, got)) return false;
  try {
    const p = JSON.parse(Buffer.from(body, "base64url").toString("utf8")) as { e?: number };
    return Boolean(p.e && p.e >= Date.now() / 1000);
  } catch {
    return false;
  }
}
