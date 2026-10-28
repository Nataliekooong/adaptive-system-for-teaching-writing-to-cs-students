from sqlalchemy.orm import Session

from ..models import EventLog, User


def log_event(
    db: Session,
    user: User,
    type: str,
    payload: dict | None = None,
    course_id: int | None = None,
    assignment_id: int | None = None,
    condition_id: int | None = None,
    commit: bool = True,
) -> None:
    """Append-only research event, keyed by pseudonym (never by name or username)."""
    db.add(EventLog(
        pseudonym=user.pseudonym, type=type, payload=payload or {}, course_id=course_id,
        assignment_id=assignment_id, condition_id=condition_id,
    ))
    if commit:
        db.commit()
