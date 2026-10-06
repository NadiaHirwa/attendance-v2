"""Tests for blocks, class days and tutorials in database.py (BR-18 to BR-21).

Every test uses a temporary in-memory database, never attendance.db.
Block B1-2627 runs Monday 07/09/2026 to Friday 25/09/2026: 15 weekdays.
"""

import sqlite3
import unittest

import database

TEST_DB_PATH = ":memory:"

# A database from before Version 3: no blocks table, no block_id, no session_type,
# and two sessions of PY101 on the same date.
OLD_SCHEMA = """
CREATE TABLE courses (course_code TEXT PRIMARY KEY, course_name TEXT NOT NULL,
                      start_date TEXT, end_date TEXT);
CREATE TABLE students (student_id TEXT PRIMARY KEY, full_name TEXT NOT NULL);
CREATE TABLE enrollments (
    student_id  TEXT NOT NULL REFERENCES students,
    course_code TEXT NOT NULL REFERENCES courses,
    start_date TEXT, end_date TEXT,
    PRIMARY KEY (student_id, course_code)
);
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    course_code TEXT NOT NULL REFERENCES courses,
    session_date TEXT NOT NULL
);
CREATE TABLE attendance (
    student_id  TEXT NOT NULL REFERENCES students,
    session_id  TEXT NOT NULL REFERENCES sessions,
    status      TEXT NOT NULL CHECK (status IN ('Present', 'Late', 'Excused', 'Absent')),
    source      TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    PRIMARY KEY (student_id, session_id)
);
INSERT INTO courses VALUES ('PY101', 'Programming with Python', NULL, NULL);
INSERT INTO students VALUES ('001', 'Nadia Hirwa');
INSERT INTO enrollments VALUES ('001', 'PY101', NULL, NULL);
INSERT INTO sessions VALUES ('PY101-W1', 'PY101', '2026-09-07');
INSERT INTO sessions VALUES ('PY101-EXTRA', 'PY101', '2026-09-07');
INSERT INTO attendance VALUES ('001', 'PY101-W1', 'Present', 'manual', '2026-09-07T10:00:00');
INSERT INTO attendance VALUES ('001', 'PY101-EXTRA', 'Late', 'manual', '2026-09-07T15:00:00');
"""


class BlockTestCase(unittest.TestCase):
    """Base class: block B1-2627 and course PY101 in it, student 001 enrolled."""

    def setUp(self):
        """Create the block, the course with its class days, and one student."""
        self.connection = database.get_connection(TEST_DB_PATH)
        database.create_tables(self.connection)
        database.add_block(self.connection, "B1-2627", "Block 1, 2026-27", "2026-09-07")
        self.class_days = database.create_course(
            self.connection, "PY101", "Programming with Python", "B1-2627"
        )
        database.add_student(self.connection, "001", "Nadia Hirwa")
        database.enroll_student(self.connection, "001", "PY101")

    def tearDown(self):
        """Close the database after each test."""
        self.connection.close()

    def class_dates(self):
        """Return the dates of PY101's class days, in order."""
        dates = []
        for session in database.get_sessions_for_course(self.connection, "PY101"):
            if session["session_type"] == "Class":
                dates.append(session["session_date"])
        return dates


class TestBlocksAndCourses(BlockTestCase):

    def test_block_end_is_calculated(self):
        """BR-18: the block's end is saved as Friday 25/09/2026, never typed."""
        block = database.get_block(self.connection, "B1-2627")

        self.assertEqual((block["start_date"], block["end_date"]), ("2026-09-07", "2026-09-25"))

    def test_course_takes_block_dates(self):
        """BR-19: a new course takes the block's dates."""
        course = database.get_course(self.connection, "PY101")

        self.assertEqual(course["block_id"], "B1-2627")
        self.assertEqual((course["start_date"], course["end_date"]), ("2026-09-07", "2026-09-25"))

    def test_class_days_are_generated(self):
        """BR-20: 15 class days, one per weekday, with generated IDs; no weekend."""
        dates = self.class_dates()

        self.assertEqual(self.class_days, 15)
        self.assertEqual(len(dates), 15)
        self.assertNotIn("2026-09-12", dates)
        self.assertNotIn("2026-09-13", dates)
        self.assertIsNotNone(database.get_session(self.connection, "PY101-2026-09-07"))
        self.assertIsNotNone(database.get_session(self.connection, "PY101-2026-09-25"))

    def test_one_class_per_course_per_day(self):
        """BR-20: a second Class session on the same date is refused by the database."""
        with self.assertRaises(sqlite3.IntegrityError):
            database.add_session(self.connection, "PY101-EXTRA", "PY101", "2026-09-07")


class TestShorterPeriod(BlockTestCase):

    def test_course_with_a_shorter_period(self):
        """BR-19, BR-20: DS102 from 14/09 to 25/09 gets 10 class days, only in that period."""
        class_days = database.create_course(
            self.connection, "DS102", "Data Science Basics", "B1-2627",
            "2026-09-14", "2026-09-25",
        )

        course = database.get_course(self.connection, "DS102")
        self.assertEqual(class_days, 10)
        self.assertEqual((course["start_date"], course["end_date"]), ("2026-09-14", "2026-09-25"))
        self.assertIsNone(database.get_class_session(self.connection, "DS102", "2026-09-11"))
        self.assertIsNotNone(database.get_class_session(self.connection, "DS102", "2026-09-14"))

    def test_shorter_period_must_stay_inside_block(self):
        """BR-19: a period that starts before the block is refused and nothing is created."""
        with self.assertRaises(ValueError) as error:
            database.create_course(
                self.connection, "DS102", "Data Science Basics", "B1-2627",
                "2026-09-01", "2026-09-25",
            )

        self.assertIn("must stay inside the block", str(error.exception))
        self.assertFalse(database.course_exists(self.connection, "DS102"))

    def test_shorter_period_end_before_start(self):
        """BR-19: an end before the start is refused."""
        with self.assertRaises(ValueError):
            database.create_course(
                self.connection, "DS102", "Data Science Basics", "B1-2627",
                "2026-09-21", "2026-09-14",
            )
        self.assertFalse(database.course_exists(self.connection, "DS102"))


class TestDeleteBlock(BlockTestCase):

    def test_block_with_courses_is_refused(self):
        """Section 6.1: block B1-2627 still has PY101, so it cannot be deleted."""
        with self.assertRaises(ValueError) as error:
            database.delete_block(self.connection, "B1-2627")

        self.assertIn("1 course(s)", str(error.exception))
        self.assertIsNotNone(database.get_block(self.connection, "B1-2627"))

    def test_empty_block_is_deleted(self):
        """Section 6.1: a block with no courses is deleted."""
        database.add_block(self.connection, "B2-2627", "Block 2, 2026-27", "2026-09-28")

        counts = database.delete_block(self.connection, "B2-2627")

        self.assertEqual(counts, {"blocks": 1})
        self.assertIsNone(database.get_block(self.connection, "B2-2627"))


class TestTutorials(BlockTestCase):

    def test_tutorials_are_numbered(self):
        """BR-21: two tutorials on one Saturday are T1 and T2; weekends are allowed."""
        first = database.add_tutorial(self.connection, "PY101", "2026-09-12")
        second = database.add_tutorial(self.connection, "PY101", "2026-09-12")

        self.assertEqual(first, "PY101-2026-09-12-T1")
        self.assertEqual(second, "PY101-2026-09-12-T2")
        self.assertEqual(database.get_session(self.connection, first)["session_type"], "Tutorial")

    def test_tutorial_on_a_class_day(self):
        """BR-21: a tutorial can be on the same date as a class."""
        tutorial_id = database.add_tutorial(self.connection, "PY101", "2026-09-10")

        self.assertEqual(tutorial_id, "PY101-2026-09-10-T1")
        self.assertIsNotNone(database.get_class_session(self.connection, "PY101", "2026-09-10"))

    def test_tutorial_outside_course_period_is_refused(self):
        """BR-21, BR-16: a tutorial after the course ends is refused."""
        with self.assertRaises(ValueError):
            database.add_tutorial(self.connection, "PY101", "2026-09-26")

    def test_tutorials_count_for_attendance(self):
        """BR-21: a tutorial is expected like a class: 001 has 15 + 1 = 16 expected sessions."""
        database.add_tutorial(self.connection, "PY101", "2026-09-12")

        self.assertEqual(len(database.get_expected_records(self.connection)), 16)


class TestChangeCoursePeriod(BlockTestCase):

    def test_narrowing_removes_class_days(self):
        """BR-19, BR-20: starting on 14/09 removes the 5 class days of week 1."""
        result = database.change_course_period(self.connection, "PY101", "2026-09-14",
                                               "2026-09-25")

        self.assertEqual(result, {"added": 0, "removed": 5})
        self.assertEqual(len(self.class_dates()), 10)
        self.assertEqual(self.class_dates()[0], "2026-09-14")

    def test_narrowing_refused_when_records_would_be_lost(self):
        """BR-20: a record on a day that would be removed blocks the change; nothing changes."""
        database.record_attendance(self.connection, "001", "PY101-2026-09-07", "Present")

        with self.assertRaises(ValueError) as error:
            database.change_course_period(self.connection, "PY101", "2026-09-14", "2026-09-25")

        self.assertIn("1 saved attendance record(s)", str(error.exception))
        self.assertEqual(len(self.class_dates()), 15)
        self.assertEqual(database.get_course(self.connection, "PY101")["start_date"],
                         "2026-09-07")

    def test_widening_adds_only_new_days_and_keeps_holidays(self):
        """BR-20: widening adds the days that are new to the period; a removed holiday
        inside the old period stays removed."""
        database.change_course_period(self.connection, "PY101", "2026-09-14", "2026-09-25")
        database.delete_session(self.connection, "PY101-2026-09-16")  # a holiday

        result = database.change_course_period(self.connection, "PY101", "2026-09-07",
                                               "2026-09-25")

        self.assertEqual(result, {"added": 5, "removed": 0})
        self.assertEqual(len(self.class_dates()), 14)
        self.assertNotIn("2026-09-16", self.class_dates())

    def test_course_must_stay_inside_block(self):
        """BR-19: a course period that leaves the block is refused."""
        with self.assertRaises(ValueError) as error:
            database.change_course_period(self.connection, "PY101", "2026-09-01", "2026-09-25")

        self.assertIn("must stay inside the block", str(error.exception))

    def test_enrollment_outside_new_period_is_refused(self):
        """BR-17: an enrollment starting 08/09 blocks a course start of 14/09."""
        database.add_student(self.connection, "002", "Grace Uwase")
        database.enroll_student(self.connection, "002", "PY101", "2026-09-08", None)

        with self.assertRaises(ValueError) as error:
            database.change_course_period(self.connection, "PY101", "2026-09-14", "2026-09-25")

        self.assertIn("1 enrollment(s)", str(error.exception))

    def test_tutorial_outside_new_period_is_removed(self):
        """BR-21: a tutorial with no records outside the new period is removed too."""
        database.add_tutorial(self.connection, "PY101", "2026-09-12")

        result = database.change_course_period(self.connection, "PY101", "2026-09-14",
                                               "2026-09-25")

        self.assertEqual(result["removed"], 6)
        self.assertIsNone(database.get_session(self.connection, "PY101-2026-09-12-T1"))


class TestUpgradeOldDatabase(unittest.TestCase):

    def setUp(self):
        """Create a database from before Version 3 and upgrade it."""
        self.connection = database.get_connection(TEST_DB_PATH)
        self.connection.executescript(OLD_SCHEMA)
        database.create_tables(self.connection)

    def tearDown(self):
        """Close the database after each test."""
        self.connection.close()

    def test_old_course_has_no_block(self):
        """Section 3: an old course keeps working with block_id NULL ("No block")."""
        course = database.get_course(self.connection, "PY101")

        self.assertIsNone(course["block_id"])
        self.assertEqual(database.get_blocks(self.connection), [])

    def test_old_sessions_become_class_and_records_are_kept(self):
        """Section 3: old sessions become Class; a second one on the same date becomes a
        Tutorial, so the one-class-per-day rule holds and no record is lost."""
        first = database.get_session(self.connection, "PY101-W1")
        second = database.get_session(self.connection, "PY101-EXTRA")

        self.assertEqual(first["session_type"], "Class")
        self.assertEqual(second["session_type"], "Tutorial")
        self.assertEqual(database.get_status(self.connection, "001", "PY101-W1"), "Present")
        self.assertEqual(database.get_status(self.connection, "001", "PY101-EXTRA"), "Late")

    def test_upgrade_runs_twice_safely(self):
        """Section 3: running create_tables() again changes nothing."""
        database.create_tables(self.connection)

        count = self.connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        self.assertEqual(count, 2)

    def test_old_course_can_still_be_recorded(self):
        """Section 3: attendance can still be recorded for an old course with no block."""
        database.add_session(self.connection, "PY101-W2", "PY101", "2026-09-14")

        result = database.record_attendance(self.connection, "001", "PY101-W2", "Present")
        self.assertEqual(result, "inserted")


if __name__ == "__main__":
    unittest.main()
