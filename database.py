"""SQLite storage for the attendance system (Section 3 of the spec).

Every query uses ? parameters, never string formatting (NFR-04).
Functions expect values that were already checked by validation.py.
"""

import sqlite3
from datetime import datetime

import validation

DB_PATH = "attendance.db"
MANUAL_SOURCE = "manual"

# The exact schema from Section 3 of the spec.
SCHEMA = """
CREATE TABLE IF NOT EXISTS courses (
    course_code TEXT PRIMARY KEY,
    course_name TEXT NOT NULL,
    start_date  TEXT,
    end_date    TEXT
);

CREATE TABLE IF NOT EXISTS students (
    student_id TEXT PRIMARY KEY,
    full_name  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS enrollments (
    student_id  TEXT NOT NULL REFERENCES students,
    course_code TEXT NOT NULL REFERENCES courses,
    start_date  TEXT,
    end_date    TEXT,
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
    status      TEXT NOT NULL CHECK (status IN ('Present', 'Late', 'Excused', 'Absent')),
    source      TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    PRIMARY KEY (student_id, session_id)
);
"""

# Used only to upgrade an older attendance table whose CHECK allows two statuses (FR-26).
NEW_ATTENDANCE_TABLE = """
CREATE TABLE attendance_new (
    student_id  TEXT NOT NULL REFERENCES students,
    session_id  TEXT NOT NULL REFERENCES sessions,
    status      TEXT NOT NULL CHECK (status IN ('Present', 'Late', 'Excused', 'Absent')),
    source      TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    PRIMARY KEY (student_id, session_id)
)
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
    """Create all tables if they do not exist yet, and upgrade an older database."""
    connection.executescript(SCHEMA)
    add_course_date_columns(connection)
    add_enrollment_date_columns(connection)
    connection.commit()
    upgrade_attendance_statuses(connection)


def upgrade_attendance_statuses(connection):
    """Allow Late and Excused in an older attendance table, keeping every row (FR-26).

    SQLite cannot change a CHECK rule with ALTER TABLE, so the table is rebuilt:
    create a new table, copy the rows, drop the old table, rename the new one.
    All four steps run in one transaction: if one fails, nothing changes.
    """
    row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'attendance'"
    ).fetchone()
    if "'Late'" in row[0]:
        return  # Already the new table.

    try:
        connection.execute("BEGIN")
        connection.execute(NEW_ATTENDANCE_TABLE)
        connection.execute(
            """
            INSERT INTO attendance_new (student_id, session_id, status, source, recorded_at)
            SELECT student_id, session_id, status, source, recorded_at FROM attendance
            """
        )
        connection.execute("DROP TABLE attendance")
        connection.execute("ALTER TABLE attendance_new RENAME TO attendance")
        connection.commit()
    except sqlite3.Error:
        connection.rollback()
        raise


def add_course_date_columns(connection):
    """Add start_date and end_date to courses if an older database lacks them (BR-16).

    Works like add_enrollment_date_columns(): old courses get NULL dates,
    which means no limit, so they keep working as before.
    """
    column_names = []
    for column in connection.execute("PRAGMA table_info(courses)"):
        column_names.append(column[1])  # Position 1 of each row is the column name.

    if "start_date" not in column_names:
        connection.execute("ALTER TABLE courses ADD COLUMN start_date TEXT")
    if "end_date" not in column_names:
        connection.execute("ALTER TABLE courses ADD COLUMN end_date TEXT")


def add_enrollment_date_columns(connection):
    """Add start_date and end_date to enrollments if an older database lacks them (BR-15).

    CREATE TABLE IF NOT EXISTS does not change a table that already exists,
    so an attendance.db made before this version needs ALTER TABLE.
    The new columns are NULL for old rows, which keeps the old behaviour.
    """
    column_names = []
    for column in connection.execute("PRAGMA table_info(enrollments)"):
        column_names.append(column[1])  # Position 1 of each row is the column name.

    if "start_date" not in column_names:
        connection.execute("ALTER TABLE enrollments ADD COLUMN start_date TEXT")
    if "end_date" not in column_names:
        connection.execute("ALTER TABLE enrollments ADD COLUMN end_date TEXT")


# ---------- Courses ----------

def add_course(connection, course_code, course_name, start_date=None, end_date=None):
    """Save a new course. The dates are 'YYYY-MM-DD' text or None for no limit (BR-16)."""
    connection.execute(
        """
        INSERT INTO courses (course_code, course_name, start_date, end_date)
        VALUES (?, ?, ?, ?)
        """,
        (course_code, course_name, start_date, end_date),
    )
    connection.commit()


def get_course(connection, course_code):
    """Return one course row (code, name, start_date, end_date), or None if not saved."""
    return connection.execute(
        """
        SELECT course_code, course_name, start_date, end_date
        FROM courses WHERE course_code = ?
        """,
        (course_code,),
    ).fetchone()


def update_course_dates(connection, course_code, start_date, end_date):
    """Change the start and end dates of a course (FR-25)."""
    connection.execute(
        "UPDATE courses SET start_date = ?, end_date = ? WHERE course_code = ?",
        (start_date, end_date, course_code),
    )
    connection.commit()


def count_sessions_outside_period(connection, course_code, start_date, end_date):
    """Return how many sessions of a course fall outside new course dates.

    A None start or end date means there is no limit on that side.
    """
    return count_rows(
        connection,
        """
        SELECT COUNT(*) FROM sessions
        WHERE course_code = ?
          AND ((? IS NOT NULL AND session_date < ?)
               OR (? IS NOT NULL AND session_date > ?))
        """,
        (course_code, start_date, start_date, end_date, end_date),
    )


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


def count_enrollments_outside_period(connection, course_code, start_date, end_date):
    """Return how many enrollments of a course have a date outside new course dates (BR-17).

    Enrollment dates that are None follow the course, so they never fall outside.
    """
    return count_rows(
        connection,
        """
        SELECT COUNT(*) FROM enrollments
        WHERE course_code = ?
          AND ((? IS NOT NULL AND start_date IS NOT NULL AND start_date < ?)
               OR (? IS NOT NULL AND start_date IS NOT NULL AND start_date > ?)
               OR (? IS NOT NULL AND end_date IS NOT NULL AND end_date > ?)
               OR (? IS NOT NULL AND end_date IS NOT NULL AND end_date < ?))
        """,
        (course_code, start_date, start_date, end_date, end_date,
         end_date, end_date, start_date, start_date),
    )


def get_courses(connection):
    """Return all courses with their dates, sorted by code."""
    return connection.execute(
        """
        SELECT course_code, course_name, start_date, end_date
        FROM courses ORDER BY course_code
        """
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


def check_enrollment_dates(connection, course_code, start_date, end_date):
    """Return the dates to store for an enrollment, or raise ValueError if they break BR-17.

    The enrollment must be inside its course period, with the start on or before the end.
    A date equal to the course's is stored as None, so it follows the course later.
    """
    course = get_course(connection, course_code)
    course_start = None
    course_end = None
    if course is not None:
        course_start = course["start_date"]
        course_end = course["end_date"]

    if not validation.is_enrollment_in_course_period(
        start_date, end_date, course_start, course_end
    ):
        period = validation.describe_course_period(course_start, course_end)
        raise ValueError(validation.ENROLLMENT_OUTSIDE_COURSE_ERROR.format(course_code, period))

    return validation.simplify_enrollment_dates(start_date, end_date, course_start, course_end)


def enroll_student(connection, student_id, course_code, start_date=None, end_date=None):
    """Enroll a student in a course. Does nothing if already enrolled.

    start_date and end_date are 'YYYY-MM-DD' text or None (BR-15):
    None as start means from the course's first session, None as end means still enrolled.
    Raises ValueError if the dates are not inside the course period (BR-17).
    """
    start_date, end_date = check_enrollment_dates(connection, course_code, start_date, end_date)
    connection.execute(
        """
        INSERT OR IGNORE INTO enrollments (student_id, course_code, start_date, end_date)
        VALUES (?, ?, ?, ?)
        """,
        (student_id, course_code, start_date, end_date),
    )
    connection.commit()


def get_enrollment(connection, student_id, course_code):
    """Return the enrollment row (with start_date and end_date), or None if not enrolled."""
    return connection.execute(
        """
        SELECT student_id, course_code, start_date, end_date
        FROM enrollments
        WHERE student_id = ? AND course_code = ?
        """,
        (student_id, course_code),
    ).fetchone()


def update_enrollment_dates(connection, student_id, course_code, start_date, end_date):
    """Change the start and end dates of an existing enrollment (FR-24).

    Raises ValueError if the dates are not inside the course period (BR-17).
    """
    start_date, end_date = check_enrollment_dates(connection, course_code, start_date, end_date)
    connection.execute(
        """
        UPDATE enrollments SET start_date = ?, end_date = ?
        WHERE student_id = ? AND course_code = ?
        """,
        (start_date, end_date, student_id, course_code),
    )
    connection.commit()


def count_records_outside_window(connection, student_id, course_code, start_date, end_date):
    """Return how many saved records of a student in a course fall outside new dates.

    A None start or end date means there is no limit on that side.
    """
    return count_rows(
        connection,
        """
        SELECT COUNT(*)
        FROM attendance
        JOIN sessions ON sessions.session_id = attendance.session_id
        WHERE attendance.student_id = ?
          AND sessions.course_code = ?
          AND ((? IS NOT NULL AND sessions.session_date < ?)
               OR (? IS NOT NULL AND sessions.session_date > ?))
        """,
        (student_id, course_code, start_date, start_date, end_date, end_date),
    )


def is_enrolled(connection, student_id, course_code):
    """Return True if the student is enrolled in the course."""
    row = connection.execute(
        "SELECT 1 FROM enrollments WHERE student_id = ? AND course_code = ?",
        (student_id, course_code),
    ).fetchone()
    return row is not None


def get_student_courses(connection, student_id):
    """Return the courses a student is enrolled in, with the course dates."""
    return connection.execute(
        """
        SELECT courses.course_code, courses.course_name, courses.start_date, courses.end_date
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
    """Save one status and return what happened.

    Returns 'inserted', 'updated', 'unchanged', 'not_enrolled' or 'outside_enrollment'.
    Only a student enrolled in the session's course can be recorded (BR-09), and only
    for a session inside their enrollment dates (BR-15).
    There is only one record per student per session (BR-08):
    recording again for the same pair edits the existing record.
    An unchanged status is not rewritten (FR-08).
    """
    session = get_session(connection, session_id)

    # A missing session is left to the foreign key, which raises an error (T14).
    if session is not None:
        enrollment = get_enrollment(connection, student_id, session["course_code"])
        if enrollment is None:
            return "not_enrolled"
        in_window = validation.is_in_enrollment_window(
            session["session_date"], enrollment["start_date"], enrollment["end_date"]
        )
        if not in_window:
            return "outside_enrollment"

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


def import_records(connection, records, source, enrollment_starts):
    """Save validated import rows in one transaction and return how many were saved.

    Each record has student_id, full_name, course_code, session_id, session_date and status.
    The student is enrolled before attendance is saved, so BR-09 holds (IR-06).
    enrollment_starts maps (student_id, course_code) to the start date of a NEW
    enrollment (BR-15); an existing enrollment keeps its dates.
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
            enrollment_key = (record["student_id"], record["course_code"])
            connection.execute(
                """
                INSERT OR IGNORE INTO enrollments (student_id, course_code, start_date)
                VALUES (?, ?, ?)
                """,
                (record["student_id"], record["course_code"],
                 enrollment_starts[enrollment_key]),
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
    """Return every student expected at the session with their status.

    A student is expected if they are enrolled in the session's course and the
    session date is inside their enrollment dates (BR-15).
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
          AND (enrollments.start_date IS NULL
               OR sessions.session_date >= enrollments.start_date)
          AND (enrollments.end_date IS NULL
               OR sessions.session_date <= enrollments.end_date)
        ORDER BY students.student_id
        """,
        (session_id,),
    ).fetchall()


def get_expected_records(connection):
    """Return one row per expected student per session of their course.

    A student is expected only for sessions inside their enrollment dates (BR-15).
    Each row has student_id, full_name, course_code, session_id, session_date, status,
    enrollment_start and enrollment_end. The status is None when nothing was recorded.
    Unknown is never stored (BR-12).
    """
    rows = connection.execute(
        """
        SELECT students.student_id, students.full_name, sessions.course_code,
               sessions.session_id, sessions.session_date, attendance.status,
               enrollments.start_date AS enrollment_start,
               enrollments.end_date AS enrollment_end
        FROM enrollments
        JOIN students ON students.student_id = enrollments.student_id
        JOIN sessions ON sessions.course_code = enrollments.course_code
        LEFT JOIN attendance
            ON attendance.student_id = enrollments.student_id
            AND attendance.session_id = sessions.session_id
        WHERE (enrollments.start_date IS NULL
               OR sessions.session_date >= enrollments.start_date)
          AND (enrollments.end_date IS NULL
               OR sessions.session_date <= enrollments.end_date)
        ORDER BY sessions.session_date, sessions.session_id, students.student_id
        """
    ).fetchall()

    records = []
    for row in rows:
        records.append(dict(row))
    return records
