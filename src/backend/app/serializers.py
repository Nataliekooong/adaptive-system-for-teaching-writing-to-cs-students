from datetime import datetime

from .models import Assignment, DraftVersion, FeedbackItem, Submission


def iso(dt: datetime | None) -> str | None:
    return dt.isoformat() + "Z" if dt else None


def assignment_out(a: Assignment) -> dict:
    return {
        "id": a.id, "course_id": a.course_id, "title": a.title, "description": a.description,
        "instructions": a.instructions, "genre_guidance": a.genre_guidance, "due_date": iso(a.due_date),
        "rubric_areas": a.rubric_areas, "get_started_content": a.get_started_content,
        "published": a.published,
    }


def feedback_out(f: FeedbackItem, research: bool = False) -> dict:
    out = {
        "id": f.id, "venue": f.venue, "source": f.source, "trigger": f.trigger, "presentation": f.presentation,
        "content": f.content, "student_helpful": f.student_helpful, "dismissed": f.dismissed,
        "created_at": iso(f.created_at),
    }
    if research:
        out.update({"style": f.style, "model_version": f.model_version, "prompt_template": f.prompt_template,
                    "guardrail_status": f.guardrail_status, "decision_id": f.decision_id,
                    "condition_id": f.condition_id, "instructor_rating": f.instructor_rating,
                    "snapshot_version_id": f.snapshot_version_id})
    return out


def version_out(v: DraftVersion) -> dict:
    return {"id": v.id, "kind": v.kind, "created_at": iso(v.created_at), "words": len(v.content.split()),
            "preview": v.content[:120]}


def submission_out(s: Submission, include_grade: bool) -> dict:
    out = {"id": s.id, "submitted_at": iso(s.submitted_at), "released": s.released, "version_id": s.version_id}
    if include_grade and s.released:
        out.update({"grade": s.grade, "comments": s.comments})
    return out
