"""Whole-document revision rounds bounded by on-demand feedback requests."""
import re
from difflib import SequenceMatcher

from ..serializers import feedback_out, iso


def text_changes(before: str, after: str) -> list[dict]:
    # Preserve punctuation and whitespace so either document can be reconstructed.
    tokens = lambda text: re.findall(r"\w+|[^\w\s]|\s+", text)
    old, new = tokens(before), tokens(after)
    changes = []
    for kind, i, j, x, y in SequenceMatcher(None, old, new).get_opcodes():
        if kind == "equal":
            changes.append({"kind": "equal", "text": "".join(new[x:y])})
        else:
            if i != j:
                changes.append({"kind": "delete", "text": "".join(old[i:j])})
            if x != y:
                changes.append({"kind": "insert", "text": "".join(new[x:y])})
    return changes


def revision_history(versions, submission=None, feedback=()) -> list[dict]:
    history = []
    previous = ""
    preceding_feedback = None
    feedback_by_snapshot = {f.snapshot_version_id: f for f in feedback if f.venue == "on_demand"}
    for version in sorted(versions, key=lambda v: (v.created_at, v.id)):
        if submission and version.id > submission.version_id:
            continue
        if version.kind != "feedback_request":
            continue
        history.append({"id": version.id, "created_at": iso(version.created_at),
                        "content": version.content, "words": len(version.content.split()),
                        "changes": text_changes(previous, version.content), "is_submission": False,
                        "preceding_feedback": feedback_out(preceding_feedback) if preceding_feedback else None})
        previous = version.content
        preceding_feedback = feedback_by_snapshot.get(version.id)
    # Submission closes the last writing interval, even if no further feedback was requested.
    if submission:
        history.append({"id": submission.version_id, "created_at": iso(submission.submitted_at),
                        "content": submission.content, "words": len(submission.content.split()),
                        "changes": text_changes(previous, submission.content), "is_submission": True,
                        "preceding_feedback": feedback_out(preceding_feedback) if preceding_feedback else None})
    return history
