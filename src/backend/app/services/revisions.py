"""Content-based revision history, independent of feedback request counts."""
import re
from difflib import SequenceMatcher

from ..serializers import iso


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


def revision_history(versions, submission=None) -> list[dict]:
    history = []
    previous = ""
    for version in sorted(versions, key=lambda v: (v.created_at, v.id)):
        if submission and version.id > submission.version_id:
            continue
        if version.content == previous:
            continue
        history.append({"id": version.id, "created_at": iso(version.created_at),
                        "content": version.content, "words": len(version.content.split()),
                        "changes": text_changes(previous, version.content), "is_submission": False})
        previous = version.content
    if submission:
        if not history or previous != submission.content:
            history.append({"id": submission.version_id, "created_at": iso(submission.submitted_at),
                            "content": submission.content, "words": len(submission.content.split()),
                            "changes": text_changes(previous, submission.content), "is_submission": True})
        else:
            history[-1]["is_submission"] = True
        history[-1]["submitted_at"] = iso(submission.submitted_at)
    return history
