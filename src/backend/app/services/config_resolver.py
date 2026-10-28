"""Resolves the effective module configuration for a (student, assignment) pair.

Layer order (later wins):
    system → course → assignment → active experiment condition(s) → per-student override
Course-scoped experiments are applied before assignment-scoped ones.
Students are lazily placed into a condition the first time they touch an active experiment.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import modules
from ..models import (
    Assignment,
    AssignmentStudent,
    Condition,
    ConditionAssignment,
    Course,
    Experiment,
)


@dataclass
class Resolved:
    config: dict
    provenance: dict
    conditions: list[Condition] = field(default_factory=list)

    @property
    def condition_id(self) -> int | None:
        # The most specific condition (assignment-scoped beats course-scoped) labels the logs.
        return self.conditions[-1].id if self.conditions else None

    def on(self, module_key: str) -> bool:
        return bool(self.config[module_key]["enabled"])

    def get(self, module_key: str, setting: str):
        return self.config[module_key][setting]


def pick_condition(db: Session, exp: Experiment, strategy: str | None = None) -> Condition | None:
    conds = list(exp.conditions)
    if not conds:
        return None
    strategy = strategy or exp.strategy
    if strategy == "random":
        return random.choices(conds, weights=[max(c.weight, 0.0001) for c in conds])[0]
    if strategy == "balanced":
        counts = dict(
            db.execute(
                select(ConditionAssignment.condition_id, func.count())
                .where(ConditionAssignment.experiment_id == exp.id)
                .group_by(ConditionAssignment.condition_id)
            ).all()
        )
        # Fill the condition that is furthest below its weighted share.
        return min(conds, key=lambda c: (counts.get(c.id, 0) / max(c.weight, 0.0001), c.id))
    return None  # manual: unassigned students get the base configuration


def condition_for(db: Session, exp: Experiment, student_id: int, auto_assign: bool = True) -> Condition | None:
    ca = db.scalar(
        select(ConditionAssignment).where(
            ConditionAssignment.experiment_id == exp.id, ConditionAssignment.student_id == student_id
        )
    )
    if ca:
        return db.get(Condition, ca.condition_id)
    if not auto_assign or exp.status != "active":
        return None
    cond = pick_condition(db, exp)
    if cond is None:
        return None
    db.add(ConditionAssignment(experiment_id=exp.id, condition_id=cond.id, student_id=student_id,
                               assigned_by=exp.strategy))
    db.commit()
    return cond


def _active_experiments(db: Session, course_id: int, assignment_id: int | None) -> list[Experiment]:
    exps = db.scalars(
        select(Experiment).where(Experiment.course_id == course_id, Experiment.status == "active")
        .order_by(Experiment.id)
    ).all()
    course_scoped = [e for e in exps if e.assignment_id is None]
    assignment_scoped = [e for e in exps if assignment_id is not None and e.assignment_id == assignment_id]
    return course_scoped + assignment_scoped


def resolve_for_course(db: Session, course: Course, student_id: int | None) -> Resolved:
    layers: list[tuple[str, dict]] = [("course", course.config)]
    conditions: list[Condition] = []
    if student_id is not None:
        for exp in _active_experiments(db, course.id, None):
            cond = condition_for(db, exp, student_id)
            if cond:
                conditions.append(cond)
                layers.append((f"experiment:{exp.name} / {cond.name}", cond.config))
    config, prov = modules.resolve(layers)
    return Resolved(config, prov, conditions)


def resolve_for_assignment(
    db: Session, assignment: Assignment, student_id: int | None, auto_assign: bool = True
) -> Resolved:
    course = db.get(Course, assignment.course_id)
    layers: list[tuple[str, dict]] = [("course", course.config), ("assignment", assignment.config)]
    conditions: list[Condition] = []
    if student_id is not None:
        for exp in _active_experiments(db, course.id, assignment.id):
            cond = condition_for(db, exp, student_id, auto_assign)
            if cond:
                conditions.append(cond)
                layers.append((f"experiment:{exp.name} / {cond.name}", cond.config))
        link = db.scalar(
            select(AssignmentStudent).where(
                AssignmentStudent.assignment_id == assignment.id, AssignmentStudent.student_id == student_id
            )
        )
        if link and link.override_config:
            layers.append(("student override", link.override_config))
    config, prov = modules.resolve(layers)
    return Resolved(config, prov, conditions)
