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
CREATE TABLE IF NOT EXISTS blocks (
    block_id   TEXT PRIMARY KEY,
    block_name TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS courses (
    course_code TEXT PRIMARY KEY,
    course_name TEXT NOT NULL,
    block_id    TEXT REFERENCES blocks,
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
    session_date TEXT NOT NULL,
    session_type TEXT NOT NULL DEFAULT 'Class' CHECK (session_type IN ('Class', 'Tutorial'))
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
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

LATE_DEDUCTION_KEY = "late_deduction"
ABSENT_DEDUCTION_KEY = "absent_deduction"


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
    add_course_block_column(connection)
    add_enrollment_date_columns(connection)
    add_session_type_column(connection)
    make_class_days_unique(connection)
    add_default_settings(connection)
    connection.commit()
    upgrade_attendance_statuses(connection)


# ---------- Settings (BR-22) ----------

def add_default_settings(connection):
    """Save Late = 1 and Absent = 2 if the settings are not there yet (BR-22).

    CREATE TABLE IF NOT EXISTS adds the settings table to an older database;
    INSERT OR IGNORE keeps values that were already changed.
    """
    connection.execute(
        "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
        (LATE_DEDUCTION_KEY, str(validation.DEFAULT_LATE_DEDUCTION)),
    )
    connection.execute(
        "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
        (ABSENT_DEDUCTION_KEY, str(validation.DEFAULT_ABSENT_DEDUCTION)),
    )


def get_deduction_settings(connection):
    """Return the marks deducted per Late and per Absent, like {'late': 1, 'absent': 2}."""
    settings = {}
    for row in connection.execute("SELECT key, value FROM settings"):
        settings[row["key"]] = int(row["value"])
    return {
        "late": settings[LATE_DEDUCTION_KEY],
        "absent": settings[ABSENT_DEDUCTION_KEY],
    }


def save_deduction_settings(connection, late_deduction, absent_deduction):
    """Save both deduction settings in one transaction (BR-22).

    Raises ValueError, and saves nothing, unless both are whole numbers from 0 to 10.
    """
    late_value = validation.parse_deduction(late_deduction)
    if late_value is None:
        raise ValueError(validation.DEDUCTION_ERROR.format("Late", f'"{late_deduction}"'))

    absent_value = validation.parse_deduction(absent_deduction)
    if absent_value is None:
        raise ValueError(validation.DEDUCTION_ERROR.format("Absent", f'"{absent_deduction}"'))

    with connection:
        connection.execute(
            "UPDATE settings SET value = ? WHERE key = ?", (str(late_value), LATE_DEDUCTION_KEY)
        )
        connection.execute(
            "UPDATE settings SET value = ? WHERE key = ?",
            (str(absent_value), ABSENT_DEDUCTION_KEY),
        )


def get_column_names(connection, pragma_query):
    """Return the column names from a 'PRAGMA table_info(...)' query."""
    column_names = []
    for column in connection.execute(pragma_query):
        column_names.append(column[1])  # Position 1 of each row is the column name.
    return column_names


def add_course_block_column(connection):
    """Add block_id to courses if an older database lacks it (BR-19).

    Old courses get NULL, shown as "No block", and keep working as before.
    """
    if "block_id" not in get_column_names(connection, "PRAGMA table_info(courses)"):
        connection.execute("ALTER TABLE courses ADD COLUMN block_id TEXT REFERENCES blocks")


def add_session_type_column(connection):
    """Add session_type to sessions if an older database lacks it (BR-20, BR-21).

    Every old session becomes a 'Class'.
    """
    if "session_type" not in get_column_names(connection, "PRAGMA table_info(sessions)"):
        connection.execute(
            """
            ALTER TABLE sessions ADD COLUMN session_type TEXT NOT NULL DEFAULT 'Class'
                CHECK (session_type IN ('Class', 'Tutorial'))
            """
        )


def make_class_days_unique(connection):
    """Allow only one Class session per course per date (BR-20).

    An older database may have two sessions of one course on the same date. The one
    saved first (lowest rowid, SQLite's own row number) stays a Class and the others
    become Tutorials, so no session and no record is lost. Then a unique index
    protects the rule from now on.
    """
    connection.execute(
        """
        UPDATE sessions SET session_type = 'Tutorial'
        WHERE session_type = 'Class'
          AND rowid NOT IN (
              SELECT MIN(rowid) FROM sessions
              WHERE session_type = 'Class'
              GROUP BY course_code, session_date
          )
        """
    )
    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS one_class_per_course_per_day
        ON sessions (course_code, session_date) WHERE session_type = 'Class'
        """
    )


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
    """Return one course row (code, name, block_id, start_date, end_date), or None."""
    return connection.execute(
        """
        SELECT course_code, course_name, block_id, start_date, end_date
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


# ---------- Blocks (BR-18) ----------

def add_block(connection, block_id, block_name, start_date):
    """Save a block that starts on start_date (a Monday). Return its calculated end date."""
    end_date = validation.calculate_block_end(start_date)
    connection.execute(
        "INSERT INTO blocks (block_id, block_name, start_date, end_date) VALUES (?, ?, ?, ?)",
        (block_id, block_name, start_date, end_date),
    )
    connection.commit()
    return end_date


def get_block(connection, block_id):
    """Return one block row, or None if the ID is not saved."""
    return connection.execute(
        "SELECT block_id, block_name, start_date, end_date FROM blocks WHERE block_id = ?",
        (block_id,),
    ).fetchone()


def get_blocks(connection):
    """Return all blocks, earliest first."""
    return connection.execute(
        "SELECT block_id, block_name, start_date, end_date FROM blocks "
        "ORDER BY start_date, block_id"
    ).fetchall()


def plan_block_move(connection, block_id, start_date):
    """Return the new (start, end) of each course in a block that moves to start_date.

    A course that covers the whole block covers the whole new block; a shorter course
    keeps its length and moves by the same number of days, so it stays inside.
    Returns a list of (course row, new start, new end).
    """
    block = get_block(connection, block_id)
    new_end = validation.calculate_block_end(start_date)
    days = validation.days_between(block["start_date"], start_date)

    plans = []
    for course in get_block_courses(connection, block_id):
        course_start = course["start_date"]
        course_end = course["end_date"]
        if course_start is None or course_start == block["start_date"]:
            new_start = start_date
        else:
            new_start = validation.shift_date(course_start, days)
        if course_end is None or course_end == block["end_date"]:
            new_end_date = new_end
        else:
            new_end_date = validation.shift_date(course_end, days)
        plans.append((course, new_start, new_end_date))
    return plans


def change_block(connection, block_id, block_name, start_date):
    """Change a block's name and start date; its courses move with it (BR-18, BR-19).

    The end is calculated (BR-18). Raises ValueError, and changes nothing, if the start
    is not a Monday, or if saved attendance or an enrollment's dates would fall outside
    a course's new period. Otherwise one transaction saves the block, the courses'
    dates and their regenerated class days (see move_course_period).
    Returns {"end_date": ..., "added": ..., "removed": ...}.
    """
    if not validation.is_monday(start_date):
        raise ValueError(validation.BLOCK_START_ERROR.format(
            validation.format_date(start_date), validation.weekday_name(start_date)
        ))

    end_date = validation.calculate_block_end(start_date)
    new_period = validation.describe_course_period(start_date, end_date)
    plans = plan_block_move(connection, block_id, start_date)

    # Check every course before anything is changed.
    for course, new_start, new_end in plans:
        course_code = course["course_code"]
        enrollments = count_enrollments_outside_period(
            connection, course_code, new_start, new_end
        )
        if enrollments > 0:
            raise ValueError(validation.BLOCK_ENROLLMENTS_OUTSIDE_ERROR.format(
                block_id, new_period, enrollments, course_code
            ))
        records = count_records_outside_period(connection, course_code, new_start, new_end)
        if records > 0:
            raise ValueError(validation.BLOCK_RECORDS_OUTSIDE_ERROR.format(
                block_id, new_period, records, course_code
            ))

    added = 0
    removed = 0
    with connection:
        connection.execute(
            "UPDATE blocks SET block_name = ?, start_date = ?, end_date = ? WHERE block_id = ?",
            (block_name, start_date, end_date, block_id),
        )
        for course, new_start, new_end in plans:
            counts = move_course_period(
                connection, course["course_code"], course["start_date"], course["end_date"],
                new_start, new_end,
            )
            added += counts["added"]
            removed += counts["removed"]

    return {"end_date": end_date, "added": added, "removed": removed}


# ---------- Courses in blocks and class days (BR-19, BR-20) ----------

def insert_class_days(connection, course_code, class_days):
    """Insert one Class session per date. A date that already has one is skipped."""
    for class_day in class_days:
        connection.execute(
            """
            INSERT OR IGNORE INTO sessions (session_id, course_code, session_date, session_type)
            VALUES (?, ?, ?, 'Class')
            """,
            (validation.make_class_session_id(course_code, class_day), course_code, class_day),
        )


def create_course(connection, course_code, course_name, block_id,
                  start_date=None, end_date=None):
    """Create a course in a block, with one class per weekday of its period.

    BR-19: the course takes the block dates, unless a shorter period inside the block
    is given (start_date and end_date). BR-20: a Class session is generated for every
    Monday to Friday of the period. Everything runs in one transaction. Returns the
    number of class days created. Raises ValueError if the period leaves the block or
    ends before it starts.
    """
    block = get_block(connection, block_id)
    if start_date is None:
        start_date = block["start_date"]
    if end_date is None:
        end_date = block["end_date"]

    if not validation.are_period_dates_valid(start_date, end_date):
        raise ValueError(validation.COURSE_DATES_ERROR)
    if not validation.is_enrollment_in_course_period(
        start_date, end_date, block["start_date"], block["end_date"]
    ):
        period = validation.describe_course_period(block["start_date"], block["end_date"])
        raise ValueError(validation.COURSE_OUTSIDE_BLOCK_ERROR.format(
            course_code, block_id, period
        ))

    class_days = validation.list_class_days(start_date, end_date)

    with connection:
        connection.execute(
            """
            INSERT INTO courses (course_code, course_name, block_id, start_date, end_date)
            VALUES (?, ?, ?, ?, ?)
            """,
            (course_code, course_name, block_id, start_date, end_date),
        )
        insert_class_days(connection, course_code, class_days)

    return len(class_days)


def get_block_courses(connection, block_id):
    """Return the courses of a block, sorted by code."""
    return connection.execute(
        """
        SELECT course_code, course_name, block_id, start_date, end_date
        FROM courses WHERE block_id = ? ORDER BY course_code
        """,
        (block_id,),
    ).fetchall()


def delete_block(connection, block_id):
    """Delete a block that has no courses (Section 6.1).

    Raises ValueError, and deletes nothing, if a course still belongs to the block.
    """
    course_count = len(get_block_courses(connection, block_id))
    if course_count > 0:
        raise ValueError(validation.BLOCK_IN_USE_ERROR.format(block_id, course_count))

    with connection:
        cursor = connection.execute("DELETE FROM blocks WHERE block_id = ?", (block_id,))
    return {"blocks": cursor.rowcount}


def count_records_outside_period(connection, course_code, start_date, end_date):
    """Return how many saved records of a course are on sessions outside new dates."""
    return count_rows(
        connection,
        """
        SELECT COUNT(*)
        FROM attendance
        JOIN sessions ON sessions.session_id = attendance.session_id
        WHERE sessions.course_code = ?
          AND ((? IS NOT NULL AND sessions.session_date < ?)
               OR (? IS NOT NULL AND sessions.session_date > ?))
        """,
        (course_code, start_date, start_date, end_date, end_date),
    )


def change_course_period(connection, course_code, start_date, end_date):
    """Change a course's dates and regenerate its class days (FR-25, BR-19, BR-20).

    Raises ValueError, and changes nothing, if the new dates are not valid, leave the
    block, leave an enrollment outside them (BR-17), or would lose saved records.
    Otherwise, in one transaction: sessions outside the new period are removed, class
    days are added for weekdays that are new to the period, and the dates are saved.
    Days inside both the old and the new period are not touched, so a removed holiday
    stays removed. Returns {"added": ..., "removed": ...}.
    """
    course = get_course(connection, course_code)
    old_start = course["start_date"]
    old_end = course["end_date"]

    if not validation.are_period_dates_valid(start_date, end_date):
        raise ValueError(validation.COURSE_DATES_ERROR)

    if course["block_id"] is not None:
        block = get_block(connection, course["block_id"])
        inside_block = validation.is_enrollment_in_course_period(
            start_date, end_date, block["start_date"], block["end_date"]
        )
        if not inside_block or start_date is None or end_date is None:
            period = validation.describe_course_period(block["start_date"], block["end_date"])
            raise ValueError(validation.COURSE_OUTSIDE_BLOCK_ERROR.format(
                course_code, block["block_id"], period
            ))

    enrollments_outside = count_enrollments_outside_period(
        connection, course_code, start_date, end_date
    )
    if enrollments_outside > 0:
        raise ValueError(validation.ENROLLMENTS_OUTSIDE_PERIOD_ERROR.format(
            enrollments_outside, course_code
        ))

    records_lost = count_records_outside_period(connection, course_code, start_date, end_date)
    if records_lost > 0:
        raise ValueError(validation.RECORDS_ON_REMOVED_DAYS_ERROR.format(
            records_lost, course_code
        ))

    with connection:
        return move_course_period(connection, course_code, old_start, old_end,
                                  start_date, end_date)


def move_course_period(connection, course_code, old_start, old_end, start_date, end_date):
    """Save a course's new dates and regenerate its class days, inside the caller's
    transaction (used by change_course_period and change_block). The checks are done
    by the caller. Returns {"added": ..., "removed": ...}.
    """
    # Weekdays of the new period that were outside the old period get a class day.
    new_class_days = []
    if start_date is not None and end_date is not None:
        for class_day in validation.list_class_days(start_date, end_date):
            if not validation.is_date_in_period(class_day, old_start, old_end):
                new_class_days.append(class_day)

    removed = connection.execute(
        """
        DELETE FROM sessions
        WHERE course_code = ?
          AND ((? IS NOT NULL AND session_date < ?)
               OR (? IS NOT NULL AND session_date > ?))
        """,
        (course_code, start_date, start_date, end_date, end_date),
    ).rowcount
    insert_class_days(connection, course_code, new_class_days)
    connection.execute(
        "UPDATE courses SET start_date = ?, end_date = ? WHERE course_code = ?",
        (start_date, end_date, course_code),
    )
    return {"added": len(new_class_days), "removed": removed}


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
    """Return all courses with their block and dates, sorted by code."""
    return connection.execute(
        """
        SELECT course_code, course_name, block_id, start_date, end_date
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


def get_course_enrollments(connection, course_code):
    """Return the students enrolled in a course with their enrollment dates, sorted by ID."""
    return connection.execute(
        """
        SELECT students.student_id, students.full_name,
               enrollments.start_date, enrollments.end_date
        FROM enrollments
        JOIN students ON students.student_id = enrollments.student_id
        WHERE enrollments.course_code = ?
        ORDER BY students.student_id
        """,
        (course_code,),
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

def add_session(connection, session_id, course_code, session_date, session_type="Class"):
    """Save a session with a given ID (used for old-style data and tests).

    New class days are generated by create_course() and tutorials by add_tutorial().
    """
    connection.execute(
        """
        INSERT INTO sessions (session_id, course_code, session_date, session_type)
        VALUES (?, ?, ?, ?)
        """,
        (session_id, course_code, session_date, session_type),
    )
    connection.commit()


def get_session(connection, session_id):
    """Return one session row, or None if the ID is not saved."""
    return connection.execute(
        """
        SELECT session_id, course_code, session_date, session_type
        FROM sessions WHERE session_id = ?
        """,
        (session_id,),
    ).fetchone()


def get_sessions_for_course(connection, course_code):
    """Return the sessions (class days and tutorials) of a course in date order."""
    return connection.execute(
        """
        SELECT session_id, course_code, session_date, session_type
        FROM sessions
        WHERE course_code = ?
        ORDER BY session_date, session_id
        """,
        (course_code,),
    ).fetchall()


def get_class_session(connection, course_code, session_date):
    """Return the Class session of a course on a date, or None if there is no class."""
    return connection.execute(
        """
        SELECT session_id, course_code, session_date, session_type
        FROM sessions
        WHERE course_code = ? AND session_date = ? AND session_type = 'Class'
        """,
        (course_code, session_date),
    ).fetchone()


def get_tutorials_on_date(connection, course_code, session_date):
    """Return the tutorials of a course on a date, T1 first."""
    return connection.execute(
        """
        SELECT session_id, course_code, session_date, session_type
        FROM sessions
        WHERE course_code = ? AND session_date = ? AND session_type = 'Tutorial'
        ORDER BY session_id
        """,
        (course_code, session_date),
    ).fetchall()


def next_tutorial_id(connection, course_code, session_date, taken_ids=()):
    """Return the next free tutorial ID on a date: T1, then T2, and so on (BR-21).

    taken_ids lists IDs planned but not saved yet (for example earlier rows of a file).
    """
    number = 1
    while True:
        session_id = validation.make_tutorial_session_id(course_code, session_date, number)
        if get_session(connection, session_id) is None and session_id not in taken_ids:
            return session_id
        number = number + 1


def add_tutorial(connection, course_code, session_date):
    """Add a tutorial on any date inside the course period and return its ID (BR-21).

    Raises ValueError if the date is outside the course period (BR-16).
    """
    course = get_course(connection, course_code)
    if not validation.is_date_in_period(session_date, course["start_date"], course["end_date"]):
        period = validation.describe_course_period(course["start_date"], course["end_date"])
        raise ValueError(validation.SESSION_OUTSIDE_COURSE_ERROR.format(course_code, period))

    session_id = next_tutorial_id(connection, course_code, session_date)
    add_session(connection, session_id, course_code, session_date, validation.TUTORIAL)
    return session_id


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

    Each record has student_id, full_name, course_code, session_id, date, type and status.
    A tutorial that does not exist yet is created (IR-13); a class day always exists.
    The student is enrolled before attendance is saved, so BR-09 holds (IR-06).
    enrollment_starts maps (student_id, course_code) to the start date of a NEW
    enrollment (BR-15); an existing enrollment keeps its dates.
    A record with 'update' set to True changes the saved status instead (FR-31 S4).
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
                INSERT OR IGNORE INTO sessions
                    (session_id, course_code, session_date, session_type)
                VALUES (?, ?, ?, ?)
                """,
                (record["session_id"], record["course_code"], record["date"], record["type"]),
            )
            enrollment_key = (record["student_id"], record["course_code"])
            # A start equal to the course's start is stored as NULL (BR-17).
            start_date, end_date = check_enrollment_dates(
                connection, record["course_code"], enrollment_starts[enrollment_key], None
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO enrollments (student_id, course_code, start_date)
                VALUES (?, ?, ?)
                """,
                (record["student_id"], record["course_code"], start_date),
            )
            if record.get("update"):
                # "Use file" (FR-31 S4): the saved record takes the file's status.
                connection.execute(
                    """
                    UPDATE attendance
                    SET status = ?, source = ?, recorded_at = ?
                    WHERE student_id = ? AND session_id = ?
                    """,
                    (record["status"], source, recorded_at,
                     record["student_id"], record["session_id"]),
                )
                continue
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


# ---------- Demo reset ----------

def clear_all_data(connection):
    """Delete every row from every table, in one transaction (used by "Reset demo data").

    The settings go back to their defaults.

    Rows that point to others go first, so the foreign keys stay valid.
    """
    with connection:
        connection.execute("DELETE FROM attendance")
        connection.execute("DELETE FROM enrollments")
        connection.execute("DELETE FROM sessions")
        connection.execute("DELETE FROM students")
        connection.execute("DELETE FROM courses")
        connection.execute("DELETE FROM blocks")
        # The demo uses the default deductions, Late = 1 and Absent = 2.
        connection.execute("DELETE FROM settings")
        add_default_settings(connection)


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


def count_delete_course(connection, course_code):
    """Return what deleting a course would remove (Version 3 rule, Section 11)."""
    return {
        "class_days": count_rows(
            connection,
            "SELECT COUNT(*) FROM sessions WHERE course_code = ? AND session_type = 'Class'",
            (course_code,),
        ),
        "tutorials": count_rows(
            connection,
            "SELECT COUNT(*) FROM sessions WHERE course_code = ? AND session_type = 'Tutorial'",
            (course_code,),
        ),
        "enrollments": count_rows(
            connection, "SELECT COUNT(*) FROM enrollments WHERE course_code = ?", (course_code,)
        ),
        "attendance": count_rows(
            connection,
            """
            SELECT COUNT(*) FROM attendance
            WHERE session_id IN (SELECT session_id FROM sessions WHERE course_code = ?)
            """,
            (course_code,),
        ),
        "courses": 1,
    }


def delete_course(connection, course_code):
    """Delete a course with its class days, tutorials, enrollments and records.

    Class days are generated, so a course always has sessions; the Version 2 rule
    "only when it has no sessions" is replaced by a preview of counts and a
    confirmation in the app (Section 11). Everything is removed in one transaction:
    the rows that point to others go first, so the foreign keys stay valid.
    """
    counts = count_delete_course(connection, course_code)

    with connection:
        connection.execute(
            """
            DELETE FROM attendance
            WHERE session_id IN (SELECT session_id FROM sessions WHERE course_code = ?)
            """,
            (course_code,),
        )
        connection.execute("DELETE FROM enrollments WHERE course_code = ?", (course_code,))
        connection.execute("DELETE FROM sessions WHERE course_code = ?", (course_code,))
        cursor = connection.execute("DELETE FROM courses WHERE course_code = ?", (course_code,))

    counts["courses"] = cursor.rowcount
    return counts


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
    enrollment_start, enrollment_end, session_type and block_id (None for a course with
    no block). The status is None when nothing was recorded. Unknown is never stored (BR-12).
    """
    rows = connection.execute(
        """
        SELECT students.student_id, students.full_name, sessions.course_code,
               sessions.session_id, sessions.session_date, attendance.status,
               enrollments.start_date AS enrollment_start,
               enrollments.end_date AS enrollment_end,
               sessions.session_type, courses.block_id
        FROM enrollments
        JOIN students ON students.student_id = enrollments.student_id
        JOIN sessions ON sessions.course_code = enrollments.course_code
        JOIN courses ON courses.course_code = enrollments.course_code
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
