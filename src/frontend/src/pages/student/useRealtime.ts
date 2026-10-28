import { useEffect, useRef } from "react";
import type { Config } from "../../types";

export type Trigger = "idle" | "sentence_end" | "deletion";

const SENTENCE_END = /[.!?]["')\]]?\s*$/;

export function lastSentences(text: string, n: number): string {
  const parts = text.trim().split(/(?<=[.!?])\s+/).filter(Boolean);
  return parts.slice(-n).join(" ");
}

/**
 * Watches writing-process signals in the browser (S9). Only the triggering excerpt is ever sent;
 * keystrokes stay in memory here and are never logged. Fires only after typing has paused.
 */
export function useRealtimeTriggers(
  text: string, config: Config | undefined, active: boolean, fire: (t: Trigger, excerpt: string) => void,
) {
  const deleted = useRef<{ t: number; n: number }[]>([]);
  const prev = useRef(text);
  const firedFor = useRef<string>("");
  const fireRef = useRef(fire);
  fireRef.current = fire;

  const rt = config?.realtime_feedback;
  const on = !!(active && rt?.enabled);

  // Deletion bursts: count characters removed in the last 60 s.
  useEffect(() => {
    const removed = prev.current.length - text.length;
    prev.current = text;
    if (!on || !rt!.trigger_deletion || removed <= 0) return;
    const now = Date.now();
    deleted.current = [...deleted.current.filter((d) => now - d.t < 60_000), { t: now, n: removed }];
    const total = deleted.current.reduce((s, d) => s + d.n, 0);
    if (total >= (rt!.deletion_threshold as number)) {
      deleted.current = [];
      const id = setTimeout(() => fireRef.current("deletion", lastSentences(text, rt!.context_sentences as number)), 1500);
      return () => clearTimeout(id);
    }
  }, [text, on, rt]);

  // Idle / sentence-settled timers restart on every edit (i.e. only fire when typing has paused).
  useEffect(() => {
    if (!on || !text.trim()) return;
    const timers: number[] = [];
    const endsSentence = SENTENCE_END.test(text);
    const excerpt = lastSentences(text, rt!.context_sentences as number);
    const once = (t: Trigger) => {
      const key = `${t}:${text.length}:${excerpt}`;
      if (firedFor.current === key) return;
      firedFor.current = key;
      fireRef.current(t, excerpt);
    };
    if (rt!.trigger_idle && (!rt!.require_sentence_end || endsSentence)) {
      timers.push(window.setTimeout(() => once("idle"), (rt!.idle_seconds as number) * 1000));
    }
    if (rt!.trigger_sentence_end && endsSentence) {
      timers.push(window.setTimeout(() => once("sentence_end"), (rt!.sentence_settle_seconds as number) * 1000));
    }
    return () => timers.forEach(clearTimeout);
  }, [text, on, rt]);
}
