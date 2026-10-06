"""Create a clean demo database: python seed_demo.py

Deletes attendance.db and recreates it with 2 courses, 12 students,
4 sessions per course, and a few missing records so Unknown is not zero.
The data is fixed (no random numbers), so every demo run looks the same.
"""

import os

import analytics
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


def create_demo_data(connection):
    """Add all the demo data to a database with empty tables."""
    add_demo_data(connection)
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
    """Print the totals so the person running the script can check them."""
    frame = analytics.build_records_frame(database.get_expected_records(connection))
    rates = analytics.summarize_frame(frame)

    print(f"Created {database.DB_PATH}")
    print(f"Courses: {len(COURSES)}, students: {len(STUDENTS)}, sessions: {len(SESSIONS)}")
    print(f"Present: {rates['present']}, Absent: {rates['absent']}, Unknown: {rates['unknown']}")
    print(f"Attendance rate: {analytics.format_rate(rates['attendance_rate'])}")
    print(f"Completeness: {analytics.format_rate(rates['completeness'])}")


def main():
    """Rebuild the demo database from scratch."""
    connection = reset_database(database.DB_PATH)
    create_demo_data(connection)
    print_summary(connection)
    connection.close()


if __name__ == "__main__":
    main()
