"""SQLite storage for the attendance system (Section 3 of the spec).

Every query uses ? parameters, never string formatting (NFR-04).
Functions expect values that were already checked by validation.py.
"""

import sqlite3
from datetime import datetime

DB_PATH = "attendance.db"
MANUAL_SOURCE = "manual"

# The exact schema from Section 3 of the spec.
SCHEMA = """
CREATE TABLE IF NOT EXISTS courses (
    course_code TEXT PRIMARY KEY,
    course_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS students (
    student_id TEXT PRIMARY KEY,
    full_name  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS enrollments (
    student_id  TEXT NOT NULL REFERENCES students,
    course_code TEXT NOT NULL REFERENCES courses,
    PRIMARY KEY (student_id, course_code)
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id   TEXT PRIMARY KEY,
    course_code  TEXT NOT NULL REFERENCES courses,
    session_date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS attendance (
    student_id  TEXT NOT NULL REFERENCES students,
    session_id  TEXT NOT NULL REFERENCES sessions,
    status      TEXT NOT NULL CHECK (status IN ('Present', 'Absent')),
    source      TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    PRIMARY KEY (student_id, session_id)
);
"""


def get_connection(path=DB_PATH):
    """Open the database with foreign keys switched on."""
    connection = sqlite3.connect(path)
    # SQLite turns foreign keys off for each new connection, so switch them on every time.
    connection.execute("PRAGMA foreign_keys = ON")
    # Rows can then be read by column name, like row["full_name"].
    connection.row_factory = sqlite3.Row
    return connection


def create_tables(connection):
    """Create all tables if they do not exist yet."""
    connection.executescript(SCHEMA)
    connection.commit()


# ---------- Courses ----------

def add_course(connection, course_code, course_name):
    """Save a new course."""
    connection.execute(
        "INSERT INTO courses (course_code, course_name) VALUES (?, ?)",
        (course_code, course_name),
    )
    connection.commit()


def course_exists(connection, course_code):
    """Return True if the course code is already saved."""
    row = connection.execute(
        "SELECT 1 FROM courses WHERE course_code = ?",
        (course_code,),
    ).fetchone()
    return row is not None


def get_courses(connection):
    """Return all courses sorted by code."""
    return connection.execute(
        "SELECT course_code, course_name FROM courses ORDER BY course_code"
    ).fetchall()


# ---------- Students and enrollments ----------

def add_student(connection, student_id, full_name):
    """Save a new student."""
    connection.execute(
        "INSERT INTO students (student_id, full_name) VALUES (?, ?)",
        (student_id, full_name),
    )
    connection.commit()


def get_student(connection, student_id):
    """Return one student row, or None if the ID is not saved."""
    return connection.execute(
        "SELECT student_id, full_name FROM students WHERE student_id = ?",
        (student_id,),
    ).fetchone()


def get_all_students(connection):
    """Return all students sorted by ID."""
    return connection.execute(
        "SELECT student_id, full_name FROM students ORDER BY student_id"
    ).fetchall()


def find_students_by_name(connection, full_name):
    """Return students whose name matches exactly, ignoring case."""
    # SQLite's lower() only handles ASCII, so compare in Python with casefold().
    matches = []
    for student in get_all_students(connection):
        if student["full_name"].casefold() == full_name.casefold():
            matches.append(student)
    return matches


def enroll_student(connection, student_id, course_code):
    """Enroll a student in a course. Does nothing if already enrolled."""
    connection.execute(
        "INSERT OR IGNORE INTO enrollments (student_id, course_code) VALUES (?, ?)",
        (student_id, course_code),
    )
    connection.commit()


def is_enrolled(connection, student_id, course_code):
    """Return True if the student is enrolled in the course."""
    row = connection.execute(
        "SELECT 1 FROM enrollments WHERE student_id = ? AND course_code = ?",
        (student_id, course_code),
    ).fetchone()
    return row is not None


def get_student_courses(connection, student_id):
    """Return the courses a student is enrolled in."""
    return connection.execute(
        """
        SELECT courses.course_code, courses.course_name
        FROM enrollments
        JOIN courses ON courses.course_code = enrollments.course_code
        WHERE enrollments.student_id = ?
        ORDER BY courses.course_code
        """,
        (student_id,),
    ).fetchall()


def get_enrolled_students(connection, course_code):
    """Return the students enrolled in a course, sorted by ID."""
    return connection.execute(
        """
        SELECT students.student_id, students.full_name
        FROM enrollments
        JOIN students ON students.student_id = enrollments.student_id
        WHERE enrollments.course_code = ?
        ORDER BY students.student_id
        """,
        (course_code,),
    ).fetchall()


# ---------- Sessions ----------

def add_session(connection, session_id, course_code, session_date):
    """Save a new session for a course."""
    connection.execute(
        "INSERT INTO sessions (session_id, course_code, session_date) VALUES (?, ?, ?)",
        (session_id, course_code, session_date),
    )
    connection.commit()


def get_session(connection, session_id):
    """Return one session row, or None if the ID is not saved."""
    return connection.execute(
        "SELECT session_id, course_code, session_date FROM sessions WHERE session_id = ?",
        (session_id,),
    ).fetchone()


def get_sessions_for_course(connection, course_code):
    """Return the sessions of a course in date order."""
    return connection.execute(
        """
        SELECT session_id, course_code, session_date
        FROM sessions
        WHERE course_code = ?
        ORDER BY session_date, session_id
        """,
        (course_code,),
    ).fetchall()


# ---------- Attendance ----------

def get_status(connection, student_id, session_id):
    """Return the saved status for a student and session, or None if there is none."""
    row = connection.execute(
        "SELECT status FROM attendance WHERE student_id = ? AND session_id = ?",
        (student_id, session_id),
    ).fetchone()

    if row is None:
        return None
    return row["status"]


def record_attendance(connection, student_id, session_id, status, source=MANUAL_SOURCE):
    """Save one status and return 'inserted', 'updated', 'unchanged' or 'not_enrolled'.

    Only a student enrolled in the session's course can be recorded (BR-09).
    There is only one record per student per session (BR-08):
    recording again for the same pair edits the existing record.
    An unchanged status is not rewritten (FR-08).
    """
    session = get_session(connection, session_id)

    # A missing session is left to the foreign key, which raises an error (T14).
    if session is not None:
        if not is_enrolled(connection, student_id, session["course_code"]):
            return "not_enrolled"

    old_status = get_status(connection, student_id, session_id)
    recorded_at = datetime.now().isoformat(timespec="seconds")

    if old_status is None:
        connection.execute(
            """
            INSERT INTO attendance (student_id, session_id, status, source, recorded_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (student_id, session_id, status, source, recorded_at),
        )
        connection.commit()
        return "inserted"

    if old_status == status:
        return "unchanged"

    connection.execute(
        """
        UPDATE attendance
        SET status = ?, source = ?, recorded_at = ?
        WHERE student_id = ? AND session_id = ?
        """,
        (status, source, recorded_at, student_id, session_id),
    )
    connection.commit()
    return "updated"


def get_session_attendance(connection, session_id):
    """Return every enrolled student of the session's course with their status.

    Students with no record yet have status None (shown later as Unknown).
    """
    return connection.execute(
        """
        SELECT students.student_id, students.full_name, attendance.status
        FROM sessions
        JOIN enrollments ON enrollments.course_code = sessions.course_code
        JOIN students ON students.student_id = enrollments.student_id
        LEFT JOIN attendance
            ON attendance.student_id = students.student_id
            AND attendance.session_id = sessions.session_id
        WHERE sessions.session_id = ?
        ORDER BY students.student_id
        """,
        (session_id,),
    ).fetchall()


def get_expected_records(connection):
    """Return one row per enrolled student per session of their course.

    Each row has student_id, full_name, course_code, session_id, session_date and status.
    The status is None when nothing was recorded. Unknown is never stored (BR-12).
    """
    rows = connection.execute(
        """
        SELECT students.student_id, students.full_name, sessions.course_code,
               sessions.session_id, sessions.session_date, attendance.status
        FROM enrollments
        JOIN students ON students.student_id = enrollments.student_id
        JOIN sessions ON sessions.course_code = enrollments.course_code
        LEFT JOIN attendance
            ON attendance.student_id = enrollments.student_id
            AND attendance.session_id = sessions.session_id
        ORDER BY sessions.session_date, sessions.session_id, students.student_id
        """
    ).fetchall()

    records = []
    for row in rows:
        records.append(dict(row))
    return records
