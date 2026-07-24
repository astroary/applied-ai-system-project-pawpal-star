"""Tests for the AI planning layer (offline — no API key or network).

A FakeLLM stands in for the real Groq client so these tests run deterministically
and for free. They verify prompt construction, retrieval wiring, JSON parsing,
and error handling — not the model's actual output quality (that's the live
smoke test and the Phase 6 evaluation harness).
"""

import json

import pytest

from ai_planner import AIPlan, AIPlanner, PlannerError, SYSTEM_PROMPT
from pawpal_system import Owner, Pet, Task
from retrieval import Retriever

VALID_REPLY = json.dumps(
    {
        "summary": "A balanced morning for Biscuit and Mochi.",
        "steps": [
            {
                "time": "08:00",
                "pet": "Biscuit",
                "task": "Morning walk",
                "rationale": "Kept short for a puppy's developing joints [S1].",
                "sources": ["S1"],
            }
        ],
        "notes": "Split play before meals [S2].",
        "sources_used": ["S1", "S2"],
    }
)


class FakeLLM:
    """Records the prompts it receives and returns a canned reply."""

    def __init__(self, reply: str = VALID_REPLY, model: str = "fake-model"):
        self.reply = reply
        self.model = model
        self.last_system: str | None = None
        self.last_user: str | None = None

    def chat(self, system: str, user: str, **kwargs) -> str:
        self.last_system = system
        self.last_user = user
        return self.reply


@pytest.fixture(scope="module")
def retriever() -> Retriever:
    return Retriever().load()


@pytest.fixture
def owner() -> Owner:
    o = Owner(name="Jordan", daily_minutes_available=90)
    dog = Pet(name="Biscuit", species="dog")
    dog.add_task(Task("Morning walk", 20, priority="high", time="08:00"))
    cat = Pet(name="Mochi", species="cat")
    cat.add_task(Task("Play session", 15, priority="medium", time="09:00"))
    o.add_pet(dog)
    o.add_pet(cat)
    return o


# --- Query construction ---------------------------------------------------
def test_build_query_includes_species_and_tasks(owner):
    """The retrieval query is derived from pet species and task titles."""
    query = AIPlanner.build_query(owner)
    assert "dog" in query
    assert "cat" in query
    assert "Morning walk" in query
    assert "Play session" in query


# --- Prompt wiring --------------------------------------------------------
def test_plan_feeds_retrieved_sources_into_prompt(retriever, owner):
    """The planner must put the deterministic plan AND sources in the prompt."""
    fake = FakeLLM()
    AIPlanner(retriever, llm=fake).plan(owner)
    assert "SOURCES:" in fake.last_user
    assert "DAILY PLAN" in fake.last_user
    assert "[S1]" in fake.last_user  # at least one retrieved, numbered source
    assert "Biscuit" in fake.last_user


def test_system_prompt_forbids_medical_advice():
    """Defense in depth: the planner instruction itself refuses dosing advice."""
    lowered = SYSTEM_PROMPT.lower()
    assert "medication" in lowered or "dosing" in lowered
    assert "veterinarian" in lowered


# --- Parsing into AIPlan --------------------------------------------------
def test_plan_parses_reply_into_aiplan(retriever, owner):
    """A well-formed JSON reply becomes a structured AIPlan."""
    fake = FakeLLM()
    plan = AIPlanner(retriever, llm=fake).plan(owner)
    assert isinstance(plan, AIPlan)
    assert plan.summary.startswith("A balanced morning")
    assert plan.steps[0]["pet"] == "Biscuit"
    assert plan.sources_used == ["S1", "S2"]
    assert plan.model == "fake-model"
    assert plan.raw  # raw text retained for the audit log


def test_parse_strips_markdown_code_fences():
    """Models often wrap JSON in ```json fences; the parser tolerates that."""
    fenced = "```json\n" + VALID_REPLY + "\n```"
    data = AIPlanner._parse(fenced)
    assert data["summary"].startswith("A balanced morning")


def test_parse_extracts_json_amid_prose():
    """Stray prose around the JSON object is sliced away."""
    noisy = "Here is your plan:\n" + VALID_REPLY + "\nHope that helps!"
    data = AIPlanner._parse(noisy)
    assert data["steps"][0]["task"] == "Morning walk"


def test_plan_raises_on_unparseable_reply(retriever, owner):
    """A reply with no JSON object raises PlannerError, not a random crash."""
    fake = FakeLLM(reply="I cannot help with that.")
    with pytest.raises(PlannerError):
        AIPlanner(retriever, llm=fake).plan(owner)


def test_aiplan_to_dict_is_json_safe(retriever, owner):
    """AIPlan.to_dict() round-trips through json (needed by the Phase 5 log)."""
    plan = AIPlanner(retriever, llm=FakeLLM()).plan(owner)
    restored = json.loads(json.dumps(plan.to_dict()))
    assert restored["model"] == "fake-model"
    assert "raw" not in restored  # raw text stays out of the structured dict
