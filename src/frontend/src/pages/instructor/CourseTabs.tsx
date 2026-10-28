import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, getToken } from "../../api";
import { countOverrides, fmtDate } from "../../config";
import { ModuleConfigEditor, OverrideSummary, moduleIcon } from "../../components/ModuleConfigEditor";
import type { Assignment, ConfigOverrides, Course, Experiment, Feedback, UserRef } from "../../types";
import { Board, Callout, Loading, Modal, STATUS_COLORS, Switch, Tag, useLoad, useToast } from "../../ui";
import { useInstructor } from "./InstructorLayout";

type AssignmentRow = Assignment & { students: number; submissions: number; overridden_modules: string[] };

/* ---------------------------------------------------------------- assignments */

export function AssignmentsTab({ course }: { course: Course }) {
  const nav = useNavigate();
  const toast = useToast();
  const { reloadCourses } = useInstructor();
  const rows = useLoad(() => api.get<AssignmentRow[]>(`/api/instructor/courses/${course.id}/assignments`), [course.id]);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ title: "", due_date: "", description: "" });

  const create = async () => {
    try {
      const a = await api.post<Assignment>(`/api/instructor/courses/${course.id}/assignments`, {
        title: form.title, description: form.description,
        due_date: form.due_date ? new Date(form.due_date).toISOString() : null,
        rubric_areas: course.rubric_areas.slice(0, 3), assign_all: true,
      });
      reloadCourses();
      nav(`/i/assignments/${a.id}`);
    } catch (e) {
      toast((e as Error).message, true);
    }
  };

  if (!rows.data) return <Loading error={rows.error} />;
  return (
    <>
      <div className="row" style={{ marginBottom: 8 }}>
        <span className="spacer" />
        <button className="btn primary" onClick={() => setCreating(true)}>New</button>
      </div>
      <table className="table">
        <thead>
          <tr>
            <th><span className="th-ico">Aa</span>Title</th>
            <th><span className="th-ico">📅</span>Due</th>
            <th><span className="th-ico">🎯</span>Focus areas</th>
            <th><span className="th-ico">🧩</span>Module overrides</th>
            <th><span className="th-ico">👥</span>Students</th>
            <th><span className="th-ico">📨</span>Submitted</th>
          </tr>
        </thead>
        <tbody>
          {rows.data.map((a) => (
            <tr key={a.id} className="clickable" onClick={() => nav(`/i/assignments/${a.id}`)}>
              <td style={{ fontWeight: 500 }}>📝 {a.title} {!a.published && <Tag color="gray">hidden</Tag>}</td>
              <td>{fmtDate(a.due_date)}</td>
              <td><div className="row wrap" style={{ gap: 4 }}>{a.rubric_areas.map((r) => <Tag key={r} color="purple">{r}</Tag>)}</div></td>
              <td>{a.overridden_modules.length ? a.overridden_modules.map((m) => <span key={m} title={m} style={{ marginRight: 4 }}>{moduleIcon(m)}</span>) : <span className="faint">—</span>}</td>
              <td>{a.students}</td>
              <td>{a.submissions}/{a.students}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {rows.data.length === 0 && <div className="empty">No assignments yet.</div>}
      {creating && (
        <Modal onClose={() => setCreating(false)}>
          <h2 style={{ marginTop: 0 }}>New assignment</h2>
          <div className="field"><label>Title</label><input className="input" autoFocus value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></div>
          <div className="field"><label>Description</label><input className="input" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></div>
          <div className="field"><label>Due date</label><input className="input" type="datetime-local" value={form.due_date} onChange={(e) => setForm({ ...form, due_date: e.target.value })} /></div>
          <div className="faint small" style={{ marginBottom: 12 }}>All enrolled students are assigned. You can configure modules and students next.</div>
          <div className="row"><span className="spacer" /><button className="btn" onClick={() => setCreating(false)}>Cancel</button>
            <button className="btn primary" disabled={!form.title} onClick={create}>Create</button></div>
        </Modal>
      )}
    </>
  );
}

/* ---------------------------------------------------------------- experiments (board) */

export function ExperimentsTab({ course }: { course: Course }) {
  const nav = useNavigate();
  const toast = useToast();
  const { registry } = useInstructor();
  const exps = useLoad(() => api.get<Experiment[]>(`/api/instructor/courses/${course.id}/experiments`), [course.id]);
  const assignments = useLoad(() => api.get<AssignmentRow[]>(`/api/instructor/courses/${course.id}/assignments`), [course.id]);

  const create = async () => {
    try {
      const e = await api.post<Experiment>(`/api/instructor/courses/${course.id}/experiments`, {
        name: "Untitled experiment", strategy: "balanced",
        conditions: [{ name: "A · Control", config: {} }, { name: "B · Variant", config: {} }],
      });
      nav(`/i/experiments/${e.id}`);
    } catch (e) {
      toast((e as Error).message, true);
    }
  };

  if (!exps.data) return <Loading error={exps.error} />;
  const by = (s: Experiment["status"]) => exps.data!.filter((e) => e.status === s);
  const aTitle = (id: number | null) => (id ? assignments.data?.find((a) => a.id === id)?.title ?? `#${id}` : "Whole course");
  return (
    <>
      <Callout icon="🧪">
        An experiment splits students into <b>conditions</b>. Each condition is a set of module overrides layered on top of
        the course and assignment settings — e.g. turn real-time feedback on for B only, or change its presentation.
      </Callout>
      <div className="row" style={{ margin: "8px 0" }}><span className="spacer" />
        <button className="btn primary" onClick={create}>New</button></div>
      <Board
        columns={[
          { key: "draft", label: "Draft", color: "gray", items: by("draft") },
          { key: "active", label: "Running", color: "green", items: by("active") },
          { key: "paused", label: "Paused", color: "yellow", items: by("paused") },
          { key: "completed", label: "Completed", color: "blue", items: by("completed") },
        ]}
        onAdd={create}
        addLabel="New experiment"
        renderCard={(e) => (
          <div key={e.id} className="card" onClick={() => nav(`/i/experiments/${e.id}`)}>
            <div className="card-title">🧪 {e.name}</div>
            <div className="card-meta" style={{ marginBottom: 6 }}>
              <Tag color="gray">{aTitle(e.assignment_id)}</Tag>
              <Tag color="gray">{e.strategy}</Tag>
            </div>
            {e.conditions.map((c) => (
              <div key={c.id} style={{ fontSize: 12.5, marginTop: 4 }}>
                <span style={{ fontWeight: 500 }}>{c.name}</span> <span className="faint">· {c.students ?? 0} students</span>
                <div style={{ marginTop: 2 }}><OverrideSummary registry={registry} config={c.config} /></div>
              </div>
            ))}
          </div>
        )}
      />
    </>
  );
}

/* ---------------------------------------------------------------- course modules */

export function ModulesTab({ course, onSaved }: { course: Course; onSaved: () => void }) {
  const { registry } = useInstructor();
  const toast = useToast();
  const [value, setValue] = useState<ConfigOverrides>(course.config);
  const dirty = JSON.stringify(value) !== JSON.stringify(course.config);
  const save = async () => {
    try {
      await api.patch(`/api/instructor/courses/${course.id}`, { config: value });
      toast("Course defaults saved");
      onSaved();
    } catch (e) {
      toast((e as Error).message, true);
    }
  };
  return (
    <>
      <Callout icon="🧩" color="blue">
        <b>Course defaults.</b> These apply to every assignment unless an assignment, an experiment condition or a
        per-student override changes them. Layer order: system → course → assignment → condition → student.
      </Callout>
      <div className="row" style={{ position: "sticky", top: 0, background: "#fff", padding: "8px 0", zIndex: 2 }}>
        <span className="muted">{countOverrides(value)} change{countOverrides(value) === 1 ? "" : "s"} from system defaults</span>
        <span className="spacer" />
        {dirty && <button className="btn" onClick={() => setValue(course.config)}>Discard</button>}
        <button className="btn primary" disabled={!dirty} onClick={save}>Save</button>
      </div>
      <ModuleConfigEditor registry={registry} value={value} inherited={registry.defaults} onChange={setValue} inheritLabel="system" />
    </>
  );
}

/* ---------------------------------------------------------------- review queue (I9) */

interface ReviewItem {
  feedback: Feedback; assignment: { id: number; title: string }; student_pseudonym: string; before: string; after: string;
}

export function ReviewTab({ course }: { course: Course }) {
  const toast = useToast();
  const q = useLoad(() => api.get<{ pending_total: number; items: ReviewItem[] }>(`/api/instructor/courses/${course.id}/review-queue`), [course.id]);
  const [done, setDone] = useState<Record<number, number>>({});
  const rate = async (fid: number, rating: number) => {
    try {
      await api.post(`/api/instructor/feedback/${fid}/rating`, { rating });
      setDone({ ...done, [fid]: rating });
    } catch (e) {
      toast((e as Error).message, true);
    }
  };
  if (!q.data) return <Loading error={q.error} />;
  return (
    <>
      <Callout icon="⭐">
        Rate how much each AI feedback item helped the student's revision. Your rating is combined with the student's
        own rating to reward the feedback-style bandit. You see a random sample of at most 5 — {q.data.pending_total} waiting in total.
        Busy? Set <b>Bandit reward → Reward source</b> to <i>student only</i> or rely on the instructor timeout.
      </Callout>
      <div className="row" style={{ margin: "8px 0" }}><span className="spacer" />
        <button className="btn outline" onClick={() => { setDone({}); q.reload(); }}>🔀 New sample</button></div>
      {q.data.items.length === 0 && <div className="empty">Nothing to review — revisions appear here after students revise in response to feedback.</div>}
      {q.data.items.map((it) => (
        <div key={it.feedback.id} className="fb-card" style={{ padding: 16 }}>
          <div className="row small" style={{ marginBottom: 8 }}>
            <Tag color="gray">{it.student_pseudonym}</Tag>
            <Tag color="gray">📝 {it.assignment.title}</Tag>
            {it.feedback.style && <Tag color="blue">style: {it.feedback.style}</Tag>}
            <Tag color="gray">{it.feedback.model_version}</Tag>
            <span className="spacer" /><span className="faint">{fmtDate(it.feedback.created_at, true)}</span>
          </div>
          <div className="chat-bubble" style={{ marginBottom: 10 }}>
            <b>{it.feedback.content.summary}</b>
            {it.feedback.content.items.map((x, i) => (
              <div key={i} style={{ marginTop: 4 }}><Tag color="purple">{x.rubric_area}</Tag> {x.comment} <span className="muted">{x.suggestion}</span></div>
            ))}
          </div>
          <div className="diff">
            <div><div className="small muted" style={{ marginBottom: 4 }}>Before feedback</div><pre>{it.before}</pre></div>
            <div><div className="small muted" style={{ marginBottom: 4 }}>After revision</div><pre>{it.after}</pre></div>
          </div>
          <div className="row" style={{ marginTop: 10 }}>
            <span className="muted">How helpful was this feedback?</span>
            {done[it.feedback.id] ? <Tag color="green">Rated {done[it.feedback.id]}/5 ✓</Tag> : (
              <div className="stars">
                {[1, 2, 3, 4, 5].map((n) => <button key={n} onClick={() => rate(it.feedback.id, n)}>{n}</button>)}
              </div>
            )}
            <span className="faint small">1 = not at all · 5 = very</span>
          </div>
        </div>
      ))}
    </>
  );
}

/* ---------------------------------------------------------------- students */

type StudentRow = UserRef & { questionnaire_done: boolean; mastery: Record<string, number> };

export function StudentsTab({ course }: { course: Course }) {
  const nav = useNavigate();
  const toast = useToast();
  const { reloadCourses } = useInstructor();
  const rows = useLoad(() => api.get<StudentRow[]>(`/api/instructor/courses/${course.id}/students`), [course.id]);
  const struggles = useLoad(() => api.get<{ area: string; students: number; mentions: number }[]>(`/api/instructor/courses/${course.id}/struggles`), [course.id]);
  const [enrolling, setEnrolling] = useState<UserRef[] | null>(null);
  const [sel, setSel] = useState<Set<number>>(new Set());

  const openEnroll = async () => {
    const all = await api.get<UserRef[]>("/api/instructor/students");
    setSel(new Set(rows.data!.map((r) => r.id)));
    setEnrolling(all);
  };
  const saveEnroll = async () => {
    try {
      await api.put(`/api/instructor/courses/${course.id}/students`, { student_ids: [...sel] });
      setEnrolling(null);
      rows.reload();
      reloadCourses();
    } catch (e) {
      toast((e as Error).message, true);
    }
  };

  if (!rows.data) return <Loading error={rows.error} />;
  const maxMentions = Math.max(1, ...(struggles.data ?? []).map((s) => s.mentions));
  return (
    <>
      <div className="row" style={{ marginBottom: 8 }}><span className="spacer" />
        <button className="btn outline" onClick={openEnroll}>Manage enrollment</button></div>
      <table className="table">
        <thead><tr><th>Aa Name</th><th>MacID</th><th>Pseudonym</th><th>Questionnaire</th><th>🧠 Avg mastery (BKT)</th></tr></thead>
        <tbody>
          {rows.data.map((s) => {
            const vals = Object.values(s.mastery);
            const avg = vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
            return (
              <tr key={s.id} className="clickable" onClick={() => nav(`/i/courses/${course.id}/students/${s.id}`)}>
                <td style={{ fontWeight: 500 }}>🧑‍🎓 {s.display_name}</td>
                <td>{s.username}</td>
                <td className="mono">{s.pseudonym}</td>
                <td>{s.questionnaire_done ? <Tag color="green">Done</Tag> : <Tag color="gray">Not yet</Tag>}</td>
                <td>{avg === null ? <span className="faint">—</span> : (
                  <div className="row"><div className="bar" style={{ width: 90 }}><div style={{ width: `${avg * 100}%` }} /></div>{avg.toFixed(2)}</div>
                )}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <h2 className="h">Common struggle areas</h2>
      <div className="muted small" style={{ marginBottom: 8 }}>Aggregated from AI feedback by rubric priority area (I7).</div>
      {(struggles.data ?? []).length === 0 && <div className="empty">No feedback yet.</div>}
      {(struggles.data ?? []).map((s) => (
        <div key={s.area} className="row" style={{ marginBottom: 6 }}>
          <span style={{ width: 200 }}><Tag color="purple">{s.area}</Tag></span>
          <div className="bar" style={{ flex: 1, maxWidth: 360 }}><div style={{ width: `${(s.mentions / maxMentions) * 100}%`, background: "var(--purple-dot)" }} /></div>
          <span className="muted small">{s.mentions} mentions · {s.students} students</span>
        </div>
      ))}
      {enrolling && (
        <Modal onClose={() => setEnrolling(null)}>
          <h2 style={{ marginTop: 0 }}>Enrollment</h2>
          {enrolling.map((u) => (
            <label key={u.id} className="row" style={{ padding: "4px 0", cursor: "pointer" }}>
              <input type="checkbox" checked={sel.has(u.id)} onChange={(e) => {
                const n = new Set(sel); if (e.target.checked) n.add(u.id); else n.delete(u.id); setSel(n);
              }} />
              {u.display_name} <span className="faint">{u.username}</span>
            </label>
          ))}
          <div className="row" style={{ marginTop: 12 }}><span className="spacer" /><button className="btn" onClick={() => setEnrolling(null)}>Cancel</button>
            <button className="btn primary" onClick={saveEnroll}>Save</button></div>
        </Modal>
      )}
    </>
  );
}

/* ---------------------------------------------------------------- library (I10, B6) */

interface Style { key: string; name: string; description: string; prompt_template: string; enabled: boolean }
interface FixedPrompt { id: number; trigger: string; rubric_area: string; text: string; enabled: boolean }

export function LibraryTab({ course }: { course: Course }) {
  const toast = useToast();
  const { reloadRegistry } = useInstructor();
  const styles = useLoad(() => api.get<Style[]>("/api/instructor/styles"), []);
  const prompts = useLoad(() => api.get<FixedPrompt[]>(`/api/instructor/courses/${course.id}/fixed-prompts`), [course.id]);
  const [editStyle, setEditStyle] = useState<Style | null>(null);
  const [editPrompt, setEditPrompt] = useState<Partial<FixedPrompt> | null>(null);

  const saveStyle = async (s: Style) => {
    try {
      await api.put(`/api/instructor/styles/${s.key}`, s);
      styles.reload();
      reloadRegistry();
      setEditStyle(null);
    } catch (e) { toast((e as Error).message, true); }
  };
  const savePrompt = async () => {
    const p = editPrompt!;
    const body = { trigger: p.trigger ?? "any", rubric_area: p.rubric_area ?? "", text: p.text ?? "", enabled: p.enabled ?? true };
    try {
      if (p.id) await api.put(`/api/instructor/fixed-prompts/${p.id}`, body);
      else await api.post(`/api/instructor/courses/${course.id}/fixed-prompts`, body);
      prompts.reload();
      setEditPrompt(null);
    } catch (e) { toast((e as Error).message, true); }
  };
  const togglePrompt = async (p: FixedPrompt) => {
    await api.put(`/api/instructor/fixed-prompts/${p.id}`, { ...p, enabled: !p.enabled });
    prompts.reload();
  };
  const deletePrompt = async (p: FixedPrompt) => {
    await api.del(`/api/instructor/fixed-prompts/${p.id}`);
    prompts.reload();
  };

  return (
    <>
      <h2 className="h" style={{ marginTop: 4 }}>🎨 Feedback styles <span className="faint small" style={{ fontWeight: 400 }}>bandit arms · I10</span></h2>
      <div className="muted small" style={{ marginBottom: 8 }}>Disabled styles are never selected by the bandit, random or fixed policies.</div>
      {!styles.data ? <Loading error={styles.error} /> : (
        <table className="table">
          <thead><tr><th>On</th><th>Aa Style</th><th>Key</th><th>Description</th><th>Prompt template</th><th /></tr></thead>
          <tbody>
            {styles.data.map((s) => (
              <tr key={s.key}>
                <td><Switch on={s.enabled} onChange={(v) => saveStyle({ ...s, enabled: v })} /></td>
                <td style={{ fontWeight: 500 }}>{s.name}</td>
                <td className="mono">{s.key}</td>
                <td className="muted">{s.description}</td>
                <td className="muted small" style={{ maxWidth: 260 }}>{s.prompt_template}</td>
                <td><button className="btn sm" onClick={() => setEditStyle(s)}>Edit</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <div className="board-add" style={{ marginTop: 4 }} onClick={() => setEditStyle({ key: "", name: "", description: "", prompt_template: "", enabled: true })}>＋ New style</div>

      <h2 className="h">📌 Instructor-approved prompts <span className="faint small" style={{ fontWeight: 400 }}>fixed prompts · S9 · B6</span></h2>
      <div className="muted small" style={{ marginBottom: 8 }}>Used when a feedback venue's source is set to <i>fixed prompts</i> (e.g. the “Fixed prompts only” study condition).</div>
      {!prompts.data ? <Loading error={prompts.error} /> : (
        <table className="table">
          <thead><tr><th>On</th><th>⚡ Trigger</th><th>🎯 Rubric area</th><th>Aa Prompt</th><th /></tr></thead>
          <tbody>
            {prompts.data.map((p) => (
              <tr key={p.id}>
                <td><Switch on={p.enabled} onChange={() => togglePrompt(p)} /></td>
                <td><Tag color="orange">{p.trigger.replace("_", " ")}</Tag></td>
                <td>{p.rubric_area ? <Tag color="purple">{p.rubric_area}</Tag> : <span className="faint">any</span>}</td>
                <td>{p.text}</td>
                <td style={{ whiteSpace: "nowrap" }}>
                  <button className="btn sm" onClick={() => setEditPrompt(p)}>Edit</button>
                  <button className="btn sm danger" onClick={() => deletePrompt(p)}>Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <div className="board-add" style={{ marginTop: 4 }} onClick={() => setEditPrompt({ trigger: "any", text: "", rubric_area: "", enabled: true })}>＋ New prompt</div>

      {editStyle && (
        <Modal onClose={() => setEditStyle(null)}>
          <h2 style={{ marginTop: 0 }}>{editStyle.name || "New style"}</h2>
          <div className="field"><label>Key (lowercase, used in logs)</label><input className="input mono" value={editStyle.key} onChange={(e) => setEditStyle({ ...editStyle, key: e.target.value })} /></div>
          <div className="field"><label>Name</label><input className="input" value={editStyle.name} onChange={(e) => setEditStyle({ ...editStyle, name: e.target.value })} /></div>
          <div className="field"><label>Description</label><input className="input" value={editStyle.description} onChange={(e) => setEditStyle({ ...editStyle, description: e.target.value })} /></div>
          <div className="field"><label>Prompt template (sent to the SLM)</label><textarea className="textarea" value={editStyle.prompt_template} onChange={(e) => setEditStyle({ ...editStyle, prompt_template: e.target.value })} /></div>
          <div className="row"><span className="spacer" /><button className="btn" onClick={() => setEditStyle(null)}>Cancel</button>
            <button className="btn primary" onClick={() => saveStyle(editStyle)}>Save</button></div>
        </Modal>
      )}
      {editPrompt && (
        <Modal onClose={() => setEditPrompt(null)}>
          <h2 style={{ marginTop: 0 }}>{editPrompt.id ? "Edit prompt" : "New prompt"}</h2>
          <div className="grid2">
            <div className="field"><label>Trigger</label>
              <select className="select" value={editPrompt.trigger} onChange={(e) => setEditPrompt({ ...editPrompt, trigger: e.target.value })}>
                {["any", "on_demand", "idle", "sentence_end", "deletion"].map((t) => <option key={t} value={t}>{t.replace("_", " ")}</option>)}
              </select></div>
            <div className="field"><label>Rubric area</label>
              <select className="select" value={editPrompt.rubric_area} onChange={(e) => setEditPrompt({ ...editPrompt, rubric_area: e.target.value })}>
                <option value="">Any</option>
                {course.rubric_areas.map((r) => <option key={r}>{r}</option>)}
              </select></div>
          </div>
          <div className="field"><label>Prompt shown to students</label><textarea className="textarea" value={editPrompt.text} onChange={(e) => setEditPrompt({ ...editPrompt, text: e.target.value })} /></div>
          <div className="row"><span className="spacer" /><button className="btn" onClick={() => setEditPrompt(null)}>Cancel</button>
            <button className="btn primary" disabled={!editPrompt.text} onClick={savePrompt}>Save</button></div>
        </Modal>
      )}
    </>
  );
}

/* ---------------------------------------------------------------- research */

interface BanditState {
  arms: { context_key: string; arm: string; alpha: number; beta: number; mean: number; pulls: number }[];
  pending_update: { context_key: string; arm: string; d_alpha: number; d_beta: number; n: number }[];
  decisions: { id: number; student: string; policy: string; arm: string; context_key: string; probability: number;
    student_score: number | null; instructor_score: number | null; reward: number | null; reward_status: string;
    formula: string; applied: boolean; created_at: string }[];
}

export function ResearchTab({ course }: { course: Course }) {
  const toast = useToast();
  const st = useLoad(() => api.get<BanditState>(`/api/instructor/courses/${course.id}/bandit`), [course.id]);
  const events = useLoad(() => api.get<{ id: number; ts: string; pseudonym: string; type: string; condition_id: number | null; payload: Record<string, unknown> }[]>(
    `/api/instructor/courses/${course.id}/events?limit=40`), [course.id]);

  const update = async () => {
    const r = await api.post<{ applied: unknown[] }>(`/api/instructor/courses/${course.id}/bandit/update`);
    toast(`Bandit updated (${r.applied.length} arm${r.applied.length === 1 ? "" : "s"})`);
    st.reload();
  };
  const download = async (format: "csv" | "json") => {
    const res = await fetch(`/api/instructor/courses/${course.id}/events?format=${format}&limit=20000`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `events_${course.code.replace(/\s/g, "_")}.${format}`; a.click();
    URL.revokeObjectURL(url);
  };

  if (!st.data) return <Loading error={st.error} />;
  const contexts = [...new Set(st.data.arms.map((a) => a.context_key))];
  return (
    <>
      <div className="row"><h2 className="h" style={{ margin: 0 }}>🎰 Feedback-style bandit</h2><span className="spacer" />
        <button className="btn outline" onClick={() => download("csv")}>⬇ Events CSV</button>
        <button className="btn outline" onClick={() => download("json")}>⬇ JSON</button>
      </div>
      <div className="muted small" style={{ margin: "4px 0 12px" }}>Thompson Sampling posteriors per learner-level context. Rewards are folded in on a schedule (MAB7) or now.</div>
      <Callout icon="⏱️" color={st.data.pending_update.length ? "yellow" : undefined}>
        <div className="row">
          <div style={{ flex: 1 }}>
            <b>Scheduled update preview.</b>{" "}
            {st.data.pending_update.length
              ? st.data.pending_update.map((p) => `${p.arm} @ ${p.context_key}: +${p.d_alpha.toFixed(2)}α +${p.d_beta.toFixed(2)}β (${p.n})`).join(" · ")
              : "No finalized rewards waiting."}
          </div>
          <button className="btn primary" disabled={!st.data.pending_update.length} onClick={update}>Apply now</button>
        </div>
      </Callout>
      {contexts.length === 0 && <div className="empty">No bandit decisions yet.</div>}
      <div className="grid2">
        {contexts.map((ctx) => (
          <div key={ctx} className="stat">
            <div className="k" style={{ marginBottom: 6 }}>Context: <Tag color="blue">{ctx}</Tag></div>
            {st.data!.arms.filter((a) => a.context_key === ctx).map((a) => (
              <div key={a.arm} className="row" style={{ marginBottom: 4 }}>
                <span style={{ width: 150 }}>{a.arm}</span>
                <div className="bar" style={{ flex: 1 }}><div style={{ width: `${a.mean * 100}%` }} /></div>
                <span className="small muted" style={{ width: 120, textAlign: "right" }}>{a.mean.toFixed(2)} · n={a.pulls}</span>
              </div>
            ))}
          </div>
        ))}
      </div>

      <h2 className="h">🧾 Decision log</h2>
      <table className="table">
        <thead><tr><th>#</th><th>Student</th><th>Policy</th><th>Style</th><th>Context</th><th>P(select)</th><th>Student</th><th>Instructor</th><th>Reward</th><th>Status</th></tr></thead>
        <tbody>
          {st.data.decisions.map((d) => (
            <tr key={d.id}>
              <td className="faint">{d.id}</td>
              <td className="mono">{d.student}</td>
              <td><Tag color="gray">{d.policy}</Tag></td>
              <td>{d.arm}</td>
              <td>{d.context_key}</td>
              <td>{d.probability.toFixed(2)}</td>
              <td>{d.student_score ?? "—"}</td>
              <td>{d.instructor_score?.toFixed(2) ?? "—"}</td>
              <td title={d.formula}>{d.reward?.toFixed(2) ?? "—"}</td>
              <td><Tag color={STATUS_COLORS[d.reward_status]}>{d.reward_status}{d.applied ? " ✓" : ""}</Tag></td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2 className="h">📜 Recent events</h2>
      <div className="muted small" style={{ marginBottom: 6 }}>Append-only, pseudonymized, linked to assignment and study condition. Raw keystrokes are never logged.</div>
      <table className="table">
        <tbody>
          {(events.data ?? []).map((e) => (
            <tr key={e.id}>
              <td className="faint small" style={{ whiteSpace: "nowrap" }}>{fmtDate(e.ts, true)}</td>
              <td className="mono">{e.pseudonym}</td>
              <td><Tag color="gray">{e.type}</Tag></td>
              <td className="faint small">{e.condition_id ? `cond ${e.condition_id}` : ""}</td>
              <td className="mono faint" style={{ maxWidth: 380, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{JSON.stringify(e.payload)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

