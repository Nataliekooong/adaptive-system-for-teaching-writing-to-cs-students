import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../../api";
import { fmtDate } from "../../config";
import type { Assignment, Course, UserRef } from "../../types";
import { Loading, STATUS_COLORS, Tag, useLoad } from "../../ui";

interface ReviewStudent {
  student: UserRef; submission_id: number | null; status: string;
  submitted_at: string | null; grade: string | null; released: boolean; words: number;
}

export function ReviewTab({ course }: { course: Course }) {
  const assignments = useLoad(() => api.get<Assignment[]>(`/api/instructor/courses/${course.id}/assignments`), [course.id]);
  const [params, setParams] = useSearchParams();
  if (!assignments.data) return <Loading error={assignments.error} />;
  if (!assignments.data.length) return <div className="empty">No assignments to review yet.</div>;
  const selected = assignments.data.find(a => String(a.id) === params.get("assignment")) ?? assignments.data[0];
  return <>
    <div className="review-toolbar">
      <div><h2 className="h">Student work</h2><p className="muted">Review each student's revisions and give one overall assignment grade.</p></div>
      <label className="field">Assignment
        <select className="input" value={selected.id} onChange={e => setParams({ assignment: e.target.value })}>
          {assignments.data.map(a => <option key={a.id} value={a.id}>{a.title}</option>)}
        </select>
      </label>
    </div>
    <StudentReviews key={selected.id} assignment={selected} />
  </>;
}

function StudentReviews({ assignment }: { assignment: Assignment }) {
  const rows = useLoad(() => api.get<ReviewStudent[]>(`/api/instructor/assignments/${assignment.id}/submissions`), [assignment.id]);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  if (!rows.data) return <Loading error={rows.error} />;
  const filtered = rows.data.filter(r => `${r.student.display_name} ${r.student.username}`.toLowerCase().includes(search.toLowerCase()));
  const pages = Math.max(1, Math.ceil(filtered.length / 10));
  const current = Math.min(page, pages - 1);
  return <>
    <div className="row wrap review-list-tools">
      <span className="muted">{rows.data.length} assigned · {rows.data.filter(r => r.submission_id !== null).length} submitted</span>
      <span className="spacer" />
      <input className="input" style={{ maxWidth: 260 }} aria-label="Search students" placeholder="Search students…" value={search} onChange={e => { setSearch(e.target.value); setPage(0); }} />
      <button className="btn outline" onClick={rows.reload}>Refresh</button>
    </div>
    {rows.error && <div role="alert">{rows.error}</div>}
    <div className="review-table-wrap"><table className="table">
      <thead><tr><th>Student</th><th>MacID</th><th>Status</th><th>Submitted</th><th>Words</th><th>Grade</th><th>Review</th></tr></thead>
      <tbody>{filtered.slice(current * 10, current * 10 + 10).map(r => <tr key={r.student.id}>
        <td><strong>{r.student.display_name}</strong></td><td className="muted">{r.student.username}</td>
        <td><Tag color={STATUS_COLORS[r.status] ?? "gray"} dot>{r.status}</Tag></td>
        <td>{r.submitted_at ? fmtDate(r.submitted_at, true) : "—"}</td><td>{r.words}</td>
        <td>{r.grade ?? "—"}{r.grade && <div className="faint small">{r.released ? "Released" : "Not released"}</div>}</td>
        <td>{r.submission_id !== null
          ? <Link className="btn outline" to={`/i/assignments/${assignment.id}/students/${r.student.id}`}>Open review</Link>
          : <span className="faint small">Awaiting submission</span>}</td>
      </tr>)}</tbody>
    </table></div>
    {!filtered.length && <div className="empty">{rows.data.length ? "No matching students." : "No students assigned yet."}</div>}
    <div className="review-pagination" aria-label="Student pages">
      <button className="btn" disabled={current === 0} onClick={() => setPage(current - 1)}>Previous</button>
      <span className="muted small">Page {current + 1} of {pages}</span>
      <button className="btn" disabled={current + 1 >= pages} onClick={() => setPage(current + 1)}>Next</button>
    </div>
  </>;
}
