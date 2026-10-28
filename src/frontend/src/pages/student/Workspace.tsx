import { useCallback, useEffect, useLayoutEffect, useRef, useState, type ClipboardEvent, type KeyboardEvent } from "react";
import { useParams } from "react-router-dom";
import { api, ApiError } from "../../api";
import { fmtDate, timeAgo, wordCount } from "../../config";
import type { Assignment, Config, Feedback } from "../../types";
import { Callout, Loading, Modal, PageHeader, Prop, Props, Tag, ToggleBlock, Topbar, useToast } from "../../ui";
import { CharacterPanel, ChatPanel, RealtimeView } from "./FeedbackViews";
import { useStudentCtx } from "./StudentLayout";
import { useRealtimeTriggers, type Trigger } from "./useRealtime";

interface Detail {
  assignment: Assignment;
  config: Config;
  draft: { content: string; updated_at: string; locked: boolean; last_saved_version_id: number | null };
  submission: { id: number; submitted_at: string; released: boolean; grade?: string; comments?: string } | null;
}

interface Version { id: number; kind: string; created_at: string; words: number; preview: string }

type SaveState = "saved" | "unsaved" | "saving" | "error";

const KIND_LABEL: Record<string, string> = {
  manual: "Saved", autosave: "Autosave", feedback_request: "Feedback requested", paste_before: "Before paste",
  paste_after: "After paste", restore: "Restored", submit: "Submitted",
};

export default function Workspace() {
  const { aid } = useParams();
  const id = Number(aid);
  const toast = useToast();
  const { toggleSidebar, reload: reloadList } = useStudentCtx();

  const [d, setD] = useState<Detail>();
  const [loadError, setLoadError] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [saveState, setSaveState] = useState<SaveState>("saved");
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const hist = useRef<{ stack: string[]; idx: number; last: number }>({ stack: [""], idx: 0, last: 0 });
  const [, force] = useState(0);
  const [feedback, setFeedback] = useState<Feedback[]>([]);
  const [busyFb, setBusyFb] = useState(false);
  const [panelOpen, setPanelOpen] = useState(true);
  const [rt, setRt] = useState<{ fb: Feedback; excerpt: string } | null>(null);
  const rtCount = useRef(0);
  const [getStarted, setGetStarted] = useState<string | null>(null);
  const [versions, setVersions] = useState<Version[] | null>(null);
  const [confirm, setConfirm] = useState<"restore" | "submit" | null>(null);
  const [submitProblems, setSubmitProblems] = useState<string[]>([]);
  const ta = useRef<HTMLTextAreaElement>(null);
  const textRef = useRef(text);
  textRef.current = text;

  const load = useCallback(async () => {
    try {
      const det = await api.get<Detail>(`/api/student/assignments/${id}`);
      setD(det);
      setText(det.draft.content);
      setSavedAt(det.draft.updated_at);
      setSaveState("saved");
      hist.current = { stack: [det.draft.content], idx: 0, last: 0 };
      setFeedback(await api.get<Feedback[]>(`/api/student/assignments/${id}/feedback`));
      setLoadError(null);
    } catch (e) {
      setLoadError((e as Error).message);
    }
  }, [id]);

  useEffect(() => {
    setD(undefined);
    setRt(null);
    rtCount.current = 0;
    setGetStarted(null);
    load();
  }, [load]);

  const cfg = d?.config;
  const locked = !!d?.draft.locked;
  const pasteAllowed = !cfg || !cfg.paste_control.enabled || !!cfg.paste_control.allow_paste;

  // ---------- saving ----------
  const save = useCallback(async (kind: "manual" | "autosave") => {
    if (locked) return;
    const content = textRef.current;
    setSaveState("saving");
    try {
      const r = await api.put<{ updated_at: string }>(`/api/student/assignments/${id}/draft`, { content, kind });
      setSavedAt(r.updated_at);
      setSaveState(textRef.current === content ? "saved" : "unsaved");
      if (kind === "manual") toast("Saved");
    } catch (e) {
      setSaveState("error");
      toast(`Couldn't save: ${(e as Error).message}`, true);
    }
  }, [id, locked, toast]);

  // Autosave (NFR: ≤ 30 s of work lost)
  useEffect(() => {
    if (saveState !== "unsaved" || !cfg) return;
    const secs = cfg.version_history.enabled ? (cfg.version_history.autosave_seconds as number) : 15;
    const t = setTimeout(() => save("autosave"), secs * 1000);
    return () => clearTimeout(t);
  }, [saveState, text, cfg, save]);

  useEffect(() => {
    const h = (e: BeforeUnloadEvent) => { if (saveState === "unsaved") e.preventDefault(); };
    window.addEventListener("beforeunload", h);
    return () => window.removeEventListener("beforeunload", h);
  }, [saveState]);

  // ---------- editing & undo/redo (S6) ----------
  const applyText = (next: string, pushHistory = true) => {
    setText(next);
    setSaveState("unsaved");
    if (!pushHistory) return;
    const h = hist.current;
    const now = Date.now();
    h.stack = h.stack.slice(0, h.idx + 1);
    if (now - h.last < 700 && h.idx > 0) h.stack[h.idx] = next; // group fast keystrokes
    else { h.stack.push(next); h.idx++; }
    if (h.stack.length > 300) { h.stack.shift(); h.idx--; }
    h.last = now;
    force((x) => x + 1);
  };
  const undo = () => {
    const h = hist.current;
    if (h.idx === 0) return;
    h.idx--; h.last = 0;
    applyText(h.stack[h.idx], false);
    force((x) => x + 1);
  };
  const redo = () => {
    const h = hist.current;
    if (h.idx >= h.stack.length - 1) return;
    h.idx++; h.last = 0;
    applyText(h.stack[h.idx], false);
    force((x) => x + 1);
  };
  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    const mod = e.metaKey || e.ctrlKey;
    if (!mod) return;
    const k = e.key.toLowerCase();
    if (k === "z" && !e.shiftKey) { e.preventDefault(); undo(); }
    else if ((k === "z" && e.shiftKey) || k === "y") { e.preventDefault(); redo(); }
    else if (k === "s") { e.preventDefault(); save("manual"); }
  };

  // Paste (S14)
  const onPaste = async (e: ClipboardEvent<HTMLTextAreaElement>) => {
    e.preventDefault();
    const pasted = e.clipboardData.getData("text/plain");
    if (!pasted) return;
    if (!pasteAllowed) {
      toast("Pasting is turned off for this assignment so your instructor can see your own writing process.", true);
      api.post(`/api/student/assignments/${id}/paste`, { before: "", after: "", chars: pasted.length }).catch(() => undefined);
      return;
    }
    const el = e.currentTarget;
    const before = text;
    const after = text.slice(0, el.selectionStart) + pasted + text.slice(el.selectionEnd);
    const caret = el.selectionStart + pasted.length;
    applyText(after);
    requestAnimationFrame(() => el.setSelectionRange(caret, caret));
    api.post(`/api/student/assignments/${id}/paste`, { before, after, chars: pasted.length }).catch(() => undefined);
  };

  // Auto-grow the page-like editor.
  useLayoutEffect(() => {
    const el = ta.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.max(el.scrollHeight, 420)}px`;
  }, [text, d]);

  // ---------- feedback ----------
  const requestFeedback = async () => {
    setBusyFb(true);
    setPanelOpen(true);
    try {
      const f = await api.post<Feedback>(`/api/student/assignments/${id}/feedback`, { content: text });
      setFeedback((xs) => [f, ...xs]);
      setSaveState("saved");
      setSavedAt(new Date().toISOString());
    } catch (e) {
      toast((e as Error).message, true);
    } finally {
      setBusyFb(false);
    }
  };

  const rate = async (f: Feedback, helpful: boolean) => {
    try {
      const upd = await api.post<Feedback>(`/api/student/feedback/${f.id}/rating`, { helpful });
      setFeedback((xs) => xs.map((x) => (x.id === f.id ? upd : x)));
      setRt((cur) => (cur && cur.fb.id === f.id ? { ...cur, fb: upd } : cur));
    } catch (e) {
      toast((e as Error).message, true);
    }
  };

  const fireRealtime = useCallback(async (trigger: Trigger, excerpt: string) => {
    if (rt) return;
    try {
      const r = await api.post<{ feedback: Feedback | null }>(`/api/student/assignments/${id}/realtime`, {
        excerpt, trigger, session_count: rtCount.current,
      });
      if (r.feedback) {
        rtCount.current++;
        setRt({ fb: r.feedback, excerpt });
        setFeedback((xs) => [r.feedback!, ...xs]);
      }
    } catch { /* real-time tips are best-effort */ }
  }, [id, rt]);

  useRealtimeTriggers(text, cfg, !locked && !rt, fireRealtime);

  const dismissRt = () => {
    if (rt) api.post(`/api/student/feedback/${rt.fb.id}/dismiss`).catch(() => undefined);
    setRt(null);
  };

  // ---------- other actions ----------
  const openGetStarted = async () => {
    try {
      const r = await api.post<{ content: string }>(`/api/student/assignments/${id}/get-started`);
      setGetStarted(r.content || "Your instructor hasn't added a Get Started outline yet.");
    } catch (e) {
      toast((e as Error).message, true);
    }
  };

  const openVersions = async () => setVersions(await api.get<Version[]>(`/api/student/assignments/${id}/versions`));

  const restore = async (versionId?: number) => {
    try {
      const r = await api.post<{ content: string }>(`/api/student/assignments/${id}/restore`, { version_id: versionId ?? null });
      applyText(r.content);
      setSaveState("saved");
      setVersions(null);
      setConfirm(null);
      toast("Restored saved version");
    } catch (e) {
      toast((e as Error).message, true);
    }
  };

  const submit = async () => {
    try {
      await api.post(`/api/student/assignments/${id}/submit`, { content: text });
      setConfirm(null);
      toast("Submitted 🎉");
      reloadList();
      load();
    } catch (e) {
      if (e instanceof ApiError && e.status === 422) {
        setSubmitProblems((e.detail as { problems: string[] }).problems ?? [e.message]);
      } else toast((e as Error).message, true);
    }
  };

  if (!d || !cfg) return <><Topbar onToggleSidebar={toggleSidebar} crumbs={[{ label: "…" }]} /><Loading error={loadError} /></>;

  const a = d.assignment;
  const words = wordCount(text);
  const paras = text.split(/\n\s*\n/).filter((p) => p.trim()).length;
  const rules = cfg.submission_rules;
  const minWords = rules.enabled ? (rules.min_words as number) : 0;
  const minParas = rules.enabled ? (rules.min_paragraphs as number) : 0;
  const showPanel = cfg.on_demand_feedback.enabled || cfg.realtime_feedback.enabled;
  const canRate = cfg.student_rating.enabled;
  const presentation = cfg.feedback_presentation.enabled ? String(cfg.feedback_presentation.mode) : "chat_panel";
  const rtMode = String(cfg.realtime_feedback.presentation);
  const canUndo = hist.current.idx > 0;
  const canRedo = hist.current.idx < hist.current.stack.length - 1;

  // highlight presentation: mark the excerpt that triggered the tip
  let hlStart = -1, hlEnd = -1;
  if (rt && rtMode === "highlight" && rt.excerpt) {
    hlStart = text.lastIndexOf(rt.excerpt);
    hlEnd = hlStart >= 0 ? hlStart + rt.excerpt.length : -1;
  }

  const saveLabel = locked ? "Read-only · submitted"
    : saveState === "saving" ? "Saving…"
    : saveState === "unsaved" ? "Unsaved changes"
    : saveState === "error" ? "⚠️ Not saved"
    : savedAt ? `Saved ${timeAgo(savedAt)}` : "Saved";

  return (
    <>
      <Topbar
        onToggleSidebar={toggleSidebar}
        crumbs={[{ label: "Home", icon: "🏠", to: "/s" }, { label: a.title, icon: "📝" }]}
        right={
          <div className="ws-toolbar">
            <span className="save-state">{saveLabel}</span>
            {!locked && (
              <>
                <button className="icon-btn" title="Undo (⌘Z)" disabled={!canUndo} onClick={undo}>↶</button>
                <button className="icon-btn" title="Redo (⇧⌘Z)" disabled={!canRedo} onClick={redo}>↷</button>
                <button className="btn" onClick={() => save("manual")} title="⌘S">Save</button>
                {cfg.version_history.enabled && (
                  <>
                    <button className="btn" onClick={() => setConfirm("restore")}>Revert</button>
                    <button className="icon-btn" title="Version history" onClick={openVersions}>🕘</button>
                  </>
                )}
                {cfg.on_demand_feedback.enabled && (
                  <button className="btn outline" onClick={requestFeedback} disabled={busyFb}>
                    {busyFb ? "Thinking…" : "✨ Request feedback"}
                  </button>
                )}
                <button className="btn primary" onClick={() => { setSubmitProblems([]); setConfirm("submit"); }}>Submit</button>
              </>
            )}
            {showPanel && (
              <button className="icon-btn" title="Toggle feedback panel" onClick={() => setPanelOpen(!panelOpen)}>💬</button>
            )}
          </div>
        }
      />
      <div className="ws" style={{ flex: 1, minHeight: 0 }}>
        <div className="ws-main">
          <div className="ws-doc">
            <PageHeader icon="📝" title={a.title} />
            <Props>
              <Prop icon="📅" label="Due">{fmtDate(a.due_date, true)}</Prop>
              <Prop icon="◉" label="Status">
                <Tag dot color={d.submission?.released ? "green" : d.submission ? "blue" : "yellow"}>
                  {d.submission?.released ? "Graded" : d.submission ? "Submitted" : "In progress"}
                </Tag>
              </Prop>
              <Prop icon="🎯" label="Focus areas">
                {a.rubric_areas.map((r) => <Tag key={r} color="purple">{r}</Tag>)}
              </Prop>
              <Prop icon="#" label="Length">
                <span>{words} words · {paras} paragraph{paras === 1 ? "" : "s"}</span>
                {minWords > 0 && <span className="faint">(min {minWords} words{minParas ? `, ${minParas} paragraphs` : ""})</span>}
              </Prop>
            </Props>

            {d.submission?.released && cfg.grades.enabled && (
              <Callout icon="🎓" color="green">
                <div style={{ fontWeight: 600 }}>Grade: {d.submission.grade}</div>
                {d.submission.comments && <div className="prewrap" style={{ marginTop: 4 }}>{d.submission.comments}</div>}
              </Callout>
            )}
            {locked && !d.submission?.released && (
              <Callout icon="📨" color="blue">Submitted {fmtDate(d.submission?.submitted_at, true)}. Your workspace is now read-only.</Callout>
            )}

            <ToggleBlock title="📄 Instructions" defaultOpen={!text}>
              {a.description && <p style={{ margin: "4px 0" }}>{a.description}</p>}
              <p className="prewrap" style={{ margin: "4px 0" }}>{a.instructions}</p>
            </ToggleBlock>
            {a.genre_guidance && (
              <ToggleBlock title="🧭 Genre guidance">
                <p className="prewrap" style={{ margin: "4px 0" }}>{a.genre_guidance}</p>
              </ToggleBlock>
            )}

            {cfg.get_started.enabled && !locked && (
              getStarted !== null ? (
                <Callout icon="🚀" color="yellow">
                  <div className="row"><b>Get started</b><span className="spacer" />
                    <button className="icon-btn" onClick={() => setGetStarted(null)}>✕</button></div>
                  <div className="prewrap" style={{ marginTop: 4 }}>{getStarted}</div>
                  <div className="faint small" style={{ marginTop: 8 }}>This is a scaffold — write each part in your own words.</div>
                </Callout>
              ) : (
                <div style={{ margin: "8px 0" }}>
                  <button
                    className="btn outline" disabled={!!text.trim()} onClick={openGetStarted}
                    title={text.trim() ? "Available while your draft is empty" : "See an outline and guiding questions"}
                  >🚀 Get started</button>
                </div>
              )
            )}

            <div className="divider" style={{ marginTop: 16 }} />
            <div className="editor-wrap">
              <div className="editor-backdrop" aria-hidden>
                {hlStart >= 0 ? (
                  <>{text.slice(0, hlStart)}<mark>{text.slice(hlStart, hlEnd)}</mark>{text.slice(hlEnd)}{"\n"}</>
                ) : text + "\n"}
              </div>
              <textarea
                ref={ta} className="editor" value={text} readOnly={locked} spellCheck
                placeholder={locked ? "" : "Start writing… (blank line = new paragraph)"}
                onChange={(e) => applyText(e.target.value)} onKeyDown={onKeyDown} onPaste={onPaste}
              />
            </div>
            {rt && rtMode === "highlight" && (
              <RealtimeView fb={rt.fb} mode="highlight" canRate={canRate && !!cfg.realtime_feedback.allow_rating}
                            onRate={(h) => rate(rt.fb, h)} onDismiss={dismissRt} />
            )}
          </div>
        </div>

        {showPanel && panelOpen && (
          <aside className="ws-panel">
            <div className="ws-panel-head">
              <span>{presentation === "character" ? "🦉" : "💬"}</span> Feedback
              <span className="spacer" />
              <span className="faint small" style={{ fontWeight: 400 }}>{feedback.length} item{feedback.length === 1 ? "" : "s"}</span>
              <button className="icon-btn" onClick={() => setPanelOpen(false)}>✕</button>
            </div>
            <div className="ws-panel-body">
              {busyFb && <div className="fb-card faint">✨ Reading your draft…</div>}
              {presentation === "character"
                ? <CharacterPanel items={feedback} canRate={canRate} onRate={rate} />
                : <ChatPanel items={feedback} canRate={canRate} onRate={rate} />}
            </div>
          </aside>
        )}
      </div>

      {rt && rtMode !== "highlight" && (
        <RealtimeView fb={rt.fb} mode={rtMode} canRate={canRate && !!cfg.realtime_feedback.allow_rating}
                      onRate={(h) => rate(rt.fb, h)} onDismiss={dismissRt} />
      )}

      {confirm === "restore" && (
        <Modal onClose={() => setConfirm(null)}>
          <h2 style={{ marginTop: 0 }}>Revert to last saved version?</h2>
          <p className="muted">Unsaved changes since your last manual save will be replaced. (They stay in version history.)</p>
          <div className="row"><span className="spacer" />
            <button className="btn" onClick={() => setConfirm(null)}>Cancel</button>
            <button className="btn primary" onClick={() => restore()}>Revert</button>
          </div>
        </Modal>
      )}

      {confirm === "submit" && (
        <Modal onClose={() => setConfirm(null)}>
          <h2 style={{ marginTop: 0 }}>Submit final draft?</h2>
          <p className="muted">After submitting, your draft becomes read-only and can't be submitted again.</p>
          {minWords > 0 && <div>{words >= minWords ? "✅" : "❌"} At least {minWords} words <span className="faint">({words})</span></div>}
          {minParas > 0 && <div>{paras >= minParas ? "✅" : "❌"} At least {minParas} paragraphs <span className="faint">({paras})</span></div>}
          {submitProblems.length > 0 && (
            <Callout icon="⚠️" color="red">{submitProblems.map((p) => <div key={p}>{p}</div>)}</Callout>
          )}
          <div className="row" style={{ marginTop: 16 }}><span className="spacer" />
            <button className="btn" onClick={() => setConfirm(null)}>Keep writing</button>
            <button className="btn primary" onClick={submit}>Submit</button>
          </div>
        </Modal>
      )}

      {versions && (
        <Modal onClose={() => setVersions(null)}>
          <h2 style={{ marginTop: 0 }}>🕘 Version history</h2>
          {versions.length === 0 && <div className="empty">No saved versions yet.</div>}
          <table className="table">
            <tbody>
              {versions.map((v) => (
                <tr key={v.id}>
                  <td style={{ whiteSpace: "nowrap" }}>{fmtDate(v.created_at, true)}</td>
                  <td><Tag color={v.kind === "manual" ? "blue" : "gray"}>{KIND_LABEL[v.kind] ?? v.kind}</Tag></td>
                  <td className="muted small" style={{ maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {v.words}w · {v.preview}
                  </td>
                  <td><button className="btn sm" onClick={() => restore(v.id)}>Restore</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </Modal>
      )}
    </>
  );
}
