
import json
import re
from pathlib import Path
from collections import Counter

# ============================================================
# File paths
# ============================================================

DATA_DIR = Path.home() / "Desktop" / "DeepSeek_Dataset"

INPUT_PATH = DATA_DIR / "draft_feedback_b1.jsonl"
OUTPUT_PATH = DATA_DIR / "feedback_review.json"

# ============================================================
# Feedback detection rules
# These rules flag candidates for review, not automatic removal.
# ============================================================

DETECTION_RULES = {

    "due_dates": [
        r"\bdue dates?\b",
        r"\bdeadlines?\b",
        r"\bdue by\b",
        r"\bdue on\b",
        r"\bmidnight\b",
        r"\bsubmission date\b",
        r"\blate submission\b",
    ],

    "filenames": [
        r"\bfile\s*names?\b",
        r"\bnaming convention\b",
        r"\brename your file\b",
        r"\bname your file\b",
    ],

    "submission_formats": [
        r"\.docx?\b",
        r"\.pdf\b",
        r"\bword document\b",
        r"\bsubmission format\b",
        r"\bfile format\b",
        r"\bPDF format\b",
        r"\bsubmit your file\b",
    ],

    "workshop_schedules": [
        r"\bworkshop\b",
        r"\bworkshopping\b",
        r"\bclass schedule\b",
        r"\bclass session\b",
        r"\bsign up\b",
        r"\bpeer review session\b",
    ],

    "submission_platforms": [
        r"\bCanvas\b",
        r"\bOneDrive\b",
        r"\bupload\b",
        r"\bsubmission folder\b",
        r"\blog in\b",
    ],

    "office_hours": [
        r"\boffice hours\b",
        r"\bschedule an appointment\b",
        r"\bmeet with your instructor\b",
    ],

    "general_encouragement": [
        r"\bgood luck\b",
        r"\bgreat job\b",
        r"\bkeep up the good work\b",
        r"\byou can do it\b",
        r"\bwell done\b",
        r"\bkeep it up\b",
        r"\bhappy writing\b",
        r"\bjust do your best\b",
        r"\bI am proud of you\b",
    ],
}

# Compile patterns once for efficient scanning
COMPILED_RULES = {
    category: [
        re.compile(pattern, re.IGNORECASE)
        for pattern in patterns
    ]
    for category, patterns in DETECTION_RULES.items()
}


# ============================================================
# Extract text without modifying the original feedback
# ============================================================

def extract_text(value, path="feedback"):
    if isinstance(value, str):
        yield path, value

    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from extract_text(
                item,
                f"{path}[{index}]"
            )

    elif isinstance(value, dict):
        for key, item in value.items():
            yield from extract_text(
                item,
                f"{path}.{key}"
            )


# ============================================================
# Detect potentially administrative content
# ============================================================

def detect_feedback(feedback):

    matches = []

    for field_path, text in extract_text(feedback):

        for category, patterns in COMPILED_RULES.items():

            seen = set()

            for pattern in patterns:

                for match in pattern.finditer(text):

                    span = match.span()

                    if span in seen:
                        continue

                    seen.add(span)

                    start = max(0, match.start() - 150)
                    end = min(len(text), match.end() + 150)

                    matches.append({
                        "category": category,
                        "field_path": field_path,
                        "matched_text": match.group(),
                        "context": text[start:end],
                        "start": match.start(),
                        "end": match.end()
                    })

    return matches


# ============================================================
# Review the complete dataset
# ============================================================

def main():

    total_records = 0
    flagged_records = 0
    invalid_records = 0
    empty_feedback_records = 0

    category_matches = Counter()
    category_records = Counter()
    feedback_types = Counter()

    review_results = []

    with INPUT_PATH.open("r", encoding="utf-8") as f:

        for line_number, line in enumerate(f, start=1):

            total_records += 1

            try:
                record = json.loads(line)

                if not isinstance(record, dict):
                    invalid_records += 1
                    continue

            except json.JSONDecodeError:
                invalid_records += 1
                continue

            feedback = record.get("feedback")

            feedback_types[type(feedback).__name__] += 1

            if not any(
                text.strip()
                for _, text in extract_text(feedback)
            ):
                empty_feedback_records += 1
                continue

            matches = detect_feedback(feedback)

            if not matches:
                continue

            flagged_records += 1

            categories = {
                match["category"]
                for match in matches
            }

            category_records.update(categories)

            category_matches.update(
                match["category"]
                for match in matches
            )

            review_results.append({
                "line_number": line_number,
                "id": record.get("id"),
                "config_hash": record.get("config_hash"),
                "categories": sorted(categories),
                "matches": matches,
                "original_feedback": feedback,
                "review_status": "pending"
            })

    # ========================================================
    # Generate review report
    # ========================================================

    flagged_percentage = (
        flagged_records / total_records * 100
        if total_records else 0
    )

    report = {
        "summary": {
            "total_records": total_records,
            "flagged_records": flagged_records,
            "flagged_percentage": round(flagged_percentage, 4),
            "invalid_records": invalid_records,
            "empty_feedback_records": empty_feedback_records,
            "feedback_types": dict(feedback_types),
            "category_matches": dict(category_matches),
            "category_records": dict(category_records)
        },
        "flagged_feedback": review_results
    }

    with OUTPUT_PATH.open("w", encoding="utf-8") as f:

        json.dump(
            report,
            f,
            ensure_ascii=False,
            indent=4
        )

    # ========================================================
    # Print summary
    # ========================================================

    print("\nFeedback Review Report")
    print("=" * 60)

    print(f"Total records: {total_records}")
    print(f"Flagged feedback records: {flagged_records}")
    print(f"Flagged percentage: {flagged_percentage:.4f}%")
    print(f"Invalid records: {invalid_records}")
    print(f"Empty feedback records: {empty_feedback_records}")

    print("\nFeedback data types")
    print("-" * 60)

    for name, count in sorted(feedback_types.items()):
        print(f"{name}: {count}")

    print("\nKeyword matches by category")
    print("-" * 60)

    for category in DETECTION_RULES:
        print(f"{category}: {category_matches[category]}")

    print("\nFlagged records by category")
    print("-" * 60)

    for category in DETECTION_RULES:
        print(f"{category}: {category_records[category]}")

    print("\nOutput file:")
    print(OUTPUT_PATH)

    print("\nReview completed.")
    print("No original training data was modified.")


if __name__ == "__main__":
    main()
