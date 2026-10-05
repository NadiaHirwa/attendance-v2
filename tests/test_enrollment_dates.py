"""Tests for enrollment start and end dates (BR-15, FR-24).

Every test uses a temporary in-memory database, never attendance.db.
PY101 sessions in the seed data: W1 2026-09-07, W2 2026-09-14, W3 2026-09-21, W4 2026-09-28.
"""

import unittest

import analytics
import database
import importer
import seed_demo
import validation

TEST_DB_PATH = ":memory:"
HEADER = "session_id,course_code,session_date,student_id,full_name,status\n"

# The enrollments table as it was before this version, without the date columns.
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
    student_id TEXT NOT NULL REFERENCES students,
    session_id TEXT NOT NULL REFERENCES sessions,
    status TEXT NOT NULL CHECK (status IN ('Present', 'Absent')),
    source TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    PRIMARY KEY (student_id, session_id)
);
INSERT INTO courses VALUES ('PY101', 'Programming with Python');
INSERT INTO students VALUES ('001', 'Nadia Hirwa');
INSERT INTO enrollments VALUES ('001', 'PY101');
INSERT INTO sessions VALUES ('PY101-W1', 'PY101', '2026-09-07');
INSERT INTO attendance VALUES ('001', 'PY101-W1', 'Present', 'manual', '2026-09-07T10:00:00');
"""


def make_file(lines):
    """Return CSV bytes made of the standard header and the given data lines."""
    text = HEADER
    for line in lines:
        text = text + line + "\n"
    return text.encode("utf-8")


class TestWindowRules(unittest.TestCase):
    """BR-15 rules as pure functions."""

    def test_window_with_no_dates(self):
        """BR-15: with no start and no end, every session is expected."""
        self.assertTrue(validation.is_in_enrollment_window("2026-09-07", None, None))

    def test_window_start_and_end_are_included(self):
        """BR-15: the start date and the end date themselves are inside the window."""
        self.assertTrue(validation.is_in_enrollment_window("2026-09-14", "2026-09-14", None))
        self.assertTrue(validation.is_in_enrollment_window("2026-09-21", None, "2026-09-21"))

    def test_window_outside(self):
        """BR-15: before the start or after the end is outside the window."""
        self.assertFalse(validation.is_in_enrollment_window("2026-09-07", "2026-09-14", None))
        self.assertFalse(validation.is_in_enrollment_window("2026-09-28", None, "2026-09-21"))

    def test_end_before_start_is_invalid(self):
        """BR-15: the end date must not be before the start date."""
        self.assertFalse(validation.are_enrollment_dates_valid("2026-09-14", "2026-09-07"))
        self.assertTrue(validation.are_enrollment_dates_valid("2026-09-14", "2026-09-14"))
        self.assertTrue(validation.are_enrollment_dates_valid(None, "2026-09-07"))


class TestUpgradeOldDatabase(unittest.TestCase):

    def test_old_database_gets_date_columns(self):
        """FR-24: create_tables() adds start_date and end_date to an old database."""
        connection = database.get_connection(TEST_DB_PATH)
        connection.executescript(OLD_SCHEMA)

        database.create_tables(connection)
        database.create_tables(connection)  # Running it twice must also work.

        column_names = []
        for column in connection.execute("PRAGMA table_info(enrollments)"):
            column_names.append(column[1])
        self.assertIn("start_date", column_names)
        self.assertIn("end_date", column_names)

        # The old enrollment has no dates, so it behaves exactly as before.
        enrollment = database.get_enrollment(connection, "001", "PY101")
        self.assertIsNone(enrollment["start_date"])
        self.assertIsNone(enrollment["end_date"])

        records = database.get_expected_records(connection)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["status"], "Present")
        connection.close()


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
        """Return the Dashboard metrics for All courses and the full date range."""
        records = analytics.build_records_frame(database.get_expected_records(self.connection))
        return analytics.calculate_dashboard_metrics(records)

    def expected_sessions(self, student_id):
        """Return the session IDs a student is expected at, in date order."""
        session_ids = []
        for record in database.get_expected_records(self.connection):
            if record["student_id"] == student_id:
                session_ids.append(record["session_id"])
        return session_ids

    def add_student_013(self, start_date=None, end_date=None):
        """Add student 013 to PY101 with the given enrollment dates."""
        database.add_student(self.connection, "013", "Alice Uwimana")
        database.enroll_student(self.connection, "013", "PY101", start_date, end_date)


class TestSeedUnchanged(SeedTestCase):

    def test_seed_dates_are_null_and_totals_unchanged(self):
        """FR-24: the seed keeps every date NULL, so totals stay 63, 9, 4, 87.50%, 94.74%."""
        dated = self.connection.execute(
            "SELECT COUNT(*) FROM enrollments WHERE start_date IS NOT NULL "
            "OR end_date IS NOT NULL"
        ).fetchone()[0]
        self.assertEqual(dated, 0)

        totals = self.totals()
        self.assertEqual((totals["present"], totals["absent"], totals["unknown"]), (63, 9, 4))
        self.assertEqual(analytics.format_rate(totals["attendance_rate"]), "87.50%")
        self.assertEqual(analytics.format_rate(totals["completeness"]), "94.74%")


class TestExpectedSessions(SeedTestCase):

    def test_null_dates_behave_like_before(self):
        """BR-15: with no dates, 013 is expected at all 4 PY101 sessions (4 Unknown)."""
        self.add_student_013()

        self.assertEqual(
            self.expected_sessions("013"), ["PY101-W1", "PY101-W2", "PY101-W3", "PY101-W4"]
        )
        self.assertEqual(self.totals()["unknown"], 8)

    def test_late_joiner(self):
        """BR-15: 013 joins on 2026-09-21, so is not Unknown for W1 and W2 (only 2 Unknown)."""
        self.add_student_013(start_date="2026-09-21")

        self.assertEqual(self.expected_sessions("013"), ["PY101-W3", "PY101-W4"])
        self.assertEqual(self.totals()["unknown"], 6)

    def test_student_who_left(self):
        """BR-15: 013 left on 2026-09-14, so is not Unknown for W3 and W4."""
        self.add_student_013(end_date="2026-09-14")

        self.assertEqual(self.expected_sessions("013"), ["PY101-W1", "PY101-W2"])

    def test_start_and_end(self):
        """BR-15: from 2026-09-14 until 2026-09-21 means W2 and W3 only."""
        self.add_student_013(start_date="2026-09-14", end_date="2026-09-21")

        self.assertEqual(self.expected_sessions("013"), ["PY101-W2", "PY101-W3"])

    def test_record_attendance_list_follows_dates(self):
        """FR-24: Record Attendance lists 013 at W3 but not at W1."""
        self.add_student_013(start_date="2026-09-21")

        w1_ids = []
        for row in database.get_session_attendance(self.connection, "PY101-W1"):
            w1_ids.append(row["student_id"])
        w3_ids = []
        for row in database.get_session_attendance(self.connection, "PY101-W3"):
            w3_ids.append(row["student_id"])

        self.assertNotIn("013", w1_ids)
        self.assertIn("013", w3_ids)


class TestRecordOutsideEnrollment(SeedTestCase):

    def test_outside_window_is_not_saved(self):
        """BR-15: recording 013 at W1, before their start, returns 'outside_enrollment'."""
        self.add_student_013(start_date="2026-09-21")

        result = database.record_attendance(self.connection, "013", "PY101-W1", "Present")

        self.assertEqual(result, "outside_enrollment")
        self.assertIsNone(database.get_status(self.connection, "013", "PY101-W1"))

    def test_on_start_date_is_saved(self):
        """BR-15: recording 013 at W3, exactly on their start date, is saved."""
        self.add_student_013(start_date="2026-09-21")

        result = database.record_attendance(self.connection, "013", "PY101-W3", "Present")

        self.assertEqual(result, "inserted")


class TestChangeEnrollmentDates(SeedTestCase):

    def test_change_refused_when_records_fall_outside(self):
        """FR-24: 001 has a W1 record, so starting on 2026-09-14 would leave 1 record outside.

        002 has records at W3 and W4, so ending on 2026-09-14 would leave 2 outside.
        """
        outside_001 = database.count_records_outside_window(
            self.connection, "001", "PY101", "2026-09-14", None
        )
        outside_002 = database.count_records_outside_window(
            self.connection, "002", "PY101", None, "2026-09-14"
        )

        self.assertEqual(outside_001, 1)
        self.assertEqual(outside_002, 2)

    def test_change_allowed_when_no_records_outside(self):
        """FR-24: 010 has records W1 to W3 and W4 missing, so ending on 2026-09-21 is allowed.

        By hand: W4 is no longer expected for 010, so Unknown 4 - 1 = 3 and
        completeness = 72 / 75 = 96.00%.
        """
        outside = database.count_records_outside_window(
            self.connection, "010", "PY101", None, "2026-09-21"
        )
        self.assertEqual(outside, 0)

        database.update_enrollment_dates(self.connection, "010", "PY101", None, "2026-09-21")

        enrollment = database.get_enrollment(self.connection, "010", "PY101")
        self.assertEqual(enrollment["end_date"], "2026-09-21")
        totals = self.totals()
        self.assertEqual(totals["unknown"], 3)
        self.assertEqual(analytics.format_rate(totals["completeness"]), "96.00%")


class TestImportWithDates(SeedTestCase):

    def import_lines(self, lines):
        """Validate and import a file made of the given lines; return (accepted, rejected)."""
        rows, error = importer.read_csv(make_file(lines))
        self.assertIsNone(error)
        accepted, duplicates, rejected = importer.validate_rows(self.connection, rows)
        importer.apply_import(self.connection, accepted, "test.csv")
        return accepted, rejected

    def test_new_student_starts_at_earliest_row(self):
        """FR-24: a new student imported for W4 and W3 is enrolled from W3 (the earliest)."""
        self.import_lines([
            "PY101-W4,PY101,2026-09-28,013,Alice Uwimana,A",
            "PY101-W3,PY101,2026-09-21,013,Alice Uwimana,P",
        ])

        enrollment = database.get_enrollment(self.connection, "013", "PY101")
        self.assertEqual(enrollment["start_date"], "2026-09-21")
        self.assertIsNone(enrollment["end_date"])
        # Not Unknown for W1 and W2, which were before they joined.
        self.assertEqual(self.expected_sessions("013"), ["PY101-W3", "PY101-W4"])

    def test_existing_student_new_course_starts_at_row(self):
        """FR-24: 001 imported into DS102 at W2 is enrolled in DS102 from 2026-09-16."""
        self.import_lines(["DS102-W2,DS102,2026-09-16,001,Nadia Hirwa,P"])

        enrollment = database.get_enrollment(self.connection, "001", "DS102")
        self.assertEqual(enrollment["start_date"], "2026-09-16")
        # PY101 is unchanged: still no dates.
        self.assertIsNone(database.get_enrollment(self.connection, "001", "PY101")["start_date"])

    def test_row_before_start_is_rejected(self):
        """FR-24: 013 is enrolled from 2026-09-14, so a W1 row (2026-09-07) is rejected."""
        self.add_student_013(start_date="2026-09-14")

        accepted, rejected = self.import_lines(["PY101-W1,PY101,2026-09-07,013,Alice Uwimana,P"])

        self.assertEqual(len(accepted), 0)
        self.assertEqual(
            rejected[0]["reason"],
            "Row 2: Student 013 is enrolled in PY101 from 2026-09-14, not on 2026-09-07.",
        )

    def test_row_after_end_is_rejected(self):
        """FR-24: 013 was enrolled until 2026-09-14, so a W3 row (2026-09-21) is rejected."""
        self.add_student_013(end_date="2026-09-14")

        accepted, rejected = self.import_lines(["PY101-W3,PY101,2026-09-21,013,Alice Uwimana,P"])

        self.assertEqual(len(accepted), 0)
        self.assertEqual(
            rejected[0]["reason"],
            "Row 2: Student 013 was enrolled in PY101 until 2026-09-14, not on 2026-09-21.",
        )


class TestReportShowsDates(SeedTestCase):

    def test_by_course_shows_start_and_now(self):
        """FR-24: with no dates, the By course table shows 'start' and 'now'."""
        records = analytics.build_records_frame(database.get_expected_records(self.connection))
        table = analytics.build_course_summary(analytics.filter_student(records, "001"))

        self.assertEqual(table[analytics.ENROLLED_FROM_COLUMN].iloc[0], "start")
        self.assertEqual(table[analytics.ENROLLED_UNTIL_COLUMN].iloc[0], "now")

    def test_by_course_shows_dates(self):
        """FR-24: with dates, the By course table shows them."""
        self.add_student_013(start_date="2026-09-14", end_date="2026-09-21")

        records = analytics.build_records_frame(database.get_expected_records(self.connection))
        table = analytics.build_course_summary(analytics.filter_student(records, "013"))

        self.assertEqual(table[analytics.ENROLLED_FROM_COLUMN].iloc[0], "2026-09-14")
        self.assertEqual(table[analytics.ENROLLED_UNTIL_COLUMN].iloc[0], "2026-09-21")


if __name__ == "__main__":
    unittest.main()
