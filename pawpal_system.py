"""PawPal+ logic layer — class skeletons generated from the UML draft.

This is the backend "blueprint" for the system. Attributes and method
signatures only; scheduling logic comes in a later phase.
"""

from dataclasses import dataclass, field


@dataclass
class Task:
    """A single pet-care task (walk, feeding, meds, etc.)."""

    title: str
    duration_minutes: int
    priority: str = "medium"  # "low" | "medium" | "high"
    category: str = "general"
    recurring: bool = False

    def priority_rank(self) -> int:
        """Return a sortable integer so higher priority sorts first."""
        raise NotImplementedError


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
        raise NotImplementedError


@dataclass
class Owner:
    """The pet owner, their time budget, and care preferences."""

    name: str
    daily_minutes_available: int = 120
    preferences: dict = field(default_factory=dict)
    pets: list[Pet] = field(default_factory=list)

    def add_pet(self, pet: Pet) -> None:
        """Register a pet under this owner."""
        raise NotImplementedError

    def set_preferences(self, prefs: dict) -> None:
        """Update owner scheduling preferences (preferred times, etc.)."""
        raise NotImplementedError


class Scheduler:
    """Builds a daily plan from tasks given time and priority constraints."""

    def __init__(self, available_minutes: int):
        self.tasks: list[Task] = []
        self.available_minutes = available_minutes

    def add_task(self, task: Task) -> None:
        """Add a task to the pool the scheduler will plan from."""
        raise NotImplementedError

    def generate_plan(self) -> list:
        """Select and order tasks to fit available time by priority."""
        raise NotImplementedError

    def explain_plan(self) -> str:
        """Return a human-readable explanation of why the plan was chosen."""
        raise NotImplementedError
