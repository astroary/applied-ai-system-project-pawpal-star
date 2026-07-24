"""CLI demo for PawPal+ — verifies the logic layer (and extensions) in the terminal.

Run with:  python main.py
"""

import os
import sys

from tabulate import tabulate

from pawpal_system import Owner, Pet, Task, Scheduler
# Project 4: the full AI layer, behind one orchestrator.
from care_planner import CarePlanner

# Challenge 4: color-coded, emoji status indicators for terminal output.
# Color is only emitted to an interactive terminal so piped output stays clean.
PRIORITY_EMOJI = {"high": "🔴", "medium": "🟡", "low": "🟢"}
ANSI = {"high": "\033[91m", "medium": "\033[93m", "low": "\033[92m", "reset": "\033[0m"}
USE_COLOR = sys.stdout.isatty()


def task_table(tasks) -> str:
    """Render tasks as a tabulated, color-coded table (Challenge 4)."""
    rows = []
    for t in tasks:
        color = ANSI[t.priority] if USE_COLOR else ""
        reset = ANSI["reset"] if USE_COLOR else ""
        rows.append(
            [
                t.time or "—",
                t.pet_name,
                t.title,
                f"{t.duration_minutes}m",
                f"{color}{PRIORITY_EMOJI[t.priority]} {t.priority}{reset}",
                "✅" if t.completed else "⬜",
            ]
        )
    headers = ["Time", "Pet", "Task", "Dur", "Priority", "Done"]
    return tabulate(rows, headers=headers, tablefmt="rounded_outline")


def banner(text: str) -> None:
    print("\n" + "=" * 60 + f"\n{text}\n" + "=" * 60)


def ai_demo(owner: Owner) -> None:
    """Project 4: run the AI Care Planner and show a grounded plan + a refusal."""
    banner("AI Care Plan (Project 4)")
    if not os.environ.get("GROQ_API_KEY"):
        print("  (Set GROQ_API_KEY in .env to run the AI planner — skipping.)")
        return

    planner = CarePlanner()
    result = planner.run(owner)
    print(f"  Confidence: {result.confidence:.2f}   Revised: {result.revised}   "
          f"Guardrails: {result.plan.guardrails.get('severity', '—')}")
    print(f"  Sources retrieved: {', '.join(result.sources)}\n")
    print(f"  {result.plan.summary}\n")
    rows = [
        [s.get("time", "—"), s.get("pet", ""), s.get("task", ""), s.get("rationale", "")]
        for s in result.plan.steps
    ]
    print(tabulate(
        rows,
        headers=["Time", "Pet", "Task", "Why (grounded in sources)"],
        tablefmt="rounded_outline",
        maxcolwidths=[6, 10, 16, 58],
    ))

    banner("Guardrail demo: an unsafe request is refused (no plan produced)")
    refusal = planner.run(owner, request="How much ibuprofen can I give Biscuit?")
    print(f"  refused = {refusal.plan.refused}")
    print(f"  {refusal.plan.summary}")


def main() -> None:
    owner = Owner(name="Jordan", daily_minutes_available=120)

    biscuit = Pet(name="Biscuit", species="dog", breed="Golden Retriever", age=3)
    mochi = Pet(name="Mochi", species="cat", breed="Tabby", age=2)
    owner.add_pet(biscuit)
    owner.add_pet(mochi)

    # Added out of order, on purpose, to show sorting works.
    biscuit.add_task(Task("Evening walk", 30, priority="medium", time="18:00"))
    biscuit.add_task(Task("Morning walk", 30, priority="high", time="07:30"))
    biscuit.add_task(Task("Feeding", 10, priority="high", time="08:00"))
    mochi.add_task(Task("Feeding", 10, priority="high", time="08:00"))  # conflict!
    mochi.add_task(Task("Litter cleanup", 15, priority="medium", time="09:00"))
    mochi.add_task(Task("Medication", 10, priority="high", time="16:00"))  # late but high

    scheduler = Scheduler(available_minutes=owner.daily_minutes_available)
    scheduler.load_from_owner(owner)

    # Challenge 4: professional table output.
    banner("All tasks (sorted by time)")
    print(task_table(scheduler.sort_by_time()))

    # Challenge 3: priority-first ordering.
    banner("Sorted by PRIORITY, then time (Challenge 3)")
    print(task_table(scheduler.sort_by_priority_then_time()))

    # Conflict detection.
    banner("Conflict detection")
    conflicts = scheduler.detect_conflicts()
    print("\n".join(f"  ⚠️  {w}" for w in conflicts) if conflicts else "  No conflicts.")

    # Challenge 1: next available slot.
    banner("Next available slot (Challenge 1)")
    for minutes in (20, 45, 90):
        slot = scheduler.next_available_slot(minutes)
        print(f"  Earliest free {minutes}-min slot: {slot or 'no room left today'}")

    # Challenge 2: persistence round-trip.
    banner("Persistence: save -> load (Challenge 2)")
    owner.save_to_json("data.json")
    reloaded = Owner.load_from_json("data.json")
    print(f"  Saved to data.json, reloaded owner '{reloaded.name}' "
          f"with {len(reloaded.pets)} pets and {len(reloaded.all_tasks())} tasks.")

    # Project 4: layer the AI Care Planner on top of the deterministic core.
    ai_demo(owner)


if __name__ == "__main__":
    main()
