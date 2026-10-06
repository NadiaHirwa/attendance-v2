"""Create a clean demo database: python seed_demo.py (Version 3 demo data, Section 12).

Deletes attendance.db and recreates it with one 3-week block, 3 courses with a class
on every weekday, one holiday, 2 tutorials per course, and 12 students, including a
late joiner and an early leaver. Everyone is Present except the explicit exceptions
below, so the numbers can be checked by hand. The data is fixed (no random numbers),
so every run gives the same numbers.
"""

import os

import analytics
import database
import validation

BLOCK_ID = "B1-2627"
BLOCK_NAME = "Block 1, 2026-27"
BLOCK_START = "2026-09-07"  # a Monday; the block ends on Friday 2026-09-25

COURSES = [
    ("PY101", "Programming with Python"),
    ("DS102", "Data Science Basics"),
    ("MA103", "Mathematics for Data Science"),
]

STUDENTS = [
    ("001", "Nadia Hirwa"),
    ("002", "Jean-Paul Mugisha"),
    ("003", "Grace O'Neil"),
    ("004", "Eric Niyonzima"),
    ("005", "Aline Uwase"),
    ("006", "Patrick Habimana"),
    ("007", "Diane Mukamana"),
    ("008", "Kevin Ndayishimiye"),
    ("009", "Sandrine Ingabire"),
    ("010", "Olivier Nkurunziza"),
    ("011", "Claudine Umutoni"),
    ("012", "Samuel Bizimana"),
]

# Most students take all three courses; 003 and 007 skip DS102, 011 and 012 skip MA103.
ENROLLMENTS = {
    "PY101": ["001", "002", "003", "004", "005", "006", "007", "008", "009", "010", "011",
              "012"],
    "DS102": ["001", "002", "004", "005", "006", "008", "009", "010", "011", "012"],
    "MA103": ["001", "002", "003", "004", "005", "006", "007", "008", "009", "010"],
}

# 010 joins late (from week 2) and 012 leaves early (after week 2), in all their courses.
LATE_JOINER = ("010", "2026-09-14")
EARLY_LEAVER = ("012", "2026-09-18")

# Class days removed as holidays (course, date).
HOLIDAYS = [("DS102", "2026-09-16")]

# Tutorials (course, date). PY101 has one on a Saturday; MA103 has two on one date (T1, T2).
TUTORIALS = [
    ("PY101", "2026-09-10"),
    ("PY101", "2026-09-19"),
    ("DS102", "2026-09-11"),
    ("DS102", "2026-09-24"),
    ("MA103", "2026-09-23"),
    ("MA103", "2026-09-23"),
]

# Every record that is not Present: (student_id, session_id) -> status.
STATUSES = {
    # 002 in PY101: 5 Absent (3 in a row) and 2 Late, so 2 x 1 + 5 x 2 = 12 marks deducted.
    ("002", "PY101-2026-09-08"): "Absent",
    ("002", "PY101-2026-09-09"): "Late",
    ("002", "PY101-2026-09-15"): "Absent",
    ("002", "PY101-2026-09-17"): "Late",
    ("002", "PY101-2026-09-21"): "Absent",
    ("002", "PY101-2026-09-22"): "Absent",
    ("002", "PY101-2026-09-23"): "Absent",
    ("001", "PY101-2026-09-10-T1"): "Late",
    ("008", "PY101-2026-09-14"): "Excused",
    # 009 in PY101: absent on the last two days, so a current streak of 2.
    ("009", "PY101-2026-09-18"): "Late",
    ("009", "PY101-2026-09-24"): "Absent",
    ("009", "PY101-2026-09-25"): "Absent",
    ("012", "PY101-2026-09-18"): "Late",
    ("006", "DS102-2026-09-07"): "Late",
    ("006", "DS102-2026-09-10"): "Excused",
    ("006", "DS102-2026-09-14"): "Late",
    ("006", "DS102-2026-09-21"): "Late",
    ("010", "DS102-2026-09-14"): "Absent",
    ("011", "DS102-2026-09-08"): "Late",
    ("011", "DS102-2026-09-11-T1"): "Absent",
    ("004", "MA103-2026-09-07"): "Late",
    ("005", "MA103-2026-09-11"): "Absent",
    ("005", "MA103-2026-09-23-T1"): "Excused",
    ("005", "MA103-2026-09-23-T2"): "Excused",
}

# Records deliberately left out, so they show as Unknown.
MISSING = [
    ("003", "PY101-2026-09-16"),
    ("011", "PY101-2026-09-19-T1"),
    ("008", "DS102-2026-09-24-T1"),
    ("007", "MA103-2026-09-25"),
]

SEED_SOURCE = "seed_demo"


def reset_database(path):
    """Delete the database file if it exists, then create empty tables."""
    if os.path.exists(path):
        os.remove(path)

    connection = database.get_connection(path)
    database.create_tables(connection)
    return connection


def add_demo_structure(connection):
    """Add the block, courses (with class days), holidays, tutorials and students."""
    database.add_block(connection, BLOCK_ID, BLOCK_NAME, BLOCK_START)

    for course_code, course_name in COURSES:
        database.create_course(connection, course_code, course_name, BLOCK_ID)

    for course_code, holiday in HOLIDAYS:
        database.delete_session(
            connection, validation.make_class_session_id(course_code, holiday)
        )

    for course_code, tutorial_date in TUTORIALS:
        database.add_tutorial(connection, course_code, tutorial_date)

    for student_id, full_name in STUDENTS:
        database.add_student(connection, student_id, full_name)


def add_demo_enrollments(connection):
    """Enroll the students, with the late joiner's start and the early leaver's end."""
    late_student, late_start = LATE_JOINER
    early_student, early_end = EARLY_LEAVER

    for course_code in ENROLLMENTS:
        for student_id in ENROLLMENTS[course_code]:
            start_date = None
            end_date = None
            if student_id == late_student:
                start_date = late_start
            if student_id == early_student:
                end_date = early_end
            database.enroll_student(connection, student_id, course_code, start_date, end_date)


def check_demo_data(connection):
    """Raise ValueError if a listed exception names a session or student that does not exist.

    Without this check, a typo in STATUSES would silently leave that record Present.
    """
    listed_pairs = list(STATUSES) + MISSING
    for student_id, session_id in listed_pairs:
        session = database.get_session(connection, session_id)
        if session is None:
            raise ValueError(f"Demo data: session {session_id} does not exist.")
        if not database.is_enrolled(connection, student_id, session["course_code"]):
            raise ValueError(f"Demo data: {student_id} is not enrolled in {session_id}.")


def add_demo_attendance(connection):
    """Record every expected student at every session: Present unless listed above.

    record_attendance() saves nothing outside a student's enrollment dates, so the
    late joiner and the early leaver only get records inside their periods.
    """
    for course_code in ENROLLMENTS:
        for session in database.get_sessions_for_course(connection, course_code):
            session_id = session["session_id"]
            for student_id in ENROLLMENTS[course_code]:
                pair = (student_id, session_id)
                if pair in MISSING:
                    continue
                status = STATUSES.get(pair, "Present")
                database.record_attendance(
                    connection, student_id, session_id, status, SEED_SOURCE
                )


def create_demo_data(connection):
    """Add all the demo data to a database with empty tables."""
    add_demo_structure(connection)
    add_demo_enrollments(connection)
    check_demo_data(connection)
    add_demo_attendance(connection)


def seed_if_empty(connection):
    """Create the demo data if the database has no courses yet. Return True if it did.

    Used when the app starts, so a fresh online copy has data to show.
    """
    if database.get_courses(connection):
        return False

    create_demo_data(connection)
    return True


def reset_demo_data(connection):
    """Remove every record and create the demo data again, in an open database."""
    database.clear_all_data(connection)
    create_demo_data(connection)


def print_summary(connection):
    """Print the totals and the deductions per student per course, to check by hand."""
    frame = analytics.build_records_frame(database.get_expected_records(connection))
    metrics = analytics.calculate_dashboard_metrics(frame)

    print(f"Created {database.DB_PATH}")
    block_end = validation.calculate_block_end(BLOCK_START)
    print(f"Block {BLOCK_ID}: {validation.describe_course_period(BLOCK_START, block_end)}")
    for course_code, course_name in COURSES:
        class_days = 0
        tutorials = 0
        for session in database.get_sessions_for_course(connection, course_code):
            if session["session_type"] == validation.CLASS:
                class_days += 1
            else:
                tutorials += 1
        print(f"  {course_code} {course_name}: {class_days} class days, {tutorials} tutorials")

    print(f"Students: {metrics['students']}, expected records: {metrics['expected']}")
    print(
        f"Present: {metrics['present']}, Late: {metrics['late']}, "
        f"Excused: {metrics['excused']}, Absent: {metrics['absent']}, "
        f"Unknown: {metrics['unknown']}"
    )
    print(f"Attendance rate: {analytics.format_rate(metrics['attendance_rate'])}")
    print(f"Completeness: {analytics.format_rate(metrics['completeness'])}")

    print("Deductions (Late x 1 + Absent x 2):")
    deductions = analytics.build_deductions_table(frame)
    for index, row in deductions.iterrows():
        print(
            f"  {row['student_id']} {row['full_name']:<20} {row['course_code']}: "
            f"Late {row['Late']}, Absent {row['Absent']}, Unknown {row['Unknown']}, "
            f"deducted {row[analytics.DEDUCTED_COLUMN]}"
        )


def main():
    """Rebuild the demo database from scratch."""
    connection = reset_database(database.DB_PATH)
    create_demo_data(connection)
    print_summary(connection)
    connection.close()


if __name__ == "__main__":
    main()
