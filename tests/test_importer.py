"""Tests for importer.py (T08 to T12 in Section 10, plus IR-06, IR-09, IR-12, IR-13, BR-23).

Every test uses a temporary in-memory database, never attendance.db.
Version 3 columns: course_code, date, student_id, full_name, status and optional type.
"""

import sqlite3
import unittest

import database
import importer

TEST_DB_PATH = ":memory:"
HEADER = "course_code,date,student_id,full_name,status\n"
HEADER_WITH_TYPE = "course_code,date,student_id,full_name,status,type\n"


def make_file(lines, header=HEADER):
    """Return CSV bytes made of a header and the given data lines."""
    text = header
    for line in lines:
        text = text + line + "\n"
    return text.encode("utf-8")


# Table names cannot be ? parameters, so each count query is written out in full (NFR-04).
COUNT_QUERIES = {
    "attendance": "SELECT COUNT(*) FROM attendance",
    "students": "SELECT COUNT(*) FROM students",
    "sessions": "SELECT COUNT(*) FROM sessions",
}


def count_rows(connection, table_name):
    """Return the number of rows in a table (only used by the tests)."""
    return connection.execute(COUNT_QUERIES[table_name]).fetchone()[0]


class ImporterTestCase(unittest.TestCase):
    """Base class: course PY101, student 001, and class days on Monday 07/09 and 14/09."""

    def setUp(self):
        """Create the tables and the starting data."""
        self.connection = database.get_connection(TEST_DB_PATH)
        database.create_tables(self.connection)
        database.add_course(self.connection, "PY101", "Programming with Python")
        database.add_student(self.connection, "001", "Nadia Hirwa")
        database.enroll_student(self.connection, "001", "PY101")
        database.add_session(self.connection, "PY101-W1", "PY101", "2026-09-07")
        database.add_session(self.connection, "PY101-W2", "PY101", "2026-09-14")

    def tearDown(self):
        """Close the database after each test."""
        self.connection.close()

    def validate(self, lines, header=HEADER):
        """Read and validate a file made of the given lines."""
        rows, error = importer.read_csv(make_file(lines, header))
        self.assertIsNone(error)
        return importer.validate_rows(self.connection, rows)


class TestReadCsv(ImporterTestCase):

    def test_t08_missing_status_column(self):
        """T08 (IR-01): a file without a status column is rejected and the column is named."""
        file_bytes = b"course_code,date,student_id,full_name\n"
        rows, error = importer.read_csv(file_bytes)

        self.assertEqual(rows, [])
        self.assertIn("status", error)

    def test_old_columns_are_rejected(self):
        """IR-01: a Version 2 file (session_date, no date column) names the missing column."""
        file_bytes = b"session_id,course_code,session_date,student_id,full_name,status\n"
        rows, error = importer.read_csv(file_bytes)

        self.assertEqual(rows, [])
        self.assertIn("date", error)

    def test_headers_any_case_and_extra_columns(self):
        """IR-01: headers are case-insensitive, in any order; extra columns are ignored."""
        file_bytes = (
            "﻿Status,Notes,Full_Name,Student_ID,Date,Course_Code,Session_ID\n"
            "P,hello,Nadia Hirwa,001,07/09/2026,PY101,PY101-W1\n"
        ).encode("utf-8")
        rows, error = importer.read_csv(file_bytes)

        self.assertIsNone(error)
        self.assertEqual(rows[0]["student_id"], "001")
        self.assertEqual(rows[0]["status"], "P")
        self.assertEqual(rows[0]["type"], "")
        self.assertNotIn("notes", rows[0])
        self.assertNotIn("session_id", rows[0])

    def test_not_utf8(self):
        """IR-01: a file that is not UTF-8 is rejected with a message, not a crash."""
        rows, error = importer.read_csv("Nadia Hirwa,é".encode("utf-16"))

        self.assertEqual(rows, [])
        self.assertIn("UTF-8", error)


class TestValidateRows(ImporterTestCase):

    def test_t09_unknown_course(self):
        """T09 (IR-03): a row for an unknown course is rejected with a reason."""
        accepted, duplicates, rejected = self.validate([
            "BIO200,2026-09-07,001,Nadia Hirwa,P",
        ])

        self.assertEqual(len(accepted), 0)
        self.assertEqual(len(rejected), 1)
        self.assertIn('Unknown course "BIO200"', rejected[0]["reason"])
        self.assertIn("Row 2", rejected[0]["reason"])

    def test_t10_same_row_twice(self):
        """T10 (IR-07, BR-23): one row twice (two date forms): one accepted, one skipped."""
        accepted, duplicates, rejected = self.validate([
            "PY101,2026-09-07,001,Nadia Hirwa,P",
            "PY101,07/09/2026,001,Nadia Hirwa,Present",
        ])

        self.assertEqual(len(accepted), 1)
        self.assertEqual(len(duplicates), 1)
        self.assertEqual(len(rejected), 0)
        self.assertEqual(accepted[0]["session_id"], "PY101-W1")
        self.assertIn("Repeats row 2", duplicates[0]["reason"])

    def test_t10_already_saved(self):
        """T10 (IR-07): a row that matches a saved record is skipped as a duplicate."""
        database.record_attendance(self.connection, "001", "PY101-W1", "Present")

        accepted, duplicates, rejected = self.validate([
            "PY101,2026-09-07,001,Nadia Hirwa,P",
        ])

        self.assertEqual(len(accepted), 0)
        self.assertEqual(len(duplicates), 1)

    def test_t11_conflicting_status(self):
        """T11 (IR-08): a conflicting status is rejected and the saved record is kept."""
        database.record_attendance(self.connection, "001", "PY101-W1", "Present")

        rows, error = importer.read_csv(make_file([
            "PY101,2026-09-07,001,Nadia Hirwa,A",
        ]))
        accepted, duplicates, rejected = importer.validate_rows(self.connection, rows)
        importer.apply_import(self.connection, accepted, "test.csv")

        self.assertEqual(len(rejected), 1)
        self.assertIn("already saved as Present", rejected[0]["reason"])
        self.assertEqual(database.get_status(self.connection, "001", "PY101-W1"), "Present")

    def test_t12_saved_id_with_different_name(self):
        """T12 (IR-04): an existing student ID with a different name is rejected."""
        accepted, duplicates, rejected = self.validate([
            "PY101,2026-09-07,001,Grace Uwase,P",
        ])

        self.assertEqual(len(rejected), 1)
        self.assertIn('already saved as "Nadia Hirwa"', rejected[0]["reason"])

    def test_t12_name_case_is_ignored(self):
        """T12 (IR-04): the same name in a different case is not a conflict."""
        accepted, duplicates, rejected = self.validate([
            "PY101,2026-09-07,001,NADIA HIRWA,P",
        ])

        self.assertEqual(len(accepted), 1)
        self.assertEqual(len(rejected), 0)

    def test_new_id_with_two_names_in_file(self):
        """IR-04: a new student ID with two names in one file keeps the first row only."""
        accepted, duplicates, rejected = self.validate([
            "PY101,2026-09-07,002,Grace Uwase,P",
            "PY101,2026-09-14,002,Grace Mukamana,P",
        ])

        self.assertEqual(len(accepted), 1)
        self.assertEqual(accepted[0]["full_name"], "Grace Uwase")
        self.assertIn("Row 3", rejected[0]["reason"])

    def test_class_row_on_a_weekend_is_rejected(self):
        """IR-12: a class row on a Saturday is rejected; there is no class that day."""
        accepted, duplicates, rejected = self.validate([
            "PY101,12/09/2026,001,Nadia Hirwa,P",
        ])

        self.assertEqual(len(accepted), 0)
        self.assertEqual(
            rejected[0]["reason"], "Row 2: PY101 has no class on Saturday 12/09/2026."
        )

    def test_class_row_without_a_class_day_is_rejected(self):
        """IR-12: a weekday with no class day (for example a removed holiday) is rejected."""
        accepted, duplicates, rejected = self.validate([
            "PY101,2026-09-08,001,Nadia Hirwa,P",
        ])

        self.assertEqual(
            rejected[0]["reason"], "Row 2: PY101 has no class on Tuesday 08/09/2026."
        )

    def test_tutorial_row_plans_one_new_tutorial(self):
        """IR-13: tutorial rows on a new date share one planned tutorial, T1 (BR-21)."""
        database.add_student(self.connection, "002", "Grace Uwase")
        database.enroll_student(self.connection, "002", "PY101")

        accepted, duplicates, rejected = self.validate([
            "PY101,12/09/2026,001,Nadia Hirwa,P,Tutorial",
            "PY101,12/09/2026,002,Grace Uwase,L,tutorial",
        ], HEADER_WITH_TYPE)

        self.assertEqual(len(accepted), 2)
        self.assertEqual(accepted[0]["session_id"], "PY101-2026-09-12-T1")
        self.assertEqual(accepted[1]["session_id"], "PY101-2026-09-12-T1")

    def test_tutorial_row_uses_an_existing_tutorial(self):
        """IR-13: a tutorial row on a date that already has a tutorial uses it."""
        tutorial_id = database.add_tutorial(self.connection, "PY101", "2026-09-10")

        accepted, duplicates, rejected = self.validate([
            "PY101,10/09/2026,001,Nadia Hirwa,P,Tutorial",
        ], HEADER_WITH_TYPE)

        self.assertEqual(accepted[0]["session_id"], tutorial_id)

    def test_invalid_type_is_rejected(self):
        """IR-02: a type that is not Class or Tutorial is rejected, quoting the value."""
        accepted, duplicates, rejected = self.validate([
            "PY101,2026-09-07,001,Nadia Hirwa,P,Lab",
        ], HEADER_WITH_TYPE)

        self.assertIn("Invalid type", rejected[0]["reason"])
        self.assertIn('Got "Lab"', rejected[0]["reason"])

    def test_format_errors_name_the_value(self):
        """IR-02, BR-23: bad values are rejected with the row number and the value found."""
        accepted, duplicates, rejected = self.validate([
            "PY101,2026-09-07,12A,Nadia Hirwa,P",
            "PY101,2026-02-30,001,Nadia Hirwa,P",
            "PY101,31/02/2026,001,Nadia Hirwa,P",
            "PY101,2026-09-07,001,Nadia Hirwa,maybe",
        ])

        self.assertEqual(len(rejected), 4)
        self.assertIn('Row 2: Invalid student ID', rejected[0]["reason"])
        self.assertIn('Got "12A"', rejected[0]["reason"])
        self.assertIn('Got "2026-02-30"', rejected[1]["reason"])
        self.assertIn('Got "31/02/2026"', rejected[2]["reason"])
        self.assertIn('Got "maybe"', rejected[3]["reason"])

    def test_validation_never_writes(self):
        """IR-09: validating a file saves nothing before Confirm, not even a new tutorial."""
        self.validate([
            "PY101,2026-09-14,002,Grace Uwase,P,Class",
            "PY101,2026-09-12,002,Grace Uwase,P,Tutorial",
        ], HEADER_WITH_TYPE)

        self.assertEqual(count_rows(self.connection, "attendance"), 0)
        self.assertEqual(count_rows(self.connection, "students"), 1)
        self.assertEqual(count_rows(self.connection, "sessions"), 2)


class TestApplyImport(ImporterTestCase):

    def test_new_student_is_enrolled_and_saved(self):
        """IR-06, IR-10: a new student is created, enrolled, and saved with the filename."""
        rows, error = importer.read_csv(make_file([
            "PY101,14/09/2026,002,Grace Uwase,A",
        ]))
        accepted, duplicates, rejected = importer.validate_rows(self.connection, rows)
        saved = importer.apply_import(self.connection, accepted, "week2.csv")

        self.assertEqual(saved, 1)
        self.assertTrue(database.is_enrolled(self.connection, "002", "PY101"))
        self.assertEqual(database.get_status(self.connection, "002", "PY101-W2"), "Absent")

        source = self.connection.execute(
            "SELECT source FROM attendance WHERE student_id = ?", ("002",)
        ).fetchone()[0]
        self.assertEqual(source, "week2.csv")

    def test_new_tutorial_is_created_at_confirm(self):
        """IR-13, BR-21: Confirm creates the planned tutorial with type Tutorial."""
        rows, error = importer.read_csv(make_file([
            "PY101,12/09/2026,001,Nadia Hirwa,P,Tutorial",
        ], HEADER_WITH_TYPE))
        accepted, duplicates, rejected = importer.validate_rows(self.connection, rows)
        importer.apply_import(self.connection, accepted, "tutorial.csv")

        tutorial = database.get_session(self.connection, "PY101-2026-09-12-T1")
        self.assertEqual(tutorial["session_type"], "Tutorial")
        self.assertEqual(database.get_status(self.connection, "001", "PY101-2026-09-12-T1"),
                         "Present")

    def test_failure_saves_nothing(self):
        """IR-09: if one row fails while saving, the whole import is rolled back."""
        good_row = {
            "student_id": "002", "full_name": "Grace Uwase", "course_code": "PY101",
            "session_id": "PY101-W2", "date": "2026-09-14", "type": "Class",
            "status": "Present",
        }
        # A course that does not exist breaks the foreign key on purpose.
        bad_row = dict(good_row)
        bad_row["student_id"] = "003"
        bad_row["course_code"] = "NOPE1"
        bad_row["session_id"] = "NOPE1-W1"

        with self.assertRaises(sqlite3.IntegrityError):
            importer.apply_import(self.connection, [good_row, bad_row], "bad.csv")

        self.assertEqual(count_rows(self.connection, "attendance"), 0)
        self.assertIsNone(database.get_student(self.connection, "002"))


class TestTemplate(unittest.TestCase):

    def test_template_has_required_columns(self):
        """FR-11: the template is a header line with every required column and type."""
        template = importer.make_template_csv()
        rows, error = importer.read_csv(template.encode("utf-8"))

        self.assertIsNone(error)
        self.assertEqual(rows, [])
        self.assertEqual(template.strip(), "course_code,date,student_id,full_name,status,type")


if __name__ == "__main__":
    unittest.main()
