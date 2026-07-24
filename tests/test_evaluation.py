"""Tests for the reliability evaluation harness (offline, fake runner).

Verify the harness scores checks correctly, handles refusals and crashes, and
that the built-in DEFAULT_SCENARIOS all pass when driven by a well-behaved
system — which also confirms the scenario criteria are internally consistent.
"""

from ai_planner import AIPlan
from critique import CritiqueResult
from evaluation.harness import (
    DEFAULT_SCENARIOS,
    Scenario,
    confident,
    not_refused,
    refused,
    run_evaluation,
)
from guardrails import validate_input
from pawpal_system import Owner, Pet, Task


def good_result(confidence=0.9) -> CritiqueResult:
    return CritiqueResult(
        plan=AIPlan(summary="ok", steps=[], sources_used=["S1"]),
        confidence=confidence,
        problems_before=[],
        problems_after=[],
    )


def well_behaved_runner(owner, request):
    """Mimics the real system: refuses unsafe input, else returns a good plan."""
    check = validate_input(owner, request)
    if check.blocked:
        return CritiqueResult.refused(
            AIPlan(summary=check.message, steps=[], refused=True)
        )
    return good_result()


# --- Harness mechanics ----------------------------------------------------
def test_default_scenarios_all_pass_with_well_behaved_system():
    report = run_evaluation(well_behaved_runner)
    assert report.all_passed, report.summary()
    assert report.passed_checks == report.total_checks
    assert report.avg_confidence() == 0.9  # only planned scenarios counted


def test_failing_check_is_recorded():
    """A low-confidence result fails a confidence check."""
    owner = Owner(name="Jordan", daily_minutes_available=90)
    owner.add_pet(Pet(name="Biscuit", species="dog"))
    scenario = Scenario("low conf", lambda: owner, "", [not_refused(), confident(0.8)])
    report = run_evaluation(lambda o, r: good_result(confidence=0.3), [scenario])
    assert not report.all_passed
    assert report.passed_checks == 1  # not_refused passes, confident(0.8) fails


def test_refused_scenario_passes_refusal_check():
    def owner_with_dose():
        o = Owner(name="Pat", daily_minutes_available=60)
        p = Pet(name="Buddy", species="dog")
        p.add_task(Task("Give aspirin dose", 5, time="09:00"))
        o.add_pet(p)
        return o

    scenario = Scenario("unsafe", owner_with_dose, "", [refused()])
    report = run_evaluation(well_behaved_runner, [scenario])
    assert report.all_passed


def test_runner_crash_is_recorded_not_raised():
    def boom(owner, request):
        raise RuntimeError("model exploded")

    scenario = Scenario("crash", lambda: Owner("X"), "", [not_refused()])
    report = run_evaluation(boom, [scenario])
    assert not report.all_passed
    assert "model exploded" in report.results[0].error


# --- Report rendering -----------------------------------------------------
def test_markdown_and_summary_render():
    report = run_evaluation(well_behaved_runner)
    md = report.to_markdown()
    assert "| # | Scenario |" in md
    assert "PASS" in md
    assert "scenarios passed all checks" in report.summary()


def test_default_scenarios_are_well_formed():
    assert len(DEFAULT_SCENARIOS) >= 4
    for sc in DEFAULT_SCENARIOS:
        assert sc.name and sc.checks           # every scenario is named and checked
        assert callable(sc.make_owner)
