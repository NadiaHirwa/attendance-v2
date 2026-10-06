"""Version 2 demo data, kept as a fixture for the tests (Version 3 Stage 1).

This is the data seed_demo.py created before Version 3: 2 courses with no block,
4 sessions each with typed IDs (PY101-W1 ...), 12 students. Its totals are
63 Present, 9 Absent, 4 Unknown, 87.50%, 94.74%. Many tests check rules against
these hand-calculated numbers, and it also shows that old-style data (no block,
typed session IDs) still works in Version 3.
"""

import os

import database

# (code, name, start date, end date). Every session below is inside its course's dates.
COURSES = [
    ("PY101", "Programming with Python", "2026-09-07", "2026-12-18"),
    ("DS102", "Data Science Basics", "2026-09-09", "2026-12-18"),
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

# Students 004 to 010 take both courses, so search shows several courses for them.
ENROLLMENTS = {
    "PY101": ["001", "002", "003", "004", "005", "006", "007", "008", "009", "010"],
    "DS102": ["004", "005", "006", "007", "008", "009", "010", "011", "012"],
}

SESSIONS = [
    ("PY101-W1", "PY101", "2026-09-07"),
    ("PY101-W2", "PY101", "2026-09-14"),
    ("PY101-W3", "PY101", "2026-09-21"),
    ("PY101-W4", "PY101", "2026-09-28"),
    ("DS102-W1", "DS102", "2026-09-09"),
    ("DS102-W2", "DS102", "2026-09-16"),
    ("DS102-W3", "DS102", "2026-09-23"),
    ("DS102-W4", "DS102", "2026-09-30"),
]

# (student_id, session_id) pairs recorded as Absent. Everyone else is Present.
ABSENCES = [
    ("002", "PY101-W1"),
    ("002", "PY101-W3"),
    ("002", "PY101-W4"),
    ("006", "PY101-W2"),
    ("009", "PY101-W4"),
    ("005", "DS102-W1"),
    ("011", "DS102-W2"),
    ("011", "DS102-W3"),
    ("012", "DS102-W4"),
]

# Pairs deliberately left without a record, so they show as Unknown.
MISSING = [
    ("003", "PY101-W2"),
    ("010", "PY101-W4"),
    ("008", "DS102-W3"),
    ("012", "DS102-W3"),
]

SEED_SOURCE = "seed_demo"


def reset_database(path):
    """Delete the database file if it exists, then create empty tables."""
    if os.path.exists(path):
        os.remove(path)

    connection = database.get_connection(path)
    database.create_tables(connection)
    return connection


def add_demo_data(connection):
    """Add the courses, students, enrollments and sessions."""
    for course_code, course_name, start_date, end_date in COURSES:
        database.add_course(connection, course_code, course_name, start_date, end_date)

    for student_id, full_name in STUDENTS:
        database.add_student(connection, student_id, full_name)

    for course_code in ENROLLMENTS:
        for student_id in ENROLLMENTS[course_code]:
            database.enroll_student(connection, student_id, course_code)

    for session_id, course_code, session_date in SESSIONS:
        database.add_session(connection, session_id, course_code, session_date)


def add_demo_attendance(connection):
    """Record attendance for every enrolled student, except the MISSING pairs."""
    for session_id, course_code, session_date in SESSIONS:
        for student_id in ENROLLMENTS[course_code]:
            pair = (student_id, session_id)

            if pair in MISSING:
                continue

            if pair in ABSENCES:
                status = "Absent"
            else:
                status = "Present"

            database.record_attendance(connection, student_id, session_id, status, SEED_SOURCE)
