import csv
import io
import random
from collections import defaultdict
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .. import modules
from ..auth import require_instructor
from ..db import get_db
from ..models import (
    Assignment,
    AssignmentStudent,
    BanditArmState,
    BanditDecision,
    Condition,
    ConditionAssignment,
    Course,
    Draft,
    DraftVersion,
    Enrollment,
    EventLog,
    Experiment,
    FeedbackItem,
    FeedbackStyle,
    FixedPrompt,
    LearnerProfile,
    Submission,
    User,
    now,
)
from ..serializers import assignment_out, feedback_out, iso, version_out
from ..services import bandit, pipeline
from ..services.config_resolver import pick_condition, resolve_for_assignment
from ..services.events import log_event

router = APIRouter(prefix="/api/instructor", tags=["instructor"])


# ---------------------------------------------------------------- helpers

def _style_keys(db: Session) -> set[str]:
    return set(db.scalars(select(FeedbackStyle.key)).all())


def _clean_config(db: Session, cfg: dict | None) -> dict:
    try:
        return modules.validate_overrides(cfg, _style_keys(db))
    except modules.ConfigError as e:
        raise HTTPException(422, str(e))


def _course(db: Session, user: User, course_id: int) -> Course:
    c = db.get(Course, course_id)
    if c is None or c.instructor_id != user.id:
        raise HTTPException(404, "Course not found")
    return c


def _assignment(db: Session, user: User, assignment_id: int) -> Assignment:
    a = db.get(Assignment, assignment_id)
    if a is None:
        raise HTTPException(404, "Assignment not found")
    _course(db, user, a.course_id)
    return a


def _experiment(db: Session, user: User, exp_id: int) -> Experiment:
    e = db.get(Experiment, exp_id)
    if e is None:
        raise HTTPException(404, "Experiment not found")
    _course(db, user, e.course_id)
    return e


def _user_out(u: User) -> dict:
    return {"id": u.id, "username": u.username, "display_name": u.display_name, "pseudonym": u.pseudonym}


def _course_out(c: Course) -> dict:
    return {"id": c.id, "code": c.code, "title": c.title, "rubric_areas": c.rubric_areas, "config": c.config}


def _purge_experiments(db: Session, exp_ids: list[int]) -> None:
    if not exp_ids:
        return
    cond_ids = list(db.scalars(select(Condition.id).where(Condition.experiment_id.in_(exp_ids))))
    db.execute(delete(ConditionAssignment).where(ConditionAssignment.experiment_id.in_(exp_ids)))
    if cond_ids:
        db.execute(delete(Condition).where(Condition.id.in_(cond_ids)))
    db.execute(delete(Experiment).where(Experiment.id.in_(exp_ids)))


def _purge_assignment(db: Session, a: Assignment) -> None:
    """Remove an assignment and its operational rows. Event logs stay (append-only, §8.2)."""
    draft_ids = list(db.scalars(select(Draft.id).where(Draft.assignment_id == a.id)))
    db.execute(delete(FeedbackItem).where(FeedbackItem.assignment_id == a.id))
    db.execute(delete(Submission).where(Submission.assignment_id == a.id))
    if draft_ids:
        db.execute(delete(DraftVersion).where(DraftVersion.draft_id.in_(draft_ids)))
        db.execute(delete(Draft).where(Draft.id.in_(draft_ids)))
    db.execute(delete(BanditDecision).where(BanditDecision.assignment_id == a.id))
    db.execute(delete(AssignmentStudent).where(AssignmentStudent.assignment_id == a.id))
    _purge_experiments(db, list(db.scalars(select(Experiment.id).where(Experiment.assignment_id == a.id))))
    db.delete(a)


def _purge_course(db: Session, c: Course) -> None:
    """Remove a course and its operational rows. Event logs stay (append-only, §8.2)."""
    for a in list(db.scalars(select(Assignment).where(Assignment.course_id == c.id))):
        _purge_assignment(db, a)
    _purge_experiments(db, list(db.scalars(select(Experiment.id).where(Experiment.course_id == c.id))))
    db.execute(delete(BanditDecision).where(BanditDecision.course_id == c.id))
    db.execute(delete(BanditArmState).where(BanditArmState.course_id == c.id))
    db.execute(delete(FixedPrompt).where(FixedPrompt.course_id == c.id))
    db.execute(delete(Enrollment).where(Enrollment.course_id == c.id))
    db.delete(c)


# ---------------------------------------------------------------- courses

@router.get("/courses")
def courses(user: User = Depends(require_instructor), db: Session = Depends(get_db)):
    rows = db.scalars(select(Course).where(Course.instructor_id == user.id).order_by(Course.id)).all()
    out = []
    for c in rows:
        n_students = len(db.scalars(select(Enrollment.id).where(Enrollment.course_id == c.id)).all())
        n_assign = len(db.scalars(select(Assignment.id).where(Assignment.course_id == c.id)).all())
        n_active = len(db.scalars(select(Experiment.id).where(Experiment.course_id == c.id,
                                                              Experiment.status == "active")).all())
        out.append({**_course_out(c), "students": n_students, "assignments": n_assign, "active_experiments": n_active})
    return out


class CourseIn(BaseModel):
    code: str
    title: str
    rubric_areas: list[str] = []


@router.post("/courses")
def create_course(body: CourseIn, user: User = Depends(require_instructor), db: Session = Depends(get_db)):
    c = Course(code=body.code, title=body.title, instructor_id=user.id, rubric_areas=body.rubric_areas, config={})
    db.add(c)
    db.commit()
    return _course_out(c)


@router.get("/courses/{course_id}")
def course(course_id: int, user: User = Depends(require_instructor), db: Session = Depends(get_db)):
    return _course_out(_course(db, user, course_id))


class CoursePatch(BaseModel):
    code: str | None = None
    title: str | None = None
    rubric_areas: list[str] | None = None
    config: dict | None = None


@router.patch("/courses/{course_id}")
def update_course(course_id: int, body: CoursePatch, user: User = Depends(require_instructor),
                  db: Session = Depends(get_db)):
    c = _course(db, user, course_id)
    for k in ("code", "title", "rubric_areas"):
        if getattr(body, k) is not None:
            setattr(c, k, getattr(body, k))
    if body.config is not None:
        c.config = _clean_config(db, body.config)
        log_event(db, user, "config_changed", {"layer": "course", "config": c.config}, c.id, commit=False)
    db.commit()
    return _course_out(c)


@router.delete("/courses/{course_id}")
def delete_course(course_id: int, user: User = Depends(require_instructor), db: Session = Depends(get_db)):
    c = _course(db, user, course_id)
    log_event(db, user, "course_deleted", {"code": c.code, "title": c.title}, c.id, commit=False)
    _purge_course(db, c)
    db.commit()
    return {"ok": True}


@router.get("/courses/{course_id}/students")
def course_students(course_id: int, user: User = Depends(require_instructor), db: Session = Depends(get_db)):
    _course(db, user, course_id)
    rows = db.scalars(select(User).join(Enrollment, Enrollment.user_id == User.id)
                      .where(Enrollment.course_id == course_id).order_by(User.display_name)).all()
    profiles = {p.student_id: p for p in db.scalars(select(LearnerProfile))}
    out = []
    for u in rows:
        p = profiles.get(u.id)
        out.append({**_user_out(u), "questionnaire_done": bool(p and p.questionnaire),
                    "mastery": p.mastery if p else {}})
    return out


@router.get("/students")
def all_students(user: User = Depends(require_instructor), db: Session = Depends(get_db)):
    return [_user_out(u) for u in db.scalars(select(User).where(User.role == "student").order_by(User.display_name))]


class EnrollIn(BaseModel):
    student_ids: list[int]


@router.put("/courses/{course_id}/students")
def set_enrollment(course_id: int, body: EnrollIn, user: User = Depends(require_instructor),
                   db: Session = Depends(get_db)):
    _course(db, user, course_id)
    existing = {e.user_id: e for e in db.scalars(select(Enrollment).where(Enrollment.course_id == course_id))}
    for sid in body.student_ids:
        if sid not in existing:
            db.add(Enrollment(course_id=course_id, user_id=sid))
    for sid, e in existing.items():
        if sid not in body.student_ids:
            db.delete(e)
    db.commit()
    return {"ok": True}


@router.get("/courses/{course_id}/students/{student_id}")
def student_detail(course_id: int, student_id: int, user: User = Depends(require_instructor),
                   db: Session = Depends(get_db)):
    """I6 assignments & grades, I7 common struggle areas."""
    c = _course(db, user, course_id)
    s = db.get(User, student_id)
    if s is None:
        raise HTTPException(404, "Student not found")
    assigns = db.scalars(select(Assignment).join(AssignmentStudent, AssignmentStudent.assignment_id == Assignment.id)
                         .where(Assignment.course_id == c.id, AssignmentStudent.student_id == s.id)).all()
    subs = {x.assignment_id: x for x in db.scalars(select(Submission).where(Submission.student_id == s.id))}
    rows = []
    for a in assigns:
        sub = subs.get(a.id)
        cfg = resolve_for_assignment(db, a, s.id, auto_assign=False)
        rows.append({"assignment_id": a.id, "title": a.title, "due_date": iso(a.due_date),
                     "status": "graded" if sub and sub.grade else "submitted" if sub else "in progress",
                     "grade": sub.grade if sub else None, "released": sub.released if sub else False,
                     "conditions": [cd.name for cd in cfg.conditions]})
    items = db.scalars(select(FeedbackItem).join(Assignment, Assignment.id == FeedbackItem.assignment_id)
                       .where(Assignment.course_id == c.id, FeedbackItem.student_id == s.id)).all()
    struggles: dict[str, int] = defaultdict(int)
    for f in items:
        for it in f.content.get("items", []):
            struggles[it.get("rubric_area", "General")] += 1
    p = db.get(LearnerProfile, s.id)
    return {"student": _user_out(s), "assignments": rows,
            "struggles": sorted(([k, v] for k, v in struggles.items()), key=lambda x: -x[1]),
            "mastery": p.mastery if p else {}, "questionnaire": p.questionnaire if p else None,
            "feedback_count": len(items)}


@router.get("/courses/{course_id}/struggles")
def class_struggles(course_id: int, user: User = Depends(require_instructor), db: Session = Depends(get_db)):
    c = _course(db, user, course_id)
    items = db.scalars(select(FeedbackItem).join(Assignment, Assignment.id == FeedbackItem.assignment_id)
                       .where(Assignment.course_id == c.id)).all()
    counts: dict[str, set] = defaultdict(set)
    totals: dict[str, int] = defaultdict(int)
    for f in items:
        for it in f.content.get("items", []):
            area = it.get("rubric_area", "General")
            counts[area].add(f.student_id)
            totals[area] += 1
    return sorted(({"area": a, "students": len(counts[a]), "mentions": totals[a]} for a in counts),
                  key=lambda r: -r["mentions"])


# ---------------------------------------------------------------- assignments

@router.get("/courses/{course_id}/assignments")
def assignments(course_id: int, user: User = Depends(require_instructor), db: Session = Depends(get_db)):
    _course(db, user, course_id)
    rows = db.scalars(select(Assignment).where(Assignment.course_id == course_id).order_by(Assignment.due_date)).all()
    out = []
    for a in rows:
        n = len(db.scalars(select(AssignmentStudent.id).where(AssignmentStudent.assignment_id == a.id)).all())
        subs = len(db.scalars(select(Submission.id).where(Submission.assignment_id == a.id)).all())
        overrides = sorted(a.config.keys())
        out.append({**assignment_out(a), "students": n, "submissions": subs, "overridden_modules": overrides})
    return out


class AssignmentIn(BaseModel):
    title: str
    description: str = ""
    instructions: str = ""
    genre_guidance: str = ""
    due_date: datetime | None = None
    rubric_areas: list[str] = []
    get_started_content: str = ""
    config: dict = {}
    published: bool = True
    assign_all: bool = True


@router.post("/courses/{course_id}/assignments")
def create_assignment(course_id: int, body: AssignmentIn, user: User = Depends(require_instructor),
                      db: Session = Depends(get_db)):
    c = _course(db, user, course_id)
    data = body.model_dump(exclude={"assign_all", "config"})
    if data["due_date"] is not None:
        data["due_date"] = data["due_date"].replace(tzinfo=None)
    a = Assignment(course_id=c.id, config=_clean_config(db, body.config), **data)
    db.add(a)
    db.flush()
    if body.assign_all:
        for e in db.scalars(select(Enrollment).where(Enrollment.course_id == c.id)):
            db.add(AssignmentStudent(assignment_id=a.id, student_id=e.user_id, override_config={}))
    db.commit()
    return assignment_out(a)


@router.get("/assignments/{assignment_id}")
def assignment(assignment_id: int, user: User = Depends(require_instructor), db: Session = Depends(get_db)):
    a = _assignment(db, user, assignment_id)
    links = db.scalars(select(AssignmentStudent).where(AssignmentStudent.assignment_id == a.id)).all()
    students = []
    for link in links:
        u = db.get(User, link.student_id)
        cfg = resolve_for_assignment(db, a, u.id, auto_assign=False)
        students.append({**_user_out(u), "override_config": link.override_config,
                         "conditions": [{"id": cd.id, "name": cd.name, "experiment": cd.experiment.name}
                                        for cd in cfg.conditions],
                         "effective": {
                             "on_demand": cfg.on("on_demand_feedback") and cfg.get("on_demand_feedback", "source"),
                             "realtime": cfg.on("realtime_feedback") and cfg.get("realtime_feedback", "presentation"),
                             "policy": cfg.get("on_demand_feedback", "style_policy"),
                         }})
    return {**assignment_out(a), "config": a.config, "students": sorted(students, key=lambda s: s["display_name"])}


class AssignmentPatch(BaseModel):
    title: str | None = None
    description: str | None = None
    instructions: str | None = None
    genre_guidance: str | None = None
    due_date: datetime | None = None
    rubric_areas: list[str] | None = None
    get_started_content: str | None = None
    config: dict | None = None
    published: bool | None = None


@router.patch("/assignments/{assignment_id}")
def update_assignment(assignment_id: int, body: AssignmentPatch, user: User = Depends(require_instructor),
                      db: Session = Depends(get_db)):
    a = _assignment(db, user, assignment_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        if k == "config":
            a.config = _clean_config(db, v)
            log_event(db, user, "config_changed", {"layer": "assignment", "config": a.config},
                      a.course_id, a.id, commit=False)
        elif k == "due_date" and v is not None:
            a.due_date = v.replace(tzinfo=None)
        else:
            setattr(a, k, v)
    db.commit()
    return assignment_out(a)


@router.delete("/assignments/{assignment_id}")
def delete_assignment(assignment_id: int, user: User = Depends(require_instructor),
                      db: Session = Depends(get_db)):
    a = _assignment(db, user, assignment_id)
    log_event(db, user, "assignment_deleted", {"title": a.title}, a.course_id, a.id, commit=False)
    _purge_assignment(db, a)
    db.commit()
    return {"ok": True}


class AssignStudentIn(BaseModel):
    student_id: int
    override_config: dict = {}


@router.put("/assignments/{assignment_id}/students")
def set_assignment_students(assignment_id: int, body: list[AssignStudentIn], user: User = Depends(require_instructor),
                            db: Session = Depends(get_db)):
    """I3 assign students + I5 per-student feedback settings (as module overrides)."""
    a = _assignment(db, user, assignment_id)
    existing = {x.student_id: x for x in db.scalars(select(AssignmentStudent)
                                                     .where(AssignmentStudent.assignment_id == a.id))}
    wanted = {b.student_id: b for b in body}
    for sid, b in wanted.items():
        cfg = _clean_config(db, b.override_config)
        if sid in existing:
            existing[sid].override_config = cfg
        else:
            db.add(AssignmentStudent(assignment_id=a.id, student_id=sid, override_config=cfg))
    for sid, link in existing.items():
        if sid not in wanted:
            db.delete(link)
    db.commit()
    return {"ok": True}


@router.get("/assignments/{assignment_id}/effective-config")
def effective_config(assignment_id: int, student_id: int | None = None, user: User = Depends(require_instructor),
                     db: Session = Depends(get_db)):
    a = _assignment(db, user, assignment_id)
    cfg = resolve_for_assignment(db, a, student_id, auto_assign=False)
    return {"config": cfg.config, "provenance": cfg.provenance,
            "conditions": [{"id": c.id, "name": c.name, "experiment": c.experiment.name} for c in cfg.conditions]}


# ---------------------------------------------------------------- submissions & grading (I8, I11)

@router.get("/assignments/{assignment_id}/submissions")
def submissions(assignment_id: int, user: User = Depends(require_instructor), db: Session = Depends(get_db)):
    a = _assignment(db, user, assignment_id)
    links = db.scalars(select(AssignmentStudent).where(AssignmentStudent.assignment_id == a.id)).all()
    subs = {s.student_id: s for s in db.scalars(select(Submission).where(Submission.assignment_id == a.id))}
    drafts = {d.student_id: d for d in db.scalars(select(Draft).where(Draft.assignment_id == a.id))}
    out = []
    for link in links:
        u = db.get(User, link.student_id)
        s, d = subs.get(u.id), drafts.get(u.id)
        n_fb = len(db.scalars(select(FeedbackItem.id).where(FeedbackItem.assignment_id == a.id,
                                                            FeedbackItem.student_id == u.id)).all())
        content = s.content if s else d.content if d else ""
        out.append({"student": _user_out(u), "submission_id": s.id if s else None,
                    "status": "graded" if s and s.grade else "submitted" if s else "not started" if not content
                    else "in progress", "submitted_at": iso(s.submitted_at) if s else None,
                    "grade": s.grade if s else None, "released": s.released if s else False,
                    "words": len(content.split()), "feedback_count": n_fb})
    return sorted(out, key=lambda r: r["student"]["display_name"])


@router.get("/assignments/{assignment_id}/students/{student_id}/work")
def student_work(assignment_id: int, student_id: int, user: User = Depends(require_instructor),
                 db: Session = Depends(get_db)):
    a = _assignment(db, user, assignment_id)
    d = db.scalar(select(Draft).where(Draft.assignment_id == a.id, Draft.student_id == student_id))
    s = db.scalar(select(Submission).where(Submission.assignment_id == a.id, Submission.student_id == student_id))
    fb = db.scalars(select(FeedbackItem).where(FeedbackItem.assignment_id == a.id,
                                               FeedbackItem.student_id == student_id)
                    .order_by(FeedbackItem.created_at.desc())).all()
    versions = db.scalars(select(DraftVersion).where(DraftVersion.draft_id == d.id)
                          .order_by(DraftVersion.id.desc())).all() if d else []
    return {"student": _user_out(db.get(User, student_id)),
            "draft": d.content if d else "", "submission": {
                "id": s.id, "content": s.content, "submitted_at": iso(s.submitted_at), "grade": s.grade,
                "comments": s.comments, "released": s.released} if s else None,
            "feedback": [feedback_out(f, research=True) for f in fb],
            "versions": [version_out(v) for v in versions]}


class GradeIn(BaseModel):
    grade: str
    comments: str = ""


@router.post("/submissions/{submission_id}/grade")
def grade(submission_id: int, body: GradeIn, user: User = Depends(require_instructor), db: Session = Depends(get_db)):
    s = db.get(Submission, submission_id)
    if s is None:
        raise HTTPException(404, "Submission not found")
    _assignment(db, user, s.assignment_id)
    s.grade, s.comments = body.grade, body.comments
    db.commit()
    return {"ok": True}


class ReleaseIn(BaseModel):
    submission_ids: list[int]
    released: bool = True


@router.post("/assignments/{assignment_id}/release")
def release(assignment_id: int, body: ReleaseIn, user: User = Depends(require_instructor),
            db: Session = Depends(get_db)):
    a = _assignment(db, user, assignment_id)
    n = 0
    for s in db.scalars(select(Submission).where(Submission.assignment_id == a.id,
                                                 Submission.id.in_(body.submission_ids))):
        if body.released and not s.grade:
            continue
        s.released = body.released
        n += 1
    db.commit()
    return {"updated": n}


# ---------------------------------------------------------------- review queue (I9)

@router.get("/courses/{course_id}/review-queue")
def review_queue(course_id: int, assignment_id: int | None = None, user: User = Depends(require_instructor),
                 db: Session = Depends(get_db)):
    c = _course(db, user, course_id)
    q = (select(FeedbackItem).join(Assignment, Assignment.id == FeedbackItem.assignment_id)
         .where(Assignment.course_id == c.id, FeedbackItem.venue == "on_demand",
                FeedbackItem.instructor_rating.is_(None)))
    if assignment_id:
        q = q.where(FeedbackItem.assignment_id == assignment_id)
    candidates = []
    for f in db.scalars(q).all():
        a = db.get(Assignment, f.assignment_id)
        cfg = resolve_for_assignment(db, a, f.student_id, auto_assign=False)
        if not cfg.on("instructor_review"):
            continue
        after = pipeline.revision_after(db, f)
        if after is None:
            continue
        candidates.append((f, a, after, cfg.get("instructor_review", "sample_size")))
    pending_total = len(candidates)
    size = min([x[3] for x in candidates] or [5])
    sample = random.sample(candidates, min(size, len(candidates)))
    out = []
    for f, a, after, _ in sample:
        before = db.get(DraftVersion, f.snapshot_version_id)
        stu = db.get(User, f.student_id)
        out.append({"feedback": feedback_out(f, research=True), "assignment": {"id": a.id, "title": a.title},
                    "student_pseudonym": stu.pseudonym, "before": before.content, "after": after.content})
    return {"pending_total": pending_total, "items": out}


class InstructorRatingIn(BaseModel):
    rating: int = Field(ge=1, le=5)


@router.post("/feedback/{feedback_id}/rating")
def instructor_rate(feedback_id: int, body: InstructorRatingIn, user: User = Depends(require_instructor),
                    db: Session = Depends(get_db)):
    f = db.get(FeedbackItem, feedback_id)
    if f is None:
        raise HTTPException(404, "Feedback not found")
    a = _assignment(db, user, f.assignment_id)
    f.instructor_rating = body.rating
    f.instructor_rated_at = now()
    if f.decision_id:
        d = db.get(BanditDecision, f.decision_id)
        d.instructor_score = bandit.instructor_score(body.rating)
        bandit.refresh_reward(d)
    db.commit()
    log_event(db, user, "instructor_rated", {"feedback_id": f.id, "rating": body.rating},
              a.course_id, a.id, f.condition_id)
    return {"ok": True}


# ---------------------------------------------------------------- experiments (A/B tests)

def _experiment_out(db: Session, e: Experiment) -> dict:
    counts = defaultdict(int)
    for ca in db.scalars(select(ConditionAssignment).where(ConditionAssignment.experiment_id == e.id)):
        counts[ca.condition_id] += 1
    return {"id": e.id, "course_id": e.course_id, "assignment_id": e.assignment_id, "name": e.name,
            "hypothesis": e.hypothesis, "status": e.status, "strategy": e.strategy, "created_at": iso(e.created_at),
            "conditions": [{"id": c.id, "name": c.name, "description": c.description, "weight": c.weight,
                            "config": c.config, "students": counts[c.id]} for c in e.conditions]}


class ConditionIn(BaseModel):
    id: int | None = None
    name: str
    description: str = ""
    weight: float = Field(default=1.0, gt=0)
    config: dict = {}


class ExperimentIn(BaseModel):
    name: str
    hypothesis: str = ""
    assignment_id: int | None = None
    strategy: str = Field(default="balanced", pattern="^(random|balanced|manual)$")
    conditions: list[ConditionIn] = []


@router.get("/courses/{course_id}/experiments")
def experiments(course_id: int, user: User = Depends(require_instructor), db: Session = Depends(get_db)):
    _course(db, user, course_id)
    return [_experiment_out(db, e) for e in db.scalars(select(Experiment).where(Experiment.course_id == course_id)
                                                       .order_by(Experiment.id.desc()))]


@router.post("/courses/{course_id}/experiments")
def create_experiment(course_id: int, body: ExperimentIn, user: User = Depends(require_instructor),
                      db: Session = Depends(get_db)):
    c = _course(db, user, course_id)
    if body.assignment_id:
        _assignment(db, user, body.assignment_id)
    e = Experiment(course_id=c.id, assignment_id=body.assignment_id, name=body.name, hypothesis=body.hypothesis,
                   strategy=body.strategy, status="draft")
    for cd in body.conditions:
        e.conditions.append(Condition(name=cd.name, description=cd.description, weight=cd.weight,
                                      config=_clean_config(db, cd.config)))
    db.add(e)
    db.commit()
    return _experiment_out(db, e)


@router.get("/experiments/{exp_id}")
def experiment(exp_id: int, user: User = Depends(require_instructor), db: Session = Depends(get_db)):
    return _experiment_out(db, _experiment(db, user, exp_id))


class ExperimentPatch(BaseModel):
    name: str | None = None
    hypothesis: str | None = None
    assignment_id: int | None = None
    strategy: str | None = Field(default=None, pattern="^(random|balanced|manual)$")
    status: str | None = Field(default=None, pattern="^(draft|active|paused|completed)$")
    conditions: list[ConditionIn] | None = None


@router.patch("/experiments/{exp_id}")
def update_experiment(exp_id: int, body: ExperimentPatch, user: User = Depends(require_instructor),
                      db: Session = Depends(get_db)):
    e = _experiment(db, user, exp_id)
    data = body.model_dump(exclude_unset=True)
    if "conditions" in data:
        started = db.scalar(select(ConditionAssignment.id).where(ConditionAssignment.experiment_id == e.id))
        keep_ids = {cd.id for cd in body.conditions if cd.id}
        if started and any(c.id not in keep_ids for c in e.conditions):
            raise HTTPException(409, "Conditions with assigned students cannot be removed. Pause or clone instead.")
        by_id = {c.id: c for c in e.conditions}
        new_list = []
        for cd in body.conditions:
            cfg = _clean_config(db, cd.config)
            if cd.id and cd.id in by_id:
                c = by_id[cd.id]
                c.name, c.description, c.weight, c.config = cd.name, cd.description, cd.weight, cfg
                new_list.append(c)
            else:
                new_list.append(Condition(name=cd.name, description=cd.description, weight=cd.weight, config=cfg))
        e.conditions = new_list
    if "status" in data and data["status"] == "active" and len(e.conditions) < 2 and \
            not (body.conditions and len(body.conditions) >= 2):
        raise HTTPException(422, "An experiment needs at least two conditions to run.")
    for k in ("name", "hypothesis", "assignment_id", "strategy", "status"):
        if k in data:
            setattr(e, k, data[k])
    db.commit()
    log_event(db, user, "experiment_updated", {"experiment_id": e.id, "status": e.status}, e.course_id)
    return _experiment_out(db, e)


@router.delete("/experiments/{exp_id}")
def delete_experiment(exp_id: int, user: User = Depends(require_instructor), db: Session = Depends(get_db)):
    e = _experiment(db, user, exp_id)
    if db.scalar(select(ConditionAssignment.id).where(ConditionAssignment.experiment_id == e.id)):
        raise HTTPException(409, "This experiment already has participants; mark it completed instead.")
    db.delete(e)
    db.commit()
    return {"ok": True}


@router.get("/experiments/{exp_id}/participants")
def participants(exp_id: int, user: User = Depends(require_instructor), db: Session = Depends(get_db)):
    e = _experiment(db, user, exp_id)
    assigned = {ca.student_id: ca for ca in db.scalars(select(ConditionAssignment)
                                                        .where(ConditionAssignment.experiment_id == e.id))}
    students = db.scalars(select(User).join(Enrollment, Enrollment.user_id == User.id)
                          .where(Enrollment.course_id == e.course_id).order_by(User.display_name)).all()
    overridden = set()
    if e.assignment_id:
        overridden = {x.student_id for x in db.scalars(select(AssignmentStudent).where(
            AssignmentStudent.assignment_id == e.assignment_id)) if x.override_config}
    return [{**_user_out(u), "condition_id": assigned[u.id].condition_id if u.id in assigned else None,
             "assigned_by": assigned[u.id].assigned_by if u.id in assigned else None,
             "has_override": u.id in overridden} for u in students]


class AssignParticipantsIn(BaseModel):
    strategy: str | None = Field(default=None, pattern="^(random|balanced)$")
    reassign: bool = False


@router.post("/experiments/{exp_id}/assign")
def assign_participants(exp_id: int, body: AssignParticipantsIn, user: User = Depends(require_instructor),
                        db: Session = Depends(get_db)):
    """Bulk-assign every enrolled student now (instead of lazily at first access)."""
    e = _experiment(db, user, exp_id)
    if not e.conditions:
        raise HTTPException(422, "Add conditions first.")
    if body.reassign:
        for ca in db.scalars(select(ConditionAssignment).where(ConditionAssignment.experiment_id == e.id)):
            db.delete(ca)
        db.flush()
    have = set(db.scalars(select(ConditionAssignment.student_id)
                          .where(ConditionAssignment.experiment_id == e.id)).all())
    ids = [x for x in db.scalars(select(Enrollment.user_id).where(Enrollment.course_id == e.course_id)).all()
           if x not in have]
    random.shuffle(ids)
    strategy = body.strategy or (e.strategy if e.strategy != "manual" else "balanced")
    for sid in ids:
        cond = pick_condition(db, e, strategy)
        db.add(ConditionAssignment(experiment_id=e.id, condition_id=cond.id, student_id=sid, assigned_by=strategy))
        db.flush()
    db.commit()
    return _experiment_out(db, e)


class MoveIn(BaseModel):
    condition_id: int | None


@router.put("/experiments/{exp_id}/participants/{student_id}")
def move_participant(exp_id: int, student_id: int, body: MoveIn, user: User = Depends(require_instructor),
                     db: Session = Depends(get_db)):
    e = _experiment(db, user, exp_id)
    ca = db.scalar(select(ConditionAssignment).where(ConditionAssignment.experiment_id == e.id,
                                                     ConditionAssignment.student_id == student_id))
    if body.condition_id is None:
        if ca:
            db.delete(ca)
    else:
        if body.condition_id not in {c.id for c in e.conditions}:
            raise HTTPException(422, "Condition does not belong to this experiment")
        if ca:
            ca.condition_id, ca.assigned_by, ca.assigned_at = body.condition_id, "manual", now()
        else:
            db.add(ConditionAssignment(experiment_id=e.id, condition_id=body.condition_id, student_id=student_id,
                                       assigned_by="manual"))
    db.commit()
    return {"ok": True}


@router.get("/experiments/{exp_id}/results")
def experiment_results(exp_id: int, user: User = Depends(require_instructor), db: Session = Depends(get_db)):
    e = _experiment(db, user, exp_id)
    out = []
    for c in e.conditions:
        sids = set(db.scalars(select(ConditionAssignment.student_id)
                              .where(ConditionAssignment.condition_id == c.id)).all())
        fq = select(FeedbackItem).where(FeedbackItem.condition_id == c.id)
        if e.assignment_id:
            fq = fq.where(FeedbackItem.assignment_id == e.assignment_id)
        fb = db.scalars(fq).all()
        rated = [f for f in fb if f.student_helpful is not None]
        decisions = db.scalars(select(BanditDecision).where(BanditDecision.condition_id == c.id,
                                                            BanditDecision.reward_status == "final")).all()
        sq = select(Submission).where(Submission.student_id.in_(sids) if sids else Submission.id == -1)
        if e.assignment_id:
            sq = sq.where(Submission.assignment_id == e.assignment_id)
        subs = db.scalars(sq).all()
        numeric = []
        for s in subs:
            try:
                numeric.append(float(s.grade))
            except (TypeError, ValueError):
                pass
        inst = [f.instructor_rating for f in fb if f.instructor_rating]
        out.append({
            "condition_id": c.id, "name": c.name, "students": len(sids),
            "on_demand_requests": sum(f.venue == "on_demand" for f in fb),
            "realtime_popups": sum(f.venue == "realtime" for f in fb),
            "dismissed": sum(f.dismissed for f in fb),
            "helpful_rate": round(sum(f.student_helpful for f in rated) / len(rated), 3) if rated else None,
            "mean_instructor_rating": round(sum(inst) / len(inst), 2) if inst else None,
            "mean_reward": round(sum(d.reward for d in decisions) / len(decisions), 3) if decisions else None,
            "final_rewards": len(decisions),
            "submissions": len(subs),
            "mean_words": round(sum(len(s.content.split()) for s in subs) / len(subs), 1) if subs else None,
            "mean_grade": round(sum(numeric) / len(numeric), 2) if numeric else None,
        })
    return out


# ---------------------------------------------------------------- library: styles (I10) & fixed prompts (B6)

@router.get("/styles")
def styles(user: User = Depends(require_instructor), db: Session = Depends(get_db)):
    return [{"key": s.key, "name": s.name, "description": s.description, "prompt_template": s.prompt_template,
             "enabled": s.enabled} for s in db.scalars(select(FeedbackStyle).order_by(FeedbackStyle.key))]


class StyleIn(BaseModel):
    key: str = Field(pattern=r"^[a-z0-9_]{2,32}$")
    name: str
    description: str = ""
    prompt_template: str = ""
    enabled: bool = True


@router.put("/styles/{key}")
def upsert_style(key: str, body: StyleIn, user: User = Depends(require_instructor), db: Session = Depends(get_db)):
    s = db.get(FeedbackStyle, key) or FeedbackStyle(key=key)
    s.name, s.description, s.prompt_template, s.enabled = body.name, body.description, body.prompt_template, body.enabled
    db.merge(s)
    db.commit()
    return {"ok": True}


@router.get("/courses/{course_id}/fixed-prompts")
def fixed_prompts(course_id: int, user: User = Depends(require_instructor), db: Session = Depends(get_db)):
    _course(db, user, course_id)
    return [{"id": p.id, "trigger": p.trigger, "rubric_area": p.rubric_area, "text": p.text, "enabled": p.enabled}
            for p in db.scalars(select(FixedPrompt).where(FixedPrompt.course_id == course_id).order_by(FixedPrompt.id))]


class FixedPromptIn(BaseModel):
    trigger: str = Field(default="any", pattern="^(any|on_demand|idle|sentence_end|deletion)$")
    rubric_area: str = ""
    text: str = Field(min_length=1)
    enabled: bool = True


@router.post("/courses/{course_id}/fixed-prompts")
def create_fixed_prompt(course_id: int, body: FixedPromptIn, user: User = Depends(require_instructor),
                        db: Session = Depends(get_db)):
    _course(db, user, course_id)
    p = FixedPrompt(course_id=course_id, **body.model_dump())
    db.add(p)
    db.commit()
    return {"id": p.id}


@router.put("/fixed-prompts/{prompt_id}")
def update_fixed_prompt(prompt_id: int, body: FixedPromptIn, user: User = Depends(require_instructor),
                        db: Session = Depends(get_db)):
    p = db.get(FixedPrompt, prompt_id)
    if p is None:
        raise HTTPException(404, "Prompt not found")
    _course(db, user, p.course_id)
    for k, v in body.model_dump().items():
        setattr(p, k, v)
    db.commit()
    return {"ok": True}


@router.delete("/fixed-prompts/{prompt_id}")
def delete_fixed_prompt(prompt_id: int, user: User = Depends(require_instructor), db: Session = Depends(get_db)):
    p = db.get(FixedPrompt, prompt_id)
    if p is None:
        raise HTTPException(404, "Prompt not found")
    _course(db, user, p.course_id)
    db.delete(p)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- research: bandit & logs

@router.get("/courses/{course_id}/bandit")
def bandit_state(course_id: int, user: User = Depends(require_instructor), db: Session = Depends(get_db)):
    _course(db, user, course_id)
    arms = db.scalars(select(BanditArmState).where(BanditArmState.course_id == course_id)
                      .order_by(BanditArmState.context_key, BanditArmState.arm)).all()
    preview = bandit.apply_finalized(db, course_id, dry_run=True)
    decisions = db.scalars(select(BanditDecision).where(BanditDecision.course_id == course_id)
                           .order_by(BanditDecision.id.desc()).limit(100)).all()
    pseudo = {u.id: u.pseudonym for u in db.scalars(select(User))}
    return {
        "arms": [{"context_key": a.context_key, "arm": a.arm, "alpha": round(a.alpha, 3), "beta": round(a.beta, 3),
                  "mean": round(a.alpha / (a.alpha + a.beta), 3), "pulls": a.pulls} for a in arms],
        "pending_update": preview,
        "decisions": [{"id": d.id, "student": pseudo.get(d.student_id), "policy": d.policy, "arm": d.arm,
                       "context_key": d.context_key, "probability": round(d.probability, 3),
                       "student_score": d.student_score, "instructor_score": d.instructor_score,
                       "reward": d.reward, "reward_status": d.reward_status, "formula": d.reward_formula,
                       "applied": d.applied, "condition_id": d.condition_id, "created_at": iso(d.created_at)}
                      for d in decisions],
    }


@router.post("/courses/{course_id}/bandit/update")
def bandit_update(course_id: int, user: User = Depends(require_instructor), db: Session = Depends(get_db)):
    _course(db, user, course_id)
    applied = bandit.apply_finalized(db, course_id)
    log_event(db, user, "bandit_updated", {"arms": len(applied)}, course_id)
    return {"applied": applied}


@router.get("/courses/{course_id}/events")
def events(course_id: int, format: str = "json", limit: int = 500, user: User = Depends(require_instructor),
           db: Session = Depends(get_db)):
    _course(db, user, course_id)
    consenting = set(db.scalars(select(User.pseudonym).where(User.research_consent.is_(True))).all())
    rows = [r for r in db.scalars(select(EventLog).where(EventLog.course_id == course_id)
                                  .order_by(EventLog.id.desc()).limit(min(limit, 20000))).all()
            if r.pseudonym in consenting]
    data = [{"id": r.id, "ts": iso(r.ts), "pseudonym": r.pseudonym, "assignment_id": r.assignment_id,
             "condition_id": r.condition_id, "type": r.type, "payload": r.payload} for r in rows]
    if format != "csv":
        return data
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["id", "ts", "pseudonym", "assignment_id", "condition_id", "type", "payload"])
    w.writeheader()
    w.writerows(data)
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f"attachment; filename=events_course_{course_id}.csv"})
