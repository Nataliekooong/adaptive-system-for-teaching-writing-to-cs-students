import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth";

// Seeded demo accounts (src/backend/app/seed.py). Replaced by McMaster SSO later.
const DEMO = [
  { u: "drlee", label: "Dr. Lee", role: "Instructor", icon: "🧑‍🏫" },
  { u: "priya", label: "Priya", role: "Student", icon: "🧑‍🎓" },
  { u: "marcus", label: "Marcus", role: "Student", icon: "🧑‍💻" },
  { u: "alex", label: "Alex", role: "Student", icon: "🧑‍🎓" },
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
        <div style={{ fontSize: 44, marginBottom: 8 }}>✍️</div>
        <h1 style={{ fontSize: 26, fontWeight: 700, margin: "0 0 4px" }}>Adaptive Writing Tutor</h1>
        <div className="muted" style={{ marginBottom: 24 }}>Sign in with your McMaster account</div>
        <form onSubmit={submit}>
          <div className="field">
            <label>MacID</label>
            <input className="input" autoFocus value={username} onChange={(e) => setUsername(e.target.value)} />
          </div>
          <div className="field">
            <label>Password</label>
            <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>
          {error && <div style={{ color: "var(--red)", marginBottom: 10 }}>{error}</div>}
          <button className="btn primary" style={{ width: "100%", justifyContent: "center", height: 34 }} disabled={busy}>
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
