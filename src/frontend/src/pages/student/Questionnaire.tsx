import { icons } from "../../icons";
import { useState } from "react";
import { api } from "../../api";
import { Field, Modal, RatingScale, useToast } from "../../ui";

/** S2: first-login questionnaire → initial learner profile. */
export default function Questionnaire({ onDone }: { onDone: () => void }) {
  const toast = useToast();
  const [saving, setSaving] = useState(false);
  const [v, setV] = useState({ writing_confidence: 3, technical_experience: 3, year_of_study: 2,
                               english_first_language: true, goals: "" });
  const save = async () => {
    if (saving) return;
    setSaving(true);
    try {
      await api.post("/api/student/questionnaire", v);
      toast("Thanks — your feedback will be tailored to you.");
      onDone();
    } catch (e) { toast((e as Error).message, true); }
    finally { setSaving(false); }
  };
  return (
    <Modal onClose={() => undefined}>
      <div className="dialog-icon" aria-hidden="true">{icons.welcome}</div>
      <h2>Welcome! A few quick questions</h2>
      <p className="muted">This helps the tutor pick feedback that suits you. Takes under a minute.</p>
      <RatingScale label="How confident are you in your writing?" value={v.writing_confidence}
        onChange={(n) => setV({ ...v, writing_confidence: n })} low="Not at all" high="Very" disabled={saving} />
      <RatingScale label="How much technical (CS) experience do you have?" value={v.technical_experience}
        onChange={(n) => setV({ ...v, technical_experience: n })} low="Little" high="A lot" disabled={saving} />
      <div className="grid2">
        <Field label="Year of study">
          <select className="select" disabled={saving} value={v.year_of_study} onChange={(e) => setV({ ...v, year_of_study: +e.target.value })}>
            {[1, 2, 3, 4, 5, 6].map((y) => <option key={y} value={y}>Year {y}</option>)}
          </select>
        </Field>
        <Field label="Is English your first language?">
          <select className="select" disabled={saving} value={v.english_first_language ? "y" : "n"}
                  onChange={(e) => setV({ ...v, english_first_language: e.target.value === "y" })}>
            <option value="y">Yes</option><option value="n">No</option>
          </select>
        </Field>
      </div>
      <Field label="What would you like to improve? (optional)">
        <textarea className="textarea" disabled={saving} value={v.goals} onChange={(e) => setV({ ...v, goals: e.target.value })} />
      </Field>
      <div className="form-actions"><button className="btn primary" disabled={saving} onClick={save}>{saving ? "Saving…" : "Start writing"}</button></div>
    </Modal>
  );
}
