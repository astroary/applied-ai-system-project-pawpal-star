# PawPal+ (Module 2 Project)

You are building **PawPal+**, a Streamlit app that helps a pet owner plan care tasks for their pet.

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
- Consider constraints (time available, priority, owner preferences)
- Produce a daily plan and explain why it chose that plan

Your job is to design the system first (UML), then implement the logic in Python, then connect it to the Streamlit UI.

## What you will build

Your final app should:

- Let a user enter basic owner + pet info
- Let a user add/edit tasks (duration + priority at minimum)
- Generate a daily schedule/plan based on constraints and priorities
- Display the plan clearly (and ideally explain the reasoning)
- Include tests for the most important scheduling behaviors

## Getting started

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Suggested workflow

1. Read the scenario carefully and identify requirements and edge cases.
2. Draft a UML diagram (classes, attributes, methods, relationships).
3. Convert UML into Python class stubs (no logic yet).
4. Implement scheduling logic in small increments.
5. Add tests to verify key behaviors.
6. Connect your logic to the Streamlit UI in `app.py`.
7. Refine UML so it matches what you actually built.

## 🖥️ Sample Output

Terminal output from running `python main.py`:

```
==================================================
Tasks sorted by time:
  07:30 — Morning walk (Biscuit) [high]
  08:00 — Feeding (Biscuit) [high]
  08:00 — Feeding (Mochi) [high]
  12:00 — Litter cleanup (Mochi) [medium]
  18:00 — Evening walk (Biscuit) [medium]

==================================================
Filtered — Biscuit's tasks only:
  18:00 — Evening walk (Biscuit) [medium]
  07:30 — Morning walk (Biscuit) [high]
  08:00 — Feeding (Biscuit) [high]

==================================================
Conflict detection:
  ⚠️  Conflict at 08:00: Feeding (Biscuit), Feeding (Mochi)

==================================================
Recurring task: completing Biscuit's daily 'Morning walk'...
  Marked complete: Morning walk (completed=True)
  Auto-created next occurrence due: 2026-06-24 (completed=False)
```

## 🧪 Testing PawPal+

Run the full test suite from the project root:

```bash
python -m pytest

# Run with coverage:
pytest --cov
```

**What the tests cover** (`tests/test_pawpal.py`, 12 tests):

- **Task basics** — `mark_complete()` flips status; adding a task grows the pet's count and stamps the pet's name.
- **Sorting correctness** — out-of-order tasks return in chronological `"HH:MM"` order; untimed tasks sort last.
- **Filtering** — `filter_by_status()` and `filter_by_pet()` return only matching tasks.
- **Recurrence logic** — completing a daily task queues one due tomorrow; weekly advances 7 days; a `"once"` task creates no follow-up.
- **Conflict detection** — two tasks at the same time produce exactly one warning; distinct times produce none.
- **Edge case** — an owner whose pet has no tasks yields an empty plan and no conflicts (no crash).

Sample test output:

```
collected 12 items

tests/test_pawpal.py ............                                         [100%]

============================== 12 passed in 0.02s ==============================
```

**Confidence level: ★★★★☆ (4/5)** — All core behaviors and the main edge cases pass. Docked one star because conflict detection only checks exact start times (not overlapping durations), and recurrence isn't yet tested across month/year boundaries.

## 📐 Smarter Scheduling

> Fill in once you've implemented scheduling logic.

| Feature | Method(s) | Notes |
|---------|-----------|-------|
| Task sorting | `Scheduler.sort_by_time()`, `Task.priority_rank()` | Sort by scheduled `"HH:MM"` time; `generate_plan()` orders by priority then duration |
| Filtering | `Scheduler.filter_by_status()`, `Scheduler.filter_by_pet()` | Filter by completion status or pet name |
| Conflict handling | `Scheduler.detect_conflicts()` | Flags tasks sharing an exact start time; returns warnings instead of crashing |
| Recurring tasks | `Pet.complete_task()`, `Task.next_occurrence()` | Completing a daily/weekly task auto-creates the next occurrence via `timedelta` |

## 📸 Demo Walkthrough

Describe your app in numbered steps so a reader can follow along without watching a video:

1. <!-- Describe this step -->
2. <!-- Describe this step -->
3. <!-- Describe this step -->
4. <!-- Describe this step -->
5. <!-- Add more steps as needed -->

**Screenshot or video** *(optional)*: <!-- Insert a screenshot or link to a demo video here -->
