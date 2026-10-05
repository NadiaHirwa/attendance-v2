"""Tests for analytics.py and database.py (T06, T07, T13 and T14 in Section 10).

Every test uses a temporary in-memory database, never attendance.db.
"""

import sqlite3
import unittest

import analytics
import database

TEST_DB_PATH = ":memory:"


class DatabaseTestCase(unittest.TestCase):
    """Base class: gives each test a fresh in-memory database with one course and session."""

    def setUp(self):
        """Create the tables, course PY101 and session PY101-W1."""
        self.connection = database.get_connection(TEST_DB_PATH)
        database.create_tables(self.connection)
        database.add_course(self.connection, "PY101", "Programming with Python")
        database.add_session(self.connection, "PY101-W1", "PY101", "2026-09-15")

    def tearDown(self):
        """Close the database after each test."""
        self.connection.close()

    def add_enrolled_student(self, student_id, full_name):
        """Add a student and enroll them in PY101."""
        database.add_student(self.connection, student_id, full_name)
        database.enroll_student(self.connection, student_id, "PY101")


class TestRates(unittest.TestCase):

    def test_t06_worked_example(self):
        """T06 (BR-10, BR-11): 7 Present, 2 Absent, 1 Unknown gives 77.78% and 90.00%."""
        rates = analytics.calculate_rates(7, 2, 1)

        self.assertEqual(rates["attendance_rate"], 77.78)
        self.assertEqual(rates["completeness"], 90.0)
        self.assertEqual(analytics.format_rate(rates["attendance_rate"]), "77.78%")
        self.assertEqual(analytics.format_rate(rates["completeness"]), "90.00%")

    def test_t07_no_records(self):
        """T07 (BR-10, BR-11): 0 records gives N/A with no division error."""
        rates = analytics.calculate_rates(0, 0, 0)

        self.assertIsNone(rates["attendance_rate"])
        self.assertIsNone(rates["completeness"])
        self.assertEqual(analytics.format_rate(rates["attendance_rate"]), "N/A")
        self.assertEqual(analytics.format_rate(rates["completeness"]), "N/A")

    def test_t07_empty_frame(self):
        """T07 (BR-10, BR-11, FR-18): an empty database gives empty summaries, not an error."""
        frame = analytics.build_records_frame([])

        self.assertEqual(len(analytics.build_student_summary(frame)), 0)
        self.assertEqual(len(analytics.build_session_summary(frame)), 0)
        self.assertIsNone(analytics.summarize_frame(frame)["attendance_rate"])


class TestWorkedExampleFromDatabase(DatabaseTestCase):

    def test_t06_worked_example_from_database(self):
        """T06 (BR-10, BR-11, BR-12): 10 enrolled, 7 Present, 2 Absent, 1 not recorded."""
        for number in range(1, 11):
            student_id = f"{number:03d}"
            self.add_enrolled_student(student_id, f"Student {chr(64 + number)}")

        for number in range(1, 8):
            database.record_attendance(self.connection, f"{number:03d}", "PY101-W1", "Present")
        database.record_attendance(self.connection, "008", "PY101-W1", "Absent")
        database.record_attendance(self.connection, "009", "PY101-W1", "Absent")
        # Student 010 has no record, so they count as Unknown.

        records = database.get_expected_records(self.connection)
        frame = analytics.build_records_frame(records)
        rates = analytics.summarize_frame(frame)

        self.assertEqual(rates["present"], 7)
        self.assertEqual(rates["absent"], 2)
        self.assertEqual(rates["unknown"], 1)
        self.assertEqual(rates["attendance_rate"], 77.78)
        self.assertEqual(rates["completeness"], 90.0)

    def test_unknown_is_not_stored(self):
        """BR-12: Unknown is computed; the attendance table only holds Present or Absent."""
        self.add_enrolled_student("001", "Nadia Hirwa")

        frame = analytics.build_records_frame(database.get_expected_records(self.connection))
        self.assertEqual(list(frame["status"]), ["Unknown"])

        row_count = self.connection.execute("SELECT COUNT(*) FROM attendance").fetchone()[0]
        self.assertEqual(row_count, 0)


class TestRecordAttendance(DatabaseTestCase):

    def test_t13_recording_twice_updates(self):
        """T13 (BR-08): recording twice for the same student and session updates the record."""
        self.add_enrolled_student("001", "Nadia Hirwa")

        first = database.record_attendance(self.connection, "001", "PY101-W1", "Present")
        second = database.record_attendance(self.connection, "001", "PY101-W1", "Absent")

        self.assertEqual(first, "inserted")
        self.assertEqual(second, "updated")
        self.assertEqual(database.get_status(self.connection, "001", "PY101-W1"), "Absent")

        row_count = self.connection.execute("SELECT COUNT(*) FROM attendance").fetchone()[0]
        self.assertEqual(row_count, 1)

    def test_t13_same_status_is_not_rewritten(self):
        """T13 (BR-08, FR-08): saving the same status again leaves the record unchanged."""
        self.add_enrolled_student("001", "Nadia Hirwa")

        database.record_attendance(self.connection, "001", "PY101-W1", "Present")
        result = database.record_attendance(self.connection, "001", "PY101-W1", "Present")

        self.assertEqual(result, "unchanged")

    def test_t14_foreign_keys_are_on(self):
        """T14 (Section 3): attendance for a missing session raises an error."""
        self.add_enrolled_student("001", "Nadia Hirwa")

        with self.assertRaises(sqlite3.IntegrityError):
            database.record_attendance(self.connection, "001", "NO-SUCH-SESSION", "Present")

    def test_t14_foreign_keys_pragma(self):
        """T14 (Section 3): get_connection() switches foreign keys on."""
        value = self.connection.execute("PRAGMA foreign_keys").fetchone()[0]
        self.assertEqual(value, 1)


if __name__ == "__main__":
    unittest.main()
