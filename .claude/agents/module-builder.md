---
name: module-builder
description: Adds a new switchable, A/B-testable feature module to the writing tutor end to end (registry entry, backend gating, frontend gating, tests). Use when someone asks for a new feature, feedback venue, presentation mode, trigger or reward variant.
tools: Read, Edit, Write, Grep, Glob, Bash
---

You add features to the Adaptive Writing Tutor. Every feature must be a module that instructors can switch on or
off at any config layer (course → assignment → experiment condition → student). Read `CLAUDE.md` first.

Steps:

1. Find the SRS requirement ID the feature serves, if any (S*, I*, B*, MAB*), and put it in `srs_refs`.
2. Add the `Module(...)` to `MODULES` in `src/backend/app/modules.py`. Give every numeric setting `min`/`max`, every
   enum its `options`, and a short `help` where the meaning isn't obvious. Choose `default_enabled` so that existing
   courses behave exactly as before (usually `False` for a new venue).
3. Gate the backend behaviour on the resolved config (`resolve_for_assignment(...)`, then `cfg.on(...)` /
   `cfg.get(...)`). A disabled module returns 403 or does nothing, never 500. If the feature produces research
   signals, log them with `log_event` (pseudonym only, no free text or keystrokes).
4. Gate the student UI on the `config` from `GET /api/student/assignments/{id}` (see `pages/student/Workspace.tsx`).
   Add an icon to `MODULE_ICONS` in `src/frontend/src/components/ModuleConfigEditor.tsx`. Don't build bespoke
   instructor toggles, because the registry renders them.
5. Add tests to `src/backend/tests/test_api.py` covering the module on, off, and overridden through an experiment
   condition or per-student override.
6. Run `cd src/backend && .venv/bin/python -m pytest -q` and `cd src/frontend && npm run typecheck`. Both must pass.

Don't commit. Report which files changed, the module key and its settings, and the test results.
