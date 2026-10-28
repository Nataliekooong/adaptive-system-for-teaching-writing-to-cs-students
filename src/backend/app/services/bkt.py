"""Bayesian Knowledge Tracing over rubric areas (B10)."""
from __future__ import annotations

P_SLIP = 0.1
P_GUESS = 0.2
P_TRANSIT = 0.1


def initial_mastery(questionnaire: dict | None, areas: list[str]) -> dict[str, float]:
    # writing_confidence is 1..5 → P(L0) between 0.2 and 0.6
    conf = (questionnaire or {}).get("writing_confidence", 3)
    try:
        conf = max(1, min(5, int(conf)))
    except (TypeError, ValueError):
        conf = 3
    p0 = 0.2 + (conf - 1) * 0.1
    return {a: round(p0, 4) for a in areas}


def update(p_known: float, correct: bool) -> float:
    if correct:
        num = p_known * (1 - P_SLIP)
        posterior = num / (num + (1 - p_known) * P_GUESS)
    else:
        num = p_known * P_SLIP
        posterior = num / (num + (1 - p_known) * (1 - P_GUESS))
    return round(posterior + (1 - posterior) * P_TRANSIT, 4)


def observe(mastery: dict[str, float], areas: list[str], flagged: set[str]) -> dict[str, float]:
    """A feedback round is evidence: flagged areas count as 'incorrect', the rest as 'correct'."""
    out = dict(mastery)
    for a in areas:
        out[a] = update(out.get(a, 0.4), a not in flagged)
    return out


def level(mastery: dict[str, float], areas: list[str]) -> str:
    vals = [mastery[a] for a in areas if a in mastery]
    if not vals:
        return "unknown"
    avg = sum(vals) / len(vals)
    return "low" if avg < 0.4 else "mid" if avg < 0.7 else "high"
