"""Self-critique loop and confidence scoring — the agentic reliability layer.

After the planner produces a grounded plan, this module runs a second reasoning
step: the model reviews its own plan against the *automated* guardrail findings
(ungrounded citations, drift from the deterministic schedule), proposes a revised
plan, and rates its confidence. The revision is only accepted if re-verification
shows it is safe and no worse than the original — the AI cannot make things worse.

A final confidence score blends two signals:
    * structural  — how many guardrail issues remain (objective);
    * self-rated  — the model's own 0..1 confidence (subjective).

Every step is recorded in a reasoning ``trace`` so it can be written to
``ai_interactions.md`` (the agentic-workflow stretch feature).
"""

from dataclasses import dataclass, field

from ai_planner import AIPlan, AIPlanner, PlannerError
from guardrails import verify_output
from llm_client import LLMError
from retrieval import Retriever

CRITIQUE_SYSTEM = """You are a meticulous reviewer of pet-care day plans. You \
are given a DRAFT PLAN (JSON), the AUTOMATED CHECKS that flagged problems with \
it, the deterministic SCHEDULE it must match, and the SOURCES it may cite.

Your job:
1. Judge whether the draft is grounded (only cites the given sources), faithful \
(every step's pet+task appears in the SCHEDULE exactly), and safe (no medical, \
diagnostic, or medication/dosing advice).
2. Fix every problem in a revised plan. Use the exact pet names and task titles \
from the SCHEDULE — do not merge pets or invent tasks. Cite only real sources.
3. Rate your confidence in the revised plan from 0.0 to 1.0.

Respond with ONLY a single valid JSON object, no prose, no code fences:
{
  "confidence": 0.0,
  "assessment": "one or two sentences on the plan's reliability",
  "problems": ["each problem you found and fixed"],
  "revised_plan": {
    "summary": "...",
    "steps": [
      {"time": "HH:MM", "pet": "...", "task": "...",
       "rationale": "grounded, with [S#] citations", "sources": ["S1"]}
    ],
    "notes": "...",
    "sources_used": ["S1"]
  }
}"""


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _to_float(value, default: float) -> float:
    """Coerce a model-supplied confidence into a float, falling back safely."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def compute_confidence(model_confidence: float, issues: list, blocked: bool) -> float:
    """Blend structural reliability with the model's self-rating into 0..1.

    A blocked plan scores 0.0. Otherwise each remaining guardrail issue costs
    0.2 of the structural score, which is then weighted 60/40 against the
    model's own confidence.
    """
    if blocked:
        return 0.0
    structural = max(0.0, 1.0 - 0.2 * len(issues))
    return round(0.6 * structural + 0.4 * _clamp(model_confidence), 2)


@dataclass
class CritiqueResult:
    """The outcome of the self-critique loop, embedding the final plan."""

    plan: AIPlan
    confidence: float
    assessment: str = ""
    problems_before: list[str] = field(default_factory=list)
    problems_after: list[str] = field(default_factory=list)
    revised: bool = False
    model_self_confidence: float = 0.0
    sources: list[str] = field(default_factory=list)  # citations of retrieved chunks
    trace: list[dict] = field(default_factory=list)

    @classmethod
    def refused(cls, plan: AIPlan) -> "CritiqueResult":
        """A short-circuit result for a refused (unsafe/unplannable) plan."""
        return cls(
            plan=plan,
            confidence=0.0,
            assessment="Refused: unsafe or unplannable input.",
            trace=[{"step": "refuse", "detail": plan.summary}],
        )

    def to_dict(self) -> dict:
        """JSON-safe form for the decision log (Phase 5)."""
        return {
            "confidence": self.confidence,
            "assessment": self.assessment,
            "problems_before": self.problems_before,
            "problems_after": self.problems_after,
            "revised": self.revised,
            "model_self_confidence": self.model_self_confidence,
            "sources": self.sources,
            "plan": self.plan.to_dict(),
        }

    def to_markdown(self) -> str:
        """Render the reasoning trace as Markdown for ai_interactions.md."""
        lines = [
            f"### Self-critique trace (confidence {self.confidence:.2f})",
            f"- **Assessment:** {self.assessment or '—'}",
            f"- **Revised:** {'yes' if self.revised else 'no'}",
            f"- **Issues before → after:** "
            f"{len(self.problems_before)} → {len(self.problems_after)}",
            "",
            "| Step | Detail |",
            "| --- | --- |",
        ]
        for entry in self.trace:
            step = entry.get("step", "")
            detail = entry.get("detail") or entry.get("assessment") or ""
            if entry.get("issues"):
                detail = f"{detail} (issues: {len(entry['issues'])})".strip()
            if "confidence" in entry:
                detail = f"{detail} confidence={entry['confidence']}".strip()
            lines.append(f"| {step} | {str(detail).replace(chr(10), ' ')[:200]} |")
        return "\n".join(lines)


def _format_schedule(scheduler_plan: list[dict]) -> str:
    """Render the deterministic plan as lines the reviewer must match."""
    if not scheduler_plan:
        return "(empty schedule)"
    return "\n".join(
        f"{slot['time']}  {slot['task'].pet_name} — {slot['task'].title}"
        for slot in scheduler_plan
    )


def build_critique_prompt(plan: AIPlan, issues: list[str], context: str, schedule: str) -> str:
    """Assemble the reviewer's user-turn prompt."""
    checks = "\n".join(f"- {i}" for i in issues) if issues else "- (no automated issues found)"
    draft = {
        "summary": plan.summary,
        "steps": plan.steps,
        "notes": plan.notes,
        "sources_used": plan.sources_used,
    }
    import json

    return (
        f"DRAFT PLAN:\n{json.dumps(draft, indent=2)}\n\n"
        f"AUTOMATED CHECKS:\n{checks}\n\n"
        f"SCHEDULE (revised plan must match these pet+task pairs exactly):\n{schedule}\n\n"
        f"SOURCES:\n{context}\n\n"
        f"Review and return the corrected plan as JSON per the schema."
    )


def self_critique(llm, plan: AIPlan, chunks: list, scheduler_plan: list[dict],
                  max_rounds: int = 1) -> CritiqueResult:
    """Review, revise, and score a plan. Returns a :class:`CritiqueResult`.

    Never lets a revision make the plan worse or unsafe, and degrades gracefully
    (keeps the original plan) if the critique call fails or can't be parsed.
    """
    if plan.refused:
        return CritiqueResult.refused(plan)

    before = verify_output(plan, chunks, scheduler_plan)
    trace: list[dict] = [
        {"step": "generate", "detail": plan.summary, "issues": before.issues}
    ]
    context = Retriever.format_context(chunks)
    schedule = _format_schedule(scheduler_plan)

    current = plan
    current_issues = before.issues
    model_conf = 0.7  # neutral prior if the model gives no usable rating
    assessment = ""

    for _ in range(max_rounds):
        prompt = build_critique_prompt(current, current_issues, context, schedule)
        try:
            raw = llm.chat(CRITIQUE_SYSTEM, prompt)
            data = AIPlanner._parse(raw)
        except (PlannerError, LLMError) as exc:
            # Error handling (rubric §4): keep the last good plan, note the failure.
            trace.append({"step": "critique_error", "detail": str(exc)})
            break

        model_conf = _clamp(_to_float(data.get("confidence"), 0.7))
        assessment = data.get("assessment", "")
        trace.append({
            "step": "critique",
            "assessment": assessment,
            "problems": data.get("problems", []) or [],
            "confidence": model_conf,
        })

        revised_data = data.get("revised_plan") or {}
        if not revised_data:
            trace.append({"step": "revise", "detail": "no revision proposed"})
            break

        revised = AIPlan(
            summary=revised_data.get("summary", ""),
            steps=revised_data.get("steps", []),
            notes=revised_data.get("notes", ""),
            sources_used=revised_data.get("sources_used", []),
            model=plan.model,
            raw=raw,
        )
        rcheck = verify_output(revised, chunks, scheduler_plan)
        revised.guardrails = rcheck.to_dict()
        trace.append({"step": "revise", "detail": revised.summary, "issues": rcheck.issues})

        # Accept only if the revision is safe and STRICTLY reduces the issue
        # count — never let the AI churn or make the plan worse.
        if not rcheck.blocked and len(rcheck.issues) < len(current_issues):
            current, current_issues = revised, rcheck.issues
            if not current_issues:
                break  # clean — nothing left to fix
        else:
            trace.append({"step": "reject_revision",
                          "detail": "revision unsafe or not an improvement; kept previous"})
            break

    final = verify_output(current, chunks, scheduler_plan)
    confidence = compute_confidence(model_conf, final.issues, final.blocked)
    trace.append({"step": "score", "confidence": confidence, "issues": final.issues})

    return CritiqueResult(
        plan=current,
        confidence=confidence,
        assessment=assessment,
        problems_before=before.issues,
        problems_after=final.issues,
        revised=(current is not plan),
        model_self_confidence=model_conf,
        sources=[c.citation() for c in chunks],
        trace=trace,
    )
