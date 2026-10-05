"""Streamlit interface for the attendance system: streamlit run app.py

This file only shows the screens. Rules live in validation.py,
SQL lives in database.py, and calculations live in analytics.py.
"""

import pandas as pd
import streamlit as st

import analytics
import database
import validation

STATUS_OPTIONS = ["Present", "Absent"]
NO_COURSES_MESSAGE = "No courses yet. Create a course first."
NO_STUDENTS_MESSAGE = "No students yet. Add a student first."


# ---------- Helpers ----------

def get_course_choices(connection):
    """Return a dict that maps a label like 'PY101 - Programming' to its course code."""
    choices = {}
    for course in database.get_courses(connection):
        label = f"{course['course_code']} - {course['course_name']}"
        choices[label] = course["course_code"]
    return choices


def get_student_choices(connection):
    """Return a dict that maps a label like '001 - Nadia Hirwa' to its student ID."""
    choices = {}
    for student in database.get_all_students(connection):
        label = f"{student['student_id']} - {student['full_name']}"
        choices[label] = student["student_id"]
    return choices


def get_session_choices(connection, course_code):
    """Return a dict that maps a label like 'PY101-W1 (2026-09-07)' to its session ID."""
    choices = {}
    for session in database.get_sessions_for_course(connection, course_code):
        label = f"{session['session_id']} ({session['session_date']})"
        choices[label] = session["session_id"]
    return choices


def join_course_codes(connection, student_id):
    """Return a student's course codes as text, like 'DS102, PY101'."""
    codes = []
    for course in database.get_student_courses(connection, student_id):
        codes.append(course["course_code"])

    if not codes:
        return "Not enrolled"
    return ", ".join(codes)


# ---------- FR-03: create a course ----------

def show_add_course(connection):
    """Show the form to create a course (FR-03)."""
    st.subheader("Create a course")

    with st.form("add_course_form", clear_on_submit=True):
        code_text = st.text_input("Course code", placeholder="PY101")
        name_text = st.text_input("Course name", placeholder="Programming with Python")
        submitted = st.form_submit_button("Create course")

    if not submitted:
        return

    course_code = validation.normalize_course_code(code_text)
    course_name = validation.clean_course_name(name_text)

    if course_code is None:
        st.error(validation.COURSE_CODE_ERROR)
    elif course_name is None:
        st.error(validation.COURSE_NAME_ERROR)
    elif database.course_exists(connection, course_code):
        st.error(validation.COURSE_EXISTS_ERROR.format(course_code))
    else:
        database.add_course(connection, course_code, course_name)
        st.success(f"Course {course_code} - {course_name} created.")


# ---------- FR-04: add and enroll a student ----------

def show_add_student(connection):
    """Show the form to add a student and enroll them in a course (FR-04)."""
    st.subheader("Add a student")

    course_choices = get_course_choices(connection)
    if not course_choices:
        st.info(NO_COURSES_MESSAGE)
        return

    with st.form("add_student_form"):
        id_text = st.text_input("Student ID", placeholder="001")
        name_text = st.text_input("Full name", placeholder="Nadia Hirwa")
        course_label = st.selectbox("Enroll in course", list(course_choices))
        confirm_same_name = st.checkbox("I confirm this is a different student with the same name")
        submitted = st.form_submit_button("Add student")

    if not submitted:
        return

    student_id = id_text.strip()
    full_name = validation.clean_name(name_text)
    course_code = course_choices[course_label]

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
    database.enroll_student(connection, student_id, course_code)
    st.success(f"Student {student_id} - {full_name} added and enrolled in {course_code}.")


# ---------- FR-05: enroll an existing student ----------

def show_enroll_student(connection):
    """Show the form to enroll an existing student in another course (FR-05)."""
    st.subheader("Enroll a student in another course")

    student_choices = get_student_choices(connection)
    course_choices = get_course_choices(connection)

    if not student_choices:
        st.info(NO_STUDENTS_MESSAGE)
        return

    with st.form("enroll_form"):
        student_label = st.selectbox("Student", list(student_choices))
        course_label = st.selectbox("Course", list(course_choices))
        submitted = st.form_submit_button("Enroll")

    if not submitted:
        return

    student_id = student_choices[student_label]
    course_code = course_choices[course_label]

    if database.is_enrolled(connection, student_id, course_code):
        st.error(validation.ALREADY_ENROLLED_ERROR.format(student_id, course_code))
    else:
        database.enroll_student(connection, student_id, course_code)
        st.success(f"Student {student_id} enrolled in {course_code}.")


# ---------- FR-06: create a session ----------

def show_add_session(connection):
    """Show the form to create a session for a course (FR-06)."""
    st.subheader("Create a session")

    course_choices = get_course_choices(connection)
    if not course_choices:
        st.info(NO_COURSES_MESSAGE)
        return

    with st.form("add_session_form", clear_on_submit=True):
        course_label = st.selectbox("Course", list(course_choices))
        id_text = st.text_input("Session ID", placeholder="PY101-W5")
        date_text = st.text_input("Session date (YYYY-MM-DD)", placeholder="2026-10-05")
        submitted = st.form_submit_button("Create session")

    if not submitted:
        return

    course_code = course_choices[course_label]
    session_id = validation.normalize_session_id(id_text)
    session_date = validation.parse_date(date_text)

    if session_id is None:
        st.error(validation.SESSION_ID_ERROR)
    elif session_date is None:
        st.error(validation.DATE_ERROR)
    elif database.get_session(connection, session_id) is not None:
        st.error(validation.SESSION_EXISTS_ERROR.format(session_id))
    else:
        database.add_session(connection, session_id, course_code, session_date)
        st.success(f"Session {session_id} on {session_date} created for {course_code}.")


# ---------- FR-07 and FR-08: record and correct attendance ----------

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


def save_attendance_table(connection, session_id, table):
    """Save every chosen status and return counts of what happened."""
    counts = {"inserted": 0, "updated": 0, "unchanged": 0, "not_enrolled": 0, "blank": 0}

    for index, row in table.iterrows():
        status = row["status"]

        # A blank status stays Unknown: nothing is saved for that student.
        if status not in STATUS_OPTIONS:
            counts["blank"] += 1
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

    if counts["not_enrolled"] > 0:
        st.error(
            f"{counts['not_enrolled']} student(s) are not enrolled in this course and were "
            "not saved. Enroll them first."
        )


def show_record_attendance(connection):
    """Show the editable attendance list for one session (FR-07, FR-08)."""
    st.subheader("Record or correct attendance")

    course_choices = get_course_choices(connection)
    if not course_choices:
        st.info(NO_COURSES_MESSAGE)
        return

    course_label = st.selectbox("Course", list(course_choices), key="record_course")
    course_code = course_choices[course_label]

    session_choices = get_session_choices(connection, course_code)
    if not session_choices:
        st.info(f"No sessions for {course_code} yet. Create a session first.")
        return

    session_label = st.selectbox("Session", list(session_choices), key="record_session")
    session_id = session_choices[session_label]

    table = build_attendance_table(connection, session_id)
    if table.empty:
        st.info(f"No students are enrolled in {course_code} yet. Add or enroll a student first.")
        return

    st.caption("Choose Present or Absent for each student. A blank status means Unknown.")

    with st.form("record_form"):
        edited_table = st.data_editor(
            table,
            key=f"editor_{session_id}",
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
        show_save_result(counts)

    # Shown after saving, so the numbers include what was just saved.
    show_session_counts(connection, session_id)


def show_session_counts(connection, session_id):
    """Show Present, Absent, Unknown and the rates for one session."""
    frame = analytics.build_records_frame(database.get_expected_records(connection))
    session_frame = frame[frame["session_id"] == session_id]
    rates = analytics.summarize_frame(session_frame)

    st.caption(
        f"{session_id}: {rates['present']} Present, {rates['absent']} Absent, "
        f"{rates['unknown']} Unknown. "
        f"Attendance rate {analytics.format_rate(rates['attendance_rate'])}, "
        f"completeness {analytics.format_rate(rates['completeness'])}."
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

    st.write(f"{len(rows)} match(es) found.")
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


# ---------- Tabs ----------

def show_coming_soon(tab_name):
    """Show a placeholder for a tab that is built in a later stage."""
    st.info(f"{tab_name}: Coming soon.")


def show_manage_tab(connection):
    """Show every Manage Attendance section, one after another."""
    show_add_course(connection)
    st.divider()
    show_add_student(connection)
    st.divider()
    show_enroll_student(connection)
    st.divider()
    show_add_session(connection)
    st.divider()
    show_record_attendance(connection)
    st.divider()
    show_search_students(connection)


def main():
    """Build the page with its four tabs (FR-01)."""
    st.set_page_config(page_title="Attendance V2", layout="wide")
    st.title("Attendance Management and Analytics")

    connection = database.get_connection()
    database.create_tables(connection)

    dashboard_tab, manage_tab, import_tab, reports_tab = st.tabs(
        ["Dashboard", "Manage Attendance", "Import & Validate", "Reports"]
    )

    with dashboard_tab:
        show_coming_soon("Dashboard")

    with manage_tab:
        show_manage_tab(connection)

    with import_tab:
        show_coming_soon("Import & Validate")

    with reports_tab:
        show_coming_soon("Reports")

    connection.close()


if __name__ == "__main__":
    main()
