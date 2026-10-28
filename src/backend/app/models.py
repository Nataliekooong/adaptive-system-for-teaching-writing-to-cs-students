"""ORM models.

Layered configuration lives in JSON columns (`config`, `override_config`): each is a *partial*
override of the module registry defaults (see app/modules.py). Logs are append-only.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    display_name: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(16))  # student | instructor
    password_hash: Mapped[str] = mapped_column(String(256))
    pseudonym: Mapped[str] = mapped_column(String(32), unique=True)
    research_consent: Mapped[bool] = mapped_column(Boolean, default=True)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Course(Base):
    __tablename__ = "courses"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(200))
    instructor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    rubric_areas: Mapped[list] = mapped_column(JSON, default=list)
    config: Mapped[dict] = mapped_column(JSON, default=dict)  # course-level module overrides


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (UniqueConstraint("course_id", "user_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))


class Assignment(Base):
    __tablename__ = "assignments"
    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    instructions: Mapped[str] = mapped_column(Text, default="")
    genre_guidance: Mapped[str] = mapped_column(Text, default="")
    due_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rubric_areas: Mapped[list] = mapped_column(JSON, default=list)  # feedback priority areas (I4)
    get_started_content: Mapped[str] = mapped_column(Text, default="")
    config: Mapped[dict] = mapped_column(JSON, default=dict)  # assignment-level module overrides
    published: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    course: Mapped[Course] = relationship()


class AssignmentStudent(Base):
    """I3 enrollment in an assignment + I5 per-student overrides."""

    __tablename__ = "assignment_students"
    __table_args__ = (UniqueConstraint("assignment_id", "student_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id"))
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    override_config: Mapped[dict] = mapped_column(JSON, default=dict)


class Experiment(Base):
    """An A/B (or A/B/n) test. Scoped to a course, or narrowed to one assignment."""

    __tablename__ = "experiments"
    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"))
    assignment_id: Mapped[int | None] = mapped_column(ForeignKey("assignments.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(200))
    hypothesis: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft|active|paused|completed
    strategy: Mapped[str] = mapped_column(String(16), default="balanced")  # random|balanced|manual
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    conditions: Mapped[list["Condition"]] = relationship(
        back_populates="experiment", cascade="all, delete-orphan", order_by="Condition.id"
    )


class Condition(Base):
    __tablename__ = "conditions"
    id: Mapped[int] = mapped_column(primary_key=True)
    experiment_id: Mapped[int] = mapped_column(ForeignKey("experiments.id"))
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="")
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    config: Mapped[dict] = mapped_column(JSON, default=dict)

    experiment: Mapped[Experiment] = relationship(back_populates="conditions")


class ConditionAssignment(Base):
    __tablename__ = "condition_assignments"
    __table_args__ = (UniqueConstraint("experiment_id", "student_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    experiment_id: Mapped[int] = mapped_column(ForeignKey("experiments.id"))
    condition_id: Mapped[int] = mapped_column(ForeignKey("conditions.id"))
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    assigned_by: Mapped[str] = mapped_column(String(16))  # random|balanced|manual
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class LearnerProfile(Base):
    __tablename__ = "learner_profiles"
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    questionnaire: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    mastery: Mapped[dict] = mapped_column(JSON, default=dict)  # BKT P(L) per rubric area
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Draft(Base):
    __tablename__ = "drafts"
    __table_args__ = (UniqueConstraint("assignment_id", "student_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id"))
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    content: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    locked: Mapped[bool] = mapped_column(Boolean, default=False)


class DraftVersion(Base):
    """Immutable snapshot. kind: manual|autosave|feedback_request|paste_before|paste_after|restore|submit"""

    __tablename__ = "draft_versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    draft_id: Mapped[int] = mapped_column(ForeignKey("drafts.id"))
    content: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class FeedbackStyle(Base):
    """Bandit arms (MAB1). Instructors can enable/disable/edit them (I10)."""

    __tablename__ = "feedback_styles"
    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="")
    prompt_template: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class FixedPrompt(Base):
    """Instructor-authored, pre-approved prompts (S9, B6)."""

    __tablename__ = "fixed_prompts"
    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"))
    trigger: Mapped[str] = mapped_column(String(32), default="any")  # any|on_demand|idle|sentence_end|deletion
    rubric_area: Mapped[str] = mapped_column(String(100), default="")
    text: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class BanditDecision(Base):
    """One style-selection decision (MAB6). Ratings and reward are appended later."""

    __tablename__ = "bandit_decisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"))
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id"))
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    condition_id: Mapped[int | None] = mapped_column(ForeignKey("conditions.id"), nullable=True)
    policy: Mapped[str] = mapped_column(String(16))  # bandit|random|fixed
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    context_key: Mapped[str] = mapped_column(String(64))
    arm: Mapped[str] = mapped_column(String(32))
    probability: Mapped[float] = mapped_column(Float)
    reward_config: Mapped[dict] = mapped_column(JSON, default=dict)  # snapshot of reward module at decision time
    student_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    instructor_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    reward: Mapped[float | None] = mapped_column(Float, nullable=True)
    reward_status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|final|skipped
    reward_formula: Mapped[str] = mapped_column(String(128), default="")
    applied: Mapped[bool] = mapped_column(Boolean, default=False)  # folded into arm posteriors yet?
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class BanditArmState(Base):
    __tablename__ = "bandit_arm_states"
    __table_args__ = (UniqueConstraint("course_id", "context_key", "arm"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"))
    context_key: Mapped[str] = mapped_column(String(64))
    arm: Mapped[str] = mapped_column(String(32))
    alpha: Mapped[float] = mapped_column(Float, default=1.0)
    beta: Mapped[float] = mapped_column(Float, default=1.0)
    pulls: Mapped[int] = mapped_column(Integer, default=0)


class FeedbackItem(Base):
    __tablename__ = "feedback_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id"))
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    condition_id: Mapped[int | None] = mapped_column(ForeignKey("conditions.id"), nullable=True)
    venue: Mapped[str] = mapped_column(String(16))  # on_demand|realtime
    source: Mapped[str] = mapped_column(String(16))  # slm|fixed_prompts
    style: Mapped[str | None] = mapped_column(String(32), nullable=True)
    trigger: Mapped[str | None] = mapped_column(String(32), nullable=True)
    presentation: Mapped[str] = mapped_column(String(32), default="")
    snapshot_version_id: Mapped[int | None] = mapped_column(ForeignKey("draft_versions.id"), nullable=True)
    decision_id: Mapped[int | None] = mapped_column(ForeignKey("bandit_decisions.id"), nullable=True)
    content: Mapped[dict] = mapped_column(JSON)  # {summary, items:[{rubric_area, comment, suggestion, quote}]}
    model_version: Mapped[str] = mapped_column(String(64))
    prompt_template: Mapped[str] = mapped_column(String(64))
    guardrail_status: Mapped[str] = mapped_column(String(16), default="approved")  # approved|rewritten|blocked
    student_helpful: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    instructor_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1..5
    instructor_rated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    dismissed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Submission(Base):
    __tablename__ = "submissions"
    __table_args__ = (UniqueConstraint("assignment_id", "student_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id"))
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    version_id: Mapped[int] = mapped_column(ForeignKey("draft_versions.id"))
    content: Mapped[str] = mapped_column(Text)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    grade: Mapped[str | None] = mapped_column(String(32), nullable=True)
    comments: Mapped[str] = mapped_column(Text, default="")
    released: Mapped[bool] = mapped_column(Boolean, default=False)


class EventLog(Base):
    """Append-only research log. Linked to pseudonym, assignment and study condition."""

    __tablename__ = "event_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=now)
    pseudonym: Mapped[str] = mapped_column(String(32))
    course_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assignment_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    condition_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    type: Mapped[str] = mapped_column(String(48))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
