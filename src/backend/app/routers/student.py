from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import require_student
from ..db import get_db
from ..models import (
    Assignment,
    AssignmentStudent,
    BanditDecision,
    Course,
    DraftVersion,
    Enrollment,
    FeedbackItem,
    LearnerProfile,
    Submission,
    User,
    now,
)
from ..serializers import assignment_out, feedback_out, submission_out, version_out
from ..services import bandit, bkt, pipeline
from ..services.config_resolver import resolve_for_assignment, resolve_for_course
from ..services.events import log_event
from ..services.feedback_service import paragraphs

router = APIRouter(prefix="/api/student", tags=["student"])


def _assignment(db: Session, user: User, assignment_id: int) -> Assignment:
    a = db.get(Assignment, assignment_id)
    link = db.scalar(select(AssignmentStudent).where(
        AssignmentStudent.assignment_id == assignment_id, AssignmentStudent.student_id == user.id))
    if a is None or link is None or not a.published:
        raise HTTPException(404, "Assignment not found")
    return a


@router.get("/courses")
def my_courses(user: User = Depends(require_student), db: Session = Depends(get_db)):
    courses = db.scalars(select(Course).join(Enrollment, Enrollment.course_id == Course.id)
                         .where(Enrollment.user_id == user.id)).all()
    profile = db.get(LearnerProfile, user.id)
    out = []
    for c in courses:
        cfg = resolve_for_course(db, c, user.id)
        out.append({"id": c.id, "code": c.code, "title": c.title,
                    "questionnaire_required": cfg.on("questionnaire") and not (profile and profile.questionnaire)})
    return out


class QuestionnaireIn(BaseModel):
    writing_confidence: int = Field(ge=1, le=5)
    technical_experience: int = Field(ge=1, le=5)
    year_of_study: int = Field(ge=1, le=6)
    english_first_language: bool
    goals: str = ""


@router.post("/questionnaire")
def submit_questionnaire(body: QuestionnaireIn, user: User = Depends(require_student),
                         db: Session = Depends(get_db)):
    p = db.get(LearnerProfile, user.id) or LearnerProfile(student_id=user.id, mastery={})
    p.questionnaire = body.model_dump()
    # B3: re-seed mastery from the answers
    p.mastery = bkt.initial_mastery(p.questionnaire, list((p.mastery or {}).keys()))
    p.updated_at = now()
    db.merge(p)
    db.commit()
    log_event(db, user, "questionnaire_completed", {"writing_confidence": body.writing_confidence,
                                                    "technical_experience": body.technical_experience})
    return {"ok": True}


@router.get("/assignments")
def my_assignments(user: User = Depends(require_student), db: Session = Depends(get_db)):
    rows = db.scalars(select(Assignment).join(AssignmentStudent, AssignmentStudent.assignment_id == Assignment.id)
                      .where(AssignmentStudent.student_id == user.id, Assignment.published.is_(True))
                      .order_by(Assignment.due_date)).all()
    subs = {s.assignment_id: s for s in db.scalars(select(Submission).where(Submission.student_id == user.id))}
    out = []
    for a in rows:
        s = subs.get(a.id)
        out.append({**assignment_out(a), "course_code": a.course.code,
                    "status": "graded" if s and s.released else "submitted" if s else "in_progress"})
    return out


@router.get("/assignments/{assignment_id}")
def assignment_detail(assignment_id: int, user: User = Depends(require_student), db: Session = Depends(get_db)):
    a = _assignment(db, user, assignment_id)
    cfg = resolve_for_assignment(db, a, user.id)
    draft = pipeline.get_draft(db, a.id, user.id)
    sub = db.scalar(select(Submission).where(Submission.assignment_id == a.id, Submission.student_id == user.id))
    last_saved = db.scalars(select(DraftVersion).where(DraftVersion.draft_id == draft.id)
                            .order_by(DraftVersion.id.desc())).first()
    log_event(db, user, "assignment_opened", {}, a.course_id, a.id, cfg.condition_id)
    out = assignment_out(a)
    if not cfg.on("get_started"):
        out["get_started_content"] = ""
    # Students get the resolved config only — never experiment/condition names (blinding).
    return {
        "assignment": out,
        "config": cfg.config,
        "draft": {"content": draft.content, "updated_at": draft.updated_at.isoformat() + "Z",
                  "locked": draft.locked, "last_saved_version_id": last_saved.id if last_saved else None},
        "submission": submission_out(sub, include_grade=cfg.on("grades")) if sub else None,
    }


class DraftIn(BaseModel):
    content: str
    kind: Literal["manual", "autosave"] = "manual"


@router.put("/assignments/{assignment_id}/draft")
def save_draft(assignment_id: int, body: DraftIn, user: User = Depends(require_student),
               db: Session = Depends(get_db)):
    a = _assignment(db, user, assignment_id)
    draft = pipeline.get_draft(db, a.id, user.id)
    if draft.locked:
        raise HTTPException(409, "This assignment has been submitted and is read-only.")
    changed = draft.content != body.content
    draft.content = body.content
    draft.updated_at = now()
    version = None
    last = db.scalars(select(DraftVersion).where(DraftVersion.draft_id == draft.id)
                      .order_by(DraftVersion.id.desc())).first()
    if body.kind == "manual" or (last is None or last.content != body.content):
        version = pipeline.snapshot(db, draft, body.kind)
    db.commit()
    if body.kind == "manual" or changed:
        cfg = resolve_for_assignment(db, a, user.id)
        log_event(db, user, f"draft_{body.kind}", {"words": len(body.content.split()),
                                                    "version_id": version.id if version else None},
                  a.course_id, a.id, cfg.condition_id)
    return {"updated_at": draft.updated_at.isoformat() + "Z", "version_id": version.id if version else None}


@router.get("/assignments/{assignment_id}/versions")
def versions(assignment_id: int, user: User = Depends(require_student), db: Session = Depends(get_db)):
    a = _assignment(db, user, assignment_id)
    cfg = resolve_for_assignment(db, a, user.id)
    if not cfg.on("version_history"):
        return []
    draft = pipeline.get_draft(db, a.id, user.id)
    rows = db.scalars(select(DraftVersion).where(DraftVersion.draft_id == draft.id)
                      .order_by(DraftVersion.id.desc()).limit(50)).all()
    return [version_out(v) for v in rows]


class RestoreIn(BaseModel):
    version_id: int | None = None  # None → most recent manual save (S7)


@router.post("/assignments/{assignment_id}/restore")
def restore(assignment_id: int, body: RestoreIn, user: User = Depends(require_student),
            db: Session = Depends(get_db)):
    a = _assignment(db, user, assignment_id)
    cfg = resolve_for_assignment(db, a, user.id)
    if not cfg.on("version_history"):
        raise HTTPException(403, "Version history is turned off for this assignment.")
    draft = pipeline.get_draft(db, a.id, user.id)
    if draft.locked:
        raise HTTPException(409, "This assignment has been submitted and is read-only.")
    q = select(DraftVersion).where(DraftVersion.draft_id == draft.id)
    if body.version_id:
        q = q.where(DraftVersion.id == body.version_id)
    else:
        q = q.where(DraftVersion.kind == "manual")
    v = db.scalars(q.order_by(DraftVersion.id.desc())).first()
    if v is None:
        raise HTTPException(404, "No saved version to restore")
    draft.content = v.content
    draft.updated_at = now()
    pipeline.snapshot(db, draft, "restore")
    db.commit()
    log_event(db, user, "draft_restored", {"version_id": v.id}, a.course_id, a.id, cfg.condition_id)
    return {"content": v.content, "restored_version_id": v.id}


class PasteIn(BaseModel):
    before: str
    after: str
    chars: int


@router.post("/assignments/{assignment_id}/paste")
def paste(assignment_id: int, body: PasteIn, user: User = Depends(require_student), db: Session = Depends(get_db)):
    a = _assignment(db, user, assignment_id)
    cfg = resolve_for_assignment(db, a, user.id)
    allowed = cfg.on("paste_control") is False or cfg.get("paste_control", "allow_paste")
    if not allowed:
        log_event(db, user, "paste_blocked", {"chars": body.chars}, a.course_id, a.id, cfg.condition_id)
        return {"allowed": False}
    draft = pipeline.get_draft(db, a.id, user.id)
    if draft.locked:
        raise HTTPException(409, "Read-only")
    v1 = pipeline.snapshot(db, draft, "paste_before", body.before)
    draft.content = body.after
    draft.updated_at = now()
    v2 = pipeline.snapshot(db, draft, "paste_after", body.after)
    db.commit()
    log_event(db, user, "paste_accepted", {"chars": body.chars, "before_version": v1.id, "after_version": v2.id},
              a.course_id, a.id, cfg.condition_id)
    return {"allowed": True}


class FeedbackIn(BaseModel):
    content: str


@router.post("/assignments/{assignment_id}/feedback")
def request_feedback(assignment_id: int, body: FeedbackIn, user: User = Depends(require_student),
                     db: Session = Depends(get_db)):
    a = _assignment(db, user, assignment_id)
    cfg = resolve_for_assignment(db, a, user.id)
    item = pipeline.on_demand(db, user, a, cfg, body.content)
    return feedback_out(item)


@router.get("/assignments/{assignment_id}/feedback")
def feedback_history(assignment_id: int, user: User = Depends(require_student), db: Session = Depends(get_db)):
    a = _assignment(db, user, assignment_id)
    rows = db.scalars(select(FeedbackItem).where(FeedbackItem.assignment_id == a.id,
                                                 FeedbackItem.student_id == user.id)
                      .order_by(FeedbackItem.created_at.desc())).all()
    return [feedback_out(f) for f in rows]


class RealtimeIn(BaseModel):
    excerpt: str = Field(max_length=4000)
    trigger: Literal["idle", "sentence_end", "deletion"]
    session_count: int = 0


@router.post("/assignments/{assignment_id}/realtime")
def realtime_feedback(assignment_id: int, body: RealtimeIn, user: User = Depends(require_student),
                      db: Session = Depends(get_db)):
    a = _assignment(db, user, assignment_id)
    cfg = resolve_for_assignment(db, a, user.id)
    item = pipeline.realtime(db, user, a, cfg, body.excerpt, body.trigger, body.session_count)
    return {"feedback": feedback_out(item) if item else None}


def _own_feedback(db: Session, user: User, feedback_id: int) -> FeedbackItem:
    f = db.get(FeedbackItem, feedback_id)
    if f is None or f.student_id != user.id:
        raise HTTPException(404, "Feedback not found")
    return f


class RatingIn(BaseModel):
    helpful: bool


@router.post("/feedback/{feedback_id}/rating")
def rate_feedback(feedback_id: int, body: RatingIn, user: User = Depends(require_student),
                  db: Session = Depends(get_db)):
    f = _own_feedback(db, user, feedback_id)
    a = db.get(Assignment, f.assignment_id)
    cfg = resolve_for_assignment(db, a, user.id, auto_assign=False)
    if not cfg.on("student_rating"):
        raise HTTPException(403, "Rating is turned off for this assignment.")
    f.student_helpful = body.helpful
    if f.decision_id:
        d = db.get(BanditDecision, f.decision_id)
        d.student_score = bandit.student_score(body.helpful)
        bandit.refresh_reward(d)
    db.commit()
    log_event(db, user, "feedback_rated", {"feedback_id": f.id, "helpful": body.helpful, "venue": f.venue},
              a.course_id, a.id, f.condition_id)
    return feedback_out(f)


@router.post("/feedback/{feedback_id}/dismiss")
def dismiss_feedback(feedback_id: int, user: User = Depends(require_student), db: Session = Depends(get_db)):
    f = _own_feedback(db, user, feedback_id)
    f.dismissed = True
    db.commit()
    a = db.get(Assignment, f.assignment_id)
    log_event(db, user, "feedback_dismissed", {"feedback_id": f.id}, a.course_id, a.id, f.condition_id)
    return {"ok": True}


@router.post("/assignments/{assignment_id}/get-started")
def get_started(assignment_id: int, user: User = Depends(require_student), db: Session = Depends(get_db)):
    a = _assignment(db, user, assignment_id)
    cfg = resolve_for_assignment(db, a, user.id)
    if not cfg.on("get_started"):
        raise HTTPException(403, "Get Started is turned off for this assignment.")
    log_event(db, user, "get_started_opened", {}, a.course_id, a.id, cfg.condition_id)
    return {"content": a.get_started_content}


class SubmitIn(BaseModel):
    content: str


@router.post("/assignments/{assignment_id}/submit")
def submit(assignment_id: int, body: SubmitIn, user: User = Depends(require_student), db: Session = Depends(get_db)):
    a = _assignment(db, user, assignment_id)
    cfg = resolve_for_assignment(db, a, user.id)
    draft = pipeline.get_draft(db, a.id, user.id)
    existing = db.scalar(select(Submission).where(Submission.assignment_id == a.id,
                                                  Submission.student_id == user.id))
    if existing or draft.locked:
        raise HTTPException(409, "Already submitted.")
    if cfg.on("submission_rules"):
        problems = []
        words = len(body.content.split())
        paras = len(paragraphs(body.content))
        mw, mp = cfg.get("submission_rules", "min_words"), cfg.get("submission_rules", "min_paragraphs")
        if words < mw:
            problems.append(f"At least {mw} words required — you have {words}.")
        if paras < mp:
            problems.append(f"At least {mp} paragraphs required — you have {paras} "
                            "(separate paragraphs with a blank line).")
        if problems:
            raise HTTPException(422, {"message": "Submission requirements not met", "problems": problems})
    draft.content = body.content
    draft.locked = True
    draft.updated_at = now()
    v = pipeline.snapshot(db, draft, "submit")
    sub = Submission(assignment_id=a.id, student_id=user.id, version_id=v.id, content=body.content)
    db.add(sub)
    db.commit()
    log_event(db, user, "submitted", {"version_id": v.id, "words": len(body.content.split())},
              a.course_id, a.id, cfg.condition_id)
    return submission_out(sub, include_grade=False)


class ClientEventIn(BaseModel):
    assignment_id: int
    type: Literal["realtime_trigger_fired", "feedback_panel_opened", "get_started_closed", "undo", "redo"]
    payload: dict = {}


@router.post("/events")
def client_event(body: ClientEventIn, user: User = Depends(require_student), db: Session = Depends(get_db)):
    a = _assignment(db, user, body.assignment_id)
    cfg = resolve_for_assignment(db, a, user.id, auto_assign=False)
    safe = {k: v for k, v in body.payload.items() if isinstance(v, (int, float, bool)) or
            (isinstance(v, str) and len(v) <= 64)}  # never accept free text / keystrokes
    log_event(db, user, body.type, safe, a.course_id, a.id, cfg.condition_id)
    return {"ok": True}
