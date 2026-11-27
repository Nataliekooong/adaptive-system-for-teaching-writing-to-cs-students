import json
import re
from pathlib import Path
from collections import Counter

# ============================================================
# File paths
# ============================================================

DATA_DIR = Path.home() / "Desktop" / "DeepSeek_Dataset"

INPUT_PATH = DATA_DIR / "unique_assignments.json"
OUTPUT_PATH = DATA_DIR / "unique_assignments_auto_cleaned.json"


# ============================================================
# 1. General administrative text cleaning rules
# ============================================================

CLEANING_RULES = {
    "answer_space": [
        r"Write your (?:response|essay) in the space provided\."
    ],

    "due_dates": [
        r"(?m)^[ \t]*The basics: due by[^\n]+",
    ],

    "filenames": [
        r"(?m)^[ \t]*Remember to title your file distinctively[^\n]+",
        r"Use your complete name in the\s+filename:[^\n]+",
    ],

    "submission_formats": [
        r"Submit a \.doc or \.doc-compatible file\.",
        r"Submit a \.doc file\.",
        r"(?m)^[ \t]*Doc or \.doc-compatible format, please\.",
    ],

    "general_encouragement": [
        r"(?m)^[ \t]*Good luck! Have fun![ \t]*$",
        r"(?m)^[ \t]*Happy writing![ \t]*$",
    ],

    "login_instructions": [
        r"Please go to our Wikipedia course site and log in using your account information\.",
    ],

    "office_hours": [
        r" And you are always welcome to set up an appointment with me or come to my office hours\.",
    ],

    "document_submission": [
        (
            r"After drafting your Wikipedia assignment"
            r"(?: in your sandbox)?,\s+"
            r"copy and paste your rough draft into a word document "
            r"and submit the word document(?:/pdf file)? here\."
        ),
    ],
}


# ============================================================
# 2. Context-specific replacement rules
#
# Remove administrative information while preserving
# meaningful academic and writing requirements.
# ============================================================

REPLACEMENT_RULES = {

    "due_date_replacements": [
        (
            r"Before our Wednesday's class, please submit a rough draft",
            "Write a rough draft"
        ),
    ],

    "submission_replacements": [
        (
            r"Please submit a final draft",
            "Write a final draft"
        ),
    ],

    "filename_replacements": [
        (
            r", make sure your name is on it, and make the file name distinctive \(not “My second story”\)",
            ""
        ),
        (
            r", and please call the file something like GoodStudentFirstShortStoryFirstDraft",
            ""
        ),
        (
            r", send a \.doc or \.doc-compatible file, and make sure your file name includes your full name \([^\n]*?\)",
            ""
        ),
        (
            r"Please put your ENTIRE name in the file name, e\.g\.: "
            r"JaneDoeSeniorSeminar2Submission\.doc\.\s*"
            r"\(This helps your classmates[^)]*\)\.",
            ""
        ),
        (
            r"It should have a title, and your name should be on the first page\.",
            "It should have a title."
        ),
    ],

    "spelling_grammar_replacements": [
        (
            r'Remember to Spell & Grammar check your doc '
            r'\(Spelling & Grammar is under the "Review"\s+'
            r'tab on your Word app[^)]*\),\s*'
            r'save it, then upload it to Canvas\s+'
            r'as an attachment\.',
            "Remember to check spelling and grammar."
        ),
    ],

    "file_format_replacements": [
        (
            r"your paper will be a \.doc or \.doc-compatible file,\s*between",
            "your paper will be between"
        ),
    ],

    "canvas_onedrive_replacements": [
        (
            r"Please submit your Video 1 \(mp4\), Video 2 \(mp4\), "
            r"and a digital story statement in this OneDrive folder\.",
            "Create Video 1, Video 2, and a digital story statement."
        ),
        (
            r"In this Canvas submission folder, individually, "
            r"submit a storytelling statement "
            r"\(400–600 words, doc or docx\)",
            "Individually, write a storytelling statement (400–600 words)"
        ),
    ],

    "workshop_replacements": [
        (
            r"Just as before, if you sign up for an earlier workshop,"
            r"\s+you will have less time to revise"
            r"\s+your story before it goes in front of the class,"
            r"\s+whereas those workshopping later will"
            r"\s+have more time before "
            r"\(but, obviously, less time after – and everyone must fully and"
            r"\s+meaningfully revise their stories for the final portfolio!\)\.",
            "Everyone must fully and meaningfully revise their stories "
            "for the final portfolio!"
        ),
    ],

    "final_refinement": [
        # Remove the course timeline, preserving the final-paper requirement.
        (
            r"I’m giving you this prompt over three months "
            r"before the paper is due so that you can think"
            r"\s+about your topic and what you want to say "
            r"over the rest of the semester\.[ \t]*",
            ""
        ),
        # Preserve the optional revision requirement; remove workshop logistics.
        (
            r"It will be returned \(I hope!\) before the first "
            r"round of workshops begin\.[^\n]*?"
            r"enough time for them to read and respond\.",
            "You are not required to revise your story "
            "before it is workshopped by the class."
        ),
        # Remove the semester countdown and generic praise, but retain
        # the 50-page requirement and the useful writing-process advice.
        (
            r"(?m)^Finally, I hope that you feel some sense of accomplishment "
            r"and pride as you approach the end of the semester\."
            r"[^\n]*?That’s awesome\. I’m proud of you\. Here we go! ☺[ \t]*$",
            "The final portfolio requires 50 pages. "
            "Work on your writing a little every day."
        ),
        # Remove the stray space introduced by filename removal.
        (
            r"(?m)^[ \t]+All the guidelines from the first "
            r"submission remain in place\.",
            "All the guidelines from the first submission remain in place."
        ),
    ],

    # Dataset-specific quality review: exact contextual replacements.
    "v4_quality_refinement": [
        (re.escape('BUT please remember that no one is expecting perfection or even something amazing. Just do your best! It’s a draft! You get to keep working on it.'), 'This is a draft that can be further revised.'),
        (re.escape('There are probably other options that are unique to your work, so feel free to discuss this with me. I do trust you to figure this out, but if you feel at sea, ask for help!'), 'Other options may be appropriate depending on your work.'),
        (re.escape('For those of you who are unfamiliar with my response style, I’d invite other students in the class to share what it’s like to get a story back with my comments… (and I hope everyone finds it liberating to know that there is NO way to get a story draft back with “Looks good, A+” on it. It has never happened!)'), ''),
        (re.escape('Remember that no one is expecting perfection or even something amazing. Just do your best! It’s a draft! If it’s terrible than you’ve given yourself lots of room for improvement! We’ll work on it! It’ll be ok!'), 'This is a draft that can be further revised.'),
        (re.escape('Finally, one more reminder that you will make life a lot easier on yourself, especially if you’re starting your draft a couple of hours before it’s due (which I do not recommend, for the record), if you write what you know.'), 'Write what you know.'),
        (re.escape('On that note, a brief reminder that you will not be able to revise this piece before it goes in front of the class. I’m very sorry, but no exceptions can be made on this policy unless I’ve made an error of some kind on your story. So you’ll need to proofread and edit carefully (again, all the more reason to get started ASAP). I will send feedback as soon as I have it, but the piece cannot be revised before it goes to the class.'), 'Proofread and edit carefully. Revision before peer review is not permitted, except to correct an error by the instructor.'),
        (re.escape('I was so\nimpressed by the revisions I saw on your work from your first drafts to the drafts you\nturned in for the class to read. You made something better before, and you can do so\nagain.'), ''),
        (re.escape("It’s natural, even correct, to feel like you don’t quite know what you’re doing on this assignment\n    or that you need to learn a lot more about writing before you start.\n    I understand. There is much more to learn and discuss.\n    But you have to start somewhere, and you already do know more than you think about how stories work.\n    So don't panic. Just try.\n    It’s just a draft, and as Lamott has been telling us all month, drafts are just something to start from.\n    Resolve yourself to the idea that you will be writing more than one draft,\n    and that there is no way to get it “perfect” on the first draft.\n    But I bet you’ll write something that will be worth keeping, even if it’s only a sentence or two.\n    This is the way all writers work, by the way.\n    You are not wrong, or stupid, or untalented.\n    Writing is hard. Just begin."), 'Writing involves multiple drafts and revisions.'),
        (re.escape('Remember, the first draft goes to me,\n    I give you feedback and send it back to you,\n    and then you can revise it if you want to before it goes to the class for workshopping.\n    You are not required to revise before it goes in front of the class.'), 'Revision before peer review is optional.'),
        (re.escape('Remember, bird by bird.'), ''),
        (re.escape(' (see the resources on our Canvas site)'), ''),
    ],

}


# ============================================================
# 3. Administrative paragraph removal
#
# Only remove paragraphs whose administrative purpose
# has been identified during dataset inspection.
# ============================================================

PARAGRAPH_RULES = {

    "workshop_schedules": [
        "It will be returned before the first round of workshops",
    ],

    "deadline_paragraphs": [
        "One final note: If you miss the deadlines involved",
        "I’ve given you a deliberately tight deadline",
        "Due date is midnight, Friday, March 28th",
    ],

    "meeting_arrangements": [
        "As always, if you have any questions, please ask or set up a time",
    ],

    "encouragement_paragraphs": [
        "I thought that the vast majority of the stories turned in for your first assignment",
        "It's been a good semester, and you’ve learned a lot about writing fiction",
    ],
}


# ============================================================
# 4. Cleaning function
# ============================================================

def clean_assignment(text):
    """
    Remove irrelevant administrative text from an assignment
    while preserving academic requirements and writing criteria.

    Returns:
        cleaned_text: Cleaned assignment text.
        changes: Number of modifications by cleaning category.
    """

    if not isinstance(text, str):
        raise TypeError("Assignment must be a string.")

    original_text = text
    changes = Counter()

    # Step 1: Remove standalone administrative instructions
    for category, patterns in CLEANING_RULES.items():

        for pattern in patterns:

            text, count = re.subn(
                pattern,
                "",
                text,
                flags=re.IGNORECASE
            )

            if count:
                changes[category] += count

    # Step 2: Apply context-specific replacements
    for category, rules in REPLACEMENT_RULES.items():

        for pattern, replacement in rules:

            text, count = re.subn(
                pattern,
                replacement,
                text,
                flags=re.IGNORECASE
            )

            if count:
                changes[category] += count

    # Step 3: Remove identified administrative paragraphs
    paragraphs = re.split(r"\n[ \t]*\n", text)
    kept_paragraphs = []
    removed_paragraphs = 0

    for paragraph in paragraphs:

        normalized = paragraph.strip().casefold()
        matched_category = None

        for category, prefixes in PARAGRAPH_RULES.items():

            if any(
                normalized.startswith(prefix.casefold())
                for prefix in prefixes
            ):
                matched_category = category
                break

        if matched_category is not None:

            changes[matched_category] += 1
            removed_paragraphs += 1

        else:

            kept_paragraphs.append(paragraph)

    if removed_paragraphs:

        text = "\n\n".join(kept_paragraphs)

    # Step 4: Normalize whitespace only when cleaning occurred
    if changes:

        text = re.sub(r"[ \t]+\n", "\n", text)

        text = re.sub(
            r"\n(?:[ \t]*\n){2,}",
            "\n\n",
            text
        )

        text = text.strip()

    # Step 5: Prevent accidental removal of the entire assignment
    if original_text.strip() and not text.strip():

        raise ValueError(
            "Cleaning would produce an empty assignment."
        )

    return text, dict(changes)


# ============================================================
# 5. Process all unique assignments
# ============================================================

def main():

    if not INPUT_PATH.exists():

        raise FileNotFoundError(
            f"Input file not found: {INPUT_PATH}"
        )

    # Load unique assignments
    with INPUT_PATH.open("r", encoding="utf-8") as f:

        assignments = json.load(f)

    modified_assignments = 0
    affected_records = 0

    total_changes = Counter()
    records_by_category = Counter()

    print("Assignment Cleaning - Version 4")
    print("=" * 50)

    # Clean each unique assignment
    for item in assignments:

        original = item["original_assignment"]

        cleaned, changes = clean_assignment(original)

        item["cleaned_assignment"] = cleaned
        item["cleaning_changes"] = changes

        if original != cleaned:

            modified_assignments += 1
            affected_records += item["occurrences"]

            total_changes.update(changes)

            for category in changes:

                records_by_category[category] += item["occurrences"]

            print(f"\nAssignment {item['assignment_id']}")
            print(f"Affected records: {item['occurrences']}")
            print(f"Cleaning changes: {changes}")

    # Save cleaning results
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:

        json.dump(
            assignments,
            f,
            ensure_ascii=False,
            indent=4
        )

    total_records = sum(
        item["occurrences"] for item in assignments
    )

    unmodified_assignments = (
        len(assignments) - modified_assignments
    )

    coverage = (
        affected_records / total_records * 100
        if total_records else 0
    )

    # ========================================================
    # 6. Print cleaning summary
    # ========================================================

    print("\nAssignment Cleaning Report")
    print("=" * 50)

    print(f"Total unique assignments: {len(assignments)}")
    print(f"Total training records: {total_records}")
    print(f"Modified assignments: {modified_assignments}")
    print(f"Unmodified assignments: {unmodified_assignments}")
    print(f"Affected training records: {affected_records}")
    print(f"Affected record coverage: {coverage:.2f}%")

    print("\nCleaning operations by category")
    print("-" * 50)

    for category, count in sorted(total_changes.items()):

        print(f"{category}: {count}")

    print("\nAffected records by category")
    print("-" * 50)

    for category, count in sorted(records_by_category.items()):

        print(f"{category}: {count}")

    print("\nOutput file:")
    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()
