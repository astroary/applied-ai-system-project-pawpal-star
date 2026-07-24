"""Tests for the guardrail layer (offline — no API key or network).

Covers input validation + unsafe-request refusal, output groundedness, plan
fidelity (the check that catches AI drift), output safety, and the planner's
integration of all of the above.
"""

import pytest

from ai_planner import AIPlan, AIPlanner
from guardrails import (
    REFUSAL_MESSAGE,
    extract_citations,
    validate_input,
    verify_output,
)
from pawpal_system import Owner, Pet, Task
from retrieval import Retriever
from tests.test_ai_planner import FakeLLM  # reuse the fake LLM


@pytest.fixture(scope="module")
def retriever() -> Retriever:
    return Retriever().load()


def make_owner() -> Owner:
    o = Owner(name="Jordan", daily_minutes_available=90)
    dog = Pet(name="Biscuit", species="dog")
    dog.add_task(Task("Morning walk", 20, priority="high", time="08:00"))
    o.add_pet(dog)
    return o


# --- Input validation -----------------------------------------------------
def test_valid_input_passes():
    assert validate_input(make_owner()).severity == "ok"


def test_empty_owner_warns_not_blocks():
    """No pets/tasks is a warning (nothing to plan), not a safety block."""
    result = validate_input(Owner(name="Jordan", daily_minutes_available=90))
    assert result.severity == "warn"
    assert result.passed  # a warning still 'passes'


@pytest.mark.parametrize(
    "request_text",
    [
        "How much ibuprofen can I give my dog?",
        "What dosage of benadryl for a cat?",
        "Give 5mg of medication",
        "Can you diagnose my dog's limp?",
        "Please prescribe something for the itching",
    ],
)
def test_unsafe_requests_are_blocked(request_text):
    """Dosing/diagnosis/treatment requests are refused with the vet message."""
    result = validate_input(make_owner(), request=request_text)
    assert result.blocked
    assert result.message == REFUSAL_MESSAGE


def test_benign_medication_reminder_is_allowed():
    """A vet-prescribed med *reminder* (no dosing) must not be refused."""
    owner = make_owner()
    owner.pets[0].add_task(Task("Medication reminder", 5, time="20:00"))
    assert validate_input(owner).severity == "ok"


def test_unsafe_task_title_is_blocked():
    """Unsafe intent hidden in a task title is caught too, not just requests."""
    owner = make_owner()
    owner.pets[0].add_task(Task("Give aspirin dose", 5, time="12:00"))
    assert validate_input(owner).blocked


# --- Citation extraction --------------------------------------------------
def test_extract_citations_handles_grouped_labels():
    """'[S1, S3, S4]' yields all three labels."""
    assert extract_citations(["grounded in [S1, S3, S4]"]) == {"S1", "S3", "S4"}


# --- Output groundedness --------------------------------------------------
def test_ungrounded_citation_warns():
    """Citing S9 when only 2 sources were retrieved is flagged."""
    plan = AIPlan(summary="see [S9]", steps=[], sources_used=["S9"])
    result = verify_output(plan, retrieved_chunks=[object(), object()], scheduler_plan=[])
    assert result.severity == "warn"
    assert any("S9" in issue for issue in result.issues)


# --- Plan fidelity --------------------------------------------------------
def test_plan_drift_is_flagged():
    """A step for a (pet, task) not in the schedule is flagged as drift.

    This is the exact Mochi/Biscuit slip from the Phase 2 live run.
    """
    walk = Task("Morning walk", 20, time="08:00", pet_name="Biscuit")
    scheduler_plan = [{"time": "08:00", "task": walk}]
    plan = AIPlan(
        summary="",
        steps=[{"time": "08:00", "pet": "Biscuit", "task": "Play session"}],
    )
    result = verify_output(plan, retrieved_chunks=[object()], scheduler_plan=scheduler_plan)
    assert result.severity == "warn"
    assert any("drift" in issue.lower() for issue in result.issues)


def test_faithful_grounded_plan_passes():
    """A plan that only cites real sources and real tasks passes clean."""
    walk = Task("Morning walk", 20, time="08:00", pet_name="Biscuit")
    scheduler_plan = [{"time": "08:00", "task": walk}]
    plan = AIPlan(
        summary="Walk grounded in [S1].",
        steps=[{"time": "08:00", "pet": "Biscuit", "task": "Morning walk",
                "rationale": "good routine [S1]", "sources": ["S1"]}],
        sources_used=["S1"],
    )
    result = verify_output(plan, retrieved_chunks=[object()], scheduler_plan=scheduler_plan)
    assert result.severity == "ok"


# --- Output safety --------------------------------------------------------
def test_dosing_in_output_is_blocked():
    """If the model somehow emits a dose, the output is blocked."""
    plan = AIPlan(summary="Give 200mg twice daily", steps=[])
    result = verify_output(plan, retrieved_chunks=[object()], scheduler_plan=[])
    assert result.blocked


# --- Planner integration --------------------------------------------------
def test_planner_refuses_unsafe_request_without_calling_model(retriever):
    """Unsafe input short-circuits: the LLM is never called."""
    fake = FakeLLM()
    plan = AIPlanner(retriever, llm=fake).plan(make_owner(), request="how much tylenol?")
    assert plan.refused
    assert plan.summary == REFUSAL_MESSAGE
    assert fake.last_user is None  # model was never invoked


def test_planner_attaches_guardrail_result(retriever):
    """A normal plan carries its output-verification result for logging."""
    plan = AIPlanner(retriever, llm=FakeLLM()).plan(make_owner())
    assert "severity" in plan.guardrails
