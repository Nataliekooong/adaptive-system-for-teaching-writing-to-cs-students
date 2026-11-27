
import json
from pathlib import Path
from collections import Counter
from itertools import zip_longest

# ============================================================
# 1. File paths and expected dataset statistics
# ============================================================

DATA_DIR = Path.home() / "Desktop" / "DeepSeek_Dataset"

INPUT_PATH = DATA_DIR / "draft_feedback_b1.jsonl"

MAPPING_PATH = DATA_DIR / "unique_assignments_auto_cleaned.json"

OUTPUT_PATH = DATA_DIR / "draft_feedback_b1_cleaned.jsonl"

REPORT_PATH = DATA_DIR / "cleaning_report.json"

TEMP_PATH = DATA_DIR / "draft_feedback_b1_cleaned.tmp"

EXPECTED_RECORDS = 30530
EXPECTED_ASSIGNMENTS = 36
EXPECTED_MODIFIED_ASSIGNMENTS = 19
EXPECTED_MODIFIED_RECORDS = 14501

REQUIRED_FIELDS = {
    "id",
    "config_hash",
    "assignment",
    "draft",
    "feedback"
}


# ============================================================
# 2. Load and validate assignment mapping
# ============================================================

def load_mapping():

    with MAPPING_PATH.open("r", encoding="utf-8") as f:
        assignments = json.load(f)

    mapping = {}
    expected_occurrences = Counter()
    modified_assignments = 0
    assignment_ids = set()

    for item in assignments:

        assignment_id = item["assignment_id"]
        original = item["original_assignment"]
        cleaned = item["cleaned_assignment"]
        occurrences = item["occurrences"]

        if assignment_id in assignment_ids:
            raise ValueError("Duplicate assignment ID detected.")

        assignment_ids.add(assignment_id)

        if not isinstance(original, str) or not original.strip():
            raise ValueError("Invalid original assignment.")

        if not isinstance(cleaned, str) or not cleaned.strip():
            raise ValueError("Invalid cleaned assignment.")

        if original in mapping:
            raise ValueError("Duplicate original assignment detected.")

        if type(occurrences) is not int or occurrences <= 0:
            raise ValueError("Invalid occurrence count.")

        mapping[original] = cleaned
        expected_occurrences[original] = occurrences

        if original != cleaned:
            modified_assignments += 1

    if len(mapping) != EXPECTED_ASSIGNMENTS:
        raise ValueError("Unexpected number of unique assignments.")

    if sum(expected_occurrences.values()) != EXPECTED_RECORDS:
        raise ValueError("Unexpected mapping record count.")

    if modified_assignments != EXPECTED_MODIFIED_ASSIGNMENTS:
        raise ValueError("Unexpected modified assignment count.")

    return mapping, expected_occurrences


# ============================================================
# 3. Apply cleaning to the full dataset
# ============================================================

def apply_cleaning(mapping, expected_occurrences):

    total_records = 0
    modified_records = 0

    original_characters = 0
    cleaned_characters = 0

    actual_occurrences = Counter()

    with INPUT_PATH.open("r", encoding="utf-8") as source, \
         TEMP_PATH.open("w", encoding="utf-8") as target:

        for line_number, line in enumerate(source, start=1):

            record = json.loads(line)

            if not isinstance(record, dict):
                raise ValueError(
                    f"Invalid record at line {line_number}"
                )

            if not REQUIRED_FIELDS.issubset(record):
                raise ValueError(
                    f"Missing required fields at line {line_number}"
                )

            original_assignment = record["assignment"]

            if not isinstance(original_assignment, str):
                raise ValueError(
                    f"Invalid assignment at line {line_number}"
                )

            if original_assignment not in mapping:
                raise ValueError(
                    f"Unmatched assignment at line {line_number}"
                )

            feedback = record["feedback"]

            if not isinstance(feedback, str) or not feedback.strip():
                raise ValueError(
                    f"Invalid feedback at line {line_number}"
                )

            cleaned_assignment = mapping[original_assignment]

            actual_occurrences[original_assignment] += 1

            original_characters += len(original_assignment)
            cleaned_characters += len(cleaned_assignment)

            # Copy the record and modify only the assignment.
            cleaned_record = record.copy()
            cleaned_record["assignment"] = cleaned_assignment

            if original_assignment != cleaned_assignment:
                modified_records += 1

            target.write(
                json.dumps(
                    cleaned_record,
                    ensure_ascii=False,
                    allow_nan=False
                ) + "\n"
            )

            total_records += 1

            if total_records % 5000 == 0:
                print(f"Processed {total_records} records...")

    if total_records != EXPECTED_RECORDS:
        raise ValueError("Unexpected total record count.")

    if modified_records != EXPECTED_MODIFIED_RECORDS:
        raise ValueError("Unexpected modified record count.")

    if actual_occurrences != expected_occurrences:
        raise ValueError("Assignment occurrence counts do not match.")

    return {
        "total_records": total_records,
        "modified_records": modified_records,
        "unmodified_records": total_records - modified_records,
        "original_assignment_characters": original_characters,
        "cleaned_assignment_characters": cleaned_characters,
        "removed_assignment_characters":
            original_characters - cleaned_characters
    }


# ============================================================
# 4. Validate original and cleaned datasets line by line
# ============================================================

def validate_dataset(mapping):

    validated_records = 0

    with INPUT_PATH.open("r", encoding="utf-8") as original_file, \
         TEMP_PATH.open("r", encoding="utf-8") as cleaned_file:

        pairs = zip_longest(original_file, cleaned_file)

        for line_number, pair in enumerate(pairs, start=1):

            original_line, cleaned_line = pair

            if original_line is None or cleaned_line is None:
                raise ValueError("Dataset record count mismatch.")

            original = json.loads(original_line)
            cleaned = json.loads(cleaned_line)

            # Verify that the dataset schema is unchanged.
            if set(original.keys()) != set(cleaned.keys()):
                raise ValueError(
                    f"Schema mismatch at line {line_number}"
                )

            # Verify the expected assignment transformation.
            expected_assignment = mapping[original["assignment"]]

            if cleaned["assignment"] != expected_assignment:
                raise ValueError(
                    f"Assignment mismatch at line {line_number}"
                )

            if not cleaned["assignment"].strip():
                raise ValueError(
                    f"Empty assignment at line {line_number}"
                )

            # Verify that ALL other fields remain unchanged.
            for field in original:

                if field == "assignment":
                    continue

                if original[field] != cleaned[field]:
                    raise ValueError(
                        f"Field '{field}' changed at line {line_number}"
                    )

            validated_records += 1

    if validated_records != EXPECTED_RECORDS:
        raise ValueError("Validation record count mismatch.")

    return validated_records


# ============================================================
# 5. Main function
# ============================================================

def main():

    print("Full Dataset Cleaning - Version 4")
    print("=" * 60)

    for path in [INPUT_PATH, MAPPING_PATH]:

        if not path.is_file():
            raise FileNotFoundError(
                f"Required file not found: {path}"
            )

    if OUTPUT_PATH.exists() or REPORT_PATH.exists():
        raise FileExistsError(
            "Output or report already exists. "
            "Back up existing files before running again."
        )

    if TEMP_PATH.exists():
        raise FileExistsError(
            f"Temporary file already exists: {TEMP_PATH}"
        )

    mapping, expected_occurrences = load_mapping()

    print(f"Loaded {len(mapping)} unique assignments.")

    try:

        # Generate temporary cleaned dataset.
        statistics = apply_cleaning(
            mapping,
            expected_occurrences
        )

        print("\nCleaning completed.")
        print("Validating cleaned dataset...")

        # Validate every record before publishing the output.
        validated_records = validate_dataset(mapping)

        original_chars = statistics[
            "original_assignment_characters"
        ]

        removed_chars = statistics[
            "removed_assignment_characters"
        ]

        report = {
            "cleaning_version": "V4",
            "unique_assignments": len(mapping),
            "modified_assignments": sum(
                original != cleaned
                for original, cleaned in mapping.items()
            ),
            **statistics,
            "affected_record_percentage": round(
                statistics["modified_records"]
                / statistics["total_records"] * 100,
                4
            ),
            "assignment_character_reduction_percentage": round(
                removed_chars / original_chars * 100,
                4
            ),
            "validation": {
                "status": "PASS",
                "validated_records": validated_records,
                "record_count_preserved": True,
                "schema_preserved": True,
                "assignment_mapping_verified": True,
                "id_preserved": True,
                "config_hash_preserved": True,
                "draft_preserved": True,
                "feedback_preserved": True,
                "all_non_assignment_fields_preserved": True
            },
            "original_file_size_bytes":
                INPUT_PATH.stat().st_size,
            "cleaned_file_size_bytes":
                TEMP_PATH.stat().st_size,
            "input_file": INPUT_PATH.name,
            "output_file": OUTPUT_PATH.name
        }

        # Publish the validated dataset.
        TEMP_PATH.replace(OUTPUT_PATH)

        # Save the cleaning report.
        with REPORT_PATH.open("w", encoding="utf-8") as f:

            json.dump(
                report,
                f,
                ensure_ascii=False,
                indent=4
            )

    except Exception:

        if TEMP_PATH.exists():
            TEMP_PATH.unlink()

        raise

    # ========================================================
    # 6. Print final report
    # ========================================================

    print("\nFinal Dataset Cleaning Report")
    print("=" * 60)

    print(f"Total records: {report['total_records']}")
    print(f"Unique assignments: {report['unique_assignments']}")
    print(f"Modified assignments: {report['modified_assignments']}")
    print(f"Modified records: {report['modified_records']}")
    print(f"Unmodified records: {report['unmodified_records']}")

    print(
        f"Affected record coverage: "
        f"{report['affected_record_percentage']:.2f}%"
    )

    print(
        f"Removed assignment characters: "
        f"{report['removed_assignment_characters']}"
    )

    print(
        f"Assignment character reduction: "
        f"{report['assignment_character_reduction_percentage']:.2f}%"
    )

    print("\nDataset Integrity Validation")
    print("-" * 60)

    print(f"Validated records: {validated_records}")
    print("Record count preserved: PASS")
    print("Assignment mapping verified: PASS")
    print("Dataset schema preserved: PASS")
    print("Assignment occurrence counts preserved: PASS")
    print("ID preserved: PASS")
    print("Config hash preserved: PASS")
    print("Draft preserved: PASS")
    print("Feedback preserved: PASS")
    print("All non-assignment fields preserved: PASS")

    print("\nCleaned dataset:")
    print(OUTPUT_PATH)

    print("\nCleaning report:")
    print(REPORT_PATH)

    print("\nDataset cleaning completed successfully.")
    print("The original dataset was not modified.")


if __name__ == "__main__":
    main()
