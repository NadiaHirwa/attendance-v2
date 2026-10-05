"""Tests for analytics.py and database.py (T06, T07, T13, T14, and the Stage 4 filters).

Every test uses a temporary in-memory database, never attendance.db.
"""

import sqlite3
import unittest

import analytics
import database
import seed_demo

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

    def test_not_enrolled_is_not_saved(self):
        """BR-09: a student not enrolled in the session's course is not recorded."""
        database.add_student(self.connection, "002", "Jean-Paul Mugisha")

        result = database.record_attendance(self.connection, "002", "PY101-W1", "Present")

        self.assertEqual(result, "not_enrolled")
        self.assertIsNone(database.get_status(self.connection, "002", "PY101-W1"))

    def test_t14_foreign_keys_are_on(self):
        """T14 (Section 3): attendance for a missing session raises an error."""
        self.add_enrolled_student("001", "Nadia Hirwa")

        with self.assertRaises(sqlite3.IntegrityError):
            database.record_attendance(self.connection, "001", "NO-SUCH-SESSION", "Present")

    def test_t14_foreign_keys_pragma(self):
        """T14 (Section 3): get_connection() switches foreign keys on."""
        value = self.connection.execute("PRAGMA foreign_keys").fetchone()[0]
        self.assertEqual(value, 1)


class SeedDataTestCase(unittest.TestCase):
    """Base class: the seed_demo.py data in an in-memory database. It has no tests itself."""

    def setUp(self):
        """Load the demo data and build the records frame."""
        self.connection = seed_demo.reset_database(TEST_DB_PATH)
        seed_demo.add_demo_data(self.connection)
        seed_demo.add_demo_attendance(self.connection)
        self.records = self.load_records()

    def tearDown(self):
        """Close the database after each test."""
        self.connection.close()

    def load_records(self):
        """Return the expected records of the test database as a frame."""
        return analytics.build_records_frame(database.get_expected_records(self.connection))

    def filter_all(self):
        """Return the records for All courses and the full date range."""
        earliest, latest = analytics.get_date_bounds(self.records)
        return analytics.filter_records(self.records, analytics.ALL_COURSES, earliest, latest)


class TestFilteredCalculations(SeedDataTestCase):
    """Dashboard and report calculations on the seed data (FR-12 to FR-16)."""

    def test_seed_totals_all_courses_full_range(self):
        """FR-12, FR-13 (BR-10 to BR-12): seed data gives 63, 9, 4, 87.50% and 94.74%."""
        earliest, latest = analytics.get_date_bounds(self.records)
        self.assertEqual((earliest, latest), ("2026-09-07", "2026-09-30"))

        metrics = analytics.calculate_dashboard_metrics(self.filter_all())

        self.assertEqual(metrics["present"], 63)
        self.assertEqual(metrics["absent"], 9)
        self.assertEqual(metrics["unknown"], 4)
        self.assertEqual(analytics.format_rate(metrics["attendance_rate"]), "87.50%")
        self.assertEqual(analytics.format_rate(metrics["completeness"]), "94.74%")
        self.assertEqual(metrics["students"], 12)
        self.assertEqual(metrics["sessions"], 8)

    def test_filter_one_course(self):
        """FR-12: PY101 only has 10 students x 4 sessions: 33 Present, 5 Absent, 2 Unknown."""
        filtered = analytics.filter_records(self.records, "PY101", "2026-09-01", "2026-09-30")
        metrics = analytics.calculate_dashboard_metrics(filtered)

        self.assertEqual(metrics["present"], 33)
        self.assertEqual(metrics["absent"], 5)
        self.assertEqual(metrics["unknown"], 2)
        self.assertEqual(metrics["attendance_rate"], 86.84)
        self.assertEqual(metrics["completeness"], 95.0)
        self.assertEqual(metrics["students"], 10)
        self.assertEqual(metrics["sessions"], 4)

    def test_filter_date_range_includes_both_ends(self):
        """FR-12: 2026-09-07 to 2026-09-14 keeps PY101-W1, DS102-W1 and PY101-W2."""
        filtered = analytics.filter_records(
            self.records, analytics.ALL_COURSES, "2026-09-07", "2026-09-14"
        )
        metrics = analytics.calculate_dashboard_metrics(filtered)

        self.assertEqual(metrics["sessions"], 3)
        self.assertEqual(metrics["present"], 25)
        self.assertEqual(metrics["absent"], 3)
        self.assertEqual(metrics["unknown"], 1)

    def test_filter_with_no_sessions(self):
        """FR-18: a date range with no sessions gives empty data and N/A, not an error."""
        filtered = analytics.filter_records(
            self.records, analytics.ALL_COURSES, "2027-01-01", "2027-01-31"
        )
        metrics = analytics.calculate_dashboard_metrics(filtered)

        self.assertTrue(filtered.empty)
        self.assertEqual(metrics["sessions"], 0)
        self.assertEqual(analytics.format_rate(metrics["attendance_rate"]), "N/A")
        self.assertTrue(analytics.build_rate_chart_data(filtered).empty)

    def test_chart_data_in_date_order(self):
        """FR-14: one rate per session in date order, with short labels and the course."""
        chart_data = analytics.build_rate_chart_data(self.filter_all())
        labels = list(chart_data[analytics.CHART_LABEL_COLUMN])
        courses = list(chart_data[analytics.CHART_COURSE_COLUMN])

        self.assertEqual(len(labels), 8)
        self.assertEqual(labels[0], "09-07 PY101-W1")
        self.assertEqual(labels[1], "09-09 DS102-W1")
        self.assertEqual(courses[0], "PY101")
        self.assertEqual(courses[1], "DS102")
        self.assertEqual(labels, sorted(labels))
        self.assertEqual(chart_data[analytics.CHART_VALUE_COLUMN].iloc[0], 90.0)

    def test_chart_same_date_two_courses(self):
        """FR-14: two sessions on the same date in different courses give two rows,
        in date-then-session order."""
        database.add_session(self.connection, "DS102-W0", "DS102", "2026-09-07")
        database.record_attendance(self.connection, "004", "DS102-W0", "Present")
        self.records = self.load_records()

        chart_data = analytics.build_rate_chart_data(self.filter_all())
        labels = list(chart_data[analytics.CHART_LABEL_COLUMN])
        courses = list(chart_data[analytics.CHART_COURSE_COLUMN])

        self.assertEqual(len(labels), 9)
        self.assertEqual(labels[0], "09-07 DS102-W0")
        self.assertEqual(labels[1], "09-07 PY101-W1")
        self.assertEqual(courses[0], "DS102")
        self.assertEqual(courses[1], "PY101")
        self.assertEqual(labels[2], "09-09 DS102-W1")

    def test_chart_labels_show_year_across_years(self):
        """FR-14: when sessions are in more than one year, the labels include the year."""
        database.add_session(self.connection, "PY101-W99", "PY101", "2027-01-11")
        database.record_attendance(self.connection, "001", "PY101-W99", "Present")
        self.records = self.load_records()

        chart_data = analytics.build_rate_chart_data(self.filter_all())
        labels = list(chart_data[analytics.CHART_LABEL_COLUMN])

        self.assertEqual(labels[0], "2026-09-07 PY101-W1")
        self.assertEqual(labels[-1], "2027-01-11 PY101-W99")

    def test_chart_one_course(self):
        """FR-14: with one course selected, every bar belongs to that course."""
        filtered = analytics.filter_records(self.records, "PY101", "2026-09-01", "2026-09-30")
        chart_data = analytics.build_rate_chart_data(filtered)

        self.assertEqual(len(chart_data), 4)
        self.assertEqual(set(chart_data[analytics.CHART_COURSE_COLUMN]), {"PY101"})

    def test_status_chart_counts_add_up_to_enrolled(self):
        """FR-20: per session, Present + Absent + Unknown = students enrolled in its course."""
        status_data = analytics.build_status_chart_data(self.filter_all())
        self.assertEqual(len(status_data), 8)

        for index, row in status_data.iterrows():
            course_code = row[analytics.CHART_COURSE_COLUMN]
            enrolled = len(database.get_enrolled_students(self.connection, course_code))
            total = row["Present"] + row["Absent"] + row["Unknown"]
            self.assertEqual(total, enrolled, row[analytics.CHART_LABEL_COLUMN])

    def test_status_chart_by_hand(self):
        """FR-20: PY101-W2 has 8 Present, 1 Absent (006) and 1 Unknown (003)."""
        status_data = analytics.build_status_chart_data(self.filter_all())
        session = status_data[status_data[analytics.CHART_LABEL_COLUMN] == "09-14 PY101-W2"]

        self.assertEqual(session["Present"].iloc[0], 8)
        self.assertEqual(session["Absent"].iloc[0], 1)
        self.assertEqual(session["Unknown"].iloc[0], 1)

    def test_status_chart_same_labels_and_order_as_rate_chart(self):
        """FR-20, FR-14: the status chart uses the same labels in the same order."""
        rate_data = analytics.build_rate_chart_data(self.filter_all())
        status_data = analytics.build_status_chart_data(self.filter_all())

        self.assertEqual(
            list(status_data[analytics.CHART_LABEL_COLUMN]),
            list(rate_data[analytics.CHART_LABEL_COLUMN]),
        )

    def test_status_chart_keeps_unrecorded_session(self):
        """FR-20: a session with no records is shown as all Unknown (the rate chart omits it)."""
        database.add_session(self.connection, "PY101-W5", "PY101", "2026-10-05")
        self.records = self.load_records()

        status_data = analytics.build_status_chart_data(self.filter_all())
        last = status_data.iloc[-1]

        self.assertEqual(last[analytics.CHART_LABEL_COLUMN], "10-05 PY101-W5")
        self.assertEqual((last["Present"], last["Absent"], last["Unknown"]), (0, 0, 10))

    def test_status_chart_long_shape(self):
        """FR-20: the long table has one row per session and status, Present first."""
        status_data = analytics.build_status_chart_data(self.filter_all())
        long_data = analytics.make_status_chart_long(status_data)

        self.assertEqual(len(long_data), 8 * 3)
        first_session = long_data.iloc[0:3]
        self.assertEqual(
            list(first_session[analytics.CHART_STATUS_COLUMN]), ["Present", "Absent", "Unknown"]
        )
        self.assertEqual(list(first_session[analytics.CHART_COUNT_COLUMN]), [9, 1, 0])

    def test_status_chart_keep_statuses(self):
        """FR-20: the status filter keeps only the chosen statuses, in stack order."""
        long_data = analytics.make_status_chart_long(
            analytics.build_status_chart_data(self.filter_all())
        )

        only_unknown = analytics.keep_statuses(long_data, ["Unknown"])
        self.assertEqual(len(only_unknown), 8)
        self.assertEqual(set(only_unknown[analytics.CHART_STATUS_COLUMN]), {"Unknown"})
        self.assertEqual(only_unknown[analytics.CHART_COUNT_COLUMN].sum(), 4)

        two_statuses = analytics.keep_statuses(long_data, ["Unknown", "Present"])
        self.assertEqual(len(two_statuses), 16)
        self.assertEqual(
            list(two_statuses[analytics.CHART_STATUS_COLUMN].iloc[0:2]), ["Present", "Unknown"]
        )

        self.assertTrue(analytics.keep_statuses(long_data, []).empty)

    def test_students_below_threshold_sorted(self):
        """FR-15: below 75% are 002 (25%), 011 (50%) and 012 (66.67%), lowest first."""
        summary = analytics.build_student_summary(self.filter_all())
        below, no_rate = analytics.split_by_threshold(summary, analytics.DEFAULT_THRESHOLD)

        self.assertEqual(list(below["student_id"]), ["002", "011", "012"])
        self.assertEqual(list(below["attendance_rate"]), [25.0, 50.0, 66.67])
        self.assertTrue(no_rate.empty)

    def test_student_without_records_listed_separately(self):
        """FR-15 (BR-10): a student with no recorded sessions has rate N/A and is listed apart."""
        database.add_student(self.connection, "013", "Alice Uwimana")
        database.enroll_student(self.connection, "013", "PY101")
        self.records = self.load_records()

        summary = analytics.build_student_summary(self.filter_all())
        below, no_rate = analytics.split_by_threshold(summary, analytics.DEFAULT_THRESHOLD)

        self.assertEqual(list(no_rate["student_id"]), ["013"])
        self.assertNotIn("013", list(below["student_id"]))

        table = analytics.format_summary_table(no_rate)
        self.assertEqual(table["Attendance rate"].iloc[0], "N/A")
        self.assertEqual(table["Completeness"].iloc[0], "0.00%")

    def test_reports_tables(self):
        """FR-16, FR-17: the report tables have the expected columns and one row per record."""
        filtered = self.filter_all()

        report = analytics.build_attendance_report(filtered)
        self.assertEqual(
            list(report.columns),
            ["Student ID", "Full name", "Course", "Session", "Date", "Status"],
        )
        self.assertEqual(len(report), 76)

        summary_table = analytics.format_summary_table(analytics.build_student_summary(filtered))
        self.assertEqual(len(summary_table), 12)
        row_002 = summary_table[summary_table["Student ID"] == "002"].iloc[0]
        self.assertEqual(row_002["Attendance rate"], "25.00%")
        self.assertEqual(row_002["Completeness"], "100.00%")


class TestSingleStudentReport(SeedDataTestCase):
    """Single student report on the seed data (FR-19)."""

    def test_two_course_student_by_hand(self):
        """FR-19: student 008 has 7 Present, 0 Absent, 1 Unknown (DS102-W3 missing).

        Attendance rate = 7 / 7 = 100.00%. Completeness = 7 / 8 = 87.50%.
        """
        student = analytics.filter_student(self.filter_all(), "008")
        rates = analytics.summarize_frame(student)

        self.assertEqual(rates["present"], 7)
        self.assertEqual(rates["absent"], 0)
        self.assertEqual(rates["unknown"], 1)
        self.assertEqual(analytics.format_rate(rates["attendance_rate"]), "100.00%")
        self.assertEqual(analytics.format_rate(rates["completeness"]), "87.50%")

    def test_course_breakdown_by_hand(self):
        """FR-19: student 008 gets one row per course: PY101 4/0/0 and DS102 3/0/1."""
        student = analytics.filter_student(self.filter_all(), "008")
        table = analytics.format_summary_table(analytics.build_course_summary(student))

        self.assertEqual(list(table["Course"]), ["DS102", "PY101"])
        self.assertEqual(list(table["Present"]), [3, 4])
        self.assertEqual(list(table["Unknown"]), [1, 0])
        self.assertEqual(list(table["Completeness"]), ["75.00%", "100.00%"])

    def test_all_three_statuses_by_hand(self):
        """FR-19: student 012 has 2 Present, 1 Absent, 1 Unknown: 66.67% and 75.00%."""
        student = analytics.filter_student(self.filter_all(), "012")
        rates = analytics.summarize_frame(student)

        self.assertEqual((rates["present"], rates["absent"], rates["unknown"]), (2, 1, 1))
        self.assertEqual(analytics.format_rate(rates["attendance_rate"]), "66.67%")
        self.assertEqual(analytics.format_rate(rates["completeness"]), "75.00%")
        self.assertEqual(len(analytics.build_course_summary(student)), 1)

    def test_history_in_date_order_with_unknown(self):
        """FR-19: the history lists every session in date order; a missing record is Unknown."""
        student = analytics.filter_student(self.filter_all(), "008")
        history = analytics.build_student_history(student)

        self.assertEqual(list(history.columns), ["Session", "Course", "Date", "Status"])
        self.assertEqual(len(history), 8)
        self.assertEqual(list(history["Date"]), sorted(history["Date"]))
        self.assertEqual(history["Session"].iloc[0], "PY101-W1")
        self.assertEqual(history["Session"].iloc[1], "DS102-W1")

        ds102_w3 = history[history["Session"] == "DS102-W3"].iloc[0]
        self.assertEqual(ds102_w3["Status"], "Unknown")

    def test_student_report_respects_filters(self):
        """FR-19, FR-12: with only PY101 selected, student 008 has 4 sessions, all Present."""
        filtered = analytics.filter_records(self.records, "PY101", "2026-09-01", "2026-09-30")
        student = analytics.filter_student(filtered, "008")
        rates = analytics.summarize_frame(student)

        self.assertEqual(len(student), 4)
        self.assertEqual((rates["present"], rates["absent"], rates["unknown"]), (4, 0, 0))

    def test_student_outside_filters_is_empty(self):
        """FR-19, FR-18: a student with no sessions in the filters gives an empty table."""
        filtered = analytics.filter_records(self.records, "PY101", "2026-09-01", "2026-09-30")
        student = analytics.filter_student(filtered, "012")

        self.assertTrue(student.empty)


if __name__ == "__main__":
    unittest.main()
