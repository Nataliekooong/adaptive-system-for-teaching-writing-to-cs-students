import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../../api";
import { countOverrides, fmtDate, mergeConfig } from "../../config";
import { ModuleConfigEditor, moduleIcon } from "../../components/ModuleConfigEditor";
import type { Assignment, Config, ConfigOverrides, Course, UserRef } from "../../types";
import {
  Board, Callout, Loading, Modal, PageHeader, Prop, Props, Switch, Tag, Topbar, useLoad, useToast, Views,
} from "../../ui";
import { useInstructor } from "./InstructorLayout";

interface StudentLink extends UserRef {
  override_config: ConfigOverrides;
  conditions: { id: number; name: string; experiment: string }[];
  effective: { on_demand: string | false; realtime: string | false; policy: string };
}
type Detail = Assignment & { config: ConfigOverrides; students: StudentLink[] };

interface SubRow {
  student: UserRef; submission_id: number | null; status: string; submitted_at: string | null; grade: string | null;
  released: boolean; words: number; feedback_count: number;
}

const TABS = [
  { key: "overview", label: "Overview", icon: "📄" },
  { key: "modules", label: "Modules", icon: "🧩" },
  { key: "students", label: "Students", icon: "👥" },
  { key: "submissions", label: "Submissions", icon: "📨" },
  { key: "effective", label: "Effective config", icon: "🔍" },
];

// I5 quick presets for "type of feedback each student receives"
const FEEDBACK_TYPES: Record<string, { label: string; cfg: ConfigOverrides }> = {
  inherit: { label: "Inherit", cfg: {} },
  slm: { label: "AI (SLM) feedback", cfg: { on_demand_feedback: { enabled: true, source: "slm" } } },
  fixed: { label: "Fixed prompts only", cfg: { on_demand_feedback: { enabled: true, source: "fixed_prompts" } } },
  none: { label: "No AI feedback", cfg: { on_demand_feedback: { enabled: false }, realtime_feedback: { enabled: false } } },
};

function feedbackTypeOf(cfg: ConfigOverrides): string {
  const j = JSON.stringify(cfg);
  return Object.entries(FEEDBACK_TYPES).find(([, v]) => JSON.stringify(v.cfg) === j)?.[0] ?? "custom";
}

export default function AssignmentPage() {
  const { aid } = useParams();
  const id = Number(aid);
  const nav = useNavigate();
  const toast = useToast();
  const { toggleSidebar, registry, reloadCourses } = useInstructor();
  const [confirming, setConfirming] = useState(false);
  const [tab, setTab] = useState("overview");
  const det = useLoad(() => api.get<Detail>(`/api/instructor/assignments/${id}`), [id]);
  const course = useLoad(
    () => (det.data ? api.get<Course>(`/api/instructor/courses/${det.data.course_id}`) : Promise.resolve(undefined)),
    [det.data?.course_id],
  );
  const [form, setForm] = useState<Detail | null>(null);
  useEffect(() => { if (det.data) setForm(det.data); }, [det.data]);

  if (!det.data || !form || !course.data) {
    return <><Topbar onToggleSidebar={toggleSidebar} crumbs={[{ label: "…" }]} /><Loading error={det.error} /></>;
  }
  const a = det.data;
  const c = course.data;
  const inherited = mergeConfig(registry.defaults, c.config);
  const dirty = JSON.stringify({ ...form, students: 0 }) !== JSON.stringify({ ...a, students: 0 });

  const save = async () => {
    try {
      await api.patch(`/api/instructor/assignments/${id}`, {
        title: form.title, description: form.description, instructions: form.instructions,
        genre_guidance: form.genre_guidance, due_date: form.due_date, rubric_areas: form.rubric_areas,
        get_started_content: form.get_started_content, config: form.config, published: form.published,
      });
      toast("Saved");
      det.reload();
    } catch (e) {
      toast((e as Error).message, true);
    }
  };

  const remove = async () => {
    try {
      await api.del(`/api/instructor/assignments/${id}`);
      reloadCourses();
      nav(`/i/courses/${c.id}/assignments`);
    } catch (e) {
      toast((e as Error).message, true);
    }
  };

  const saveBar = (
    <div className="row" style={{ position: "sticky", top: 0, background: "#fff", padding: "8px 0", zIndex: 2 }}>
      <span className="spacer" />
      {dirty && <button className="btn" onClick={() => setForm(a)}>Discard</button>}
      <button className="btn primary" disabled={!dirty} onClick={save}>Save</button>
    </div>
  );

  return (
    <>
      <Topbar
        onToggleSidebar={toggleSidebar}
        crumbs={[
          { label: c.code, icon: "🎓", to: `/i/courses/${c.id}` },
          { label: "Assignments", icon: "📝", to: `/i/courses/${c.id}/assignments` },
          { label: a.title },
        ]}
        right={<button className="btn danger" onClick={() => setConfirming(true)}>Delete</button>}
      />
      <div className="content">
        <div className="page wide">
          <PageHeader icon="📝" title={<input className="page-title-input" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />} />
          <Props>
            <Prop icon="📅" label="Due" editable>
              <input
                className="input ghost" type="datetime-local" style={{ width: 230 }}
                value={form.due_date ? new Date(form.due_date).toISOString().slice(0, 16) : ""}
                onChange={(e) => setForm({ ...form, due_date: e.target.value ? new Date(e.target.value + "Z").toISOString() : null })}
              />
            </Prop>
            <Prop icon="👁" label="Visible to students"><Switch on={form.published} onChange={(v) => setForm({ ...form, published: v })} /></Prop>
            <Prop icon="🎯" label="Feedback priority areas">
              {c.rubric_areas.map((r) => {
                const on = form.rubric_areas.includes(r);
                return (
                  <span key={r} style={{ cursor: "pointer", opacity: on ? 1 : 0.45 }}
                        onClick={() => setForm({ ...form, rubric_areas: on ? form.rubric_areas.filter((x) => x !== r) : [...form.rubric_areas, r] })}>
                    <Tag color={on ? "purple" : "gray"}>{on ? "✓ " : ""}{r}</Tag>
                  </span>
                );
              })}
            </Prop>
            <Prop icon="🧩" label="Module overrides">
              {countOverrides(form.config) ? Object.keys(form.config).map((m) => <Tag key={m} color="blue">{moduleIcon(m)} {registry.modules.find((x) => x.key === m)?.label}</Tag>) : <span className="faint">Inherits course defaults</span>}
            </Prop>
          </Props>
          <Views tabs={TABS.map((t) => t.key === "students" ? { ...t, count: a.students.length } : t)} active={tab} onChange={setTab} />

          {tab === "overview" && (
            <>
              {saveBar}
              <div className="field"><label>Description</label><input className="input" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></div>
              <div className="field"><label>Instructions</label><textarea className="textarea" rows={5} value={form.instructions} onChange={(e) => setForm({ ...form, instructions: e.target.value })} /></div>
              <div className="field"><label>Genre guidance / example</label><textarea className="textarea" rows={4} value={form.genre_guidance} onChange={(e) => setForm({ ...form, genre_guidance: e.target.value })} /></div>
              <div className="field"><label>🚀 “Get Started” outline & guiding questions (S10 — never a finished response)</label><textarea className="textarea" rows={7} value={form.get_started_content} onChange={(e) => setForm({ ...form, get_started_content: e.target.value })} /></div>
            </>
          )}

          {tab === "modules" && (
            <>
              <Callout icon="🧩" color="blue">
                Overrides for <b>this assignment only</b>. Anything left on “Inherit” follows the course defaults.
                Experiments and per-student overrides can still change these for specific students.
              </Callout>
              {saveBar}
              <ModuleConfigEditor registry={registry} value={form.config} inherited={inherited}
                                  onChange={(v) => setForm({ ...form, config: v })} inheritLabel="course" />
            </>
          )}

          {tab === "students" && <StudentsPanel a={a} course={c} inherited={mergeConfig(inherited, a.config)} onSaved={det.reload} />}
          {tab === "submissions" && <SubmissionsPanel aid={a.id} onOpen={(sid) => nav(`/i/assignments/${a.id}/students/${sid}`)} />}
          {tab === "effective" && <EffectivePanel a={a} />}
        </div>
      </div>
      {confirming && (
        <Modal onClose={() => setConfirming(false)}>
          <h2 style={{ marginTop: 0 }}>Delete {a.title}?</h2>
          <p className="muted">This removes the assignment and its drafts, submissions, feedback and assignment-scoped experiments. Research logs stay.</p>
          <div className="row">
            <span className="spacer" />
            <button className="btn" onClick={() => setConfirming(false)}>Cancel</button>
            <button className="btn danger" onClick={remove}>Delete</button>
          </div>
        </Modal>
      )}
    </>
  );
}

function StudentsPanel({ a, course, inherited, onSaved }: { a: Detail; course: Course; inherited: Config; onSaved: () => void }) {
  const { registry } = useInstructor();
  const toast = useToast();
  const enrolled = useLoad(() => api.get<UserRef[]>(`/api/instructor/courses/${course.id}/students`), [course.id]);
  const [links, setLinks] = useState<Record<number, ConfigOverrides>>(
    Object.fromEntries(a.students.map((s) => [s.id, s.override_config])),
  );
  const [editing, setEditing] = useState<number | null>(null);
  const dirty = JSON.stringify(links) !== JSON.stringify(Object.fromEntries(a.students.map((s) => [s.id, s.override_config])));

  const save = async () => {
    try {
      await api.put(`/api/instructor/assignments/${a.id}/students`,
        Object.entries(links).map(([sid, cfg]) => ({ student_id: Number(sid), override_config: cfg })));
      toast("Students saved");
      onSaved();
    } catch (e) {
      toast((e as Error).message, true);
    }
  };

  if (!enrolled.data) return <Loading />;
  const info = Object.fromEntries(a.students.map((s) => [s.id, s]));
  return (
    <>
      <Callout icon="👥">
        Choose who gets this assignment (I3) and, if needed, the type of feedback each student receives (I5).
        Per-student settings are the most specific layer — they win over experiment conditions, so the A/B page flags them.
      </Callout>
      <div className="row" style={{ position: "sticky", top: 0, background: "#fff", padding: "8px 0", zIndex: 2 }}>
        <span className="muted">{Object.keys(links).length} of {enrolled.data.length} assigned</span><span className="spacer" />
        {dirty && <button className="btn" onClick={() => setLinks(Object.fromEntries(a.students.map((s) => [s.id, s.override_config])))}>Discard</button>}
        <button className="btn primary" disabled={!dirty} onClick={save}>Save</button>
      </div>
      <table className="table">
        <thead><tr><th>Assigned</th><th>Aa Student</th><th>🧪 Conditions</th><th>💬 Feedback type</th><th>Effective</th><th /></tr></thead>
        <tbody>
          {enrolled.data.map((u) => {
            const assigned = u.id in links;
            const s = info[u.id];
            const type = assigned ? feedbackTypeOf(links[u.id]) : "inherit";
            return (
              <tr key={u.id}>
                <td><input type="checkbox" checked={assigned} onChange={(e) => {
                  const n = { ...links }; if (e.target.checked) n[u.id] = {}; else delete n[u.id]; setLinks(n);
                }} /></td>
                <td style={{ fontWeight: 500 }}>{u.display_name} <span className="faint small">{u.username}</span></td>
                <td>{s?.conditions.length ? s.conditions.map((c) => <Tag key={c.id} color="purple">{c.name}</Tag>) : <span className="faint">—</span>}</td>
                <td>
                  {assigned && (
                    <select className="select" style={{ width: 190 }} value={type}
                            onChange={(e) => setLinks({ ...links, [u.id]: FEEDBACK_TYPES[e.target.value]?.cfg ?? links[u.id] })}>
                      {Object.entries(FEEDBACK_TYPES).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
                      {type === "custom" && <option value="custom">Custom ({countOverrides(links[u.id])} overrides)</option>}
                    </select>
                  )}
                </td>
                <td className="small">
                  {s && (
                    <div className="row wrap" style={{ gap: 4 }}>
                      <Tag color={s.effective.on_demand ? "green" : "gray"}>💬 {s.effective.on_demand || "off"}</Tag>
                      <Tag color={s.effective.realtime ? "green" : "gray"}>⚡ {s.effective.realtime || "off"}</Tag>
                    </div>
                  )}
                </td>
                <td>{assigned && <button className="btn sm" onClick={() => setEditing(u.id)}>All settings</button>}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {editing !== null && (
        <Modal wide onClose={() => setEditing(null)}>
          <h2 style={{ marginTop: 0 }}>Per-student overrides · {enrolled.data.find((u) => u.id === editing)?.display_name}</h2>
          <ModuleConfigEditor registry={registry} value={links[editing] ?? {}} inherited={inherited}
                              onChange={(v) => setLinks({ ...links, [editing]: v })} inheritLabel="assignment" />
          <div className="row" style={{ marginTop: 12 }}><span className="spacer" /><button className="btn primary" onClick={() => setEditing(null)}>Done</button></div>
        </Modal>
      )}
    </>
  );
}

function SubmissionsPanel({ aid, onOpen }: { aid: number; onOpen: (sid: number) => void }) {
  const toast = useToast();
  const rows = useLoad(() => api.get<SubRow[]>(`/api/instructor/assignments/${aid}/submissions`), [aid]);
  if (!rows.data) return <Loading error={rows.error} />;
  const releasable = rows.data.filter((r) => r.submission_id && r.grade && !r.released);
  const release = async () => {
    const r = await api.post<{ updated: number }>(`/api/instructor/assignments/${aid}/release`, {
      submission_ids: releasable.map((x) => x.submission_id),
    });
    toast(`Released ${r.updated} grade${r.updated === 1 ? "" : "s"}`);
    rows.reload();
  };
  const by = (s: string) => rows.data!.filter((r) => r.status === s);
  return (
    <>
      <div className="row" style={{ marginBottom: 8 }}>
        <span className="muted">Unreleased grades stay hidden from students (I11).</span><span className="spacer" />
        <button className="btn primary" disabled={!releasable.length} onClick={release}>Release {releasable.length} grade{releasable.length === 1 ? "" : "s"}</button>
      </div>
      <Board
        columns={[
          { key: "ns", label: "Not started", color: "gray", items: by("not started") },
          { key: "ip", label: "In progress", color: "yellow", items: by("in progress") },
          { key: "sub", label: "Submitted", color: "blue", items: by("submitted") },
          { key: "gr", label: "Graded", color: "green", items: by("graded") },
        ]}
        renderCard={(r) => (
          <div key={r.student.id} className="card" onClick={() => onOpen(r.student.id)}>
            <div className="card-title">{r.student.display_name}</div>
            <div className="card-meta">
              <span>{r.words} words</span><span>· {r.feedback_count} feedback</span>
              {r.grade && <Tag color={r.released ? "green" : "yellow"}>{r.grade}{r.released ? "" : " · unreleased"}</Tag>}
              {r.submitted_at && <span>· {fmtDate(r.submitted_at)}</span>}
            </div>
          </div>
        )}
      />
    </>
  );
}

function EffectivePanel({ a }: { a: Detail }) {
  const { registry } = useInstructor();
  const [sid, setSid] = useState<number | "">(a.students[0]?.id ?? "");
  const eff = useLoad(
    () => api.get<{ config: Config; provenance: Record<string, Record<string, string>>; conditions: { name: string; experiment: string }[] }>(
      `/api/instructor/assignments/${a.id}/effective-config${sid ? `?student_id=${sid}` : ""}`),
    [a.id, sid],
  );
  const layerColor = (p: string) =>
    p === "system" ? "gray" : p === "course" ? "brown" : p === "assignment" ? "blue" : p.startsWith("experiment") ? "purple" : p.startsWith("dependency") ? "orange" : "pink";
  return (
    <>
      <Callout icon="🔍">
        What a specific student actually gets, and which layer decided each value. Use this to sanity-check an A/B setup.
      </Callout>
      <div className="row" style={{ margin: "8px 0 12px" }}>
        <span className="muted">Student</span>
        <select className="select" style={{ width: 240 }} value={sid} onChange={(e) => setSid(e.target.value ? Number(e.target.value) : "")}>
          <option value="">(no student — base config)</option>
          {a.students.map((s) => <option key={s.id} value={s.id}>{s.display_name}</option>)}
        </select>
        {eff.data?.conditions.map((c) => <Tag key={c.name} color="purple">🧪 {c.experiment} → {c.name}</Tag>)}
      </div>
      {!eff.data ? <Loading error={eff.error} /> : (
        <table className="table">
          <thead><tr><th>Module</th><th>Setting</th><th>Value</th><th>Decided by</th></tr></thead>
          <tbody>
            {registry.modules.flatMap((m) =>
              ["enabled", ...m.settings.map((s) => s.key)].map((k, i) => {
                const v = eff.data!.config[m.key][k];
                const p = eff.data!.provenance[m.key][k];
                return (
                  <tr key={m.key + k}>
                    <td>{i === 0 ? <b>{moduleIcon(m.key)} {m.label}</b> : ""}</td>
                    <td className="muted">{k === "enabled" ? "Enabled" : m.settings.find((s) => s.key === k)?.label}</td>
                    <td>{typeof v === "boolean" ? <Tag color={v ? "green" : "gray"}>{v ? "on" : "off"}</Tag> : Array.isArray(v) ? (v.length ? v.join(", ") : "all") : String(v)}</td>
                    <td><Tag color={layerColor(p) as "gray"}>{p}</Tag></td>
                  </tr>
                );
              }),
            )}
          </tbody>
        </table>
      )}
      <div className="row wrap faint small" style={{ marginTop: 8, gap: 4 }}>
        Layers, lowest to highest: <Tag color="gray">system</Tag><Tag color="brown">course</Tag><Tag color="blue">assignment</Tag>
        <Tag color="purple">experiment</Tag><Tag color="pink">student override</Tag>
      </div>
    </>
  );
}
