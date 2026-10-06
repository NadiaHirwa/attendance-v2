"""Tests for validation.py (T01 to T05 in Section 10 of the spec)."""

import unittest

import validation


class TestStudentId(unittest.TestCase):

    def test_t01_student_id(self):
        """T01 (BR-01): 001 and 999 are valid; 000, 1, 1000, 12A, +01 and Arabic digits are not."""
        for student_id in ["001", "999"]:
            self.assertTrue(validation.is_valid_student_id(student_id), student_id)

        for student_id in ["000", "1", "1000", "12A", "+01", "٠٠١"]:
            self.assertFalse(validation.is_valid_student_id(student_id), student_id)


class TestName(unittest.TestCase):

    def test_t02_valid_names(self):
        """T02 (BR-02): Jean-Paul is valid; O’Neil is cleaned to O'Neil and is valid."""
        self.assertTrue(validation.is_valid_name(validation.clean_name("Jean-Paul")))

        cleaned = validation.clean_name("O’Neil")
        self.assertEqual(cleaned, "O'Neil")
        self.assertTrue(validation.is_valid_name(cleaned))

    def test_t02_invalid_names(self):
        """T02 (BR-02): -Nadia, Jean--Paul, Jean - Paul and a 51-letter name are invalid."""
        long_name = "A" * 51
        for name in ["-Nadia", "Jean--Paul", "Jean - Paul", long_name]:
            cleaned = validation.clean_name(name)
            self.assertFalse(validation.is_valid_name(cleaned), name)

    def test_t02_clean_name_collapses_spaces(self):
        """T02 (BR-02): extra spaces are collapsed when the name is cleaned."""
        self.assertEqual(validation.clean_name("  Nadia   Hirwa "), "Nadia Hirwa")


class TestCourseCode(unittest.TestCase):

    def test_t03_course_code(self):
        """T03 (BR-03): py101 becomes PY101; 1, 123 and 'PY 101' are invalid."""
        self.assertEqual(validation.normalize_course_code("py101"), "PY101")

        for course_code in ["1", "123", "PY 101"]:
            self.assertIsNone(validation.normalize_course_code(course_code), course_code)


class TestSessionDate(unittest.TestCase):

    def test_t04_session_date(self):
        """T04 (BR-06): 2026-09-15 is valid; 2026-02-30, 15/09/2026 and empty are invalid."""
        self.assertEqual(validation.parse_date("2026-09-15"), "2026-09-15")

        for date_text in ["2026-02-30", "15/09/2026", ""]:
            self.assertIsNone(validation.parse_date(date_text), date_text)


class TestStatus(unittest.TestCase):

    def test_t05_status(self):
        """T05 (BR-07): p, PRESENT and ' a ' are accepted; maybe and x are rejected."""
        self.assertEqual(validation.normalize_status("p"), "Present")
        self.assertEqual(validation.normalize_status("PRESENT"), "Present")
        self.assertEqual(validation.normalize_status(" a "), "Absent")

        for status in ["maybe", "x"]:
            self.assertIsNone(validation.normalize_status(status), status)

    def test_t05_late_and_excused(self):
        """T05 (BR-07, FR-26): L, late, E and EXCUSED are accepted and stored as full words."""
        self.assertEqual(validation.normalize_status("L"), "Late")
        self.assertEqual(validation.normalize_status("late"), "Late")
        self.assertEqual(validation.normalize_status("e"), "Excused")
        self.assertEqual(validation.normalize_status(" EXCUSED "), "Excused")


if __name__ == "__main__":
    unittest.main()
