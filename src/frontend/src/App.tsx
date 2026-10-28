import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import Login from "./pages/Login";
import StudentLayout from "./pages/student/StudentLayout";
import StudentHome from "./pages/student/StudentHome";
import Workspace from "./pages/student/Workspace";
import InstructorLayout from "./pages/instructor/InstructorLayout";
import InstructorHome from "./pages/instructor/InstructorHome";
import CoursePage from "./pages/instructor/CoursePage";
import AssignmentPage from "./pages/instructor/AssignmentPage";
import ExperimentPage from "./pages/instructor/ExperimentPage";
import StudentWorkPage from "./pages/instructor/StudentWorkPage";
import StudentProfilePage from "./pages/instructor/StudentProfilePage";
import { Loading } from "./ui";

export default function App() {
  const { me, loading } = useAuth();
  if (loading) return <Loading />;
  if (!me) {
    return (
      <Routes>
        <Route path="*" element={<Login />} />
      </Routes>
    );
  }
  if (me.role === "student") {
    return (
      <Routes>
        <Route element={<StudentLayout />}>
          <Route path="/s" element={<StudentHome />} />
          <Route path="/s/assignments/:aid" element={<Workspace />} />
        </Route>
        <Route path="*" element={<Navigate to="/s" replace />} />
      </Routes>
    );
  }
  return (
    <Routes>
      <Route element={<InstructorLayout />}>
        <Route path="/i" element={<InstructorHome />} />
        <Route path="/i/courses/:cid" element={<CoursePage />} />
        <Route path="/i/courses/:cid/:tab" element={<CoursePage />} />
        <Route path="/i/courses/:cid/students/:sid" element={<StudentProfilePage />} />
        <Route path="/i/assignments/:aid" element={<AssignmentPage />} />
        <Route path="/i/assignments/:aid/students/:sid" element={<StudentWorkPage />} />
        <Route path="/i/experiments/:eid" element={<ExperimentPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/i" replace />} />
    </Routes>
  );
}
