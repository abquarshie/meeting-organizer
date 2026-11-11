/** Unicode NFC and trimmed, as utils.nfc. Names with ɛ, ɔ and ŋ typed on different keyboards must compare equal. */
export function nfc(text: unknown): string {
  return String(text ?? "").normalize("NFC").trim();
}

const LETTER_SUBSTITUTES: Record<string, string> = { "3": "ɛ", ")": "ɔ" };

/** Typists use 3 ) N for ɛ ɔ ŋ when the keyboard lacks them (Admin → Settings switches this on), as
 * db.apply_letter_substitutes. A capital N only becomes ŋ between letters, so real initials survive. */
export function letterSubstitutes(text: string, on: boolean): string {
  if (!on) return text;
  const swapped = [...(text ?? "")].map((ch) => LETTER_SUBSTITUTES[ch] ?? ch).join("");
  return swapped.replace(/(?<=[A-Za-zɛɔŋ])N(?=[a-zɛɔŋ])/g, "ŋ");
}

/** CSV text with a BOM, so Excel keeps ɛ and ɔ right. */
export function toCSV(header: string[], rows: (string | number | null | undefined)[][]): string {
  const cell = (v: string | number | null | undefined) => {
    const s = v === null || v === undefined ? "" : String(v);
    return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return "﻿" + [header, ...rows].map((r) => r.map(cell).join(",")).join("\r\n") + "\r\n";
}
