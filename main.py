"""Temporary CLI demo for PawPal+ — verifies the logic layer in the terminal.

Run with:  python main.py
"""

from pawpal_system import Owner, Pet, Task, Scheduler


def show(label, tasks):
    """Print a labeled list of tasks as 'time — title (pet) [priority]'."""
    print(label)
    for t in tasks:
        stamp = t.time or "--:--"
        print(f"  {stamp} — {t.title} ({t.pet_name}) [{t.priority}]")


def main() -> None:
    owner = Owner(name="Jordan", daily_minutes_available=120)

    biscuit = Pet(name="Biscuit", species="dog", breed="Golden Retriever", age=3)
    mochi = Pet(name="Mochi", species="cat", breed="Tabby", age=2)
    owner.add_pet(biscuit)
    owner.add_pet(mochi)

    # Add tasks intentionally OUT OF ORDER to prove sorting works.
    biscuit.add_task(Task("Evening walk", duration_minutes=30, priority="medium", time="18:00"))
    biscuit.add_task(Task("Morning walk", duration_minutes=30, priority="high", time="07:30"))
    biscuit.add_task(Task("Feeding", duration_minutes=10, priority="high", time="08:00"))
    mochi.add_task(Task("Feeding", duration_minutes=10, priority="high", time="08:00"))  # conflict!
    mochi.add_task(Task("Litter cleanup", duration_minutes=15, priority="medium", time="12:00"))

    scheduler = Scheduler(available_minutes=owner.daily_minutes_available)
    scheduler.load_from_owner(owner)

    print("=" * 50)
    show("Tasks sorted by time:", scheduler.sort_by_time())

    print("\n" + "=" * 50)
    show("Filtered — Biscuit's tasks only:", scheduler.filter_by_pet("Biscuit"))

    print("\n" + "=" * 50)
    show("Filtered — pending (not completed) tasks:", scheduler.filter_by_status(completed=False))

    print("\n" + "=" * 50)
    print("Conflict detection:")
    conflicts = scheduler.detect_conflicts()
    if conflicts:
        for w in conflicts:
            print(f"  ⚠️  {w}")
    else:
        print("  No conflicts.")

    print("\n" + "=" * 50)
    print("Recurring task: completing Biscuit's daily 'Morning walk'...")
    morning = biscuit.tasks[1]  # the 07:30 morning walk
    nxt = biscuit.complete_task(morning)
    print(f"  Marked complete: {morning.title} (completed={morning.completed})")
    print(f"  Auto-created next occurrence due: {nxt.due_date} (completed={nxt.completed})")


if __name__ == "__main__":
    main()
