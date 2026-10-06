"""Tests for seeding the demo data when the app starts and for "Reset demo data".

Every test uses a temporary in-memory database, never attendance.db.
"""

import unittest

import analytics
import database
import seed_demo

TEST_DB_PATH = ":memory:"


class TestDemoSeed(unittest.TestCase):

    def setUp(self):
        """Create an empty database, as on a fresh online copy."""
        self.connection = database.get_connection(TEST_DB_PATH)
        database.create_tables(self.connection)

    def tearDown(self):
        """Close the database after each test."""
        self.connection.close()

    def assert_seed_totals(self):
        """Check the demo totals: 63, 9, 4, 87.50%, 94.74%, 12 students, 8 sessions."""
        records = analytics.build_records_frame(database.get_expected_records(self.connection))
        totals = analytics.calculate_dashboard_metrics(records)

        self.assertEqual((totals["present"], totals["absent"], totals["unknown"]), (63, 9, 4))
        self.assertEqual(analytics.format_rate(totals["attendance_rate"]), "87.50%")
        self.assertEqual(analytics.format_rate(totals["completeness"]), "94.74%")
        self.assertEqual(totals["students"], 12)
        self.assertEqual(totals["sessions"], 8)

    def test_empty_database_is_seeded(self):
        """An empty database gets the demo data with the expected totals."""
        seeded = seed_demo.seed_if_empty(self.connection)

        self.assertTrue(seeded)
        self.assert_seed_totals()

    def test_database_with_courses_is_not_seeded_again(self):
        """A database that already has courses is left alone."""
        seed_demo.seed_if_empty(self.connection)
        seeded_again = seed_demo.seed_if_empty(self.connection)

        self.assertFalse(seeded_again)
        self.assert_seed_totals()

    def test_reset_restores_the_demo_data(self):
        """After changes, 'Reset demo data' brings back exactly the demo totals."""
        seed_demo.seed_if_empty(self.connection)
        database.add_student(self.connection, "013", "Emile Uwase")
        database.delete_session(self.connection, "PY101-W1")

        seed_demo.reset_demo_data(self.connection)

        self.assertIsNone(database.get_student(self.connection, "013"))
        self.assert_seed_totals()


if __name__ == "__main__":
    unittest.main()
