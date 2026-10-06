"""Tests for importer.py (T08 to T12 in Section 10, plus IR-05, IR-06 and IR-09).

Every test uses a temporary in-memory database, never attendance.db.
"""

import sqlite3
import unittest

import database
import importer

TEST_DB_PATH = ":memory:"
HEADER = "session_id,course_code,session_date,student_id,full_name,status\n"


def make_file(lines):
    """Return CSV bytes made of the standard header and the given data lines."""
    text = HEADER
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
    """Base class: a fresh database with course PY101, student 001 and session PY101-W1."""

    def setUp(self):
        """Create the tables and the starting data."""
        self.connection = database.get_connection(TEST_DB_PATH)
        database.create_tables(self.connection)
        database.add_course(self.connection, "PY101", "Programming with Python")
        database.add_student(self.connection, "001", "Nadia Hirwa")
        database.enroll_student(self.connection, "001", "PY101")
        database.add_session(self.connection, "PY101-W1", "PY101", "2026-09-07")

    def tearDown(self):
        """Close the database after each test."""
        self.connection.close()

    def validate(self, lines):
        """Read and validate a file made of the given lines."""
        rows, error = importer.read_csv(make_file(lines))
        self.assertIsNone(error)
        return importer.validate_rows(self.connection, rows)


class TestReadCsv(ImporterTestCase):

    def test_t08_missing_status_column(self):
        """T08 (IR-01): a file without a status column is rejected and the column is named."""
        file_bytes = b"session_id,course_code,session_date,student_id,full_name\n"
        rows, error = importer.read_csv(file_bytes)

        self.assertEqual(rows, [])
        self.assertIn("status", error)

    def test_headers_any_case_and_extra_columns(self):
        """IR-01: headers are case-insensitive, in any order; extra columns are ignored."""
        file_bytes = (
            "﻿Status,Notes,Full_Name,Student_ID,Session_Date,Course_Code,Session_ID\n"
            "P,hello,Nadia Hirwa,001,2026-09-07,PY101,PY101-W1\n"
        ).encode("utf-8")
        rows, error = importer.read_csv(file_bytes)

        self.assertIsNone(error)
        self.assertEqual(rows[0]["student_id"], "001")
        self.assertEqual(rows[0]["status"], "P")
        self.assertNotIn("notes", rows[0])

    def test_not_utf8(self):
        """IR-01: a file that is not UTF-8 is rejected with a message, not a crash."""
        rows, error = importer.read_csv("Nadia Hirwa,é".encode("utf-16"))

        self.assertEqual(rows, [])
        self.assertIn("UTF-8", error)


class TestValidateRows(ImporterTestCase):

    def test_t09_unknown_course(self):
        """T09 (IR-03): a row for an unknown course is rejected with a reason."""
        accepted, duplicates, rejected = self.validate([
            "BIO200-W1,BIO200,2026-09-07,001,Nadia Hirwa,P",
        ])

        self.assertEqual(len(accepted), 0)
        self.assertEqual(len(rejected), 1)
        self.assertIn('Unknown course "BIO200"', rejected[0]["reason"])
        self.assertIn("Row 2", rejected[0]["reason"])

    def test_t10_same_row_twice(self):
        """T10 (IR-07): the same row twice gives one accepted and one skipped duplicate."""
        accepted, duplicates, rejected = self.validate([
            "PY101-W1,PY101,2026-09-07,001,Nadia Hirwa,P",
            "PY101-W1,PY101,2026-09-07,001,Nadia Hirwa,Present",
        ])

        self.assertEqual(len(accepted), 1)
        self.assertEqual(len(duplicates), 1)
        self.assertEqual(len(rejected), 0)
        self.assertIn("Repeats row 2", duplicates[0]["reason"])

    def test_t10_already_saved(self):
        """T10 (IR-07): a row that matches a saved record is skipped as a duplicate."""
        database.record_attendance(self.connection, "001", "PY101-W1", "Present")

        accepted, duplicates, rejected = self.validate([
            "PY101-W1,PY101,2026-09-07,001,Nadia Hirwa,P",
        ])

        self.assertEqual(len(accepted), 0)
        self.assertEqual(len(duplicates), 1)

    def test_t11_conflicting_status(self):
        """T11 (IR-08): a conflicting status is rejected and the saved record is kept."""
        database.record_attendance(self.connection, "001", "PY101-W1", "Present")

        rows, error = importer.read_csv(make_file([
            "PY101-W1,PY101,2026-09-07,001,Nadia Hirwa,A",
        ]))
        accepted, duplicates, rejected = importer.validate_rows(self.connection, rows)
        importer.apply_import(self.connection, accepted, "test.csv")

        self.assertEqual(len(rejected), 1)
        self.assertIn("already saved as Present", rejected[0]["reason"])
        self.assertEqual(database.get_status(self.connection, "001", "PY101-W1"), "Present")

    def test_t12_saved_id_with_different_name(self):
        """T12 (IR-04): an existing student ID with a different name is rejected."""
        accepted, duplicates, rejected = self.validate([
            "PY101-W1,PY101,2026-09-07,001,Grace Uwase,P",
        ])

        self.assertEqual(len(rejected), 1)
        self.assertIn('already saved as "Nadia Hirwa"', rejected[0]["reason"])

    def test_t12_name_case_is_ignored(self):
        """T12 (IR-04): the same name in a different case is not a conflict."""
        accepted, duplicates, rejected = self.validate([
            "PY101-W1,PY101,2026-09-07,001,NADIA HIRWA,P",
        ])

        self.assertEqual(len(accepted), 1)
        self.assertEqual(len(rejected), 0)

    def test_new_id_with_two_names_in_file(self):
        """IR-04: a new student ID with two names in one file keeps the first row only."""
        accepted, duplicates, rejected = self.validate([
            "PY101-W1,PY101,2026-09-07,002,Grace Uwase,P",
            "PY101-W2,PY101,2026-09-14,002,Grace Mukamana,P",
        ])

        self.assertEqual(len(accepted), 1)
        self.assertEqual(accepted[0]["full_name"], "Grace Uwase")
        self.assertIn("Row 3", rejected[0]["reason"])

    def test_saved_session_with_different_date(self):
        """IR-05: an existing session with a different date is rejected."""
        accepted, duplicates, rejected = self.validate([
            "PY101-W1,PY101,2026-09-08,001,Nadia Hirwa,P",
        ])

        self.assertEqual(len(rejected), 1)
        self.assertIn("already saved for PY101 on 2026-09-07", rejected[0]["reason"])

    def test_new_session_with_two_courses_in_file(self):
        """IR-05: a new session ID with two different courses in one file keeps the first row."""
        database.add_course(self.connection, "DS102", "Data Science Basics")

        accepted, duplicates, rejected = self.validate([
            "NEW-1,PY101,2026-09-20,001,Nadia Hirwa,P",
            "NEW-1,DS102,2026-09-20,002,Grace Uwase,P",
        ])

        self.assertEqual(len(accepted), 1)
        self.assertEqual(len(rejected), 1)
        self.assertIn("earlier in this file (row 2)", rejected[0]["reason"])

    def test_format_errors_name_the_value(self):
        """IR-02: bad values are rejected with the row number and the value found."""
        accepted, duplicates, rejected = self.validate([
            "PY101-W1,PY101,2026-09-07,12A,Nadia Hirwa,P",
            "PY101-W1,PY101,2026-02-30,001,Nadia Hirwa,P",
            "PY101-W1,PY101,2026-09-07,001,Nadia Hirwa,maybe",
        ])

        self.assertEqual(len(rejected), 3)
        self.assertIn('Row 2: Invalid student ID', rejected[0]["reason"])
        self.assertIn('Got "12A"', rejected[0]["reason"])
        self.assertIn('Got "2026-02-30"', rejected[1]["reason"])
        self.assertIn('Got "maybe"', rejected[2]["reason"])

    def test_validation_never_writes(self):
        """IR-09: validating a file saves nothing before Confirm."""
        self.validate([
            "PY101-W2,PY101,2026-09-14,002,Grace Uwase,P",
        ])

        self.assertEqual(count_rows(self.connection, "attendance"), 0)
        self.assertEqual(count_rows(self.connection, "students"), 1)
        self.assertEqual(count_rows(self.connection, "sessions"), 1)


class TestApplyImport(ImporterTestCase):

    def test_new_student_is_enrolled_and_saved(self):
        """IR-06, IR-10: a new student is created, enrolled, and saved with the filename."""
        rows, error = importer.read_csv(make_file([
            "PY101-W2,PY101,2026-09-14,002,Grace Uwase,A",
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

    def test_failure_saves_nothing(self):
        """IR-09: if one row fails while saving, the whole import is rolled back."""
        good_row = {
            "student_id": "002", "full_name": "Grace Uwase", "course_code": "PY101",
            "session_id": "PY101-W2", "session_date": "2026-09-14", "status": "Present",
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
        """FR-11: the template is a header line with every required column."""
        template = importer.make_template_csv()
        rows, error = importer.read_csv(template.encode("utf-8"))

        self.assertIsNone(error)
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
