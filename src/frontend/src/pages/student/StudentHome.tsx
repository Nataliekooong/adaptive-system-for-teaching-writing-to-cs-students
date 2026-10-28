import { useNavigate } from "react-router-dom";
import { useAuth } from "../../auth";
import { fmtDate } from "../../config";
import { Board, PageHeader, Tag, Topbar } from "../../ui";
import { useStudentCtx, type StudentAssignment } from "./StudentLayout";

export default function StudentHome() {
  const { me } = useAuth();
  const { toggleSidebar, assignments } = useStudentCtx();
  const nav = useNavigate();
  const col = (s: StudentAssignment["status"]) => assignments.filter((a) => a.status === s);
  return (
    <>
      <Topbar onToggleSidebar={toggleSidebar} crumbs={[{ label: "Home", icon: "🏠" }]} />
      <div className="content">
        <div className="page wide">
          <PageHeader icon="📚" title={`Hi, ${me!.display_name.split(" ")[0]}`} sub="Your writing assignments" />
          <Board
            columns={[
              { key: "in_progress", label: "In progress", color: "yellow", items: col("in_progress") },
              { key: "submitted", label: "Submitted", color: "blue", items: col("submitted") },
              { key: "graded", label: "Graded", color: "green", items: col("graded") },
            ]}
            renderCard={(a) => (
              <div key={a.id} className="card" onClick={() => nav(`/s/assignments/${a.id}`)}>
                <div className="card-title">{a.title}</div>
                <div className="card-meta">
                  <Tag color="gray">{a.course_code}</Tag>
                  <span>Due {fmtDate(a.due_date)}</span>
                </div>
              </div>
            )}
          />
        </div>
      </div>
    </>
  );
}
