# AI Interactions Log

> **Stretch features only.** Only fill in the sections that apply to stretch features you attempted. If you did not attempt a stretch feature, leave its section blank or delete it. This file is not required for the core project.

---

## Agent Workflow (SF7)

> Document your experience using an AI agent (e.g., Cursor Agent, Claude, Copilot) to make multi-step changes autonomously.

**What task did you give the agent?**

I asked the agent to implement the four optional extensions on top of the finished core project: a "next available slot" algorithm (Challenge 1), JSON data persistence (Challenge 2), priority-based scheduling (Challenge 3), and professional CLI output formatting (Challenge 4).

**What did the agent do?**

Working across multiple files in one pass, the agent:

- **`pawpal_system.py`** — added `Scheduler.next_available_slot()` and `sort_by_priority_then_time()`; added `to_dict()`/`from_dict()` to `Task`, `Pet`, and `Owner`, plus `Owner.save_to_json()` / `load_from_json()` (with ISO-string date handling).
- **`main.py`** — rebuilt the demo to showcase each extension and added a `tabulate`-based, emoji/color-coded `task_table()` renderer.
- **`tests/test_pawpal.py`** — added tests for priority sorting, next-available-slot (including the day-full edge case), and a JSON save/load round-trip. Final suite: 16 tests passing.
- **`requirements.txt`** — added `tabulate`; **`.gitignore`** — ignored the runtime `data.json`.
- **`README.md`** — documented all four extensions with CLI output examples.

It also ran `python main.py` and `pytest` after each change to verify the code worked.

**What did you have to verify or fix manually?**

- The first demo data didn't actually *demonstrate* the new features — priority sort looked identical to time sort, and every slot size returned the same time. I had the agent rework the sample data (a late high-priority task + a tighter morning schedule) so the output visibly proves the algorithms.
- The color-coded table printed raw ANSI escape codes when piped. I had it gate color on `sys.stdout.isatty()` so redirected/documented output stays clean.
- I confirmed the persistence round-trip preserves `date` fields (not just strings) by checking `due_date` in a test rather than trusting the demo print.

---

## Prompt Comparison (SF11)

> Compare two different prompts (or two different models) on the same task.

| | Option A | Option B |
|-|----------|----------|
| **Model / tool used** | | |
| **Prompt** | | |
| **Response summary** | | |
| **What was useful** | | |
| **Problems noticed** | | |
| **Decision** | | |

**Which approach did you use in your final implementation and why?**

<!-- Your conclusion -->
