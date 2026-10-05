"""Validation rules for the attendance system (BR-01 to BR-07).

Every function here is pure: it takes text and returns a result.
There is no database and no Streamlit code, so all rules can be tested.
"""

import unicodedata
from datetime import datetime

MAX_NAME_LENGTH = 50
MIN_COURSE_CODE_LENGTH = 2
MAX_COURSE_CODE_LENGTH = 10
MAX_COURSE_NAME_LENGTH = 80
MAX_SESSION_ID_LENGTH = 20
DATE_FORMAT = "%Y-%m-%d"

# Error messages say what was wrong and what is expected (BR-13).
STUDENT_ID_ERROR = "Invalid student ID. Expected exactly 3 digits from 001 to 999."
NAME_ERROR = (
    "Invalid name. Use 1 to 50 letters, spaces, hyphens or apostrophes, "
    "with at least one letter. Each hyphen or apostrophe needs a letter "
    "directly on both sides."
)
COURSE_CODE_ERROR = (
    "Invalid course code. Expected 2 to 10 letters or digits, "
    "with at least one letter (for example PY101)."
)
COURSE_NAME_ERROR = "Invalid course name. Expected 1 to 80 characters."
SESSION_ID_ERROR = (
    "Invalid session ID. Expected 1 to 20 letters, digits or hyphens "
    "(for example PY101-W1)."
)
DATE_ERROR = "Invalid date. Expected a real date in YYYY-MM-DD format (for example 2026-09-15)."
STATUS_ERROR = "Invalid status. Expected P, A, Present or Absent."


def is_valid_student_id(student_id):
    """Return True if student_id is exactly 3 ASCII digits from 001 to 999 (BR-01)."""
    if len(student_id) != 3:
        return False

    # isascii() rejects digits from other scripts, such as Arabic-Indic digits.
    if not student_id.isascii() or not student_id.isdigit():
        return False

    if student_id == "000":
        return False

    return True


def clean_name(name):
    """Return the name with standard apostrophes, single spaces and NFC form (BR-02)."""
    name = name.replace("’", "'")
    name = unicodedata.normalize("NFC", name)
    words = name.split()
    return " ".join(words)


def is_valid_name(name):
    """Return True if an already-cleaned name follows the V1 name rules (BR-02)."""
    if len(name) == 0 or len(name) > MAX_NAME_LENGTH:
        return False

    has_letter = False
    last_index = len(name) - 1

    for index, character in enumerate(name):
        if character.isalpha():
            has_letter = True

        elif character == " ":
            continue

        elif character in ("-", "'"):
            # A hyphen or apostrophe must sit between two letters.
            if index == 0 or index == last_index:
                return False
            if not name[index - 1].isalpha() or not name[index + 1].isalpha():
                return False

        else:
            return False

    return has_letter


def normalize_course_code(course_code):
    """Return the course code in uppercase, or None if it is invalid (BR-03)."""
    course_code = course_code.strip()
    length = len(course_code)

    if length < MIN_COURSE_CODE_LENGTH or length > MAX_COURSE_CODE_LENGTH:
        return None

    if not course_code.isascii() or not course_code.isalnum():
        return None

    has_letter = False
    for character in course_code:
        if character.isalpha():
            has_letter = True

    if not has_letter:
        return None

    return course_code.upper()


def clean_course_name(course_name):
    """Return the trimmed course name, or None if it is invalid (BR-04)."""
    course_name = course_name.strip()

    if len(course_name) == 0 or len(course_name) > MAX_COURSE_NAME_LENGTH:
        return None

    return course_name


def is_valid_session_id(session_id):
    """Return True if session_id has 1 to 20 ASCII letters, digits or hyphens (BR-05)."""
    if len(session_id) == 0 or len(session_id) > MAX_SESSION_ID_LENGTH:
        return False

    for character in session_id:
        if not character.isascii():
            return False
        if not character.isalnum() and character != "-":
            return False

    return True


def normalize_session_id(session_id):
    """Return the session ID in uppercase, or None if it is invalid (BR-05)."""
    session_id = session_id.strip()

    if not is_valid_session_id(session_id):
        return None

    return session_id.upper()


def parse_date(date_text):
    """Return the date as 'YYYY-MM-DD' text, or None if it is not a real date (BR-06)."""
    date_text = date_text.strip()

    # strptime alone would accept '2026-9-15', so check the exact shape first.
    if len(date_text) != 10 or date_text[4] != "-" or date_text[7] != "-":
        return None

    try:
        parsed = datetime.strptime(date_text, DATE_FORMAT)
    except ValueError:
        return None

    return parsed.strftime(DATE_FORMAT)


def normalize_status(status):
    """Return 'Present' or 'Absent', or None if the status is not accepted (BR-07)."""
    status = status.strip().lower()

    if status in ("p", "present"):
        return "Present"

    if status in ("a", "absent"):
        return "Absent"

    return None
