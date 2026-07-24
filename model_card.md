# Model Card & Reflection — PawPal+ AI Care Planner

A quick honest write-up of what this system is, where it falls short, and what I
learned building it.

**What it is:** I took my Module 2 pet-care scheduler and put an AI layer on top
of it. The scheduler still decides what fits in your day; the AI (a Groq
`llama-3.3-70b` model) explains the plan, backs each step with a cited source
from a small pet-care knowledge base, refuses anything medical, double-checks its
own work, and gives a confidence score. Every decision gets logged.

**What it's for:** planning everyday pet care — walks, feedings, play, grooming,
litter, and reminders for treatments a vet already prescribed. It is **not** a
vet. It won't diagnose anything or tell you how much medicine to give, on purpose.

---

## Limitations and biases

I want to be upfront that this system is narrower than it might look.

The AI never actually decides whether your day is feasible — my original
`Scheduler` does that math, and the AI only explains and reorders around it. I
did that deliberately so the model can't hallucinate a broken schedule, but it
does mean the AI can't do something genuinely smart like "you're overloaded,
drop the low-priority task."

The retrieval is keyword-based (TF-IDF), so it matches words, not meaning. If I
ask about a "stroll" and my notes only say "walk," it might miss the right
source. And the knowledge base itself is just five short documents of general,
English, fairly Western dog-and-cat advice — so anything about other species,
other regions, or unusual situations simply isn't there, and the system will
reach for the closest thing it has, which won't always be right.

The confidence score is a helpful signal, not truth. It mixes my guardrail
checks with the model's own self-rating, so a plan can still be confidently wrong
if the mistake isn't one my checks look for. And all of this rides on one model
from one provider (though I did wrap it so it's easy to swap).

## Could this be misused, and how do I prevent it?

The misuse I worried about most is someone treating it like a vet — asking how
much ibuprofen to give their dog, for example. That's genuinely dangerous, so I
block it in two places: the input guardrail refuses dosing, diagnosis, and
prescription questions *before* the model is even called, and a second check on
the output catches an actual dose (a number plus a unit, or "give <human drug>")
if the model ever slips one through. The knowledge base reinforces this by
literally telling the assistant to defer to a vet.

The other risk is quieter: people over-trusting whatever the AI says. I tried to
push against that by always showing citations, a confidence score, and a
guardrail status, plus a reasoning trace you can open up — so it reads as "here's
my reasoning, check it" rather than "here's the answer." And because every
decision (including refusals) is written to a JSONL log, nothing it does is
invisible.

I'm not pretending this is airtight. A determined person could reword a question
to slip past my keyword patterns. The layered approach lowers the risk, but a
real safety classifier would do better, and that's where I'd take it next.

## What surprised me while testing reliability

The thing I did not see coming: a guardrail can fail by being *too strict*.

My output-safety check originally blocked any text like "administer medication."
That sounded reasonable, and it passed all my unit tests — because I'd only
tested obviously-unsafe inputs. Then I ran the whole app end-to-end for the first
time and a perfectly normal plan came back **refused, confidence 0.0**. The only
"crime" was that it scheduled a *vet-prescribed medication reminder* and used the
word "administer." A legitimate, in-scope feature was being killed by my own
safety rule.

That flipped how I think about guardrails. I'd been testing them like a
prosecutor — only throwing bad inputs at them — when I also needed to test them
like a defense attorney, with benign-but-similar cases. I narrowed the rule to
real dosing and added a regression test for the reminder case.

The happier surprise was the self-critique loop. On a two-pet plan the model kept
smushing both pets into one step, and the loop caught it and rebuilt the plan
correctly every time (2 issues → 0). Watching the AI fix its own mistake was the
moment the "agentic" part actually clicked for me.

## My collaboration with AI (one helpful, one flawed)

I built this with an AI coding assistant, going phase by phase — RAG, then the
planner, guardrails, self-critique, logging, evaluation, and docs. I made the
design calls and every commit myself; the assistant wrote code, ran the tests,
and pointed out problems as we went.

**Where it really helped:** it suggested a *plan-fidelity* guardrail — a check
that every step the AI produces actually matches a task in the deterministic
schedule. I hadn't thought to verify that, and it immediately caught the model
merging two pets into one step. That single idea ended up being the backbone of
how the self-critique loop knows what to fix.

**Where it was wrong:** the assistant's first version of the output-safety
guardrail was the over-aggressive one I described above — it looked fine in
review and passed the tests, but it broke a real, valid use case (the medication
reminder) that only showed up when I ran the app for real. It was a good reminder
that I can't just accept AI-written safety logic because it looks careful; I have
to test it against the normal cases too, not only the scary ones.

Biggest takeaway: the AI was great for moving fast and catching things I'd miss,
but the judgment about *what "safe" and "correct" actually mean here* had to stay
with me.
