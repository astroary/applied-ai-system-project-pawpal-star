"""Tests for the self-critique loop and confidence scoring (offline).

A ScriptedLLM returns a pre-written draft then a pre-written critique, so we can
prove the loop fixes plan drift, refuses to make things worse, scores confidence
sensibly, and degrades gracefully when the critique call fails.
"""

import json

import pytest

from ai_planner import AIPlan, AIPlanner
from critique import CritiqueResult, compute_confidence, self_critique
from pawpal_system import Owner, Pet, Task
from retrieval import Retriever


@pytest.fixture(scope="module")
def retriever() -> Retriever:
    return Retriever().load()


def make_owner() -> Owner:
    o = Owner(name="Jordan", daily_minutes_available=90)
    dog = Pet(name="Biscuit", species="dog")
    dog.add_task(Task("Morning walk", 20, priority="high", time="08:00"))
    cat = Pet(name="Mochi", species="cat")
    cat.add_task(Task("Play session", 15, priority="medium", time="09:00"))
    o.add_pet(dog)
    o.add_pet(cat)
    return o


# A draft that drifts: it assigns Mochi's "Play session" to Biscuit.
DRAFT_WITH_DRIFT = json.dumps({
    "summary": "Draft day plan.",
    "steps": [
        {"time": "08:00", "pet": "Biscuit", "task": "Morning walk",
         "rationale": "good routine [S1]", "sources": ["S1"]},
        {"time": "09:00", "pet": "Biscuit", "task": "Play session",
         "rationale": "enrichment [S1]", "sources": ["S1"]},
    ],
    "notes": "",
    "sources_used": ["S1"],
})

# A critique that fixes the drift (Play session reassigned to Mochi).
CRITIQUE_FIX = json.dumps({
    "confidence": 0.9,
    "assessment": "Reassigned the play session to the correct pet.",
    "problems": ["Play session was assigned to Biscuit instead of Mochi."],
    "revised_plan": {
        "summary": "Corrected day plan.",
        "steps": [
            {"time": "08:00", "pet": "Biscuit", "task": "Morning walk",
             "rationale": "good routine [S1]", "sources": ["S1"]},
            {"time": "09:00", "pet": "Mochi", "task": "Play session",
             "rationale": "enrichment [S1]", "sources": ["S1"]},
        ],
        "notes": "",
        "sources_used": ["S1"],
    },
})


class ScriptedLLM:
    """Returns queued replies in order and records every call."""

    def __init__(self, replies, model="fake-model"):
        self.replies = list(replies)
        self.model = model
        self.calls = []

    def chat(self, system, user, **kwargs):
        self.calls.append((system, user))
        return self.replies.pop(0) if self.replies else "{}"


# --- Confidence scoring ---------------------------------------------------
def test_confidence_zero_when_blocked():
    assert compute_confidence(0.9, [], blocked=True) == 0.0


def test_confidence_drops_with_issues():
    clean = compute_confidence(0.8, [], blocked=False)
    dirty = compute_confidence(0.8, ["a", "b"], blocked=False)
    assert clean > dirty
    assert 0.0 <= dirty <= clean <= 1.0


def test_confidence_clamps_bad_model_rating():
    """A nonsensical self-rating can't push confidence out of range."""
    assert 0.0 <= compute_confidence(5.0, [], blocked=False) <= 1.0


# --- The critique loop ----------------------------------------------------
def _drifted_plan(retriever, owner) -> tuple:
    """Produce a real drifted AIPlan plus the chunks/schedule to verify against."""
    planner = AIPlanner(retriever, llm=ScriptedLLM([DRAFT_WITH_DRIFT]))
    plan, chunks, scheduler_plan = planner._generate(owner)
    return plan, chunks, scheduler_plan


def test_critique_fixes_plan_drift(retriever):
    """The loop should accept a revision that removes drift and raise confidence."""
    owner = make_owner()
    plan, chunks, scheduler_plan = _drifted_plan(retriever, owner)
    assert plan.guardrails["issues"], "draft should start with drift issues"

    result = self_critique(ScriptedLLM([CRITIQUE_FIX]), plan, chunks, scheduler_plan)
    assert result.revised
    assert result.problems_after == []          # drift resolved
    assert result.plan.steps[1]["pet"] == "Mochi"
    assert result.confidence > compute_confidence(0.7, plan.guardrails["issues"], False)


def test_critique_keeps_original_when_revision_not_better(retriever):
    """A revision that reintroduces drift is rejected; original is kept."""
    owner = make_owner()
    plan, chunks, scheduler_plan = _drifted_plan(retriever, owner)
    worse = json.dumps({
        "confidence": 0.99,
        "assessment": "no real fix",
        "problems": [],
        "revised_plan": {
            "summary": "still drifted",
            "steps": [{"time": "09:00", "pet": "Biscuit", "task": "Play session"}],
            "notes": "", "sources_used": ["S1"],
        },
    })
    result = self_critique(ScriptedLLM([worse]), plan, chunks, scheduler_plan)
    assert result.revised is False
    assert any("reject" in e["step"] for e in result.trace)


def test_critique_degrades_gracefully_on_bad_reply(retriever):
    """If the critique reply can't be parsed, keep the plan and don't crash."""
    owner = make_owner()
    plan, chunks, scheduler_plan = _drifted_plan(retriever, owner)
    result = self_critique(ScriptedLLM(["not json at all"]), plan, chunks, scheduler_plan)
    assert result.plan is plan
    assert any(e["step"] == "critique_error" for e in result.trace)


def test_refused_plan_short_circuits(retriever):
    """A refused plan is returned immediately with zero confidence."""
    refused = AIPlan(summary="refused", steps=[], refused=True)
    result = self_critique(ScriptedLLM([]), refused, [], [])
    assert result.confidence == 0.0
    assert result.plan is refused


# --- Trace / logging surface ----------------------------------------------
def test_trace_is_recorded_and_serializable(retriever):
    owner = make_owner()
    plan, chunks, scheduler_plan = _drifted_plan(retriever, owner)
    result = self_critique(ScriptedLLM([CRITIQUE_FIX]), plan, chunks, scheduler_plan)
    steps = [e["step"] for e in result.trace]
    assert steps[0] == "generate" and steps[-1] == "score"
    json.loads(json.dumps(result.to_dict()))       # JSON-safe for the log
    assert "Self-critique trace" in result.to_markdown()


def test_markdown_shows_before_and_after_steps(retriever):
    """The trace visibly shows the drifted draft step and the corrected step."""
    owner = make_owner()
    plan, chunks, scheduler_plan = _drifted_plan(retriever, owner)
    result = self_critique(ScriptedLLM([CRITIQUE_FIX]), plan, chunks, scheduler_plan)
    md = result.to_markdown()
    assert "First draft (before critique):" in md
    assert "After self-critique:" in md
    # draft assigned the play session to Biscuit; the fix reassigns it to Mochi
    assert "Biscuit · Play session" in md
    assert "Mochi · Play session" in md


# --- End-to-end integration through the planner ---------------------------
def test_plan_and_review_runs_full_loop(retriever):
    """plan_and_review: draft (drift) -> critique (fix) -> scored result."""
    owner = make_owner()
    llm = ScriptedLLM([DRAFT_WITH_DRIFT, CRITIQUE_FIX])
    result = AIPlanner(retriever, llm=llm).plan_and_review(owner)
    assert isinstance(result, CritiqueResult)
    assert len(llm.calls) == 2                      # one plan call, one critique call
    assert result.revised
    assert result.problems_after == []


def test_plan_and_review_refuses_unsafe_input(retriever):
    """Unsafe input is refused before any model call, even via the review path."""
    llm = ScriptedLLM([])
    result = AIPlanner(retriever, llm=llm).plan_and_review(
        make_owner(), request="what dose of aspirin?")
    assert result.plan.refused
    assert result.confidence == 0.0
    assert llm.calls == []
