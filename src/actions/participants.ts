"use server";
import { getTranslations } from "next-intl/server";
import { attempt, convertOn, logChange, needId, ok, Refusal, strings } from "@/lib/action";
import { requireSignIn } from "@/lib/auth";
import { CATEGORIES, GROUPS, PRIVILEGES } from "@/lib/constants";
import { addDays, isISODate, today } from "@/lib/dates";
import { prisma } from "@/lib/db";
import { letterSubstitutes, nfc } from "@/lib/text";

// The same writes as db.add_student, update_student, set_suspension, set_unavailable and delete_student.

export type PersonInput = {
  name: string; gender: string; privileges: string[]; groups: string[]; family: string | null; active?: boolean;
};

async function clean(input: PersonInput) {
  const t = await getTranslations("people");
  const convert = await convertOn();
  const name = letterSubstitutes(nfc(input.name), convert);
  if (!name) throw new Refusal(t("need_name"));
  if (!(CATEGORIES as readonly string[]).includes(input.gender)) throw new Refusal(t("need_category"));
  const privileges = PRIVILEGES.filter((p) => strings(input.privileges).includes(p));
  const groups = GROUPS.filter((g) => strings(input.groups).includes(g));
  const family = input.family ? letterSubstitutes(nfc(input.family), convert) || null : null;
  return { name, gender: input.gender, privileges: privileges.join(", "), groups: groups.join(", "), family };
}

export async function addPerson(input: PersonInput) {
  return attempt(async () => {
    const t = await getTranslations();
    const p = await clean(input);
    const same = await prisma.students.count({ where: { name: { equals: p.name, mode: "insensitive" } } });
    await prisma.students.create({ data: { ...p, active: 1 }, select: { id: true } });
    await logChange(t("log.person_added"), p.name);
    return ok(same ? t("people.added_dup", { name: p.name }) : t("people.added", { name: p.name }));
  });
}

export async function updatePerson(id: number, input: PersonInput) {
  return attempt(async () => {
    const t = await getTranslations();
    await needId(id);
    const p = await clean(input);
    await prisma.$transaction(async (tx) => {
      await tx.students.update({ where: { id }, data: { ...p, active: input.active ? 1 : 0 } });
      // keep the name snapshot on old schedules in step with the rename
      await tx.schedules.updateMany({ where: { student_id: id }, data: { assigned_person: p.name } });
      await tx.schedules.updateMany({ where: { assistant_id: id }, data: { assistant_name: p.name } });
      await logChange(t("log.person_edited"), `${p.name} (active=${input.active ? "True" : "False"})`, tx);
    });
    return ok(t("people.saved"));
  });
}

export async function setSuspension(id: number, suspended: boolean, until: string | null) {
  return attempt(async () => {
    const t = await getTranslations();
    await needId(id);
    if (suspended && until && !isISODate(until)) throw new Refusal(t("people.bad_end"));
    await prisma.students.update({ where: { id }, data: { suspended: suspended ? 1 : 0, suspended_until: suspended ? until : null } });
    await logChange(t(suspended ? "log.suspension_set" : "log.suspension_lifted"),
      `id ${id}${until && suspended ? ` ${t("log.until", { date: until })}` : ""}`);
    return ok(t(suspended ? "people.suspension_saved" : "people.suspension_lifted"));
  });
}

/** Meetings this person is already on from today (to the end date, if any): to reassign when suspending. */
export async function upcomingFor(id: number, until: string | null) {
  await requireSignIn();
  if (!Number.isSafeInteger(id) || (until !== null && !isISODate(until))) return [];
  try {
    const rows = await prisma.schedules.findMany({
      where: { OR: [{ student_id: id }, { assistant_id: id }], meeting_date: { gte: today(), ...(until ? { lte: until } : {}) } },
      orderBy: { meeting_date: "asc" }, select: { meeting_date: true, part_name: true },
    });
    return rows.map((r) => ({ date: r.meeting_date ?? "", part: r.part_name ?? "" }));
  } catch (e) {
    console.error(e); // only a hint on the page, so a failed read just shows none
    return [];
  }
}

export async function addAway(id: number, start: string, end: string) {
  return attempt(async () => {
    const t = await getTranslations();
    await needId(id);
    if (!isISODate(start) || !isISODate(end || start)) throw new Refusal(t("people.pick_days"));
    const last = end && end >= start ? end : start;
    const days: string[] = [];
    for (let d = start; d <= last; d = addDays(d, 1)) days.push(d);
    if (days.length > 400) throw new Refusal(t("people.too_long"));
    await prisma.$transaction(async (tx) => {
      await tx.unavailable.createMany({ data: days.map((d) => ({ student_id: id, meeting_date: d })), skipDuplicates: true });
      const total = await tx.unavailable.count({ where: { student_id: id } });
      await logChange(t("log.away_changed"), `id ${id}: ${t("log.days", { count: total })}`, tx);
    });
    return ok(t("people.away_added"));
  });
}

export async function clearAway(id: number) {
  return attempt(async () => {
    const t = await getTranslations();
    await prisma.unavailable.deleteMany({ where: { student_id: await needId(id) } });
    await logChange(t("log.away_changed"), `id ${id}: ${t("log.days", { count: 0 })}`);
    return ok(t("people.away_cleared"));
  });
}

export async function deletePerson(id: number) {
  return attempt(async () => {
    const t = await getTranslations();
    await needId(id);
    const used = await prisma.schedules.count({ where: { OR: [{ student_id: id }, { assistant_id: id }] } });
    if (used) throw new Refusal(t("people.has_history"));
    const p = await prisma.students.delete({ where: { id } });
    await logChange(t("log.person_deleted"), `id ${id}`);
    return ok(t("people.deleted", { name: p.name }));
  });
}
