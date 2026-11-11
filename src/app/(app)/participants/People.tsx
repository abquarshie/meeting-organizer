"use client";
import { useTranslations } from "next-intl";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  addAway, addPerson, clearAway, deletePerson, setSuspension, updatePerson, upcomingFor, type PersonInput,
} from "@/actions/participants";
import { Confirm } from "@/components/Sheet";
import { Note } from "@/components/ui";
import { useAct } from "@/components/useAct";
import { CATEGORIES, GROUPS, PRIVILEGES } from "@/lib/constants";
import type { Person } from "@/lib/data";
import { dateWords } from "@/lib/dateWords";
import { addDays, awaySummary, fmtDate, today } from "@/lib/dates";
import { categoryLabel, groupLabel, roleLabel } from "@/lib/labels";

const NO_FAMILY = "__none";

function suspendedNow(p: Person) {
  return p.suspended && (!p.suspendedUntil || today() <= p.suspendedUntil);
}

function PersonForm({ initial, families, submit, button, withActive }: {
  initial: PersonInput; families: string[]; button: string; withActive?: boolean;
  submit: (p: PersonInput) => void;
}) {
  const t = useTranslations();
  const [p, setP] = useState(initial);
  const [newFamily, setNewFamily] = useState("");
  const toggle = (list: string[], v: string) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);
  return (
    <form className="form" onSubmit={(e) => { e.preventDefault(); submit({ ...p, family: newFamily.trim() || p.family }); }}>
      <label className="field"><span>{t("people.full_name")}</span>
        <input className="input" value={p.name} onChange={(e) => setP({ ...p, name: e.target.value })} required />
      </label>
      <div className="row2">
        <label className="field"><span>{t("people.category")}</span>
          <select className="input" value={p.gender} onChange={(e) => setP({ ...p, gender: e.target.value })}>
            {CATEGORIES.map((c) => <option key={c} value={c}>{categoryLabel(t, c)}</option>)}
          </select>
        </label>
        <div className="field"><span>{t("people.group")}</span>
          <div className="flex flex-wrap gap-3 pt-2">
            {GROUPS.map((g) => (
              <label key={g} className="check"><input type="checkbox" checked={p.groups.includes(g)}
                onChange={() => setP({ ...p, groups: toggle(p.groups, g) })} />{groupLabel(t, g)}</label>
            ))}
          </div>
          <span className="msg hint">{t("people.group_hint")}</span>
        </div>
      </div>
      <div className="row2 rounded-xl border border-line p-3">
        <label className="field"><span>{t("people.family")}</span>
          <select className="input" value={p.family ?? NO_FAMILY} onChange={(e) => setP({ ...p, family: e.target.value === NO_FAMILY ? null : e.target.value })}>
            <option value={NO_FAMILY}>{t("common.none_option")}</option>
            {families.map((f) => <option key={f}>{f}</option>)}
          </select>
        </label>
        <label className="field"><span>{t("people.new_family")}</span>
          <input className="input" placeholder={t("people.family_ph")} value={newFamily} onChange={(e) => setNewFamily(e.target.value)} />
        </label>
      </div>
      <div className="field"><span>{t("people.privileges")}</span>
        <div className="grid gap-x-4 gap-y-2 sm:grid-cols-2 lg:grid-cols-3">
          {PRIVILEGES.map((v) => (
            <label key={v} className="check"><input type="checkbox" checked={p.privileges.includes(v)}
              onChange={() => setP({ ...p, privileges: toggle(p.privileges, v) })} />{roleLabel(t, v)}</label>
          ))}
        </div>
      </div>
      {withActive ? (
        <label className="check"><input type="checkbox" checked={p.active ?? true} onChange={(e) => setP({ ...p, active: e.target.checked })} />
          {t("people.active")}</label>
      ) : null}
      <button className="btn primary w-fit">{button}</button>
    </form>
  );
}

export function People({ people, families, tab, selected, last, used, away }: {
  people: Person[]; families: string[]; tab: string; selected: number;
  last: Record<number, string>; used: Record<number, number>; away: Record<number, string[]>;
}) {
  const t = useTranslations("people");
  const c = useTranslations("common");
  const router = useRouter();
  const path = usePathname();
  const [busy, act] = useAct();
  const [addKey, setAddKey] = useState(0);
  const go = (k: string, id?: number) => router.replace(`${path}?tab=${k}${id ? `&id=${id}` : ""}`);
  const tabs: [string, string][] = [["add", t("tab_add")], ["edit", t("tab_edit")], ["list", t("tab_list")]];

  return (
    <>
      <nav className="tabs" aria-label={c("sections")}>
        {tabs.map(([k, l]) => <button key={k} type="button" aria-current={tab === k ? "page" : undefined} onClick={() => go(k)}>{l}</button>)}
      </nav>
      {tab === "add" ? (
        <div className="card">
          <PersonForm key={addKey} families={families} button={t("add")}
            initial={{ name: "", gender: "Brother", privileges: [], groups: [], family: null }}
            submit={(p) => act(() => addPerson(p), () => { setAddKey((k) => k + 1); router.refresh(); })} />
        </div>
      ) : tab === "edit" ? (
        people.length ? <Edit key={selected} people={people} families={families} id={selected} used={used} away={away}
          pick={(id) => go("edit", id)} busy={busy} act={act} /> : <Note>{t("none")}</Note>
      ) : <List people={people} last={last} />}
    </>
  );
}

function Edit({ people, families, id, used, away, pick, busy, act }: {
  people: Person[]; families: string[]; id: number; used: Record<number, number>; away: Record<number, string[]>;
  pick: (id: number) => void; busy: boolean; act: ReturnType<typeof useAct>[1];
}) {
  const t = useTranslations();
  const W = dateWords(t);
  const router = useRouter();
  const p = people.find((x) => x.id === id) ?? people[0];
  const [sus, setSus] = useState(suspendedNow(p));
  const [openEnded, setOpenEnded] = useState(!p.suspendedUntil);
  const [until, setUntil] = useState(p.suspendedUntil ?? addDays(today(), 90));
  const [clash, setClash] = useState<{ date: string; part: string }[]>([]);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [confirm, setConfirm] = useState(false);
  const refresh = () => router.refresh();

  useEffect(() => {
    if (!sus) { setClash([]); return; }
    let live = true;
    void upcomingFor(p.id, openEnded ? null : until).then((r) => { if (live) setClash(r); });
    return () => { live = false; };
  }, [sus, openEnded, until, p.id]);

  const status = suspendedNow(p) ? (p.suspendedUntil ? t("people.suspended_until", { date: fmtDate(p.suspendedUntil, W) }) : t("people.status_suspended")) : "";
  const awayDays = away[p.id] ?? [];
  return (
    <div className="stack">
      <label className="field max-w-md"><span>{t("people.participant")}</span>
        <select className="input" value={p.id} onChange={(e) => pick(Number(e.target.value))}>
          {people.map((x) => <option key={x.id} value={x.id}>{x.name}{x.active ? "" : ` ${t("people.inactive_suffix")}`}</option>)}
        </select>
      </label>
      <div className="card">
        <PersonForm key={p.id} families={families} button={t("people.save")} withActive
          initial={{ name: p.name, gender: p.gender || "Brother", privileges: p.privileges, groups: p.groups, family: p.family, active: p.active }}
          submit={(x) => act(() => updatePerson(p.id, x), refresh)} />
      </div>

      <details className="card" open={Boolean(status)} key={`s${p.id}`}>
        <summary>{t("people.suspension")}</summary>
        <div className="form">
          {status ? <Note tone="warn">{status}</Note> : null}
          <label className="check"><input type="checkbox" checked={sus} onChange={(e) => setSus(e.target.checked)} /> {t("people.suspended_box")}</label>
          {sus ? (
            <>
              <label className="check"><input type="checkbox" checked={openEnded} onChange={(e) => setOpenEnded(e.target.checked)} /> {t("people.no_end")}</label>
              {!openEnded ? <label className="field max-w-xs"><span>{t("people.suspended_until_label")}</span>
                <input className="input" type="date" value={until} onChange={(e) => setUntil(e.target.value)} /></label> : null}
              {clash.length ? <Note>{t("people.reassign")} {clash.map((c) => t("people.clash_line", { date: fmtDate(c.date, W), part: c.part })).join("; ")}</Note> : null}
            </>
          ) : null}
          <button type="button" className="btn w-fit" disabled={busy}
            onClick={() => act(() => setSuspension(p.id, sus, sus && !openEnded ? until : null), refresh)}>{t("people.save_suspension")}</button>
        </div>
      </details>

      <details className="card" key={`a${p.id}`}>
        <summary>{t("people.away")}</summary>
        <div className="form">
          {awayDays.length ? <div className="text-sm">{t("people.currently_away", { dates: awaySummary(awayDays, W) })}</div> : <div className="empty">{t("people.no_away")}</div>}
          <div className="row2">
            <label className="field"><span>{t("people.first_day")}</span><input className="input" type="date" value={start} onChange={(e) => setStart(e.target.value)} /></label>
            <label className="field"><span>{t("people.last_day")}</span><input className="input" type="date" value={end} min={start} onChange={(e) => setEnd(e.target.value)} /></label>
          </div>
          <div className="btns">
            <button type="button" className="btn" disabled={busy || !start}
              onClick={() => act(() => addAway(p.id, start, end || start), () => { setStart(""); setEnd(""); refresh(); })}>{t("people.add_period")}</button>
            {awayDays.length ? <button type="button" className="btn danger" disabled={busy} onClick={() => act(() => clearAway(p.id), refresh)}>{t("people.clear_all")}</button> : null}
          </div>
        </div>
      </details>

      <details className="card" key={`d${p.id}`}>
        <summary>{t("people.delete_title")}</summary>
        {used[p.id] ? (
          <Note>{t("people.in_use", { name: p.name, count: used[p.id] })}</Note>
        ) : <button type="button" className="btn danger" onClick={() => setConfirm(true)}>{t("people.delete")}</button>}
      </details>
      <Confirm open={confirm} busy={busy} onCancel={() => setConfirm(false)}
        message={t("people.delete_confirm", { name: p.name })}
        onConfirm={() => act(() => deletePerson(p.id), () => { setConfirm(false); router.replace("/participants?tab=list"); router.refresh(); })} />
    </div>
  );
}

function List({ people, last }: { people: Person[]; last: Record<number, string> }) {
  const t = useTranslations();
  const W = dateWords(t);
  const [show, setShow] = useState("Everyone");
  if (!people.length) return <Note>{t("people.none")}</Note>;
  const filters = ["Everyone", "Families", "Adults", ...GROUPS, "Suspended"];
  const filterLabel = (f: string) => ({ Everyone: t("people.filter_everyone"), Families: t("people.filter_families"),
    Adults: t("people.filter_adults"), Suspended: t("people.filter_suspended") } as Record<string, string>)[f] ?? groupLabel(t, f);
  let rows = people;
  if (show === "Families") rows = rows.filter((p) => p.family);
  else if (show === "Adults") rows = rows.filter((p) => !p.groups.length);
  else if (show === "Suspended") rows = rows.filter(suspendedNow);
  else if ((GROUPS as readonly string[]).includes(show)) rows = rows.filter((p) => p.groups.includes(show));
  const status = (p: Person) => (!p.active ? t("people.status_inactive") : suspendedNow(p)
    ? (p.suspendedUntil ? t("people.suspended_until", { date: fmtDate(p.suspendedUntil, W) }) : t("people.status_suspended")) : t("people.status_active"));
  const table = (list: Person[], family: boolean) => (
    <div className="table-wrap">
      <table className="table">
        <thead><tr><th>{t("people.col_name")}</th><th>{t("people.col_category")}</th><th>{t("people.col_group")}</th>{family ? <th>{t("people.col_family")}</th> : null}<th>{t("people.col_privileges")}</th><th>{t("people.col_last")}</th><th>{t("people.col_status")}</th></tr></thead>
        <tbody>
          {list.map((p) => (
            <tr key={p.id}>
              <td className="whitespace-nowrap"><a href={`/participants?tab=edit&id=${p.id}`}>{p.name}</a></td>
              <td>{categoryLabel(t, p.gender)}</td><td>{p.groups.map((g) => groupLabel(t, g)).join(", ") || t("people.adult")}</td>{family ? <td>{p.family ?? ""}</td> : null}
              <td className="text-xs">{p.privileges.map((v) => roleLabel(t, v)).join(", ")}</td><td className="whitespace-nowrap">{last[p.id] ? fmtDate(last[p.id], W) : ""}</td>
              <td className="whitespace-nowrap">{status(p)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
  const byFamily = new Map<string, Person[]>();
  if (show === "Families") for (const p of rows) byFamily.set(p.family!, [...(byFamily.get(p.family!) ?? []), p]);
  return (
    <div className="stack">
      <div className="flex flex-wrap gap-1.5">
        {filters.map((f) => <button key={f} type="button" className={`btn small ${show === f ? "primary" : ""}`} onClick={() => setShow(f)}>{filterLabel(f)}</button>)}
      </div>
      {!rows.length ? <Note>{t("people.empty_group")}</Note> : show === "Families" ? (
        [...byFamily.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([f, list]) => (
          <div key={f} className="card"><div className="mb-2 font-semibold">{t("people.members", { family: f, count: list.length })}</div>{table(list, false)}</div>
        ))
      ) : <div className="card"><div className="caption mt-0 mb-2">{t("people.count", { count: rows.length })}</div>{table(rows, true)}</div>}
    </div>
  );
}
