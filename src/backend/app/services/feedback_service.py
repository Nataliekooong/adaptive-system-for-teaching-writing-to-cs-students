"""Feedback-service interface (SRS §6: every model call goes through one interface).

`FeedbackProvider` is the contract. The SLM is not built yet, so `MockSLMProvider` produces
rubric-aligned, heuristic feedback with the same structured shape the real model must return.
Set SLM_PROVIDER=http and SLM_URL=... to point at the self-hosted model later.
"""
from __future__ import annotations

import json
import os
import random
import re
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class FeedbackUnavailable(Exception):
    """Model service failed or returned something unusable. The draft is never affected."""


@dataclass
class FeedbackRequest:
    text: str  # full draft (on-demand) or the latest sentence(s) (real-time)
    venue: str  # on_demand | realtime
    rubric_areas: list[str]
    style: str | None
    style_template: str = ""
    learner_context: dict = field(default_factory=dict)
    assignment_title: str = ""
    trigger: str | None = None


@dataclass
class FeedbackResult:
    content: dict  # {"summary": str, "items": [{rubric_area, comment, suggestion, quote}]}
    model_version: str
    prompt_template: str
    guardrail_status: str = "approved"


class FeedbackProvider(ABC):
    @abstractmethod
    def generate(self, req: FeedbackRequest) -> FeedbackResult: ...


# ---------------------------------------------------------------- mock SLM

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
_FILLERS = ["very", "really", "basically", "actually", "just", "in order to", "a lot of", "kind of", "sort of"]
_VAGUE = ["thing", "things", "stuff", "good", "bad", "fast", "big", "nice", "etc"]
_EVIDENCE = ["because", "for example", "for instance", "such as", "e.g.", "%", "ms", "according to", "["]
_DIRECT_ANSWER = re.compile(r"\b(write (it|this|my|the) (for me|essay|assignment)|do my (homework|assignment))\b", re.I)


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT_SPLIT.split(text.strip()) if s.strip()]


def paragraphs(text: str) -> list[str]:
    return [p for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]


def _short(s: str, n: int = 12) -> str:
    words = s.split()
    return " ".join(words[:n]) + ("…" if len(words) > n else "")


def _findings(text: str, areas: list[str]) -> list[dict]:
    """Heuristic stand-in for model analysis. Returns at most one finding per rubric area."""
    sents = sentences(text)
    paras = paragraphs(text)
    low = text.lower()
    out: list[dict] = []
    for area in areas:
        a = area.lower()
        f = None
        if "clarity" in a or "concis" in a:
            long_s = next((s for s in sents if len(s.split()) > 30), None)
            filler = next((w for w in _FILLERS if re.search(rf"\b{re.escape(w)}\b", low)), None)
            if long_s:
                f = ("This sentence runs over 30 words, so the main point gets buried.",
                     "split it at the point where a new idea begins", long_s)
            elif filler:
                f = (f"Words like “{filler}” add length without adding meaning.",
                     "cut filler words and check whether the sentence still says the same thing", filler)
        elif "organ" in a or "structure" in a:
            if len(paras) < 3 and len(text.split()) > 120:
                f = ("The draft reads as one or two large blocks, which makes the structure hard to follow.",
                     "group related ideas and give each paragraph a single job", paras[0] if paras else "")
        elif "thesis" in a or "purpose" in a:
            first = sentences(paras[0]) if paras else []
            if len(first) < 2:
                f = ("The opening does not yet tell the reader what the document will argue or propose.",
                     "state the purpose and the main claim in the first paragraph", first[0] if first else "")
        elif "precision" in a or "technical" in a:
            vague = next((w for w in _VAGUE if re.search(rf"\b{re.escape(w)}\b", low)), None)
            if vague:
                f = (f"“{vague}” is imprecise for a technical reader.",
                     "replace it with a specific term, metric or component name", vague)
        elif "evidence" in a or "support" in a:
            if not any(k in low for k in _EVIDENCE) and len(sents) >= 3:
                f = ("Claims are made without supporting evidence, data or examples.",
                     "back the strongest claim with a measurement, citation or concrete example",
                     sents[1] if len(sents) > 1 else "")
        elif "grammar" in a or "mechanic" in a:
            bad = next((s for s in sents if s[:1].islower()), None)
            if bad or "  " in text or re.search(r"\bi\b", text):
                f = ("There are small mechanical issues (capitalization or spacing).",
                     "proofread sentence starts, the pronoun “I”, and double spaces", bad or "")
        elif "audience" in a:
            if len(re.findall(r"\b[A-Z]{3,}\b", text)) >= 3:
                f = ("Several acronyms appear; a reader new to the project may not know them.",
                     "define each acronym the first time you use it", "")
        if f:
            out.append({"rubric_area": area, "comment": f[0], "suggestion": f[1], "quote": _short(f[2])})
    return out


_STYLE_RENDER = {
    "direct": lambda f: (f["comment"], f"Revise: {f['suggestion']}."),
    "socratic": lambda f: (f"Looking at “{f['quote']}” — what is the one idea a reader should take away?"
                           if f["quote"] else "What would a reader need here that is not on the page yet?",
                           f"Ask yourself: how could you {f['suggestion']}?"),
    "praise_then_suggest": lambda f: (f"You have a solid base to work from. One thing to strengthen: "
                                      f"{f['comment'][0].lower()}{f['comment'][1:]}",
                                      f"Next step: {f['suggestion']}."),
    "rubric_checklist": lambda f: (f"☐ {f['rubric_area']}: {f['comment']}",
                                   f"Check: {f['suggestion']}."),
}


class MockSLMProvider(FeedbackProvider):
    model_version = "mock-slm-0.1"

    def generate(self, req: FeedbackRequest) -> FeedbackResult:
        if os.getenv("MOCK_SLM_FAIL") == "1":
            raise FeedbackUnavailable("Mock SLM configured to fail (MOCK_SLM_FAIL=1).")
        style = req.style or "direct"
        template = f"{req.venue}/{style}/v1"
        if _DIRECT_ANSWER.search(req.text):
            # Authorship guardrail: never write the assignment for the student.
            return FeedbackResult(
                {"summary": "I can't write the assignment for you, but I can help you plan it.",
                 "items": [{"rubric_area": "Process", "comment": "Start by listing the three points you most "
                            "want the reader to remember.", "suggestion": "Turn each point into a topic sentence "
                            "in your own words.", "quote": ""}]},
                self.model_version, template, "rewritten")
        areas = req.rubric_areas or ["Clarity & Concision"]
        found = _findings(req.text, areas)
        if req.venue == "realtime":
            found = found[:1]
            if not found:
                return FeedbackResult({"summary": "Nice flow — keep going.", "items": []},
                                      self.model_version, template)
        else:
            random.shuffle(found)
            found = found[:3]
        render = _STYLE_RENDER.get(style, _STYLE_RENDER["direct"])
        items = []
        for f in found:
            comment, suggestion = render(f)
            items.append({**f, "comment": comment, "suggestion": suggestion})
        if not req.text.strip():
            summary = "Your draft is empty — try “Get Started” or write a first rough paragraph."
        elif not items:
            summary = "No major issues in your priority areas. Re-read once from the reader's point of view."
        else:
            summary = f"{len(items)} suggestion(s) focused on: " + ", ".join(i["rubric_area"] for i in items)
        return FeedbackResult({"summary": summary, "items": items}, self.model_version, template)


class HTTPSLMProvider(FeedbackProvider):
    """Adapter for the self-hosted SLM (e.g. vLLM behind a small JSON endpoint)."""

    def __init__(self, url: str, timeout: float = 15.0):
        self.url = url
        self.timeout = timeout

    def generate(self, req: FeedbackRequest) -> FeedbackResult:
        body = json.dumps(req.__dict__).encode()
        http_req = urllib.request.Request(self.url, data=body, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(http_req, timeout=self.timeout) as resp:
                data = json.loads(resp.read())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            raise FeedbackUnavailable(f"SLM service unavailable: {e}") from e
        try:
            return FeedbackResult(data["content"], data["model_version"], data["prompt_template"])
        except (KeyError, TypeError) as e:
            raise FeedbackUnavailable("SLM returned an invalid response") from e


def get_slm_provider() -> FeedbackProvider:
    if os.getenv("SLM_PROVIDER", "mock") == "http":
        return HTTPSLMProvider(os.environ["SLM_URL"])
    return MockSLMProvider()


# ---------------------------------------------------------------- guardrail (B9)

MAX_FIELD_WORDS = 80


def validate(result: FeedbackResult) -> FeedbackResult:
    """Schema check + authorship guard. Long prose is truncated ("rewritten"); malformed → error."""
    c = result.content
    if not isinstance(c, dict) or not isinstance(c.get("summary"), str) or not isinstance(c.get("items"), list):
        raise FeedbackUnavailable("Feedback failed validation (malformed structure).")
    status = result.guardrail_status
    for item in c["items"]:
        if not isinstance(item, dict):
            raise FeedbackUnavailable("Feedback failed validation (malformed item).")
        for key in ("comment", "suggestion"):
            words = str(item.get(key, "")).split()
            if len(words) > MAX_FIELD_WORDS:
                item[key] = " ".join(words[:MAX_FIELD_WORDS]) + "…"
                status = "rewritten"
    result.guardrail_status = status
    return result
