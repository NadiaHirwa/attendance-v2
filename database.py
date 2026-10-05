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


def get_course_name(connection, course_code):
    """Return the name of a course, or None if the code is not saved."""
    row = connection.execute(
        "SELECT course_name FROM courses WHERE course_code = ?",
        (course_code,),
    ).fetchone()

    if row is None:
        return None
    return row["course_name"]


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


def import_records(connection, records, source):
    """Save validated import rows in one transaction and return how many were saved.

    Each record has student_id, full_name, course_code, session_id, session_date and status.
    The student is enrolled before attendance is saved, so BR-09 holds (IR-06).
    If any row fails, the whole import is rolled back and nothing is saved.
    """
    recorded_at = datetime.now().isoformat(timespec="seconds")

    # "with connection" commits at the end, or rolls back everything if an error happens.
    with connection:
        for record in records:
            # INSERT OR IGNORE keeps an existing student, session or enrollment as it is.
            connection.execute(
                "INSERT OR IGNORE INTO students (student_id, full_name) VALUES (?, ?)",
                (record["student_id"], record["full_name"]),
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO sessions (session_id, course_code, session_date)
                VALUES (?, ?, ?)
                """,
                (record["session_id"], record["course_code"], record["session_date"]),
            )
            connection.execute(
                "INSERT OR IGNORE INTO enrollments (student_id, course_code) VALUES (?, ?)",
                (record["student_id"], record["course_code"]),
            )
            # A plain INSERT: if the record already exists, the error cancels the import.
            connection.execute(
                """
                INSERT INTO attendance (student_id, session_id, status, source, recorded_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (record["student_id"], record["session_id"], record["status"],
                 source, recorded_at),
            )

    return len(records)


# ---------- Rename (FR-22) ----------

def rename_student(connection, student_id, full_name):
    """Change a student's full name. The student ID never changes."""
    connection.execute(
        "UPDATE students SET full_name = ? WHERE student_id = ?",
        (full_name, student_id),
    )
    connection.commit()


def rename_course(connection, course_code, course_name):
    """Change a course's name. The course code never changes."""
    connection.execute(
        "UPDATE courses SET course_name = ? WHERE course_code = ?",
        (course_name, course_code),
    )
    connection.commit()


# ---------- Delete (FR-23) ----------
# Each count_... function says what the matching delete_... function would remove,
# using the same keys, so the screen can show it before the user confirms.

def count_rows(connection, query, parameters):
    """Run a SELECT COUNT(*) query and return the number."""
    return connection.execute(query, parameters).fetchone()[0]


def count_course_attendance(connection, student_id, course_code):
    """Return how many attendance records a student has in one course's sessions."""
    return count_rows(
        connection,
        """
        SELECT COUNT(*) FROM attendance
        WHERE student_id = ?
          AND session_id IN (SELECT session_id FROM sessions WHERE course_code = ?)
        """,
        (student_id, course_code),
    )


def count_unenroll(connection, student_id, course_code):
    """Return what un-enrolling a student from a course would remove."""
    return {
        "attendance": count_course_attendance(connection, student_id, course_code),
        "enrollments": 1,
    }


def count_delete_student(connection, student_id):
    """Return what deleting a student would remove."""
    return {
        "attendance": count_rows(
            connection, "SELECT COUNT(*) FROM attendance WHERE student_id = ?", (student_id,)
        ),
        "enrollments": count_rows(
            connection, "SELECT COUNT(*) FROM enrollments WHERE student_id = ?", (student_id,)
        ),
        "students": 1,
    }


def count_delete_session(connection, session_id):
    """Return what deleting a session would remove."""
    return {
        "attendance": count_rows(
            connection, "SELECT COUNT(*) FROM attendance WHERE session_id = ?", (session_id,)
        ),
        "sessions": 1,
    }


def get_course_usage(connection, course_code):
    """Return (number of sessions, number of enrolled students) of a course."""
    session_count = count_rows(
        connection, "SELECT COUNT(*) FROM sessions WHERE course_code = ?", (course_code,)
    )
    student_count = count_rows(
        connection, "SELECT COUNT(*) FROM enrollments WHERE course_code = ?", (course_code,)
    )
    return session_count, student_count


def delete_attendance_record(connection, student_id, session_id):
    """Delete one attendance record, so the student becomes Unknown for that session."""
    with connection:
        cursor = connection.execute(
            "DELETE FROM attendance WHERE student_id = ? AND session_id = ?",
            (student_id, session_id),
        )
    return {"attendance": cursor.rowcount}


def unenroll_student(connection, student_id, course_code):
    """Un-enroll a student from a course and delete their records for its sessions.

    Both deletes run in one transaction: either both happen or neither does.
    """
    with connection:
        attendance_cursor = connection.execute(
            """
            DELETE FROM attendance
            WHERE student_id = ?
              AND session_id IN (SELECT session_id FROM sessions WHERE course_code = ?)
            """,
            (student_id, course_code),
        )
        enrollment_cursor = connection.execute(
            "DELETE FROM enrollments WHERE student_id = ? AND course_code = ?",
            (student_id, course_code),
        )
    return {
        "attendance": attendance_cursor.rowcount,
        "enrollments": enrollment_cursor.rowcount,
    }


def delete_student(connection, student_id):
    """Delete a student with their attendance and enrollments, in one transaction.

    The rows that point to the student go first, so the foreign keys stay valid.
    Afterwards the student ID can be used again.
    """
    with connection:
        attendance_cursor = connection.execute(
            "DELETE FROM attendance WHERE student_id = ?", (student_id,)
        )
        enrollment_cursor = connection.execute(
            "DELETE FROM enrollments WHERE student_id = ?", (student_id,)
        )
        student_cursor = connection.execute(
            "DELETE FROM students WHERE student_id = ?", (student_id,)
        )
    return {
        "attendance": attendance_cursor.rowcount,
        "enrollments": enrollment_cursor.rowcount,
        "students": student_cursor.rowcount,
    }


def delete_session(connection, session_id):
    """Delete a session and its attendance records, in one transaction."""
    with connection:
        attendance_cursor = connection.execute(
            "DELETE FROM attendance WHERE session_id = ?", (session_id,)
        )
        session_cursor = connection.execute(
            "DELETE FROM sessions WHERE session_id = ?", (session_id,)
        )
    return {
        "attendance": attendance_cursor.rowcount,
        "sessions": session_cursor.rowcount,
    }


def delete_course(connection, course_code):
    """Delete a course that has no sessions and no enrolled students.

    Raises ValueError if anything still uses the course, so nothing is removed by accident.
    """
    session_count, student_count = get_course_usage(connection, course_code)
    if session_count > 0 or student_count > 0:
        raise ValueError(
            f"Course {course_code} still has {session_count} session(s) and "
            f"{student_count} enrolled student(s)."
        )

    with connection:
        cursor = connection.execute(
            "DELETE FROM courses WHERE course_code = ?", (course_code,)
        )
    return {"courses": cursor.rowcount}


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
