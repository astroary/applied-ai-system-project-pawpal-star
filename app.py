import streamlit as st

# Step 1: bring the logic layer into the UI.
from pawpal_system import Owner, Pet, Task, Scheduler

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

st.title("🐾 PawPal+")
st.caption("Plan your pets' care around the time you actually have.")

# Step 2: persist the Owner in session_state so data survives reruns.
# Streamlit re-runs this whole script on every interaction; without this,
# the Owner (and all its pets/tasks) would be recreated empty each time.
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
        c1, c2 = st.columns(2)
        with c1:
            t_duration = st.number_input("Duration (min)", min_value=1, max_value=240, value=20)
        with c2:
            t_priority = st.selectbox("Priority", ["high", "medium", "low"])
        submitted_task = st.form_submit_button("Add task")
        if submitted_task:
            pet = owner.pets[pet_names.index(target)]
            pet.add_task(Task(t_title, duration_minutes=int(t_duration), priority=t_priority))
            st.success(f"Added '{t_title}' to {target}.")

    # Show each pet's current tasks.
    for pet in owner.pets:
        if pet.tasks:
            st.markdown(f"**{pet.name}** ({pet.task_count()} task(s))")
            st.table(
                [
                    {"title": t.title, "duration_minutes": t.duration_minutes, "priority": t.priority}
                    for t in pet.tasks
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
        st.code(scheduler.explain_plan(), language=None)
