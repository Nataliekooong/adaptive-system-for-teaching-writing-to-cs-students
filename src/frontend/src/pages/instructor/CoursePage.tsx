import { useNavigate, useParams } from "react-router-dom";
import { api } from "../../api";
import type { Course } from "../../types";
import { Loading, PageHeader, Prop, Props, Tag, Topbar, useLoad, Views } from "../../ui";
import { COURSE_TABS, useInstructor } from "./InstructorLayout";
import {
  AssignmentsTab,
  ExperimentsTab,
  LibraryTab,
  ModulesTab,
  ResearchTab,
  ReviewTab,
  StudentsTab,
} from "./CourseTabs";

export default function CoursePage() {
  const { cid, tab = "assignments" } = useParams();
  const courseId = Number(cid);
  const nav = useNavigate();
  const { toggleSidebar, courses } = useInstructor();
  const course = useLoad(() => api.get<Course>(`/api/instructor/courses/${courseId}`), [courseId]);
  const summary = courses.find((c) => c.id === courseId);
  const c = course.data;
  const current = COURSE_TABS.find((t) => t.key === tab) ?? COURSE_TABS[0];

  return (
    <>
      <Topbar
        onToggleSidebar={toggleSidebar}
        crumbs={[{ label: c?.code ?? "…", icon: "🎓", to: `/i/courses/${courseId}` }, { label: current.label, icon: current.icon }]}
      />
      <div className="content">
        {!c ? <Loading error={course.error} /> : (
          <div className="page wide">
            <PageHeader icon="🎓" title={c.title} />
            <Props>
              <Prop icon="#" label="Code">{c.code}</Prop>
              <Prop icon="👥" label="Students">{summary?.students ?? "—"}</Prop>
              <Prop icon="🎯" label="Rubric areas">{c.rubric_areas.map((r) => <Tag key={r} color="purple">{r}</Tag>)}</Prop>
            </Props>
            <Views
              tabs={COURSE_TABS}
              active={current.key}
              onChange={(k) => nav(`/i/courses/${courseId}/${k}`)}
            />
            {current.key === "assignments" && <AssignmentsTab course={c} />}
            {current.key === "experiments" && <ExperimentsTab course={c} />}
            {current.key === "modules" && <ModulesTab course={c} onSaved={course.reload} />}
            {current.key === "review" && <ReviewTab course={c} />}
            {current.key === "students" && <StudentsTab course={c} />}
            {current.key === "library" && <LibraryTab course={c} />}
            {current.key === "research" && <ResearchTab course={c} />}
          </div>
        )}
      </div>
    </>
  );
}
