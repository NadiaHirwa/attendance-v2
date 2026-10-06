"""Tests for FR-31: import auto-fixes and suggested fixes (S1 to S4).

Every test uses a temporary in-memory database, never attendance.db.
"""

import unittest

import database
import importer
import validation
from tests.test_importer import HEADER_WITH_TYPE, ImporterTestCase, count_rows, make_file

TYPE_COLUMN = importer.TYPE_COLUMN


class FixesTestCase(ImporterTestCase):
    """Course PY101, student 001 Nadia Hirwa, class days PY101-W1 (07/09) and PY101-W2 (14/09)."""

    def review(self, lines, accepted_keys=()):
        """Read and review a file with a type column; return the review_rows result."""
        rows, error = importer.read_csv(make_file(lines, HEADER_WITH_TYPE))
        self.assertIsNone(error)
        return importer.review_rows(self.connection, rows, accepted_keys)

    def fixes_of(self, result, column):
        """Return (before, after) for each fix of one column."""
        pairs = []
        for fix in result["fixes"]:
            if fix["column"] == column:
                pairs.append((fix["before"], fix["after"]))
        return pairs

    def suggestion_keys(self, result):
        """Return the keys of all suggestions."""
        keys = []
        for suggestion in result["suggestions"]:
            keys.append(suggestion["key"])
        return keys

    def suggestion_texts(self, result):
        """Return the texts of all suggestions, in file order."""
        texts = []
        for suggestion in result["suggestions"]:
            texts.append(suggestion["text"])
        return texts


class TestAutoFixes(FixesTestCase):

    def test_fix_lists_row_column_before_after_and_why(self):
        """FR-31: each auto-fix is listed as row, column, before -> after, with why."""
        result = self.review(["py101,2026-09-07,001,Nadia Hirwa,P,"])

        self.assertIn(
            {"row": 2, "column": "course_code", "before": "py101", "after": "PY101",
             "why": validation.FIX_CAPITALS},
            result["fixes"],
        )
        self.assertEqual(len(result["accepted"]), 1)

    def test_spaces_are_fixed(self):
        """FR-31: extra spaces around values and inside names are removed."""
        result = self.review([" PY101 , 07/09/2026 ,001 ,Nadia   Hirwa,Present ,"])

        self.assertEqual(self.fixes_of(result, "course_code"), [(" PY101 ", "PY101")])
        self.assertEqual(self.fixes_of(result, "date"), [(" 07/09/2026 ", "07/09/2026")])
        self.assertEqual(self.fixes_of(result, "student_id"), [("001 ", "001")])
        self.assertEqual(self.fixes_of(result, "full_name"), [("Nadia   Hirwa", "Nadia Hirwa")])
        self.assertEqual(self.fixes_of(result, "status"), [("Present ", "Present")])
        self.assertEqual(len(result["accepted"]), 1)

    def test_curly_apostrophe_is_fixed(self):
        """FR-31: a curly apostrophe in a name becomes a straight one."""
        result = self.review(["PY101,2026-09-07,002,Grace O’Neil,P,"])

        self.assertEqual(self.fixes_of(result, "full_name"), [("Grace O’Neil", "Grace O'Neil")])
        self.assertEqual(result["accepted"][0]["full_name"], "Grace O'Neil")

    def test_status_letters_and_words_are_fixed(self):
        """FR-31: P/L/E/A and full words in any case become the stored status."""
        lines = []
        statuses = ["P", "l", "E", "a", "present", "LATE", "Excused", "absent"]
        for status in statuses:
            lines.append(f"PY101,2026-09-07,001,Nadia Hirwa,{status},")
        result = self.review(lines)

        self.assertEqual(
            self.fixes_of(result, "status"),
            [("P", "Present"), ("l", "Late"), ("E", "Excused"), ("a", "Absent"),
             ("present", "Present"), ("LATE", "Late"), ("absent", "Absent")],
        )

    def test_one_and_two_digit_ids_are_padded(self):
        """FR-31: '4' -> '004' and '04' -> '004'."""
        result = self.review([
            "PY101,2026-09-07,4,Eric Niyonzima,P,",
            "PY101,2026-09-14,04,Eric Niyonzima,P,",
        ])

        self.assertEqual(self.fixes_of(result, "student_id"), [("4", "004"), ("04", "004")])
        self.assertEqual(len(result["accepted"]), 2)
        self.assertEqual(result["accepted"][1]["student_id"], "004")

    def test_zero_ids_are_not_padded(self):
        """FR-31: '0' and '00' are not fixed and are rejected as before (BR-01)."""
        result = self.review([
            "PY101,2026-09-07,0,Eric Niyonzima,P,",
            "PY101,2026-09-07,00,Eric Niyonzima,P,",
        ])

        self.assertEqual(self.fixes_of(result, "student_id"), [])
        self.assertEqual(len(result["rejected"]), 2)
        self.assertIn('Got "0".', result["rejected"][0]["reason"])
        self.assertIn('Got "00".', result["rejected"][1]["reason"])

    def test_id_with_a_letter_is_not_padded(self):
        """FR-31: only ASCII digits are padded; '4A' is rejected."""
        result = self.review(["PY101,2026-09-07,4A,Eric Niyonzima,P,"])

        self.assertEqual(self.fixes_of(result, "student_id"), [])
        self.assertEqual(len(result["rejected"]), 1)

    def test_dates_are_fixed_to_dd_mm_yyyy(self):
        """FR-31, BR-23: D/M/YYYY and YYYY-MM-DD become DD/MM/YYYY; DD/MM/YYYY is not a fix."""
        result = self.review([
            "PY101,7/9/2026,001,Nadia Hirwa,P,",
            "PY101,14/09/2026,001,Nadia Hirwa,P,",
            "PY101,2026-09-07,001,Nadia Hirwa,P,",
        ])

        self.assertEqual(
            self.fixes_of(result, "date"),
            [("7/9/2026", "07/09/2026"), ("2026-09-07", "07/09/2026")],
        )
        self.assertEqual(result["accepted"][0]["session_id"], "PY101-W1")
        self.assertEqual(result["accepted"][1]["date"], "2026-09-14")

    def test_impossible_short_date_is_rejected(self):
        """FR-31: 31/9/2026 is not a real date, so it is not fixed."""
        result = self.review(["PY101,31/9/2026,001,Nadia Hirwa,P,"])

        self.assertEqual(self.fixes_of(result, "date"), [])
        self.assertIn('Got "31/9/2026".', result["rejected"][0]["reason"])

    def test_type_words_are_fixed(self):
        """FR-31: 'tut', 'tutorial' and 'class' in any case become Tutorial or Class."""
        result = self.review([
            "PY101,2026-09-07,001,Nadia Hirwa,P,class",
            "PY101,2026-09-08,001,Nadia Hirwa,P,TUT",
            "PY101,2026-09-08,001,Nadia Hirwa,P,tutorial",
        ])

        self.assertEqual(
            self.fixes_of(result, TYPE_COLUMN),
            [("class", "Class"), ("TUT", "Tutorial"), ("tutorial", "Tutorial")],
        )
        self.assertEqual(result["accepted"][1]["type"], "Tutorial")

    def test_empty_type_is_not_listed(self):
        """FR-31: an empty type (Class) and a DD/MM/YYYY date are not auto-fixes."""
        result = self.review(["PY101,07/09/2026,001,Nadia Hirwa,Present,"])

        self.assertEqual(result["fixes"], [])

    def test_name_letters_are_not_changed(self):
        """FR-31: names keep their letters and capitals; only spaces and apostrophes change."""
        result = self.review(["PY101,2026-09-07,002,eric niyonzima,P,"])

        self.assertEqual(self.fixes_of(result, "full_name"), [])
        self.assertEqual(result["accepted"][0]["full_name"], "eric niyonzima")



class TestSuggestions(FixesTestCase):

    def test_s1_similar_name_suggests_the_saved_name(self):
        """S1: a saved ID with a similar name; unticked, the row stays rejected."""
        result = self.review(["PY101,2026-09-07,001,Nadia Hirwaa,P,"])

        self.assertEqual(self.suggestion_texts(result), ["Use saved name Nadia Hirwa"])
        self.assertEqual(result["suggestions"][0]["kind"], "S1")
        self.assertEqual(len(result["rejected"]), 1)
        self.assertIn('Suggestion: "Use saved name Nadia Hirwa"', result["rejected"][0]["reason"])

    def test_s1_accepted_uses_the_saved_name(self):
        """S1: when accepted, the row is accepted with the saved name."""
        result = self.review(["PY101,2026-09-07,001,nadia hirwaa,P,"], ["2-S1"])

        self.assertEqual(len(result["accepted"]), 1)
        self.assertEqual(result["accepted"][0]["full_name"], "Nadia Hirwa")
        self.assertTrue(result["suggestions"][0]["accepted"])

    def test_s2_different_name_suggests_the_next_free_id(self):
        """S2: a saved ID with a different name gets the next free ID as a new student."""
        result = self.review(["PY101,2026-09-07,001,Fabrice Gasana,P,"])

        self.assertEqual(self.suggestion_texts(result),
                         ["Assign next free ID 002 as a new student"])
        self.assertEqual(result["suggestions"][0]["kind"], "S2")
        self.assertEqual(len(result["rejected"]), 1)

    def test_s2_accepted_uses_the_new_id(self):
        """S2: when accepted, the row is a new student with the proposed ID."""
        result = self.review(["PY101,2026-09-07,001,Fabrice Gasana,P,"], ["2-S2"])

        self.assertEqual(len(result["accepted"]), 1)
        self.assertEqual(result["accepted"][0]["student_id"], "002")
        self.assertEqual(result["accepted"][0]["full_name"], "Fabrice Gasana")

    def test_next_free_id_skips_used_and_proposed_ids(self):
        """S2: the next free ID is not saved, not in the file and not already proposed."""
        database.add_student(self.connection, "003", "Aline Uwase")
        result = self.review([
            "PY101,2026-09-07,002,Eric Niyonzima,P,",
            "PY101,2026-09-07,001,Fabrice Gasana,P,",
            "PY101,2026-09-07,001,Alice Kayitesi,P,",
        ])

        # 001 and 003 are saved, 002 is in the file, 004 is proposed first.
        self.assertEqual(
            self.suggestion_texts(result),
            ["Assign next free ID 004 as a new student",
             "Assign next free ID 005 as a new student"],
        )

    def test_same_pair_gets_the_same_id(self):
        """S2: the same (file ID, name) pair gets the same proposed ID in every row."""
        result = self.review([
            "PY101,2026-09-07,001,Fabrice Gasana,P,",
            "PY101,2026-09-07,001,Alice Kayitesi,P,",
            "PY101,2026-09-14,001,fabrice  gasana,A,",
        ])

        self.assertEqual(
            self.suggestion_texts(result),
            ["Assign next free ID 002 as a new student",
             "Assign next free ID 003 as a new student",
             "Assign next free ID 002 as a new student"],
        )

    def test_s3_new_id_with_two_names_moves_the_later_name(self):
        """S3: a new ID with two names in the file: the later name gets the next free ID."""
        result = self.review([
            "PY101,2026-09-07,005,Alice Uwimana,P,",
            "PY101,2026-09-14,005,Alice Kayitesi,P,",
        ])

        self.assertEqual(self.suggestion_texts(result),
                         ["Assign next free ID 002 as a new student"])
        self.assertEqual(result["suggestions"][0]["kind"], "S3")
        self.assertEqual(result["suggestions"][0]["row"], 3)
        self.assertEqual(len(result["accepted"]), 1)
        self.assertEqual(len(result["rejected"]), 1)

        accepted = self.review([
            "PY101,2026-09-07,005,Alice Uwimana,P,",
            "PY101,2026-09-14,005,Alice Kayitesi,P,",
        ], ["3-S3"])["accepted"]
        self.assertEqual([row["student_id"] for row in accepted], ["005", "002"])

    def test_s4_status_differs_from_the_saved_record(self):
        """S4: the choice is 'Keep saved Present' (default) or 'Use file: Absent'."""
        database.record_attendance(self.connection, "001", "PY101-W1", "Present")
        result = self.review(["PY101,2026-09-07,001,Nadia Hirwa,A,"])

        suggestion = result["suggestions"][0]
        self.assertEqual(suggestion["kind"], "S4")
        self.assertEqual(suggestion["keep_text"], "Keep saved Present")
        self.assertEqual(suggestion["text"], "Use file: Absent")
        self.assertFalse(suggestion["accepted"])

    def test_s4_default_keeps_the_saved_status(self):
        """S4: by default the row is rejected and Confirm keeps the saved status."""
        database.record_attendance(self.connection, "001", "PY101-W1", "Present")
        result = self.review([
            "PY101,2026-09-07,001,Nadia Hirwa,A,",
            "PY101,2026-09-14,001,Nadia Hirwa,P,",
        ])

        self.assertEqual(len(result["rejected"]), 1)
        importer.apply_import(self.connection, result["accepted"], "file.csv")
        self.assertEqual(database.get_status(self.connection, "001", "PY101-W1"), "Present")

    def test_s4_use_file_updates_the_saved_record(self):
        """S4: 'Use file' updates the record (source = filename) in the import transaction."""
        database.record_attendance(self.connection, "001", "PY101-W1", "Present")
        result = self.review([
            "PY101,2026-09-07,001,Nadia Hirwa,A,",
            "PY101,2026-09-14,001,Nadia Hirwa,P,",
        ], ["2-S4"])

        self.assertEqual(len(result["accepted"]), 2)
        self.assertTrue(result["accepted"][0]["update"])
        saved = importer.apply_import(self.connection, result["accepted"], "file.csv")

        self.assertEqual(saved, 2)
        row = self.connection.execute(
            "SELECT status, source FROM attendance WHERE student_id = ? AND session_id = ?",
            ("001", "PY101-W1"),
        ).fetchone()
        self.assertEqual((row["status"], row["source"]), ("Absent", "file.csv"))
        self.assertEqual(database.get_status(self.connection, "001", "PY101-W2"), "Present")

    def test_suggestions_are_unticked_by_default(self):
        """FR-31: no suggestion is accepted unless its key is given."""
        result = self.review([
            "PY101,2026-09-07,001,Nadia Hirwaa,P,",
            "PY101,2026-09-14,001,Fabrice Gasana,P,",
        ])

        self.assertEqual([s["accepted"] for s in result["suggestions"]], [False, False])
        self.assertEqual(len(result["rejected"]), 2)

    def test_nothing_is_written_before_confirm(self):
        """FR-31, IR-09: reviewing with accepted suggestions does not change the database."""
        database.record_attendance(self.connection, "001", "PY101-W1", "Present")
        lines = [
            "PY101,2026-09-07,001,Nadia Hirwa,A,",
            "PY101,2026-09-14,001,Fabrice Gasana,P,",
            "PY101,2026-09-08,1,Nadia Hirwa,p,tut",
        ]
        first = self.review(lines)
        self.review(lines, self.suggestion_keys(first))

        self.assertEqual(count_rows(self.connection, "attendance"), 1)
        self.assertEqual(count_rows(self.connection, "students"), 1)
        self.assertEqual(count_rows(self.connection, "sessions"), 2)
        self.assertEqual(database.get_status(self.connection, "001", "PY101-W1"), "Present")

    def test_cleaned_file_contents(self):
        """FR-31: the cleaned file has every valid row after fixes and accepted suggestions."""
        database.record_attendance(self.connection, "001", "PY101-W1", "Present")
        result = self.review([
            " py101 ,14/9/2026,1,Nadia  Hirwa,p,",
            "PY101,2026-09-07,001,Nadia Hirwa,P,",
            "PY101,2026-09-14,001,Fabrice Gasana,L,CLASS",
            "BIO200,2026-09-07,001,Nadia Hirwa,P,",
        ], ["4-S2"])

        cleaned = importer.make_cleaned_csv(result["accepted"], result["duplicates"])
        self.assertEqual(
            cleaned,
            "course_code,date,student_id,full_name,status,type\n"
            "PY101,14/09/2026,001,Nadia Hirwa,Present,Class\n"
            "PY101,07/09/2026,001,Nadia Hirwa,Present,Class\n"
            "PY101,14/09/2026,002,Fabrice Gasana,Late,Class\n",
        )

    def test_cleaned_file_can_be_imported_again(self):
        """FR-31: the cleaned file reads back with no auto-fixes and no rejected rows."""
        result = self.review(["py101,7/9/2026,1,Nadia Hirwa,p,"])
        cleaned = importer.make_cleaned_csv(result["accepted"], result["duplicates"])

        rows, error = importer.read_csv(cleaned.encode("utf-8"))
        again = importer.review_rows(self.connection, rows)
        self.assertIsNone(error)
        self.assertEqual(again["fixes"], [])
        self.assertEqual(len(again["accepted"]), 1)
        self.assertEqual(again["rejected"], [])

    def test_count_accepted_suggestions(self):
        """FR-31: the result message counts the accepted suggestions."""
        result = self.review([
            "PY101,2026-09-07,001,Nadia Hirwaa,P,",
            "PY101,2026-09-14,001,Fabrice Gasana,P,",
        ], ["2-S1"])

        self.assertEqual(importer.count_accepted_suggestions(result["suggestions"]), 1)


class TestRemovedClassDay(FixesTestCase):
    """Course DS102 in block B1 (07/09 to 25/09/2026) with Wednesday 16/09 removed."""

    def setUp(self):
        """Add the block, the course and the student, then remove the holiday."""
        super().setUp()
        database.add_block(self.connection, "B1", "Block 1", "2026-09-07")
        database.create_course(self.connection, "DS102", "Data Science Basics", "B1")
        database.enroll_student(self.connection, "001", "DS102")
        database.delete_session(self.connection, "DS102-2026-09-16")

    def test_removed_class_day_says_so(self):
        """IR-12: a weekday whose class was removed names the removed class day."""
        result = self.review(["DS102,16/09/2026,001,Nadia Hirwa,P,"])

        self.assertEqual(
            result["rejected"][0]["reason"],
            "Row 2: DS102 has no class on Wednesday 16/09/2026 (class day removed).",
        )

    def test_import_start_on_course_start_is_stored_as_null(self):
        """BR-17: a new student's first row on the course's first day stores start NULL."""
        result = self.review([
            "DS102,07/09/2026,002,Eric Niyonzima,P,",
            "DS102,08/09/2026,003,Aline Uwase,P,",
        ])
        importer.apply_import(self.connection, result["accepted"], "file.csv")

        first = database.get_enrollment(self.connection, "002", "DS102")
        later = database.get_enrollment(self.connection, "003", "DS102")
        self.assertIsNone(first["start_date"])
        self.assertEqual(later["start_date"], "2026-09-08")

    def test_weekend_keeps_the_plain_message(self):
        """IR-12: a weekend has no class anyway, so the message does not say removed."""
        result = self.review(["DS102,19/09/2026,001,Nadia Hirwa,P,"])

        self.assertEqual(
            result["rejected"][0]["reason"],
            "Row 2: DS102 has no class on Saturday 19/09/2026.",
        )


class TestNextFreeId(unittest.TestCase):

    def test_lowest_free_id(self):
        """S2: the lowest 3-digit ID that is not taken."""
        self.assertEqual(importer.find_next_free_id({"001", "002", "004"}), "003")

    def test_no_free_id(self):
        """S2: None when every ID from 001 to 999 is taken."""
        taken = set()
        for number in range(1, 1000):
            taken.add(f"{number:03d}")
        self.assertIsNone(importer.find_next_free_id(taken))

    def test_similar_name_ratio(self):
        """S1: names at least 80% alike, ignoring case, are similar."""
        self.assertTrue(importer.is_similar_name("Eric Niyonzima", "eric niyonzimma"))
        self.assertFalse(importer.is_similar_name("Claudine Umutoni", "Fabrice Gasana"))


class TestFixHelpers(unittest.TestCase):

    def test_pad_student_id(self):
        """FR-31: 1 or 2 ASCII digits are padded; 0, 00 and other text are unchanged."""
        self.assertEqual(validation.pad_student_id("4"), "004")
        self.assertEqual(validation.pad_student_id("04"), "004")
        self.assertEqual(validation.pad_student_id("12"), "012")
        self.assertEqual(validation.pad_student_id("0"), "0")
        self.assertEqual(validation.pad_student_id("00"), "00")
        self.assertEqual(validation.pad_student_id("١"), "١")

    def test_parse_short_date(self):
        """FR-31: D/M/YYYY is 'day/month/year'; anything else is None."""
        self.assertEqual(validation.parse_short_date("7/9/2026"), "2026-09-07")
        self.assertEqual(validation.parse_short_date("07/9/2026"), "2026-09-07")
        self.assertIsNone(validation.parse_short_date("7/9/26"))
        self.assertIsNone(validation.parse_short_date("31/9/2026"))
        self.assertIsNone(validation.parse_short_date("2026-9-7"))

    def test_parse_date_stays_strict(self):
        """BR-23: typed dates still need the exact form; only the import fixes D/M/YYYY."""
        self.assertIsNone(validation.parse_date("7/9/2026"))

    def test_tut_is_a_tutorial(self):
        """FR-31: 'tut' in any case is a Tutorial."""
        self.assertEqual(validation.normalize_session_type("TuT"), "Tutorial")


if __name__ == "__main__":
    unittest.main()
