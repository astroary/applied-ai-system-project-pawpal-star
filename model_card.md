# Model Card & Responsible-AI Reflection — PawPal+ AI Care Planner

**System:** an AI layer over a deterministic pet-care scheduler. It retrieves
pet-care knowledge (RAG), generates a grounded, cited daily plan with a Groq
`llama-3.3-70b-versatile` model, enforces guardrails, self-critiques, scores
confidence, and logs every decision.

**Intended use:** scheduling routine pet care — walks, feedings, play, grooming,
litter care, and reminders for treatments a veterinarian has already prescribed.

**Out of scope (by design):** medical diagnosis, symptom interpretation, and any
medication dosing or treatment advice. These are refused and redirected to a vet.

---

## Limitations and biases

- **Deterministic feasibility is not AI-verified.** Whether tasks fit the time
  budget is decided by the `Scheduler`, not the model. That's a strength for
  trust, but it means the AI's "improvements" are limited to explanation and
  ordering — it cannot, for example, suggest dropping a low-value task.
- **Retrieval is lexical, not semantic.** The TF-IDF retriever matches words, not
  meaning, so a query using synonyms the knowledge base doesn't contain
  ("stroll" vs. "walk") may retrieve weaker sources. Top-k retrieval and the
  groundedness guardrail reduce, but don't eliminate, this.
- **Knowledge-base bias.** The five source documents are general, English-only,
  Western pet-care norms centered on dogs and cats. Advice for other species,
  regions, or edge cases is simply absent, and the system will ground on the
  closest available (possibly inappropriate) section.
- **Confidence is a heuristic.** The score blends guardrail results with the
  model's self-rating; a plan can be confidently wrong if a flaw isn't one the
  guardrails check for.
- **Single-model, single-provider.** Behavior depends on one Groq model's
  quality and availability (though the client is swappable).

## Could the AI be misused, and how is that prevented?

- **Seeking medical/dosing advice.** The most serious misuse. Prevented by
  **input guardrails** that refuse dosing/diagnosis/prescription requests *before*
  any model call, and by an **output guardrail** that blocks a real dose (a
  number + unit, or "give <human drug>") if the model ever emits one. The
  knowledge base itself encodes the "defer to a vet" boundary.
- **Over-trusting the output.** Prevented by surfacing a **confidence score**,
  **inline citations**, and a **guardrail status** so users can see how grounded
  a plan is, plus a visible reasoning trace.
- **Silent unsafe behavior.** Prevented by the **JSONL decision log**, which
  records every refusal, guardrail outcome, and confidence score for audit.
- **Residual risk:** a determined user could rephrase to evade the refusal
  patterns. The layered defense (input + output + knowledge-base framing) lowers
  this risk but does not fully remove it; keyword patterns would benefit from a
  dedicated safety-classifier model in future work.

## What surprised me while testing reliability

The biggest surprise was that a **guardrail can fail by being too strict**, not
just too loose. My output-safety check originally blocked any text matching
"administer/prescribe … medication." When I ran the full CLI end-to-end, a
completely legitimate plan — one that simply *scheduled a vet-prescribed
medication reminder* — was refused with 0.0 confidence. The unit tests hadn't
caught it because they only tested clearly-unsafe inputs. It taught me to test
guardrails against **benign-but-similar** cases, and I narrowed the pattern to
real dosing and added a regression test. I was also (pleasantly) surprised how
reliably the **self-critique loop** fixed the model's own plan-drift — a draft
that merged two pets into one step was consistently corrected to 0 issues.

## Collaboration with AI during this project

I built this system in a guided collaboration with an AI coding assistant,
working phase by phase (RAG → planner → guardrails → self-critique → logging →
evaluation → docs). I made all the design decisions and every git commit; the
assistant wrote and explained code, ran the tests, and flagged issues.

- **A helpful suggestion:** the assistant proposed a **plan-fidelity guardrail**
  that checks every AI step against the deterministic schedule. This directly
  caught the model merging two pets into a single step — a subtle failure I would
  likely have missed by eye — and became the trigger the self-critique loop uses
  to fix such drift.
- **A flawed suggestion:** the assistant's first version of the **output-safety
  guardrail** was over-aggressive and blocked a legitimate medication *reminder*
  (it matched the words "administer medication"). It looked reasonable in review
  and passed the initial unit tests, but it broke a valid, in-scope use case that
  only surfaced when I ran the whole app. I had it narrow the rule to actual
  dosing and add a regression test. The lesson: AI-suggested safety rules still
  need adversarial *and* benign testing before I trust them.
