import { useNavigate, useParams } from "react-router-dom";
import { api } from "../../api";
import { fmtDate } from "../../config";
import type { UserRef } from "../../types";
import { Loading, PageHeader, Prop, Props, STATUS_COLORS, Tag, Topbar, useLoad } from "../../ui";
import { useInstructor } from "./InstructorLayout";

interface Profile {
  student: UserRef;
  assignments: { assignment_id: number; title: string; due_date: string | null; status: string; grade: string | null; released: boolean; conditions: string[] }[];
  struggles: [string, number][];
  mastery: Record<string, number>;
  questionnaire: Record<string, unknown> | null;
  feedback_count: number;
}

/** I6 + I7: a student's assignments, grades, learner model and common struggle areas. */
export default function StudentProfilePage() {
  const { cid, sid } = useParams();
  const nav = useNavigate();
  const { toggleSidebar, courses } = useInstructor();
  const p = useLoad(() => api.get<Profile>(`/api/instructor/courses/${cid}/students/${sid}`), [cid, sid]);
  const course = courses.find((c) => c.id === Number(cid));
  if (!p.data) return <><Topbar onToggleSidebar={toggleSidebar} crumbs={[{ label: "…" }]} /><Loading error={p.error} /></>;
  const d = p.data;
  const max = Math.max(1, ...d.struggles.map((s) => s[1]));
  return (
    <>
      <Topbar onToggleSidebar={toggleSidebar} crumbs={[
        { label: course?.code ?? "Course", icon: "🎓", to: `/i/courses/${cid}` },
        { label: "Students", icon: "👥", to: `/i/courses/${cid}/students` },
        { label: d.student.display_name },
      ]} />
      <div className="content">
        <div className="page">
          <PageHeader icon="🧑‍🎓" title={d.student.display_name} />
          <Props>
            <Prop icon="🆔" label="MacID">{d.student.username}</Prop>
            <Prop icon="🕶" label="Pseudonym"><span className="mono">{d.student.pseudonym}</span></Prop>
            <Prop icon="📋" label="Questionnaire">
              {d.questionnaire ? Object.entries(d.questionnaire).filter(([, v]) => v !== "").map(([k, v]) => <Tag key={k} color="gray">{k.replace(/_/g, " ")}: {String(v)}</Tag>) : <span className="faint">Not completed</span>}
            </Prop>
            <Prop icon="💬" label="Feedback received">{d.feedback_count}</Prop>
          </Props>

          <h2 className="h">📝 Assignments & grades</h2>
          <table className="table">
            <thead><tr><th>Aa Assignment</th><th>Due</th><th>Status</th><th>Grade</th><th>🧪 Condition</th></tr></thead>
            <tbody>
              {d.assignments.map((a) => (
                <tr key={a.assignment_id} className="clickable" onClick={() => nav(`/i/assignments/${a.assignment_id}/students/${d.student.id}`)}>
                  <td style={{ fontWeight: 500 }}>{a.title}</td>
                  <td>{fmtDate(a.due_date)}</td>
                  <td><Tag dot color={STATUS_COLORS[a.status] ?? "gray"}>{a.status}</Tag></td>
                  <td>{a.grade ? <>{a.grade} {!a.released && <span className="faint small">(unreleased)</span>}</> : "—"}</td>
                  <td>{a.conditions.map((c) => <Tag key={c} color="purple">{c}</Tag>)}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="grid2" style={{ marginTop: 8 }}>
            <div>
              <h2 className="h">🔥 Common struggle areas</h2>
              {d.struggles.length === 0 && <div className="faint">No feedback yet.</div>}
              {d.struggles.map(([area, n]) => (
                <div key={area} style={{ marginBottom: 8 }}>
                  <div className="row small"><span>{area}</span><span className="spacer" /><span className="faint">{n}</span></div>
                  <div className="bar"><div style={{ width: `${(n / max) * 100}%`, background: "var(--red-dot)" }} /></div>
                </div>
              ))}
            </div>
            <div>
              <h2 className="h">🧠 Learner model (BKT)</h2>
              {Object.keys(d.mastery).length === 0 && <div className="faint">No estimates yet.</div>}
              {Object.entries(d.mastery).map(([area, v]) => (
                <div key={area} style={{ marginBottom: 8 }}>
                  <div className="row small"><span>{area}</span><span className="spacer" /><span className="faint">P(mastery) {v.toFixed(2)}</span></div>
                  <div className="bar"><div style={{ width: `${v * 100}%`, background: "var(--green-dot)" }} /></div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
