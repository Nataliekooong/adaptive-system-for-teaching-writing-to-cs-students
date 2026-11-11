# Adaptive Writing Tutor (Team 21)

The full-stack app (React + TypeScript frontend, FastAPI backend) for the adaptive writing tutor described in the SRS.
The SLM is **not** included yet. A mock model sits behind the feedback-service interface, so the rest of the system
runs end to end. You switch to the real model with one environment variable.

## Core idea: every component is a module, so anything can be A/B tested

All features are defined once in [`src/backend/app/modules.py`](src/backend/app/modules.py). Each module has an
`enabled` switch and typed settings. The instructor UI draws its controls straight from that registry, so a new
module shows up everywhere without any frontend work.

The effective configuration for a student on an assignment is resolved in layers (later layers win):

```
system defaults → course → assignment → experiment condition(s) → per-student override
```

| Module | What it controls | SRS |
|---|---|---|
| 💬 On-demand AI feedback | source (SLM / fixed prompts), style policy (bandit / random / fixed), allowed styles, cooldown, cap | S8, B5, MAB3–5, B8 |
| ⚡ Real-time pop-up feedback | triggers (idle N s + sentence end, sentence settled, repeated deletion), context sentences, **presentation (popup / window / highlight)**, frequency limits | S9 |
| 🎭 Feedback presentation | chat panel vs character | S15 |
| 👍 Student rating · 🧑‍🏫 Instructor review | the two reward signals, review sample size ≤ 5 | S11, I9 |
| 🎯 Bandit reward | `combined` / `student_only` / `instructor_only`, weight *a*, **instructor timeout → student-only fallback** | MAB6–7, B7 |
| 🧠 Learner model (BKT) · 📋 Questionnaire | bandit context, initial profile | B3, B10, S2 |
| 🚀 Get Started · 🕘 Version history · 📋 Paste · 📏 Submission rules · 🎓 Grades | workspace features | S5–S7, S10, S12–S14 |

**Experiments** (instructor → course → *A/B experiments*) split students into conditions. Each condition is a set of
module overrides. Students are placed by a balanced, random or manual strategy, either lazily on first access or all
at once. The *Effective config* tab on an assignment shows which layer decided each value for a given student.
Results compare request counts, helpful rate, instructor rating, mean reward, submissions and grades for each
condition. Templates are included for on-demand vs real-time, popup vs window vs highlight, bandit vs random vs fixed,
and chat panel vs character.

### Feedback flows
* **On-demand:** student → snapshot → bandit (Thompson Sampling per BKT context) → SLM → guardrail → panel.
  Student revises, student rates, instructor rates a sampled before/after pair, reward = *a*·student + (1−*a*)·instructor.
  Finalized rewards are folded into the posteriors on a schedule (`BANDIT_UPDATE_SECONDS`), or with *Apply now* in Research data.
* **Real-time:** the browser watches writing-process signals and sends only the last *N* sentences after typing pauses.
  Raw keystrokes are never logged. Only the trigger and the prompt shown are logged.

## Run locally

### Requirements

- **Node.js + npm** for the frontend. Node 22.15.0 and npm 10.9.2 are installed on this Windows machine.
- **Python 3.12 + pip + venv** for the backend (matching the backend Docker image). The ordinary `python`
  command on this Windows machine points to an unusable WindowsApps alias; the commands below include a working
  bundled-runtime alternative.
- **No separate database install, GPU, model download, API key, or `.env` file is needed** for the default demo.
  SQLite is included with Python, and AI feedback uses the built-in mock provider.
- Docker Desktop with Compose is optional for the container setup; it is not required for the native setup.

Run npm commands in `src/frontend`, where `package.json` and the frontend lockfile live, rather than the repo root.
`npm ci` installs all pinned frontend dependencies: React, React DOM, React Router, TypeScript, Vite, the React
Vite plugin, and React type definitions. Backend dependencies are FastAPI, Uvicorn, SQLAlchemy, Pydantic, and
Psycopg; `requirements-dev.txt` also installs pytest and HTTPX for testing. Both package managers install the
required transitive dependencies automatically. The data preprocessing folder has separate requirements that
are not needed to run the web app.

### Windows (PowerShell)

From the repository root, set up the backend once:

```powershell
cd src/backend
python -m venv .venv
# If `python` is the broken WindowsApps alias on this machine, use this instead:
# & "$env:USERPROFILE/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe" -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

If neither Python command is available on another machine, install Python 3.12 with pip and add it to PATH,
then open a new terminal. Virtual environment activation is unnecessary with these explicit executable paths.

Start the backend in that terminal (also use this command on subsequent runs):

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In a second terminal, starting from the repository root:

```powershell
cd src/frontend
npm.cmd ci                     # first setup, or after the lockfile changes
npm.cmd run dev -- --host 127.0.0.1 --strictPort
```

Use `npm.cmd` to avoid PowerShell execution-policy errors from `npm.ps1`. Open **http://localhost:5173**;
Vite proxies `/api` to the backend on port 8000. API documentation is at **http://127.0.0.1:8000/docs**.
Keep both terminals running; press Ctrl+C in each to stop. On subsequent starts, run the backend command above
and `npm.cmd run dev -- --host 127.0.0.1 --strictPort` from their respective folders.

The backend creates `src/backend/writing_tutor.db` and seeds demo accounts on its first start. Use `drlee` for
the instructor or `priya` for a student, with password `password`.

Checks (from their respective folders):

```powershell
# src/frontend
npm.cmd run typecheck
npm.cmd run build
# src/backend
.\.venv\Scripts\python.exe -m pytest -q
```

### macOS / Linux

```bash
# backend
cd src/backend && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --port 8000

# frontend (another terminal)
cd src/frontend && npm ci && npm run dev   # http://localhost:5173
```

SQLite is the zero-setup default. Set `DATABASE_URL=postgresql+psycopg://…` for PostgreSQL, or run
`docker compose up` (Postgres + backend + frontend). Demo data is seeded on the first start: instructor `drlee`
and students `priya`, `marcus`, `alex`, `jordan`, `sam`, `taylor`. Every demo account uses the password `password`
(dev only; McMaster SSO replaces this login).

Tests: `cd src/backend && .venv/bin/python -m pytest`

## Plugging in the SLM later
Implement the JSON contract of `HTTPSLMProvider` in
[`feedback_service.py`](src/backend/app/services/feedback_service.py), then set `SLM_PROVIDER=http SLM_URL=…`.
The response must be `{content: {summary, items:[{rubric_area, comment, suggestion, quote}]}, model_version, prompt_template}`.
`MOCK_SLM_FAIL=1` simulates an outage, so you can see the "draft preserved" error path.

## Layout
```
src/backend/app/modules.py            module registry + layered resolution
src/backend/app/services/             config_resolver, pipeline, bandit, bkt, feedback_service, events
src/backend/app/routers/              student, instructor, common (auth, /api/modules)
src/frontend/src/components/ModuleConfigEditor.tsx   schema-driven on/off + settings editor (any layer)
src/frontend/src/pages/student/       workspace, real-time triggers, feedback presentations
src/frontend/src/pages/instructor/    course, assignment, experiment, review, research pages
```
