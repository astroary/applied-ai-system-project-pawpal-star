"""CarePlanner — the integrated entry point for the AI Care Planner.

This is the one object the UI (Streamlit / CLI) talks to. It ties the whole
pipeline together and makes logging a first-class step rather than a bolt-on:

    input guardrails -> deterministic schedule -> retrieval (RAG)
        -> LLM plan -> output guardrails -> self-critique + confidence
        -> decision log (JSONL) + reasoning trace (ai_interactions.md)

Errors from the model or parser are caught, logged with their cause, and turned
into a safe zero-confidence result so a single bad response never crashes the
app (rubric §4: logging and error handling).
"""

from ai_planner import AIPlan, AIPlanner, PlannerError
from critique import CritiqueResult
from decision_log import (
    DecisionLogger,
    INTERACTIONS_PATH,
    append_interaction,
    build_record,
)
from llm_client import LLMClient, LLMError
from retrieval import Retriever


class CarePlanner:
    """Orchestrates the full pipeline and logs every decision.

    Args:
        retriever:         a loaded Retriever (built and loaded if omitted).
        llm:               an LLM client (LLMClient() if omitted).
        logger:            a DecisionLogger (default JSONL logger if omitted).
        k:                 how many knowledge-base chunks to retrieve.
        interactions_path: where to append reasoning traces; None disables it.
    """

    def __init__(self, retriever=None, llm=None, logger=None, k: int = 4,
                 interactions_path=INTERACTIONS_PATH):
        self.planner = AIPlanner(retriever or Retriever().load(), llm=llm or LLMClient(), k=k)
        self.logger = logger or DecisionLogger()
        self.interactions_path = interactions_path

    def run(self, owner, request: str = "", max_rounds: int = 1) -> CritiqueResult:
        """Produce a reviewed, scored, logged plan for the owner.

        Always returns a CritiqueResult — on an LLM/parse failure it returns a
        zero-confidence result whose plan explains the failure, and records the
        error in the log.
        """
        try:
            result = self.planner.plan_and_review(owner, request, max_rounds=max_rounds)
        except (LLMError, PlannerError) as exc:
            self.logger.log_error(owner, request, exc)
            model = getattr(self.planner.llm, "model", "")
            failed = AIPlan(
                summary=f"Planning failed and was not shown: {type(exc).__name__}.",
                steps=[],
                model=model,
                refused=True,
                guardrails={"severity": "block", "issues": [str(exc)], "message": ""},
            )
            return CritiqueResult(
                plan=failed,
                confidence=0.0,
                assessment="Planning failed; see the decision log.",
                trace=[{"step": "error", "detail": f"{type(exc).__name__}: {exc}"}],
            )

        # Integrated logging — one audit record per decision.
        self.logger.log(build_record(owner, request, result))

        # Agentic stretch — commit the reasoning trace (skip trivial refusals).
        if self.interactions_path and not result.plan.refused:
            append_interaction(result, owner, request, path=self.interactions_path)

        return result
