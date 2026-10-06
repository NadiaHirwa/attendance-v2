"""Tests for BR-17: an enrollment period must be inside its course period.

Every test uses a temporary in-memory database, never attendance.db.
Seed course dates: PY101 2026-09-07 to 2026-12-18.
"""

import unittest

import database
import seed_demo
import validation

TEST_DB_PATH = ":memory:"
PY101_START = "2026-09-07"
PY101_END = "2026-12-18"


class TestPeriodRule(unittest.TestCase):
    """BR-17 as a pure function, with the PY101 period."""

    def test_inside_course_period(self):
        """BR-17: 2026-09-14 to 2026-11-30 is inside 2026-09-07 to 2026-12-18."""
        self.assertTrue(validation.is_enrollment_in_course_period(
            "2026-09-14", "2026-11-30", PY101_START, PY101_END
        ))

    def test_same_as_course_period(self):
        """BR-17: exactly the course period is allowed (both ends included)."""
        self.assertTrue(validation.is_enrollment_in_course_period(
            PY101_START, PY101_END, PY101_START, PY101_END
        ))

    def test_start_before_course_start(self):
        """BR-17: starting on 2026-09-06, the day before the course, is refused."""
        self.assertFalse(validation.is_enrollment_in_course_period(
            "2026-09-06", None, PY101_START, PY101_END
        ))

    def test_end_after_course_end(self):
        """BR-17: ending on 2026-12-19, the day after the course, is refused."""
        self.assertFalse(validation.is_enrollment_in_course_period(
            None, "2026-12-19", PY101_START, PY101_END
        ))

    def test_start_after_course_end(self):
        """BR-17: a start after the course has ended is refused."""
        self.assertFalse(validation.is_enrollment_in_course_period(
            "2027-01-05", None, PY101_START, PY101_END
        ))

    def test_start_after_end(self):
        """BR-17: the start must be on or before the end."""
        self.assertFalse(validation.is_enrollment_in_course_period(
            "2026-11-30", "2026-09-14", PY101_START, PY101_END
        ))

    def test_course_without_dates_has_no_limit(self):
        """BR-17: a course with no dates allows any enrollment dates (start <= end)."""
        self.assertTrue(validation.is_enrollment_in_course_period(
            "1990-01-01", "2099-12-31", None, None
        ))


class TestSimplify(unittest.TestCase):
    """BR-17 storage: a date equal to the course's is stored as None."""

    def test_full_course_period_becomes_none(self):
        """BR-17: the course start and end are both stored as None."""
        self.assertEqual(
            validation.simplify_enrollment_dates(PY101_START, PY101_END, PY101_START, PY101_END),
            (None, None),
        )

    def test_other_dates_are_kept(self):
        """BR-17: a late start and an early end are stored as they are."""
        self.assertEqual(
            validation.simplify_enrollment_dates(
                "2026-09-21", "2026-11-30", PY101_START, PY101_END
            ),
            ("2026-09-21", "2026-11-30"),
        )


class SeedTestCase(unittest.TestCase):
    """Base class: the seed data and a new student 013. It has no tests itself."""

    def setUp(self):
        """Load the demo data and add student 013, who has no course yet."""
        self.connection = seed_demo.reset_database(TEST_DB_PATH)
        seed_demo.add_demo_data(self.connection)
        seed_demo.add_demo_attendance(self.connection)
        database.add_student(self.connection, "013", "Emile Uwase")

    def tearDown(self):
        """Close the database after each test."""
        self.connection.close()


class TestEnrollInDatabase(SeedTestCase):

    def test_new_student_has_no_course(self):
        """FR-04: a new student starts with no course."""
        self.assertEqual(database.get_student_courses(self.connection, "013"), [])

    def test_enroll_outside_period_is_refused(self):
        """BR-17: the database refuses an enrollment that ends after the course."""
        with self.assertRaises(ValueError):
            database.enroll_student(self.connection, "013", "PY101", PY101_START, "2027-01-31")
        self.assertFalse(database.is_enrolled(self.connection, "013", "PY101"))

    def test_enroll_start_after_end_is_refused(self):
        """BR-17: the database refuses a start after the end."""
        with self.assertRaises(ValueError):
            database.enroll_student(self.connection, "013", "PY101", "2026-11-30", "2026-09-14")

    def test_full_period_is_stored_as_null(self):
        """BR-17: enrolling for the full course period stores NULL for both dates."""
        database.enroll_student(self.connection, "013", "PY101", PY101_START, PY101_END)

        enrollment = database.get_enrollment(self.connection, "013", "PY101")
        self.assertIsNone(enrollment["start_date"])
        self.assertIsNone(enrollment["end_date"])

    def test_null_dates_follow_the_course(self):
        """BR-17: after the course is extended, a NULL end follows the new course end."""
        database.enroll_student(self.connection, "013", "PY101", "2026-09-21", PY101_END)
        database.update_course_dates(self.connection, "PY101", PY101_START, "2027-01-31")
        database.add_session(self.connection, "PY101-W20", "PY101", "2027-01-25")

        enrollment = database.get_enrollment(self.connection, "013", "PY101")
        self.assertEqual(enrollment["start_date"], "2026-09-21")
        self.assertIsNone(enrollment["end_date"])
        # 013 is expected at the new session in January, because the end follows the course.
        result = database.record_attendance(self.connection, "013", "PY101-W20", "Present")
        self.assertEqual(result, "inserted")

    def test_update_outside_period_is_refused(self):
        """BR-17: changing enrollment dates to start before the course is refused."""
        database.enroll_student(self.connection, "013", "PY101")

        with self.assertRaises(ValueError):
            database.update_enrollment_dates(self.connection, "013", "PY101", "2026-09-01", None)
        self.assertIsNone(database.get_enrollment(self.connection, "013", "PY101")["start_date"])


class TestChangeCourseDatesKeepsEnrollmentsInside(SeedTestCase):

    def test_course_cannot_shrink_past_an_enrollment(self):
        """BR-17: 013 is enrolled until 2026-11-30, so PY101 cannot end on 2026-11-01."""
        database.enroll_student(self.connection, "013", "PY101", "2026-09-21", "2026-11-30")

        outside = database.count_enrollments_outside_period(
            self.connection, "PY101", PY101_START, "2026-11-01"
        )
        self.assertEqual(outside, 1)

    def test_null_enrollment_dates_never_block(self):
        """BR-17: the seed enrollments have NULL dates, so they never block a course change."""
        outside = database.count_enrollments_outside_period(
            self.connection, "PY101", PY101_START, "2026-10-31"
        )
        self.assertEqual(outside, 0)


if __name__ == "__main__":
    unittest.main()
