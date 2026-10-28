"""Module registry: the single source of truth for every switchable component.

Every feature the system offers is a *module* with an `enabled` flag and typed settings.
Configuration is resolved by layering partial overrides on top of these defaults:

    system defaults → course → assignment → experiment condition(s) → per-student override

The frontend renders its configuration UI straight from `registry_schema()`, so adding a
module here is all it takes to make it toggleable and A/B-testable everywhere.
"""
from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Setting:
    key: str
    type: str  # bool | int | float | enum | multi_enum | text
    label: str
    default: Any
    help: str = ""
    options: list[str] | None = None
    options_source: str | None = None  # "styles" → options come from the FeedbackStyle table
    min: float | None = None
    max: float | None = None


@dataclass
class Module:
    key: str
    label: str
    category: str
    description: str
    default_enabled: bool
    srs_refs: list[str] = field(default_factory=list)
    settings: list[Setting] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)


MODULES: list[Module] = [
    Module(
        key="on_demand_feedback",
        label="On-demand AI feedback",
        category="Feedback venues",
        description="Student clicks “Request Feedback” → MAB picks a style → SLM → feedback panel. "
        "Student revises, ratings flow back as reward.",
        default_enabled=True,
        srs_refs=["S8", "B5", "MAB3", "MAB4"],
        settings=[
            Setting("source", "enum", "Feedback source", "slm", options=["slm", "fixed_prompts"],
                    help="slm = model-generated; fixed_prompts = instructor-approved prompt library only."),
            Setting("style_policy", "enum", "Style selection policy", "bandit",
                    options=["bandit", "random", "fixed"],
                    help="bandit = Thompson Sampling; random / fixed are the comparison baselines (MAB8)."),
            Setting("fixed_style", "enum", "Fixed / fallback style", "direct", options_source="styles",
                    help="Used when policy is fixed, or as the fallback when the bandit is unavailable (MAB5)."),
            Setting("allowed_styles", "multi_enum", "Allowed styles", [], options_source="styles",
                    help="Empty = all enabled styles."),
            Setting("cooldown_seconds", "int", "Cooldown between requests (s)", 30, min=0, max=3600,
                    help="Abuse protection (B8)."),
            Setting("max_requests", "int", "Max requests per assignment", 20, min=1, max=500),
        ],
    ),
    Module(
        key="realtime_feedback",
        label="Real-time pop-up feedback",
        category="Feedback venues",
        description="Watches writing-process signals (idle after a finished sentence, repeated deletion) "
        "and sends the latest sentence(s) for a short pop-up. Raw keystrokes are never logged.",
        default_enabled=False,
        srs_refs=["S9"],
        settings=[
            Setting("source", "enum", "Feedback source", "slm", options=["slm", "fixed_prompts"]),
            Setting("trigger_idle", "bool", "Trigger: idle pause", True),
            Setting("idle_seconds", "int", "Idle threshold (s)", 300, min=5, max=3600,
                    help="SRS default: 5 minutes."),
            Setting("require_sentence_end", "bool", "Idle trigger requires sentence end (. ? !)", True),
            Setting("trigger_sentence_end", "bool", "Trigger: sentence completed and left unchanged", False),
            Setting("sentence_settle_seconds", "int", "Sentence-unchanged wait (s)", 20, min=3, max=600),
            Setting("trigger_deletion", "bool", "Trigger: repeated deletion", False),
            Setting("deletion_threshold", "int", "Deleted characters to count as struggle", 80, min=10, max=2000),
            Setting("context_sentences", "int", "Sentences sent to the model", 2, min=1, max=10),
            Setting("presentation", "enum", "Presentation", "popup", options=["popup", "window", "highlight"],
                    help="Itself A/B-testable."),
            Setting("min_interval_seconds", "int", "Min seconds between pop-ups", 120, min=0, max=7200),
            Setting("max_per_session", "int", "Max pop-ups per writing session", 5, min=1, max=100),
            Setting("allow_rating", "bool", "Let students rate pop-ups", True),
        ],
    ),
    Module(
        key="feedback_presentation",
        label="On-demand feedback presentation",
        category="Feedback venues",
        description="How on-demand feedback is displayed (S15).",
        default_enabled=True,
        srs_refs=["S15"],
        settings=[
            Setting("mode", "enum", "Display mode", "chat_panel", options=["chat_panel", "character"]),
        ],
    ),
    Module(
        key="student_rating",
        label="Student helpfulness rating",
        category="Reward",
        description="Students optionally rate feedback helpful / unhelpful (S11).",
        default_enabled=True,
        srs_refs=["S11"],
    ),
    Module(
        key="instructor_review",
        label="Instructor revision review",
        category="Reward",
        description="Instructor rates a random sample of feedback → revision pairs (I9).",
        default_enabled=True,
        srs_refs=["I9"],
        settings=[
            Setting("sample_size", "int", "Revisions sampled per review session", 5, min=1, max=5),
        ],
    ),
    Module(
        key="reward",
        label="Bandit reward",
        category="Reward",
        description="score = a × student rating + (1 − a) × instructor rating (MAB6). When the "
        "instructor is unavailable the reward falls back to the student signal after a timeout.",
        default_enabled=True,
        srs_refs=["MAB6", "MAB7", "B7"],
        depends_on=["on_demand_feedback"],
        settings=[
            Setting("mode", "enum", "Reward source", "combined",
                    options=["combined", "student_only", "instructor_only"]),
            Setting("student_weight", "float", "Student weight a", 0.5, min=0, max=1),
            Setting("instructor_timeout_hours", "float", "Instructor timeout (h)", 72, min=0, max=24 * 60,
                    help="After this, pending decisions fall back to the student signal."),
            Setting("fallback_student_weight", "float", "Student weight after timeout", 1.0, min=0, max=1),
        ],
    ),
    Module(
        key="learner_model",
        label="Learner model (BKT)",
        category="Adaptivity",
        description="Bayesian Knowledge Tracing per rubric area; feeds the bandit's context (B10, MAB2).",
        default_enabled=True,
        srs_refs=["B10", "MAB2"],
    ),
    Module(
        key="questionnaire",
        label="First-login questionnaire",
        category="Adaptivity",
        description="Writing confidence & technical experience → initial learner profile (S2, B3).",
        default_enabled=True,
        srs_refs=["S2", "B3"],
    ),
    Module(
        key="get_started",
        label="“Get Started” scaffold",
        category="Workspace",
        description="Outline / guiding questions for an empty draft; never a completed response (S10).",
        default_enabled=True,
        srs_refs=["S10"],
    ),
    Module(
        key="version_history",
        label="Version history & restore",
        category="Workspace",
        description="Autosave, manual saves, restore last saved version (S5, S7, B4).",
        default_enabled=True,
        srs_refs=["S5", "S7", "B4"],
        settings=[
            Setting("autosave_seconds", "int", "Autosave interval (s)", 15, min=5, max=30,
                    help="NFR: autosave loses ≤ 30 s of work."),
        ],
    ),
    Module(
        key="paste_control",
        label="Paste handling",
        category="Workspace",
        description="Allow or block paste; accepted pastes are logged with before/after snapshots (S14).",
        default_enabled=True,
        srs_refs=["S14"],
        settings=[
            Setting("allow_paste", "bool", "Allow pasting", True),
        ],
    ),
    Module(
        key="submission_rules",
        label="Submission requirements",
        category="Workspace",
        description="Minimum word / paragraph counts checked before submission (S12).",
        default_enabled=True,
        srs_refs=["S12"],
        settings=[
            Setting("min_words", "int", "Minimum words", 0, min=0, max=20000),
            Setting("min_paragraphs", "int", "Minimum paragraphs", 0, min=0, max=200),
        ],
    ),
    Module(
        key="grades",
        label="Grades visible to students",
        category="Workspace",
        description="Students see released grades and comments (S13).",
        default_enabled=True,
        srs_refs=["S13", "I11"],
    ),
]

MODULES_BY_KEY = {m.key: m for m in MODULES}


def registry_schema() -> list[dict]:
    return [asdict(m) for m in MODULES]


def default_config() -> dict:
    cfg: dict[str, dict] = {}
    for m in MODULES:
        cfg[m.key] = {"enabled": m.default_enabled}
        for s in m.settings:
            cfg[m.key][s.key] = copy.deepcopy(s.default)
    return cfg


class ConfigError(ValueError):
    pass


def _coerce(setting: Setting, value: Any, style_keys: set[str] | None) -> Any:
    t = setting.type
    if t == "bool":
        if not isinstance(value, bool):
            raise ConfigError(f"{setting.key} must be a boolean")
        return value
    if t in ("int", "float"):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ConfigError(f"{setting.key} must be a number")
        value = int(value) if t == "int" else float(value)
        if setting.min is not None and value < setting.min:
            raise ConfigError(f"{setting.key} must be ≥ {setting.min}")
        if setting.max is not None and value > setting.max:
            raise ConfigError(f"{setting.key} must be ≤ {setting.max}")
        return value
    options = set(setting.options or []) if setting.options_source is None else style_keys
    if t == "enum":
        if not isinstance(value, str) or (options is not None and value not in options):
            raise ConfigError(f"{setting.key} must be one of {sorted(options or [])}")
        return value
    if t == "multi_enum":
        if not isinstance(value, list) or (options is not None and any(v not in options for v in value)):
            raise ConfigError(f"{setting.key} must be a subset of {sorted(options or [])}")
        return value
    if t == "text":
        if not isinstance(value, str):
            raise ConfigError(f"{setting.key} must be text")
        return value
    raise ConfigError(f"unknown setting type {t}")


def validate_overrides(overrides: dict | None, style_keys: set[str] | None = None) -> dict:
    """Validate a partial override dict; returns a cleaned copy. Unknown keys are rejected."""
    if not overrides:
        return {}
    if not isinstance(overrides, dict):
        raise ConfigError("config must be an object")
    clean: dict[str, dict] = {}
    for mkey, mval in overrides.items():
        module = MODULES_BY_KEY.get(mkey)
        if module is None:
            raise ConfigError(f"unknown module '{mkey}'")
        if not isinstance(mval, dict):
            raise ConfigError(f"{mkey} must be an object")
        settings = {s.key: s for s in module.settings}
        out = {}
        for k, v in mval.items():
            if k == "enabled":
                if not isinstance(v, bool):
                    raise ConfigError(f"{mkey}.enabled must be a boolean")
                out[k] = v
            elif k in settings:
                out[k] = _coerce(settings[k], v, style_keys)
            else:
                raise ConfigError(f"unknown setting '{mkey}.{k}'")
        if out:
            clean[mkey] = out
    return clean


def resolve(layers: list[tuple[str, dict | None]]) -> tuple[dict, dict]:
    """Merge layers in order. Returns (config, provenance) where provenance[module][field]
    names the layer that set the effective value."""
    config = default_config()
    provenance = {m: {f: "system" for f in fields} for m, fields in config.items()}
    for layer_name, overrides in layers:
        for mkey, mval in (overrides or {}).items():
            if mkey not in config:
                continue
            for fkey, value in mval.items():
                if fkey in config[mkey]:
                    config[mkey][fkey] = copy.deepcopy(value)
                    provenance[mkey][fkey] = layer_name
    # A module whose dependency is off is forced off, so the system stays coherent.
    for m in MODULES:
        for dep in m.depends_on:
            if config[m.key]["enabled"] and not config[dep]["enabled"]:
                config[m.key]["enabled"] = False
                provenance[m.key]["enabled"] = f"dependency:{dep}"
    return config, provenance
