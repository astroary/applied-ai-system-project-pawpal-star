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

## ✨ Features

- **Multi-pet management** — one owner can track multiple pets, each with its own task list (`Owner`, `Pet`).
- **Priority-aware daily plan** — `Scheduler.generate_plan()` fits the highest-priority tasks into the owner's time budget and explains its choices.
- **Sorting by time** — `Scheduler.sort_by_time()` returns tasks in chronological order regardless of entry order.
- **Filtering** — by completion status or pet (`filter_by_status()`, `filter_by_pet()`).
- **Conflict warnings** — `detect_conflicts()` flags tasks sharing a start time and returns a warning instead of crashing.
- **Daily / weekly recurrence** — completing a recurring task auto-creates its next occurrence (`Task.next_occurrence()`).

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

## 🎬 Demo Walkthrough

Launch the app with `streamlit run app.py`, then:

1. **Set up the owner** — enter your name and how many minutes you have for pet care today (the daily time budget the scheduler plans within).
2. **Add pets** — submit the "Add pet" form for each pet (e.g., Biscuit the dog, Mochi the cat). Each pet keeps its own task list.
3. **Add tasks** — for each pet, add care tasks with a duration, priority, scheduled time, and frequency (daily/weekly/once). The "All tasks" table updates and shows everything **sorted by time**, even when entered out of order.
4. **Generate the schedule** — click **Generate schedule**. The app:
   - shows **conflict warnings** (`st.warning`) if two tasks share a start time, or a success message if none,
   - prints a **priority-ordered daily plan** that fits your time budget and lists any tasks skipped for lack of time.

Key `Scheduler` behaviors you'll see in action: **time sorting**, **conflict warnings**, and **priority-based planning within a time budget**.

### Sample CLI output (`python main.py`)

The CLI demo prints color-coded, tabulated tables (color shown only in an interactive terminal):

```
============================================================
All tasks (sorted by time)
============================================================
╭────────┬─────────┬────────────────┬───────┬────────────┬────────╮
│ Time   │ Pet     │ Task           │ Dur   │ Priority   │ Done   │
├────────┼─────────┼────────────────┼───────┼────────────┼────────┤
│ 07:30  │ Biscuit │ Morning walk   │ 30m   │ 🔴 high    │ ⬜     │
│ 08:00  │ Biscuit │ Feeding        │ 10m   │ 🔴 high    │ ⬜     │
│ 08:00  │ Mochi   │ Feeding        │ 10m   │ 🔴 high    │ ⬜     │
│ 09:00  │ Mochi   │ Litter cleanup │ 15m   │ 🟡 medium  │ ⬜     │
│ 16:00  │ Mochi   │ Medication     │ 10m   │ 🔴 high    │ ⬜     │
│ 18:00  │ Biscuit │ Evening walk   │ 30m   │ 🟡 medium  │ ⬜     │
╰────────┴─────────┴────────────────┴───────┴────────────┴────────╯

============================================================
Conflict detection
============================================================
  ⚠️  Conflict at 08:00: Feeding (Biscuit), Feeding (Mochi)

============================================================
Next available slot (Challenge 1)
============================================================
  Earliest free 20-min slot: 08:10
  Earliest free 45-min slot: 08:10
  Earliest free 90-min slot: 09:15
```

**Screenshot or video** *(optional)*: <!-- Insert a screenshot or link to a demo video here -->

## 🧩 Optional Extensions

These build on the core project. All are exercised by `python main.py` and covered by the test suite.

### Challenge 1 — Next available slot
`Scheduler.next_available_slot(duration_minutes)` scans the day from `start_hour`, steps over already-timed tasks, and returns the earliest `"HH:MM"` gap big enough for a task of the given length (or `None` if the day is full). In the demo, a 20- or 45-minute task fits at `08:10`, but a 90-minute task is pushed to `09:15` because it can't fit the morning gap:

```
  Earliest free 20-min slot: 08:10
  Earliest free 45-min slot: 08:10
  Earliest free 90-min slot: 09:15
```

### Challenge 2 — Data persistence
`Owner.save_to_json(path)` and `Owner.load_from_json(path)` serialize the entire owner → pets → tasks tree to `data.json` and rebuild it on load. Serialization is handled by `to_dict()` / `from_dict()` on each class; `date` fields are stored as ISO strings and parsed back on load. **Workflow:** the demo saves state to `data.json` after building the schedule, then reloads it to prove the round-trip. `data.json` is git-ignored since it's regenerated at runtime. *(Files modified: `pawpal_system.py`, `main.py`, `.gitignore`.)*

### Challenge 3 — Advanced priority scheduling
`Scheduler.sort_by_priority_then_time()` sorts by priority first (high → low), then by time — so an important task scheduled later still leads the list. Note how the `16:00` Medication (high) jumps above the `09:00` Litter cleanup (medium):

```
By priority, then time:
  07:30  Morning walk    🔴 high
  08:00  Feeding         🔴 high
  08:00  Feeding         🔴 high
  16:00  Medication      🔴 high     <- late, but high priority
  09:00  Litter cleanup  🟡 medium
  18:00  Evening walk    🟡 medium
```

### Challenge 4 — Professional output formatting
The CLI uses the [`tabulate`](https://pypi.org/project/tabulate/) library (`rounded_outline` format) for bordered tables, plus emoji priority indicators (🔴/🟡/🟢) and status markers (✅/⬜). ANSI color is applied only when writing to an interactive terminal (`sys.stdout.isatty()`), so piped/redirected output stays clean. *(Library used: `tabulate`; see `task_table()` in `main.py`.)*
