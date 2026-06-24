"""Behavior tests for the PawPal+ logic layer.

Covers happy paths (completion, addition, sorting, recurrence, conflicts)
and a couple of edge cases (no tasks, untimed tasks).
"""

from datetime import date, timedelta

from pawpal_system import Owner, Pet, Task, Scheduler


# --- Phase 2 basics -------------------------------------------------------
def test_mark_complete_changes_status():
    """Task Completion: mark_complete() should flip a task to done."""
    task = Task("Morning walk", duration_minutes=30, priority="high")
    assert task.completed is False
    task.mark_complete()
    assert task.completed is True


def test_add_task_increases_pet_task_count():
    """Task Addition: adding a task should grow the pet's task count."""
    pet = Pet(name="Biscuit", species="dog")
    assert pet.task_count() == 0
    pet.add_task(Task("Feeding", duration_minutes=10, priority="high"))
    assert pet.task_count() == 1


def test_add_task_stamps_pet_name():
    """Adding a task records which pet it belongs to (used by filtering)."""
    pet = Pet(name="Biscuit", species="dog")
    task = Task("Feeding", duration_minutes=10)
    pet.add_task(task)
    assert task.pet_name == "Biscuit"


# --- Sorting correctness --------------------------------------------------
def test_sort_by_time_returns_chronological_order():
    """Tasks added out of order come back sorted by their HH:MM time."""
    scheduler = Scheduler(available_minutes=120)
    scheduler.add_task(Task("Evening walk", 30, time="18:00"))
    scheduler.add_task(Task("Morning walk", 30, time="07:30"))
    scheduler.add_task(Task("Lunch feed", 10, time="12:00"))
    times = [t.time for t in scheduler.sort_by_time()]
    assert times == ["07:30", "12:00", "18:00"]


def test_sort_by_time_puts_untimed_tasks_last():
    """Tasks with no scheduled time sort after timed ones, not first."""
    scheduler = Scheduler(available_minutes=120)
    scheduler.add_task(Task("No time", 10, time=""))
    scheduler.add_task(Task("Has time", 10, time="09:00"))
    titles = [t.title for t in scheduler.sort_by_time()]
    assert titles == ["Has time", "No time"]


# --- Filtering ------------------------------------------------------------
def test_filter_by_status_and_pet():
    """Filtering returns only matching tasks by status and by pet."""
    scheduler = Scheduler(available_minutes=120)
    done = Task("Done task", 10, time="08:00", completed=True, pet_name="Biscuit")
    pending = Task("Pending task", 10, time="09:00", pet_name="Mochi")
    scheduler.add_task(done)
    scheduler.add_task(pending)
    assert scheduler.filter_by_status(completed=True) == [done]
    assert scheduler.filter_by_status(completed=False) == [pending]
    assert scheduler.filter_by_pet("Mochi") == [pending]


# --- Recurrence logic -----------------------------------------------------
def test_completing_daily_task_creates_next_day_occurrence():
    """Recurrence: completing a daily task queues one due tomorrow."""
    pet = Pet(name="Biscuit", species="dog")
    walk = Task("Walk", 30, frequency="daily", due_date=date.today())
    pet.add_task(walk)

    nxt = pet.complete_task(walk)

    assert walk.completed is True
    assert nxt is not None
    assert nxt.completed is False
    assert nxt.due_date == date.today() + timedelta(days=1)
    assert pet.task_count() == 2  # original + new occurrence


def test_completing_weekly_task_advances_seven_days():
    """A weekly task's next occurrence is seven days out."""
    pet = Pet(name="Biscuit", species="dog")
    bath = Task("Bath", 45, frequency="weekly", due_date=date.today())
    pet.add_task(bath)
    nxt = pet.complete_task(bath)
    assert nxt.due_date == date.today() + timedelta(days=7)


def test_one_off_task_does_not_recur():
    """A 'once' task creates no follow-up when completed."""
    pet = Pet(name="Biscuit", species="dog")
    vet = Task("Vet visit", 60, frequency="once")
    pet.add_task(vet)
    nxt = pet.complete_task(vet)
    assert nxt is None
    assert pet.task_count() == 1


# --- Conflict detection ---------------------------------------------------
def test_detect_conflicts_flags_duplicate_times():
    """Two tasks at the same time produce one conflict warning."""
    scheduler = Scheduler(available_minutes=120)
    scheduler.add_task(Task("Feed dog", 10, time="08:00", pet_name="Biscuit"))
    scheduler.add_task(Task("Feed cat", 10, time="08:00", pet_name="Mochi"))
    warnings = scheduler.detect_conflicts()
    assert len(warnings) == 1
    assert "08:00" in warnings[0]


def test_no_conflicts_when_times_differ():
    """Distinct times produce no warnings."""
    scheduler = Scheduler(available_minutes=120)
    scheduler.add_task(Task("Feed dog", 10, time="08:00"))
    scheduler.add_task(Task("Feed cat", 10, time="09:00"))
    assert scheduler.detect_conflicts() == []


# --- Edge cases -----------------------------------------------------------
def test_empty_owner_produces_empty_plan_and_no_conflicts():
    """A pet with no tasks yields an empty plan and no conflicts."""
    owner = Owner(name="Jordan", daily_minutes_available=60)
    owner.add_pet(Pet(name="Biscuit", species="dog"))
    scheduler = Scheduler(available_minutes=60)
    scheduler.load_from_owner(owner)
    assert scheduler.generate_plan() == []
    assert scheduler.detect_conflicts() == []
    assert scheduler.explain_plan() == "No tasks fit in the available time."
