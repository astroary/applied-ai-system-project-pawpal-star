"""Guardrails — safety and reliability checks around the AI planner.

Three layers protect the system:

Input (before any model call):
    * validate the owner/pets/tasks are plannable at all;
    * refuse unsafe requests — medication dosing, diagnosis, treatment — and
      redirect to a veterinarian (grounded in health_and_safety.md).

Output (after the model replies):
    * groundedness — every [S#] the plan cites must be a source that was
      actually retrieved (no invented citations);
    * plan fidelity — every (pet, task) the AI lists must exist in the
      deterministic scheduler's plan (catches drift like assigning one pet's
      task to another, or inventing tasks);
    * output safety — the reply must not contain dosing/treatment advice.

Each check returns a :class:`GuardrailResult` with a severity so the caller (and
the Phase 4 self-critique / Phase 5 logger) can decide what to do: ``block``
stops the plan from being shown, ``warn`` lowers confidence but is surfaced,
``ok`` passes clean.
"""

import re
from dataclasses import dataclass, field

# The single message shown whenever an unsafe request is refused.
REFUSAL_MESSAGE = (
    "I can't help with medical, diagnostic, or medication/dosing questions — "
    "those depend on your pet's exact health and can be dangerous if wrong. "
    "Please contact your veterinarian or a pet poison hotline. I can still help "
    "you schedule walks, feedings, play, grooming, and vet-prescribed reminders."
)

# Requests that must be refused outright. These target dosing/diagnosis INTENT,
# not benign scheduling — "Medication reminder" is allowed, "how much ibuprofen"
# is not.
UNSAFE_INPUT_PATTERNS = [
    re.compile(r"\b(dose|dosage|dosing|overdose)\b", re.I),
    re.compile(r"\bhow\s+much\b.*\b(give|medicine|medication|drug|pill|meds?)\b", re.I),
    re.compile(r"\b\d+\s*(mg|ml|milligram|milliliter|cc)\b", re.I),
    re.compile(r"\bprescri\w+", re.I),
    re.compile(r"\bdiagnos\w+", re.I),
    re.compile(
        r"\b(ibuprofen|tylenol|acetaminophen|aspirin|benadryl|paracetamol|"
        r"naproxen|advil)\b",
        re.I,
    ),
    re.compile(r"\bis it (safe|ok|okay) to give\b.*\b(human|medicine|medication)\b", re.I),
]

# Dosing/treatment advice that must never appear in the model's OUTPUT.
UNSAFE_OUTPUT_PATTERNS = [
    re.compile(r"\b\d+\s*(mg|ml|milligram|milliliter|cc)\b", re.I),
    re.compile(r"\bgive\b.*\b(ibuprofen|tylenol|acetaminophen|aspirin|benadryl)\b", re.I),
    re.compile(r"\b(administer|prescribe)\b.*\b(dose|medication|drug|pill)\b", re.I),
]

# Matches citation labels like S1, S2 — including inside "[S1, S3, S4]".
_CITATION_RE = re.compile(r"S(\d+)", re.I)


@dataclass
class GuardrailResult:
    """Outcome of one or more guardrail checks.

    Attributes:
        severity: "ok" (clean), "warn" (surface but allow), or "block" (stop).
        issues:   human-readable descriptions of every problem found.
        message:  user-facing text when blocked (e.g. the refusal message).
    """

    severity: str = "ok"
    issues: list[str] = field(default_factory=list)
    message: str = ""

    @property
    def passed(self) -> bool:
        """True unless something blocked the plan."""
        return self.severity != "block"

    @property
    def blocked(self) -> bool:
        return self.severity == "block"

    def to_dict(self) -> dict:
        """JSON-safe form for the decision log (Phase 5)."""
        return {"severity": self.severity, "issues": self.issues, "message": self.message}


# --- Input guardrails -----------------------------------------------------
def validate_input(owner, request: str = "") -> GuardrailResult:
    """Check the owner/tasks are plannable and the request is safe.

    Scans the free-text ``request`` and every task title for unsafe intent.
    Returns a ``block`` result (with the refusal message) on anything unsafe,
    a ``warn`` if there's simply nothing to plan, otherwise ``ok``.
    """
    issues: list[str] = []

    # Structural validity — is there anything to plan?
    if owner.daily_minutes_available <= 0:
        issues.append("Daily minutes available must be greater than zero.")
    if not owner.pets:
        issues.append("No pets on file — add a pet before planning.")
    elif not owner.all_tasks():
        issues.append("No tasks on file — add at least one task to plan.")

    # Safety — refuse dosing/diagnosis/treatment requests.
    texts = [request] + [t.title for t in owner.all_tasks()]
    for text in texts:
        for pattern in UNSAFE_INPUT_PATTERNS:
            if pattern.search(text):
                return GuardrailResult(
                    severity="block",
                    issues=[f"Unsafe request detected: {text!r} matched {pattern.pattern!r}"],
                    message=REFUSAL_MESSAGE,
                )

    if issues:
        return GuardrailResult(severity="warn", issues=issues)
    return GuardrailResult(severity="ok")


# --- Output guardrails ----------------------------------------------------
def extract_citations(texts: list[str]) -> set[str]:
    """Return the set of citation labels (e.g. {"S1", "S3"}) found in texts."""
    labels: set[str] = set()
    for text in texts:
        for num in _CITATION_RE.findall(text or ""):
            labels.add(f"S{num}")
    return labels


def _scheduled_pairs(scheduler_plan: list[dict]) -> set[tuple[str, str]]:
    """Normalized (pet, task) pairs the deterministic scheduler actually placed."""
    pairs = set()
    for slot in scheduler_plan:
        task = slot["task"]
        pairs.add((task.pet_name.strip().lower(), task.title.strip().lower()))
    return pairs


def verify_output(ai_plan, retrieved_chunks: list, scheduler_plan: list[dict]) -> GuardrailResult:
    """Check the AI plan for grounded citations, plan fidelity, and safety.

    Args:
        ai_plan:          the :class:`ai_planner.AIPlan` to verify.
        retrieved_chunks: the chunks passed to the model (defines valid S# labels).
        scheduler_plan:   the deterministic plan (list of {"time", "task"} slots).

    Returns a ``block`` result if the output contains unsafe advice, otherwise
    ``warn`` if any citation is ungrounded or any step drifts from the schedule,
    otherwise ``ok``.
    """
    issues: list[str] = []

    # 1. Groundedness — cited labels must be within the retrieved set S1..Sn.
    valid_labels = {f"S{i}" for i in range(1, len(retrieved_chunks) + 1)}
    cited_texts = [ai_plan.summary, ai_plan.notes]
    for step in ai_plan.steps:
        cited_texts.append(step.get("rationale", ""))
        cited_texts.extend(step.get("sources", []) or [])
    cited_texts.extend(ai_plan.sources_used or [])
    ungrounded = extract_citations(cited_texts) - valid_labels
    for label in sorted(ungrounded):
        issues.append(f"Ungrounded citation {label}: not among retrieved sources.")

    # 2. Plan fidelity — every AI step must map to a scheduled (pet, task).
    scheduled = _scheduled_pairs(scheduler_plan)
    for step in ai_plan.steps:
        pair = (step.get("pet", "").strip().lower(), step.get("task", "").strip().lower())
        if pair not in scheduled:
            issues.append(
                f"Plan drift: step '{step.get('task', '?')}' for "
                f"'{step.get('pet', '?')}' is not in the deterministic schedule."
            )

    # 3. Output safety — no dosing/treatment advice should ever be surfaced.
    output_text = " ".join(
        [ai_plan.summary, ai_plan.notes] + [s.get("rationale", "") for s in ai_plan.steps]
    )
    for pattern in UNSAFE_OUTPUT_PATTERNS:
        if pattern.search(output_text):
            return GuardrailResult(
                severity="block",
                issues=issues + [f"Unsafe advice in output: matched {pattern.pattern!r}"],
                message=REFUSAL_MESSAGE,
            )

    return GuardrailResult(severity="warn" if issues else "ok", issues=issues)
