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

- How did you use AI tools during this project (for example: design brainstorming, debugging, refactoring)?
- What kinds of prompts or questions were most helpful?

**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.
- How did you evaluate or verify what the AI suggested?

---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?
- Why were these tests important?

**b. Confidence**

- How confident are you that your scheduler works correctly?
- What edge cases would you test next if you had more time?

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?
