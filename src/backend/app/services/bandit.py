"""Contextual Thompson-Sampling bandit over feedback styles (MAB3–MAB7) and reward logic.

Arms are (course, context_key, style) Beta posteriors. Context comes from the learner model.
Reward (MAB6): the student's 1–5 score on the feedback is the primary signal. The first score
opens a window (`window_hours`); an instructor rating that arrives before it closes adds weight b.
When the window closes the reward is final. No score before the due date / submission → skipped.
Instructor ratings after that are archived only. The 👍/👎 helpfulness rating is research data
and never enters the reward. `apply_finalized` folds final rewards into the posteriors (MAB7).
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Assignment, BanditArmState, BanditDecision, Submission, now

MC_SAMPLES = 500


def _arm(db: Session, course_id: int, context_key: str, arm: str) -> BanditArmState:
    st = db.scalar(select(BanditArmState).where(
        BanditArmState.course_id == course_id, BanditArmState.context_key == context_key,
        BanditArmState.arm == arm))
    if st is None:
        st = BanditArmState(course_id=course_id, context_key=context_key, arm=arm, alpha=1.0, beta=1.0, pulls=0)
        db.add(st)
        db.flush()
    return st


def select_style(
    db: Session, course_id: int, context_key: str, arms: list[str], policy: str, fixed: str
) -> tuple[str, float, str]:
    """Returns (style, selection probability, policy actually used)."""
    if not arms:
        return fixed, 1.0, "fixed"
    if policy == "fixed":
        return (fixed if fixed in arms else arms[0]), 1.0, "fixed"
    if policy == "random":
        return random.choice(arms), 1.0 / len(arms), "random"
    try:
        states = {a: _arm(db, course_id, context_key, a) for a in arms}
        draws = {a: random.betavariate(s.alpha, s.beta) for a, s in states.items()}
        choice = max(draws, key=draws.get)
        wins = 0
        for _ in range(MC_SAMPLES):  # selection probability for off-policy evaluation
            d = {a: random.betavariate(s.alpha, s.beta) for a, s in states.items()}
            wins += max(d, key=d.get) == choice
        return choice, max(wins / MC_SAMPLES, 1 / MC_SAMPLES), "bandit"
    except Exception:  # MAB5: never block feedback because of the selector
        return (fixed if fixed in arms else arms[0]), 1.0, "fixed"


def _deadline(db: Session, d: BanditDecision) -> datetime | None:
    """Last moment a first student score can still count: assignment due date or the student's
    submission, whichever comes first. None = neither exists yet."""
    a = db.get(Assignment, d.assignment_id)
    sub = db.scalar(select(Submission.submitted_at).where(
        Submission.assignment_id == d.assignment_id, Submission.student_id == d.student_id))
    times = [t for t in (a.due_date if a else None, sub) if t is not None]
    return min(times) if times else None


def window_closes_at(d: BanditDecision) -> datetime | None:
    if d.student_scored_at is None:
        return None
    hours = float((d.reward_config or {}).get("window_hours", 24))
    return d.student_scored_at + timedelta(hours=hours)


def refresh_reward(db: Session, d: BanditDecision) -> None:
    """MAB6: the student 1–5 score is the reward; an instructor rating that arrives before the
    window closes adds weight b. Pending → final once the window (opened by the first student
    score) closes; pending → skipped when no score arrived before the deadline."""
    if d.reward_status != "pending":
        return
    cfg = d.reward_config or {}
    if not cfg.get("enabled", True):
        _skip(d, "reward module disabled")
        return
    if not cfg.get("student_score_enabled", True):
        _skip(d, "student score disabled")
        return
    t = now()
    deadline = _deadline(db, d)
    if d.student_score is None or (deadline is not None and d.student_scored_at > deadline):
        if deadline is not None and t >= deadline:
            _skip(d, "no student score before deadline")
        return
    if t < window_closes_at(d):
        return
    b = float(cfg.get("instructor_weight", 0.2)) if cfg.get("instructor_review_enabled", True) else 0.0
    if d.instructor_score is not None and b > 0:
        d.reward = round((1 - b) * d.student_score + b * d.instructor_score, 4)
        d.reward_formula = f"{1 - b:g}×student + {b:g}×instructor"
        d.instructor_counted = True
    else:
        d.reward = round(d.student_score, 4)
        d.reward_formula = "student score"
    d.reward_status = "final"
    d.finalized_at = t


def _skip(d: BanditDecision, reason: str) -> None:
    d.reward_status = "skipped"
    d.reward_formula = reason
    d.finalized_at = now()


def record_student_score(db: Session, d: BanditDecision, score: int) -> bool:
    """Returns True when the score counts toward the reward (the decision was still pending).
    The first score opens the window; re-scores inside it replace the value (latest wins)."""
    refresh_reward(db, d)  # close an expired window / passed deadline before accepting the score
    if d.reward_status != "pending":
        return False
    if d.student_scored_at is None:
        d.student_scored_at = now()
    d.student_score = normalize_score(score)
    refresh_reward(db, d)
    return True


def record_instructor_score(db: Session, d: BanditDecision, rating: int) -> bool:
    """Returns True when the rating can still enter the reward. Otherwise it is stored for
    MAB8 offline evaluation and M5 only (`instructor_counted` stays False)."""
    refresh_reward(db, d)
    d.instructor_score = normalize_score(rating)
    if d.reward_status != "pending":
        return False
    refresh_reward(db, d)
    return True


def apply_finalized(db: Session, course_id: int | None = None, dry_run: bool = False) -> list[dict]:
    """MAB7 scheduled update. With dry_run=True returns the preview without changing anything."""
    q = select(BanditDecision).where(BanditDecision.applied.is_(False))
    if course_id is not None:
        q = q.where(BanditDecision.course_id == course_id)
    pending = db.scalars(q).all()
    for d in pending:  # every policy is finalized, so random / fixed baselines get rewards too
        refresh_reward(db, d)
    finals = [d for d in pending if d.reward_status == "final" and d.policy == "bandit"]
    deltas: dict[tuple, dict] = {}
    for d in finals:
        k = (d.course_id, d.context_key, d.arm)
        e = deltas.setdefault(k, {"course_id": d.course_id, "context_key": d.context_key, "arm": d.arm,
                                  "d_alpha": 0.0, "d_beta": 0.0, "n": 0})
        e["d_alpha"] += d.reward
        e["d_beta"] += 1 - d.reward
        e["n"] += 1
    if dry_run:
        db.rollback()
        return list(deltas.values())
    for e in deltas.values():
        st = _arm(db, e["course_id"], e["context_key"], e["arm"])
        st.alpha += e["d_alpha"]
        st.beta += e["d_beta"]
        st.pulls += e["n"]
    for d in finals:
        d.applied = True
    db.commit()
    return list(deltas.values())


def normalize_score(score: int) -> float:
    """1..5 → 0..1 (student score and instructor rating use the same scale)."""
    return (score - 1) / 4
