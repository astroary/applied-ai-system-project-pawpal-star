"""Tests for decision logging and the CarePlanner orchestrator (offline).

All file writes go to pytest's tmp_path, so these never touch the real
logs/ directory or ai_interactions.md.
"""

import json

import pytest

from care_planner import CarePlanner
from decision_log import DecisionLogger, append_interaction, build_record
from pawpal_system import Owner, Pet, Task
from retrieval import Retriever
from tests.test_critique import DRAFT_WITH_DRIFT, CRITIQUE_FIX, ScriptedLLM


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


# --- DecisionLogger -------------------------------------------------------
def test_logger_appends_jsonl_with_timestamp(tmp_path):
    logger = DecisionLogger(tmp_path / "logs" / "decisions.jsonl")
    logger.log({"owner": "Jordan", "confidence": 0.9})
    logger.log({"owner": "Sam", "confidence": 0.5})
    records = logger.read_all()
    assert len(records) == 2
    assert records[0]["owner"] == "Jordan"
    assert "timestamp" in records[0]           # stamped automatically


def test_logger_creates_missing_directory(tmp_path):
    """The log directory is created on demand."""
    path = tmp_path / "deep" / "nested" / "decisions.jsonl"
    DecisionLogger(path).log({"x": 1})
    assert path.exists()


def test_log_error_records_cause(tmp_path):
    logger = DecisionLogger(tmp_path / "decisions.jsonl")
    owner = make_owner()
    logger.log_error(owner, "please plan", ValueError("boom"))
    rec = logger.read_all()[0]
    assert "ValueError: boom" in rec["error"]


# --- CarePlanner integration ----------------------------------------------
def test_care_planner_runs_and_logs(tmp_path, retriever):
    """A full run logs exactly one record and returns the reviewed result."""
    log_path = tmp_path / "decisions.jsonl"
    interactions = tmp_path / "ai_interactions.md"
    llm = ScriptedLLM([DRAFT_WITH_DRIFT, CRITIQUE_FIX])
    planner = CarePlanner(
        retriever=retriever, llm=llm,
        logger=DecisionLogger(log_path), interactions_path=interactions,
    )

    result = planner.run(make_owner())

    assert result.revised
    records = DecisionLogger(log_path).read_all()
    assert len(records) == 1
    rec = records[0]
    assert rec["owner"] == "Jordan"
    assert rec["confidence"] == result.confidence
    assert rec["problems_after"] == []
    assert rec["sources_retrieved"]            # RAG sources captured
    # Reasoning trace was appended for the agentic stretch.
    assert interactions.exists()
    assert "Self-critique trace" in interactions.read_text()


def test_care_planner_logs_refusal_without_trace(tmp_path, retriever):
    """An unsafe request is logged as refused; no reasoning trace is written."""
    log_path = tmp_path / "decisions.jsonl"
    interactions = tmp_path / "ai_interactions.md"
    planner = CarePlanner(
        retriever=retriever, llm=ScriptedLLM([]),
        logger=DecisionLogger(log_path), interactions_path=interactions,
    )

    result = planner.run(make_owner(), request="what dosage of tylenol?")

    assert result.plan.refused
    rec = DecisionLogger(log_path).read_all()[0]
    assert rec["refused"] is True
    assert not interactions.exists()           # nothing meaningful to trace


def test_care_planner_handles_llm_failure_gracefully(tmp_path, retriever):
    """An LLM/parse failure is caught, logged, and returned as zero confidence."""
    class BoomLLM:
        model = "boom"

        def chat(self, *a, **k):
            raise __import__("llm_client").LLMError("network down")

    log_path = tmp_path / "decisions.jsonl"
    planner = CarePlanner(
        retriever=retriever, llm=BoomLLM(),
        logger=DecisionLogger(log_path), interactions_path=tmp_path / "ai.md",
    )

    result = planner.run(make_owner())
    assert result.confidence == 0.0
    assert result.plan.refused
    rec = DecisionLogger(log_path).read_all()[0]
    assert "network down" in rec["error"]


# --- Record shape ---------------------------------------------------------
def test_build_record_is_json_safe(retriever):
    llm = ScriptedLLM([DRAFT_WITH_DRIFT, CRITIQUE_FIX])
    from ai_planner import AIPlanner
    result = AIPlanner(retriever, llm=llm).plan_and_review(make_owner())
    record = build_record(make_owner(), "", result)
    json.loads(json.dumps(record))             # must serialize cleanly
    assert record["pets"][0]["species"] == "dog"
