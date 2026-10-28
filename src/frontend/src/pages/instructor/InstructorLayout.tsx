import { useState } from "react";
import { Outlet, useLocation, useNavigate, useOutletContext } from "react-router-dom";
import { api } from "../../api";
import { useAuth } from "../../auth";
import type { Course, Registry } from "../../types";
import { Loading, useLoad } from "../../ui";

interface Ctx {
  toggleSidebar: () => void;
  registry: Registry;
  reloadRegistry: () => void;
  courses: Course[];
  reloadCourses: () => void;
}

export const useInstructor = () => useOutletContext<Ctx>();

export const COURSE_TABS = [
  { key: "assignments", label: "Assignments", icon: "📝" },
  { key: "experiments", label: "A/B experiments", icon: "🧪" },
  { key: "modules", label: "Course modules", icon: "🧩" },
  { key: "review", label: "Review queue", icon: "⭐" },
  { key: "students", label: "Students", icon: "👥" },
  { key: "library", label: "Feedback library", icon: "📚" },
  { key: "research", label: "Research data", icon: "📊" },
];

export default function InstructorLayout() {
  const { me, logout } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [openCourse, setOpenCourse] = useState<Record<number, boolean>>({});
  const registry = useLoad(() => api.get<Registry>("/api/modules"), []);
  const courses = useLoad(() => api.get<Course[]>("/api/instructor/courses"), []);

  if (!registry.data || !courses.data) return <Loading error={registry.error ?? courses.error} />;

  return (
    <div className="shell">
      <aside className={`sidebar ${collapsed ? "collapsed" : ""}`}>
        <div className="sidebar-inner">
          <div className="sb-workspace">
            <span className="sb-avatar">✍</span>
            <span style={{ flex: 1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              {me!.display_name}'s Workspace
            </span>
            <button className="icon-btn" title="Collapse sidebar" onClick={() => setCollapsed(true)}>«</button>
          </div>
          <div className="sb-scroll">
            <div className={`sb-item ${loc.pathname === "/i" ? "active" : ""}`} onClick={() => nav("/i")}>
              <span className="ico">🏠</span><span className="label">Home</span>
            </div>
            <div className="sb-section">Courses</div>
            {courses.data.map((c) => {
              const open = openCourse[c.id] ?? true;
              const base = `/i/courses/${c.id}`;
              return (
                <div key={c.id}>
                  <div
                    className={`sb-item ${loc.pathname === base ? "active" : ""}`}
                    onClick={() => nav(base)}
                  >
                    <span
                      className={`caret ${open ? "open" : ""}`} style={{ width: 16 }}
                      onClick={(e) => { e.stopPropagation(); setOpenCourse({ ...openCourse, [c.id]: !open }); }}
                    >▶</span>
                    <span className="ico">🎓</span>
                    <span className="label">{c.code}</span>
                  </div>
                  {open && COURSE_TABS.map((t) => (
                    <div
                      key={t.key}
                      className={`sb-item sub ${loc.pathname === `${base}/${t.key}` ? "active" : ""}`}
                      onClick={() => nav(`${base}/${t.key}`)}
                    >
                      <span className="ico">{t.icon}</span><span className="label">{t.label}</span>
                      {t.key === "experiments" && !!c.active_experiments && <span className="meta">{c.active_experiments} live</span>}
                    </div>
                  ))}
                </div>
              );
            })}
          </div>
          <div className="sb-footer">
            <div className="sb-item" onClick={() => logout().then(() => nav("/login"))}>
              <span className="ico">↩︎</span><span className="label">Log out</span>
            </div>
          </div>
        </div>
      </aside>
      <main className="main">
        <Outlet context={{
          toggleSidebar: () => setCollapsed(!collapsed), registry: registry.data, reloadRegistry: registry.reload,
          courses: courses.data, reloadCourses: courses.reload,
        } satisfies Ctx} />
      </main>
    </div>
  );
}
