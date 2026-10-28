"""Demo data for local development. All accounts use the password `password` (test values only)."""
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import hash_password
from .models import (
    Assignment,
    AssignmentStudent,
    Condition,
    Course,
    Enrollment,
    Experiment,
    FeedbackStyle,
    FixedPrompt,
    User,
    now,
)

DEMO_PASSWORD = "password"

RUBRIC = ["Thesis & Purpose", "Organization", "Clarity & Concision", "Technical Precision",
          "Evidence & Support", "Grammar & Mechanics", "Audience Awareness"]

STYLES = [
    ("direct", "Direct", "States the issue and the fix plainly.",
     "Identify the issue in {area} and state concretely how to revise it. Do not rewrite the text."),
    ("socratic", "Socratic", "Guiding questions that lead the student to the fix.",
     "Ask one or two guiding questions about {area} that help the student find the revision themselves."),
    ("praise_then_suggest", "Praise → suggest", "Names a strength, then one next step.",
     "Name one genuine strength, then one next step for {area}."),
    ("rubric_checklist", "Rubric checklist", "Checklist items mapped to rubric areas.",
     "Return a checklist line for {area} with a check the student can perform."),
]

FIXED_PROMPTS = [
    ("idle", "", "Stuck? Try writing the next sentence badly on purpose — you can fix it later."),
    ("idle", "Organization", "Re-read your last paragraph: what is its one job in the document?"),
    ("sentence_end", "Clarity & Concision", "Read that sentence aloud. Could you say it in fewer words?"),
    ("sentence_end", "Technical Precision", "Is there a vague word in that sentence you could replace with a "
                                            "specific term or number?"),
    ("deletion", "", "Lots of rewriting here. Try jotting the idea as a bullet first, then turn it into prose."),
    ("on_demand", "Thesis & Purpose", "Can a reader find your main claim in the first paragraph?"),
    ("on_demand", "Evidence & Support", "Pick your strongest claim. What evidence would convince a skeptical reader?"),
    ("any", "Audience Awareness", "Who is your reader? Underline one term they might not know."),
]

STUDENTS = [("priya", "Priya Sharma"), ("marcus", "Marcus Chen"), ("alex", "Alex Kim"),
            ("jordan", "Jordan Lee"), ("sam", "Sam Okafor"), ("taylor", "Taylor Nguyen")]


def seed_if_empty(db: Session) -> None:
    if db.scalar(select(User.id)):
        return
    pw = hash_password(DEMO_PASSWORD)
    lee = User(username="drlee", display_name="Dr. Lee", role="instructor", password_hash=pw, pseudonym="I-0001")
    db.add(lee)
    students = []
    for i, (u, name) in enumerate(STUDENTS, start=1):
        s = User(username=u, display_name=name, role="student", password_hash=pw, pseudonym=f"S-{1000 + i:04d}")
        db.add(s)
        students.append(s)
    for key, name, desc, tmpl in STYLES:
        db.add(FeedbackStyle(key=key, name=name, description=desc, prompt_template=tmpl, enabled=True))
    db.flush()

    course = Course(code="COMPSCI 2ME3", title="Technical Writing for Software Engineers", instructor_id=lee.id,
                    rubric_areas=RUBRIC, config={})
    db.add(course)
    db.flush()
    for s in students:
        db.add(Enrollment(course_id=course.id, user_id=s.id))
    for trigger, area, text in FIXED_PROMPTS:
        db.add(FixedPrompt(course_id=course.id, trigger=trigger, rubric_area=area, text=text))

    a1 = Assignment(
        course_id=course.id, title="Design Document: Caching Layer",
        description="Propose a caching layer for the course-registration service.",
        instructions="Write a 600–900 word design document. Explain the problem, the proposed design, "
                     "alternatives you considered, and how you will measure success.",
        genre_guidance="A design doc persuades engineers to adopt a design. Lead with the problem and the "
                       "decision; support it with data; be explicit about trade-offs.",
        due_date=now() + timedelta(days=14),
        rubric_areas=["Thesis & Purpose", "Organization", "Clarity & Concision", "Technical Precision",
                      "Evidence & Support"],
        get_started_content="Outline to fill in with your own words:\n\n1. Problem — what is slow or broken, "
                            "and for whom?\n2. Goals and non-goals\n3. Proposed design — components and data flow\n"
                            "4. Alternatives considered — why not them?\n5. How will you measure success?\n\n"
                            "Guiding questions:\n• What number would convince your team lead this is worth doing?\n"
                            "• What happens when the cache is stale?",
        config={"submission_rules": {"min_words": 150, "min_paragraphs": 3}},
    )
    a2 = Assignment(
        course_id=course.id, title="Lab Report: Sorting Benchmarks",
        description="Report on your sorting algorithm benchmark results.",
        instructions="Write a short lab report (400–600 words) presenting your benchmark method and results.",
        genre_guidance="Lab reports are precise and reproducible. Every claim should point at a measurement.",
        due_date=now() + timedelta(days=28),
        rubric_areas=["Organization", "Technical Precision", "Evidence & Support", "Grammar & Mechanics"],
        get_started_content="Sections: Introduction · Method · Results · Discussion.\n"
                            "Ask yourself: could a classmate rerun your experiment from the Method section alone?",
        config={"realtime_feedback": {"enabled": True, "idle_seconds": 30, "min_interval_seconds": 60}},
    )
    db.add_all([a1, a2])
    db.flush()
    for a in (a1, a2):
        for s in students:
            db.add(AssignmentStudent(assignment_id=a.id, student_id=s.id, override_config={}))

    # Example A/B tests, left in draft so the instructor chooses when to start them.
    venue = Experiment(
        course_id=course.id, assignment_id=a1.id, name="Feedback venue: on-demand vs real-time",
        hypothesis="Real-time nudges lead to more revisions than on-demand feedback alone.",
        strategy="balanced", status="draft")
    venue.conditions = [
        Condition(name="A · On-demand only", weight=1,
                  config={"on_demand_feedback": {"enabled": True}, "realtime_feedback": {"enabled": False}}),
        Condition(name="B · Real-time only", weight=1,
                  config={"on_demand_feedback": {"enabled": False},
                          "realtime_feedback": {"enabled": True, "idle_seconds": 30, "presentation": "popup"}}),
        Condition(name="C · Both", weight=1,
                  config={"on_demand_feedback": {"enabled": True},
                          "realtime_feedback": {"enabled": True, "idle_seconds": 30, "presentation": "highlight"}}),
    ]
    source = Experiment(
        course_id=course.id, assignment_id=None, name="Fixed prompts only vs SLM + fixed prompts",
        hypothesis="Model-generated feedback is rated more helpful than the fixed prompt library.",
        strategy="random", status="draft")
    source.conditions = [
        Condition(name="Fixed prompts only", config={"on_demand_feedback": {"source": "fixed_prompts"},
                                                     "realtime_feedback": {"source": "fixed_prompts"}}),
        Condition(name="SLM + fixed prompts", config={"on_demand_feedback": {"source": "slm"},
                                                      "realtime_feedback": {"source": "fixed_prompts"}}),
    ]
    db.add_all([venue, source])
    db.commit()
