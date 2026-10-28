"""Feedback pipelines for both venues. Every branch is gated by the resolved module config,
so turning a module off in any layer (course / assignment / condition / student) takes effect here."""
from __future__ import annotations

import random
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import (
    Assignment,
    BanditDecision,
    Draft,
    DraftVersion,
    FeedbackItem,
    FeedbackStyle,
    FixedPrompt,
    LearnerProfile,
    User,
    now,
)
from . import bandit, bkt
from .config_resolver import Resolved
from .events import log_event
from .feedback_service import (
    FeedbackRequest,
    FeedbackResult,
    FeedbackUnavailable,
    get_slm_provider,
    validate,
)

FIXED_MODEL_VERSION = "fixed-prompts"


def get_draft(db: Session, assignment_id: int, student_id: int) -> Draft:
    d = db.scalar(select(Draft).where(Draft.assignment_id == assignment_id, Draft.student_id == student_id))
    if d is None:
        d = Draft(assignment_id=assignment_id, student_id=student_id, content="")
        db.add(d)
        db.commit()
    return d


def snapshot(db: Session, draft: Draft, kind: str, content: str | None = None) -> DraftVersion:
    v = DraftVersion(draft_id=draft.id, content=draft.content if content is None else content, kind=kind)
    db.add(v)
    db.flush()
    return v


def get_profile(db: Session, student_id: int, areas: list[str]) -> LearnerProfile:
    p = db.get(LearnerProfile, student_id)
    if p is None:
        p = LearnerProfile(student_id=student_id, questionnaire=None, mastery={})
        db.add(p)
    missing = [a for a in areas if a not in (p.mastery or {})]
    if missing:
        p.mastery = {**(p.mastery or {}), **bkt.initial_mastery(p.questionnaire, missing)}
    db.flush()
    return p


def _fixed_prompt_result(db: Session, a: Assignment, trigger: str, areas: list[str]) -> FeedbackResult:
    rows = db.scalars(select(FixedPrompt).where(FixedPrompt.course_id == a.course_id,
                                                FixedPrompt.enabled.is_(True))).all()
    matching = [r for r in rows if r.trigger in ("any", trigger)]
    preferred = [r for r in matching if not r.rubric_area or r.rubric_area in areas] or matching
    if not preferred:
        raise FeedbackUnavailable("No instructor-approved prompts are configured for this trigger.")
    pick = random.choice(preferred)
    return FeedbackResult(
        {"summary": pick.text, "items": [{"rubric_area": pick.rubric_area or "General", "comment": pick.text,
                                         "suggestion": "", "quote": ""}]},
        FIXED_MODEL_VERSION, f"fixed_prompt/{pick.id}")


def _allowed_styles(db: Session, cfg: Resolved) -> list[str]:
    enabled = [s.key for s in db.scalars(select(FeedbackStyle).where(FeedbackStyle.enabled.is_(True))
                                         .order_by(FeedbackStyle.key)).all()]
    allowed = cfg.get("on_demand_feedback", "allowed_styles") or []
    arms = [s for s in enabled if not allowed or s in allowed]
    return arms


def on_demand(db: Session, user: User, a: Assignment, cfg: Resolved, content: str) -> FeedbackItem:
    if not cfg.on("on_demand_feedback"):
        raise HTTPException(403, "On-demand feedback is turned off for this assignment.")
    draft = get_draft(db, a.id, user.id)
    if draft.locked:
        raise HTTPException(409, "This assignment has already been submitted.")

    # B8 abuse protection: cooldown + per-assignment cap
    prior = db.scalars(select(FeedbackItem).where(
        FeedbackItem.assignment_id == a.id, FeedbackItem.student_id == user.id,
        FeedbackItem.venue == "on_demand").order_by(FeedbackItem.created_at.desc())).all()
    if len(prior) >= cfg.get("on_demand_feedback", "max_requests"):
        raise HTTPException(429, "You have reached the feedback limit for this assignment.")
    cooldown = cfg.get("on_demand_feedback", "cooldown_seconds")
    if prior and now() - prior[0].created_at < timedelta(seconds=cooldown):
        wait = cooldown - int((now() - prior[0].created_at).total_seconds())
        raise HTTPException(429, f"Please revise for a bit before asking again ({wait}s).")

    # Save first so a model failure never loses or corrupts the draft (NFR reliability).
    draft.content = content
    draft.updated_at = now()
    version = snapshot(db, draft, "feedback_request")
    db.commit()

    areas = a.rubric_areas or []
    source = cfg.get("on_demand_feedback", "source")
    profile = get_profile(db, user.id, areas) if cfg.on("learner_model") else None
    level = bkt.level(profile.mastery, areas) if profile else "unknown"
    rounds = len(prior)
    context = {"level": level, "rounds": rounds, "assignment_id": a.id,
               "weak_areas": sorted([k for k, v in (profile.mastery if profile else {}).items()
                                     if k in areas and v < 0.4])}
    context_key = level

    style = None
    decision = None
    if source == "slm":
        arms = _allowed_styles(db, cfg)
        style, prob, used_policy = bandit.select_style(
            db, a.course_id, context_key, arms, cfg.get("on_demand_feedback", "style_policy"),
            cfg.get("on_demand_feedback", "fixed_style"))
        reward_cfg = dict(cfg.config["reward"])
        reward_cfg["instructor_review_enabled"] = cfg.on("instructor_review")
        reward_cfg["student_rating_enabled"] = cfg.on("student_rating")
        decision = BanditDecision(
            course_id=a.course_id, assignment_id=a.id, student_id=user.id, condition_id=cfg.condition_id,
            policy=used_policy, context=context, context_key=context_key, arm=style, probability=prob,
            reward_config=reward_cfg,
            reward_status="pending" if cfg.on("reward") else "skipped")
        db.add(decision)
        db.flush()
        tmpl = db.get(FeedbackStyle, style)
        try:
            result = get_slm_provider().generate(FeedbackRequest(
                text=content, venue="on_demand", rubric_areas=areas, style=style,
                style_template=tmpl.prompt_template if tmpl else "", learner_context=context,
                assignment_title=a.title))
            result = validate(result)
        except FeedbackUnavailable as e:
            db.rollback()
            log_event(db, user, "feedback_error", {"venue": "on_demand", "error": str(e)},
                      a.course_id, a.id, cfg.condition_id)
            raise HTTPException(503, f"AI feedback is unavailable right now. Your draft is saved. ({e})")
    else:
        try:
            result = _fixed_prompt_result(db, a, "on_demand", areas)
        except FeedbackUnavailable as e:
            raise HTTPException(503, str(e))

    item = FeedbackItem(
        assignment_id=a.id, student_id=user.id, condition_id=cfg.condition_id, venue="on_demand",
        source=source, style=style, trigger="request",
        presentation=cfg.get("feedback_presentation", "mode") if cfg.on("feedback_presentation") else "chat_panel",
        snapshot_version_id=version.id, decision_id=decision.id if decision else None,
        content=result.content, model_version=result.model_version, prompt_template=result.prompt_template,
        guardrail_status=result.guardrail_status)
    db.add(item)

    if profile is not None and source == "slm":
        flagged = {i["rubric_area"] for i in result.content["items"]}
        profile.mastery = bkt.observe(profile.mastery, areas, flagged)
        profile.updated_at = now()
    db.commit()
    log_event(db, user, "feedback_shown", {
        "venue": "on_demand", "feedback_id": item.id, "source": source, "style": style,
        "policy": decision.policy if decision else None,
        "probability": decision.probability if decision else None,
        "model_version": result.model_version, "prompt_template": result.prompt_template,
        "guardrail": result.guardrail_status, "snapshot_version_id": version.id,
    }, a.course_id, a.id, cfg.condition_id)
    return item


def realtime(db: Session, user: User, a: Assignment, cfg: Resolved, excerpt: str, trigger: str,
             session_count: int) -> FeedbackItem | None:
    """Returns None when the trigger is ineligible (module off, wrong trigger, frequency limits)."""
    if not cfg.on("realtime_feedback"):
        return None
    rt = cfg.config["realtime_feedback"]
    enabled_triggers = {"idle": rt["trigger_idle"], "sentence_end": rt["trigger_sentence_end"],
                        "deletion": rt["trigger_deletion"]}
    if not enabled_triggers.get(trigger):
        return None
    if session_count >= rt["max_per_session"]:
        return None
    last = db.scalar(select(func.max(FeedbackItem.created_at)).where(
        FeedbackItem.assignment_id == a.id, FeedbackItem.student_id == user.id,
        FeedbackItem.venue == "realtime"))
    if last and now() - last < timedelta(seconds=rt["min_interval_seconds"]):
        return None
    draft = get_draft(db, a.id, user.id)
    if draft.locked:
        return None

    areas = a.rubric_areas or []
    try:
        if rt["source"] == "slm":
            result = validate(get_slm_provider().generate(FeedbackRequest(
                text=excerpt, venue="realtime", rubric_areas=areas, style="direct", trigger=trigger,
                assignment_title=a.title)))
        else:
            result = _fixed_prompt_result(db, a, trigger, areas)
    except FeedbackUnavailable as e:
        log_event(db, user, "feedback_error", {"venue": "realtime", "error": str(e)},
                  a.course_id, a.id, cfg.condition_id)
        return None
    if not result.content["items"] and rt["source"] == "slm":
        return None  # nothing worth interrupting the student for
    item = FeedbackItem(
        assignment_id=a.id, student_id=user.id, condition_id=cfg.condition_id, venue="realtime",
        source=rt["source"], style=None, trigger=trigger, presentation=rt["presentation"],
        snapshot_version_id=None, content=result.content, model_version=result.model_version,
        prompt_template=result.prompt_template, guardrail_status=result.guardrail_status)
    db.add(item)
    db.commit()
    # Only the trigger and the prompt shown are recorded — never raw keystrokes (SRS §8.2).
    log_event(db, user, "realtime_shown", {"feedback_id": item.id, "trigger": trigger,
                                           "presentation": rt["presentation"], "source": rt["source"]},
              a.course_id, a.id, cfg.condition_id)
    return item


def revision_after(db: Session, item: FeedbackItem) -> DraftVersion | None:
    """The student's revision in response to a feedback item: the last saved version after the
    feedback and before the next on-demand request (or now)."""
    if item.snapshot_version_id is None:
        return None
    snap = db.get(DraftVersion, item.snapshot_version_id)
    nxt = db.scalar(select(FeedbackItem.created_at).where(
        FeedbackItem.assignment_id == item.assignment_id, FeedbackItem.student_id == item.student_id,
        FeedbackItem.venue == "on_demand", FeedbackItem.created_at > item.created_at)
        .order_by(FeedbackItem.created_at))
    q = select(DraftVersion).where(DraftVersion.draft_id == snap.draft_id, DraftVersion.id > snap.id)
    if nxt is not None:
        q = q.where(DraftVersion.created_at <= nxt)
    v = db.scalars(q.order_by(DraftVersion.id.desc())).first()
    if v is None or v.content == snap.content:
        return None
    return v
