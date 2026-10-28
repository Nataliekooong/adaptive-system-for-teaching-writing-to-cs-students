# CLAUDE.md — Adaptive Writing Tutor (COMPSCI 4ZP6, Team 21)

Shared guide for Claude Code and for teammates working with it. Read [README.md](README.md) for the product overview.
The source of truth for requirements is the team's SRS. Requirement IDs (S1–S15, I1–I12, B1–B10, M1–M5, MAB1–MAB9)
are used in code comments; keep using them.

## What the SRS asks for (read before planning work)

- **Requirement status:** [docs/srs-traceability.md](docs/srs-traceability.md) maps every S/I/B/M/MAB requirement
  and NFR to its status and code. Work P0 gaps before P1, and P1 before P2. Update the table in the same change.
- **Architecture constraint (§6):** React views → backend API → feedback selector + feedback-service interface →
  self-hosted SLM, with all data in PostgreSQL. Every model call goes through one interface so model versions can
  change without touching the frontend.
- **Out of scope (§6):** automated grading, plagiarism detection, Avenue integration, writing answers for students.
  Push back if asked to build these.
- **Platform (§6):** desktop browsers (Chrome, Firefox, Safari, Edge). Mobile isn't required.
- **Privacy (§6, §8.2):** FIPPA and PIPEDA principles apply. Student writing stays on university-controlled servers,
  so don't add third-party APIs or analytics that receive student text. No real student data before MREB approval.
  Only consenting students appear in exports or training data. Records are removed when a student withdraws consent.
- **Compute (§6):** base model ≤ 8B parameters, quantized for serving, LoRA via PEFT, inference on a single
  ≥ 24 GB GPU with vLLM.
- **NFR targets (§9):** feedback p95 ≤ 15 s (model p95 ≤ 10 s at 20 concurrent requests); save, undo and revert
  ≤ 500 ms; about 100 concurrent students; autosave loses ≤ 30 s of work; backend test coverage ≥ 80 %;
  SUS ≥ 70; a new student starts writing within 10 minutes.
- **Metrics (§8.2):** the bandit should beat random by +0.10 feedback score and match or beat the best fixed style.
  Expert rating ≥ 4.0/5. Valid JSON ≥ 99 %. Answer leakage ≤ 2 % and false blocks ≤ 5 %. BKT AUROC ≥ 0.70.
- **Milestones:** proof of concept by **November 23, 2026** (SRS §15 lists the demo features); Expo demo April 2027.

## Team roles (SRS §1) — who to ask

| Member | Role | Area |
|---|---|---|
| Mike Wang | Backend lead | `src/backend` routers, auth, persistence |
| Chenhe Wu | Team coordinator / architect | cross-cutting design, meeting minutes in `/meetings` |
| Yan Bao | ML lead: fine-tuning | M1, M2, M5 (`src/ml`) |
| Yuexi Sun | ML engineer: evaluation & safety | M3, guardrail and red-team set |
| Wenhan Dong | Adaptive learning & ML engineer | bandit (MAB*), BKT (B10) |
| Qinquan Wang | Frontend lead: student UX | `src/frontend` student pages |
| Yitian Kong | Full-stack & QA lead | integration, tests, CI |

## Stack and layout

| Path | What | Owner area |
|---|---|---|
| `src/backend/app/` | FastAPI + SQLAlchemy 2 (Python 3.10+) | Backend |
| `src/frontend/src/` | React 18 + TypeScript + Vite, no UI library (Notion-style CSS in `styles.css`) | Frontend |
| `src/ml/` (not yet created) | SLM fine-tuning, evaluation, serving | ML |
| `docker-compose.yml` | Postgres + backend + frontend | Infra |

## Commands

```bash
# backend (from src/backend)
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload --port 8000
.venv/bin/python -m pytest -q

# frontend (from src/frontend)
npm install
npm run dev          # http://localhost:5173, proxies /api → :8000
npm run typecheck    # must pass before any PR
```

Reset demo data: stop the backend, delete `src/backend/writing_tutor.db`, restart (seed runs on an empty DB).
Demo logins: `drlee` (instructor), `priya` `marcus` `alex` `jordan` `sam` `taylor` (students), password `password`.

## Architecture in one paragraph

Every feature is a **module** in `app/modules.py` (an `enabled` flag + typed settings). Config is resolved per
(student, assignment) by `services/config_resolver.py` in layers:
**system → course → assignment → active experiment condition(s) → per-student override** (later wins).
Routers call the resolver and then gate behaviour on `cfg.on("<module>")` / `cfg.get("<module>", "<setting>")`.
Feedback goes through `services/pipeline.py` → `services/bandit.py` (Thompson Sampling, context from
`services/bkt.py`) → `services/feedback_service.py` (the single model interface; `MockSLMProvider` today).
Every research-relevant action is written with `services/events.log_event`. The frontend reads the module schema
from `GET /api/modules` and renders all switches with `components/ModuleConfigEditor.tsx`.

## The modularity rule (most important)

The system exists to run A/B tests, so **every new feature must be a switchable module**:

1. Add a `Module(...)` to `MODULES` in `app/modules.py` (key, label, category, description, `srs_refs`, settings with
   min/max/options, `depends_on` if it needs another module).
2. Gate the backend behaviour on the resolved config — never on a hard-coded flag, env var or role check.
   A disabled module must make its endpoint refuse (403) or no-op, not crash.
3. Gate the frontend UI on the `config` returned by `GET /api/student/assignments/{id}`.
4. The instructor UI picks the module up automatically. Only add a `MODULE_ICONS` entry in
   `components/ModuleConfigEditor.tsx`.
5. Add tests in `src/backend/tests/test_api.py`: on, off, and overridden by an experiment condition.

Do not add per-feature config tables or columns. Overrides live in the JSON `config` / `override_config` columns
and are validated by `modules.validate_overrides`.

## Invariants — do not break these

- **Authorship:** AI output gives guidance and never writes the assignment (NFR usability, S10). Keep the
  direct-answer guard and `validate()` in `feedback_service.py`. Any new provider must go through `validate()`.
- **The draft is saved before any model call.** A model failure returns 503 with a clear message and never touches
  the draft (NFR reliability).
- **Students are blind to conditions.** Student endpoints never return experiment/condition names, style, policy
  or model internals (`feedback_out(..., research=False)`).
- **Research logs are pseudonymous and append-only.** Log `user.pseudonym`, never usernames, names or emails.
  Never log raw keystrokes or free text from the editor (S9, §8.2). `POST /api/student/events` whitelists types and
  drops long strings — keep it that way.
- **Bandit decisions are reproducible.** Every decision stores policy, context, arm, selection probability and a
  snapshot of the reward config. Every feedback item stores `model_version` and `prompt_template`.
- **Submissions are final.** After submit the draft is locked and the backend rejects edits and resubmission.
  Unreleased grades never reach students (I11).
- **Role checks:** instructor routes use `require_instructor` and check course ownership via `_course(...)`;
  students only reach their own assigned work.

## Conventions

- Backend: type hints, Pydantic request models next to their route, SQLAlchemy 2 `Mapped[...]` style.
  Store naive UTC datetimes (`models.now()`); serialize with `serializers.iso()`.
- Frontend: function components + hooks, `api.get/post/...` from `src/api.ts`, data loading via `useLoad`,
  UI primitives from `src/ui.tsx` (`Tag`, `Board`, `Views`, `Props`, `Callout`, `Modal`, `useToast`).
  Keep the Notion look: no new UI libraries, reuse the CSS tokens in `styles.css`.
- Match the surrounding comment density; reference SRS IDs instead of long explanations.
- `npm run typecheck` and `pytest` must both pass before handing work back.

## SLM integration (ML team)

Implement an HTTP service returning
`{content: {summary, items:[{rubric_area, comment, suggestion, quote}]}, model_version, prompt_template}`
and run the backend with `SLM_PROVIDER=http SLM_URL=...`. Do not call the model from anywhere except
`feedback_service.get_slm_provider()`. `MOCK_SLM_FAIL=1` simulates an outage.

## Team workflow (SRS §12)

- Branches: `main` (release), `develop` (integration), `feature/<issue>-<name>`.
- PRs: one approving review; **two** for auth, data export, and the feedback interface. CI green, linked issue,
  squash merge.
- Claude: do not commit, push or open PRs unless the person you are working with asks for it.
- No real student data in the repo or in tests before MREB approval. Seed and fixture data only.

## Project subagents

Defined in `.claude/agents/`:

- `module-builder`: adds a new switchable module end to end, backend plus frontend plus tests.
- `invariant-reviewer`: read-only review of a diff against the invariants above.
- `slm-integrator`: work on the feedback-service interface and the ML handoff.
- `srs-tracer`: checks code against the SRS and updates `docs/srs-traceability.md`.
