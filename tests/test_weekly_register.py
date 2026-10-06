"""Tests for the weekly view (FR-27), the class register (FR-28) and the filter (FR-30).

Every test uses a temporary in-memory database, never attendance.db.
Worked out by hand from seed_demo.py: block 07/09/2026 (Monday) to 25/09/2026;
week 1 starts 07/09, week 2 14/09, week 3 21/09. PY101 tutorials 10/09 (Thu) and
19/09 (Sat); DS102 holiday Wed 16/09; MA103 tutorials T1 and T2 on Wed 23/09.
010 joins on 14/09; 012 leaves after 18/09.
"""

import unittest

import analytics
import database
import seed_demo

TEST_DB_PATH = ":memory:"


class SeedTestCase(unittest.TestCase):
    """Base class: the Version 3 seed in an in-memory database. It has no tests itself."""

    def setUp(self):
        """Create the seed data."""
        self.connection = database.get_connection(TEST_DB_PATH)
        database.create_tables(self.connection)
        seed_demo.create_demo_data(self.connection)
        self.records = analytics.build_records_frame(
            database.get_expected_records(self.connection)
        )

    def tearDown(self):
        """Close the database after each test."""
        self.connection.close()

    def student_records(self, student_id, course_code):
        """Return one student's records in one course."""
        records = analytics.filter_student(self.records, student_id)
        return records[records["course_code"] == course_code]

    def weekly(self, student_id, course_code, symbols=analytics.WEEKLY_WORDS):
        """Return the weekly grid of a student in a course."""
        course = database.get_course(self.connection, course_code)
        sessions = database.get_sessions_for_course(self.connection, course_code)
        return analytics.build_weekly_view(
            sessions, self.student_records(student_id, course_code),
            course["start_date"], course["end_date"], symbols,
        )

    def register(self, course_code, week=None, late=1, absent=2):
        """Return the class register of a course."""
        sessions = database.get_sessions_for_course(self.connection, course_code)
        records = self.records[self.records["course_code"] == course_code]
        return analytics.build_class_register(sessions, records, late, absent, week)

    def week_row(self, grid, number):
        """Return one week of a weekly grid as a dict."""
        return grid.iloc[number - 1].to_dict()

    def register_row(self, register, student_id):
        """Return one student's row of a register as a dict."""
        return register[register["Student ID"] == student_id].iloc[0].to_dict()


class TestWeeklyView(SeedTestCase):

    def test_002_in_py101(self):
        """FR-27, by hand: 002 is Absent on Tue 08/09, Tue 15/09, Mon 21, Tue 22 and
        Wed 23/09, and Late on Wed 09/09 and Thu 17/09; both tutorials Present.
        Totals: 10 Present, 2 Late, 5 Absent: 12 / 17 = 70.59%, deducted 12."""
        grid = self.weekly("002", "PY101")

        self.assertEqual(list(grid["Week"]),
                         ["Week 1 (07/09)", "Week 2 (14/09)", "Week 3 (21/09)"])
        self.assertEqual(self.week_row(grid, 1), {
            "Week": "Week 1 (07/09)", "Mon": "Present", "Tue": "Absent", "Wed": "Late",
            "Thu": "Present", "Fri": "Present", "Tutorials": "10/09 Present",
        })
        self.assertEqual(self.week_row(grid, 2), {
            "Week": "Week 2 (14/09)", "Mon": "Present", "Tue": "Absent", "Wed": "Present",
            "Thu": "Late", "Fri": "Present", "Tutorials": "19/09 Present",
        })
        self.assertEqual(self.week_row(grid, 3), {
            "Week": "Week 3 (21/09)", "Mon": "Absent", "Tue": "Absent", "Wed": "Absent",
            "Thu": "Present", "Fri": "Present", "Tutorials": "",
        })

        rates = analytics.summarize_frame(self.student_records("002", "PY101"))
        self.assertEqual(analytics.format_rate(rates["attendance_rate"]), "70.59%")
        self.assertEqual(analytics.calculate_deduction(rates["late"], rates["absent"], 1, 2), 12)

    def test_symbols_on_screen(self):
        """FR-27: on screen, 002's week 1 shows ❌ on Tuesday and 🕐 on Wednesday."""
        grid = self.weekly("002", "PY101", analytics.WEEKLY_SYMBOLS)
        week_1 = self.week_row(grid, 1)

        self.assertEqual((week_1["Mon"], week_1["Tue"], week_1["Wed"]), ("✅", "❌", "🕐"))
        self.assertEqual(week_1["Tutorials"], "10/09 ✅")

    def test_late_joiner_010(self):
        """FR-27: 010 joins on 14/09, so week 1 is all "—", including the 10/09 tutorial."""
        grid = self.weekly("010", "PY101", analytics.WEEKLY_SYMBOLS)
        week_1 = self.week_row(grid, 1)

        for weekday in analytics.WEEKDAY_COLUMNS:
            self.assertEqual(week_1[weekday], "—", weekday)
        self.assertEqual(week_1["Tutorials"], "10/09 —")
        self.assertEqual(self.week_row(grid, 2)["Mon"], "✅")

    def test_ds102_holiday(self):
        """FR-27: DS102 has no class on Wed 16/09, so week 2 Wednesday is "—"."""
        grid = self.weekly("001", "DS102", analytics.WEEKLY_SYMBOLS)

        self.assertEqual(self.week_row(grid, 2)["Wed"], "—")
        self.assertEqual(self.week_row(grid, 2)["Tue"], "✅")

    def test_two_tutorials_on_one_day(self):
        """FR-27: MA103 has T1 and T2 on 23/09; both appear in week 3 (005 was Excused)."""
        grid = self.weekly("005", "MA103")

        self.assertEqual(self.week_row(grid, 3)["Tutorials"],
                         "23/09 Excused, 23/09 (T2) Excused")

    def test_early_leaver_012(self):
        """FR-27: 012 leaves after 18/09, so week 3 and the Saturday 19/09 tutorial are "—"."""
        grid = self.weekly("012", "PY101", analytics.WEEKLY_SYMBOLS)
        week_3 = self.week_row(grid, 3)

        for weekday in analytics.WEEKDAY_COLUMNS:
            self.assertEqual(week_3[weekday], "—", weekday)
        self.assertEqual(self.week_row(grid, 2)["Tutorials"], "19/09 —")
        self.assertEqual(self.week_row(grid, 2)["Fri"], "🕐")

    def test_missing_record(self):
        """FR-27: 003 has no record on Wed 16/09 in PY101: ❔ (not recorded)."""
        grid = self.weekly("003", "PY101", analytics.WEEKLY_SYMBOLS)

        self.assertEqual(self.week_row(grid, 2)["Wed"], "❔")


class TestClassRegister(SeedTestCase):

    def test_columns_in_date_order(self):
        """FR-28: PY101 has 15 class days and 2 tutorials, labelled 'Mon 07/09' and
        'Tut 10/09', in date order, then the totals."""
        register = self.register("PY101")
        columns = list(register.columns)

        self.assertEqual(columns[:7], ["Student ID", "Full name", "Mon 07/09", "Tue 08/09",
                                       "Wed 09/09", "Thu 10/09", "Tut 10/09"])
        self.assertIn("Tut 19/09", columns)
        self.assertEqual(columns[-7:], ["Present", "Late", "Excused", "Absent", "Unknown",
                                        "Rate", "Deducted"])
        self.assertEqual(len(columns), 2 + 17 + 7)
        self.assertEqual(list(register["Student ID"]), sorted(register["Student ID"]))

    def test_002_row_matches_stage_3(self):
        """FR-28: 002's PY101 row: A on 08/09, L on 09/09; 10 / 2 / 0 / 5 / 0, 70.59%, 12."""
        row = self.register_row(self.register("PY101"), "002")

        self.assertEqual((row["Tue 08/09"], row["Wed 09/09"], row["Tut 10/09"]), ("A", "L", "P"))
        self.assertEqual((row["Present"], row["Late"], row["Excused"], row["Absent"],
                          row["Unknown"]), (10, 2, 0, 5, 0))
        self.assertEqual((row["Rate"], row["Deducted"]), ("70.59%", 12))

    def test_every_deduction_matches_stage_3(self):
        """FR-28, FR-29: for every student and course, the register's Deducted equals the
        Stage 3 deductions table, also with other settings (Late 2 / Absent 3)."""
        for late, absent in [(1, 2), (2, 3)]:
            deductions = analytics.build_deductions_table(self.records, late, absent)
            for course_code in ["PY101", "DS102", "MA103"]:
                register = self.register(course_code, late=late, absent=absent)
                for index, row in register.iterrows():
                    expected = deductions[(deductions["student_id"] == row["Student ID"])
                                          & (deductions["course_code"] == course_code)]
                    self.assertEqual(row["Deducted"],
                                     expected[analytics.DEDUCTED_COLUMN].iloc[0])

    def test_late_joiner_010(self):
        """FR-28: 010's week-1 cells in PY101 are "—"; Mon 14/09 is P; 11 sessions counted."""
        row = self.register_row(self.register("PY101"), "010")

        for label in ["Mon 07/09", "Tue 08/09", "Wed 09/09", "Thu 10/09", "Tut 10/09",
                      "Fri 11/09"]:
            self.assertEqual(row[label], "—", label)
        self.assertEqual(row["Mon 14/09"], "P")
        self.assertEqual(row["Present"], 11)

    def test_ds102_holiday_has_no_column(self):
        """FR-28: DS102 has no Wed 16/09 column, so nobody can be marked on the holiday."""
        columns = list(self.register("DS102").columns)

        self.assertIn("Tue 15/09", columns)
        self.assertNotIn("Wed 16/09", columns)

    def test_two_tutorials_on_one_day(self):
        """FR-28: MA103 shows 'Tut 23/09' and 'Tut 23/09 (T2)'; 005 is E in both."""
        row = self.register_row(self.register("MA103"), "005")

        self.assertEqual((row["Tut 23/09"], row["Tut 23/09 (T2)"]), ("E", "E"))

    def test_early_leaver_012(self):
        """FR-28: 012's PY101 cells after 18/09 are "—"; Late on Fri 18/09."""
        row = self.register_row(self.register("PY101"), "012")

        self.assertEqual((row["Fri 18/09"], row["Tut 19/09"], row["Mon 21/09"]), ("L", "—", "—"))

    def test_week_filter(self):
        """FR-28: PY101 week 3 only has 21/09 to 25/09; 002 has 3 Absent there: 6 deducted."""
        register = self.register("PY101", week=3)
        row = self.register_row(register, "002")

        self.assertEqual(list(register.columns)[2:7],
                         ["Mon 21/09", "Tue 22/09", "Wed 23/09", "Thu 24/09", "Fri 25/09"])
        self.assertEqual((row["Absent"], row["Deducted"], row["Rate"]), (3, 6, "40.00%"))

    def test_csv_equals_table(self):
        """FR-28, FR-17: the download is made from the table itself, with no date column to
        change, so the CSV has exactly the rows and columns on screen."""
        register = self.register("PY101")
        shown = analytics.format_date_columns(register)

        self.assertTrue(shown.equals(register))
        csv_lines = shown.to_csv(index=False).strip().split("\n")
        self.assertEqual(len(csv_lines), len(register) + 1)
        self.assertEqual(csv_lines[0].split(",")[:3], ["Student ID", "Full name", "Mon 07/09"])


class TestBlockCourseFilter(SeedTestCase):

    def setUp(self):
        """Add a second block with one course, so the filter has a choice."""
        super().setUp()
        database.add_block(self.connection, "B2-2627", "Block 2, 2026-27", "2026-09-28")
        database.create_course(self.connection, "ML201", "Machine Learning", "B2-2627")

    def test_block_limits_the_course_list(self):
        """FR-30: block B1-2627 lists PY101, DS102, MA103 but not ML201 (block B2-2627)."""
        b1_codes = []
        for course in database.get_block_courses(self.connection, "B1-2627"):
            b1_codes.append(course["course_code"])

        self.assertEqual(b1_codes, ["DS102", "MA103", "PY101"])
        self.assertNotIn("ML201", b1_codes)

    def test_course_sets_the_date_range(self):
        """FR-30: a course's period wins; a block's period is next; else all session dates."""
        block_period = ("2026-09-28", "2026-10-16")

        course_period = ("2026-10-05", "2026-10-16")
        self.assertEqual(
            analytics.choose_filter_period(self.records, block_period, course_period),
            course_period,
        )
        self.assertEqual(analytics.choose_filter_period(self.records, block_period, None),
                         block_period)
        self.assertEqual(analytics.choose_filter_period(self.records, None, None),
                         ("2026-09-07", "2026-09-25"))

    def test_block_with_all_courses(self):
        """FR-30: block B1 with "All courses" keeps only B1's courses (all 505 records)."""
        filtered = analytics.filter_records_by_courses(
            self.records, ["DS102", "MA103", "PY101"], "2026-09-07", "2026-09-25"
        )
        self.assertEqual(len(filtered), 505)

        only_py101 = analytics.filter_records_by_courses(
            self.records, ["PY101"], "2026-09-07", "2026-09-25"
        )
        self.assertEqual(len(only_py101), 192)


if __name__ == "__main__":
    unittest.main()
