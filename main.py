"""CLI demo for PawPal+ — verifies the logic layer (and extensions) in the terminal.

Run with:  python main.py
"""

import sys

from tabulate import tabulate

from pawpal_system import Owner, Pet, Task, Scheduler

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


if __name__ == "__main__":
    main()
