import { icons } from "../icons";
import { Field } from "../ui";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth";

// Seeded demo accounts (src/backend/app/seed.py). Replaced by McMaster SSO later.
const DEMO = [
  { u: "drlee", label: "Dr. Lee", role: "Instructor", icon: icons.instructor },
  { u: "priya", label: "Priya", role: "Student", icon: icons.student },
  { u: "marcus", label: "Marcus", role: "Student", icon: icons.developer },
  { u: "alex", label: "Alex", role: "Student", icon: icons.student },
];

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const go = async (u: string, p: string) => {
    setBusy(true);
    setError("");
    try {
      const me = await login(u, p);
      nav(me.role === "student" ? "/s" : "/i", { replace: true });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    go(username, password);
  };

  return (
    <div className="login-wrap">
      <div className="login-box">
        <div className="dialog-icon" aria-hidden="true">{icons.writing}</div>
        <h1 className="login-title">Adaptive Writing Tutor</h1>
        <div className="muted" style={{ marginBottom: 24 }}>Sign in with your McMaster account</div>
        <form onSubmit={submit}>
          <Field label="MacID">
            <input className="input" autoFocus value={username} onChange={(e) => setUsername(e.target.value)} />
          </Field>
          <Field label="Password">
            <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
          </Field>
          {error && <div className="form-error" role="alert">{error}</div>}
          <button className="btn primary full-width" disabled={busy}>
            Continue
          </button>
        </form>
        <div className="divider" style={{ margin: "24px 0 12px" }} />
        <div className="muted small">Demo accounts (dev only)</div>
        <div className="demo-users">
          {DEMO.map((d) => (
            <button key={d.u} className="demo-user" onClick={() => go(d.u, "password")} disabled={busy}>
              <div>{d.icon} <b>{d.label}</b></div>
              <div className="faint small">{d.role} · {d.u}</div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
