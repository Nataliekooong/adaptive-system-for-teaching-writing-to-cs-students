import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../../api";
import { fmtDate, mergeConfig } from "../../config";
import { ModuleConfigEditor, OverrideSummary } from "../../components/ModuleConfigEditor";
import type { Assignment, Condition, ConfigOverrides, Course, Experiment, UserRef } from "../../types";
import {
  Callout, Loading, Modal, PageHeader, Prop, Props, STATUS_COLORS, Tag, Topbar, useLoad, useToast, Views,
} from "../../ui";
import { useInstructor } from "./InstructorLayout";

type Participant = UserRef & { condition_id: number | null; assigned_by: string | null; has_override: boolean };

interface Result {
  condition_id: number; name: string; students: number; on_demand_requests: number; realtime_popups: number;
  dismissed: number; helpful_rate: number | null; mean_instructor_rating: number | null; mean_reward: number | null;
  final_rewards: number; submissions: number; mean_words: number | null; mean_grade: number | null;
}

const COND_COLORS = ["blue", "orange", "green", "purple", "pink", "yellow"] as const;

// One-click templates for the venues described in the study design.
const TEMPLATES: { name: string; hypothesis: string; conditions: Condition[] }[] = [
  {
    name: "On-demand vs real-time feedback",
    hypothesis: "Real-time nudges lead to more revisions than on-demand feedback alone.",
    conditions: [
      { name: "A · On-demand", description: "", weight: 1, config: { on_demand_feedback: { enabled: true }, realtime_feedback: { enabled: false } } },
      { name: "B · Real-time", description: "", weight: 1, config: { on_demand_feedback: { enabled: false }, realtime_feedback: { enabled: true } } },
    ],
  },
  {
    name: "Pop-up presentation: popup vs window vs highlight",
    hypothesis: "Less intrusive real-time presentations are dismissed less often.",
    conditions: ["popup", "window", "highlight"].map((p, i) => ({
      name: `${"ABC"[i]} · ${p}`, description: "", weight: 1, config: { realtime_feedback: { enabled: true, presentation: p } },
    })),
  },
  {
    name: "Bandit vs random vs fixed style",
    hypothesis: "Thompson Sampling beats random and the best fixed style on feedback score (MAB8).",
    conditions: ["bandit", "random", "fixed"].map((p, i) => ({
      name: `${"ABC"[i]} · ${p}`, description: "", weight: 1, config: { on_demand_feedback: { style_policy: p } },
    })),
  },
  {
    name: "Chat panel vs character",
    hypothesis: "A character presentation increases how often students rate feedback.",
    conditions: ["chat_panel", "character"].map((p, i) => ({
      name: `${"AB"[i]} · ${p.replace("_", " ")}`, description: "", weight: 1, config: { feedback_presentation: { mode: p } },
    })),
  },
];

export default function ExperimentPage() {
  const { eid } = useParams();
  const id = Number(eid);
  const nav = useNavigate();
  const toast = useToast();
  const { toggleSidebar, registry, reloadCourses } = useInstructor();
  const [e, setE] = useState<Experiment | null>(null);
  const [form, setForm] = useState<Experiment | null>(null);
  const [course, setCourse] = useState<Course | null>(null);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [assignmentCfg, setAssignmentCfg] = useState<Record<number, ConfigOverrides>>({});
  const [tab, setTab] = useState("design");
  const [openCond, setOpenCond] = useState<number | null>(0);
  const [templates, setTemplates] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      const found = await api.get<Experiment>(`/api/instructor/experiments/${id}`);
      const [c, as] = await Promise.all([
        api.get<Course>(`/api/instructor/courses/${found.course_id}`),
        api.get<Assignment[]>(`/api/instructor/courses/${found.course_id}/assignments`),
      ]);
      // condition editors show values inherited from the scoped assignment's overrides
      const cfgs = await Promise.all(as.map((a) => api.get<{ config: ConfigOverrides }>(`/api/instructor/assignments/${a.id}`)));
      setAssignmentCfg(Object.fromEntries(as.map((a, i) => [a.id, cfgs[i].config])));
      setE(found); setForm(found); setCourse(c); setAssignments(as);
    } catch (err) {
      setError((err as Error).message);
    }
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [id]);

  if (!e || !form || !course) return <><Topbar onToggleSidebar={toggleSidebar} crumbs={[{ label: "…" }]} /><Loading error={error} /></>;

  const locked = e.status !== "draft";
  const dirty = JSON.stringify(form) !== JSON.stringify(e);
  const inherited = mergeConfig(registry.defaults, course.config, form.assignment_id ? assignmentCfg[form.assignment_id] : undefined);

  const patch = async (body: Partial<Experiment>) => {
    try {
      const upd = await api.patch<Experiment>(`/api/instructor/experiments/${id}`, body);
      setE(upd); setForm(upd);
      reloadCourses();
      return true;
    } catch (err) {
      toast((err as Error).message, true);
      return false;
    }
  };
  const save = () => patch({
    name: form.name, hypothesis: form.hypothesis, assignment_id: form.assignment_id, strategy: form.strategy,
    conditions: form.conditions,
  }).then((ok) => ok && toast("Saved"));
  const setStatus = async (status: Experiment["status"]) => {
    if (dirty && !(await patch({ name: form.name, hypothesis: form.hypothesis, assignment_id: form.assignment_id, strategy: form.strategy, conditions: form.conditions }))) return;
    if (await patch({ status })) toast(status === "active" ? "Experiment is live 🚀" : `Experiment ${status}`);
  };
  const del = async () => {
    try {
      await api.del(`/api/instructor/experiments/${id}`);
      reloadCourses();
      nav(`/i/courses/${course.id}/experiments`);
    } catch (err) {
      toast((err as Error).message, true);
    }
  };
  const setCond = (i: number, c: Partial<Condition>) =>
    setForm({ ...form, conditions: form.conditions.map((x, j) => (j === i ? { ...x, ...c } : x)) });

  return (
    <>
      <Topbar
        onToggleSidebar={toggleSidebar}
        crumbs={[
          { label: course.code, icon: "🎓", to: `/i/courses/${course.id}` },
          { label: "A/B experiments", icon: "🧪", to: `/i/courses/${course.id}/experiments` },
          { label: e.name },
        ]}
        right={
          <div className="row" style={{ gap: 4 }}>
            {e.status === "draft" && <button className="btn danger" onClick={del}>Delete</button>}
            {(e.status === "draft" || e.status === "paused") && <button className="btn primary" onClick={() => setStatus("active")}>▶ {e.status === "paused" ? "Resume" : "Start experiment"}</button>}
            {e.status === "active" && <button className="btn outline" onClick={() => setStatus("paused")}>⏸ Pause</button>}
            {(e.status === "active" || e.status === "paused") && <button className="btn outline" onClick={() => setStatus("completed")}>■ Complete</button>}
          </div>
        }
      />
      <div className="content">
        <div className="page wide">
          <PageHeader icon="🧪" title={<input className="page-title-input" value={form.name} onChange={(ev) => setForm({ ...form, name: ev.target.value })} />} />
          <Props>
            <Prop icon="◉" label="Status"><Tag dot color={STATUS_COLORS[e.status]}>{e.status === "active" ? "running" : e.status}</Tag></Prop>
            <Prop icon="🎯" label="Scope" editable>
              <select className="select" style={{ width: 300 }} disabled={locked} value={form.assignment_id ?? ""}
                      onChange={(ev) => setForm({ ...form, assignment_id: ev.target.value ? Number(ev.target.value) : null })}>
                <option value="">Whole course (all assignments)</option>
                {assignments.map((a) => <option key={a.id} value={a.id}>📝 {a.title}</option>)}
              </select>
            </Prop>
            <Prop icon="🎲" label="Assignment strategy" editable>
              <select className="select" style={{ width: 300 }} value={form.strategy} onChange={(ev) => setForm({ ...form, strategy: ev.target.value as Experiment["strategy"] })}>
                <option value="balanced">Balanced — fill conditions evenly (by weight)</option>
                <option value="random">Random — weighted coin flip per student</option>
                <option value="manual">Manual — I place students myself</option>
              </select>
            </Prop>
            <Prop icon="💡" label="Hypothesis" editable>
              <input className="input ghost" value={form.hypothesis} placeholder="What do you expect to happen?" onChange={(ev) => setForm({ ...form, hypothesis: ev.target.value })} />
            </Prop>
            <Prop icon="🕐" label="Created">{fmtDate(e.created_at, true)}</Prop>
          </Props>
          <Views
            tabs={[
              { key: "design", label: "Conditions", icon: "🧩", count: form.conditions.length },
              { key: "participants", label: "Participants", icon: "👥" },
              { key: "results", label: "Results", icon: "📊" },
            ]}
            active={tab} onChange={setTab}
            right={tab === "design" && (
              <div className="row" style={{ gap: 4, paddingBottom: 6 }}>
                {e.status === "draft" && <button className="btn" onClick={() => setTemplates(true)}>✨ Templates</button>}
                {dirty && <button className="btn" onClick={() => setForm(e)}>Discard</button>}
                <button className="btn primary" disabled={!dirty} onClick={save}>Save</button>
              </div>
            )}
          />

          {tab === "design" && (
            <>
              {e.status === "active" && (
                <Callout icon="⚠️" color="yellow">This experiment is running. Editing a condition changes what its students see from now on; results before and after the edit will be mixed.</Callout>
              )}
              {form.conditions.map((c, i) => {
                const color = COND_COLORS[i % COND_COLORS.length];
                const open = openCond === i;
                return (
                  <div key={c.id ?? `new${i}`} className="fb-card" style={{ padding: "12px 16px" }}>
                    <div className="row">
                      <span className={`caret ${open ? "open" : ""}`} style={{ cursor: "pointer" }} onClick={() => setOpenCond(open ? null : i)}>▶</span>
                      <Tag color={color} dot>Condition {String.fromCharCode(65 + i)}</Tag>
                      <input className="input ghost" style={{ fontWeight: 600, fontSize: 15, flex: 1 }} value={c.name} onChange={(ev) => setCond(i, { name: ev.target.value })} />
                      <span className="faint small">weight</span>
                      <input className="input" type="number" min={0.1} step={0.1} style={{ width: 70 }} value={c.weight} onChange={(ev) => setCond(i, { weight: Number(ev.target.value) || 1 })} />
                      {c.students !== undefined && <Tag color="gray">👥 {c.students}</Tag>}
                      {(!c.students || e.status === "draft") && form.conditions.length > 1 && (
                        <button className="icon-btn" title="Remove condition" onClick={() => setForm({ ...form, conditions: form.conditions.filter((_, j) => j !== i) })}>🗑</button>
                      )}
                    </div>
                    <div style={{ padding: "6px 0 0 30px" }}><OverrideSummary registry={registry} config={c.config} /></div>
                    {open && (
                      <div style={{ paddingLeft: 30, marginTop: 8 }}>
                        <input className="input ghost muted" placeholder="Description (optional)" value={c.description} onChange={(ev) => setCond(i, { description: ev.target.value })} />
                        <ModuleConfigEditor registry={registry} value={c.config} inherited={inherited}
                                            onChange={(v) => setCond(i, { config: v })}
                                            inheritLabel={form.assignment_id ? "assignment" : "course"} />
                      </div>
                    )}
                  </div>
                );
              })}
              <div className="board-add" onClick={() => {
                setForm({ ...form, conditions: [...form.conditions, { name: `${String.fromCharCode(65 + form.conditions.length)} · Variant`, description: "", weight: 1, config: {} }] });
                setOpenCond(form.conditions.length);
              }}>＋ Add condition</div>
            </>
          )}

          {tab === "participants" && <ParticipantsPanel e={e} onChanged={load} />}
          {tab === "results" && <ResultsPanel e={e} />}
        </div>
      </div>
      {templates && (
        <Modal onClose={() => setTemplates(false)}>
          <h2 style={{ marginTop: 0 }}>✨ Start from a template</h2>
          {TEMPLATES.map((t) => (
            <div key={t.name} className="card" onClick={() => { setForm({ ...form, name: t.name, hypothesis: t.hypothesis, conditions: t.conditions }); setTemplates(false); setOpenCond(null); }}>
              <div className="card-title">{t.name}</div>
              <div className="muted small" style={{ marginBottom: 4 }}>{t.hypothesis}</div>
              <div className="card-meta">{t.conditions.map((c, i) => <Tag key={c.name} color={COND_COLORS[i]}>{c.name}</Tag>)}</div>
            </div>
          ))}
        </Modal>
      )}
    </>
  );
}

function ParticipantsPanel({ e, onChanged }: { e: Experiment; onChanged: () => void }) {
  const toast = useToast();
  const parts = useLoad(() => api.get<Participant[]>(`/api/instructor/experiments/${e.id}/participants`), [e.id]);
  const assignAll = async (reassign: boolean) => {
    try {
      await api.post(`/api/instructor/experiments/${e.id}/assign`, { reassign });
      parts.reload(); onChanged();
      toast(reassign ? "Everyone re-randomized" : "Unassigned students placed");
    } catch (err) { toast((err as Error).message, true); }
  };
  const move = async (sid: number, cid: number | null) => {
    await api.put(`/api/instructor/experiments/${e.id}/participants/${sid}`, { condition_id: cid });
    parts.reload(); onChanged();
  };
  if (!parts.data) return <Loading error={parts.error} />;
  const unassigned = parts.data.filter((p) => !p.condition_id).length;
  const overrides = parts.data.filter((p) => p.has_override).length;
  return (
    <>
      <Callout icon="👥">
        {e.strategy === "manual"
          ? "Manual strategy: unassigned students get the baseline configuration until you place them."
          : "Students are placed automatically the first time they open an affected assignment while the experiment runs — or place everyone now."}
      </Callout>
      {overrides > 0 && <Callout icon="⚠️" color="yellow">{overrides} student{overrides > 1 ? "s have" : " has"} per-student overrides on this assignment, which take precedence over their condition. Consider excluding them from analysis.</Callout>}
      <div className="row" style={{ margin: "8px 0" }}>
        <span className="muted">{unassigned} unassigned</span><span className="spacer" />
        <button className="btn outline" disabled={!unassigned} onClick={() => assignAll(false)}>Place unassigned</button>
        {e.status === "draft" && <button className="btn outline" onClick={() => assignAll(true)}>Re-randomize all</button>}
      </div>
      <table className="table">
        <thead><tr><th>Aa Student</th><th>Pseudonym</th><th>🧪 Condition</th><th>Placed by</th></tr></thead>
        <tbody>
          {parts.data.map((p) => (
            <tr key={p.id}>
              <td style={{ fontWeight: 500 }}>{p.display_name} {p.has_override && <Tag color="yellow">override</Tag>}</td>
              <td className="mono">{p.pseudonym}</td>
              <td>
                <select className="select" style={{ width: 240 }} value={p.condition_id ?? ""} onChange={(ev) => move(p.id, ev.target.value ? Number(ev.target.value) : null)}>
                  <option value="">— unassigned —</option>
                  {e.conditions.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              </td>
              <td>{p.assigned_by ? <Tag color="gray">{p.assigned_by}</Tag> : <span className="faint">—</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function ResultsPanel({ e }: { e: Experiment }) {
  const r = useLoad(() => api.get<Result[]>(`/api/instructor/experiments/${e.id}/results`), [e.id]);
  if (!r.data) return <Loading error={r.error} />;
  const pct = (v: number | null) => (v === null ? "—" : `${Math.round(v * 100)}%`);
  const num = (v: number | null, d = 2) => (v === null ? "—" : v.toFixed(d));
  const metrics: [string, (x: Result) => string][] = [
    ["👥 Students", (x) => String(x.students)],
    ["💬 On-demand requests", (x) => String(x.on_demand_requests)],
    ["⚡ Real-time pop-ups", (x) => String(x.realtime_popups)],
    ["🙈 Pop-ups dismissed", (x) => String(x.dismissed)],
    ["👍 Student helpful rate", (x) => pct(x.helpful_rate)],
    ["🧑‍🏫 Mean instructor rating (1–5)", (x) => num(x.mean_instructor_rating)],
    ["🎯 Mean bandit reward", (x) => `${num(x.mean_reward)} (n=${x.final_rewards})`],
    ["📨 Submissions", (x) => String(x.submissions)],
    ["📏 Mean words submitted", (x) => num(x.mean_words, 0)],
    ["🎓 Mean grade", (x) => num(x.mean_grade)],
  ];
  return (
    <>
      <div className="muted small" style={{ marginBottom: 8 }}>Live descriptive statistics per condition. Export the pseudonymized event log from Research data for inferential analysis.</div>
      <table className="table">
        <thead><tr><th>Metric</th>{r.data.map((c, i) => <th key={c.condition_id}><Tag color={COND_COLORS[i % COND_COLORS.length]} dot>{c.name}</Tag></th>)}</tr></thead>
        <tbody>
          {metrics.map(([label, f]) => (
            <tr key={label}><td className="muted">{label}</td>{r.data!.map((c) => <td key={c.condition_id} style={{ fontWeight: 500 }}>{f(c)}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
