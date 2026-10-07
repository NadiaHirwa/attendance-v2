"""Streamlit interface for the attendance system: streamlit run app.py

This file only shows the screens. Rules live in validation.py,
SQL lives in database.py, and calculations live in analytics.py.
"""

import sqlite3
from datetime import date

import altair as alt
import pandas as pd
import streamlit as st

import analytics
import database
import importer
import seed_demo
import validation

STATUS_OPTIONS = ["Present", "Late", "Excused", "Absent"]
# Present blue, Late light blue, Excused pink, Absent orange, Unknown grey: colour-blind
# friendly (Okabe-Ito palette), and grey suggests "missing".
# Same order as analytics.STATUS_ORDER.
STATUS_COLORS = ["#0072B2", "#56B4E9", "#CC79A7", "#E69F00", "#999999"]
# Width in pixels, so the longest import reasons fit without being cut off.
REASON_COLUMN_WIDTH = 1500
ALL_STUDENTS = "All students"
ALL_BLOCKS = analytics.ALL_BLOCKS
ALL_WEEKS = "All weeks"
THRESHOLD_KEY = "threshold"
# Widget keys of the "Alert rules" inputs, by rule name (see analytics.DEFAULT_ATTENTION_RULES).
ATTENTION_KEYS = {
    "recent_absences": "attention_recent",
    "absences": "attention_absences",
    "rate": "attention_rate",
    "marks": "attention_marks",
}
# The status names under the Dashboard cards, in the order of STATUS_COLORS.
STATUS_DOT_LABELS = ["Present", "Late", "Excused", "Absent", "Not recorded"]
# Every date input shows dates as DD/MM/YYYY, like the rest of the app (BR-23).
DATE_INPUT_FORMAT = "DD/MM/YYYY"
NO_COURSES_MESSAGE = "No courses yet. Create a course first."
NO_BLOCKS_MESSAGE = "No blocks yet. Create a block first."
# Courses from a database made before Version 3 have no block.
NO_BLOCK_LABEL = analytics.NO_BLOCK_LABEL
NO_STUDENTS_MESSAGE = "No students yet. Add a student first."
NO_DATA_MESSAGE = (
    "No sessions with enrolled students yet. Create a course, a session and a student "
    "in Manage Attendance, or import a CSV file."
)
NO_MATCH_MESSAGE = (
    "No sessions match these filters. Choose another course or a wider date range."
)


# ---------- Helpers ----------

def format_course_period(start_date, end_date):
    """Return a course period for labels, like '07/09/2026 to 25/09/2026' (FR-25, BR-23)."""
    start_text = validation.format_date(start_date)
    if start_date is None:
        start_text = "no start"
    end_text = validation.format_date(end_date)
    if end_date is None:
        end_text = "no end"
    return f"{start_text} to {end_text}"


def make_course_label(course):
    """Return a label like 'PY101 - Programming with Python (07/09/2026 to 25/09/2026)'."""
    period = format_course_period(course["start_date"], course["end_date"])
    return f"{course['course_code']} - {course['course_name']} ({period})"


def get_course_choices(connection):
    """Return a dict that maps a course label (with its period) to its course code."""
    choices = {}
    for course in database.get_courses(connection):
        choices[make_course_label(course)] = course["course_code"]
    return choices


def get_student_choices(connection):
    """Return a dict that maps a label like '001 - Nadia Hirwa' to its student ID."""
    choices = {}
    for student in database.get_all_students(connection):
        label = f"{student['student_id']} - {student['full_name']}"
        choices[label] = student["student_id"]
    return choices


def describe_session(session):
    """Return a label like 'Mon 07/09/2026 - Class' or 'Sat 12/09/2026 - Tutorial T1'.

    Session IDs are never shown (Stage 7): date, day and type say which session it is.
    """
    session_date = session["session_date"]
    weekday = validation.weekday_name(session_date)[:3]
    session_type = analytics.describe_session_type(session["session_id"], session["session_type"])
    return f"{weekday} {validation.format_date(session_date)} - {session_type}"


def get_session_choices(connection, course_code):
    """Return a dict that maps a label like 'Mon 07/09/2026 - Class' to its session ID."""
    choices = {}
    for session in database.get_sessions_for_course(connection, course_code):
        choices[describe_session(session)] = session["session_id"]
    return choices


def to_date_or_none(date_text):
    """Turn 'YYYY-MM-DD' text into a date, or return None when there is no date."""
    if date_text is None:
        return None
    return date.fromisoformat(date_text)


def to_text_or_none(chosen_date):
    """Turn a date from st.date_input into 'YYYY-MM-DD' text, or None when it is empty."""
    if chosen_date is None:
        return None
    return chosen_date.isoformat()


def show_enrollment_period_inputs(course, start_value, end_value, key):
    """Show 'Enrolled from' and 'Enrolled until', limited to the course period (BR-17).

    start_value and end_value are dates or None (an empty input means no limit).
    Returns (start_date, end_date) as 'YYYY-MM-DD' text or None.
    """
    course_start = to_date_or_none(course["start_date"])
    course_end = to_date_or_none(course["end_date"])

    start = st.date_input(
        "Enrolled from", value=start_value, min_value=course_start, max_value=course_end,
        format=DATE_INPUT_FORMAT, key=f"{key}_from",
    )
    end = st.date_input(
        "Enrolled until", value=end_value, min_value=course_start, max_value=course_end,
        format=DATE_INPUT_FORMAT, key=f"{key}_until",
    )
    st.caption(
        "Use this only when a student joins after the course starts or leaves before it ends."
    )
    return to_text_or_none(start), to_text_or_none(end)


def describe_enrollment_dates(start_date, end_date):
    """Return text like 'from 14/09/2026' or 'from 14/09/2026 until 18/09/2026'."""
    if start_date is None:
        text = "from the first session"
    else:
        text = f"from {validation.format_date(start_date)}"

    if end_date is not None:
        text = text + f" until {validation.format_date(end_date)}"
    return text


def join_course_codes(connection, student_id):
    """Return a student's course codes as text, like 'DS102, PY101'."""
    codes = []
    for course in database.get_student_courses(connection, student_id):
        codes.append(course["course_code"])

    if not codes:
        return "Not enrolled"
    return ", ".join(codes)


# ---------- BR-18: create a block ----------

def get_block_choices(connection):
    """Return a dict that maps a label like 'B1-2627 - Block 1, 2026-27 (07/09/2026 to
    25/09/2026)' to its block ID."""
    choices = {}
    for block in database.get_blocks(connection):
        period = format_course_period(block["start_date"], block["end_date"])
        choices[f"{block['block_id']} - {block['block_name']} ({period})"] = block["block_id"]
    return choices


def show_add_block(connection):
    """Show the form to create a block: ID, name and a Monday start (BR-18)."""
    st.subheader("Create a block")

    with st.form("add_block_form", clear_on_submit=True):
        id_text = st.text_input("Block ID", placeholder="B1-2627")
        name_text = st.text_input("Block name", placeholder="Block 1, 2026-27")
        start = st.date_input("Start date (a Monday)", value=None, format=DATE_INPUT_FORMAT)
        st.caption("The block lasts 3 weeks: the end date (Friday of week 3) is calculated.")
        submitted = st.form_submit_button("Create block")

    if not submitted:
        return

    block_id = validation.normalize_block_id(id_text)
    block_name = validation.clean_course_name(name_text)
    start_date = to_text_or_none(start)

    if block_id is None:
        st.error(validation.BLOCK_ID_ERROR)
    elif block_name is None:
        st.error(validation.BLOCK_NAME_ERROR)
    elif start_date is None:
        st.error(validation.DATE_ERROR)
    elif not validation.is_monday(start_date):
        st.error(validation.BLOCK_START_ERROR.format(
            validation.format_date(start_date), validation.weekday_name(start_date)
        ))
    elif database.get_block(connection, block_id) is not None:
        st.error(validation.BLOCK_EXISTS_ERROR.format(block_id))
    else:
        end_date = database.add_block(connection, block_id, block_name, start_date)
        st.success(
            f"Block {block_id} created, running "
            f"{validation.describe_course_period(start_date, end_date)}."
        )


# ---------- FR-03: create a course in a block ----------

def show_add_course(connection):
    """Show the form to create a course in a block; its class days are generated (FR-03).

    The dates default to the block (BR-19). The "Shorter period" box narrows them
    inside the block, and class days are generated for that period only (BR-20).
    The block is chosen outside the form, so the date limits follow it.
    """
    st.subheader("Create a course")

    block_choices = get_block_choices(connection)
    if not block_choices:
        st.info(NO_BLOCKS_MESSAGE)
        return

    block_label = st.selectbox("Block", list(block_choices), key="add_course_block")
    block_id = block_choices[block_label]
    block = database.get_block(connection, block_id)
    block_start = to_date_or_none(block["start_date"])
    block_end = to_date_or_none(block["end_date"])

    with st.form(f"add_course_form_{block_id}", clear_on_submit=True):
        code_text = st.text_input("Course code", placeholder="PY101")
        name_text = st.text_input("Course name", placeholder="Programming with Python")
        shorter = st.checkbox("Shorter period (inside the block)")
        start = st.date_input(
            "Start date", value=block_start, min_value=block_start, max_value=block_end,
            format=DATE_INPUT_FORMAT,
        )
        end = st.date_input(
            "End date", value=block_end, min_value=block_start, max_value=block_end,
            format=DATE_INPUT_FORMAT,
        )
        st.caption("Without the box ticked, the course runs for the whole block.")
        submitted = st.form_submit_button("Create course")

    if not submitted:
        return

    course_code = validation.normalize_course_code(code_text)
    course_name = validation.clean_course_name(name_text)
    start_date = None
    end_date = None
    if shorter:
        start_date = to_text_or_none(start)
        end_date = to_text_or_none(end)

    if course_code is None:
        st.error(validation.COURSE_CODE_ERROR)
        return
    if course_name is None:
        st.error(validation.COURSE_NAME_ERROR)
        return
    if database.course_exists(connection, course_code):
        st.error(validation.COURSE_EXISTS_ERROR.format(course_code))
        return

    try:
        class_days = database.create_course(
            connection, course_code, course_name, block_id, start_date, end_date
        )
    except ValueError as error:
        st.error(str(error))
        return

    course = database.get_course(connection, course_code)
    period = validation.describe_course_period(course["start_date"], course["end_date"])
    finish_edit(
        f"Course {course_code} - {course_name} created in block {block_id}, running "
        f"{period}, with {class_days} class days (every weekday)."
    )


def show_block_list(connection):
    """List every block with its period and its courses (Section 6.1)."""
    st.subheader("Blocks")

    rows = []
    for block in database.get_blocks(connection):
        codes = []
        for course in database.get_block_courses(connection, block["block_id"]):
            codes.append(course["course_code"])
        courses_text = ", ".join(codes)
        if not codes:
            courses_text = "No courses yet"
        rows.append({
            "Block": block["block_id"],
            "Name": block["block_name"],
            "Start date": validation.format_date(block["start_date"]),
            "End date": validation.format_date(block["end_date"]),
            "Courses": courses_text,
        })

    if not rows:
        st.info(NO_BLOCKS_MESSAGE)
        return
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


def show_edit_block(connection):
    """Change a block's name or start date; its courses and class days move with it."""
    st.subheader("Edit a block")

    block_choices = get_block_choices(connection)
    if not block_choices:
        st.info(NO_BLOCKS_MESSAGE)
        return

    block_label = st.selectbox("Block", list(block_choices), key="edit_block")
    block_id = block_choices[block_label]
    block = database.get_block(connection, block_id)

    with st.form(f"edit_block_form_{block_id}"):
        name_text = st.text_input("Block name", value=block["block_name"])
        start = st.date_input(
            "Start date (a Monday)", value=to_date_or_none(block["start_date"]),
            format=DATE_INPUT_FORMAT,
        )
        st.caption(
            "The end date (Friday of week 3) is calculated. The block's courses move with "
            "it and their class days are regenerated; a removed holiday stays removed if its "
            "date is still in the block. Refused if saved attendance or an enrollment's "
            "dates would fall outside."
        )
        submitted = st.form_submit_button("Save block")

    if not submitted:
        return

    block_name = validation.clean_course_name(name_text)
    start_date = to_text_or_none(start)
    if block_name is None:
        st.error(validation.BLOCK_NAME_ERROR)
        return
    if start_date is None:
        st.error(validation.DATE_ERROR)
        return
    if block_name == block["block_name"] and start_date == block["start_date"]:
        st.info(validation.NO_CHANGE_MESSAGE.format("name and start date"))
        return

    try:
        result = database.change_block(connection, block_id, block_name, start_date)
    except ValueError as error:
        st.error(str(error))
        return

    finish_edit(
        f"Block {block_id} ({block_name}) now runs "
        f"{validation.describe_course_period(start_date, result['end_date'])}: "
        f"{result['added']} class day(s) added, {result['removed']} session(s) removed."
    )


def show_delete_block(connection):
    """Delete a block, only when it has no courses (Section 6.1)."""
    st.subheader("Delete a block")

    block_choices = get_block_choices(connection)
    if not block_choices:
        st.info(NO_BLOCKS_MESSAGE)
        return

    block_label = st.selectbox("Block", list(block_choices), key="delete_block")
    block_id = block_choices[block_label]
    course_count = len(database.get_block_courses(connection, block_id))

    if course_count > 0:
        st.error(validation.BLOCK_IN_USE_ERROR.format(block_id, course_count))
        return

    st.warning(f"This will remove 1 block: {block_label}. It has no courses.")
    if ask_to_confirm(f"block_{block_id}"):
        counts = database.delete_block(connection, block_id)
        finish_edit(f"Deleted block {block_id}: removed {describe_counts(counts)}.")


def show_course_list(connection):
    """List every course with its block and period (FR-25, BR-23)."""
    st.subheader("Courses")

    rows = []
    for course in database.get_courses(connection):
        block_text = course["block_id"]
        if block_text is None:
            block_text = "No block"
        start_text = validation.format_date(course["start_date"])
        if start_text is None:
            start_text = "no start"
        end_text = validation.format_date(course["end_date"])
        if end_text is None:
            end_text = "no end"
        rows.append({
            "Course": course["course_code"],
            "Name": course["course_name"],
            "Block": block_text,
            "Start date": start_text,
            "End date": end_text,
        })

    if not rows:
        st.info(NO_COURSES_MESSAGE)
        return
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


# ---------- FR-04: add a student ----------

def show_add_student(connection):
    """Show the form to add a student: details only, no course yet (FR-04)."""
    st.subheader("Add a student")
    st.caption(
        "Only enrolled students appear in Record attendance, the Dashboard and the class "
        "register. Enroll the new student in a course from their profile."
    )

    with st.form("add_student_form"):
        id_text = st.text_input("Student ID", placeholder="001")
        name_text = st.text_input("Full name", placeholder="Nadia Hirwa")
        confirm_same_name = st.checkbox("I confirm this is a different student with the same name")
        submitted = st.form_submit_button("Add student")

    if not submitted:
        return

    student_id = id_text.strip()
    full_name = validation.clean_name(name_text)

    if not validation.is_valid_student_id(student_id):
        st.error(validation.STUDENT_ID_ERROR)
        return

    if not validation.is_valid_name(full_name):
        st.error(validation.NAME_ERROR)
        return

    if database.get_student(connection, student_id) is not None:
        st.error(validation.STUDENT_EXISTS_ERROR.format(student_id))
        return

    # V1 rule: a repeated name is allowed only after the user confirms it.
    same_name_students = database.find_students_by_name(connection, full_name)
    if same_name_students and not confirm_same_name:
        first_match = same_name_students[0]
        st.warning(validation.DUPLICATE_NAME_WARNING.format(
            first_match["full_name"], first_match["student_id"]
        ))
        return

    database.add_student(connection, student_id, full_name)
    # Open the new student's profile above, where they can be enrolled.
    st.session_state["open_profile"] = f"{student_id} - {full_name}"
    finish_edit(
        f"Student {student_id} - {full_name} added. Enroll them in a course in their "
        "profile above."
    )


# ---------- Shared: messages, confirmation and the Block -> Course picker ----------

def finish_edit(message):
    """Remember a success message and rerun, so every list on the page is up to date."""
    st.session_state["edit_message"] = message
    st.rerun()


def show_edit_message():
    """Show the message of the last change or delete once, then forget it."""
    message = st.session_state.pop("edit_message", None)
    if message is not None:
        st.success(message)


def ask_to_confirm(key):
    """Show the 'cannot be undone' checkbox and a Delete button that works only when ticked.

    The key includes the item's ID, so the box starts unticked for every new item.
    """
    understood = st.checkbox("I understand this cannot be undone", key=f"understand_{key}")
    return st.button("Delete", type="primary", disabled=not understood, key=f"delete_{key}")


def describe_counts(counts):
    """Return text like '3 attendance record(s), 1 enrollment(s)' for a dict of counts."""
    names = {
        "attendance": "attendance record(s)",
        "enrollments": "enrollment(s)",
        "students": "student(s)",
        "sessions": "session(s)",
        "class_days": "class day(s)",
        "tutorials": "tutorial(s)",
        "courses": "course(s)",
        "blocks": "block(s)",
    }
    parts = []
    for key in counts:
        parts.append(f"{counts[key]} {names[key]}")
    return ", ".join(parts)


def choose_course(connection, key_prefix):
    """Show a Block box, then a Course box limited to that block; return the course code.

    Courses from an older database have no block; they are listed under "No block".
    Returns None (after an info message) when there is nothing to choose.
    """
    block_choices = get_block_choices(connection)

    has_old_courses = False
    for course in database.get_courses(connection):
        if course["block_id"] is None:
            has_old_courses = True
    if has_old_courses:
        block_choices[NO_BLOCK_LABEL] = None

    if not block_choices:
        st.info(NO_BLOCKS_MESSAGE)
        return None

    block_label = st.selectbox("Block", list(block_choices), key=f"{key_prefix}_block")
    block_id = block_choices[block_label]

    course_choices = {}
    for course in database.get_courses(connection):
        if course["block_id"] == block_id:
            course_choices[make_course_label(course)] = course["course_code"]

    if not course_choices:
        st.info("This block has no courses yet. Create a course first.")
        return None

    # The key includes the block, so the Course box starts again when the block changes.
    course_label = st.selectbox(
        "Course", list(course_choices), key=f"{key_prefix}_course_{block_id}"
    )
    return course_choices[course_label]


# ---------- Blocks & Courses: one course (FR-22, FR-23, FR-25) ----------

def show_course_enrollments(connection, course_code):
    """List the students enrolled in a course, with their enrollment period (BR-15)."""
    course = database.get_course(connection, course_code)
    rows = []
    for enrollment in database.get_course_enrollments(connection, course_code):
        rows.append({
            "Student ID": enrollment["student_id"],
            "Full name": enrollment["full_name"],
            "Enrolled": describe_current_enrollment(
                enrollment["start_date"], enrollment["end_date"], course
            ).replace("Current: ", ""),
        })

    if not rows:
        st.info(f"No students are enrolled in {course_code} yet. Enroll them in Students.")
        return
    st.caption(f"{len(rows)} student(s) enrolled.")
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


def show_rename_course(connection, course_code):
    """Change a course's name. The course code stays the same (FR-22)."""
    current_name = database.get_course_name(connection, course_code)

    with st.form(f"rename_course_form_{course_code}"):
        name_text = st.text_input(
            "New course name", value=current_name, key=f"rename_course_name_{course_code}"
        )
        submitted = st.form_submit_button("Rename course")

    if not submitted:
        return

    new_name = validation.clean_course_name(name_text)
    if new_name is None:
        st.error(validation.COURSE_NAME_ERROR)
    elif new_name == current_name:
        st.info(validation.NO_CHANGE_MESSAGE.format("course name"))
    else:
        database.rename_course(connection, course_code, new_name)
        finish_edit(f"Course {course_code} renamed from {current_name} to {new_name}.")


def show_change_course_dates(connection, course_code):
    """Change a course's start and end dates and regenerate its class days (FR-25, BR-20).

    A course in a block must stay inside the block (BR-19). Refused, with counts, when
    saved records would be lost or an enrollment would fall outside the new period.
    """
    course = database.get_course(connection, course_code)
    current_start = course["start_date"]
    current_end = course["end_date"]

    with st.form(f"course_dates_form_{course_code}"):
        has_start = st.checkbox(
            "Set a start date (otherwise no limit)", value=current_start is not None
        )
        start = st.date_input(
            "Start date", value=to_date(current_start), format=DATE_INPUT_FORMAT
        )
        has_end = st.checkbox(
            "Set an end date (otherwise no limit)", value=current_end is not None
        )
        end = st.date_input("End date", value=to_date(current_end), format=DATE_INPUT_FORMAT)
        submitted = st.form_submit_button("Change course dates")

    if not submitted:
        return

    start_date = None
    if has_start:
        start_date = start.isoformat()
    end_date = None
    if has_end:
        end_date = end.isoformat()

    if start_date == current_start and end_date == current_end:
        st.info(validation.NO_CHANGE_MESSAGE.format("dates"))
        return

    # change_course_period() checks the block, enrollments and records, and
    # regenerates the class days, all in one transaction (BR-19, BR-20, BR-17).
    try:
        result = database.change_course_period(connection, course_code, start_date, end_date)
    except ValueError as error:
        st.error(str(error))
        return

    finish_edit(
        f"{course_code} now runs {validation.describe_course_period(start_date, end_date)}: "
        f"{result['added']} class day(s) added, {result['removed']} session(s) removed."
    )


def show_delete_course(connection, course_code):
    """Delete a course with its class days, tutorials, enrollments and records (FR-23).

    Version 3 rule (Section 11): show the counts first; delete only after the tick.
    """
    counts = database.count_delete_course(connection, course_code)

    st.warning(
        f"This will remove {describe_counts(counts)}: {course_code} and everything in it."
    )
    if ask_to_confirm(f"course_{course_code}"):
        counts = database.delete_course(connection, course_code)
        finish_edit(f"Deleted course {course_code}: removed {describe_counts(counts)}.")


def show_course_details(connection):
    """Pick a course, then see its students and rename, re-date or delete it."""
    st.subheader("Course details")

    course_code = choose_course(connection, "manage")
    if course_code is None:
        return

    show_course_enrollments(connection, course_code)

    with st.expander("Rename the course"):
        show_rename_course(connection, course_code)

    with st.expander("Change course dates (class days are regenerated)"):
        show_change_course_dates(connection, course_code)

    with st.expander("Delete the course"):
        show_delete_course(connection, course_code)


# ---------- Students: the student profile (FR-04, FR-05, FR-22 to FR-24) ----------

def describe_current_enrollment(start_date, end_date, course):
    """Return text like 'Current: 20/09/2026 to 25/09/2026 (joined late)'.

    A date that is not set follows the course, so the course's date is shown instead.
    """
    course_start = course["start_date"]
    course_end = course["end_date"]

    shown_start = start_date
    if shown_start is None:
        shown_start = course_start
    shown_end = end_date
    if shown_end is None:
        shown_end = course_end

    starts_late = shown_start != course_start
    ends_early = shown_end != course_end
    if starts_late and ends_early:
        note = "custom period"
    elif starts_late:
        note = "joined late"
    elif ends_early:
        note = "leaves early"
    else:
        note = "full course period"

    return f"Current: {format_course_period(shown_start, shown_end)} ({note})"


def get_student_course_choices(connection, student_id):
    """Return a dict that maps the full label of each of the student's courses to its code."""
    choices = {}
    for course in database.get_student_courses(connection, student_id):
        choices[make_course_label(course)] = course["course_code"]
    return choices


def show_enroll_student(connection, student_id):
    """Enroll the student in a course for the full course period (FR-05).

    The enrollment dates are stored as NULL, so they follow the course (BR-17).
    A late start or early leave is set afterwards, just below.
    """
    course_choices = get_course_choices(connection)
    if not course_choices:
        st.info(NO_COURSES_MESSAGE)
        return

    course_label = st.selectbox(
        "Course", list(course_choices), key=f"enroll_course_{student_id}"
    )
    course_code = course_choices[course_label]
    course = database.get_course(connection, course_code)

    if not st.button("Enroll", key=f"enroll_button_{student_id}"):
        return

    if database.is_enrolled(connection, student_id, course_code):
        st.error(validation.ALREADY_ENROLLED_ERROR.format(student_id, course_code))
        return

    database.enroll_student(connection, student_id, course_code)
    period = format_course_period(course["start_date"], course["end_date"])
    finish_edit(
        f"{student_id} enrolled in {course_code} for the full course period ({period})."
    )


def show_rename_student(connection, student_id):
    """Change the student's name with the same rules as Add Student (FR-22)."""
    current_name = database.get_student(connection, student_id)["full_name"]

    with st.form(f"rename_student_form_{student_id}"):
        name_text = st.text_input(
            "New full name", value=current_name, key=f"rename_student_name_{student_id}"
        )
        confirm_same_name = st.checkbox("I confirm this is a different student with the same name")
        submitted = st.form_submit_button("Rename student")

    if not submitted:
        return

    new_name = validation.clean_name(name_text)
    if not validation.is_valid_name(new_name):
        st.error(validation.NAME_ERROR)
        return

    if new_name == current_name:
        st.info(validation.NO_CHANGE_MESSAGE.format("name"))
        return

    # Same-name warning as Add Student, ignoring the student's own current name.
    other_students = []
    for student in database.find_students_by_name(connection, new_name):
        if student["student_id"] != student_id:
            other_students.append(student)

    if other_students and not confirm_same_name:
        first_match = other_students[0]
        st.warning(validation.DUPLICATE_NAME_WARNING.format(
            first_match["full_name"], first_match["student_id"]
        ))
        return

    database.rename_student(connection, student_id, new_name)
    finish_edit(f"Student {student_id} renamed from {current_name} to {new_name}.")


def show_change_enrollment_dates(connection, student_id):
    """Change the start and end dates of one of the student's enrollments (FR-24).

    Refused when saved attendance would fall outside the new dates.
    """
    course_choices = get_student_course_choices(connection, student_id)
    if not course_choices:
        st.info("This student is not enrolled in any course.")
        return

    course_label = st.selectbox(
        "Course", list(course_choices), key=f"dates_course_{student_id}"
    )
    course_code = course_choices[course_label]
    course = database.get_course(connection, course_code)
    enrollment = database.get_enrollment(connection, student_id, course_code)
    current_start = enrollment["start_date"]
    current_end = enrollment["end_date"]
    st.caption(describe_current_enrollment(current_start, current_end, course))

    # A date that is not set follows the course, so show the course's date instead.
    start_value = to_date_or_none(current_start)
    if start_value is None:
        start_value = to_date_or_none(course["start_date"])
    end_value = to_date_or_none(current_end)
    if end_value is None:
        end_value = to_date_or_none(course["end_date"])

    with st.form(f"dates_form_{student_id}_{course_code}"):
        start_date, end_date = show_enrollment_period_inputs(
            course, start_value, end_value, key=f"dates_{student_id}_{course_code}"
        )
        submitted = st.form_submit_button("Change dates")

    if not submitted:
        return

    if not validation.is_enrollment_in_course_period(
        start_date, end_date, course["start_date"], course["end_date"]
    ):
        period = validation.describe_course_period(course["start_date"], course["end_date"])
        st.error(validation.ENROLLMENT_OUTSIDE_COURSE_ERROR.format(course_code, period))
        return

    # Compare what would be stored: a date equal to the course's is stored as None.
    new_start, new_end = validation.simplify_enrollment_dates(
        start_date, end_date, course["start_date"], course["end_date"]
    )
    if new_start == current_start and new_end == current_end:
        st.info(validation.NO_CHANGE_MESSAGE.format("dates"))
        return

    outside = database.count_records_outside_window(
        connection, student_id, course_code, new_start, new_end
    )
    if outside > 0:
        st.error(validation.RECORDS_OUTSIDE_DATES_ERROR.format(outside, student_id, course_code))
        return

    database.update_enrollment_dates(connection, student_id, course_code, new_start, new_end)
    finish_edit(
        f"{student_id} is now enrolled in {course_code} "
        f"{describe_enrollment_dates(new_start, new_end)}."
    )


def to_date(date_text):
    """Turn 'YYYY-MM-DD' text into a date for st.date_input, or today when it is None."""
    if date_text is None:
        return date.today()
    return date.fromisoformat(date_text)


def show_unenroll_student(connection, student_id):
    """Un-enroll the student from one course, with their records for it (FR-23)."""
    course_choices = get_student_course_choices(connection, student_id)
    if not course_choices:
        st.info("This student is not enrolled in any course.")
        return

    course_label = st.selectbox(
        "Course", list(course_choices), key=f"unenroll_course_{student_id}"
    )
    course_code = course_choices[course_label]
    counts = database.count_unenroll(connection, student_id, course_code)

    st.warning(
        f"This will remove {describe_counts(counts)}: {student_id} leaves {course_code} "
        f"and their records for {course_code} sessions are deleted."
    )
    if ask_to_confirm(f"unenroll_{student_id}_{course_code}"):
        counts = database.unenroll_student(connection, student_id, course_code)
        finish_edit(
            f"Un-enrolled {student_id} from {course_code}: removed {describe_counts(counts)}."
        )


def show_delete_student(connection, student_id, student_label):
    """Delete the student with all their enrollments and records (FR-23)."""
    counts = database.count_delete_student(connection, student_id)

    st.warning(
        f"This will remove {describe_counts(counts)}: {student_label} and everything "
        "recorded for them. The ID can be used again afterwards."
    )
    if ask_to_confirm(f"student_{student_id}"):
        # The profile box would point to a student who no longer exists.
        if "profile_student" in st.session_state:
            del st.session_state["profile_student"]
        counts = database.delete_student(connection, student_id)
        finish_edit(f"Deleted student {student_label}: removed {describe_counts(counts)}.")


def show_profile_table(connection, student_id):
    """Show the student's courses with period, counts, rate, completeness and deductions."""
    records = analytics.build_records_frame(database.get_expected_records(connection))
    student_records = analytics.filter_student(records, student_id)

    if student_records.empty:
        course_codes = join_course_codes(connection, student_id)
        if course_codes == "Not enrolled":
            st.info("Not enrolled in any course yet. Enroll the student below.")
        else:
            st.info(f"Enrolled in {course_codes}, but no sessions are expected yet.")
        return

    settings = database.get_deduction_settings(connection)
    profile = analytics.build_student_profile(
        student_records, settings["late"], settings["absent"]
    )
    profile = analytics.format_date_columns(analytics.format_summary_table(profile))
    columns = [
        "Course", analytics.ENROLLED_FROM_COLUMN, analytics.ENROLLED_UNTIL_COLUMN,
        "Present", "Late", "Excused", "Absent", "Unknown", "Attendance rate",
        "Completeness", analytics.DEDUCTED_COLUMN, analytics.NOT_RECORDED_FLAG_COLUMN,
    ]
    st.dataframe(profile[columns], hide_index=True, width="stretch")
    st.caption(describe_deduction_rule(settings))


def show_student_profile(connection):
    """Show one student's profile and every change for that student (Section 6.1)."""
    st.subheader("Student profile")

    student_choices = get_student_choices(connection)
    if not student_choices:
        st.info(NO_STUDENTS_MESSAGE)
        return

    # A search or a new student asks to open a profile; the box must be set before it is drawn.
    requested = st.session_state.pop("open_profile", None)
    if requested in student_choices:
        st.session_state["profile_student"] = requested

    student_label = st.selectbox("Student", list(student_choices), key="profile_student")
    student_id = student_choices[student_label]

    # Every title names the student, so it is clear whose profile is open (Stage 7).
    st.markdown(f"#### {student_label}")
    show_profile_table(connection, student_id)

    with st.expander(f"Enroll {student_label} in a course"):
        show_enroll_student(connection, student_id)

    with st.expander(f"Late start or early leave: {student_label}"):
        show_change_enrollment_dates(connection, student_id)

    with st.expander(f"Rename {student_label}"):
        show_rename_student(connection, student_id)

    with st.expander(f"Un-enroll {student_label} from a course"):
        show_unenroll_student(connection, student_id)

    with st.expander(f"Delete {student_label}"):
        show_delete_student(connection, student_id, student_label)


# ---------- Class days & Tutorials (BR-20, BR-21) ----------

def show_session_list(connection, course_code):
    """List a course's class days and tutorials in date order (BR-20, BR-21, BR-23).

    Columns: Date, Day, Type, Records saved and Not recorded; no session IDs (Stage 7).
    """
    records = analytics.build_records_frame(database.get_expected_records(connection))
    rows = []
    for session in database.get_sessions_for_course(connection, course_code):
        session_records = records[records["session_id"] == session["session_id"]]
        not_recorded = int((session_records["status"] == analytics.UNKNOWN).sum())
        rows.append({
            "Date": validation.format_date(session["session_date"]),
            "Day": validation.weekday_name(session["session_date"]),
            "Type": analytics.describe_session_type(
                session["session_id"], session["session_type"]
            ),
            "Records saved": len(session_records) - not_recorded,
            "Not recorded": not_recorded,
        })

    if not rows:
        st.info(f"{course_code} has no class days or tutorials.")
        return

    class_days = 0
    for row in rows:
        if row["Type"] == validation.CLASS:
            class_days += 1
    st.caption(f"{class_days} class days and {len(rows) - class_days} tutorials.")
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


def show_add_tutorial(connection, course_code):
    """Show the form to add a tutorial on any date inside the course period (BR-21)."""
    with st.form(f"add_tutorial_form_{course_code}", clear_on_submit=True):
        chosen_date = st.date_input("Tutorial date", value=None, format=DATE_INPUT_FORMAT)
        st.caption("Any date inside the course period, weekends included. "
                   "Several tutorials on one date are numbered T1, T2...")
        submitted = st.form_submit_button("Add tutorial")

    if not submitted:
        return

    tutorial_date = to_text_or_none(chosen_date)
    if tutorial_date is None:
        st.error(validation.DATE_ERROR)
        return

    try:
        session_id = database.add_tutorial(connection, course_code, tutorial_date)
    except ValueError as error:
        st.error(str(error))
        return

    session = database.get_session(connection, session_id)
    finish_edit(f"Tutorial added to {course_code}: {describe_session(session)}.")


def show_remove_session(connection, course_code):
    """Remove a class day (for example a holiday) or a tutorial, with its records (BR-20)."""
    session_choices = get_session_choices(connection, course_code)
    if not session_choices:
        st.info(f"{course_code} has no class days or tutorials.")
        return

    session_label = st.selectbox(
        "Class day or tutorial", list(session_choices), key=f"remove_session_{course_code}"
    )
    session_id = session_choices[session_label]
    counts = database.count_delete_session(connection, session_id)

    st.warning(
        f"This will remove {session_label} and delete "
        f"{counts['attendance']} attendance record(s) saved for it."
    )
    if ask_to_confirm(f"session_{session_id}"):
        counts = database.delete_session(connection, session_id)
        finish_edit(f"Removed {session_label} from {course_code}: "
                    f"{describe_counts(counts)} deleted.")


def show_class_days_tab(connection):
    """Pick a course; list, add and remove its class days and tutorials (Section 6.1)."""
    st.subheader("Class days & Tutorials")

    course_code = choose_course(connection, "days")
    if course_code is None:
        return

    show_session_list(connection, course_code)

    with st.expander("Add a tutorial"):
        show_add_tutorial(connection, course_code)

    with st.expander("Remove a class day (holiday) or a tutorial"):
        show_remove_session(connection, course_code)


# ---------- Record attendance (FR-07, FR-08) ----------

def build_attendance_table(connection, session_id):
    """Return a DataFrame of enrolled students and their saved status (empty if none)."""
    rows = []
    for record in database.get_session_attendance(connection, session_id):
        rows.append({
            "student_id": record["student_id"],
            "full_name": record["full_name"],
            "status": record["status"],
        })
    return pd.DataFrame(rows, columns=["student_id", "full_name", "status"])


def mark_blank_as_present(table):
    """Return a copy of the table where every student with no status is Present.

    Students who already have a saved status keep it, so a saved Absent is never
    overwritten by "Mark all Present".
    """
    marked = table.copy()
    new_statuses = []
    for status in marked["status"]:
        if status in STATUS_OPTIONS:
            new_statuses.append(status)
        else:
            new_statuses.append("Present")
    marked["status"] = new_statuses
    return marked


def save_attendance_table(connection, session_id, table):
    """Save every chosen status and return counts of what happened."""
    counts = {
        "inserted": 0, "updated": 0, "unchanged": 0, "not_enrolled": 0,
        "outside_enrollment": 0, "blank": 0, "cleared": 0,
    }

    for index, row in table.iterrows():
        status = row["status"]

        # A blank status saves nothing. Clearing a cell does not delete, so if the
        # student already had a saved status, that status is kept.
        if status not in STATUS_OPTIONS:
            saved_status = database.get_status(connection, row["student_id"], session_id)
            if saved_status is None:
                counts["blank"] += 1
            else:
                counts["cleared"] += 1
            continue

        result = database.record_attendance(connection, row["student_id"], session_id, status)
        counts[result] += 1

    return counts


def show_save_result(counts):
    """Show a summary of what was saved."""
    saved = counts["inserted"] + counts["updated"]
    st.success(
        f"Saved {saved} record(s): {counts['inserted']} new, {counts['updated']} changed. "
        f"{counts['unchanged']} unchanged record(s) were not rewritten."
    )

    if counts["blank"] > 0:
        st.info(f"{counts['blank']} student(s) left blank. They stay Unknown.")

    if counts["cleared"] > 0:
        st.warning(
            f"{counts['cleared']} saved status(es) were cleared on screen but kept. "
            "To delete a record, use \"Delete one attendance record\" below."
        )

    if counts["outside_enrollment"] > 0:
        st.error(
            f"{counts['outside_enrollment']} student(s) were not saved: this session's date is "
            "outside their enrollment dates. Change them in Students > student profile > "
            "Late start or early leave first."
        )

    if counts["not_enrolled"] > 0:
        st.error(
            f"{counts['not_enrolled']} student(s) are not enrolled in this course and were "
            "not saved. Enroll them first."
        )


def choose_session(connection, course_code):
    """Show the day box for a course, starting on today if today is a class day."""
    sessions = database.get_sessions_for_course(connection, course_code)
    if not sessions:
        st.info(f"{course_code} has no class days or tutorials.")
        return None

    labels = []
    session_ids = []
    default_index = 0
    today = date.today().isoformat()
    for index, session in enumerate(sessions):
        labels.append(describe_session(session))
        session_ids.append(session["session_id"])
        if session["session_date"] == today and session["session_type"] == validation.CLASS:
            default_index = index

    label = st.selectbox(
        "Day", labels, index=default_index, key=f"record_session_{course_code}"
    )
    return session_ids[labels.index(label)]


def show_record_attendance(connection):
    """Pick block, course and day, then record or correct attendance (FR-07, FR-08)."""
    st.subheader("Record or correct attendance")

    course_code = choose_course(connection, "record")
    if course_code is None:
        return

    session_id = choose_session(connection, course_code)
    if session_id is None:
        return
    session_label = describe_session(database.get_session(connection, session_id))

    table = build_attendance_table(connection, session_id)
    if table.empty:
        st.info(
            f"No students are expected on {session_label}: nobody is enrolled in "
            f"{course_code} on that date. Enroll a student, or check their enrollment dates."
        )
        return

    # "Mark all Present" fills the blank rows; a new editor key shows the new values.
    marked_key = f"mark_all_{session_id}"
    if st.button("Mark all Present", key=f"mark_all_button_{session_id}"):
        st.session_state[marked_key] = st.session_state.get(marked_key, 0) + 1
    marked_times = st.session_state.get(marked_key, 0)
    if marked_times > 0:
        table = mark_blank_as_present(table)

    st.caption(
        "Choose Present, Late, Excused or Absent for each student. A blank status means "
        "Unknown. \"Mark all Present\" fills only the students with no status yet; "
        "then change the exceptions and save."
    )

    with st.form(f"record_form_{session_id}"):
        edited_table = st.data_editor(
            table,
            key=f"editor_{session_id}_{marked_times}",
            hide_index=True,
            width="stretch",
            disabled=["student_id", "full_name"],
            column_config={
                "student_id": st.column_config.TextColumn("Student ID"),
                "full_name": st.column_config.TextColumn("Full name"),
                "status": st.column_config.SelectboxColumn(
                    "Status", options=STATUS_OPTIONS, required=False
                ),
            },
        )
        submitted = st.form_submit_button("Save attendance")

    if submitted:
        counts = save_attendance_table(connection, session_id, edited_table)
        if marked_key in st.session_state:
            del st.session_state[marked_key]
        show_save_result(counts)

    # Shown after saving, so the numbers include what was just saved.
    show_session_counts(connection, session_id, session_label)

    with st.expander("Delete one attendance record"):
        show_delete_attendance_record(connection, session_id, session_label)


def show_session_counts(connection, session_id, session_label):
    """Show the five status counts and the rates for one session."""
    frame = analytics.build_records_frame(database.get_expected_records(connection))
    session_frame = frame[frame["session_id"] == session_id]
    rates = analytics.summarize_frame(session_frame)

    st.caption(
        f"{session_label}: {rates['present']} Present, {rates['late']} Late, "
        f"{rates['excused']} Excused, {rates['absent']} Absent, "
        f"{rates['unknown']} Unknown. "
        f"Attendance rate {analytics.format_rate(rates['attendance_rate'])}, "
        f"completeness {analytics.format_rate(rates['completeness'])}."
    )


def show_delete_attendance_record(connection, session_id, session_label):
    """Delete one saved attendance record of this day; the student becomes Unknown (FR-23)."""
    # Only students with a saved record can have it deleted.
    record_choices = {}
    for record in database.get_session_attendance(connection, session_id):
        if record["status"] is not None:
            label = f"{record['student_id']} - {record['full_name']} ({record['status']})"
            record_choices[label] = record["student_id"]

    if not record_choices:
        st.info("No saved attendance records on this day.")
        return

    record_label = st.selectbox(
        "Student", list(record_choices), key=f"delete_record_student_{session_id}"
    )
    student_id = record_choices[record_label]

    st.warning(
        f"This will remove 1 attendance record: {record_label} on {session_label}. "
        "The student becomes Unknown for that day."
    )
    if ask_to_confirm(f"record_{session_id}_{student_id}"):
        counts = database.delete_attendance_record(connection, student_id, session_id)
        finish_edit(f"Deleted {describe_counts(counts)} for {student_id} on {session_label}.")


# ---------- Settings (BR-22) ----------

def describe_deduction_rule(settings):
    """Return text like 'Deducted marks per course: Late x 1 + Absent x 2 ...' (BR-22)."""
    return (
        f"Deducted marks per course: Late x {settings['late']} + Absent x {settings['absent']}. "
        "Present and Excused deduct nothing; Unknown deducts nothing but is flagged "
        "as \"not recorded\". There is no maximum."
    )


def show_settings(connection):
    """Show and change the marks deducted per Late and per Absent (BR-22)."""
    st.subheader("Settings")
    settings = database.get_deduction_settings(connection)

    # No min/max on the inputs: the rule is checked when saving, with a clear message.
    with st.form("settings_form"):
        late_value = st.number_input(
            "Late deduction (marks)", value=settings["late"], step=1
        )
        absent_value = st.number_input(
            "Absent deduction (marks)", value=settings["absent"], step=1
        )
        st.caption("Whole numbers from 0 to 10.")
        submitted = st.form_submit_button("Save settings")

    st.caption(describe_deduction_rule(settings))

    if not submitted:
        return

    if late_value == settings["late"] and absent_value == settings["absent"]:
        st.info(validation.NO_CHANGE_MESSAGE.format("settings"))
        return

    try:
        database.save_deduction_settings(connection, late_value, absent_value)
    except ValueError as error:
        st.error(str(error))
        return

    finish_edit(
        f"Settings saved: Late deducts {int(late_value)} mark(s), Absent deducts "
        f"{int(absent_value)} mark(s). Every report now uses these values."
    )


# ---------- FR-09: search students ----------

def find_students(connection, search_by, search_text):
    """Return (matching students, error message). The error is None when the search is valid."""
    if search_by == "Student ID":
        student_id = search_text.strip()
        if not validation.is_valid_student_id(student_id):
            return [], validation.STUDENT_ID_ERROR

        student = database.get_student(connection, student_id)
        if student is None:
            return [], None
        return [student], None

    full_name = validation.clean_name(search_text)
    if not validation.is_valid_name(full_name):
        return [], validation.NAME_ERROR

    return database.find_students_by_name(connection, full_name), None


def show_search_students(connection):
    """Show the student search by exact ID or exact name (FR-09)."""
    st.subheader("Search students")

    with st.form("search_form"):
        search_by = st.radio("Search by", ["Student ID", "Full name"], horizontal=True)
        search_text = st.text_input("Search for")
        submitted = st.form_submit_button("Search")

    if not submitted:
        return

    matches, error = find_students(connection, search_by, search_text)

    if error is not None:
        st.error(error)
        return

    if not matches:
        st.info(f"No student found for \"{search_text.strip()}\". Check the spelling or the ID.")
        return

    rows = []
    for student in matches:
        rows.append({
            "Student ID": student["student_id"],
            "Full name": student["full_name"],
            "Courses": join_course_codes(connection, student["student_id"]),
        })

    first_match = matches[0]
    if len(rows) == 1:
        st.write(f"1 match, showing {first_match['student_id']} in the profile below.")
    else:
        st.write(
            f"{len(rows)} matches, showing {first_match['student_id']}; "
            "choose another in the Student box."
        )
    st.session_state["open_profile"] = f"{first_match['student_id']} - {first_match['full_name']}"
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


# ---------- FR-10 and FR-11: import and validate a CSV file ----------

def forget_validation():
    """Remove a stored validation result, so Confirm cannot use an old file."""
    if "import_validation" in st.session_state:
        del st.session_state["import_validation"]


def show_template_download():
    """Offer the empty CSV template (FR-11)."""
    st.download_button(
        "Download empty CSV template",
        data=importer.make_template_csv(),
        file_name="attendance_template.csv",
        mime="text/csv",
    )


def show_last_import_result():
    """Show the result of the last confirmed import, with rejected rows to download (IR-11)."""
    result = st.session_state.get("import_result")
    if result is None:
        return

    st.success(
        f"Import of {result['filename']} finished. Edited by you: {result['edits']}. "
        f"Auto-fixes: {result['fixes']}. "
        f"Accepted suggestions: {result['accepted_suggestions']}. "
        f"Saved: {result['accepted']}. Skipped duplicates: {result['duplicates']}. "
        f"Rejected: {result['rejected']}."
    )

    rejected_table = result["rejected_table"]
    if not rejected_table.empty:
        st.download_button(
            "Download rejected rows (CSV)",
            data=rejected_table.to_csv(index=False),
            file_name="rejected_rows.csv",
            mime="text/csv",
            key="download_rejected_after_import",
        )


def validate_upload(connection, uploaded_file, rows, accepted_keys=(), edits=None):
    """Validate the rows and keep the result in session_state (the database is not changed).

    accepted_keys are the suggestions ticked under Suggestions (FR-31); edits are the
    values typed in the Rejected table, by row number (Stage 7). Validate starts with
    neither, so every suggestion is unticked and no value is edited.
    """
    edits = dict(edits or {})
    result = importer.review_rows(connection, rows, accepted_keys, edits)
    accepted = result["accepted"]
    duplicates = result["duplicates"]

    # Each validation gets new widget keys, so old ticks and edits are not shown again.
    run = st.session_state.get("import_validation_run", 0) + 1
    st.session_state["import_validation_run"] = run

    st.session_state["import_validation"] = {
        "file_id": uploaded_file.file_id,
        "filename": uploaded_file.name,
        "run": run,
        "accepted": accepted,
        "accepted_keys": list(accepted_keys),
        "edits": edits,
        "edit_count": len(result["edits"]),
        "fix_count": len(result["fixes"]),
        "suggestions": result["suggestions"],
        # The user's edits come first, then the automatic fixes.
        "fixes_table": importer.make_fixes_table(result["edits"] + result["fixes"]),
        "cleaned_csv": importer.make_cleaned_csv(accepted, duplicates),
        # Dates are shown as DD/MM/YYYY (BR-23); "accepted" keeps the stored form for saving.
        "accepted_table": analytics.format_date_columns(
            importer.make_table(accepted, with_reason=False)
        ),
        "duplicates_table": analytics.format_date_columns(
            importer.make_table(duplicates, with_reason=True)
        ),
        # Rejected rows keep the file's text (after edits), so they can be corrected.
        "rejected_table": importer.make_table(result["rejected"], with_reason=True),
    }

    # A new validation replaces the result of an earlier import.
    if "import_result" in st.session_state:
        del st.session_state["import_result"]


def show_table_with_reasons(table):
    """Show duplicate or rejected rows with a reason column wide enough to read."""
    st.dataframe(
        table,
        hide_index=True,
        width="stretch",
        column_config={
            importer.ROW_COLUMN: st.column_config.NumberColumn("row", width="small"),
            importer.REASON_COLUMN: st.column_config.TextColumn(
                "reason", width=REASON_COLUMN_WIDTH
            ),
        },
    )


def describe_suggestion_row(suggestion):
    """Return 'Row 13: 011 Fabrice Gasana' for a suggestion's label."""
    return (
        f"Row {suggestion[importer.ROW_COLUMN]}: "
        f"{suggestion['student_id']} {suggestion['full_name']}"
    )


def show_suggestions(connection, uploaded_file, rows, validation_result):
    """Show each suggestion with an Accept tick, or a choice for a status (FR-31).

    Apply suggestions validates the file again with the accepted ones. Nothing is
    saved before Confirm.
    """
    suggestions = validation_result["suggestions"]
    st.markdown("**Suggestions** (nothing is changed unless you accept it)")
    if not suggestions:
        st.caption("No suggestions for this file.")
        return

    run = validation_result["run"]
    with st.form(f"suggestions_form_{run}"):
        accepted_keys = []
        for suggestion in suggestions:
            widget_key = f"suggestion_{run}_{suggestion['key']}"
            label = describe_suggestion_row(suggestion)
            if suggestion["keep_text"] is None:
                ticked = st.checkbox(
                    f"{label}: accept \"{suggestion['text']}\"",
                    value=suggestion["accepted"],
                    key=widget_key,
                )
            else:
                options = [suggestion["keep_text"], suggestion["text"]]
                choice = st.radio(
                    label,
                    options,
                    index=1 if suggestion["accepted"] else 0,
                    horizontal=True,
                    key=widget_key,
                )
                ticked = choice == suggestion["text"]
            if ticked:
                accepted_keys.append(suggestion["key"])

        if st.form_submit_button("Apply suggestions"):
            validate_upload(
                connection, uploaded_file, rows, accepted_keys, validation_result["edits"]
            )
            st.rerun()


def show_rejected_rows(connection, uploaded_file, rows, validation_result):
    """Show the rejected rows in an editable table; Re-check validates the file again.

    The six file columns can be edited; the row number and reason cannot. Edits are
    kept by row number, listed as "edited by you", included in the cleaned file and
    saved only after Confirm (Stage 7).
    """
    rejected_table = validation_result["rejected_table"]
    st.markdown("**Rejected** (fix a value in the table, then click Re-check)")

    run = validation_result["run"]
    with st.form(f"rejected_form_{run}"):
        edited_table = st.data_editor(
            rejected_table,
            key=f"rejected_editor_{run}",
            hide_index=True,
            width="stretch",
            num_rows="fixed",
            disabled=[importer.ROW_COLUMN, importer.REASON_COLUMN],
            column_config={
                importer.ROW_COLUMN: st.column_config.NumberColumn("row", width="small"),
                importer.REASON_COLUMN: st.column_config.TextColumn(
                    "reason", width=REASON_COLUMN_WIDTH
                ),
            },
        )
        submitted = st.form_submit_button("Re-check")

    if submitted:
        edits = importer.collect_edits(
            validation_result["edits"],
            rejected_table.to_dict("records"),
            edited_table.to_dict("records"),
        )
        validate_upload(
            connection, uploaded_file, rows, validation_result["accepted_keys"], edits
        )
        st.rerun()

    st.download_button(
        "Download rejected rows (CSV)",
        data=rejected_table.to_csv(index=False),
        file_name="rejected_rows.csv",
        mime="text/csv",
        key="download_rejected_review",
    )


def show_review(connection, uploaded_file, rows, validation_result):
    """Show the counts, Auto-fixed, Suggestions and the accepted, duplicate and rejected rows."""
    fixes_table = validation_result["fixes_table"]
    accepted_table = validation_result["accepted_table"]
    duplicates_table = validation_result["duplicates_table"]
    rejected_table = validation_result["rejected_table"]
    suggestions = validation_result["suggestions"]

    count_columns = st.columns(5)
    count_columns[0].metric("Auto-fixes", validation_result["fix_count"])
    count_columns[1].metric(
        "Accepted suggestions",
        f"{importer.count_accepted_suggestions(suggestions)} of {len(suggestions)}",
    )
    count_columns[2].metric("Accepted", len(accepted_table))
    count_columns[3].metric("Skipped duplicates", len(duplicates_table))
    count_columns[4].metric("Rejected", len(rejected_table))

    st.markdown("**Auto-fixed** (applied automatically, and your edits)")
    if fixes_table.empty:
        st.caption("Nothing needed fixing.")
    else:
        st.dataframe(fixes_table, hide_index=True, width="stretch")

    show_suggestions(connection, uploaded_file, rows, validation_result)

    st.markdown("**Accepted rows** (saved only after Confirm)")
    if accepted_table.empty:
        st.info("No rows can be imported from this file.")
    else:
        st.dataframe(accepted_table, hide_index=True, width="stretch")

    if not duplicates_table.empty:
        st.markdown("**Skipped duplicates** (already saved or repeated in this file)")
        show_table_with_reasons(duplicates_table)

    if not accepted_table.empty or not duplicates_table.empty:
        st.download_button(
            "Download cleaned file",
            data=validation_result["cleaned_csv"],
            file_name="cleaned_" + validation_result["filename"],
            mime="text/csv",
            key="download_cleaned_review",
        )

    if not rejected_table.empty:
        show_rejected_rows(connection, uploaded_file, rows, validation_result)


def confirm_import(connection, validation_result):
    """Save the accepted rows, then store the result and clear the validation (Result step)."""
    try:
        saved = importer.apply_import(
            connection, validation_result["accepted"], validation_result["filename"]
        )
    except sqlite3.Error:
        # The import runs in one transaction, so a failure leaves the database unchanged.
        st.error(
            "The import failed and nothing was saved. The data may have changed since "
            "validation. Click Validate again, then Confirm."
        )
        return

    st.session_state["import_result"] = {
        "filename": validation_result["filename"],
        "edits": validation_result["edit_count"],
        "fixes": validation_result["fix_count"],
        "accepted_suggestions": importer.count_accepted_suggestions(
            validation_result["suggestions"]
        ),
        "accepted": saved,
        "duplicates": len(validation_result["duplicates_table"]),
        "rejected": len(validation_result["rejected_table"]),
        "rejected_table": validation_result["rejected_table"],
    }
    # Clearing the validation removes the Confirm button, so it cannot be clicked twice.
    forget_validation()
    st.rerun()


def show_import_tab(connection):
    """Show the import workflow: Upload, Preview, Validate, Review, Confirm, Result (IR-09)."""
    st.subheader("Import attendance from a CSV file")
    st.caption(
        "Required columns: " + ", ".join(importer.REQUIRED_COLUMNS)
        + ". Optional: type (Class, the default, or Tutorial). "
        "Dates as DD/MM/YYYY or YYYY-MM-DD. Spaces, capitals, P/L/E/A, short IDs "
        "such as 4 and dates such as 7/9/2026 are fixed automatically."
    )
    show_template_download()

    show_last_import_result()

    # Step 1: Upload
    uploaded_file = st.file_uploader("Upload a CSV file", type=["csv"])
    if uploaded_file is None:
        forget_validation()
        return

    # A different file makes the stored validation out of date.
    validation_result = st.session_state.get("import_validation")
    if validation_result is not None and validation_result["file_id"] != uploaded_file.file_id:
        forget_validation()

    rows, error = importer.read_csv(uploaded_file.getvalue())
    if error is not None:
        st.error(error)
        forget_validation()
        return

    if not rows:
        st.info("The file has the right columns but no data rows.")
        return

    # Step 2: Preview
    st.markdown(f"**Preview of {uploaded_file.name}** ({len(rows)} data rows)")
    st.dataframe(importer.make_table(rows, with_reason=False), hide_index=True, width="stretch")

    # Step 3: Validate
    if st.button("Validate"):
        validate_upload(connection, uploaded_file, rows)

    validation_result = st.session_state.get("import_validation")
    if validation_result is None:
        return

    # Step 4: Review issues, with auto-fixes and suggested fixes (FR-31)
    show_review(connection, uploaded_file, rows, validation_result)

    # Step 5: Confirm
    if validation_result["accepted"]:
        if st.button("Confirm import", type="primary"):
            confirm_import(connection, validation_result)


# ---------- FR-12: filters for the Dashboard and Reports ----------

def get_filter_course_codes(connection, block_id):
    """Return the course codes of a block (block_id None: the courses with no block)."""
    codes = []
    for course in database.get_courses(connection):
        if course["block_id"] == block_id:
            codes.append(course["course_code"])
    return codes


def show_filters(connection):
    """Show the Block -> Course -> Week filters in the sidebar (FR-30, Stage 7).

    "Custom dates" shows a date range for rare cases; with "All blocks" it is the only
    choice. Returns (filtered records, text describing the filters, view), where view
    has the chosen 'block' and 'course' and the 'period_start' that weeks count from.
    The records are None when there is nothing to show yet; the text then explains why.
    """
    st.sidebar.header("Dashboard and Reports filters")

    all_records = analytics.build_records_frame(database.get_expected_records(connection))
    earliest, latest = analytics.get_date_bounds(all_records)
    if earliest is None:
        return None, NO_DATA_MESSAGE, None

    # Block: "All blocks", each block, and "No block" for courses of an older database.
    block_options = {ALL_BLOCKS: ALL_BLOCKS}
    block_options.update(get_block_choices(connection))
    if get_filter_course_codes(connection, None):
        block_options[NO_BLOCK_LABEL] = None
    block_label = st.sidebar.selectbox("Block", list(block_options), key="filter_block")
    block_id = block_options[block_label]

    # Course: only the chosen block's courses. The key includes the block, so the
    # Course box starts again at "All courses" when the block changes.
    course_options = {analytics.ALL_COURSES: analytics.ALL_COURSES}
    for course in database.get_courses(connection):
        if block_id == ALL_BLOCKS or course["block_id"] == block_id:
            course_options[make_course_label(course)] = course["course_code"]
    course_label = st.sidebar.selectbox(
        "Course", list(course_options), key=f"filter_course_{block_id}"
    )
    course_code = course_options[course_label]

    # The period is the course's, else the block's, else all dates.
    block = None
    block_period = None
    if block_id not in (ALL_BLOCKS, None):
        block = database.get_block(connection, block_id)
        block_period = (block["start_date"], block["end_date"])
    course_period = None
    if course_code != analytics.ALL_COURSES:
        course = database.get_course(connection, course_code)
        course_period = (course["start_date"], course["end_date"])
    start_date, end_date = analytics.choose_filter_period(
        all_records, block_period, course_period
    )
    period_text = None

    # Week: only inside one block. A week runs Monday to Sunday, so a weekend
    # tutorial belongs to the week before it.
    if block is not None:
        weeks = analytics.build_week_options(block["start_date"], block["end_date"])
        week_labels = [ALL_WEEKS]
        for week in weeks:
            week_labels.append(week["label"])
        week_label = st.sidebar.selectbox("Week", week_labels, key=f"filter_week_{block_id}")
        if week_label != ALL_WEEKS:
            week = weeks[week_labels.index(week_label) - 1]
            start_date = week["start"]
            end_date = week["end"]
            period_text = week_label

    if st.sidebar.checkbox("Custom dates", key="filter_custom_dates"):
        # No key: when the default changes, the widget starts again with the new range.
        chosen_dates = st.sidebar.date_input(
            "Date range",
            value=(date.fromisoformat(start_date), date.fromisoformat(end_date)),
            format=DATE_INPUT_FORMAT,
        )
        # While the user is picking, the range has only a start date.
        if len(chosen_dates) != 2:
            return None, "Choose an end date to finish the date range.", None
        start_date = chosen_dates[0].isoformat()
        end_date = chosen_dates[1].isoformat()
        period_text = None

    if period_text is None:
        period_text = (
            f"from {validation.format_date(start_date)} to {validation.format_date(end_date)}"
        )

    if course_code == analytics.ALL_COURSES and block_id != ALL_BLOCKS:
        filtered = analytics.filter_records_by_courses(
            all_records, get_filter_course_codes(connection, block_id), start_date, end_date
        )
    else:
        filtered = analytics.filter_records(all_records, course_code, start_date, end_date)

    # Weeks in the charts count from the course's start, else the block's.
    period_start = None
    if block_period is not None:
        period_start = block_period[0]
    if course_period is not None and course_period[0] is not None:
        period_start = course_period[0]

    filter_text = f"Showing: {block_label.split(' - ')[0]}, {course_code}, {period_text}."
    view = {"block": block_id, "course": course_code, "period_start": period_start}
    return filtered, filter_text, view


def has_data_to_show(filtered_records, filter_text):
    """Show the filters, or a message instead of empty tables (FR-18).

    Returns True if there is data to show.
    """
    if filtered_records is None:
        st.info(filter_text)
        return False

    st.caption(filter_text)

    if filtered_records.empty:
        st.info(NO_MATCH_MESSAGE)
        return False

    return True


# ---------- FR-13 to FR-15: Dashboard ----------

def show_status_counts(rates):
    """Show Present, Late, Excused, Absent and Unknown as five metrics in a row (FR-26)."""
    columns = st.columns(5)
    columns[0].metric("Present", rates["present"])
    columns[1].metric("Late", rates["late"])
    columns[2].metric("Excused", rates["excused"])
    columns[3].metric("Absent", rates["absent"])
    columns[4].metric("Unknown", rates["unknown"])


def show_kpi_cards(filtered_records, settings):
    """Show the Dashboard cards, the status counts and what is counted (FR-13, Stage 7).

    The threshold and the alert rules come from their widgets further down the page.
    """
    threshold = st.session_state.get(THRESHOLD_KEY, analytics.DEFAULT_THRESHOLD)
    rules = get_attention_rules()
    kpis = analytics.calculate_kpis(
        filtered_records, settings["late"], settings["absent"], threshold, rules
    )

    cards = [
        ("Attendance rate", analytics.format_rate(kpis["attendance_rate"]),
         "(Present + Late) / (Present + Late + Absent)"),
        ("Completeness", analytics.format_rate(kpis["completeness"]),
         "Recorded / expected"),
        ("Deducted marks", kpis["deducted"],
         f"Total: Late x {settings['late']} + Absent x {settings['absent']}"),
        ("Students below threshold", kpis["below_threshold"],
         f"Attendance rate below {threshold}% (slider below)"),
        ("Need attention", kpis["need_attention"],
         "Students meeting at least one alert rule in a course (table below)"),
    ]
    columns = st.columns(len(cards))
    for column, (label, value, help_text) in zip(columns, cards):
        with column.container(border=True):
            st.metric(label, value, help=help_text)

    counts = [kpis["present"], kpis["late"], kpis["excused"], kpis["absent"], kpis["unknown"]]
    parts = []
    for color, label, count in zip(STATUS_COLORS, STATUS_DOT_LABELS, counts):
        parts.append(f'<span style="color:{color}">&#9679;</span> {label} <b>{count}</b>')
    st.markdown(" &nbsp;&nbsp; ".join(parts), unsafe_allow_html=True)
    st.caption(
        f"{kpis['students']} students · {kpis['class_days']} class days · "
        f"{kpis['tutorials']} tutorials"
    )


def show_drilldown_charts(filtered_records, view):
    """Show the rate and status charts at the level the filters choose (FR-14, FR-20).

    All blocks: a bar per block. One block: per course. One course: per week, or
    per day with "Show by day" (Stage 7).
    """
    by_day = False
    if view["course"] != analytics.ALL_COURSES:
        by_day = st.toggle("Show by day", key="chart_by_day")

    level, summary = analytics.build_drilldown_chart_data(
        filtered_records, view["block"], view["course"], by_day, view["period_start"]
    )
    show_rate_chart(summary, level)
    st.divider()
    show_status_chart(summary, level)


def make_x_axis(level):
    """Return the x axis of both charts: bars in the order given, labels named by level."""
    angle = 0
    if level == analytics.LEVEL_DAY:
        angle = -45
    # sort=None keeps the order from analytics.py instead of sorting the labels.
    return alt.X(analytics.CHART_LABEL_COLUMN, type="nominal", sort=None,
                 title=level.capitalize(), axis=alt.Axis(labelAngle=angle, labelLimit=200))


def show_rate_chart(summary, level):
    """Show the attendance rate per bar, with the % on each bar and the axis 0 to 100."""
    st.subheader(analytics.make_chart_title("Attendance rate", level))

    bars = analytics.build_rate_bars(summary)
    if bars.empty:
        st.info("No attendance has been recorded for these filters yet, so there is nothing "
                "to chart.")
        return

    labels = []
    for rate in bars[analytics.CHART_VALUE_COLUMN]:
        labels.append(analytics.format_rate(rate))
    bars["Label"] = labels

    base = alt.Chart(bars).encode(
        x=make_x_axis(level),
        y=alt.Y(analytics.CHART_VALUE_COLUMN, type="quantitative",
                scale=alt.Scale(domain=[0, 100])),
    )
    chart = base.mark_bar(color=STATUS_COLORS[0]) + base.mark_text(dy=-8).encode(text="Label")
    st.altair_chart(chart, width="stretch")
    st.caption("Excused and not recorded sessions are left out of the rate.")


def show_status_chart(summary, level):
    """Show a stacked bar per block, course, week or day: the five status counts (FR-20)."""
    st.subheader(analytics.make_chart_title("Recording status", level))

    if summary.empty:
        st.info("Nothing to show for these filters.")
        return

    chosen_statuses = st.multiselect(
        "Show statuses", analytics.STATUS_ORDER, default=analytics.STATUS_ORDER,
        key="status_filter",
    )
    if not chosen_statuses:
        st.info("No statuses selected. Choose at least one status to show the chart.")
        return

    all_statuses = analytics.make_status_chart_long(summary)
    chart_data = analytics.keep_statuses(all_statuses, chosen_statuses)
    # The colour scale always lists all statuses, so each keeps its colour
    # whatever is selected.
    chart = alt.Chart(chart_data).mark_bar().encode(
        x=make_x_axis(level),
        y=alt.Y(analytics.CHART_COUNT_COLUMN, type="quantitative", stack="zero"),
        color=alt.Color(
            analytics.CHART_STATUS_COLUMN, type="nominal",
            scale=alt.Scale(domain=analytics.STATUS_ORDER, range=STATUS_COLORS),
        ),
        order=alt.Order(analytics.CHART_ORDER_COLUMN, type="quantitative"),
    )
    st.altair_chart(chart, width="stretch")
    st.caption(
        "Grey shows enrolled students with no record: missing data, not absence. "
        "Excused is recorded but not counted in the attendance rate."
    )


def show_threshold_list(filtered_records):
    """List students below a chosen attendance rate, lowest first (FR-15)."""
    st.subheader("Students below a threshold")

    threshold = st.slider(
        "Attendance rate threshold (%)", min_value=0, max_value=100,
        value=analytics.DEFAULT_THRESHOLD, key=THRESHOLD_KEY,
    )

    student_summary = analytics.build_student_summary(filtered_records)
    below, no_rate = analytics.split_by_threshold(student_summary, threshold)

    if below.empty:
        st.success(f"No students are below {threshold}%.")
    else:
        st.dataframe(analytics.format_summary_table(below), hide_index=True, width="stretch")

    if not no_rate.empty:
        st.markdown("**Students with no recorded sessions** (attendance rate N/A)")
        st.dataframe(analytics.format_summary_table(no_rate), hide_index=True, width="stretch")


def get_attention_rules():
    """Return the alert rules from their inputs, or the defaults before they are drawn."""
    rules = {}
    for name, key in ATTENTION_KEYS.items():
        rules[name] = int(st.session_state.get(key, analytics.DEFAULT_ATTENTION_RULES[name]))
    return rules


def show_students_needing_attention(filtered_records, settings):
    """List each student and course that meets at least one alert rule (FR-21).

    Replaces the absence alerts. The rules are set in the "Alert rules" row; the
    deducted marks use the current settings, and the sidebar filters are respected.
    """
    st.subheader("Students needing attention")

    st.markdown("**Alert rules**")
    defaults = analytics.DEFAULT_ATTENTION_RULES
    columns = st.columns(4)
    columns[0].number_input(
        "Absent the last N days in a row", min_value=1, step=1,
        value=defaults["recent_absences"], key=ATTENTION_KEYS["recent_absences"],
    )
    columns[1].number_input(
        "Absences at least", min_value=1, step=1,
        value=defaults["absences"], key=ATTENTION_KEYS["absences"],
    )
    columns[2].number_input(
        "Attendance rate below (%)", min_value=0, max_value=100, step=1,
        value=defaults["rate"], key=ATTENTION_KEYS["rate"],
    )
    columns[3].number_input(
        "Deducted marks at least", min_value=1, step=1,
        value=defaults["marks"], key=ATTENTION_KEYS["marks"],
    )

    table = analytics.build_attention_table(
        filtered_records, settings["late"], settings["absent"], get_attention_rules()
    )
    if table.empty:
        st.success("No students need attention with these rules.")
        return

    st.dataframe(
        analytics.format_date_columns(table), hide_index=True, width="stretch",
        column_config={"Reasons": st.column_config.TextColumn("Reasons", width="large")},
    )
    st.caption(
        "One row per student per course. Sorted by the number of reasons, then the lowest "
        f"attendance rate. {describe_deduction_rule(settings)}"
    )


def show_dashboard_tab(connection, filtered_records, filter_text, view):
    """Show the Dashboard tab: cards, drill-down charts, threshold list and the students
    needing attention."""
    if not has_data_to_show(filtered_records, filter_text):
        return

    settings = database.get_deduction_settings(connection)
    show_kpi_cards(filtered_records, settings)
    st.divider()
    show_drilldown_charts(filtered_records, view)
    st.divider()
    show_threshold_list(filtered_records)
    st.divider()
    show_students_needing_attention(filtered_records, settings)


# ---------- FR-16 and FR-17: Reports ----------

def show_table_with_download(table, file_name, button_key):
    """Show a table and a CSV download made from that same table (FR-17).

    Dates are shown as DD/MM/YYYY on screen and in the download (BR-23).
    """
    table = analytics.format_date_columns(table)
    st.dataframe(table, hide_index=True, width="stretch")
    st.download_button(
        "Download as CSV",
        data=table.to_csv(index=False),
        file_name=file_name,
        mime="text/csv",
        key=button_key,
    )


def show_reports_tab(connection, filtered_records, filter_text):
    """Show the Reports tab: all students by default, or one chosen student (FR-16, FR-19)."""
    if not has_data_to_show(filtered_records, filter_text):
        return

    settings = database.get_deduction_settings(connection)
    student_choices = get_student_choices(connection)
    options = [ALL_STUDENTS] + list(student_choices)
    student_label = st.selectbox("Student", options, key="report_student")

    if student_label == ALL_STUDENTS:
        show_all_students_report(connection, filtered_records, settings)
    else:
        student_id = student_choices[student_label]
        show_single_student_report(
            connection, student_id, student_label, filtered_records, settings
        )


def show_all_students_report(connection, filtered_records, settings):
    """Show the overall numbers, the per-student summary with deducted marks, the
    attendance records and the deductions export (FR-16, FR-29)."""
    st.subheader("All students")
    show_summary_metrics(filtered_records)

    st.markdown("**Per-student summary**")
    student_summary = analytics.add_deduction_columns(
        analytics.build_student_summary(filtered_records), settings["late"], settings["absent"]
    )
    summary_table = analytics.format_summary_table(student_summary)
    show_table_with_download(summary_table, "student_summary.csv", "download_summary")
    st.caption(describe_deduction_rule(settings))

    st.markdown("**Attendance records**")
    attendance_report = analytics.build_attendance_report(filtered_records)
    show_table_with_download(attendance_report, "attendance_report.csv", "download_attendance")

    show_deductions_export(filtered_records, settings)
    show_class_register(connection, settings)


def show_deductions_export(filtered_records, settings):
    """Show one course's deductions, ready for the grade sheet, with a CSV download (FR-29)."""
    st.markdown("**Deductions export**")

    course_codes = sorted(filtered_records["course_code"].unique())
    course_code = st.selectbox("Course", course_codes, key="deductions_course")

    export = analytics.build_course_deductions(
        filtered_records, course_code, settings["late"], settings["absent"]
    )
    show_table_with_download(export, f"deductions_{course_code}.csv", "download_deductions")
    st.caption(
        "One row per enrolled student, using the filters above. \"Not recorded\" counts "
        "the missing records, which deduct nothing."
    )


# ---------- FR-19: single student report ----------

def show_summary_metrics(records, settings=None):
    """Show the five status counts, attendance rate and completeness for some records.

    With settings (one student's report), the deducted marks are shown too (FR-29).
    """
    rates = analytics.summarize_frame(records)

    show_status_counts(rates)
    rate_columns = st.columns(5)
    rate_columns[0].metric("Attendance rate", analytics.format_rate(rates["attendance_rate"]))
    rate_columns[1].metric("Completeness", analytics.format_rate(rates["completeness"]))

    if settings is not None:
        deducted = analytics.calculate_deduction(
            rates["late"], rates["absent"], settings["late"], settings["absent"]
        )
        rate_columns[2].metric(analytics.DEDUCTED_COLUMN, deducted)
        flag = analytics.describe_not_recorded(rates["unknown"])
        if flag:
            rate_columns[3].metric("Note", flag)


def show_single_student_report(connection, student_id, student_label, filtered_records,
                                settings):
    """Show one student's numbers, courses and session history, using the filters (FR-19)."""
    st.subheader(f"Report for {student_label}")

    student_records = analytics.filter_student(filtered_records, student_id)
    if student_records.empty:
        st.info(
            f"No sessions for {student_label} match these filters. "
            "Choose another course or a wider date range."
        )
        return

    show_summary_metrics(student_records, settings)

    # Shown even for one course, because it holds the absence streaks (FR-21)
    # and the deducted marks per course (FR-29).
    st.markdown("**By course**")
    course_summary = analytics.add_deduction_columns(
        analytics.build_course_summary(student_records), settings["late"], settings["absent"]
    )
    course_table = analytics.format_summary_table(course_summary)
    show_table_with_download(
        course_table, f"student_{student_id}_by_course.csv", "download_by_course"
    )
    st.caption(describe_deduction_rule(settings))

    st.markdown("**Session history**")
    history = analytics.build_student_history(student_records)
    show_table_with_download(history, f"student_{student_id}_history.csv", "download_history")

    show_weekly_view(connection, student_id, settings)


# ---------- FR-27: weekly view ----------

def show_weekly_view(connection, student_id, settings):
    """Show one student's week-by-week grid for one of their courses (FR-27).

    The grid covers the whole course, not the sidebar dates, so every week is complete.
    """
    st.markdown("**Weekly view**")

    course_choices = get_student_course_choices(connection, student_id)
    if not course_choices:
        st.info("This student is not enrolled in any course.")
        return

    course_label = st.selectbox(
        "Course", list(course_choices), key=f"weekly_course_{student_id}"
    )
    course_code = course_choices[course_label]
    course = database.get_course(connection, course_code)
    sessions = database.get_sessions_for_course(connection, course_code)
    if not sessions:
        st.info(f"{course_code} has no class days or tutorials.")
        return

    records = analytics.build_records_frame(database.get_expected_records(connection))
    records = analytics.filter_student(records, student_id)
    records = records[records["course_code"] == course_code]

    grid = analytics.build_weekly_view(
        sessions, records, course["start_date"], course["end_date"], analytics.WEEKLY_SYMBOLS
    )
    st.dataframe(grid, hide_index=True, width="stretch")
    st.caption(
        "✅ Present, 🕐 Late, 📝 Excused, ❌ Absent, ❔ Not recorded, "
        "— no class (removed day, or outside the student's enrollment period)."
    )

    show_summary_metrics(records, settings)

    # The download uses plain words instead of symbols, so it opens well in a spreadsheet.
    words_grid = analytics.build_weekly_view(
        sessions, records, course["start_date"], course["end_date"], analytics.WEEKLY_WORDS
    )
    st.download_button(
        "Download as CSV",
        data=words_grid.to_csv(index=False),
        file_name=f"weekly_{student_id}_{course_code}.csv",
        mime="text/csv",
        key=f"download_weekly_{student_id}_{course_code}",
    )


# ---------- FR-28: class register ----------

def show_class_register(connection, settings):
    """Show the class register of one course, for all weeks or one week (FR-28)."""
    st.markdown("**Class register**")

    course_code = choose_course(connection, "register")
    if course_code is None:
        return

    course = database.get_course(connection, course_code)
    sessions = database.get_sessions_for_course(connection, course_code)
    if not sessions:
        st.info(f"{course_code} has no class days or tutorials.")
        return

    week_labels = analytics.list_week_labels(sessions, course["start_date"], course["end_date"])
    week_label = st.selectbox(
        "Week", [ALL_WEEKS] + week_labels, key=f"register_week_{course_code}"
    )
    week = None
    if week_label != ALL_WEEKS:
        week = week_labels.index(week_label) + 1

    records = analytics.build_records_frame(database.get_expected_records(connection))
    records = records[records["course_code"] == course_code]
    if records.empty:
        st.info(f"No students are enrolled in {course_code} yet.")
        return

    register = analytics.build_class_register(
        sessions, records, settings["late"], settings["absent"], week
    )
    file_name = f"register_{course_code}.csv"
    if week is not None:
        file_name = f"register_{course_code}_week{week}.csv"
    show_table_with_download(register, file_name, f"download_register_{course_code}")
    st.caption(
        "P Present, L Late, E Excused, A Absent, ? not recorded, — outside the student's "
        f"enrollment period. {describe_deduction_rule(settings)}"
    )


# ---------- Tabs ----------

def show_manage_tab(connection):
    """Show the Manage Attendance sub-tabs: each thing is changed in its own sub-tab (6.1).

    Every change ends with a rerun (finish_edit), so all lists are up to date and
    its message is shown here, above the sub-tabs.
    """
    show_edit_message()
    courses_tab, students_tab, days_tab, record_tab, settings_tab = st.tabs(
        ["Blocks & Courses", "Students", "Class days & Tutorials", "Record attendance",
         "Settings"]
    )

    with courses_tab:
        show_add_block(connection)
        st.divider()
        show_add_course(connection)
        st.divider()
        show_block_list(connection)
        show_course_list(connection)
        st.divider()
        show_course_details(connection)
        st.divider()
        show_edit_block(connection)
        st.divider()
        show_delete_block(connection)

    with students_tab:
        # Search first, so the user can check whether a student exists before adding.
        show_search_students(connection)
        st.divider()
        show_student_profile(connection)
        st.divider()
        show_add_student(connection)

    with days_tab:
        show_class_days_tab(connection)

    with record_tab:
        show_record_attendance(connection)

    with settings_tab:
        show_settings(connection)


def show_demo_controls(connection):
    """Show the demo warning and the 'Reset demo data' button at the bottom of the sidebar."""
    st.sidebar.divider()
    st.sidebar.caption(
        "Demo version: data may reset when the app restarts. Do not enter real personal data."
    )

    message = st.session_state.pop("demo_message", None)
    if message is not None:
        st.sidebar.success(message)

    understood = st.sidebar.checkbox(
        "I understand this replaces all data with the demo data", key="confirm_reset_demo"
    )
    if st.sidebar.button("Reset demo data", disabled=not understood, key="reset_demo"):
        seed_demo.reset_demo_data(connection)
        st.session_state["demo_message"] = "Demo data restored."
        # Untick the box, so the next reset needs a new confirmation.
        del st.session_state["confirm_reset_demo"]
        st.rerun()


def main():
    """Build the page with its four tabs (FR-01)."""
    # With toolbarMode "minimal" the menu is shown only when the app has its own item;
    # About keeps it, so the theme (System, Light, Dark) can be switched there.
    st.set_page_config(
        page_title="Attendance V3",
        layout="wide",
        menu_items={"About": "Attendance Management and Analytics, Version 3.1. "
                             "Programming with Python, AIMS Rwanda."},
    )
    st.title("Attendance Management and Analytics")

    connection = database.get_connection()
    database.create_tables(connection)
    # A fresh online copy starts empty, so give it the demo data to show.
    seed_demo.seed_if_empty(connection)

    dashboard_tab, manage_tab, import_tab, reports_tab = st.tabs(
        ["Dashboard", "Manage Attendance", "Import & Validate", "Reports"]
    )

    # The tabs that change data run first, so the Dashboard and Reports
    # include anything saved in this same run. The tab order on screen stays the same.
    with manage_tab:
        show_manage_tab(connection)

    with import_tab:
        show_import_tab(connection)

    filtered_records, filter_text, view = show_filters(connection)
    show_demo_controls(connection)

    with dashboard_tab:
        show_dashboard_tab(connection, filtered_records, filter_text, view)

    with reports_tab:
        show_reports_tab(connection, filtered_records, filter_text)

    connection.close()


if __name__ == "__main__":
    main()
