"""Contextual Thompson-Sampling bandit over feedback styles (MAB3–MAB7) and reward logic.

Arms are (course, context_key, style) Beta posteriors. Context comes from the learner model.
Rewards arrive asynchronously (student rating, instructor rating); `refresh_reward` decides
when a decision's reward is final, and `apply_finalized` folds finalized rewards into the
posteriors (the scheduled update, MAB7).
"""
from __future__ import annotations

import random
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import BanditArmState, BanditDecision, now

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


def refresh_reward(d: BanditDecision) -> None:
    """Recompute reward status from available signals and the reward config snapshot."""
    if d.reward_status != "pending":
        return
    cfg = d.reward_config or {}
    instructor_review_on = cfg.get("instructor_review_enabled", True)
    if not cfg.get("enabled", True):
        d.reward_status = "skipped"
        d.reward_formula = "reward module disabled"
        return
    mode = cfg.get("mode", "combined")
    a = float(cfg.get("student_weight", 0.5))
    timeout = timedelta(hours=float(cfg.get("instructor_timeout_hours", 72)))
    timed_out = now() - d.created_at >= timeout or not instructor_review_on
    s, i = d.student_score, d.instructor_score
    reward, formula = None, ""
    if mode == "student_only":
        if s is not None:
            reward, formula = s, "student only"
    elif mode == "instructor_only":
        if i is not None:
            reward, formula = i, "instructor only"
        elif timed_out and s is not None:
            reward, formula = s, "instructor timeout → student fallback"
    else:
        if s is not None and i is not None:
            reward, formula = a * s + (1 - a) * i, f"{a:g}×student + {1 - a:g}×instructor"
        elif s is None and i is not None and timed_out:
            reward, formula = i, "no student rating → instructor only"
        elif s is not None and timed_out:
            fa = float(cfg.get("fallback_student_weight", 1.0))
            # remaining weight goes to a neutral prior of 0.5
            reward = fa * s + (1 - fa) * 0.5
            formula = f"instructor timeout → {fa:g}×student + {1 - fa:g}×0.5"
    if reward is not None:
        d.reward = round(reward, 4)
        d.reward_formula = formula
        d.reward_status = "final"
        d.finalized_at = now()


def apply_finalized(db: Session, course_id: int | None = None, dry_run: bool = False) -> list[dict]:
    """MAB7 scheduled update. With dry_run=True returns the preview without changing anything."""
    q = select(BanditDecision).where(BanditDecision.applied.is_(False), BanditDecision.policy == "bandit")
    if course_id is not None:
        q = q.where(BanditDecision.course_id == course_id)
    pending = db.scalars(q).all()
    for d in pending:
        refresh_reward(d)
    finals = [d for d in pending if d.reward_status == "final"]
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


def student_score(helpful: bool | None) -> float | None:
    return None if helpful is None else (1.0 if helpful else 0.0)


def instructor_score(rating: int | None) -> float | None:
    return None if rating is None else (rating - 1) / 4
