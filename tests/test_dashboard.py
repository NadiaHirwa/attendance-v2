"""Tests for the Stage 7 Dashboard: chart levels, KPI cards, weeks, and no session IDs.

Every test uses the Version 3 demo data in a temporary in-memory database, never
attendance.db (the screen test runs the app in a temporary folder).
"""

import os
import re
import tempfile
import unittest

import analytics
import database
import seed_demo

TEST_DB_PATH = ":memory:"
APP_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")
# A generated session ID, like 'PY101-2026-08-31' or 'MA103-2026-09-16-T2'.
SESSION_ID_PATTERN = re.compile(r"[A-Z]{2,}\d*-\d{4}-\d{2}-\d{2}")


class SeedTestCase(unittest.TestCase):
    """Base class: the Version 3 demo data (block B1-2627, PY101, DS102, MA103)."""

    def setUp(self):
        """Create an empty database and seed it."""
        self.connection = database.get_connection(TEST_DB_PATH)
        database.create_tables(self.connection)
        seed_demo.seed_if_empty(self.connection)
        self.records = analytics.build_records_frame(
            database.get_expected_records(self.connection)
        )

    def tearDown(self):
        """Close the database after each test."""
        self.connection.close()

    def course(self, course_code):
        """Return the records of one course."""
        return self.records[self.records["course_code"] == course_code]

    def rates_by_label(self, summary):
        """Return {label: attendance rate} of a level summary."""
        rates = {}
        for index, row in summary.iterrows():
            rates[row[analytics.CHART_LABEL_COLUMN]] = row["attendance_rate"]
        return rates


class TestChartLevel(unittest.TestCase):

    def test_several_blocks_all_blocks_is_by_block(self):
        """All blocks with several blocks: one bar per block."""
        self.assertEqual(
            analytics.choose_chart_level(analytics.ALL_BLOCKS, analytics.ALL_COURSES, 2),
            analytics.LEVEL_BLOCK,
        )

    def test_only_one_block_is_by_course(self):
        """All blocks with only one block (or none): one bar per course."""
        for block_count in (0, 1):
            self.assertEqual(
                analytics.choose_chart_level(
                    analytics.ALL_BLOCKS, analytics.ALL_COURSES, block_count
                ),
                analytics.LEVEL_COURSE,
            )

    def test_chosen_block_is_by_course(self):
        """One block chosen (or "No block"), even with several blocks: one bar per course."""
        for block_choice in ("B1-2627", None):
            self.assertEqual(
                analytics.choose_chart_level(block_choice, analytics.ALL_COURSES, 2),
                analytics.LEVEL_COURSE,
            )

    def test_one_course_is_by_week_or_day(self):
        """One course: one bar per week, or per day with "Show by day"; "Show by day" only
        matters for one course."""
        self.assertEqual(analytics.choose_chart_level("B1-2627", "PY101", 2),
                         analytics.LEVEL_WEEK)
        self.assertEqual(analytics.choose_chart_level(analytics.ALL_BLOCKS, "PY101", 2),
                         analytics.LEVEL_WEEK)
        self.assertEqual(analytics.choose_chart_level("B1-2627", "PY101", 1, by_day=True),
                         analytics.LEVEL_DAY)
        self.assertEqual(
            analytics.choose_chart_level("B1-2627", analytics.ALL_COURSES, 1, by_day=True),
            analytics.LEVEL_COURSE,
        )

    def test_titles_follow_the_level(self):
        """Stage 7: 'Attendance rate by course', 'Recording status by week'."""
        self.assertEqual(analytics.make_chart_title("Attendance rate", analytics.LEVEL_COURSE),
                         "Attendance rate by course")
        self.assertEqual(analytics.make_chart_title("Recording status", analytics.LEVEL_WEEK),
                         "Recording status by week")


class TestDrillDownRates(SeedTestCase):

    def test_only_one_block_shows_courses(self):
        """The seed has only one block, so All blocks shows one bar per course:
        PY101 96.30%, DS102 98.63%, MA103 99.38% (worked out in test_rate_per_course)."""
        self.assertEqual(analytics.count_blocks(self.records), 1)
        level, summary = analytics.build_drilldown_chart_data(
            self.records, analytics.ALL_BLOCKS, analytics.ALL_COURSES
        )

        self.assertEqual(level, analytics.LEVEL_COURSE)
        self.assertEqual(self.rates_by_label(summary),
                         {"PY101": 96.30, "DS102": 98.63, "MA103": 99.38})

    def test_rate_per_block(self):
        """With a second block, All blocks shows one bar per block. B2-2627 starts on
        21/09/2026 with PY201; 001 is enrolled and Present on 21/09 only, so B2-2627 has
        1 Present and 14 Unknown: 1 / 1 = 100.00%. B1-2627 keeps the seed totals:
        (477 + 10) / (477 + 10 + 10) = 487 / 497 = 97.99%."""
        database.add_block(self.connection, "B2-2627", "Block 2, 2026-27", "2026-09-21")
        database.create_course(self.connection, "PY201", "Python 2", "B2-2627")
        database.enroll_student(self.connection, "001", "PY201")
        database.record_attendance(self.connection, "001", "PY201-2026-09-21", "Present")
        records = analytics.build_records_frame(database.get_expected_records(self.connection))

        level, summary = analytics.build_drilldown_chart_data(
            records, analytics.ALL_BLOCKS, analytics.ALL_COURSES
        )

        self.assertEqual(level, analytics.LEVEL_BLOCK)
        self.assertEqual(list(summary[analytics.CHART_LABEL_COLUMN]), ["B1-2627", "B2-2627"])
        self.assertEqual(self.rates_by_label(summary), {"B1-2627": 97.99, "B2-2627": 100.0})
        self.assertEqual(summary.iloc[1]["Unknown"], 14)

    def test_rate_per_course(self):
        """Stage 7: one bar per course of B1-2627, by hand from the seed:
        DS102 140 P, 4 L, 1 E, 2 A, 1 Unknown: 144 / 146 = 98.63%.
        MA103 160 P, 1 L, 2 E, 1 A, 1 Unknown: 161 / 162 = 99.38%.
        PY101 177 P, 5 L, 1 E, 7 A, 2 Unknown: 182 / 189 = 96.30%.
        Together 477 / 10 / 4 / 10 / 4, the seed totals."""
        level, summary = analytics.build_drilldown_chart_data(
            self.records, "B1-2627", analytics.ALL_COURSES
        )

        self.assertEqual(level, analytics.LEVEL_COURSE)
        self.assertEqual(self.rates_by_label(summary),
                         {"DS102": 98.63, "MA103": 99.38, "PY101": 96.30})
        py101 = summary[summary[analytics.CHART_LABEL_COLUMN] == "PY101"].iloc[0]
        self.assertEqual(
            (py101["Present"], py101["Late"], py101["Excused"], py101["Absent"],
             py101["Unknown"]),
            (177, 5, 1, 7, 2),
        )

    def test_rate_per_week(self):
        """Stage 7: PY101 by week, by hand from the seed.

        Week 1 (31/08-04/09): 5 class days + tutorial 03/09, 11 students (010 joins on
        07/09) = 66: 63 P, 2 L, 1 A (002 on 01/09): 65 / 66 = 98.48%.
        Week 2 (07/09-11/09): 5 class days for 12 students + Saturday tutorial 12/09 for
        11 (012 left on 11/09) = 71: 64 P, 3 L, 1 E, 1 A, 2 Unknown (003 on 09/09, 011 at
        the tutorial): 67 / 68 = 98.53%. The weekend tutorial belongs to the week before.
        Week 3 (14/09-18/09): 5 class days, 11 students = 55: 50 P, 5 A (002 on 14-16/09,
        009 on 17-18/09): 50 / 55 = 90.91%.
        """
        level, summary = analytics.build_drilldown_chart_data(
            self.course("PY101"), "B1-2627", "PY101", period_start="2026-08-31"
        )

        self.assertEqual(level, analytics.LEVEL_WEEK)
        self.assertEqual(self.rates_by_label(summary), {
            "Week 1 (31/08–04/09)": 98.48,
            "Week 2 (07/09–11/09)": 98.53,
            "Week 3 (14/09–18/09)": 90.91,
        })
        expected = []
        for index, row in summary.iterrows():
            total = 0
            for status in analytics.STATUS_ORDER:
                total += row[status]
            expected.append(total)
        self.assertEqual(expected, [66, 71, 55])

    def test_rate_per_day(self):
        """Stage 7: "Show by day" gives one bar per date: PY101 has 15 class days and the
        Saturday tutorial; the tutorial on Thursday 03/09 shares that day's bar."""
        level, summary = analytics.build_drilldown_chart_data(
            self.course("PY101"), "B1-2627", "PY101", by_day=True
        )

        self.assertEqual(level, analytics.LEVEL_DAY)
        labels = list(summary[analytics.CHART_LABEL_COLUMN])
        self.assertEqual(len(labels), 16)
        self.assertEqual(labels[0], "Mon 31/08")
        self.assertIn("Sat 12/09", labels)
        # 002 was Absent on 21, 22 and 16/09: 10 of 11 attended each day.
        self.assertEqual(self.rates_by_label(summary)["Mon 14/09"], 90.91)


class TestWeeks(unittest.TestCase):

    def test_block_weeks(self):
        """Stage 7: the Week box of B1-2627 lists three weeks, Monday to Friday in the label."""
        weeks = analytics.build_week_options("2026-08-31", "2026-09-18")

        labels = []
        for week in weeks:
            labels.append(week["label"])
        self.assertEqual(labels, ["Week 1 (31/08–04/09)", "Week 2 (07/09–11/09)",
                                  "Week 3 (14/09–18/09)"])

    def test_weekend_belongs_to_the_week_before(self):
        """Stage 7: a week runs Monday to Sunday, so Saturday 12/09 is in week 2."""
        week_2 = analytics.build_week_options("2026-08-31", "2026-09-18")[1]

        self.assertEqual((week_2["start"], week_2["end"]), ("2026-09-07", "2026-09-13"))


class TestKpiCards(SeedTestCase):

    def test_seed_kpis(self):
        """Stage 7: the seed cards. Deducted marks = 10 Late x 1 + 10 Absent x 2 = 30.
        Nobody is below 75%. One alert: 009 in PY101 (current streak 2).
        12 students, 44 class days (15 + 14 + 15) and 6 tutorials."""
        kpis = analytics.calculate_kpis(self.records, 1, 2, 75, 2)

        self.assertEqual(analytics.format_rate(kpis["attendance_rate"]), "97.99%")
        self.assertEqual(analytics.format_rate(kpis["completeness"]), "99.21%")
        self.assertEqual(kpis["deducted"], 30)
        self.assertEqual(kpis["below_threshold"], 0)
        self.assertEqual(kpis["alerts"], 1)
        self.assertEqual(
            (kpis["present"], kpis["late"], kpis["excused"], kpis["absent"], kpis["unknown"]),
            (477, 10, 4, 10, 4),
        )
        self.assertEqual((kpis["students"], kpis["class_days"], kpis["tutorials"]), (12, 44, 6))

    def test_kpis_follow_the_settings_and_slider(self):
        """Stage 7: Late x 2 + Absent x 3 = 50. At 97%: 002 (90.00%), 009 (96.00%),
        011 (96.88%) and 010 (96.97%) are below. A streak of 3 has no alert."""
        kpis = analytics.calculate_kpis(self.records, 2, 3, 97, 3)

        self.assertEqual(kpis["deducted"], 50)
        self.assertEqual(kpis["below_threshold"], 4)
        self.assertEqual(kpis["alerts"], 0)


class TestNoSessionIds(SeedTestCase):

    def assert_no_session_ids(self, table, name):
        """Fail if a column is about sessions or a cell holds a session ID."""
        for column in table.columns:
            self.assertNotIn("session", str(column).lower(), name)
        for value in table.astype(str).values.ravel():
            self.assertIsNone(SESSION_ID_PATTERN.search(str(value)), f"{name}: {value}")

    def test_report_tables(self):
        """Stage 7: no table built for the screen or a download shows a session ID."""
        records = self.records
        tables = {
            "attendance report": analytics.build_attendance_report(records),
            "student summary": analytics.format_summary_table(
                analytics.add_deduction_columns(analytics.build_student_summary(records), 1, 2)
            ),
            "streaks": analytics.build_streak_table(records),
            "history 011": analytics.build_student_history(
                analytics.filter_student(records, "011")
            ),
            "profile 002": analytics.build_student_profile(
                analytics.filter_student(records, "002"), 1, 2
            ),
        }
        for level in (analytics.LEVEL_BLOCK, analytics.LEVEL_COURSE, analytics.LEVEL_WEEK,
                      analytics.LEVEL_DAY):
            tables[f"chart {level}"] = analytics.build_level_summary(records, level)
        for course_code in ("PY101", "DS102", "MA103"):
            course = database.get_course(self.connection, course_code)
            sessions = database.get_sessions_for_course(self.connection, course_code)
            course_records = self.course(course_code)
            tables[f"register {course_code}"] = analytics.build_class_register(
                sessions, course_records, 1, 2
            )
            tables[f"deductions {course_code}"] = analytics.build_course_deductions(
                records, course_code, 1, 2
            )
            tables[f"weekly 005 {course_code}"] = analytics.build_weekly_view(
                sessions, analytics.filter_student(course_records, "005"),
                course["start_date"], course["end_date"], analytics.WEEKLY_WORDS,
            )

        for name, table in tables.items():
            self.assert_no_session_ids(table, name)

    def test_type_names_the_tutorial(self):
        """Stage 7: the Type column says 'Class' or 'Tutorial T2' instead of the ID."""
        self.assertEqual(analytics.describe_session_type("PY101-2026-08-31", "Class"), "Class")
        self.assertEqual(
            analytics.describe_session_type("MA103-2026-09-16-T2", "Tutorial"), "Tutorial T2"
        )
        report = analytics.build_attendance_report(self.course("MA103"))
        self.assertEqual(
            sorted(set(report["Type"])), ["Class", "Tutorial T1", "Tutorial T2"]
        )


class TestScreensShowNoSessionIds(unittest.TestCase):
    """Stage 7: runs the app on the demo data and checks every table on screen.

    Downloads are made from the same tables (show_table_with_download), so they are
    covered too. The app runs in a temporary folder, so attendance.db is not touched.
    """

    def test_screens(self):
        """Dashboard, Reports (one student), class days list and import review."""
        from streamlit.testing.v1 import AppTest

        old_folder = os.getcwd()
        with tempfile.TemporaryDirectory() as folder:
            os.chdir(folder)
            try:
                found = self.run_screens()
            finally:
                os.chdir(old_folder)
        self.assertEqual(found, [])

    def run_screens(self):
        """Visit the screens and return every session ID found in a table."""
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_file(APP_PATH, default_timeout=120)
        found = []

        def run_and_scan(where):
            app.run()
            self.assertFalse(app.exception, app.exception)
            for frame in app.dataframe:
                for column in frame.value.columns:
                    if "session" in str(column).lower():
                        found.append((where, column))
                for value in frame.value.astype(str).values.ravel():
                    if SESSION_ID_PATTERN.search(str(value)):
                        found.append((where, value))

        run_and_scan("start")
        app.selectbox(key="report_student").select("011 - Claudine Umutoni")
        app.selectbox(key="days_block").select(app.selectbox(key="days_block").options[0])
        run_and_scan("report 011 and class days")
        course_box = app.selectbox(key="days_course_B1-2627")
        course_box.select(course_box.options[-1])
        run_and_scan("class days")

        messy = os.path.join(os.path.dirname(APP_PATH), "demo_data", "messy_import.csv")
        with open(messy, "rb") as handle:
            app.file_uploader[0].set_value(("messy_import.csv", handle.read(), "text/csv"))
        run_and_scan("upload")
        for button in app.button:
            if button.label == "Validate":
                button.click()
        run_and_scan("import review")
        return found


if __name__ == "__main__":
    unittest.main()
