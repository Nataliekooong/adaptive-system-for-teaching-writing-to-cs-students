# Pre-Fine-Tuning Dataset Cleaning

**Jira Ticket:** SAM1-26

## 1. Overview

This directory contains the dataset cleaning pipeline developed
for SLM fine-tuning in the Adaptive System for Teaching Writing
to CS Students project.

The objective is to remove irrelevant administrative information
from the training dataset while preserving meaningful writing
instructions, academic requirements, and student feedback.

## 2. Dataset Structure

The original dataset contains 30,530 training records and
36 unique assignments.

Each training record contains the following fields:

- `id`
- `config_hash`
- `assignment`
- `draft`
- `feedback`

Only the `assignment` field is modified during the cleaning
process. All other fields remain unchanged.

## 3. File Descriptions

| File | Description |
|---|---|
| `pre_cleaning.py` | Initial dataset inspection and administrative content analysis. |
| `clean_assignments.py` | Rule-based assignment cleaning algorithm (Version 4). |
| `compare_cleaning.py` | Optional development utility for comparing automated cleaning results with a manually reviewed reference. |
| `review_feedback.py` | Detects potentially irrelevant administrative content in feedback records for contextual review. |
| `test_clean_assignments.py` | Contains 35 automated unit and dataset integration tests. |
| `apply_cleaning.py` | Applies the cleaned assignment mapping to the complete dataset and validates data integrity. |
| `cleaning_report.json` | Final cleaning statistics and dataset integrity validation results. |
| `README.md` | Documentation of the cleaning methodology, workflow, and results. |

## 4. Cleaning Methodology

The cleaning pipeline uses regular expressions and
context-specific replacement rules to remove irrelevant
administrative information, including:

- Assignment due dates and deadlines
- File naming requirements
- File submission formats
- Workshop schedules
- Platform-specific submission instructions
- Login instructions
- Generic encouragement

The following academic content is preserved:

- Writing objectives and instructions
- Word counts and page limits
- Assessment rubrics
- Citation and formatting requirements
- Revision requirements
- Meaningful writing guidance

Since the dataset contains only 36 unique assignments,
each unique assignment is cleaned before the resulting
mapping is applied to all corresponding training records.

## 5. Feedback Review

All 30,530 feedback records were scanned for potentially
irrelevant administrative content.

A total of 127 records were flagged for contextual review.
The flagged keywords were associated with meaningful writing
feedback rather than irrelevant administrative instructions.

Therefore, the original feedback was preserved to avoid
removing valuable training information.

## 6. Requirements

- Python 3.12 (development environment)
- Python standard library only
- No additional packages required

The scripts use the following local data directory:

`~/Desktop/DeepSeek_Dataset/`

Required input files:

- `draft_feedback_b1.jsonl`
- `unique_assignments.json`

The unique assignment file contains assignment IDs,
original assignment texts, and occurrence counts.

## 7. Execution Workflow

Run the following commands from the repository root.

### Step 1: Initial Dataset Inspection

```powershell
python "./pre-preocessing data/source/dataset_cleaning/pre_cleaning.py"
```

### Step 2: Clean Unique Assignments

```powershell
python "./pre-preocessing data/source/dataset_cleaning/clean_assignments.py"
```

Output:

- `unique_assignments_auto_cleaned.json`

### Step 3: Review Feedback

```powershell
python "./pre-preocessing data/source/dataset_cleaning/review_feedback.py"
```

Output:

- `feedback_review.json`

This step identifies candidates for contextual review
without automatically modifying feedback.

### Step 4: Run Automated Tests

```powershell
python "./pre-preocessing data/source/dataset_cleaning/test_clean_assignments.py"
```

### Step 5: Apply Cleaning to the Complete Dataset

```powershell
python "./pre-preocessing data/source/dataset_cleaning/apply_cleaning.py"
```

Outputs:

- `draft_feedback_b1_cleaned.jsonl`
- `cleaning_report.json`

The cleaned dataset is validated before being finalized.
The original dataset is not modified.

Existing output files must be backed up or removed before
rerunning the final dataset cleaning script.

## 8. Cleaning Results

| Metric | Result |
|---|---:|
| Total training records | 30,530 |
| Unique assignments | 36 |
| Modified assignments | 19 |
| Unmodified assignments | 17 |
| Modified training records | 14,501 |
| Unmodified training records | 16,029 |
| Affected record coverage | 47.50% |
| Original assignment characters | 36,599,596 |
| Cleaned assignment characters | 31,100,579 |
| Net assignment characters removed | 5,499,017 |
| Assignment character reduction | 15.02% |
| Original dataset size | 127.99 MB |
| Cleaned dataset size | 122.68 MB |
| Deleted training records | 0 |
| Automated tests passed | 35/35 |
| Dataset integrity validation | PASS |

## 9. Testing and Validation

All 35 automated tests passed, covering:

- Administrative content removal
- Academic content preservation
- Invalid input handling
- Empty assignment prevention
- Cleaning reproducibility
- Cleaning idempotency
- Assignment mapping integrity

Additionally, all 30,530 records passed full dataset
integrity validation.

The following fields and properties were preserved:

- Record count
- Dataset schema
- Record IDs
- Configuration hashes
- Original student drafts
- Original feedback
- All other non-assignment fields

## 10. Limitations

- The cleaning rules are tailored to the current dataset.
- Keyword-based detection may produce false positives or
  miss some administrative content.
- Data integrity validation does not guarantee perfect
  semantic cleaning.
- The impact of dataset cleaning on SLM fine-tuning
  performance has not yet been experimentally evaluated.

## 11. Dataset Availability

The cleaned training dataset is shared separately through
Jira ticket SAM1-26.

The original and cleaned training datasets are not committed
to GitHub due to their file sizes and potential data
privacy considerations.

The final cleaning statistics are available in
`cleaning_report.json`.