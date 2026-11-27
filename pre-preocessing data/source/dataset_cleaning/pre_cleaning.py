import json
from pathlib import Path
from collections import Counter

INPUT_PATH = (
    Path.home()
    / "Desktop"
    / "DeepSeek_Dataset"
    / "draft_feedback_b1.jsonl"
)

total_records = 0
invalid_records = 0
empty_feedback = 0
field_counts = Counter()

with INPUT_PATH.open("r", encoding="utf-8") as f:
    for line in f:
        total_records += 1

        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            invalid_records += 1
            continue

        field_counts.update(record.keys())

        if not str(record.get("feedback") or "").strip():
            empty_feedback += 1

print("Dataset Inspection")
print("-" * 40)
print(f"Total records: {total_records}")
print(f"Invalid JSON records: {invalid_records}")
print(f"Empty feedback: {empty_feedback}")

print("\nField distribution:")
for field, count in field_counts.items():
    print(f"{field}: {count}")
    
    
import re

patterns = {
    "due_dates": r"\b(due date|deadline|due on|due by|submit by)\b",
    "filenames": r"\b(file name|filename|name your file)\b",
    "submission_formats": r"\b(submit|upload|submission|pdf format|docx)\b",
    "workshop_schedules": r"\b(workshop|office hours|class schedule)\b",
    "general_encouragement": r"\b(good luck|great job|well done|keep up the good work)\b",
}

matches = {
    field: Counter()
    for field in ["assignment", "feedback"]
}

with INPUT_PATH.open("r", encoding="utf-8") as f:
    for line in f:
        record = json.loads(line)

        for field in matches:
            text = record.get(field, "")

            for category, pattern in patterns.items():
                if re.search(pattern, text, re.IGNORECASE):
                    matches[field][category] += 1

print("\nAdministrative Text Inspection")
print("-" * 40)

for field, counts in matches.items():
    print(f"\nField: {field}")

    for category in patterns:
        print(f"{category}: {counts[category]}")
print("\nAdministrative Text Samples")
print("=" * 60)

sample_limit = 5

for field in ["assignment", "feedback"]:
    for category, pattern in patterns.items():

        print(f"\nField: {field} | Category: {category}")
        print("-" * 60)

        count = 0
        seen = set()

        with INPUT_PATH.open("r", encoding="utf-8") as f:
            for line in f:
                record = json.loads(line)
                text = record.get(field, "")

                match = re.search(pattern, text, re.IGNORECASE)

                if not match:
                    continue

                start = max(0, match.start() - 150)
                end = min(len(text), match.end() + 150)

                sample = text[start:end]

                if sample in seen:
                    continue

                seen.add(sample)
                count += 1

                print(f"\nSample {count}:")
                print(sample)

                if count >= sample_limit:
                    break

        if count == 0:
            print("No matches found.")
            
# Analyze repeated assignments
assignment_counts = Counter()

with INPUT_PATH.open("r", encoding="utf-8") as f:
    for line in f:
        record = json.loads(line)
        assignment_counts[record["assignment"]] += 1

print("\nAssignment Distribution")
print("-" * 50)

print(f"Total records: {sum(assignment_counts.values())}")
print(f"Unique assignments: {len(assignment_counts)}")

print("\nMost frequent assignments:")

for i, (assignment, count) in enumerate(
    assignment_counts.most_common(10), start=1
):
    print(f"\nAssignment {i}")
    print(f"Occurrences: {count}")
    print(f"Preview: {assignment[:200]}")
    
# Export unique assignments for manual review

unique_assignments = []

for i, (assignment, count) in enumerate(
    assignment_counts.most_common(), start=1
):
    unique_assignments.append({
        "assignment_id": i,
        "occurrences": count,
        "original_assignment": assignment,
        "cleaned_assignment": assignment
    })

output_path = INPUT_PATH.parent / "unique_assignments.json"

with output_path.open("w", encoding="utf-8") as f:
    json.dump(
        unique_assignments,
        f,
        ensure_ascii=False,
        indent=4
    )

print("\nUnique Assignment Export")
print("-" * 50)
print(f"Exported assignments: {len(unique_assignments)}")
print(f"Saved to: {output_path}")