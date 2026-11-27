
import json
import unittest
from pathlib import Path

from clean_assignments import clean_assignment


DATA_DIR = Path.home() / "Desktop" / "DeepSeek_Dataset"

ORIGINAL_PATH = DATA_DIR / "unique_assignments.json"
CLEANED_PATH = DATA_DIR / "unique_assignments_auto_cleaned.json"


# ============================================================
# 1. Unit tests for assignment cleaning
# ============================================================

class TestAssignmentCleaning(unittest.TestCase):

    def test_remove_answer_space(self):
        text = (
            "Write an argumentative essay. "
            "Write your response in the space provided."
        )

        cleaned, changes = clean_assignment(text)

        self.assertEqual(
            cleaned,
            "Write an argumentative essay."
        )
        self.assertIn("answer_space", changes)

    def test_remove_due_dates(self):
        text = (
            "The basics: due by midnight, Wednesday, February 12th.\n"
            "Write a short story of at least 500 words."
        )

        cleaned, changes = clean_assignment(text)

        self.assertNotIn("midnight", cleaned)
        self.assertIn("500 words", cleaned)
        self.assertIn("due_dates", changes)

    def test_remove_filenames(self):
        text = (
            "Write a short story.\n"
            "Remember to title your file distinctively."
        )

        cleaned, changes = clean_assignment(text)

        self.assertNotIn("file distinctively", cleaned)
        self.assertIn("Write a short story.", cleaned)
        self.assertIn("filenames", changes)

    def test_remove_submission_formats(self):
        text = (
            "Write a 1000-word essay. "
            "Submit a .doc file."
        )

        cleaned, changes = clean_assignment(text)

        self.assertNotIn(".doc file", cleaned)
        self.assertIn("1000-word essay", cleaned)

    def test_remove_workshop_schedules(self):
        text = (
            "Write a complete short story.\n\n"
            "It will be returned before the first round "
            "of workshops, scheduled for Friday.\n\n"
            "Revise your story for the final portfolio."
        )

        cleaned, changes = clean_assignment(text)

        self.assertNotIn("scheduled for Friday", cleaned)
        self.assertIn("Revise your story", cleaned)
        self.assertIn("workshop_schedules", changes)

    def test_remove_generic_encouragement(self):
        text = (
            "Develop a clear central argument.\n\n"
            "Good luck! Have fun!"
        )

        cleaned, changes = clean_assignment(text)

        self.assertEqual(
            cleaned,
            "Develop a clear central argument."
        )
        self.assertIn("general_encouragement", changes)

    def test_remove_login_instructions(self):
        text = (
            "Please go to our Wikipedia course site "
            "and log in using your account information.\n\n"
            "Use at least five academic sources."
        )

        cleaned, changes = clean_assignment(text)

        self.assertNotIn("log in", cleaned)
        self.assertIn("five academic sources", cleaned)

    def test_remove_platform_reference(self):
        text = (
            "Use the writing forms chosen from the options "
            "we discussed in class "
            "(see the resources on our Canvas site)."
        )

        cleaned, changes = clean_assignment(text)

        self.assertNotIn("Canvas", cleaned)
        self.assertIn("writing forms", cleaned)


# ============================================================
# 2. Tests for preserving academic requirements
# ============================================================

class TestAcademicContentPreservation(unittest.TestCase):

    def test_preserve_word_count(self):
        text = (
            "Write an essay between 600 and 900 words. "
            "Submit a .doc file."
        )

        cleaned, _ = clean_assignment(text)

        self.assertIn("600 and 900 words", cleaned)

    def test_preserve_page_limits(self):
        text = (
            "Write a short story between 3 and 10 pages. "
            "Submit a .doc file."
        )

        cleaned, _ = clean_assignment(text)

        self.assertIn("3 and 10 pages", cleaned)

    def test_preserve_rubric(self):
        text = (
            "RUBRIC:\n"
            "Argument and evidence: 40 pts\n"
            "Organization: 30 pts\n"
            "Grammar and punctuation: 30 pts\n\n"
            "Happy writing!"
        )

        cleaned, _ = clean_assignment(text)

        self.assertIn("Argument and evidence: 40 pts", cleaned)
        self.assertIn("Organization: 30 pts", cleaned)
        self.assertIn("Grammar and punctuation: 30 pts", cleaned)

    def test_preserve_citation_formats(self):
        text = (
            "Use MLA format and APA citations where appropriate. "
            "Submit a .doc file."
        )

        cleaned, _ = clean_assignment(text)

        self.assertIn("MLA format", cleaned)
        self.assertIn("APA citations", cleaned)

    def test_preserve_source_requirements(self):
        text = (
            "Use at least five academic sources "
            "to support your argument."
        )

        cleaned, changes = clean_assignment(text)

        self.assertEqual(cleaned, text)
        self.assertEqual(changes, {})

    def test_preserve_writing_guidance(self):
        text = (
            "Develop strong characters, establish conflict, "
            "and maintain a consistent narrative perspective."
        )

        cleaned, _ = clean_assignment(text)

        self.assertEqual(cleaned, text)

    def test_preserve_revision_requirements(self):
        text = (
            "Everyone must fully and meaningfully revise "
            "their stories for the final portfolio!"
        )

        cleaned, _ = clean_assignment(text)

        self.assertEqual(cleaned, text)

    def test_preserve_contextual_deadline(self):
        text = (
            "The protagonist faces a deadline to pay rent. "
            "Develop this conflict throughout the story."
        )

        cleaned, _ = clean_assignment(text)

        self.assertEqual(cleaned, text)

    def test_preserve_contextual_midnight(self):
        text = (
            "The story begins at midnight. "
            "Use descriptive language to establish the setting."
        )

        cleaned, _ = clean_assignment(text)

        self.assertEqual(cleaned, text)

    def test_preserve_contextual_workshop(self):
        text = (
            "Describe how the protagonist repairs "
            "the broken machine in his workshop."
        )

        cleaned, _ = clean_assignment(text)

        self.assertEqual(cleaned, text)


# ============================================================
# 3. Safety and consistency tests
# ============================================================

class TestCleaningSafety(unittest.TestCase):

    def test_unchanged_clean_text(self):
        text = (
            "Write an argumentative essay with a clear thesis, "
            "supporting evidence, and a conclusion."
        )

        cleaned, changes = clean_assignment(text)

        self.assertEqual(cleaned, text)
        self.assertEqual(changes, {})

    def test_idempotency(self):
        text = (
            "Write an argumentative essay. "
            "Write your response in the space provided.\n\n"
            "Happy writing!"
        )

        first_cleaned, _ = clean_assignment(text)
        second_cleaned, second_changes = clean_assignment(
            first_cleaned
        )

        self.assertEqual(first_cleaned, second_cleaned)
        self.assertEqual(second_changes, {})

    def test_prevent_empty_assignment(self):
        text = "Good luck! Have fun!"

        with self.assertRaises(ValueError):
            clean_assignment(text)

    def test_invalid_input(self):
        for invalid_value in [None, 123, [], {}]:

            with self.subTest(value=invalid_value):

                with self.assertRaises(TypeError):
                    clean_assignment(invalid_value)


# ============================================================
# 4. Integration tests using the actual assignment dataset
# ============================================================

class TestAssignmentDataset(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        with ORIGINAL_PATH.open("r", encoding="utf-8") as f:
            cls.original_data = json.load(f)

        with CLEANED_PATH.open("r", encoding="utf-8") as f:
            cls.cleaned_data = json.load(f)

        cls.original_mapping = {
            item["assignment_id"]: item
            for item in cls.original_data
        }

        cls.cleaned_mapping = {
            item["assignment_id"]: item
            for item in cls.cleaned_data
        }

    def test_unique_assignment_count(self):
        self.assertEqual(len(self.original_data), 36)
        self.assertEqual(len(self.cleaned_data), 36)

    def test_total_record_count(self):

        original_count = sum(
            item["occurrences"]
            for item in self.original_data
        )

        cleaned_count = sum(
            item["occurrences"]
            for item in self.cleaned_data
        )

        self.assertEqual(original_count, 30530)
        self.assertEqual(cleaned_count, 30530)

    def test_no_duplicate_assignment_ids(self):

        ids = [
            item["assignment_id"]
            for item in self.cleaned_data
        ]

        self.assertEqual(len(ids), len(set(ids)))

    def test_no_duplicate_original_assignments(self):

        originals = [
            item["original_assignment"]
            for item in self.cleaned_data
        ]

        self.assertEqual(
            len(originals),
            len(set(originals))
        )

    def test_preserve_assignment_ids(self):

        self.assertEqual(
            set(self.original_mapping),
            set(self.cleaned_mapping)
        )

    def test_preserve_original_fields(self):

        for assignment_id, original in self.original_mapping.items():

            with self.subTest(assignment_id=assignment_id):

                cleaned = self.cleaned_mapping[assignment_id]

                self.assertEqual(
                    original["original_assignment"],
                    cleaned["original_assignment"]
                )

                self.assertEqual(
                    original["occurrences"],
                    cleaned["occurrences"]
                )

    def test_no_empty_cleaned_assignments(self):

        for item in self.cleaned_data:

            with self.subTest(
                assignment_id=item["assignment_id"]
            ):

                self.assertIsInstance(
                    item["cleaned_assignment"],
                    str
                )

                self.assertTrue(
                    item["cleaned_assignment"].strip()
                )

    def test_dataset_reproducibility(self):

        for item in self.cleaned_data:

            with self.subTest(
                assignment_id=item["assignment_id"]
            ):

                cleaned, changes = clean_assignment(
                    item["original_assignment"]
                )

                self.assertEqual(
                    cleaned,
                    item["cleaned_assignment"]
                )

                self.assertEqual(
                    changes,
                    item["cleaning_changes"]
                )

    def test_dataset_idempotency(self):

        for item in self.cleaned_data:

            with self.subTest(
                assignment_id=item["assignment_id"]
            ):

                first_cleaned = item["cleaned_assignment"]

                second_cleaned, changes = clean_assignment(
                    first_cleaned
                )

                self.assertEqual(
                    first_cleaned,
                    second_cleaned
                )

                self.assertEqual(changes, {})

    def test_modified_assignment_count(self):

        modified_count = sum(
            item["original_assignment"]
            != item["cleaned_assignment"]
            for item in self.cleaned_data
        )

        self.assertEqual(modified_count, 19)

    def test_affected_record_count(self):

        affected_count = sum(
            item["occurrences"]
            for item in self.cleaned_data
            if item["original_assignment"]
            != item["cleaned_assignment"]
        )

        self.assertEqual(affected_count, 14501)

    def test_assignment_14_rubric_preserved(self):

        item = self.cleaned_mapping[14]

        original = item["original_assignment"]
        cleaned = item["cleaned_assignment"]

        rubric_marker = "RUBRIC: Essay 1"

        self.assertIn(rubric_marker, original)
        self.assertIn(rubric_marker, cleaned)

        original_rubric = original[
            original.index(rubric_marker):
        ]

        cleaned_rubric = cleaned[
            cleaned.index(rubric_marker):
        ]

        self.assertEqual(
            original_rubric,
            cleaned_rubric
        )

    def test_assignment_12_revision_exception(self):

        cleaned = self.cleaned_mapping[12][
            "cleaned_assignment"
        ]

        self.assertIn("Proofread and edit carefully", cleaned)
        self.assertIn("except to correct an error", cleaned)


# ============================================================
# Run all tests
# ============================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
