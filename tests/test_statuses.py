"""Tests for the Late and Excused statuses (BR-07, BR-10 to BR-12, BR-14, FR-26).

Every test uses a temporary in-memory database, never attendance.db.
"""

import os
import sqlite3
import unittest

import analytics
import database
import importer
import seed_demo

TEST_DB_PATH = ":memory:"
HEADER = "session_id,course_code,session_date,student_id,full_name,status\n"
DEMO_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), "demo_data")

# An attendance table from before this version: its CHECK allows only two statuses.
OLD_SCHEMA = """
CREATE TABLE courses (course_code TEXT PRIMARY KEY, course_name TEXT NOT NULL);
CREATE TABLE students (student_id TEXT PRIMARY KEY, full_name TEXT NOT NULL);
CREATE TABLE enrollments (
    student_id  TEXT NOT NULL REFERENCES students,
    course_code TEXT NOT NULL REFERENCES courses,
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
    status      TEXT NOT NULL CHECK (status IN ('Present', 'Absent')),
    source      TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    PRIMARY KEY (student_id, session_id)
);
INSERT INTO courses VALUES ('PY101', 'Programming with Python');
INSERT INTO students VALUES ('001', 'Nadia Hirwa');
INSERT INTO students VALUES ('002', 'Jean-Paul Mugisha');
INSERT INTO enrollments VALUES ('001', 'PY101');
INSERT INTO enrollments VALUES ('002', 'PY101');
INSERT INTO sessions VALUES ('PY101-W1', 'PY101', '2026-09-07');
INSERT INTO attendance VALUES ('001', 'PY101-W1', 'Present', 'manual', '2026-09-07T10:00:00');
INSERT INTO attendance VALUES ('002', 'PY101-W1', 'Absent', 'old.csv', '2026-09-07T10:00:00');
"""


def make_file(lines):
    """Return CSV bytes made of the standard header and the given data lines."""
    text = HEADER
    for line in lines:
        text = text + line + "\n"
    return text.encode("utf-8")


class TestRates(unittest.TestCase):

    def test_worked_example(self):
        """BR-10, BR-11: 6 Present, 1 Late, 1 Excused, 1 Absent, 1 Unknown.

        Attendance = (6 + 1) / (6 + 1 + 1) = 7 / 8 = 87.50% (Excused is left out).
        Completeness = (6 + 1 + 1 + 1) / 10 = 9 / 10 = 90.00%.
        """
        rates = analytics.calculate_rates(6, 1, 1, 1, 1)

        self.assertEqual(analytics.format_rate(rates["attendance_rate"]), "87.50%")
        self.assertEqual(analytics.format_rate(rates["completeness"]), "90.00%")
        self.assertEqual(rates["expected"], 10)

    def test_only_excused(self):
        """BR-10: only Excused records give an attendance rate of N/A, not an error."""
        rates = analytics.calculate_rates(0, 0, 3, 0, 0)

        self.assertEqual(analytics.format_rate(rates["attendance_rate"]), "N/A")
        self.assertEqual(analytics.format_rate(rates["completeness"]), "100.00%")


class TestStreaks(unittest.TestCase):

    def test_excused_ends_a_streak(self):
        """BR-14: Absent, Excused, Absent gives longest 1."""
        self.assertEqual(analytics.calculate_streaks(["Absent", "Excused", "Absent"]), (1, 1))

    def test_late_ends_a_streak(self):
        """BR-14: Absent, Absent, Late gives longest 2 and current 0."""
        self.assertEqual(analytics.calculate_streaks(["Absent", "Absent", "Late"]), (2, 0))


class TestUpgradeOldDatabase(unittest.TestCase):

    def setUp(self):
        """Create an old-style database and upgrade it."""
        self.connection = database.get_connection(TEST_DB_PATH)
        self.connection.executescript(OLD_SCHEMA)
        database.create_tables(self.connection)

    def tearDown(self):
        """Close the database after each test."""
        self.connection.close()

    def test_rows_survive_the_upgrade(self):
        """FR-26: both old records are still there, with their status and source."""
        rows = self.connection.execute(
            "SELECT student_id, status, source FROM attendance ORDER BY student_id"
        ).fetchall()

        self.assertEqual(len(rows), 2)
        self.assertEqual(tuple(rows[0]), ("001", "Present", "manual"))
        self.assertEqual(tuple(rows[1]), ("002", "Absent", "old.csv"))

    def test_late_and_excused_can_be_saved(self):
        """FR-26: after the upgrade, Late and Excused are accepted by the table."""
        result = database.record_attendance(self.connection, "002", "PY101-W1", "Late")

        self.assertEqual(result, "updated")
        self.assertEqual(database.get_status(self.connection, "002", "PY101-W1"), "Late")

    def test_rules_still_work_after_upgrade(self):
        """FR-26: the new table still refuses other statuses and missing sessions."""
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO attendance VALUES ('001', 'PY101-W1', 'Maybe', 'x', 'x')"
            )
        with self.assertRaises(sqlite3.IntegrityError):
            database.record_attendance(self.connection, "001", "NO-SUCH-SESSION", "Present")

    def test_upgrade_runs_once(self):
        """FR-26: running create_tables() again keeps the rows and changes nothing."""
        database.create_tables(self.connection)

        count = self.connection.execute("SELECT COUNT(*) FROM attendance").fetchone()[0]
        self.assertEqual(count, 2)


class SeedTestCase(unittest.TestCase):
    """Base class: the seed data in an in-memory database. It has no tests itself."""

    def setUp(self):
        """Load the demo data."""
        self.connection = seed_demo.reset_database(TEST_DB_PATH)
        seed_demo.add_demo_data(self.connection)
        seed_demo.add_demo_attendance(self.connection)

    def tearDown(self):
        """Close the database after each test."""
        self.connection.close()

    def totals(self):
        """Return the Dashboard metrics for all the data."""
        records = analytics.build_records_frame(database.get_expected_records(self.connection))
        return analytics.calculate_dashboard_metrics(records)

    def validate_bytes(self, file_bytes):
        """Read and validate a file; return (accepted, duplicates, rejected)."""
        rows, error = importer.read_csv(file_bytes)
        self.assertIsNone(error)
        return importer.validate_rows(self.connection, rows)

    def read_demo_file(self, name):
        """Return the bytes of a file in demo_data."""
        with open(os.path.join(DEMO_FOLDER, name), "rb") as demo_file:
            return demo_file.read()


class TestSeedAndImport(SeedTestCase):

    def test_seed_totals_unchanged(self):
        """FR-26: the seed still gives 63 Present, 0 Late, 0 Excused, 9 Absent, 4 Unknown."""
        totals = self.totals()

        self.assertEqual(
            (totals["present"], totals["late"], totals["excused"],
             totals["absent"], totals["unknown"]),
            (63, 0, 0, 9, 4),
        )
        self.assertEqual(analytics.format_rate(totals["attendance_rate"]), "87.50%")
        self.assertEqual(analytics.format_rate(totals["completeness"]), "94.74%")

    def test_import_late_and_excused(self):
        """FR-26: rows with L and E are accepted and saved as Late and Excused."""
        accepted, duplicates, rejected = self.validate_bytes(make_file([
            "PY101-W2,PY101,2026-09-14,003,Grace O'Neil,L",
            "DS102-W3,DS102,2026-09-23,008,Kevin Ndayishimiye,e",
        ]))
        importer.apply_import(self.connection, accepted, "test.csv")

        self.assertEqual(len(accepted), 2)
        self.assertEqual(database.get_status(self.connection, "003", "PY101-W2"), "Late")
        self.assertEqual(database.get_status(self.connection, "008", "DS102-W3"), "Excused")

    def test_messy_file_still_gives_5_2_10(self):
        """FR-26: messy_import.csv still gives 5 accepted, 2 skipped and 10 rejected."""
        accepted, duplicates, rejected = self.validate_bytes(
            self.read_demo_file("messy_import.csv")
        )

        self.assertEqual((len(accepted), len(duplicates), len(rejected)), (5, 2, 10))
        reasons = ""
        for row in rejected:
            reasons = reasons + row["reason"] + "\n"
        self.assertIn('Got "maybe"', reasons)

    def test_clean_file_adds_one_late_and_one_excused(self):
        """FR-26: clean_import.csv gives 14 accepted, including 1 Late and 1 Excused.

        By hand after the import: Present 63 + 9 (PY101-W5) + 1 (003 at W2) = 73;
        Absent 9 + 2 (002 and 007 at W5) = 11; Late 1 (010 at W4); Excused 1 (012 at DS102-W3);
        Unknown 1 (008 at DS102-W3). Rate (73 + 1) / (73 + 1 + 11) = 74 / 85 = 87.06%;
        completeness 86 / 87 = 98.85%.
        """
        accepted, duplicates, rejected = self.validate_bytes(
            self.read_demo_file("clean_import.csv")
        )
        self.assertEqual((len(accepted), len(duplicates), len(rejected)), (14, 0, 0))

        importer.apply_import(self.connection, accepted, "clean_import.csv")
        totals = self.totals()

        self.assertEqual(
            (totals["present"], totals["late"], totals["excused"],
             totals["absent"], totals["unknown"]),
            (73, 1, 1, 11, 1),
        )
        self.assertEqual(analytics.format_rate(totals["attendance_rate"]), "87.06%")
        self.assertEqual(analytics.format_rate(totals["completeness"]), "98.85%")

    def test_summaries_have_late_and_excused_columns(self):
        """FR-26: student, session and course summaries show Late and Excused."""
        records = analytics.build_records_frame(database.get_expected_records(self.connection))

        for table in [
            analytics.build_student_summary(records),
            analytics.build_session_summary(records),
            analytics.build_course_summary(analytics.filter_student(records, "001")),
        ]:
            self.assertIn("Late", list(table.columns))
            self.assertIn("Excused", list(table.columns))


if __name__ == "__main__":
    unittest.main()
