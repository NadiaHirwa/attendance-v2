"""Tests for mark deductions (BR-22, FR-29).

Every test uses a temporary in-memory database, never attendance.db.
Seed facts used below (seed_demo.py): 002 in PY101 has 2 Late and 5 Absent;
001's only Late is at the PY101 tutorial on 03/09; 008's DS102 tutorial on 17/09
is not recorded.
"""

import unittest

import analytics
import database
import seed_demo
import validation

TEST_DB_PATH = ":memory:"

# A database from before Stage 3: no settings table.
OLD_SCHEMA = """
CREATE TABLE courses (course_code TEXT PRIMARY KEY, course_name TEXT NOT NULL);
CREATE TABLE students (student_id TEXT PRIMARY KEY, full_name TEXT NOT NULL);
CREATE TABLE enrollments (student_id TEXT NOT NULL, course_code TEXT NOT NULL,
                          PRIMARY KEY (student_id, course_code));
CREATE TABLE sessions (session_id TEXT PRIMARY KEY, course_code TEXT NOT NULL,
                       session_date TEXT NOT NULL);
CREATE TABLE attendance (student_id TEXT NOT NULL, session_id TEXT NOT NULL,
                         status TEXT NOT NULL CHECK (status IN ('Present', 'Absent')),
                         source TEXT NOT NULL, recorded_at TEXT NOT NULL,
                         PRIMARY KEY (student_id, session_id));
"""


def make_records(statuses):
    """Return a records frame for student 001 in PY101 with one session per status.

    None means no record (Unknown).
    """
    records = []
    for number, status in enumerate(statuses, start=1):
        records.append({
            "student_id": "001", "full_name": "Nadia Hirwa", "course_code": "PY101",
            "session_id": f"S{number}", "session_date": f"2026-09-{number:02d}",
            "status": status, "enrollment_start": None, "enrollment_end": None,
        })
    return analytics.build_records_frame(records)


class TestCalculation(unittest.TestCase):

    def test_worked_example(self):
        """BR-22, by hand: 2 Late + 3 Absent = 2 x 1 + 3 x 2 = 8 with the defaults,
        and 2 x 2 + 3 x 3 = 13 with Late 2 / Absent 3."""
        self.assertEqual(analytics.calculate_deduction(2, 3, 1, 2), 8)
        self.assertEqual(analytics.calculate_deduction(2, 3, 2, 3), 13)

    def test_excused_and_present_deduct_nothing(self):
        """BR-22: 3 Excused and 2 Present deduct 0."""
        records = make_records(["Excused", "Excused", "Excused", "Present", "Present"])
        table = analytics.build_deductions_table(records, 1, 2)

        self.assertEqual(table[analytics.DEDUCTED_COLUMN].iloc[0], 0)
        self.assertEqual(table["Excused"].iloc[0], 3)

    def test_unknown_deducts_nothing_and_is_flagged(self):
        """BR-22: 2 Unknown and 1 Absent deduct 2 (the Absent only), flagged '2 not recorded'."""
        records = make_records([None, None, "Absent"])
        summary = analytics.add_deduction_columns(
            analytics.build_course_summary(records), 1, 2
        )

        self.assertEqual(summary[analytics.DEDUCTED_COLUMN].iloc[0], 2)
        self.assertEqual(summary[analytics.NOT_RECORDED_FLAG_COLUMN].iloc[0], "2 not recorded")

    def test_no_flag_when_everything_is_recorded(self):
        """FR-29: the flag is empty when nothing is missing."""
        records = make_records(["Present", "Late"])
        summary = analytics.add_deduction_columns(analytics.build_course_summary(records), 1, 2)

        self.assertEqual(summary[analytics.NOT_RECORDED_FLAG_COLUMN].iloc[0], "")

    def test_no_maximum(self):
        """BR-22: there is no maximum: 20 Late + 30 Absent at 10 each = 500."""
        self.assertEqual(analytics.calculate_deduction(20, 30, 10, 10), 500)


class TestSettingsValidation(unittest.TestCase):

    def test_accepted_values(self):
        """BR-22: whole numbers 0 to 10 are accepted, also as text or 5.0."""
        for value, expected in [(0, 0), (10, 10), ("0", 0), (" 10 ", 10), (5.0, 5)]:
            self.assertEqual(validation.parse_deduction(value), expected, value)

    def test_rejected_values(self):
        """BR-22: -1, 11, 1.5, text, empty and True are rejected."""
        for value in [-1, 11, 1.5, "1.5", "-1", "two", "", True]:
            self.assertIsNone(validation.parse_deduction(value), value)


class SeedTestCase(unittest.TestCase):
    """Base class: the Version 3 seed in an in-memory database. It has no tests itself."""

    def setUp(self):
        """Create the seed data (the settings start at Late 1, Absent 2)."""
        self.connection = database.get_connection(TEST_DB_PATH)
        database.create_tables(self.connection)
        seed_demo.create_demo_data(self.connection)

    def tearDown(self):
        """Close the database after each test."""
        self.connection.close()

    def records(self):
        """Return all expected records as a frame."""
        return analytics.build_records_frame(database.get_expected_records(self.connection))

    def settings(self):
        """Return (late, absent) from the settings table."""
        settings = database.get_deduction_settings(self.connection)
        return settings["late"], settings["absent"]

    def deduction_of(self, table, student_id, course_code=None):
        """Return the deducted marks of one student (and course) in a table."""
        rows = table[table["student_id"] == student_id]
        if course_code is not None:
            rows = rows[rows["course_code"] == course_code]
        return rows[analytics.DEDUCTED_COLUMN].iloc[0]


class TestSettingsInDatabase(SeedTestCase):

    def test_defaults(self):
        """BR-22: a new database starts with Late 1 and Absent 2."""
        self.assertEqual(self.settings(), (1, 2))

    def test_save_and_read(self):
        """BR-22: saved values are read back; 0 and 10 are allowed."""
        database.save_deduction_settings(self.connection, 0, 10)

        self.assertEqual(self.settings(), (0, 10))

    def test_invalid_value_saves_nothing(self):
        """BR-22, BR-13: Absent 11 is refused with a clear message; Late is not saved either."""
        with self.assertRaises(ValueError) as error:
            database.save_deduction_settings(self.connection, 3, 11)

        self.assertIn("Expected a whole number from 0 to 10", str(error.exception))
        self.assertEqual(self.settings(), (1, 2))

    def test_reset_demo_restores_defaults(self):
        """BR-22: 'Reset demo data' puts the settings back to Late 1 and Absent 2."""
        database.save_deduction_settings(self.connection, 5, 5)

        seed_demo.reset_demo_data(self.connection)

        self.assertEqual(self.settings(), (1, 2))

    def test_old_database_gets_settings(self):
        """BR-22: an older database gets the settings table with the defaults."""
        connection = database.get_connection(TEST_DB_PATH)
        connection.executescript(OLD_SCHEMA)
        database.create_tables(connection)

        self.assertEqual(database.get_deduction_settings(connection), {"late": 1, "absent": 2})
        connection.close()


class TestDeductionsOnSeed(SeedTestCase):

    def test_002_in_py101_with_defaults(self):
        """FR-29, by hand: 002 in PY101 has 2 Late and 5 Absent: 2 x 1 + 5 x 2 = 12."""
        late, absent = self.settings()
        table = analytics.build_deductions_table(self.records(), late, absent)

        self.assertEqual(self.deduction_of(table, "002", "PY101"), 12)

    def test_tutorials_count(self):
        """BR-21, BR-22: 001's only Late is at the PY101 tutorial on 03/09, so 1 mark."""
        table = analytics.build_deductions_table(self.records(), 1, 2)

        self.assertEqual(self.deduction_of(table, "001", "PY101"), 1)

    def test_changing_a_setting_changes_every_report(self):
        """FR-29: with Late 2 / Absent 3, 002 in PY101 loses 2 x 2 + 5 x 3 = 19 marks in the
        deductions table, the export, the student profile, the by-course table and the
        per-student summary (002 has no Late or Absent in other courses)."""
        database.save_deduction_settings(self.connection, 2, 3)
        late, absent = self.settings()
        records = self.records()
        student = analytics.filter_student(records, "002")

        deductions = analytics.build_deductions_table(records, late, absent)
        export = analytics.build_course_deductions(records, "PY101", late, absent)
        profile = analytics.build_student_profile(student, late, absent)
        by_course = analytics.add_deduction_columns(
            analytics.build_course_summary(student), late, absent
        )
        summary = analytics.add_deduction_columns(
            analytics.build_student_summary(records), late, absent
        )

        self.assertEqual(self.deduction_of(deductions, "002", "PY101"), 19)
        self.assertEqual(
            export[export["Student ID"] == "002"][analytics.DEDUCTED_COLUMN].iloc[0], 19
        )
        self.assertEqual(
            profile[profile["course_code"] == "PY101"][analytics.DEDUCTED_COLUMN].iloc[0], 19
        )
        self.assertEqual(
            by_course[by_course["course_code"] == "PY101"][analytics.DEDUCTED_COLUMN].iloc[0],
            19,
        )
        self.assertEqual(self.deduction_of(summary, "002"), 19)

    def test_course_export(self):
        """FR-29: the PY101 export has one row per enrolled student, sorted by ID, with the
        columns for the grade sheet; 008's missing DS102 tutorial shows in DS102's export."""
        records = self.records()
        py101 = analytics.build_course_deductions(records, "PY101", 1, 2)
        ds102 = analytics.build_course_deductions(records, "DS102", 1, 2)

        self.assertEqual(list(py101.columns), [
            "Student ID", "Full name", "Late", "Absent", "Excused", "Not recorded",
            analytics.DEDUCTED_COLUMN,
        ])
        self.assertEqual(len(py101), 12)
        self.assertEqual(list(py101["Student ID"]), sorted(py101["Student ID"]))
        row_008 = ds102[ds102["Student ID"] == "008"].iloc[0]
        self.assertEqual((row_008["Not recorded"], row_008[analytics.DEDUCTED_COLUMN]), (1, 0))


if __name__ == "__main__":
    unittest.main()
