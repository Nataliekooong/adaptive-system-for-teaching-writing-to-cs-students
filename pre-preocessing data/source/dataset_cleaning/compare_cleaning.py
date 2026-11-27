import json
import difflib
from pathlib import Path

DATA_DIR = Path.home() / "Desktop" / "DeepSeek_Dataset"

AUTO_PATH = DATA_DIR / "unique_assignments_auto_cleaned.json"
REVIEWED_PATH = DATA_DIR / "unique_assignments_reviewed.json"
REPORT_PATH = DATA_DIR / "cleaning_comparison.txt"


def load_assignments(path):
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return {
        item["original_assignment"]: item
        for item in data
    }


auto_data = load_assignments(AUTO_PATH)
reviewed_data = load_assignments(REVIEWED_PATH)

if auto_data.keys() != reviewed_data.keys():
    raise ValueError("Assignment datasets do not match.")

same = 0
different = 0
affected_records = 0

with REPORT_PATH.open("w", encoding="utf-8") as report:

    for original, auto_item in auto_data.items():

        reviewed_item = reviewed_data[original]

        auto_text = auto_item["cleaned_assignment"]
        reviewed_text = reviewed_item["cleaned_assignment"]

        if auto_text == reviewed_text:
            same += 1
            continue

        different += 1
        affected_records += auto_item["occurrences"]

        report.write(
            f"\nAssignment {auto_item['assignment_id']}\n"
        )

        report.write(
            f"Affected records: {auto_item['occurrences']}\n"
        )

        report.write("=" * 60 + "\n")

        diff = difflib.unified_diff(
            auto_text.splitlines(),
            reviewed_text.splitlines(),
            fromfile="Automatic cleaning",
            tofile="Reviewed reference",
            lineterm=""
        )

        report.write("\n".join(diff))
        report.write("\n\n")


print("Cleaning Comparison Report")
print("=" * 50)

print(f"Total assignments: {len(auto_data)}")
print(f"Identical results: {same}")
print(f"Different results: {different}")
print(f"Records with different results: {affected_records}")
print(f"Report saved to: {REPORT_PATH}")