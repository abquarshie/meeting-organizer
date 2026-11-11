"use client";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Icon } from "@/components/icons";
import { py } from "@/components/py";
import { Confirm } from "@/components/Sheet";
import { Bar, Note } from "@/components/ui";
import { useAct } from "@/components/useAct";
import { CATEGORIES, MIDWEEK, SECTION_COLORS } from "@/lib/constants";
import { dateWords } from "@/lib/dateWords";
import { fmtDate } from "@/lib/dates";
import { categoryLabel, sectionLabel } from "@/lib/labels";

type Slot = {
  hall: string; part_no: number | null; title: string; role: string; section: string;
  minutes: number | null; student_part: boolean; needs_assistant: boolean;
};
type Pick = { sid: number | null; aid: number | null };
type Issue = { level: "error" | "warning"; slots: number[]; text: string };
type Meta = Record<"heading" | "book" | "opening_song" | "middle_song" | "closing_song" | "aux_group", string>;
type PersonInfo = { name: string; gender: string; family: string | null; active: boolean };
type EditorData = {
  weekLabel: string; relative: string; event: string | null; eventOther?: string;
  saved: boolean; slots: Slot[]; slotLabels: string[]; picks: Pick[]; meta: Meta; aux: boolean;
  workbook: null | {
    weeks: { label: string; dates: string }[]; matched: string | null; differs: boolean; use: boolean;
    week: string | null; savedCount: number; workbookCount: number;
    parts: { "No.": number | null; Title: string; Min: number | string; Section: string }[]; gaps: number[]; text: string;
  };
  people: Record<string, PersonInfo>;
  options: { ids: number[]; labels: Record<string, string>; eligible: number[]; mixed: boolean }[];
  assistantOrder: number[]; assistantLabels: Record<string, string>; unavailable: string[];
  snapshot: { note: string; reason: string } | null; issues: Issue[];
  activeCount: number;
};
type Choices = { aux?: boolean; useWorkbook?: boolean; week?: string | null };

const slotKey = (s: Slot) => `${s.hall}|${s.role}|${s.part_no ?? s.title.toLowerCase()}`;

function sameFamily(people: Record<string, PersonInfo>, a: number | null, b: number | null) {
  if (a === null || b === null) return false;
  const fa = people[a]?.family;
  return Boolean(fa) && fa === people[b]?.family;
}

export function Editor({ date, mode, saved }: {
  date: string; mode: "new" | "edit"; saved: { date: string; type: string }[];
}) {
  const type = MIDWEEK;
  const t = useTranslations();
  const W = dateWords(t);
  const router = useRouter();
  const [busy, act] = useAct();
  const [data, setData] = useState<EditorData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [picks, setPicks] = useState<Pick[]>([]);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [issues, setIssues] = useState<Issue[]>([]);
  const [categories, setCategories] = useState<Record<number, string>>({});
  const [confirm, setConfirm] = useState<null | "undo" | "delete">(null);
  const [choices, setChoices] = useState<Choices>({});
  const touched = useRef(false); // picks changed since the last load: carry them over when the parts list changes

  const go = (d: string, m = mode) => {
    const q = new URLSearchParams({ date: d, type });
    if (m === "edit") q.set("mode", "edit");
    router.replace(`/schedule?${q.toString()}`);
  };

  const load = useCallback(async (next: Choices, carry?: { slots: Slot[]; picks: Pick[] }) => {
    const r = await py<EditorData>("editor", { date, type, ...next });
    if (!r.ok) { setError(r.error); return; }
    setError(null);
    let p = r.picks;
    if (carry) {
      const old = new Map(carry.slots.map((s, i) => [slotKey(s), carry.picks[i]]));
      p = r.slots.map((s, i) => old.get(slotKey(s)) ?? r.picks[i]);
    }
    setData(r);
    setPicks(p);
    setMeta((m) => (carry && m ? { ...r.meta, ...m } : r.meta));
    setIssues(r.issues);
  }, [date, type]);

  useEffect(() => { void load({}); }, [load]);

  const change = (next: Choices) => {
    const merged = { ...choices, ...next };
    setChoices(merged);
    void load(merged, data && touched.current ? { slots: data.slots, picks } : undefined);
  };

  // the checks, re-run shortly after every change so a clash shows the moment it is made
  const checkSeq = useRef(0);
  useEffect(() => {
    if (!data || data.event || !touched.current) return;
    const seq = ++checkSeq.current;
    const timer = setTimeout(async () => {
      const r = await py<{ issues: Issue[] }>("check", { date, type, slots: data.slots, picks });
      if (r.ok && seq === checkSeq.current) setIssues(r.issues);
    }, 350);
    return () => clearTimeout(timer);
  }, [picks, data, date, type]);

  const setPick = (i: number, patch: Partial<Pick>) => {
    touched.current = true;
    setPicks((ps) => ps.map((p, j) => (j === i ? { ...p, ...patch } : p)));
  };

  const issuesAt = useMemo(() => {
    const m = new Map<number, Issue[]>();
    for (const x of issues) for (const i of x.slots) m.set(i, [...(m.get(i) ?? []), x]);
    return m;
  }, [issues]);

  const header = (
    <div className="card mb-4 grid gap-3">
      <div className="seg w-fit" role="group" aria-label={t("sched.mode")}>
        <button type="button" aria-pressed={mode === "new"} onClick={() => go(date, "new")}>{t("sched.create_new")}</button>
        <button type="button" aria-pressed={mode === "edit"} onClick={() => go(saved[0]?.date ?? date, "edit")}>{t("sched.edit_saved")}</button>
      </div>
      {mode === "edit" ? (
        saved.length ? (
          <label className="field"><span>{t("sched.saved_schedule")}</span>
            <select className="input" value={date} onChange={(e) => go(e.target.value)}>
              {!saved.some((m) => m.date === date) ? <option value={date}>{fmtDate(date, W)}</option> : null}
              {saved.map((m) => <option key={m.date} value={m.date}>{fmtDate(m.date, W)}</option>)}
            </select>
          </label>
        ) : <Note>{t("sched.no_saved")}</Note>
      ) : (
        <label className="field max-w-xs"><span>{t("sched.meeting_date")}</span>
          <input className="input" type="date" value={date} onChange={(e) => e.target.value && go(e.target.value)} />
        </label>
      )}
      {data ? (
        <div className="text-sm text-muted">
          <b className="text-ink">{data.weekLabel}</b>{data.relative ? ` · ${data.relative}` : ""}
        </div>
      ) : null}
    </div>
  );

  if (error) return <>{header}<Note tone="error">{error}</Note></>;
  if (!data || !meta) return <>{header}<div className="empty">{t("common.loading")}</div></>;
  if (data.event) {
    return (
      <>
        {header}
        <div className="card">
          <h2 className="mt-0 text-lg font-bold">{data.event}</h2>
          {data.eventOther ? <div className="text-sm text-muted">{t("sched.in_other_language", { language: t("lang.dangme") })} {data.eventOther}</div> : null}
          <p>{t("sched.event_week")}</p>
          <div className="caption">{t("sched.event_undo")}</div>
        </div>
      </>
    );
  }
  if (data.activeCount === 0) return <>{header}<Note tone="warn">{t("sched.no_people")}</Note></>;

  const { slots, people, options } = data;

  // progress: a part plus its assistant where one is needed (utils.fill_progress)
  let needed = 0, filled = 0;
  slots.forEach((s, i) => {
    const p = picks[i];
    needed += 1 + (s.needs_assistant ? 1 : 0);
    filled += (p.sid !== null ? 1 : 0) + (s.needs_assistant && p.aid !== null ? 1 : 0);
  });
  const errors = issues.filter((x) => x.level === "error");
  const warnings = issues.filter((x) => x.level === "warning");

  const suggest = () => act(async () => {
    const r = await py<{ picks: Record<string, [number | null, number | null]> }>("suggest", { date, type, slots, picks });
    if (!r.ok) return r;
    touched.current = true;
    setPicks((ps) => ps.map((p, i) => {
      const s = r.picks[String(i)];
      if (!s || p.sid !== null) return p;
      return { ...p, sid: s[0], aid: slots[i].needs_assistant ? s[1] : null };
    }));
    return { ok: true, message: t("sched.suggested") };
  });

  const save = () => act(async () => {
    const r = await py("save", { date, type, slots, picks, aux: data.aux, meta });
    if (r.ok) {
      touched.current = false;
      setChoices({});
      await load({});
      router.refresh();
    }
    return r;
  });

  const doConfirm = () => act(async () => {
    const r = await py(confirm === "undo" ? "undo" : "delete", { date, type });
    setConfirm(null);
    if (r.ok) {
      touched.current = false;
      setChoices({});
      await load({});
      router.refresh();
    }
    return r;
  });

  const renderSlot = (i: number) => {
    const s = slots[i], p = picks[i], opt = options[i];
    const label = data.slotLabels[i];
    const notes = (issuesAt.get(i) ?? []).map((x, k) => <div key={k} className={`slot-issue ${x.level}`}>⚠ {x.text}</div>);
    return (
      <div className="slot" key={i}>
        {s.needs_assistant ? (
          <div className="grid gap-x-3 sm:grid-cols-2">
            <div className="slot-title">{label}</div>
            <div className="slot-title max-sm:hidden">{t("sched.assistant")}</div>
          </div>
        ) : <div className="slot-title">{label}</div>}
        {personSelect(i, s, p, opt)}
        {notes}
      </div>
    );
  };

  function personSelect(i: number, s: Slot, p: Pick, opt: EditorData["options"][number]) {
    let ids = opt.ids;
    let category: string | null = null;
    if (opt.mixed) {
      category = categories[i] ?? (p.sid !== null ? people[p.sid]?.gender : null) ?? CATEGORIES[1];
      ids = ids.filter((id) => people[id]?.gender === category || id === p.sid);
    }
    const gone = p.sid !== null && !opt.eligible.includes(p.sid);
    const main = (
      <div className="grid gap-1.5">
        {opt.mixed ? (
          <div className="seg w-fit" role="group" aria-label={t("sched.category")}>
            {CATEGORIES.map((c) => (
              <button key={c} type="button" aria-pressed={category === c}
                onClick={() => setCategories((x) => ({ ...x, [i]: c }))}>{categoryLabel(t, c)}</button>
            ))}
          </div>
        ) : null}
        <select className="input" aria-label={data!.slotLabels[i]} value={p.sid ?? ""}
          onChange={(e) => setPick(i, { sid: e.target.value ? Number(e.target.value) : null })}>
          <option value="">{t("common.unassigned")}</option>
          {ids.map((id) => <option key={id} value={id}>{opt.labels[id] ?? people[id]?.name}</option>)}
        </select>
        {gone ? <div className="msg hint">{t("sched.gone", { name: people[p.sid!]?.name ?? t("sched.this_person") })}</div> : null}
      </div>
    );
    if (!s.needs_assistant) return main;
    // the assistant: same category or family as the student (a parent can assist their child), family first
    let pool = data!.assistantOrder.filter((id) => id !== p.sid && (p.sid === null
      || people[id]?.gender === people[p.sid]?.gender || sameFamily(people, id, p.sid)));
    if (p.aid !== null && !pool.includes(p.aid)) pool = [...pool, p.aid];
    pool = [...pool].sort((a, b) => Number(!sameFamily(people, a, p.sid)) - Number(!sameFamily(people, b, p.sid)));
    return (
      <div className="grid gap-x-3 gap-y-1.5 sm:grid-cols-2">
        {main}
        <div className="grid gap-1.5 self-end">
          <span className="slot-title sm:hidden">{t("sched.assistant")}</span>
          <select className="input" aria-label={t("sched.assistant_for", { part: data!.slotLabels[i] })} value={p.aid ?? ""}
            onChange={(e) => setPick(i, { aid: e.target.value ? Number(e.target.value) : null })}>
            <option value="">{t("common.unassigned")}</option>
            {pool.map((id) => <option key={id} value={id}>{data!.assistantLabels[id] ?? people[id]?.name}</option>)}
          </select>
        </div>
      </div>
    );
  }

  // one block per workbook section; single parts sit two to a row
  const groups: { section: string; items: number[] }[] = [];
  slots.forEach((s, i) => {
    if (!groups.length || groups[groups.length - 1].section !== s.section) groups.push({ section: s.section, items: [] });
    groups[groups.length - 1].items.push(i);
  });
  const wide = (s: Slot) => s.needs_assistant;

  const wbk = data.workbook;
  return (
    <>
      {header}
      <div className="stack">
        {mode === "new" && data.saved ? <Note>{t("sched.already_saved")}</Note> : null}

        <div className="card grid gap-3">
            {wbk ? (
              <>
                {!wbk.matched ? <Note tone="warn">{t("sched.no_workbook_week", { date: fmtDate(date, W) })}</Note> : null}
                {wbk.differs ? <Note tone="warn">{t("sched.workbook_differs", { saved: wbk.savedCount, week: wbk.matched ?? "", count: wbk.workbookCount })}</Note> : null}
                <label className="check">
                  <input type="checkbox" checked={wbk.use} onChange={(e) => change({ useWorkbook: e.target.checked })} />
                  {t("sched.use_workbook")}
                </label>
                {wbk.use ? (
                  <label className="field"><span>{t("sched.workbook_week")}</span>
                    <select className="input" value={wbk.week ?? ""} onChange={(e) => change({ week: e.target.value || null })}>
                      {!wbk.week ? <option value="">{t("sched.choose_week")}</option> : null}
                      {wbk.weeks.map((w) => <option key={w.label} value={w.label}>{w.label} · {w.dates}</option>)}
                    </select>
                  </label>
                ) : null}
                {wbk.week ? (
                  <details className="rounded-xl border border-line px-3 py-2" open={wbk.differs}>
                    <summary className="cursor-pointer text-sm font-semibold">{t("sched.cross_check", { week: wbk.week, count: wbk.parts.length })}</summary>
                    {wbk.gaps.length ? <Note tone="error">{t("sched.gaps", { numbers: wbk.gaps.join(", ") })}</Note> : null}
                    <div className="table-wrap mt-2">
                      <table className="table">
                        <thead><tr><th>{t("sched.col_no")}</th><th>{t("sched.col_title")}</th><th>{t("sched.col_min")}</th><th>{t("sched.col_section")}</th></tr></thead>
                        <tbody>{wbk.parts.map((r, k) => <tr key={k}><td>{r["No."]}</td><td>{r.Title}</td><td>{r.Min}</td><td>{sectionLabel(t, r.Section)}</td></tr>)}</tbody>
                      </table>
                    </div>
                    {wbk.text ? <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap rounded-lg bg-subtle p-2 text-xs">{wbk.text}</pre> : null}
                  </details>
                ) : null}
              </>
            ) : <div className="caption mt-0">{t("sched.standard_list")}</div>}
            <label className="check">
              <input type="checkbox" checked={data.aux} onChange={(e) => change({ aux: e.target.checked })} />
              {t("sched.aux")}
            </label>
            {data.aux ? (
              <label className="field max-w-xs"><span>{t("sched.aux_group")}</span>
                <input className="input" placeholder={t("month.group_ph")} value={meta.aux_group} onChange={(e) => setMeta({ ...meta, aux_group: e.target.value })} />
              </label>
            ) : null}
          </div>

        <div className="flex flex-wrap items-center justify-between gap-2">
          {data.unavailable.length ? (
            <details className="text-sm">
              <summary className="cursor-pointer font-semibold text-muted">{t("sched.unavailable", { count: data.unavailable.length })}</summary>
              <div className="mt-1">{data.unavailable.join(", ")}</div>
              <div className="caption">{t("sched.unavailable_hint")}</div>
            </details>
          ) : <span />}
          <button type="button" className="btn" onClick={suggest} disabled={busy}
            title={t("sched.suggest_hint")}>
            <Icon name="sparkle" /> {t("sched.suggest")}
          </button>
        </div>

        <details className="card">
          <summary>{t("sched.details")}</summary>
          <div className="row2">
            {([["heading", "sched.heading"], ["book", "sched.bible_reading"], ["opening_song", "sched.opening_song"],
              ["middle_song", "sched.middle_song"], ["closing_song", "sched.closing_song"]] as const).map(([k, l]) => (
              <label key={k} className="field"><span>{t(l)}</span>
                <input className="input" value={meta[k]} onChange={(e) => setMeta({ ...meta, [k]: e.target.value })} />
              </label>
            ))}
          </div>
        </details>

        {groups.map((g, gi) => {
          const rows: number[][] = [];
          let pending: number[] | null = null;
          for (const i of g.items) {
            if (wide(slots[i])) { pending = null; rows.push([i]); continue; }
            if (pending) { pending.push(i); pending = null; } else { pending = [i]; rows.push(pending); }
          }
          return (
            <section key={gi}>
              <div className="section-head"><span className="swatch" style={{ background: SECTION_COLORS[g.section] ?? "#8A94A0" }} />{sectionLabel(t, g.section)}</div>
              <div className="card grid gap-4">
                {rows.map((r, k) => (
                  <div key={k} className={r.length > 1 ? "grid gap-4 sm:grid-cols-2" : "grid"}>{r.map(renderSlot)}</div>
                ))}
              </div>
            </section>
          );
        })}

        {issues.length ? (
          <div className="card grid gap-2">
            <div className="font-semibold">{t("sched.checks", { count: issues.length })}</div>
            {errors.map((x, k) => <Note key={`e${k}`} tone="error">{x.text}</Note>)}
            {warnings.map((x, k) => <Note key={`w${k}`} tone="warn">{x.text}</Note>)}
            {errors.length ? <div className="caption mt-0">{t("sched.blocked")}</div> : null}
          </div>
        ) : null}

        <div className="card savebar">
          <div className="min-w-48 flex-1">
            <div className="mb-1 text-sm font-semibold">{needed - filled ? t("sched.progress", { filled, needed, open: needed - filled }) : t("sched.all_filled", { count: needed })}</div>
            <Bar pct={needed ? (100 * filled) / needed : 100} label={t("common.filled")} />
          </div>
          <div className="btns max-sm:w-full max-sm:flex-nowrap">
            <button type="button" className="btn primary max-sm:flex-1" onClick={save} disabled={busy || errors.length > 0}><Icon name="save" /> {t("sched.save")}</button>
            {data.snapshot ? <button type="button" className="btn" onClick={() => setConfirm("undo")} disabled={busy}><Icon name="undo" /><span className="max-sm:sr-only">{t("common.undo")}</span></button> : null}
            {data.saved ? <button type="button" className="btn danger" onClick={() => setConfirm("delete")} disabled={busy}><Icon name="trash" /><span className="max-sm:sr-only">{t("common.delete")}</span></button> : null}
          </div>
        </div>
      </div>
      <Confirm open={confirm !== null} busy={busy} onCancel={() => setConfirm(null)} onConfirm={doConfirm}
        button={confirm === "undo" ? t("common.undo") : t("common.delete")}
        message={confirm === "undo"
          ? t("sched.undo_confirm", { what: data.snapshot?.note ?? "", meeting: t("mt.midweek_lower"), date: fmtDate(date, W) })
          : t("sched.delete_confirm", { meeting: t("mt.midweek_lower"), date: fmtDate(date, W) })} />
    </>
  );
}
