"""Tests for course start and end dates (BR-16, FR-25).

Every test uses a temporary in-memory database, never attendance.db.
Seed course dates: PY101 2026-09-07 to 2026-12-18, DS102 2026-09-09 to 2026-12-18.
PY101 sessions: W1 2026-09-07, W2 2026-09-14, W3 2026-09-21, W4 2026-09-28.
"""

import unittest

import analytics
import database
import importer
from tests import v2_data
import validation

TEST_DB_PATH = ":memory:"
HEADER = "course_code,date,student_id,full_name,status,type\n"

# The courses and enrollments tables as they were before any date columns existed.
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
INSERT INTO courses VALUES ('PY101', 'Programming with Python');
INSERT INTO sessions VALUES ('PY101-W1', 'PY101', '2026-09-07');
"""


def make_file(lines):
    """Return CSV bytes made of the standard header and the given data lines."""
    text = HEADER
    for line in lines:
        text = text + line + "\n"
    return text.encode("utf-8")


class TestPeriodRules(unittest.TestCase):
    """BR-16 rules as pure functions, with the PY101 seed period."""

    def test_session_inside_period(self):
        """BR-16: a date inside 2026-09-07 to 2026-12-18 is allowed."""
        self.assertTrue(validation.is_date_in_period("2026-10-05", "2026-09-07", "2026-12-18"))

    def test_session_on_boundary_dates(self):
        """BR-16: the start date and the end date themselves are allowed."""
        self.assertTrue(validation.is_date_in_period("2026-09-07", "2026-09-07", "2026-12-18"))
        self.assertTrue(validation.is_date_in_period("2026-12-18", "2026-09-07", "2026-12-18"))

    def test_session_outside_period(self):
        """BR-16: the day before the start and the day after the end are refused."""
        self.assertFalse(validation.is_date_in_period("2026-09-06", "2026-09-07", "2026-12-18"))
        self.assertFalse(validation.is_date_in_period("2026-12-19", "2026-09-07", "2026-12-18"))

    def test_no_dates_means_no_limit(self):
        """BR-16: a course with NULL dates allows any session date, like before."""
        self.assertTrue(validation.is_date_in_period("1990-01-01", None, None))
        self.assertTrue(validation.is_date_in_period("2099-01-01", "2026-09-07", None))

    def test_end_before_start_is_rejected(self):
        """BR-16: a course's end date must not be before its start date."""
        self.assertFalse(validation.are_period_dates_valid("2026-12-18", "2026-09-07"))
        self.assertTrue(validation.are_period_dates_valid("2026-09-07", "2026-09-07"))

    def test_period_messages(self):
        """BR-16, BR-13: the messages say the period and what is expected."""
        period = validation.describe_course_period("2026-09-07", "2026-12-18")
        self.assertEqual(
            validation.SESSION_OUTSIDE_COURSE_ERROR.format("PY101", period),
            "PY101 runs from 07/09/2026 to 18/12/2026. Choose a date in that period.",
        )
        self.assertEqual(validation.describe_course_period("2026-09-07", None),
                         "from 07/09/2026")
        self.assertEqual(validation.describe_course_period(None, "2026-12-18"),
                         "until 18/12/2026")


class TestUpgradeOldDatabase(unittest.TestCase):

    def test_old_database_gets_course_date_columns(self):
        """FR-25: create_tables() adds start_date and end_date to an old courses table."""
        connection = database.get_connection(TEST_DB_PATH)
        connection.executescript(OLD_SCHEMA)

        database.create_tables(connection)
        database.create_tables(connection)  # Running it twice must also work.

        course = database.get_course(connection, "PY101")
        self.assertEqual(course["course_name"], "Programming with Python")
        self.assertIsNone(course["start_date"])
        self.assertIsNone(course["end_date"])
        # The enrollment date columns are added too, from the same old database.
        self.assertIsNone(database.get_enrollment(connection, "001", "PY101"))
        database.add_student(connection, "001", "Nadia Hirwa")
        database.enroll_student(connection, "001", "PY101")
        self.assertEqual(len(database.get_expected_records(connection)), 1)
        connection.close()


class SeedTestCase(unittest.TestCase):
    """Base class: the seed data in an in-memory database. It has no tests itself."""

    def setUp(self):
        """Load the demo data."""
        self.connection = v2_data.reset_database(TEST_DB_PATH)
        v2_data.add_demo_data(self.connection)
        v2_data.add_demo_attendance(self.connection)

    def tearDown(self):
        """Close the database after each test."""
        self.connection.close()

    def validate(self, lines):
        """Read and validate a file made of the given lines; return (accepted, rejected)."""
        rows, error = importer.read_csv(make_file(lines))
        self.assertIsNone(error)
        accepted, duplicates, rejected = importer.validate_rows(self.connection, rows)
        return accepted, rejected


class TestSeed(SeedTestCase):

    def test_seed_course_dates(self):
        """FR-25: the seed sets PY101 and DS102 dates."""
        py101 = database.get_course(self.connection, "PY101")
        ds102 = database.get_course(self.connection, "DS102")

        self.assertEqual((py101["start_date"], py101["end_date"]), ("2026-09-07", "2026-12-18"))
        self.assertEqual((ds102["start_date"], ds102["end_date"]), ("2026-09-09", "2026-12-18"))

    def test_seed_totals_unchanged(self):
        """FR-25: course dates do not change who is expected: 63, 9, 4, 87.50%, 94.74%."""
        records = analytics.build_records_frame(database.get_expected_records(self.connection))
        totals = analytics.calculate_dashboard_metrics(records)

        self.assertEqual((totals["present"], totals["absent"], totals["unknown"]), (63, 9, 4))
        self.assertEqual(analytics.format_rate(totals["attendance_rate"]), "87.50%")
        self.assertEqual(analytics.format_rate(totals["completeness"]), "94.74%")


class TestImportPeriod(SeedTestCase):

    def test_row_after_course_end_is_rejected(self):
        """FR-25: a PY101 row on 2027-01-05, after the course ends, is rejected with a reason."""
        accepted, rejected = self.validate(["PY101,2027-01-05,001,Nadia Hirwa,P"])

        self.assertEqual(len(accepted), 0)
        self.assertEqual(
            rejected[0]["reason"],
            "Row 2: PY101 runs from 07/09/2026 to 18/12/2026, not on 05/01/2027.",
        )

    def test_row_before_course_start_is_rejected(self):
        """FR-25: a DS102 row on 2026-09-08, the day before the course starts, is rejected."""
        accepted, rejected = self.validate(["DS102,2026-09-08,004,Eric Niyonzima,P"])

        self.assertEqual(len(accepted), 0)
        self.assertIn("DS102 runs from 09/09/2026 to 18/12/2026", rejected[0]["reason"])

    def test_row_on_last_day_is_accepted(self):
        """FR-25: a PY101 tutorial row on 2026-12-18, the course's last day, is accepted."""
        accepted, rejected = self.validate(["PY101,2026-12-18,001,Nadia Hirwa,P,Tutorial"])

        self.assertEqual(len(accepted), 1)
        self.assertEqual(len(rejected), 0)


class TestChangeCourseDates(SeedTestCase):

    def test_change_refused_when_sessions_fall_outside(self):
        """FR-25: starting PY101 on 2026-09-10 leaves W1 outside (1 session);
        ending it on 2026-09-20 leaves W3 and W4 outside (2 sessions)."""
        later_start = database.count_sessions_outside_period(
            self.connection, "PY101", "2026-09-10", "2026-12-18"
        )
        earlier_end = database.count_sessions_outside_period(
            self.connection, "PY101", "2026-09-07", "2026-09-20"
        )

        self.assertEqual(later_start, 1)
        self.assertEqual(earlier_end, 2)

    def test_change_allowed_when_sessions_stay_inside(self):
        """FR-25: widening PY101 to 2026-09-01 .. 2027-01-31 keeps all 4 sessions inside."""
        outside = database.count_sessions_outside_period(
            self.connection, "PY101", "2026-09-01", "2027-01-31"
        )
        self.assertEqual(outside, 0)

        database.update_course_dates(self.connection, "PY101", "2026-09-01", "2027-01-31")

        course = database.get_course(self.connection, "PY101")
        self.assertEqual((course["start_date"], course["end_date"]), ("2026-09-01", "2027-01-31"))


class TestDefaultDateRange(SeedTestCase):

    def load_records(self):
        """Return the expected records of the test database as a frame."""
        return analytics.build_records_frame(database.get_expected_records(self.connection))

    def test_all_courses_uses_session_dates(self):
        """FR-12: for All courses, the range is the first to the last session date."""
        records = self.load_records()
        default = analytics.get_default_date_range(records, analytics.ALL_COURSES, None, None)

        self.assertEqual(default, ("2026-09-07", "2026-09-30"))

    def test_one_course_uses_its_period(self):
        """FR-25: for PY101, the range is the course period 2026-09-07 to 2026-12-18."""
        records = self.load_records()
        default = analytics.get_default_date_range(records, "PY101", "2026-09-07", "2026-12-18")

        self.assertEqual(default, ("2026-09-07", "2026-12-18"))

    def test_course_without_dates_uses_its_sessions(self):
        """FR-25: for a course with NULL dates, the range is its own sessions' dates."""
        records = self.load_records()
        default = analytics.get_default_date_range(records, "DS102", None, None)

        self.assertEqual(default, ("2026-09-09", "2026-09-30"))


if __name__ == "__main__":
    unittest.main()
