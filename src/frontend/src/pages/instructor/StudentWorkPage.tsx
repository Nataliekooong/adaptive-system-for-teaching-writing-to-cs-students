import { icons } from "../../icons";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../../api";
import { fmtDate, wordCount } from "../../config";
import type { Assignment, Feedback, UserRef } from "../../types";
import { Field, Loading, PageHeader, RatingScale, Tag, Topbar, useLoad, useToast } from "../../ui";
import { useInstructor } from "./InstructorLayout";

interface Revision {
  preceding_feedback: Feedback | null;
  id: number; created_at: string; content: string; words: number; is_submission: boolean;
  changes: { kind: "equal" | "delete" | "insert"; text: string }[];
}
interface Work {
  grading_enabled: boolean;
  student: UserRef; draft: string; revisions: Revision[];
  bandit_rating: BanditRatingStatus | null;
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
  const [releaseOnSave, setReleaseOnSave] = useState(false);
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
      await api.post(`/api/instructor/submissions/${submission.id}/grade`, { ...grade, release });
      toast(release ? "Overall grade saved and released" : "Overall grade saved (not released)");
      setReleaseOnSave(false);
      w.reload();
    } catch (e) { toast((e as Error).message, true); }
    finally { setSaving(false); }
  };

  return <>
    <Topbar onToggleSidebar={toggleSidebar} crumbs={[
      { label: "Review", to: reviewUrl }, { label: a.data.title, to: `/i/assignments/${aid}` }, { label: student.display_name },
    ]} />
    <div className="content"><div className="page review-page">
      <Link className="review-back" to={reviewUrl}>{icons.back} All students</Link>
      <PageHeader title={student.display_name} sub="Writing revisions" />
      <div className="row wrap review-meta">
        <span className="muted">{a.data.title} · {student.username}</span>
        <Tag color={submission ? "green" : "yellow"}>{submission ? "Submitted" : "In progress"}</Tag>
        <span className="spacer" /><span className="muted small">{revisions.filter(v => !v.is_submission).length} feedback rounds</span>
      </div>
      <div className="review-workspace">
        <aside className="revision-sidebar" aria-label="Revision history">
          <div className="revision-heading"><strong>Revision list</strong><span className="faint small">Oldest to newest</span></div>
          {!revisions.length && <p className="muted">No feedback requested yet.</p>}
          {revisions.slice(page * 8, page * 8 + 8).map((v, i) => {
            const n = page * 8 + i;
            return <button key={v.id} className={`revision-item ${n === index ? "active" : ""}`} aria-current={n === index ? "step" : undefined} onClick={() => choose(n)}>
              <span className="row"><strong>{v.is_submission ? "Final submission" : `Revision ${n + 1}`}</strong>{v.is_submission && <Tag color="green">Final</Tag>}</span>
              <span className="small muted">{fmtDate(v.created_at, true)}</span>
              <span className="small faint">{v.words} words{n === 0 ? " · First saved draft" : ""}</span>
            </button>;
          })}
          <div className="review-pagination">
            <button className="btn" aria-label="Previous revision page" disabled={page === 0} onClick={() => choose((page - 1) * 8)}>{icons.back}</button>
            <span className="small muted">{page + 1} / {pages}</span>
            <button className="btn" aria-label="Next revision page" disabled={page + 1 >= pages} onClick={() => choose((page + 1) * 8)}>{icons.forward}</button>
          </div>
        </aside>
        <section className="revision-main" aria-label="Student writing">
          {revision && <section className="revision-feedback" aria-label="Feedback preceding this revision">
            <h2>{index === 0 ? "Initial writing" : `AI feedback from request ${index}`}</h2>
            {index === 0 ? <p className="muted small">The student's writing before their first AI feedback request.</p>
              : revision.preceding_feedback ? <>
                <p>{revision.preceding_feedback.content.summary}</p>
                {revision.preceding_feedback.content.items.map((item, i) => <div className="revision-feedback-item" key={i}>
                  <Tag color="purple">{item.rubric_area}</Tag>
                  {item.quote && <blockquote>{item.quote}</blockquote>}
                  <p>{item.comment}</p><p className="muted">{item.suggestion}</p>
                </div>)}
                <p className="small muted">The writing below shows the changes after this feedback, up to {revision.is_submission ? "final submission" : "the next feedback request"}.</p>
              </> : <p className="muted small">No feedback was returned for the preceding request. The saved writing is preserved below.</p>}
          </section>}
          <div className="revision-document">
            <div className="revision-document-toolbar">
              <div><h2>{revision ? revision.is_submission ? "Final submission" : `Revision ${index + 1}` : "Current draft"}</h2>
                <span className="muted small">{index === 0 ? "Initial writing · No prior AI feedback" : `Compared with revision ${index}`} · {wordCount(text)} words</span>
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
              <button className="btn" disabled={!revision || index === 0} onClick={() => choose(index - 1)}>{icons.back} Earlier</button>
              <span className="small muted">{revision?.is_submission ? "Final submitted version" : "Snapshot at feedback request"}</span>
              <button className="btn" disabled={!revision || index + 1 >= revisions.length} onClick={() => choose(index + 1)}>Later {icons.forward}</button>
            </div>
          </div>
          {w.data.grading_enabled ? <section className="review-grade" aria-label="Overall assignment grade">
            <div className="row wrap"><h2>Overall assignment grade</h2><span className="spacer" />
              {submission && <div className="review-grade-status">
                <Tag color={submission.released ? "green" : "gray"}>{submission.released ? "Released" : "Not released"}</Tag>
                <label className="row small"><input type="checkbox" checked={releaseOnSave} disabled={saving} onChange={e => setReleaseOnSave(e.target.checked)} />Directly Release</label>
              </div>}
            </div>
            <p className="muted small">One grade for the final submission, across all revisions.</p>
            {!submission ? <p className="muted">Grading opens after the student submits.</p> : <>
              <div className="row wrap small" style={{ marginBottom: 16 }}><span className="muted">Submitted {fmtDate(submission.submitted_at, true)}</span>
                <button className="btn" onClick={() => choose(revisions.length - 1)}>View final submission</button></div>
              <Field label="Student grade"><input id="overall-grade" className="input" maxLength={32} value={grade.grade} placeholder="e.g. 85 or A-" onChange={e => setGrade({ ...grade, grade: e.target.value })} /><span className="small muted">The student's assignment result. This does not train the bandit.</span></Field>
              <Field label="Overall comments"><textarea id="overall-comments" className="textarea" rows={4} value={grade.comments} placeholder="Feedback on the assignment as a whole…" onChange={e => setGrade({ ...grade, comments: e.target.value })} /></Field>
              <div className="form-actions wrap">
                <button className="btn primary" disabled={!grade.grade.trim() || saving} onClick={() => saveGrade(releaseOnSave)}>{saving ? releaseOnSave ? "Releasing…" : "Saving…" : releaseOnSave ? "Release" : "Save"}</button>
              </div>
              <p className="small muted">{releaseOnSave ? "Release will save and publish this grade and comments to the student." : "Save will keep this grade private, including changes to a previously released grade. You can release saved grades together from the student list."}</p>
            </>}
          </section> : <p className="muted small">Ungraded assignment · No grade is required.</p>}
          {submission && w.data.bandit_rating && <BanditRatingPanel key={submission.id} submissionId={submission.id} initial={w.data.bandit_rating} />}
        </section>
      </div>
    </div></div>
  </>;
}

interface BanditRatingStatus {
  rating: number | null;
  rated_at: string | null;
  rated_decisions: number;
  eligible_decisions: number;
}

function BanditRatingPanel({ submissionId, initial }: { submissionId: number; initial: BanditRatingStatus }) {
  const [status, setStatus] = useState(initial);
  const [rating, setRating] = useState<number | null>(initial.rating);
  const [saving, setSaving] = useState(false);
  const toast = useToast();
  const save = async () => {
    if (rating === null || saving) return;
    setSaving(true);
    try {
      const result = await api.post<BanditRatingStatus>(`/api/instructor/submissions/${submissionId}/bandit-rating`, { rating });
      setStatus(result);
      toast(`Bandit rating recorded for ${result.rated_decisions} feedback decisions`);
    } catch (e) { toast((e as Error).message, true); }
    finally { setSaving(false); }
  };
  const locked = status.rating !== null;
  return <section className="review-bandit-rating" aria-label="Bandit feedback rating">
    <h2>Bandit feedback rating</h2>
    <p className="small muted">How helpful was the AI feedback across this assignment? This instructor-only rating is separate from the student's grade.</p>
    <RatingScale label="AI feedback helpfulness" value={rating} onChange={setRating}
      low="Not helpful" high="Very helpful" disabled={locked || saving || status.eligible_decisions === 0} />
    {locked ? <p className="small" role="status">Recorded: {status.rating}/5 for {status.rated_decisions} feedback decisions. It adds to the reward only where the student's scoring window is still open; otherwise it is kept for evaluation.</p>
      : status.eligible_decisions === 0 ? <p className="muted small">No bandit decisions can receive this rating. Feedback may not use the bandit, or instructor rewards may be disabled.</p>
      : <>
        <p className="small muted">One shared rating for {status.eligible_decisions} feedback decisions. It is supplementary: it counts (weight b) only while the student's scoring window is open. Once recorded, it cannot be changed. Saving a student grade does not save this rating.</p>
        <button className="btn outline" disabled={rating === null || saving} onClick={save}>{saving ? "Recording…" : "Record bandit rating"}</button>
      </>}
  </section>;
}
