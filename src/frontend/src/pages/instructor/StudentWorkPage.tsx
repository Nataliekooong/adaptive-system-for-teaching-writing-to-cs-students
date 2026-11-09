import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../../api";
import { fmtDate, wordCount } from "../../config";
import type { Assignment, UserRef } from "../../types";
import { Loading, PageHeader, Tag, Topbar, useLoad, useToast } from "../../ui";
import { useInstructor } from "./InstructorLayout";

interface Revision {
  id: number; created_at: string; content: string; words: number; is_submission: boolean;
  changes: { kind: "equal" | "delete" | "insert"; text: string }[];
}
interface Work {
  student: UserRef; draft: string; revisions: Revision[];
  submission: { id: number; content: string; submitted_at: string; grade: string | null; comments: string; released: boolean } | null;
}

export default function StudentWorkPage() {
  const { aid, sid } = useParams();
  return <ReviewPage key={`${aid}/${sid}`} aid={aid!} sid={sid!} />;
}

function ReviewPage({ aid, sid }: { aid: string; sid: string }) {
  const toast = useToast();
  const { toggleSidebar } = useInstructor();
  const a = useLoad(() => api.get<Assignment>(`/api/instructor/assignments/${aid}`), [aid]);
  const w = useLoad(() => api.get<Work>(`/api/instructor/assignments/${aid}/students/${sid}/work`), [aid, sid]);
  const [selected, setSelected] = useState<number | null>(null);
  const [page, setPage] = useState(0);
  const [showChanges, setShowChanges] = useState(true);
  const [grade, setGrade] = useState({ grade: "", comments: "" });
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    if (w.data?.submission) setGrade({ grade: w.data.submission.grade ?? "", comments: w.data.submission.comments });
  }, [w.data]);

  if (!w.data || !a.data) return <><Topbar onToggleSidebar={toggleSidebar} crumbs={[{ label: "Review" }]} /><Loading error={w.error ?? a.error} /></>;
  const { student, submission, revisions } = w.data;
  const index = Math.max(0, revisions.findIndex(v => v.id === selected));
  const revision = revisions[index];
  const pages = Math.max(1, Math.ceil(revisions.length / 8));
  const text = revision?.content ?? submission?.content ?? w.data.draft;
  const reviewUrl = `/i/courses/${a.data.course_id}/review?assignment=${aid}`;
  const choose = (i: number) => { setSelected(revisions[i].id); setPage(Math.floor(i / 8)); };
  const saveGrade = async (release: boolean) => {
    if (!submission || saving) return;
    setSaving(true);
    try {
      await api.post(`/api/instructor/submissions/${submission.id}/grade`, grade);
      if (release) await api.post(`/api/instructor/assignments/${aid}/release`, { submission_ids: [submission.id] });
      toast(release ? "Overall grade saved and released" : submission.released ? "Released grade updated" : "Overall grade saved (not released)");
      w.reload();
    } catch (e) { toast((e as Error).message, true); }
    finally { setSaving(false); }
  };

  return <>
    <Topbar onToggleSidebar={toggleSidebar} crumbs={[
      { label: "Review", to: reviewUrl }, { label: a.data.title, to: `/i/assignments/${aid}` }, { label: student.display_name },
    ]} />
    <div className="content"><div className="page wide">
      <Link className="review-back" to={reviewUrl}>← All students</Link>
      <PageHeader icon="✎" title={student.display_name} />
      <div className="row wrap review-meta">
        <span className="muted">{a.data.title} · {student.username}</span>
        <Tag color={submission ? "green" : "yellow"}>{submission ? "Submitted" : "In progress"}</Tag>
        <span className="spacer" /><span className="muted small">{revisions.length} saved revisions</span>
      </div>
      <div className="review-workspace">
        <aside className="revision-sidebar" aria-label="Revision history">
          <div className="revision-heading"><strong>Revision list</strong><span className="faint small">Oldest to newest</span></div>
          {!revisions.length && <p className="muted">No saved revisions yet.</p>}
          {revisions.slice(page * 8, page * 8 + 8).map((v, i) => {
            const n = page * 8 + i;
            return <button key={v.id} className={`revision-item ${n === index ? "active" : ""}`} aria-current={n === index ? "step" : undefined} onClick={() => choose(n)}>
              <span className="row"><strong>Revision {n + 1}</strong>{v.is_submission && <Tag color="green">Final</Tag>}</span>
              <span className="small muted">{fmtDate(v.created_at, true)}</span>
              <span className="small faint">{v.words} words{n === 0 ? " · First saved draft" : ""}</span>
            </button>;
          })}
          <div className="review-pagination">
            <button className="btn" aria-label="Previous revision page" disabled={page === 0} onClick={() => choose((page - 1) * 8)}>←</button>
            <span className="small muted">{page + 1} / {pages}</span>
            <button className="btn" aria-label="Next revision page" disabled={page + 1 >= pages} onClick={() => choose((page + 1) * 8)}>→</button>
          </div>
        </aside>
        <section className="revision-main" aria-label="Student writing">
          <div className="revision-document">
            <div className="revision-document-toolbar">
              <div><h2>{revision ? `Revision ${index + 1}` : "Current draft"}</h2>
                <span className="muted small">{index === 0 ? "First saved draft" : `Compared with revision ${index}`} · {wordCount(text)} words</span>
              </div>
              <label className="row small"><input type="checkbox" checked={showChanges} onChange={e => setShowChanges(e.target.checked)} />Show changes</label>
            </div>
            {showChanges && index > 0 && <div className="revision-legend small"><span><del>Removed text</del></span><span><ins>Added text</ins></span></div>}
            <article className="revision-writing" aria-label={`Revision ${index + 1} content`}>
              {showChanges && revision && index > 0
                ? revision.changes.map((change, i) => change.kind === "delete" ? <del key={i}>{change.text}</del> : change.kind === "insert" ? <ins key={i}>{change.text}</ins> : <span key={i}>{change.text}</span>)
                : text || <span className="faint">No text in this revision.</span>}
            </article>
            <div className="revision-document-footer">
              <button className="btn" disabled={!revision || index === 0} onClick={() => choose(index - 1)}>← Earlier</button>
              <span className="small muted">{revision?.is_submission ? "Final submitted version" : "Saved draft"}</span>
              <button className="btn" disabled={!revision || index + 1 >= revisions.length} onClick={() => choose(index + 1)}>Later →</button>
            </div>
          </div>
          <section className="review-grade" aria-label="Overall assignment grade">
            <div className="row wrap"><h2>Overall assignment grade</h2><span className="spacer" />
              {submission?.grade && <Tag color={submission.released ? "green" : "gray"}>{submission.released ? "Released" : "Not released"}</Tag>}
            </div>
            <p className="muted small">One grade for the final submission, across all revisions.</p>
            {!submission ? <p className="muted">Grading opens after the student submits.</p> : <>
              <div className="row wrap small" style={{ marginBottom: 16 }}><span className="muted">Submitted {fmtDate(submission.submitted_at, true)}</span>
                <button className="btn" onClick={() => choose(revisions.length - 1)}>View final submission</button></div>
              <div className="field"><label htmlFor="overall-grade">Grade</label><input id="overall-grade" className="input" maxLength={32} value={grade.grade} placeholder="e.g. 85 or A-" onChange={e => setGrade({ ...grade, grade: e.target.value })} /></div>
              <div className="field"><label htmlFor="overall-comments">Overall comments</label><textarea id="overall-comments" className="textarea" rows={4} value={grade.comments} placeholder="Feedback on the assignment as a whole…" onChange={e => setGrade({ ...grade, comments: e.target.value })} /></div>
              <div className="row wrap"><span className="spacer" />
                <button className="btn outline" disabled={!grade.grade.trim() || saving} onClick={() => saveGrade(false)}>{saving ? "Saving…" : "Save grade"}</button>
                {!submission.released && <button className="btn primary" disabled={!grade.grade.trim() || saving} onClick={() => saveGrade(true)}>Save & release</button>}
              </div>
            </>}
          </section>
        </section>
      </div>
    </div></div>
  </>;
}
