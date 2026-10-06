"""Tests for rename and delete in database.py (FR-22, FR-23).

Every test loads the v2_data.py data into a temporary in-memory database,
never attendance.db. The expected counts were worked out by hand from v2_data.py.
"""

import unittest

import analytics
import database
from tests import v2_data
import validation

TEST_DB_PATH = ":memory:"

# Each query counts rows that point to something that no longer exists.
ORPHAN_QUERIES = [
    """SELECT COUNT(*) FROM attendance
       WHERE student_id NOT IN (SELECT student_id FROM students)
          OR session_id NOT IN (SELECT session_id FROM sessions)""",
    """SELECT COUNT(*) FROM enrollments
       WHERE student_id NOT IN (SELECT student_id FROM students)
          OR course_code NOT IN (SELECT course_code FROM courses)""",
    """SELECT COUNT(*) FROM sessions
       WHERE course_code NOT IN (SELECT course_code FROM courses)""",
]


class SeedDatabaseTestCase(unittest.TestCase):
    """Base class: the seed data in an in-memory database. It has no tests itself."""

    def setUp(self):
        """Load the demo data."""
        self.connection = v2_data.reset_database(TEST_DB_PATH)
        v2_data.add_demo_data(self.connection)
        v2_data.add_demo_attendance(self.connection)

    def tearDown(self):
        """Close the database after each test."""
        self.connection.close()

    def count(self, query, parameters=()):
        """Return the number from a SELECT COUNT(*) query."""
        return self.connection.execute(query, parameters).fetchone()[0]

    def assert_no_orphans(self):
        """Check that no row points to a deleted student, session or course."""
        for query in ORPHAN_QUERIES:
            self.assertEqual(self.count(query), 0, query)

    def dashboard_totals(self):
        """Return the Dashboard metrics for All courses and the full date range."""
        records = analytics.build_records_frame(database.get_expected_records(self.connection))
        return analytics.calculate_dashboard_metrics(records)


class TestRename(SeedDatabaseTestCase):

    def test_rename_student(self):
        """FR-22: the name changes and the student ID stays the same."""
        new_name = validation.clean_name("  Jean-Paul   Mugisha-Habimana ")
        self.assertTrue(validation.is_valid_name(new_name))

        database.rename_student(self.connection, "002", new_name)

        student = database.get_student(self.connection, "002")
        self.assertEqual(student["full_name"], "Jean-Paul Mugisha-Habimana")
        self.assertEqual(self.count("SELECT COUNT(*) FROM students"), 12)

    def test_rename_course(self):
        """FR-22: the course name changes and the code stays the same."""
        new_name = validation.clean_course_name("  Python Programming ")
        self.assertEqual(new_name, "Python Programming")

        database.rename_course(self.connection, "PY101", new_name)

        self.assertEqual(database.get_course_name(self.connection, "PY101"), new_name)
        self.assertEqual(len(database.get_sessions_for_course(self.connection, "PY101")), 4)

    def test_rename_values_are_validated(self):
        """FR-22 (BR-02, BR-04): invalid new names are rejected before any update."""
        self.assertFalse(validation.is_valid_name(validation.clean_name("-Nadia")))
        self.assertIsNone(validation.clean_course_name("   "))
        self.assertIsNone(validation.clean_course_name("A" * 81))


class TestDeleteAttendanceRecord(SeedDatabaseTestCase):

    def test_delete_present_record(self):
        """FR-23: deleting 001's Present in PY101-W1 gives 62 Present, 9 Absent, 5 Unknown.

        By hand: 63 - 1 = 62 Present; 4 + 1 = 5 Unknown; rate 62 / 71 = 87.32%;
        completeness 71 / 76 = 93.42%.
        """
        counts = database.delete_attendance_record(self.connection, "001", "PY101-W1")

        self.assertEqual(counts, {"attendance": 1})
        self.assertIsNone(database.get_status(self.connection, "001", "PY101-W1"))

        totals = self.dashboard_totals()
        self.assertEqual((totals["present"], totals["absent"], totals["unknown"]), (62, 9, 5))
        self.assertEqual(analytics.format_rate(totals["attendance_rate"]), "87.32%")
        self.assertEqual(analytics.format_rate(totals["completeness"]), "93.42%")

    def test_delete_absent_record(self):
        """FR-23: deleting 002's Absent in PY101-W1 gives 63 Present, 8 Absent, 5 Unknown.

        By hand: 9 - 1 = 8 Absent; rate 63 / 71 = 88.73%.
        """
        database.delete_attendance_record(self.connection, "002", "PY101-W1")

        totals = self.dashboard_totals()
        self.assertEqual((totals["present"], totals["absent"], totals["unknown"]), (63, 8, 5))
        self.assertEqual(analytics.format_rate(totals["attendance_rate"]), "88.73%")


class TestUnenroll(SeedDatabaseTestCase):

    def test_unenroll_removes_course_records_only(self):
        """FR-23: 004 leaves DS102: 4 DS102 records and 1 enrollment go; PY101 is untouched."""
        preview = database.count_unenroll(self.connection, "004", "DS102")
        counts = database.unenroll_student(self.connection, "004", "DS102")

        self.assertEqual(counts, {"attendance": 4, "enrollments": 1})
        self.assertEqual(counts, preview)
        self.assertFalse(database.is_enrolled(self.connection, "004", "DS102"))
        self.assertTrue(database.is_enrolled(self.connection, "004", "PY101"))
        self.assertEqual(database.count_course_attendance(self.connection, "004", "PY101"), 4)
        self.assertEqual(database.count_course_attendance(self.connection, "004", "DS102"), 0)
        self.assert_no_orphans()

    def test_unenroll_with_missing_record(self):
        """FR-23: 012 has 3 DS102 records (DS102-W3 was never recorded), so 3 are removed."""
        counts = database.unenroll_student(self.connection, "012", "DS102")

        self.assertEqual(counts, {"attendance": 3, "enrollments": 1})
        self.assert_no_orphans()


class TestDeleteStudent(SeedDatabaseTestCase):

    def test_delete_student_removes_everything(self):
        """FR-23: 004 has 8 records (4 per course) and 2 enrollments; all are removed."""
        preview = database.count_delete_student(self.connection, "004")
        counts = database.delete_student(self.connection, "004")

        self.assertEqual(counts, {"attendance": 8, "enrollments": 2, "students": 1})
        self.assertEqual(counts, preview)
        self.assertIsNone(database.get_student(self.connection, "004"))
        self.assertEqual(self.count("SELECT COUNT(*) FROM attendance WHERE student_id = ?",
                                    ("004",)), 0)
        self.assert_no_orphans()

    def test_deleted_id_can_be_used_again(self):
        """FR-23: after deleting 004, a new student can be added with ID 004."""
        database.delete_student(self.connection, "004")

        database.add_student(self.connection, "004", "Alice Uwimana")
        database.enroll_student(self.connection, "004", "PY101")

        self.assertEqual(database.get_student(self.connection, "004")["full_name"],
                         "Alice Uwimana")
        # The new student has no old records: Unknown for all 4 PY101 sessions.
        self.assertEqual(database.count_course_attendance(self.connection, "004", "PY101"), 0)


class TestDeleteSession(SeedDatabaseTestCase):

    def test_delete_session(self):
        """FR-23: DS102-W3 has 7 records (9 enrolled, 008 and 012 missing); all are removed."""
        preview = database.count_delete_session(self.connection, "DS102-W3")
        counts = database.delete_session(self.connection, "DS102-W3")

        self.assertEqual(counts, {"attendance": 7, "sessions": 1})
        self.assertEqual(counts, preview)
        self.assertIsNone(database.get_session(self.connection, "DS102-W3"))
        self.assertEqual(self.count("SELECT COUNT(*) FROM sessions"), 7)
        self.assert_no_orphans()

        # By hand: DS102-W3 had 6 Present, 1 Absent (011) and 2 Unknown (008, 012).
        # Present 63 - 6 = 57; Absent 9 - 1 = 8; Unknown 4 - 2 = 2.
        totals = self.dashboard_totals()
        self.assertEqual((totals["present"], totals["absent"], totals["unknown"]), (57, 8, 2))


class TestDeleteCourse(SeedDatabaseTestCase):

    def test_delete_course_counts(self):
        """FR-23 (Version 3 rule): PY101 is deleted with everything in it; the preview
        matches. By hand: 4 class days, 0 tutorials, 10 enrollments, and 40 - 2 missing
        = 38 attendance records."""
        preview = database.count_delete_course(self.connection, "PY101")
        counts = database.delete_course(self.connection, "PY101")

        expected = {"class_days": 4, "tutorials": 0, "enrollments": 10, "attendance": 38,
                    "courses": 1}
        self.assertEqual(preview, expected)
        self.assertEqual(counts, expected)
        self.assertFalse(database.course_exists(self.connection, "PY101"))
        self.assert_no_orphans()

    def test_other_courses_are_untouched(self):
        """FR-23: deleting PY101 leaves DS102 as it was: 30 Present, 4 Absent, 2 Unknown;
        the students themselves are kept."""
        database.delete_course(self.connection, "PY101")

        totals = self.dashboard_totals()
        self.assertEqual((totals["present"], totals["absent"], totals["unknown"]), (30, 4, 2))
        self.assertEqual(self.count("SELECT COUNT(*) FROM students"), 12)

    def test_course_with_a_tutorial(self):
        """FR-23: tutorials are counted separately from class days."""
        database.add_session(self.connection, "PY101-T1", "PY101", "2026-09-19", "Tutorial")

        counts = database.count_delete_course(self.connection, "PY101")

        self.assertEqual((counts["class_days"], counts["tutorials"]), (4, 1))

    def test_empty_course_is_deleted(self):
        """FR-23: a course with no sessions and no students is deleted; every other count is 0."""
        database.add_course(self.connection, "ML300", "Machine Learning")

        counts = database.delete_course(self.connection, "ML300")

        self.assertEqual(counts, {"class_days": 0, "tutorials": 0, "enrollments": 0,
                                  "attendance": 0, "courses": 1})
        self.assertFalse(database.course_exists(self.connection, "ML300"))
        self.assert_no_orphans()


if __name__ == "__main__":
    unittest.main()
