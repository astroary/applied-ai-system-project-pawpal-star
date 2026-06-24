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


# --- Extensions -----------------------------------------------------------
def test_sort_by_priority_then_time():
    """Challenge 3: high-priority tasks lead even if they occur later."""
    scheduler = Scheduler(available_minutes=120)
    scheduler.add_task(Task("Early low", 10, priority="low", time="07:00"))
    scheduler.add_task(Task("Late high", 10, priority="high", time="09:00"))
    titles = [t.title for t in scheduler.sort_by_priority_then_time()]
    assert titles == ["Late high", "Early low"]


def test_next_available_slot_finds_gap_after_busy_time():
    """Challenge 1: the next slot starts when the existing task ends."""
    scheduler = Scheduler(available_minutes=240, start_hour=8)
    scheduler.add_task(Task("Walk", 30, time="08:00"))  # busy 08:00-08:30
    assert scheduler.next_available_slot(20) == "08:30"


def test_next_available_slot_returns_none_when_day_is_full():
    """Challenge 1: returns None if nothing fits before midnight."""
    scheduler = Scheduler(available_minutes=60, start_hour=23)
    scheduler.add_task(Task("Late task", 30, time="23:00"))  # busy 23:00-23:30
    assert scheduler.next_available_slot(60) is None


def test_owner_json_round_trip(tmp_path):
    """Challenge 2: saving then loading reproduces pets, tasks, and dates."""
    owner = Owner(name="Jordan", daily_minutes_available=90)
    pet = Pet(name="Biscuit", species="dog")
    pet.add_task(Task("Walk", 30, priority="high", time="08:00",
                      frequency="daily", due_date=date.today()))
    owner.add_pet(pet)

    path = tmp_path / "data.json"
    owner.save_to_json(str(path))
    loaded = Owner.load_from_json(str(path))

    assert loaded.name == "Jordan"
    assert loaded.daily_minutes_available == 90
    assert len(loaded.pets) == 1
    reloaded_task = loaded.pets[0].tasks[0]
    assert reloaded_task.title == "Walk"
    assert reloaded_task.due_date == date.today()
    assert reloaded_task.pet_name == "Biscuit"
