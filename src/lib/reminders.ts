// Who has a part in the coming days, as one reminder per person, and the same parts as a calendar (.ics) feed.
// Pure functions, so they can be checked on their own. The wording comes in as ReminderWords, in the slip language
// (see lib/docWords.ts), since these go to the participants.
import { MAIN_HALL } from "./constants";
import { longDate, type DateWords } from "./dates";

export type PartRow = {
  id: number; meeting_date: string; meeting_type: string; part_name: string | null; part_no: number | null;
  student_id: number | null; assistant_id: number | null; person: string | null; assistant: string | null;
  hall: string; role?: string | null;
};

export type Duty = { rowId: number; date: string; part: string; hall: string; with: string | null; assisting: boolean };
export type Reminder = { id: number; name: string; duties: Duty[] };

export type ReminderWords = {
  dates: DateWords;
  meeting: string; // "midweek meeting"
  halls: Record<string, string>;
  themed: Record<string, string>; // role -> the name shown before a part's theme
  aPart: string; aStudent: string;
  hello: (name: string) => string;
  intro: (many: boolean, congregation: string) => string;
  line: (date: string, meeting: string, parts: string) => string;
  youHave: (part: string) => string;
  withAssisting: (name: string) => string;
  assisting: (name: string, part: string) => string;
  thanks: string;
  calTitle: (name: string) => string;
  calAssisting: (name: string, part: string) => string;
  calDescription: (meeting: string, congregation: string, part: string) => string;
  kingdomHall: string;
};

const bare = (s: string) => s.trim().replace(/^[“"‘']+|[”"’']+$/g, "").trim();

/** The part's name, with its theme when it has one: "Treasures Talk - Jehovah Cares for You". */
export function partName(r: Pick<PartRow, "part_name" | "role">, W: Pick<ReminderWords, "themed" | "aPart">): string {
  const title = (r.part_name ?? "").trim();
  const label = r.role ? W.themed[r.role] : undefined;
  if (label && title && !title.toLowerCase().includes(label.toLowerCase())) return `${label} - ${bare(title)}`;
  return title || W.aPart;
}
const firstName = (name: string) => name.trim().split(/\s+/)[0] ?? name;

/** Everyone with a part or assisting in the rows given, earliest first. */
export function remindersFrom(rows: PartRow[], W: Pick<ReminderWords, "themed" | "aPart">): Reminder[] {
  const by = new Map<number, Reminder>();
  const add = (id: number | null, name: string | null, d: Duty) => {
    if (!id || !name) return;
    const r = by.get(id) ?? { id, name, duties: [] };
    r.duties.push(d);
    by.set(id, r);
  };
  for (const r of rows) {
    const base = { rowId: r.id, date: r.meeting_date, part: partName(r, W), hall: r.hall || MAIN_HALL };
    add(r.student_id, r.person, { ...base, with: r.assistant, assisting: false });
    add(r.assistant_id, r.assistant, { ...base, with: r.person, assisting: true });
  }
  for (const r of by.values()) r.duties.sort((a, b) => a.date.localeCompare(b.date) || a.rowId - b.rowId);
  return [...by.values()].sort((a, b) => a.duties[0].date.localeCompare(b.duties[0].date) || a.name.localeCompare(b.name));
}

function dutyLine(d: Duty, W: ReminderWords): string {
  const hall = d.hall !== MAIN_HALL ? ` (${W.halls[d.hall] ?? d.hall})` : "";
  if (d.assisting) return `${W.assisting(d.with ?? W.aStudent, d.part)}${hall}`;
  return `${W.youHave(d.part)}${hall}${d.with ? W.withAssisting(d.with) : ""}`;
}

/** The WhatsApp message for one person. */
export function reminderText(r: Reminder, congregation: string, W: ReminderWords): string {
  const byDate = new Map<string, Duty[]>();
  for (const d of r.duties) byDate.set(d.date, [...(byDate.get(d.date) ?? []), d]);
  const lines = [...byDate.values()].map((ds) =>
    W.line(longDate(ds[0].date, W.dates), W.meeting, ds.map((d) => dutyLine(d, W)).join("; ")));
  return [W.hello(firstName(r.name)), "", W.intro(r.duties.length > 1, congregation), ...lines, "", W.thanks].join("\n");
}

// ---- calendar -------------------------------------------------------------------------------------------------------

/** "18:30", "6:30pm", "6.30 pm", "7pm" -> [18, 30]; null when it can't be read. */
export function parseTime(text: string | null | undefined): [number, number] | null {
  const m = String(text ?? "").trim().toLowerCase().match(/^(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)?$/);
  if (!m) return null;
  let h = Number(m[1]);
  const min = Number(m[2] ?? 0);
  if (m[3] === "pm" && h < 12) h += 12;
  if (m[3] === "am" && h === 12) h = 0;
  return h < 24 && min < 60 ? [h, min] : null;
}

const esc = (s: string) => s.replace(/\\/g, "\\\\").replace(/;/g, "\;").replace(/,/g, "\\,").replace(/\r?\n/g, "\\n");
const two = (n: number) => String(n).padStart(2, "0");
/** Long lines folded at 75 octets (RFC 5545), counting bytes so ɛ and ɔ aren't split badly. */
function fold(line: string): string {
  const out: string[] = [];
  let cur = "", bytes = 0;
  for (const ch of line) {
    const b = Buffer.byteLength(ch);
    if (bytes + b > (out.length ? 74 : 75)) { out.push(cur); cur = ""; bytes = 0; }
    cur += ch; bytes += b;
  }
  out.push(cur);
  return out.join("\r\n ");
}

/** One person's parts as an iCalendar feed. Times are local Ghana time (UTC, all year), so they're written in UTC. */
export function calendar(r: Reminder | null, name: string, opts: { time: string; congregation: string }, W: ReminderWords): string {
  const stamp = new Date().toISOString().replace(/[-:]/g, "").slice(0, 15) + "Z";
  const lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Meeting Organizer//EN", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
    `X-WR-CALNAME:${esc(W.calTitle(name))}`, "X-WR-TIMEZONE:Africa/Accra", "REFRESH-INTERVAL;VALUE=DURATION:PT12H"];
  const t = parseTime(opts.time);
  const meeting = W.meeting ? W.meeting[0].toUpperCase() + W.meeting.slice(1) : "";
  for (const d of r?.duties ?? []) {
    const day = d.date.replace(/-/g, "");
    lines.push("BEGIN:VEVENT", `UID:mo-${d.rowId}-${d.assisting ? "a" : "p"}@meeting-organizer`, `DTSTAMP:${stamp}`);
    if (t) {
      const end = t[0] * 60 + t[1] + 105; // a meeting is about 1 h 45
      lines.push(`DTSTART:${day}T${two(t[0])}${two(t[1])}00Z`, `DTEND:${day}T${two(Math.floor(end / 60) % 24)}${two(end % 60)}00Z`);
    } else {
      lines.push(`DTSTART;VALUE=DATE:${day}`);
    }
    const summary = d.assisting ? W.calAssisting(d.with ?? "", d.part) : d.part;
    lines.push(`SUMMARY:${esc(summary.trim())}`,
      `DESCRIPTION:${esc(W.calDescription(meeting, opts.congregation ? `, ${opts.congregation}` : "", dutyLine(d, W)))}`);
    lines.push(`LOCATION:${esc(W.kingdomHall)}`);
    // a nudge the evening before
    lines.push("BEGIN:VALARM", "ACTION:DISPLAY", `DESCRIPTION:${esc(summary.trim())}`, "TRIGGER:-PT18H", "END:VALARM", "END:VEVENT");
  }
  lines.push("END:VCALENDAR");
  return lines.map(fold).join("\r\n") + "\r\n";
}
