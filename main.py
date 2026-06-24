"""Temporary CLI demo for PawPal+ — verifies the logic layer in the terminal.

Run with:  python main.py
"""

from pawpal_system import Owner, Pet, Task, Scheduler


def main() -> None:
    # 1. Set up an owner with a daily time budget.
    owner = Owner(name="Jordan", daily_minutes_available=90)

    # 2. Add a couple of pets.
    biscuit = Pet(name="Biscuit", species="dog", breed="Golden Retriever", age=3)
    mochi = Pet(name="Mochi", species="cat", breed="Tabby", age=2)
    owner.add_pet(biscuit)
    owner.add_pet(mochi)

    # 3. Give the pets some tasks with different durations and priorities.
    biscuit.add_task(Task("Morning walk", duration_minutes=30, priority="high"))
    biscuit.add_task(Task("Feeding", duration_minutes=10, priority="high"))
    biscuit.add_task(Task("Training session", duration_minutes=45, priority="low"))
    mochi.add_task(Task("Feeding", duration_minutes=10, priority="high"))
    mochi.add_task(Task("Litter cleanup", duration_minutes=15, priority="medium"))

    # 4. Build today's schedule from all of the owner's pets' tasks.
    scheduler = Scheduler(available_minutes=owner.daily_minutes_available)
    scheduler.load_from_owner(owner)

    print(f"Today's Schedule for {owner.name}")
    print("=" * 40)
    print(scheduler.explain_plan())


if __name__ == "__main__":
    main()
