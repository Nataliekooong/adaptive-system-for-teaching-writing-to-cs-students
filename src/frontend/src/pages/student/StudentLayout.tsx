import { useState } from "react";
import { Outlet, useNavigate, useOutletContext, useParams, useLocation } from "react-router-dom";
import { api } from "../../api";
import { useAuth } from "../../auth";
import type { Assignment } from "../../types";
import { useLoad } from "../../ui";
import Questionnaire from "./Questionnaire";

export type StudentAssignment = Assignment & { course_code: string; status: "in_progress" | "submitted" | "graded" };

interface Ctx {
  toggleSidebar: () => void;
  assignments: StudentAssignment[];
  reload: () => void;
}

export const useStudentCtx = () => useOutletContext<Ctx>();

const STATUS_ICON = { in_progress: "📝", submitted: "📨", graded: "✅" };

export default function StudentLayout() {
  const { me, logout } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const { aid } = useParams();
  const [collapsed, setCollapsed] = useState(false);
  const list = useLoad(() => api.get<StudentAssignment[]>("/api/student/assignments"), []);
  const courses = useLoad(
    () => api.get<{ id: number; code: string; questionnaire_required: boolean }[]>("/api/student/courses"), [],
  );
  const needsQuestionnaire = courses.data?.some((c) => c.questionnaire_required);
  const assignments = list.data ?? [];
  const byCourse = [...new Set(assignments.map((a) => a.course_code))];

  return (
    <div className="shell">
      <aside className={`sidebar ${collapsed ? "collapsed" : ""}`}>
        <div className="sidebar-inner">
          <div className="sb-workspace">
            <span className="sb-avatar">{me!.display_name[0]}</span>
            <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {me!.display_name}
            </span>
            <button className="icon-btn" title="Collapse sidebar" onClick={() => setCollapsed(true)}>«</button>
          </div>
          <div className="sb-scroll">
            <div className={`sb-item ${loc.pathname === "/s" ? "active" : ""}`} onClick={() => nav("/s")}>
              <span className="ico">🏠</span><span className="label">Home</span>
            </div>
            {byCourse.map((code) => (
              <div key={code}>
                <div className="sb-section">{code}</div>
                {assignments.filter((a) => a.course_code === code).map((a) => (
                  <div
                    key={a.id} className={`sb-item ${String(a.id) === aid ? "active" : ""}`}
                    onClick={() => nav(`/s/assignments/${a.id}`)}
                  >
                    <span className="ico">{STATUS_ICON[a.status]}</span>
                    <span className="label">{a.title}</span>
                  </div>
                ))}
              </div>
            ))}
          </div>
          <div className="sb-footer">
            <div className="sb-item" onClick={() => logout().then(() => nav("/login"))}>
              <span className="ico">↩︎</span><span className="label">Log out</span>
            </div>
          </div>
        </div>
      </aside>
      <main className="main">
        <Outlet context={{ toggleSidebar: () => setCollapsed(!collapsed), assignments, reload: list.reload } satisfies Ctx} />
      </main>
      {needsQuestionnaire && <Questionnaire onDone={courses.reload} />}
    </div>
  );
}
