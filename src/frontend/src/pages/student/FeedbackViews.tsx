import { icons } from "../../icons";
import { useEffect, useRef } from "react";
import { timeAgo } from "../../config";
import type { Feedback } from "../../types";
import { RatingScale, Tag } from "../../ui";

export function RateButtons({ fb, onRate }: { fb: Feedback; onRate: (helpful: boolean) => void }) {
  return (
    <div className="fb-rate">
      <span>Was this helpful?</span>
      <button className={`icon-btn ${fb.student_helpful === true ? "sel" : ""}`} title="Helpful" onClick={() => onRate(true)}>{icons.helpful}</button>
      <button className={`icon-btn ${fb.student_helpful === false ? "sel" : ""}`} title="Not helpful" onClick={() => onRate(false)}>{icons.unhelpful}</button>
    </div>
  );
}

/** MAB6: the 1–5 score is the bandit reward. Students can change it; only on-demand feedback is scored. */
export function ScoreScale({ fb, onScore }: { fb: Feedback; onScore: (score: number) => void }) {
  return (
    <div className="fb-score">
      <RatingScale label="How useful was this feedback?" value={fb.student_score} onChange={onScore}
        low="Not useful" high="Very useful" />
    </div>
  );
}

/** Score (1–5) and helpfulness (👍/👎) controls; each is switched by its own module. */
export interface FeedbackActions {
  canRate: boolean; onRate: (f: Feedback, helpful: boolean) => void;
  canScore: boolean; onScore: (f: Feedback, score: number) => void;
}

function Actions({ fb, act }: { fb: Feedback; act: FeedbackActions }) {
  return (
    <>
      {act.canScore && fb.venue === "on_demand" && <ScoreScale fb={fb} onScore={(s) => act.onScore(fb, s)} />}
      {act.canRate && <RateButtons fb={fb} onRate={(h) => act.onRate(fb, h)} />}
    </>
  );
}

/** `compact` (real-time tips): skip the summary line and show the items directly. */
export function FeedbackBody({ fb, compact = false }: { fb: Feedback; compact?: boolean }) {
  const items = compact ? fb.content.items : fb.content.items.filter((it) => it.comment !== fb.content.summary);
  return (
    <>
      {!(compact && items.length) && (
        <div style={{ fontWeight: 500, marginBottom: items.length ? 6 : 0 }}>{fb.content.summary}</div>
      )}
      {items.map((it, i) => (
        <div className="fb-item" key={i}>
          <Tag color="purple">{it.rubric_area}</Tag>
          {it.quote && <div className="fb-quote">“{it.quote}”</div>}
          <div style={{ marginTop: 4 }}>{it.comment}</div>
          {it.suggestion && <div className="muted" style={{ marginTop: 2 }}>{it.suggestion}</div>}
        </div>
      ))}
    </>
  );
}

/** S15 condition "chat panel" */
export function ChatPanel({ items, act }: { items: Feedback[]; act: FeedbackActions }) {
  if (!items.length) {
    return <div className="empty">No feedback yet.<br />Click <b>Request feedback</b> when you want a second pair of eyes.</div>;
  }
  return (
    <>
      {items.map((f) => (
        <div key={f.id} style={{ marginBottom: 16 }}>
          <div className="row small faint" style={{ marginBottom: 4 }}>
            <span>{icons.writing} Writing tutor</span>
            {f.venue === "realtime" && <Tag color="orange">pop-up</Tag>}
            <span className="spacer" />
            <span>{timeAgo(f.created_at)}</span>
          </div>
          <div className="chat-bubble"><FeedbackBody fb={f} /></div>
          <Actions fb={f} act={act} />
        </div>
      ))}
    </>
  );
}

/** S15 condition "character with a speech bubble" */
export function CharacterPanel({ items, act }: { items: Feedback[]; act: FeedbackActions }) {
  const [latest, ...rest] = items;
  return (
    <>
      <div className="character">
        <div className="character-avatar">{icons.character}</div>
        <div className="speech">
          {latest ? <FeedbackBody fb={latest} /> : <span>Hoo! I'm Ollie. Ask me for feedback whenever you're ready.</span>}
          {latest && <Actions fb={latest} act={act} />}
        </div>
      </div>
      {rest.length > 0 && <div className="sb-section" style={{ paddingLeft: 0 }}>Earlier</div>}
      {rest.map((f) => (
        <div key={f.id} className="fb-card">
          <div className="small faint" style={{ marginBottom: 4 }}>{timeAgo(f.created_at)}</div>
          <FeedbackBody fb={f} />
          <Actions fb={f} act={act} />
        </div>
      ))}
    </>
  );
}

/**
 * Real-time presentations (popup / window / highlight note) — itself an A/B variable.
 * `anchorTop`: popup is placed just below the text that triggered it (px from the top of `.editor-wrap`).
 */
export function RealtimeView({ fb, mode, canRate, onRate, onDismiss, anchorTop }: {
  fb: Feedback; mode: string; canRate: boolean; onRate: (h: boolean) => void; onDismiss: () => void;
  anchorTop?: number | null;
}) {
  const popRef = useRef<HTMLDivElement>(null);
  const anchored = mode === "popup" && anchorTop != null;
  useEffect(() => {
    if (anchored) popRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [anchored, fb.id]);
  const body = (
    <>
      <FeedbackBody fb={fb} compact />
      <div className="row" style={{ marginTop: 6 }}>
        {canRate && <RateButtons fb={fb} onRate={onRate} />}
        <span className="spacer" />
        <button className="btn sm" onClick={onDismiss}>Dismiss</button>
      </div>
    </>
  );
  if (mode === "window") {
    return (
      <div className="rt-window">
        <div className="rt-window-bar"><span>{icons.realtime} Writing tip</span><span className="spacer" />
          <button className="icon-btn sm" title="Dismiss writing tip" onClick={onDismiss}>{icons.close}</button>
        </div>
        <div className="rt-window-body">{body}</div>
      </div>
    );
  }
  if (mode === "highlight") {
    return <div className="rt-highlight-note"><div className="small faint" style={{ marginBottom: 4 }}>{icons.highlight} About the highlighted text</div>{body}</div>;
  }
  return (
    <div ref={popRef} className={`rt-popup${anchored ? " anchored" : ""}`} style={anchored ? { top: anchorTop! } : undefined}>
      <div className="small faint" style={{ marginBottom: 4 }}>{icons.realtime} Quick tip</div>{body}
    </div>
  );
}
