"""Tests for the Version 3 demo data (seed_demo.py) and the demo CSV files.

Every test uses a temporary in-memory database, never attendance.db.
The numbers were worked out by hand from the lists in seed_demo.py:
block 07/09/2026 to 25/09/2026 (15 weekdays); DS102 loses 16/09 as a holiday;
tutorials PY101 10/09 and 19/09, DS102 11/09 and 24/09, MA103 23/09 (T1 and T2);
010 joins on 14/09 and 012 leaves after 18/09.
"""

import os
import unittest

import analytics
import database
import importer
import seed_demo

TEST_DB_PATH = ":memory:"
DEMO_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), "demo_data")


class SeedV3TestCase(unittest.TestCase):
    """Base class: the Version 3 demo data in an in-memory database. It has no tests itself."""

    def setUp(self):
        """Create an empty database and seed it, as on a fresh online copy."""
        self.connection = database.get_connection(TEST_DB_PATH)
        database.create_tables(self.connection)
        self.seeded = seed_demo.seed_if_empty(self.connection)

    def tearDown(self):
        """Close the database after each test."""
        self.connection.close()

    def records(self):
        """Return all expected records as a frame."""
        return analytics.build_records_frame(database.get_expected_records(self.connection))

    def student_course(self, student_id, course_code):
        """Return the records of one student in one course."""
        frame = analytics.filter_student(self.records(), student_id)
        return frame[frame["course_code"] == course_code]

    def read_demo_file(self, name):
        """Read and validate a demo CSV file; return (accepted, duplicates, rejected)."""
        with open(os.path.join(DEMO_FOLDER, name), "rb") as demo_file:
            rows, error = importer.read_csv(demo_file.read())
        self.assertIsNone(error)
        return importer.validate_rows(self.connection, rows)


class TestSeedTotals(SeedV3TestCase):

    def test_empty_database_is_seeded(self):
        """Section 12: the totals, worked out by hand.

        Expected: PY101 10 students x 17 sessions + 010 (11) + 012 (11) = 192;
        DS102 8 x 16 + 010 (10) + 012 (10) = 148; MA103 9 x 17 + 010 (12) = 165; total 505.
        Not Present: 10 Late, 4 Excused, 10 Absent and 4 Unknown, so 477 Present.
        Rate (477 + 10) / (477 + 10 + 10) = 487 / 497 = 97.99%;
        completeness 501 / 505 = 99.21%.
        """
        self.assertTrue(self.seeded)
        totals = analytics.calculate_dashboard_metrics(self.records())

        self.assertEqual(totals["expected"], 505)
        self.assertEqual(
            (totals["present"], totals["late"], totals["excused"],
             totals["absent"], totals["unknown"]),
            (477, 10, 4, 10, 4),
        )
        self.assertEqual(analytics.format_rate(totals["attendance_rate"]), "97.99%")
        self.assertEqual(analytics.format_rate(totals["completeness"]), "99.21%")
        self.assertEqual(totals["students"], 12)
        self.assertEqual(totals["sessions"], 50)

    def test_class_days_holiday_and_tutorials(self):
        """BR-20, BR-21: 15 class days per course (DS102 14: holiday 16/09), 2 tutorials each."""
        expected_counts = {"PY101": (15, 2), "DS102": (14, 2), "MA103": (15, 2)}

        for course_code in expected_counts:
            class_days = 0
            tutorials = 0
            for session in database.get_sessions_for_course(self.connection, course_code):
                if session["session_type"] == "Class":
                    class_days += 1
                else:
                    tutorials += 1
            self.assertEqual((class_days, tutorials), expected_counts[course_code], course_code)

        self.assertIsNone(database.get_class_session(self.connection, "DS102", "2026-09-16"))
        self.assertIsNotNone(database.get_session(self.connection, "MA103-2026-09-23-T2"))

    def test_database_with_courses_is_not_seeded_again(self):
        """A database that already has courses is left alone."""
        seeded_again = seed_demo.seed_if_empty(self.connection)

        self.assertFalse(seeded_again)
        self.assertEqual(analytics.calculate_dashboard_metrics(self.records())["expected"], 505)

    def test_reset_restores_the_demo_data(self):
        """After changes, 'Reset demo data' brings back exactly the demo totals."""
        database.add_student(self.connection, "013", "Emile Uwase")
        database.delete_session(self.connection, "PY101-2026-09-07")

        seed_demo.reset_demo_data(self.connection)

        self.assertIsNone(database.get_student(self.connection, "013"))
        totals = analytics.calculate_dashboard_metrics(self.records())
        self.assertEqual((totals["expected"], totals["present"]), (505, 477))


class TestTwoStudentsByHand(SeedV3TestCase):

    def test_student_002_in_py101(self):
        """Section 12, by hand: 002 in PY101 has 17 sessions (15 class days, 2 tutorials).

        Absent 08/09, 15/09, 21/09, 22/09, 23/09 (5); Late 09/09, 17/09 (2); the other 10 Present.
        Rate (10 + 2) / (10 + 2 + 5) = 12 / 17 = 70.59%. Deducted 2 x 1 + 5 x 2 = 12.
        Longest streak 3 (21-23/09); current streak 0 (25/09 is Present).
        """
        records = self.student_course("002", "PY101")
        rates = analytics.summarize_frame(records)

        self.assertEqual(len(records), 17)
        self.assertEqual(
            (rates["present"], rates["late"], rates["excused"],
             rates["absent"], rates["unknown"]),
            (10, 2, 0, 5, 0),
        )
        self.assertEqual(analytics.format_rate(rates["attendance_rate"]), "70.59%")
        self.assertEqual(analytics.calculate_deduction(rates["late"], rates["absent"], 1, 2), 12)
        statuses = analytics.statuses_in_session_order(records)
        self.assertEqual(analytics.calculate_streaks(statuses), (3, 0))

    def test_late_joiner_010(self):
        """Section 12, by hand: 010 joins on 14/09, so is expected only from week 2.

        PY101: 10 class days + tutorial 19/09 = 11. DS102: 10 weekdays minus the holiday
        16/09 = 9 class days + tutorial 24/09 = 10. MA103: 10 class days + 2 tutorials on
        23/09 = 12. Only one record is not Present: Absent in DS102 on 14/09.
        Total 33: 32 Present, 1 Absent, rate 32 / 33 = 96.97%, DS102 deducted 2.
        """
        expected = {"PY101": 11, "DS102": 10, "MA103": 12}
        for course_code in expected:
            self.assertEqual(
                len(self.student_course("010", course_code)), expected[course_code], course_code
            )

        rates = analytics.summarize_frame(analytics.filter_student(self.records(), "010"))
        self.assertEqual((rates["present"], rates["absent"], rates["unknown"]), (32, 1, 0))
        self.assertEqual(analytics.format_rate(rates["attendance_rate"]), "96.97%")

        deductions = analytics.build_deductions_table(self.records(), 1, 2)
        row = deductions[(deductions["student_id"] == "010")
                         & (deductions["course_code"] == "DS102")].iloc[0]
        self.assertEqual(row[analytics.DEDUCTED_COLUMN], 2)

    def test_absence_alert_at_default(self):
        """FR-21: at the default of 2, only 009 in PY101 is listed (absent on 24/09 and 25/09)."""
        alerts = analytics.find_streak_alerts(
            analytics.build_streak_table(self.records()), analytics.DEFAULT_STREAK_ALERT
        )

        self.assertEqual(list(alerts["Student ID"]), ["009"])
        self.assertEqual(list(alerts["Course"]), ["PY101"])


class TestManageOnSeed(SeedV3TestCase):

    def test_delete_course_counts_ma103(self):
        """FR-23 (Version 3 rule), by hand: MA103 has 15 class days, 2 tutorials and
        10 enrollments; its 165 expected records minus 1 Unknown (007 on 25/09) = 164."""
        preview = database.count_delete_course(self.connection, "MA103")
        counts = database.delete_course(self.connection, "MA103")

        expected = {"class_days": 15, "tutorials": 2, "enrollments": 10, "attendance": 164,
                    "courses": 1}
        self.assertEqual(preview, expected)
        self.assertEqual(counts, expected)
        # 505 expected - 165 for MA103 = 340 left.
        self.assertEqual(analytics.calculate_dashboard_metrics(self.records())["expected"], 340)

    def test_remove_holiday_preview(self):
        """Section 11: removing PY101's class on 16/09 deletes 11 records (12 students
        enrolled, 003 has no record that day)."""
        counts = database.count_delete_session(self.connection, "PY101-2026-09-16")

        self.assertEqual(counts["attendance"], 11)

    def test_student_profile_of_002(self):
        """Section 6.1, by hand: 002's profile shows PY101 with 70.59% and 12 marks deducted,
        and DS102 and MA103 with 100.00% and 0 deducted."""
        records = analytics.filter_student(self.records(), "002")
        profile = analytics.format_summary_table(analytics.build_student_profile(records, 1, 2))

        py101 = profile[profile["Course"] == "PY101"].iloc[0]
        self.assertEqual(py101["Attendance rate"], "70.59%")
        self.assertEqual(py101[analytics.DEDUCTED_COLUMN], 12)
        self.assertEqual(py101[analytics.ENROLLED_FROM_COLUMN], "start")
        for course_code in ["DS102", "MA103"]:
            row = profile[profile["Course"] == course_code].iloc[0]
            self.assertEqual(row["Attendance rate"], "100.00%")
            self.assertEqual(row[analytics.DEDUCTED_COLUMN], 0)


class TestDemoFiles(SeedV3TestCase):

    def review_messy_file(self, accept_all):
        """Review messy_import.csv, with no suggestions or all of them accepted (FR-31)."""
        with open(os.path.join(DEMO_FOLDER, "messy_import.csv"), "rb") as demo_file:
            rows, error = importer.read_csv(demo_file.read())
        self.assertIsNone(error)
        result = importer.review_rows(self.connection, rows)
        if accept_all:
            keys = []
            for suggestion in result["suggestions"]:
                keys.append(suggestion["key"])
            result = importer.review_rows(self.connection, rows, keys)
        return result

    def count_result(self, result):
        """Return (accepted, duplicates, rejected) counts."""
        return len(result["accepted"]), len(result["duplicates"]), len(result["rejected"])

    def test_messy_file_counts(self):
        """FR-31: messy_import.csv gives 31 auto-fixes, 5 suggestions, 6 / 2 / 11."""
        result = self.review_messy_file(accept_all=False)

        self.assertEqual(len(result["fixes"]), 31)
        kinds = []
        for suggestion in result["suggestions"]:
            kinds.append(suggestion["kind"])
        self.assertEqual(kinds, ["S1", "S2", "S2", "S3", "S4"])
        self.assertEqual(self.count_result(result), (6, 2, 11))

        reasons = ""
        for row in result["rejected"]:
            reasons = reasons + row["reason"] + "\n"
        self.assertIn('Row 6: Invalid student ID. Expected exactly 3 digits from 001 to 999. '
                      'Got "0".', reasons)
        self.assertIn('Got "maybe"', reasons)
        self.assertIn('Row 8: Unknown course "BIO200".', reasons)
        self.assertIn("Row 9: PY101 has no class on Saturday 12/09/2026.", reasons)
        self.assertIn("Row 10: DS102 has no class on Wednesday 16/09/2026.", reasons)
        self.assertIn("Row 11: PY101 runs from 07/09/2026 to 25/09/2026, not on 02/10/2026.",
                      reasons)
        self.assertIn('Suggestion: "Use saved name Eric Niyonzima"', reasons)
        self.assertIn('Suggestion: "Assign next free ID 013 as a new student"', reasons)
        self.assertIn('Suggestion: "Assign next free ID 015 as a new student"', reasons)
        self.assertIn('Suggestion: "Use file: Present"', reasons)

    def test_messy_file_counts_after_accepting_all(self):
        """FR-31: with every suggestion accepted, 11 accepted / 2 duplicates / 6 rejected."""
        result = self.review_messy_file(accept_all=True)

        self.assertEqual(importer.count_accepted_suggestions(result["suggestions"]), 5)
        self.assertEqual(self.count_result(result), (11, 2, 6))
        new_ids = {}
        for row in result["accepted"]:
            new_ids[row["row"]] = (row["student_id"], row["full_name"])
        self.assertEqual(new_ids[12], ("004", "Eric Niyonzima"))
        self.assertEqual(new_ids[13], ("013", "Fabrice Gasana"))
        self.assertEqual(new_ids[14], ("013", "Fabrice Gasana"))
        self.assertEqual(new_ids[16], ("015", "Alice Kayitesi"))

    def test_messy_file_shares_one_new_tutorial(self):
        """IR-13: rows 12 and 20 share the new MA103 Saturday tutorial MA103-2026-09-19-T1."""
        result = self.review_messy_file(accept_all=True)

        tutorial_ids = []
        for row in result["accepted"]:
            if row["type"] == "Tutorial" and row["course_code"] == "MA103":
                tutorial_ids.append(row["session_id"])
        self.assertEqual(tutorial_ids, ["MA103-2026-09-19-T1", "MA103-2026-09-19-T1"])

    def test_messy_file_totals_before_suggestions(self):
        """FR-31: Confirm with no suggestions accepted; totals by hand.

        Fills 003 PY101 16/09 (P), 008 DS102 24/09 T1 (L), 007 MA103 25/09 (E) and
        011 PY101 19/09 T1 (E). New 014 in MA103 from 21/09: 7 expected, 1 Present.
        New MA103 tutorial 19/09: 10 expected, 005 Absent.
        Present 479, Late 11, Excused 6, Absent 11, Unknown 4 - 4 + 6 + 9 = 15;
        expected 505 + 7 + 10 = 522. Rate 490 / 501 = 97.80%; completeness 507 / 522 = 97.13%.
        """
        result = self.review_messy_file(accept_all=False)
        importer.apply_import(self.connection, result["accepted"], "messy_import.csv")

        self.assert_totals((479, 11, 6, 11, 15), 522, "97.80%", "97.13%")

    def test_messy_file_totals_after_all_suggestions(self):
        """FR-31: Confirm with every suggestion accepted; totals by hand.

        Adds 004's MA103 tutorial (P), new 013 in PY101 from 21/09 (5 expected: A, P),
        new 015 in MA103 from 22/09 (6 expected: P), and 002's 08/09 Absent becomes Present.
        Present 483, Late 11, Excused 6, Absent 11, Unknown 15 - 1 + 3 + 5 = 22;
        expected 522 + 5 + 6 = 533. Rate 494 / 505 = 97.82%; completeness 511 / 533 = 95.87%.
        """
        result = self.review_messy_file(accept_all=True)
        importer.apply_import(self.connection, result["accepted"], "messy_import.csv")

        self.assert_totals((483, 11, 6, 11, 22), 533, "97.82%", "95.87%")
        row = self.connection.execute(
            "SELECT status, source FROM attendance WHERE student_id = ? AND session_id = ?",
            ("002", "PY101-2026-09-08"),
        ).fetchone()
        self.assertEqual((row["status"], row["source"]), ("Present", "messy_import.csv"))

    def assert_totals(self, counts, expected, rate, completeness):
        """Check the dashboard totals after an import."""
        totals = analytics.calculate_dashboard_metrics(self.records())
        self.assertEqual(
            (totals["present"], totals["late"], totals["excused"],
             totals["absent"], totals["unknown"]),
            counts,
        )
        self.assertEqual(totals["expected"], expected)
        self.assertEqual(analytics.format_rate(totals["attendance_rate"]), rate)
        self.assertEqual(analytics.format_rate(totals["completeness"]), completeness)

    def test_clean_file_totals(self):
        """FR-10: clean_import.csv gives 7 accepted; totals after Confirm, by hand.

        It fills 011's PY101 tutorial on 19/09 (Present) and 007's MA103 class on 25/09
        (Excused), and adds 013 in PY101 from 21/09 (5 class days: 4 Present, 1 Late).
        Present 477 + 1 + 4 = 482; Late 11; Excused 5; Absent 10; Unknown 4 - 2 = 2;
        expected 505 + 5 = 510. Rate 493 / 503 = 98.01%; completeness 508 / 510 = 99.61%.
        """
        accepted, duplicates, rejected = self.read_demo_file("clean_import.csv")
        self.assertEqual((len(accepted), len(duplicates), len(rejected)), (7, 0, 0))

        importer.apply_import(self.connection, accepted, "clean_import.csv")
        totals = analytics.calculate_dashboard_metrics(self.records())

        self.assertEqual(
            (totals["present"], totals["late"], totals["excused"],
             totals["absent"], totals["unknown"]),
            (482, 11, 5, 10, 2),
        )
        self.assertEqual(totals["expected"], 510)
        self.assertEqual(analytics.format_rate(totals["attendance_rate"]), "98.01%")
        self.assertEqual(analytics.format_rate(totals["completeness"]), "99.61%")


if __name__ == "__main__":
    unittest.main()
