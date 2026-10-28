import { useState } from "react";
import { api } from "../../api";
import { Modal, useToast } from "../../ui";

function Scale({ value, onChange, low, high }: { value: number; onChange: (v: number) => void; low: string; high: string }) {
  return (
    <div>
      <div className="stars">
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n} type="button" onClick={() => onChange(n)}
            style={n === value ? { background: "var(--blue)", color: "#fff" } : undefined}
          >{n}</button>
        ))}
      </div>
      <div className="row faint small" style={{ width: 186, marginTop: 2 }}><span>{low}</span><span className="spacer" /><span>{high}</span></div>
    </div>
  );
}

/** S2: first-login questionnaire → initial learner profile. */
export default function Questionnaire({ onDone }: { onDone: () => void }) {
  const toast = useToast();
  const [v, setV] = useState({ writing_confidence: 3, technical_experience: 3, year_of_study: 2,
                               english_first_language: true, goals: "" });
  const save = async () => {
    await api.post("/api/student/questionnaire", v);
    toast("Thanks — your feedback will be tailored to you.");
    onDone();
  };
  return (
    <Modal onClose={() => undefined}>
      <div style={{ fontSize: 40 }}>👋</div>
      <h2 style={{ fontSize: 22, margin: "6px 0 2px" }}>Welcome! A few quick questions</h2>
      <div className="muted" style={{ marginBottom: 20 }}>This helps the tutor pick feedback that suits you. Takes under a minute.</div>
      <div className="field">
        <label>How confident are you in your writing?</label>
        <Scale value={v.writing_confidence} onChange={(n) => setV({ ...v, writing_confidence: n })} low="Not at all" high="Very" />
      </div>
      <div className="field">
        <label>How much technical (CS) experience do you have?</label>
        <Scale value={v.technical_experience} onChange={(n) => setV({ ...v, technical_experience: n })} low="Little" high="A lot" />
      </div>
      <div className="grid2">
        <div className="field">
          <label>Year of study</label>
          <select className="select" value={v.year_of_study} onChange={(e) => setV({ ...v, year_of_study: +e.target.value })}>
            {[1, 2, 3, 4, 5, 6].map((y) => <option key={y} value={y}>Year {y}</option>)}
          </select>
        </div>
        <div className="field">
          <label>Is English your first language?</label>
          <select className="select" value={v.english_first_language ? "y" : "n"}
                  onChange={(e) => setV({ ...v, english_first_language: e.target.value === "y" })}>
            <option value="y">Yes</option><option value="n">No</option>
          </select>
        </div>
      </div>
      <div className="field">
        <label>What would you like to improve? (optional)</label>
        <textarea className="textarea" value={v.goals} onChange={(e) => setV({ ...v, goals: e.target.value })} />
      </div>
      <div className="row"><span className="spacer" /><button className="btn primary" onClick={save}>Start writing</button></div>
    </Modal>
  );
}
