# SRS traceability — Team 21, Adaptive Writing Tutor (SRS v0.1 baseline)

Maps every functional requirement in the SRS to its implementation. Update the **Status** and **Where** columns in
the same change that implements a requirement.

Priority: **P0** must have (MVP) · **P1** high · **P2** medium · **P3** stretch.
Status: ✅ done · 🟡 partial · ⬜ not started. "Module" is the `app/modules.py` key that switches the feature.

## 7.1 Student view

| ID | Requirement (short) | Pri | Status | Module | Where |
|---|---|---|---|---|---|
| S1 | Log in with McMaster account via SSO | P0 | 🟡 dev password login; SSO method not confirmed (§14) | — | `app/auth.py`, `routers/common.py` |
| S2 | First-login questionnaire → initial learner profile | P1 | ✅ | `questionnaire` | `routers/student.py` `/questionnaire`, `pages/student/Questionnaire.tsx` |
| S3 | Assigned tasks in a collapsible sidebar with prompt, instructions, genre guidance, due date | P0 | ✅ | — | `pages/student/StudentLayout.tsx`, `Workspace.tsx` |
| S4 | Write and edit a draft in an assignment workspace | P0 | ✅ | — | `Workspace.tsx` |
| S5 | Snapshots around feedback rounds and paste events | P1 | ✅ | `version_history` | `pipeline.snapshot`, `DraftVersion.kind` |
| S6 | Undo / redo | P0 | ✅ | — | `Workspace.tsx` (own history stack, ⌘Z / ⇧⌘Z) |
| S7 | Restore most recently saved draft after confirmation | P0 | ✅ | `version_history` | `/restore` |
| S8 | Request AI feedback; past feedback in side panel; never unrequested | P0 | ✅ (mock SLM) | `on_demand_feedback` | `pipeline.on_demand`, `FeedbackViews.tsx` |
| S9 | Instructor-approved prompt on writing-process signals, after typing pauses, dismissible, frequency-limited | P1 | ✅ | `realtime_feedback` | `useRealtime.ts`, `pipeline.realtime` |
| S10 | “Get Started” outline / guiding questions, never a completed response | P1 | ✅ | `get_started` | `/get-started`, `Assignment.get_started_content` |
| S11 | Optionally rate feedback helpful / unhelpful | P0 | ✅ | `student_rating` | `/feedback/{id}/rating` |
| S12 | Check minimum word / paragraph count before submission | P2 | ✅ | `submission_rules` | `/submit` |
| S13 | View grade and comments after release | P1 | ✅ | `grades` | `submission_out(include_grade)` |
| S14 | Detect paste; explain if disabled, otherwise log with surrounding versions | P2 | ✅ | `paste_control` | `/paste` |
| S15 | Presentation per study group (chat panel / character) | P2 | ✅ | `feedback_presentation` | `FeedbackViews.tsx` |

## 7.2 Instructor view

| ID | Requirement (short) | Pri | Status | Module | Where |
|---|---|---|---|---|---|
| I1 | Log in with an instructor account | P0 | 🟡 dev login, no SSO | — | `auth.require_instructor` |
| I2 | Create / edit assignments | P0 | ✅ | — | `AssignmentPage.tsx` Overview |
| I3 | Assign students to an assignment | P0 | ✅ | — | `PUT /assignments/{id}/students` |
| I4 | Select feedback priority areas from a rubric | P0 | ✅ | — | `Assignment.rubric_areas` |
| I5 | Select the type of feedback each student receives | P1 | ✅ | any (per-student override) | `AssignmentStudent.override_config` |
| I6 | Student macID, assignments and grades | P1 | ✅ | — | `StudentProfilePage.tsx` |
| I7 | A student's common struggle areas by rubric area | P2 | ✅ | — | `/students/{sid}`, `/struggles` |
| I8 | See students' work and feedback; enter grades | P1 | ✅ | — | `StudentWorkPage.tsx` |
| I9 | Random sample of ≤ 5 revisions with feedback + before/after; rate helpfulness | P0 | ✅ | `instructor_review` | `/review-queue`, `pipeline.revision_after` |
| I10 | Enable / disable / edit AI feedback styles | P1 | ✅ | — | `FeedbackStyle`, Library tab |
| I11 | Release grades; unreleased stay hidden | P0 | ✅ | `grades` | `/release` |
| I12 | Configure paste, min word count, prompt triggers, Get Started content | P1 | ✅ | `paste_control`, `submission_rules`, `realtime_feedback`, `get_started` | `ModuleConfigEditor.tsx` |

## 7.3 Backend & adaptive logic

| ID | Requirement (short) | Pri | Status | Module | Where |
|---|---|---|---|---|---|
| B1 | Validate McMaster login, manage sessions, role-based access | P0 | 🟡 sessions + RBAC; no SSO, no session expiry | — | `auth.py` |
| B2 | Manage assignments, enrollments, rubrics, feedback settings | P0 | ✅ | — | `routers/instructor.py` |
| B3 | Questionnaire stored; writing score seeded from answers | P1 | ✅ | `questionnaire` | `bkt.initial_mastery` |
| B4 | Manual saves, autosaves, version history, confirmed restore, submit | P0 | ✅ | `version_history` | `routers/student.py` |
| B5 | Feedback request: personal context → allowed bandit style → SLM → validate | P0 | ✅ (mock SLM) | `on_demand_feedback` | `pipeline.on_demand` |
| B6 | Manage pre-written prompts selected by instructor rules; Get Started | P1 | ✅ | `realtime_feedback.source`, `on_demand_feedback.source` | `FixedPrompt`, `_fixed_prompt_result` |
| B7 | Store feedback, decisions, ratings, revision differences | P1 | 🟡 stored; feeding them back to SLM training is ML work (M5) | `reward` | `BanditDecision`, `FeedbackItem` |
| B8 | Block abuse such as rapid repeated SLM requests; grades released only when authorized | P1 | 🟡 cooldown + per-assignment cap; no account blocking | `on_demand_feedback.cooldown_seconds`, `max_requests` | `pipeline.on_demand` |
| B9 | Record where students asked for feedback and where they revised; show instructors; guardrail outcome logged | P1 | 🟡 snapshots + guardrail status; no character-position tracking | — | `DraftVersion`, `FeedbackItem.guardrail_status` |
| B10 | Update learner marks after each round (BKT) | P1 | ✅ | `learner_model` | `services/bkt.py` |

## 7.4 SLM pipeline (ML team, `src/ml/`)

| ID | Requirement (short) | Pri | Status |
|---|---|---|---|
| M1 | Prepare SEFORA: pseudonymization check, 80/10/10 split by essay ID, training pairs | P0 | ⬜ |
| M2 | Map SEFORA rubric items to priority areas; LoRA fine-tune | P0 | ⬜ |
| M3 | Compare fine-tuned vs base (F1 on SEFORA test, gold set) | P0 | ⬜ |
| M4 | Serve SLM on department servers within latency target | P0 | 🟡 backend side ready: `HTTPSLMProvider`, `SLM_PROVIDER=http` |
| M5 | Repeat M1–M3 on the January dataset after removing personal info | P1 | ⬜ |

## 7.5 Bandit selector

| ID | Requirement (short) | Pri | Status | Module | Where |
|---|---|---|---|---|---|
| MAB1 | Small set of feedback styles | P0 | ✅ 4 seeded | — | `seed.STYLES` |
| MAB2 | Student context: weak rubric items, rounds, assignment type | P0 | 🟡 all logged in `context`; arm key uses BKT level only | `learner_model` | `pipeline.on_demand` |
| MAB3 | Contextual bandit picks a style per request | P0 | ✅ Thompson Sampling | `on_demand_feedback.style_policy` | `bandit.select_style` |
| MAB4 | Pass chosen style to the SLM | P0 | ✅ | — | `FeedbackRequest.style`, `style_template` |
| MAB5 | Fallback default style; instructors can disable or fix styles | P0 | ✅ | `fixed_style`, `allowed_styles` | `bandit.select_style` |
| MAB6 | Score = a × student + (1 − a) × instructor (≤ 5 sampled) | P0 | ✅ + timeout fallback | `reward` | `bandit.refresh_reward` |
| MAB7 | Update bandit from the log on a schedule | P1 | ✅ | — | `main._bandit_scheduler`, `bandit.apply_finalized` |
| MAB8 | Offline check: bandit beats random and fixed styles | P1 | ⬜ (A/B template exists; offline eval script missing) | `style_policy` | — |
| MAB9 | After REB, learn from student data, compare conditions | P3 | ⬜ | — | experiment results page is the starting point |

## Non-functional requirements (SRS §9)

| Category | Target | Status |
|---|---|---|
| Usability | Start writing ≤ 10 min after login; SUS ≥ 70; AI never produces a finished draft | 🟡 authorship guard in place; SUS not measured |
| Performance | Feedback p95 ≤ 15 s; save / undo / revert ≤ 500 ms; ~100 concurrent students | ⬜ not load-tested |
| Security & privacy | RBAC; students can't see others' work; HTTPS + encryption at rest; hashed passwords; only consenting students in exports | 🟡 RBAC, PBKDF2 hashes, consent filter on export; HTTPS / at-rest encryption are deployment work |
| Reliability | Autosave loses ≤ 30 s; AI outage shows clear error without losing draft; model version + template recorded; backend coverage ≥ 80 %; daily backups | 🟡 autosave ≤ 30 s, outage handling, versions recorded; coverage not measured; backups are deployment work |
| Data (§8.2) | Events timestamped + pseudonymous + condition-linked; raw keystrokes never logged; append-only except consent withdrawal (R1) | 🟡 consent-withdrawal deletion not implemented |

## Out of scope (SRS §6) — do not build

Automated grading, plagiarism detection, Avenue integration, writing answers for students.
