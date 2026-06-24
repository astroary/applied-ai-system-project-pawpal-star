# PawPal+ Project Reflection

## 1. System Design

**a. Initial design**

My initial UML uses four classes:

- **Owner** — holds the user's name, daily time budget (`daily_minutes_available`), and `preferences`. Responsible for owning pets and storing scheduling preferences.
- **Pet** — holds basic info (name, species, breed, age) and the list of care tasks for that pet.
- **Task** — a single care item with a title, `duration_minutes`, `priority`, `category`, and a `recurring` flag. Responsible for reporting its own priority rank for sorting.
- **Scheduler** — the "brain." Takes a pool of tasks plus the available-minutes constraint and is responsible for building (`generate_plan`) and explaining (`explain_plan`) the daily plan.

Relationships: an Owner owns one or more Pets, each Pet has many Tasks, and the Scheduler schedules from a set of Tasks. I kept data (Owner/Pet/Task) separate from logic (Scheduler) so the scheduling rules live in one place.

**b. Design changes**

Yes. The biggest change was to the **Task** class. My initial skeleton had `category` and `recurring` fields but no way to track whether a task was done. While implementing the demo and tests, I realized the scheduler needs to know which tasks are still pending, so I:

- Added a `completed` flag and a `mark_complete()` method to track status.
- Replaced the `recurring` boolean with a `frequency` field (`"daily"`/`"weekly"`/`"once"`), which is more expressive.
- Dropped `category`, since it wasn't used by any scheduling logic — keeping it would have been unnecessary complexity.

I also added two helper methods that emerged naturally from the relationships: `Owner.all_tasks()` (flatten every task across the owner's pets) and `Scheduler.load_from_owner()`. These came directly from thinking through "how does the Scheduler get tasks from the Owner's pets?" — it was cleaner to give the Owner that responsibility than to have the Scheduler reach into each pet itself.

---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

The scheduler considers two main constraints: the owner's **daily time budget** (`available_minutes`) and each task's **priority**. `generate_plan()` sorts pending tasks by priority first (high → low), then by shortest duration, and greedily fills the day until the time budget runs out — so the most important tasks are guaranteed a slot and low-value tasks are dropped when time is tight. I treated time as the hard limit and priority as the tiebreaker, because a busy owner's real constraint is the minutes they actually have.

**b. Tradeoffs**

My conflict detection only flags tasks that share the **exact same start time** ("HH:MM" match); it does not account for overlapping *durations*. So a 30-minute walk at 08:00 and a feeding at 08:15 are treated as non-conflicting, even though they overlap in real life.

This is a reasonable tradeoff for the scenario: exact-match detection is simple, fast, and easy to reason about, and it catches the most common mistake (double-booking the same slot). Full overlap math would add complexity for a planning aid where the owner can eyeball the schedule and adjust. It's an obvious place to extend later.

---

## 3. AI Collaboration

**a. How you used AI**

I used my AI coding assistant at every phase, but for different jobs:

- **Design brainstorming (Phase 1):** turning the four classes into a Mermaid UML diagram and a matching skeleton.
- **Implementation (Phases 2–4):** fleshing out method bodies, then adding the algorithmic features — sorting by time, filtering, recurrence with `timedelta`, and conflict detection.
- **Multi-file edits:** when a change touched both `Task` and `Pet` (e.g., adding recurrence), the assistant updated them together and kept `main.py` in sync.
- **Testing (Phase 5):** drafting pytest cases for the trickier behaviors and explaining what each one asserted.

The most helpful prompts were **specific and grounded in my actual code** — e.g., "based on my skeletons, how should the Scheduler get tasks from the Owner's pets?" — rather than vague "write me a scheduler" requests. Asking it to *explain* its choice was as useful as the code itself.

**b. Judgment and verification**

I did not accept the design as-is. The initial `Task` skeleton had `category` and `recurring` fields, but as I implemented the features I realized `category` was never used by any logic and `recurring` (a bool) couldn't express "daily vs. weekly." I dropped `category` to avoid dead complexity and replaced `recurring` with a `frequency` string. I also kept conflict detection deliberately simple (exact time match) rather than accepting a more elaborate overlap algorithm, because the simpler version was easier to verify and fit the scenario.

I verified suggestions by **running them**: the `main.py` CLI demo let me eyeball that sorting, conflicts, and recurrence behaved correctly, and the pytest suite (12 tests) locked in those behaviors so later changes couldn't silently break them.

---

## 4. Testing and Verification

**a. What you tested**

I tested the behaviors most likely to be wrong or to regress:

- **Task basics** — `mark_complete()` changes status; adding a task increases a pet's count and stamps the pet's name.
- **Sorting correctness** — out-of-order tasks return chronologically; untimed tasks sort last.
- **Filtering** — by completion status and by pet.
- **Recurrence logic** — a daily task creates one due tomorrow, weekly advances 7 days, and a `"once"` task creates nothing.
- **Conflict detection** — two tasks at the same time produce exactly one warning; distinct times produce none.
- **Edge case** — a pet with no tasks yields an empty plan and no conflicts (no crash).

These matter because they are the core "intelligence" of the app — if sorting, recurrence, or conflict detection is wrong, the daily plan misleads the owner.

**b. Confidence**

I'm fairly confident (★★★★☆). All core behaviors and the main edge cases pass. With more time I'd test: recurrence across **month/year boundaries**, conflict detection for **overlapping durations** (not just identical start times), and behavior when the **time budget is smaller than the highest-priority task**.

---

## 5. Reflection

**a. What went well**

I'm most satisfied with the **clean separation between data and logic**. Keeping `Owner`/`Pet`/`Task` as simple dataclasses and putting all the decision-making in `Scheduler` made each feature (sorting, filtering, conflicts, recurrence) easy to add and easy to test in isolation.

**b. What you would improve**

I'd make conflict detection **duration-aware** so overlapping tasks are caught, not just identical start times. I'd also unify the two notions of "time" in the system: tasks now have an explicit scheduled `time`, but `generate_plan()` still assigns its own sequential slots by priority — reconciling those would make the UI and the plan tell a single consistent story.

**c. Key takeaway**

The biggest lesson was that my job was to be the **lead architect, not the typist**. The AI could generate plausible code instantly, but it was my responsibility to decide what the system *should* be — to reject unused fields, choose the simpler conflict-detection tradeoff, and verify everything with a demo and tests. AI accelerated the work; judgment and verification kept it correct.
