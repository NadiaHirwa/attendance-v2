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
        """T04 (BR-06, BR-23): 2026-09-15 and 15/09/2026 are valid and stored as 2026-09-15;
        2026-02-30, 31/02/2026, 2026-9-5 and empty are invalid."""
        self.assertEqual(validation.parse_date("2026-09-15"), "2026-09-15")
        self.assertEqual(validation.parse_date("15/09/2026"), "2026-09-15")

        for date_text in ["2026-02-30", "31/02/2026", "2026-9-5", ""]:
            self.assertIsNone(validation.parse_date(date_text), date_text)

    def test_day_comes_first(self):
        """BR-23: 07/09/2026 always means 7 September, not 9 July."""
        self.assertEqual(validation.parse_date("07/09/2026"), "2026-09-07")

    def test_format_date_for_display(self):
        """BR-23: stored dates are shown as DD/MM/YYYY; other text is left unchanged."""
        self.assertEqual(validation.format_date("2026-09-07"), "07/09/2026")
        self.assertEqual(validation.format_date("now"), "now")
        self.assertEqual(validation.format_date("2026-02-30"), "2026-02-30")
        self.assertIsNone(validation.format_date(None))


class TestBlocksAndClassDays(unittest.TestCase):

    def test_block_id(self):
        """BR-18: b1-2627 becomes B1-2627; B, a 11-character ID and B1 2627 are invalid."""
        self.assertEqual(validation.normalize_block_id(" b1-2627 "), "B1-2627")

        for block_id in ["B", "B1-2627-ABC", "B1 2627", "B1_2627"]:
            self.assertIsNone(validation.normalize_block_id(block_id), block_id)

    def test_block_starts_on_monday(self):
        """BR-18: 2026-09-07 is a Monday; 2026-09-08 is not."""
        self.assertTrue(validation.is_monday("2026-09-07"))
        self.assertFalse(validation.is_monday("2026-09-08"))

    def test_block_end_is_friday_of_week_3(self):
        """BR-18: a block starting Monday 07/09/2026 ends Friday 25/09/2026 (start + 18 days)."""
        end_date = validation.calculate_block_end("2026-09-07")

        self.assertEqual(end_date, "2026-09-25")
        self.assertEqual(validation.weekday_name(end_date), "Friday")

    def test_class_days_skip_weekends(self):
        """BR-20: a 3-week block has 15 class days, Monday to Friday, never a weekend."""
        class_days = validation.list_class_days("2026-09-07", "2026-09-25")

        self.assertEqual(len(class_days), 15)
        self.assertEqual(class_days[0], "2026-09-07")
        self.assertEqual(class_days[4], "2026-09-11")
        self.assertEqual(class_days[5], "2026-09-14")
        self.assertNotIn("2026-09-12", class_days)
        self.assertNotIn("2026-09-13", class_days)

    def test_generated_session_ids(self):
        """BR-20, BR-21: class day and tutorial IDs are built from the course and date."""
        self.assertEqual(
            validation.make_class_session_id("PY101", "2026-09-07"), "PY101-2026-09-07"
        )
        self.assertEqual(
            validation.make_tutorial_session_id("PY101", "2026-09-10", 2), "PY101-2026-09-10-T2"
        )

    def test_session_type(self):
        """IR-12, IR-13: an empty type means Class; Tutorial in any case; other values fail."""
        self.assertEqual(validation.normalize_session_type(""), "Class")
        self.assertEqual(validation.normalize_session_type(" CLASS "), "Class")
        self.assertEqual(validation.normalize_session_type("tutorial"), "Tutorial")
        self.assertIsNone(validation.normalize_session_type("Lab"))


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
