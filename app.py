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
import validation

STATUS_OPTIONS = ["Present", "Absent"]
# Present blue, Absent orange, Unknown grey: colour-blind friendly (Okabe-Ito palette),
# and grey suggests "missing". Same order as analytics.STATUS_ORDER.
STATUS_COLORS = ["#0072B2", "#E69F00", "#999999"]
# Width in pixels, so the longest import reasons fit without being cut off.
REASON_COLUMN_WIDTH = 1500
ALL_STUDENTS = "All students"
NO_COURSES_MESSAGE = "No courses yet. Create a course first."
NO_STUDENTS_MESSAGE = "No students yet. Add a student first."
NO_DATA_MESSAGE = (
    "No sessions with enrolled students yet. Create a course, a session and a student "
    "in Manage Attendance, or import a CSV file."
)
NO_MATCH_MESSAGE = (
    "No sessions match these filters. Choose another course or a wider date range."
)


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

    if not course_choices:
        st.info(NO_COURSES_MESSAGE)
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
    counts = {
        "inserted": 0, "updated": 0, "unchanged": 0, "not_enrolled": 0,
        "blank": 0, "cleared": 0,
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
            "To delete a record, use Manage Attendance > Edit & Delete."
        )

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


# ---------- FR-22 and FR-23: rename and delete ----------

def finish_edit(message):
    """Remember a success message and rerun, so every list on the page is up to date."""
    st.session_state["edit_message"] = message
    st.rerun()


def show_edit_message():
    """Show the message of the last rename or delete once, then forget it."""
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
        "courses": "course(s)",
    }
    parts = []
    for key in counts:
        parts.append(f"{counts[key]} {names[key]}")
    return ", ".join(parts)


def show_rename_student(connection):
    """Change a student's name with the same rules as Add Student (FR-22)."""
    st.subheader("Rename a student")

    student_choices = get_student_choices(connection)
    if not student_choices:
        st.info(NO_STUDENTS_MESSAGE)
        return

    student_label = st.selectbox("Student", list(student_choices), key="rename_student")
    student_id = student_choices[student_label]
    current_name = database.get_student(connection, student_id)["full_name"]

    with st.form("rename_student_form"):
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


def show_rename_course(connection):
    """Change a course's name. The course code stays the same (FR-22)."""
    st.subheader("Rename a course")

    course_choices = get_course_choices(connection)
    if not course_choices:
        st.info(NO_COURSES_MESSAGE)
        return

    course_label = st.selectbox("Course", list(course_choices), key="rename_course")
    course_code = course_choices[course_label]
    current_name = database.get_course_name(connection, course_code)

    with st.form("rename_course_form"):
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


def show_delete_attendance_record(connection):
    """Delete one saved attendance record; the student becomes Unknown (FR-23)."""
    st.subheader("Delete one attendance record")

    course_choices = get_course_choices(connection)
    if not course_choices:
        st.info(NO_COURSES_MESSAGE)
        return

    course_label = st.selectbox("Course", list(course_choices), key="delete_record_course")
    session_choices = get_session_choices(connection, course_choices[course_label])
    if not session_choices:
        st.info("This course has no sessions.")
        return

    session_label = st.selectbox("Session", list(session_choices), key="delete_record_session")
    session_id = session_choices[session_label]

    # Only students with a saved record can have it deleted.
    record_choices = {}
    for record in database.get_session_attendance(connection, session_id):
        if record["status"] is not None:
            label = f"{record['student_id']} - {record['full_name']} ({record['status']})"
            record_choices[label] = record["student_id"]

    if not record_choices:
        st.info("No saved attendance records in this session.")
        return

    record_label = st.selectbox("Student", list(record_choices), key="delete_record_student")
    student_id = record_choices[record_label]

    st.warning(
        f"This will remove 1 attendance record: {record_label} in {session_id}. "
        "The student becomes Unknown for that session."
    )
    if ask_to_confirm(f"record_{session_id}_{student_id}"):
        counts = database.delete_attendance_record(connection, student_id, session_id)
        finish_edit(f"Deleted {describe_counts(counts)} for {student_id} in {session_id}.")


def show_unenroll_student(connection):
    """Un-enroll a student from one course, with their records for it (FR-23)."""
    st.subheader("Un-enroll a student from a course")

    student_choices = get_student_choices(connection)
    if not student_choices:
        st.info(NO_STUDENTS_MESSAGE)
        return

    student_label = st.selectbox("Student", list(student_choices), key="unenroll_student")
    student_id = student_choices[student_label]

    course_codes = []
    for course in database.get_student_courses(connection, student_id):
        course_codes.append(course["course_code"])

    if not course_codes:
        st.info(f"{student_label} is not enrolled in any course.")
        return

    course_code = st.selectbox("Course", course_codes, key="unenroll_course")
    counts = database.count_unenroll(connection, student_id, course_code)

    st.warning(
        f"This will remove {describe_counts(counts)}: {student_label} leaves {course_code} "
        f"and their records for {course_code} sessions are deleted."
    )
    if ask_to_confirm(f"unenroll_{student_id}_{course_code}"):
        counts = database.unenroll_student(connection, student_id, course_code)
        finish_edit(
            f"Un-enrolled {student_id} from {course_code}: removed {describe_counts(counts)}."
        )


def show_delete_student(connection):
    """Delete a student with all their enrollments and records (FR-23)."""
    st.subheader("Delete a student")

    student_choices = get_student_choices(connection)
    if not student_choices:
        st.info(NO_STUDENTS_MESSAGE)
        return

    student_label = st.selectbox("Student", list(student_choices), key="delete_student")
    student_id = student_choices[student_label]
    counts = database.count_delete_student(connection, student_id)

    st.warning(
        f"This will remove {describe_counts(counts)}: {student_label} and everything "
        "recorded for them. The ID can be used again afterwards."
    )
    if ask_to_confirm(f"student_{student_id}"):
        counts = database.delete_student(connection, student_id)
        finish_edit(f"Deleted student {student_label}: removed {describe_counts(counts)}.")


def show_delete_session(connection):
    """Delete a session and its attendance records (FR-23)."""
    st.subheader("Delete a session")

    course_choices = get_course_choices(connection)
    if not course_choices:
        st.info(NO_COURSES_MESSAGE)
        return

    course_label = st.selectbox("Course", list(course_choices), key="delete_session_course")
    session_choices = get_session_choices(connection, course_choices[course_label])
    if not session_choices:
        st.info("This course has no sessions.")
        return

    session_label = st.selectbox("Session", list(session_choices), key="delete_session")
    session_id = session_choices[session_label]
    counts = database.count_delete_session(connection, session_id)

    st.warning(f"This will remove {describe_counts(counts)}: {session_label} and its records.")
    if ask_to_confirm(f"session_{session_id}"):
        counts = database.delete_session(connection, session_id)
        finish_edit(f"Deleted session {session_id}: removed {describe_counts(counts)}.")


def show_delete_course(connection):
    """Delete a course, only when no sessions or students use it (FR-23)."""
    st.subheader("Delete a course")

    course_choices = get_course_choices(connection)
    if not course_choices:
        st.info(NO_COURSES_MESSAGE)
        return

    course_label = st.selectbox("Course", list(course_choices), key="delete_course")
    course_code = course_choices[course_label]
    session_count, student_count = database.get_course_usage(connection, course_code)

    if session_count > 0 or student_count > 0:
        st.error(validation.COURSE_IN_USE_ERROR.format(course_code, session_count, student_count))
        return

    st.warning(f"This will remove 1 course: {course_label}. No sessions or students use it.")
    if ask_to_confirm(f"course_{course_code}"):
        counts = database.delete_course(connection, course_code)
        finish_edit(f"Deleted course {course_code}: removed {describe_counts(counts)}.")


def show_edit_and_delete(connection):
    """Show every rename and delete section (FR-22, FR-23)."""
    show_edit_message()
    show_rename_student(connection)
    st.divider()
    show_rename_course(connection)
    st.divider()
    show_delete_attendance_record(connection)
    st.divider()
    show_unenroll_student(connection)
    st.divider()
    show_delete_student(connection)
    st.divider()
    show_delete_session(connection)
    st.divider()
    show_delete_course(connection)


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
        f"Import of {result['filename']} finished. Accepted and saved: {result['accepted']}. "
        f"Skipped duplicates: {result['duplicates']}. Rejected: {result['rejected']}."
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


def validate_upload(connection, uploaded_file, rows):
    """Validate the rows and keep the result in session_state (the database is not changed)."""
    accepted, duplicates, rejected = importer.validate_rows(connection, rows)

    st.session_state["import_validation"] = {
        "file_id": uploaded_file.file_id,
        "filename": uploaded_file.name,
        "accepted": accepted,
        "accepted_table": importer.make_table(accepted, with_reason=False),
        "duplicates_table": importer.make_table(duplicates, with_reason=True),
        "rejected_table": importer.make_table(rejected, with_reason=True),
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


def show_review(validation_result):
    """Show the counts and the accepted, duplicate and rejected rows (Review issues step)."""
    accepted_table = validation_result["accepted_table"]
    duplicates_table = validation_result["duplicates_table"]
    rejected_table = validation_result["rejected_table"]

    count_columns = st.columns(3)
    count_columns[0].metric("Accepted", len(accepted_table))
    count_columns[1].metric("Skipped duplicates", len(duplicates_table))
    count_columns[2].metric("Rejected", len(rejected_table))

    st.markdown("**Accepted rows** (saved only after Confirm)")
    if accepted_table.empty:
        st.info("No rows can be imported from this file.")
    else:
        st.dataframe(accepted_table, hide_index=True, width="stretch")

    if not duplicates_table.empty:
        st.markdown("**Skipped duplicates** (already saved or repeated in this file)")
        show_table_with_reasons(duplicates_table)

    if not rejected_table.empty:
        st.markdown("**Rejected rows**")
        show_table_with_reasons(rejected_table)
        st.download_button(
            "Download rejected rows (CSV)",
            data=rejected_table.to_csv(index=False),
            file_name="rejected_rows.csv",
            mime="text/csv",
            key="download_rejected_review",
        )


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
    st.caption("Required columns: " + ", ".join(importer.REQUIRED_COLUMNS))
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

    # Step 4: Review issues
    show_review(validation_result)

    # Step 5: Confirm
    if validation_result["accepted"]:
        if st.button("Confirm import", type="primary"):
            confirm_import(connection, validation_result)


# ---------- FR-12: filters for the Dashboard and Reports ----------

def show_filters(connection):
    """Show the course and date filters in the sidebar.

    Returns (filtered records, text describing the filters). The records are None
    when there is nothing to show yet; the text then explains why.
    """
    st.sidebar.header("Dashboard and Reports filters")

    all_records = analytics.build_records_frame(database.get_expected_records(connection))
    earliest, latest = analytics.get_date_bounds(all_records)
    if earliest is None:
        return None, NO_DATA_MESSAGE

    course_options = [analytics.ALL_COURSES]
    for course in database.get_courses(connection):
        course_options.append(course["course_code"])
    course_code = st.sidebar.selectbox("Course", course_options)

    chosen_dates = st.sidebar.date_input(
        "Date range",
        value=(date.fromisoformat(earliest), date.fromisoformat(latest)),
    )
    # While the user is picking, the range has only a start date.
    if len(chosen_dates) != 2:
        return None, "Choose an end date to finish the date range."

    start_date = chosen_dates[0].isoformat()
    end_date = chosen_dates[1].isoformat()

    filtered = analytics.filter_records(all_records, course_code, start_date, end_date)
    filter_text = f"Showing: {course_code}, from {start_date} to {end_date}."
    return filtered, filter_text


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

def show_metrics(filtered_records):
    """Show the seven dashboard numbers (FR-13)."""
    metrics = analytics.calculate_dashboard_metrics(filtered_records)

    first_row = st.columns(4)
    first_row[0].metric("Students", metrics["students"])
    first_row[1].metric("Sessions", metrics["sessions"])
    first_row[2].metric("Attendance rate", analytics.format_rate(metrics["attendance_rate"]))
    first_row[3].metric("Completeness", analytics.format_rate(metrics["completeness"]))

    second_row = st.columns(4)
    second_row[0].metric("Present", metrics["present"])
    second_row[1].metric("Absent", metrics["absent"])
    second_row[2].metric("Unknown", metrics["unknown"])


def show_rate_chart(filtered_records):
    """Show one chart: attendance rate by session in date order (FR-14)."""
    st.subheader("Attendance rate by session")

    chart_data = analytics.build_rate_chart_data(filtered_records)
    if chart_data.empty:
        st.info(
            "No attendance has been recorded for these sessions yet, "
            "so there is nothing to chart."
        )
        return

    chart = alt.Chart(chart_data).mark_bar().encode(
        # sort=None keeps the date order from analytics.py instead of sorting the labels.
        x=alt.X(analytics.CHART_LABEL_COLUMN, type="nominal", sort=None,
                axis=alt.Axis(labelAngle=-45)),
        y=alt.Y(analytics.CHART_VALUE_COLUMN, type="quantitative",
                scale=alt.Scale(domain=[0, 100])),
        color=alt.Color(analytics.CHART_COURSE_COLUMN, type="nominal"),
    )
    st.altair_chart(chart, width="stretch")
    st.caption(
        "One bar per session, coloured by course. "
        "Use the course and date filters to focus on fewer sessions."
    )


def show_status_chart(filtered_records):
    """Show a stacked bar per session: Present, Absent and Unknown counts (FR-20)."""
    st.subheader("Recording status by session")

    status_data = analytics.build_status_chart_data(filtered_records)
    if status_data.empty:
        st.info("No sessions to show for these filters.")
        return

    chosen_statuses = st.multiselect(
        "Show statuses", analytics.STATUS_ORDER, default=analytics.STATUS_ORDER,
        key="status_filter",
    )
    if not chosen_statuses:
        st.info("No statuses selected. Choose at least one status to show the chart.")
        return

    all_statuses = analytics.make_status_chart_long(status_data)
    chart_data = analytics.keep_statuses(all_statuses, chosen_statuses)
    # The colour scale always lists all three statuses, so each keeps its colour
    # whatever is selected.
    chart = alt.Chart(chart_data).mark_bar().encode(
        # sort=None keeps the date order from analytics.py, like the rate chart.
        x=alt.X(analytics.CHART_LABEL_COLUMN, type="nominal", sort=None,
                axis=alt.Axis(labelAngle=-45)),
        y=alt.Y(analytics.CHART_COUNT_COLUMN, type="quantitative", stack="zero"),
        color=alt.Color(
            analytics.CHART_STATUS_COLUMN, type="nominal",
            scale=alt.Scale(domain=analytics.STATUS_ORDER, range=STATUS_COLORS),
        ),
        order=alt.Order(analytics.CHART_ORDER_COLUMN, type="quantitative"),
    )
    st.altair_chart(chart, width="stretch")
    st.caption("Grey shows enrolled students with no record: missing data, not absence.")


def show_threshold_list(filtered_records):
    """List students below a chosen attendance rate, lowest first (FR-15)."""
    st.subheader("Students below a threshold")

    threshold = st.slider(
        "Attendance rate threshold (%)", min_value=0, max_value=100,
        value=analytics.DEFAULT_THRESHOLD,
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


def show_absence_alerts(filtered_records):
    """List students whose current absence streak reaches a chosen length (FR-21)."""
    st.subheader("Absence alerts")

    minimum = st.number_input(
        "Alert when current streak is at least", min_value=1,
        value=analytics.DEFAULT_STREAK_ALERT, step=1, key="streak_minimum",
    )

    streak_table = analytics.build_streak_table(filtered_records)
    alerts = analytics.find_streak_alerts(streak_table, minimum)

    if alerts.empty:
        st.success(f"No students have {minimum} or more absences in a row.")
    else:
        st.dataframe(alerts, hide_index=True, width="stretch")


def show_dashboard_tab(filtered_records, filter_text):
    """Show the Dashboard tab."""
    if not has_data_to_show(filtered_records, filter_text):
        return

    show_metrics(filtered_records)
    st.divider()
    show_rate_chart(filtered_records)
    st.divider()
    show_status_chart(filtered_records)
    st.divider()
    show_threshold_list(filtered_records)
    st.divider()
    show_absence_alerts(filtered_records)


# ---------- FR-16 and FR-17: Reports ----------

def show_table_with_download(table, file_name, button_key):
    """Show a table and a CSV download made from that same table (FR-17)."""
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

    student_choices = get_student_choices(connection)
    options = [ALL_STUDENTS] + list(student_choices)
    student_label = st.selectbox("Student", options, key="report_student")

    if student_label == ALL_STUDENTS:
        show_all_students_report(filtered_records)
    else:
        student_id = student_choices[student_label]
        show_single_student_report(student_id, student_label, filtered_records)


def show_all_students_report(filtered_records):
    """Show the overall numbers, the per-student summary and the attendance records (FR-16)."""
    st.subheader("All students")
    show_summary_metrics(filtered_records)

    st.markdown("**Per-student summary**")
    student_summary = analytics.build_student_summary(filtered_records)
    summary_table = analytics.format_summary_table(student_summary)
    show_table_with_download(summary_table, "student_summary.csv", "download_summary")

    st.markdown("**Attendance records**")
    attendance_report = analytics.build_attendance_report(filtered_records)
    show_table_with_download(attendance_report, "attendance_report.csv", "download_attendance")


# ---------- FR-19: single student report ----------

def show_summary_metrics(records):
    """Show Present, Absent, Unknown, attendance rate and completeness for some records."""
    rates = analytics.summarize_frame(records)

    metric_columns = st.columns(5)
    metric_columns[0].metric("Present", rates["present"])
    metric_columns[1].metric("Absent", rates["absent"])
    metric_columns[2].metric("Unknown", rates["unknown"])
    metric_columns[3].metric("Attendance rate", analytics.format_rate(rates["attendance_rate"]))
    metric_columns[4].metric("Completeness", analytics.format_rate(rates["completeness"]))


def show_single_student_report(student_id, student_label, filtered_records):
    """Show one student's numbers, courses and session history, using the filters (FR-19)."""
    st.subheader(f"Report for {student_label}")

    student_records = analytics.filter_student(filtered_records, student_id)
    if student_records.empty:
        st.info(
            f"No sessions for {student_label} match these filters. "
            "Choose another course or a wider date range."
        )
        return

    show_summary_metrics(student_records)

    # Shown even for one course, because it holds the absence streaks (FR-21).
    st.markdown("**By course**")
    course_summary = analytics.build_course_summary(student_records)
    course_table = analytics.format_summary_table(course_summary)
    st.dataframe(course_table, hide_index=True, width="stretch")

    st.markdown("**Session history**")
    history = analytics.build_student_history(student_records)
    show_table_with_download(history, f"student_{student_id}_history.csv", "download_history")


# ---------- Tabs ----------

def show_manage_tab(connection):
    """Show the Manage Attendance sections grouped into sub-tabs."""
    students_tab, courses_tab, sessions_tab, record_tab, edit_tab = st.tabs(
        ["Students", "Courses", "Sessions", "Record Attendance", "Edit & Delete"]
    )

    # Courses run first so a course created in this run already appears in the
    # Students and Sessions lists. The order of the sub-tabs on screen stays the same.
    with courses_tab:
        show_add_course(connection)

    with students_tab:
        # Search first, so the user can check whether a student exists before adding.
        show_search_students(connection)
        st.divider()
        show_add_student(connection)
        st.divider()
        show_enroll_student(connection)

    with sessions_tab:
        show_add_session(connection)

    with record_tab:
        show_record_attendance(connection)

    with edit_tab:
        show_edit_and_delete(connection)


def main():
    """Build the page with its four tabs (FR-01)."""
    st.set_page_config(page_title="Attendance V2", layout="wide")
    st.title("Attendance Management and Analytics")

    connection = database.get_connection()
    database.create_tables(connection)

    dashboard_tab, manage_tab, import_tab, reports_tab = st.tabs(
        ["Dashboard", "Manage Attendance", "Import & Validate", "Reports"]
    )

    # The tabs that change data run first, so the Dashboard and Reports
    # include anything saved in this same run. The tab order on screen stays the same.
    with manage_tab:
        show_manage_tab(connection)

    with import_tab:
        show_import_tab(connection)

    filtered_records, filter_text = show_filters(connection)

    with dashboard_tab:
        show_dashboard_tab(filtered_records, filter_text)

    with reports_tab:
        show_reports_tab(connection, filtered_records, filter_text)

    connection.close()


if __name__ == "__main__":
    main()
