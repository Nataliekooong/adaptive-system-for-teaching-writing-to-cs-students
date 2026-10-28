import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../../api";
import { fmtDate, wordCount } from "../../config";
import type { Assignment, Feedback, UserRef } from "../../types";
import { Callout, Loading, PageHeader, Prop, Props, Tag, Topbar, useLoad, useToast, Views } from "../../ui";
import { useInstructor } from "./InstructorLayout";

interface Work {
  student: UserRef;
  draft: string;
  submission: { id: number; content: string; submitted_at: string; grade: string | null; comments: string; released: boolean } | null;
  feedback: Feedback[];
  versions: { id: number; kind: string; created_at: string; words: number; preview: string }[];
}

/** I8: a student's work on an assignment, their feedback history, and grading. */
export default function StudentWorkPage() {
  const { aid, sid } = useParams();
  const toast = useToast();
  const { toggleSidebar } = useInstructor();
  const a = useLoad(() => api.get<Assignment>(`/api/instructor/assignments/${aid}`), [aid]);
  const w = useLoad(() => api.get<Work>(`/api/instructor/assignments/${aid}/students/${sid}/work`), [aid, sid]);
  const [tab, setTab] = useState("work");
  const [grade, setGrade] = useState({ grade: "", comments: "" });
  useEffect(() => {
    if (w.data?.submission) setGrade({ grade: w.data.submission.grade ?? "", comments: w.data.submission.comments });
  }, [w.data]);

  if (!w.data || !a.data) return <><Topbar onToggleSidebar={toggleSidebar} crumbs={[{ label: "…" }]} /><Loading error={w.error ?? a.error} /></>;
  const { student, submission, feedback } = w.data;
  const text = submission?.content ?? w.data.draft;

  const saveGrade = async (release: boolean) => {
    try {
      await api.post(`/api/instructor/submissions/${submission!.id}/grade`, grade);
      if (release) await api.post(`/api/instructor/assignments/${aid}/release`, { submission_ids: [submission!.id] });
      toast(release ? "Grade saved and released" : "Grade saved (hidden until released)");
      w.reload();
    } catch (e) {
      toast((e as Error).message, true);
    }
  };

  return (
    <>
      <Topbar
        onToggleSidebar={toggleSidebar}
        crumbs={[
          { label: a.data.title, icon: "📝", to: `/i/assignments/${aid}` },
          { label: student.display_name, icon: "🧑‍🎓" },
        ]}
      />
      <div className="content">
        <div className="page wide">
          <PageHeader icon="🧑‍🎓" title={student.display_name} />
          <Props>
            <Prop icon="🆔" label="MacID">{student.username} <span className="faint mono">{student.pseudonym}</span></Prop>
            <Prop icon="◉" label="Status">
              {submission ? <Tag dot color={submission.released ? "green" : "blue"}>{submission.released ? "Graded · released" : "Submitted"}</Tag> : <Tag dot color="yellow">In progress</Tag>}
              {submission && <span className="faint">{fmtDate(submission.submitted_at, true)}</span>}
            </Prop>
            <Prop icon="#" label="Length">{wordCount(text)} words · {w.data.versions.length} versions · {feedback.length} feedback</Prop>
          </Props>
          <Views
            tabs={[
              { key: "work", label: submission ? "Submission" : "Current draft", icon: "📄" },
              { key: "feedback", label: "Feedback history", icon: "💬", count: feedback.length },
              { key: "versions", label: "Versions", icon: "🕘", count: w.data.versions.length },
            ]}
            active={tab} onChange={setTab}
          />
          {tab === "work" && (
            <div className="grid2" style={{ gridTemplateColumns: "1.6fr 1fr", alignItems: "start" }}>
              <div className="prewrap" style={{ fontFamily: "var(--serif)", fontSize: 16, lineHeight: 1.7 }}>
                {text || <span className="faint">Nothing written yet.</span>}
              </div>
              <div className="fb-card" style={{ position: "sticky", top: 8 }}>
                <h3 className="h" style={{ marginTop: 0 }}>🎓 Grade</h3>
                {!submission ? <div className="faint">Grading opens after the student submits.</div> : (
                  <>
                    <div className="field"><label>Grade</label><input className="input" value={grade.grade} placeholder="e.g. 85 or A-" onChange={(e) => setGrade({ ...grade, grade: e.target.value })} /></div>
                    <div className="field"><label>Comments</label><textarea className="textarea" rows={6} value={grade.comments} onChange={(e) => setGrade({ ...grade, comments: e.target.value })} /></div>
                    <div className="row"><span className="spacer" />
                      <button className="btn outline" disabled={!grade.grade} onClick={() => saveGrade(false)}>Save</button>
                      <button className="btn primary" disabled={!grade.grade} onClick={() => saveGrade(true)}>Save & release</button>
                    </div>
                  </>
                )}
              </div>
            </div>
          )}
          {tab === "feedback" && (
            <>
              {feedback.length === 0 && <div className="empty">No feedback requested yet.</div>}
              {feedback.map((f) => (
                <div key={f.id} className="fb-card">
                  <div className="row wrap small" style={{ marginBottom: 6, gap: 4 }}>
                    <Tag color={f.venue === "realtime" ? "orange" : "blue"}>{f.venue === "realtime" ? `⚡ real-time · ${f.trigger}` : "💬 on-demand"}</Tag>
                    <Tag color="gray">{f.source}</Tag>
                    {f.style && <Tag color="purple">style: {f.style}</Tag>}
                    <Tag color="gray">{f.presentation}</Tag>
                    <Tag color={f.guardrail_status === "approved" ? "green" : "yellow"}>guardrail: {f.guardrail_status}</Tag>
                    {f.student_helpful !== null && <Tag color={f.student_helpful ? "green" : "red"}>student: {f.student_helpful ? "👍" : "👎"}</Tag>}
                    {f.instructor_rating && <Tag color="blue">instructor: {f.instructor_rating}/5</Tag>}
                    {f.dismissed && <Tag color="gray">dismissed</Tag>}
                    <span className="spacer" /><span className="faint">{fmtDate(f.created_at, true)} · {f.model_version} · {f.prompt_template}</span>
                  </div>
                  <b>{f.content.summary}</b>
                  {f.content.items.map((x, i) => (
                    <div key={i} style={{ marginTop: 4 }}><Tag color="purple">{x.rubric_area}</Tag> {x.comment} <span className="muted">{x.suggestion}</span></div>
                  ))}
                </div>
              ))}
            </>
          )}
          {tab === "versions" && (
            <>
              <Callout icon="🕘">Snapshots around feedback rounds and paste events, so revisions can be compared (S5, B9).</Callout>
              <table className="table">
                <tbody>
                  {w.data.versions.map((v) => (
                    <tr key={v.id}>
                      <td style={{ whiteSpace: "nowrap" }}>{fmtDate(v.created_at, true)}</td>
                      <td><Tag color={v.kind.startsWith("paste") ? "orange" : v.kind === "feedback_request" ? "blue" : "gray"}>{v.kind.replace("_", " ")}</Tag></td>
                      <td>{v.words}w</td>
                      <td className="muted small">{v.preview}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </div>
      </div>
    </>
  );
}
