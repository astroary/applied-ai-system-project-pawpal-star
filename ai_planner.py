"""AI planning layer — turns the deterministic schedule plus retrieved pet-care
knowledge into a grounded, explained care plan with citations.

Design principle: the AI never overrides the deterministic Scheduler. The
Scheduler decides what fits the time budget and what conflicts; the LLM adds
rationale and grounds each recommendation in the retrieved knowledge base,
citing sources as [S1], [S2], .... Guardrails (Phase 3) and a self-critique loop
(Phase 4) build on top of the structured output produced here.

The planner depends only on the small ``chat(system, user)`` surface of
:class:`llm_client.LLMClient`, so tests inject a fake LLM and run offline.
"""

import json
from dataclasses import dataclass, field

from guardrails import validate_input, verify_output
from llm_client import LLMClient
from pawpal_system import Owner, Scheduler
from retrieval import Retriever

SYSTEM_PROMPT = """You are PawPal+, a careful and responsible pet-care \
scheduling assistant.

You will be given (a) an owner's time-boxed DAILY PLAN produced by a \
deterministic scheduler and (b) numbered SOURCES from a pet-care knowledge base.

Follow these rules strictly:
1. Keep the scheduler's task selection and times. You may explain and lightly \
reorder within the plan, but do NOT add tasks that were not scheduled or change \
the total time budget.
2. Ground every recommendation in the SOURCES and cite them inline like [S1]. \
Do not state facts that are not supported by the SOURCES.
3. NEVER provide medical, diagnostic, or medication/dosing advice. If the input \
implies such a request, do not answer it — note that it must go to a \
veterinarian.
4. Respond with ONLY a single valid JSON object, no prose before or after, no \
markdown code fences.

The JSON must match this schema exactly:
{
  "summary": "one or two sentence overview of the day's plan",
  "steps": [
    {
      "time": "HH:MM",
      "pet": "pet name",
      "task": "task title",
      "rationale": "why, grounded in the sources, with [S#] citations",
      "sources": ["S1"]
    }
  ],
  "notes": "optional extra guidance, still grounded and cited",
  "sources_used": ["S1", "S2"]
}"""


class PlannerError(RuntimeError):
    """Raised when the model's response cannot be parsed into a plan."""


@dataclass
class AIPlan:
    """A structured, grounded care plan returned by the AI planner."""

    summary: str
    steps: list[dict]
    notes: str = ""
    sources_used: list[str] = field(default_factory=list)
    model: str = ""
    raw: str = ""  # the raw model text, kept for logging/auditing
    refused: bool = False  # True when guardrails blocked input or output
    guardrails: dict = field(default_factory=dict)  # verification result

    def to_dict(self) -> dict:
        """Return a JSON-safe dict (used by the decision log in Phase 5)."""
        return {
            "summary": self.summary,
            "steps": self.steps,
            "notes": self.notes,
            "sources_used": self.sources_used,
            "model": self.model,
            "refused": self.refused,
            "guardrails": self.guardrails,
        }


class AIPlanner:
    """Orchestrates retrieval + deterministic scheduling + LLM grounding.

    Args:
        retriever: a loaded :class:`retrieval.Retriever`.
        llm:       any object with ``chat(system, user)``; defaults to LLMClient.
        k:         how many knowledge-base chunks to retrieve for grounding.
    """

    def __init__(self, retriever: Retriever, llm=None, k: int = 4):
        self.retriever = retriever
        self.llm = llm or LLMClient()
        self.k = k

    # --- Prompt construction ---------------------------------------------
    @staticmethod
    def build_query(owner: Owner) -> str:
        """Derive a retrieval query from the owner's pets and tasks.

        Combines each pet's species with its task titles so the retriever pulls
        the sections most relevant to what actually needs scheduling.
        """
        parts: list[str] = []
        for pet in owner.pets:
            parts.append(pet.species)
            parts.extend(task.title for task in pet.tasks)
        parts.append("daily care routine schedule")
        return " ".join(parts)

    def build_user_prompt(self, owner: Owner, base_plan: str, context: str) -> str:
        """Assemble the user-turn prompt from owner context, plan, and sources."""
        pets = ", ".join(
            f"{p.name} ({p.species}" + (f", {p.breed}" if p.breed else "") + ")"
            for p in owner.pets
        ) or "no pets on file"
        return (
            f"OWNER: {owner.name}, ~{owner.daily_minutes_available} minutes "
            f"available today.\n"
            f"PETS: {pets}.\n\n"
            f"DAILY PLAN (from the deterministic scheduler — keep these tasks "
            f"and times):\n{base_plan}\n\n"
            f"SOURCES:\n{context}\n\n"
            f"Produce the grounded plan as JSON per the schema."
        )

    # --- Response parsing -------------------------------------------------
    @staticmethod
    def _parse(raw: str) -> dict:
        """Extract the JSON object from the model's reply, tolerating fences.

        Strips ```json fences and any stray prose by slicing from the first
        ``{`` to the last ``}``. Raises PlannerError if nothing parses.
        """
        text = raw.strip()
        if text.startswith("```"):
            # drop the opening fence line and any closing fence
            text = text.split("\n", 1)[-1]
            text = text.rsplit("```", 1)[0]
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise PlannerError(f"No JSON object found in model reply: {raw[:200]!r}")
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise PlannerError(f"Invalid JSON in model reply: {exc}") from exc

    # --- Public API -------------------------------------------------------
    def _refuse(self, check) -> AIPlan:
        """Build a refused AIPlan from a blocking guardrail result."""
        return AIPlan(
            summary=check.message,
            steps=[],
            model=getattr(self.llm, "model", ""),
            refused=True,
            guardrails=check.to_dict(),
        )

    def _generate(self, owner: Owner):
        """Schedule -> retrieve -> LLM -> parse -> output guardrails.

        Assumes input has already been validated. Returns a tuple of
        ``(plan, chunks, scheduler_plan)`` so a critique step can re-verify the
        revised plan against the very same sources and schedule.
        """
        scheduler = Scheduler(available_minutes=owner.daily_minutes_available)
        scheduler.load_from_owner(owner)
        base_plan = scheduler.explain_plan()
        scheduler_plan = scheduler.generate_plan()

        chunks = self.retriever.search(self.build_query(owner), k=self.k)
        context = Retriever.format_context(chunks)

        raw = self.llm.chat(SYSTEM_PROMPT, self.build_user_prompt(owner, base_plan, context))
        data = self._parse(raw)
        plan = AIPlan(
            summary=data.get("summary", ""),
            steps=data.get("steps", []),
            notes=data.get("notes", ""),
            sources_used=data.get("sources_used", []),
            model=getattr(self.llm, "model", ""),
            raw=raw,
        )

        output_check = verify_output(plan, chunks, scheduler_plan)
        plan.guardrails = output_check.to_dict()
        if output_check.blocked:
            plan.refused = True
            plan.summary = output_check.message
            plan.steps = []
        return plan, chunks, scheduler_plan

    def plan(self, owner: Owner, request: str = "") -> AIPlan:
        """Build a grounded, guardrailed AI plan for the owner's pets and tasks.

        Flow: input guardrails -> deterministic schedule -> retrieval -> LLM ->
        output guardrails. Unsafe input is refused *before* any model call, and
        the returned plan carries its output-verification result in ``guardrails``.
        The optional ``request`` is a free-text owner question, also screened.

        Raises PlannerError if a (non-refused) response can't be parsed, and
        LLMError if the model call itself fails.
        """
        input_check = validate_input(owner, request)
        if input_check.blocked:
            return self._refuse(input_check)
        plan, _chunks, _scheduler_plan = self._generate(owner)
        return plan

    def plan_and_review(self, owner: Owner, request: str = "", max_rounds: int = 1):
        """Plan, then run the self-critique loop to review, revise, and score it.

        Returns a :class:`critique.CritiqueResult` (which embeds the final plan
        and its confidence). Unsafe input is refused with no model call.
        """
        # Local import avoids a circular dependency (critique imports AIPlan).
        from critique import CritiqueResult, self_critique

        input_check = validate_input(owner, request)
        if input_check.blocked:
            return CritiqueResult.refused(self._refuse(input_check))
        plan, chunks, scheduler_plan = self._generate(owner)
        return self_critique(self.llm, plan, chunks, scheduler_plan, max_rounds=max_rounds)
