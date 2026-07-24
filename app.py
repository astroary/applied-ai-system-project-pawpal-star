import os
from datetime import time

import streamlit as st

# Step 1: bring the logic layer into the UI.
from pawpal_system import Owner, Pet, Task, Scheduler
# Project 4: the AI layer (retrieval + planner + guardrails + critique + logging).
from care_planner import CarePlanner


@st.cache_resource
def get_care_planner() -> CarePlanner:
    """Build the AI Care Planner once and reuse it across Streamlit reruns.

    Loading the knowledge base and the LLM client is done a single time; the
    Groq API key is only needed when a plan is actually generated.
    """
    return CarePlanner()

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

st.title("🐾 PawPal+")
st.caption("Plan your pets' care around the time you actually have.")

# Persist the Owner in session_state so data survives Streamlit reruns.
if "owner" not in st.session_state:
    st.session_state.owner = Owner(name="Jordan", daily_minutes_available=90)

owner = st.session_state.owner

# --- Owner settings -------------------------------------------------------
st.subheader("Owner")
col_a, col_b = st.columns(2)
with col_a:
    owner.name = st.text_input("Owner name", value=owner.name)
with col_b:
    owner.daily_minutes_available = st.number_input(
        "Minutes available today",
        min_value=10,
        max_value=600,
        value=owner.daily_minutes_available,
        step=10,
    )

st.divider()

# --- Add a pet ------------------------------------------------------------
st.subheader("Pets")
with st.form("add_pet", clear_on_submit=True):
    p_name = st.text_input("Pet name", value="")
    p_species = st.selectbox("Species", ["dog", "cat", "other"])
    p_breed = st.text_input("Breed", value="")
    submitted_pet = st.form_submit_button("Add pet")
    if submitted_pet and p_name.strip():
        owner.add_pet(Pet(name=p_name.strip(), species=p_species, breed=p_breed.strip()))
        st.success(f"Added {p_name.strip()}!")

if not owner.pets:
    st.info("No pets yet. Add one above.")
else:
    st.write(f"**{len(owner.pets)}** pet(s): " + ", ".join(p.name for p in owner.pets))

st.divider()

# --- Add a task to a pet --------------------------------------------------
st.subheader("Tasks")
if owner.pets:
    with st.form("add_task", clear_on_submit=True):
        pet_names = [p.name for p in owner.pets]
        target = st.selectbox("For which pet?", pet_names)
        t_title = st.text_input("Task title", value="Morning walk")
        c1, c2, c3 = st.columns(3)
        with c1:
            t_duration = st.number_input("Duration (min)", min_value=1, max_value=240, value=20)
        with c2:
            t_priority = st.selectbox("Priority", ["high", "medium", "low"])
        with c3:
            t_time = st.time_input("Scheduled time", value=time(8, 0))
        t_frequency = st.selectbox("Frequency", ["daily", "weekly", "once"])
        submitted_task = st.form_submit_button("Add task")
        if submitted_task:
            pet = owner.pets[pet_names.index(target)]
            pet.add_task(
                Task(
                    t_title,
                    duration_minutes=int(t_duration),
                    priority=t_priority,
                    frequency=t_frequency,
                    time=t_time.strftime("%H:%M"),
                )
            )
            st.success(f"Added '{t_title}' to {target} at {t_time.strftime('%H:%M')}.")

    # Show all tasks across pets, sorted by scheduled time (Step 1 sorting).
    if owner.all_tasks():
        scheduler = Scheduler(available_minutes=owner.daily_minutes_available)
        scheduler.load_from_owner(owner)
        st.markdown("**All tasks (sorted by time):**")
        st.table(
            [
                {
                    "time": t.time or "—",
                    "pet": t.pet_name,
                    "task": t.title,
                    "min": t.duration_minutes,
                    "priority": t.priority,
                    "done": "✅" if t.completed else "",
                }
                for t in scheduler.sort_by_time()
            ]
        )
else:
    st.caption("Add a pet first, then you can add tasks for it.")

st.divider()

# --- Generate the schedule ------------------------------------------------
st.subheader("Today's Schedule")
if st.button("Generate schedule", type="primary"):
    if not owner.all_tasks():
        st.warning("No tasks to schedule yet. Add some tasks above.")
    else:
        scheduler = Scheduler(available_minutes=owner.daily_minutes_available)
        scheduler.load_from_owner(owner)

        # Surface conflict warnings prominently so the owner can fix them.
        conflicts = scheduler.detect_conflicts()
        if conflicts:
            for w in conflicts:
                st.warning(f"⚠️ {w}")
        else:
            st.success("No scheduling conflicts found.")

        st.code(scheduler.explain_plan(), language=None)

st.divider()

# --- AI Care Plan (Project 4) --------------------------------------------
st.subheader("🤖 AI Care Plan")
st.caption(
    "Grounds the schedule in a pet-care knowledge base, explains each step with "
    "citations, refuses unsafe requests, self-critiques, and scores its confidence."
)

if not os.environ.get("GROQ_API_KEY"):
    st.warning(
        "No `GROQ_API_KEY` found. Copy `.env.example` to `.env` and add your free "
        "Groq key (console.groq.com/keys) to enable the AI plan."
    )

ai_request = st.text_input(
    "Optional question or context for the AI (e.g. 'my puppy tires quickly')",
    value="",
)

if st.button("Generate AI care plan"):
    if not owner.all_tasks():
        st.warning("Add some tasks first, then generate an AI plan.")
    else:
        with st.spinner("Retrieving knowledge, planning, and self-critiquing…"):
            result = get_care_planner().run(owner, request=ai_request)

        if result.plan.refused:
            # Guardrails blocked the request (e.g. medication dosing).
            st.error(result.plan.summary)
        else:
            st.progress(result.confidence, text=f"Confidence: {result.confidence:.2f}")
            if result.revised:
                st.caption(
                    f"🔧 Self-critique revised the plan to fix "
                    f"{len(result.problems_before)} issue(s)."
                )
            st.write(result.plan.summary)

            if result.plan.steps:
                st.table(
                    [
                        {
                            "time": s.get("time", "—"),
                            "pet": s.get("pet", ""),
                            "task": s.get("task", ""),
                            "why (grounded)": s.get("rationale", ""),
                        }
                        for s in result.plan.steps
                    ]
                )
            if result.plan.notes:
                st.info(result.plan.notes)

            severity = result.plan.guardrails.get("severity", "ok")
            badge = {"ok": "✅ clean", "warn": "⚠️ warnings", "block": "⛔ blocked"}
            st.caption(
                f"Guardrails: {badge.get(severity, severity)} · "
                f"Sources retrieved: {', '.join(result.sources) or '—'}"
            )

            with st.expander("🔍 Reasoning trace (how the AI checked its own work)"):
                st.markdown(result.to_markdown())
