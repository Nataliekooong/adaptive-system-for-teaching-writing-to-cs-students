import { icons } from "../../icons";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api";
import { useAuth } from "../../auth";
import { Field, Callout, Modal, PageHeader, Tag, Topbar, useToast } from "../../ui";
import { useInstructor } from "./InstructorLayout";

export default function InstructorHome() {
  const { me } = useAuth();
  const { toggleSidebar, courses, reloadCourses, registry } = useInstructor();
  const nav = useNavigate();
  const toast = useToast();
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ code: "", title: "" });

  const create = async () => {
    try {
      const c = await api.post<{ id: number }>("/api/instructor/courses", {
        ...form, rubric_areas: ["Thesis & Purpose", "Organization", "Clarity & Concision", "Technical Precision",
          "Evidence & Support", "Grammar & Mechanics", "Audience Awareness"],
      });
      reloadCourses();
      setCreating(false);
      nav(`/i/courses/${c.id}`);
    } catch (e) {
      toast((e as Error).message, true);
    }
  };

  return (
    <>
      <Topbar onToggleSidebar={toggleSidebar} crumbs={[{ label: "Home", icon: icons.home }]} />
      <div className="content">
        <div className="page wide">
          <PageHeader icon={icons.instructor} title={`Good to see you, ${me!.display_name}`} sub="Your courses, assignments and experiments" />
          <Callout icon={icons.modules} color="blue">
            Every part of the tutor is a <b>module</b> you can switch on or off — for a whole course, one assignment,
            one A/B condition, or one student. There are {registry.modules.length} modules today. Open a course's{" "}
            <b>A/B experiments</b> to compare configurations.
          </Callout>
          <div className="row" style={{ margin: "24px 0 10px" }}>
            <h2 className="h" style={{ margin: 0 }}>Courses</h2><span className="spacer" />
            <button className="btn primary" onClick={() => setCreating(true)}>New</button>
          </div>
          <div className="gallery">
            {courses.map((c) => (
              <div key={c.id} className="gallery-card" onClick={() => nav(`/i/courses/${c.id}`)}>
                <div className="gallery-cover" aria-hidden="true">{icons.course}</div>
                <div className="gallery-body">
                  <div style={{ fontWeight: 600 }}>{c.code}</div>
                  <div className="muted" style={{ marginBottom: 8 }}>{c.title}</div>
                  <div className="card-meta">
                    <Tag color="gray">{icons.students} {c.students} students</Tag>
                    <Tag color="gray">{icons.assignment} {c.assignments} assignments</Tag>
                    {!!c.active_experiments && <Tag color="green" dot>{c.active_experiments} live A/B</Tag>}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
      {creating && (
        <Modal onClose={() => setCreating(false)}>
          <h2 style={{ marginTop: 0 }}>New course</h2>
          <Field label="Code"><input className="input" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} placeholder="COMPSCI 4ZP6" /></Field>
          <Field label="Title"><input className="input" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></Field>
          <div className="form-actions"><button className="btn" onClick={() => setCreating(false)}>Cancel</button>
            <button className="btn primary" disabled={!form.code || !form.title} onClick={create}>Create</button></div>
        </Modal>
      )}
    </>
  );
}
