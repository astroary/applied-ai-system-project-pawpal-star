"""PawPal+ logic layer — the backend "brain" for pet-care planning.

Classes:
    Task      — a single care activity (walk, feeding, meds, ...).
    Pet       — a pet plus the list of tasks it needs.
    Owner     — a person who manages one or more pets.
    Scheduler — selects and orders tasks into a daily plan under a time budget.
"""

from dataclasses import dataclass, field

# Lower number = higher priority, so tasks sort high -> low.
PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


@dataclass
class Task:
    """A single pet-care activity with a duration, priority, and status."""

    title: str
    duration_minutes: int
    priority: str = "medium"        # "low" | "medium" | "high"
    frequency: str = "daily"        # "daily" | "weekly" | "once"
    completed: bool = False

    def priority_rank(self) -> int:
        """Return a sortable rank (0 = highest) based on priority."""
        return PRIORITY_ORDER.get(self.priority, 1)

    def mark_complete(self) -> None:
        """Mark this task as done."""
        self.completed = True


@dataclass
class Pet:
    """A pet owned by the user, with its own list of care tasks."""

    name: str
    species: str
    breed: str = ""
    age: int = 0
    tasks: list[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        """Attach a care task to this pet."""
        self.tasks.append(task)

    def task_count(self) -> int:
        """Return how many tasks this pet currently has."""
        return len(self.tasks)


@dataclass
class Owner:
    """A pet owner: manages multiple pets and a daily time budget."""

    name: str
    daily_minutes_available: int = 120
    preferences: dict = field(default_factory=dict)
    pets: list[Pet] = field(default_factory=list)

    def add_pet(self, pet: Pet) -> None:
        """Register a pet under this owner."""
        self.pets.append(pet)

    def set_preferences(self, prefs: dict) -> None:
        """Merge in owner scheduling preferences (preferred times, etc.)."""
        self.preferences.update(prefs)

    def all_tasks(self) -> list[Task]:
        """Return every task across all of this owner's pets."""
        return [task for pet in self.pets for task in pet.tasks]


class Scheduler:
    """Builds a daily plan from tasks given a time budget and priorities."""

    def __init__(self, available_minutes: int, start_hour: int = 8):
        self.tasks: list[Task] = []
        self.available_minutes = available_minutes
        self.start_hour = start_hour

    def add_task(self, task: Task) -> None:
        """Add a single task to the pool the scheduler plans from."""
        self.tasks.append(task)

    def load_from_owner(self, owner: "Owner") -> None:
        """Pull every task from all of an owner's pets into the pool."""
        for task in owner.all_tasks():
            self.add_task(task)

    def generate_plan(self) -> list[dict]:
        """Select and time-order tasks to fit the available minutes.

        Highest-priority tasks are placed first; a task is skipped if it
        would push the plan past the time budget. Returns a list of slots:
        {"time": "HH:MM", "task": Task}.
        """
        # Only plan tasks that still need doing, hardest-priority first.
        pending = [t for t in self.tasks if not t.completed]
        ordered = sorted(pending, key=lambda t: (t.priority_rank(), t.duration_minutes))

        plan: list[dict] = []
        minutes_used = 0
        clock = self.start_hour * 60  # minutes since midnight

        for task in ordered:
            if minutes_used + task.duration_minutes > self.available_minutes:
                continue  # doesn't fit; try the next (possibly shorter) task
            plan.append({"time": f"{clock // 60:02d}:{clock % 60:02d}", "task": task})
            minutes_used += task.duration_minutes
            clock += task.duration_minutes

        return plan

    def explain_plan(self) -> str:
        """Return a human-readable summary of the plan and why it was chosen."""
        plan = self.generate_plan()
        if not plan:
            return "No tasks fit in the available time."

        scheduled = {id(slot["task"]) for slot in plan}
        used = sum(slot["task"].duration_minutes for slot in plan)

        lines = [f"Daily plan ({used}/{self.available_minutes} min used):"]
        for slot in plan:
            t = slot["task"]
            lines.append(
                f"  {slot['time']} — {t.title} ({t.duration_minutes} min) "
                f"[priority: {t.priority}]"
            )

        skipped = [
            t for t in self.tasks
            if not t.completed and id(t) not in scheduled
        ]
        if skipped:
            lines.append("Skipped (not enough time):")
            for t in skipped:
                lines.append(f"  - {t.title} ({t.duration_minutes} min, {t.priority})")

        return "\n".join(lines)
