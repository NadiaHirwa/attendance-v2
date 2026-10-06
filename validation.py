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
STATUS_ERROR = (
    "Invalid status. Expected P, L, E, A, Present, Late, Excused or Absent."
)

# Messages for values that are valid but already used. {} is filled in with the value.
COURSE_EXISTS_ERROR = "Course {} already exists. Enter a different course code."
STUDENT_EXISTS_ERROR = "Student ID {} is already used. Enter a different student ID."
SESSION_EXISTS_ERROR = "Session {} already exists. Session IDs must be unique across all courses."
ALREADY_ENROLLED_ERROR = "Student {} is already enrolled in {}. Choose a different course."
NO_CHANGE_MESSAGE = "No change: the new {} is the same as the current one."
ENROLLMENT_DATES_ERROR = (
    "Invalid enrollment dates. The end date must be on or after the start date."
)
COURSE_DATES_ERROR = (
    "Invalid course dates. The end date must be on or after the start date."
)
# {} are the course code and describe_course_period(), e.g. "from 2026-09-07 to 2026-12-18".
SESSION_OUTSIDE_COURSE_ERROR = "{} runs {}. Choose a date in that period."
ROW_OUTSIDE_COURSE_ERROR = "{} runs {}, not on {}."
ENROLLMENT_OUTSIDE_COURSE_ERROR = (
    "Invalid enrollment dates. {} runs {}. The enrollment must be inside that period, "
    "with the start on or before the end."
)
ENROLLMENTS_OUTSIDE_PERIOD_ERROR = (
    "Cannot change the dates: {} enrollment(s) in {} would fall outside them. "
    "Change those enrollment dates first or choose a wider period."
)
SESSIONS_OUTSIDE_PERIOD_ERROR = (
    "Cannot change the dates: {} session(s) of {} would fall outside them. "
    "Delete those sessions first or choose a wider period."
)
ENROLLED_FROM_ERROR = "Student {} is enrolled in {} from {}, not on {}."
ENROLLED_UNTIL_ERROR = "Student {} was enrolled in {} until {}, not on {}."
RECORDS_OUTSIDE_DATES_ERROR = (
    "Cannot change the dates: {} saved attendance record(s) of {} in {} would fall "
    "outside them. Delete those records first or choose wider dates."
)
COURSE_IN_USE_ERROR = (
    "Course {} cannot be deleted: it still has {} session(s) and {} enrolled student(s). "
    "Delete those sessions and un-enroll those students first."
)
DUPLICATE_NAME_WARNING = (
    "A student named {} already exists (ID {}). If this is a different person, "
    "tick the confirmation box and submit again."
)

# Messages for CSV import (Section 5). Row reasons start with "Row N: " in importer.py.
FILE_NOT_UTF8_ERROR = (
    "The file could not be read as UTF-8 text. Save it as \"CSV UTF-8\" and upload it again."
)
FILE_NOT_CSV_ERROR = (
    "The file could not be read as CSV. Expected comma-separated rows with a header."
)
MISSING_COLUMNS_ERROR = "The file is missing required column(s): {}. Expected columns: {}."
UNKNOWN_COURSE_ERROR = 'Unknown course "{}". Create it first in Manage Attendance.'
NAME_CONFLICT_SAVED_ERROR = (
    'Student ID {} is already saved as "{}", not "{}". '
    "Use the saved name or a different student ID."
)
NAME_CONFLICT_FILE_ERROR = (
    'Student ID {} appears earlier in this file (row {}) as "{}", not "{}". '
    "Use one name per student ID."
)
SESSION_CONFLICT_SAVED_ERROR = (
    "Session {} is already saved for {} on {}, not {} on {}. "
    "Use the saved course and date or a different session ID."
)
SESSION_CONFLICT_FILE_ERROR = (
    "Session {} appears earlier in this file (row {}) for {} on {}, not {} on {}. "
    "Use one course and date per session ID."
)
STATUS_CONFLICT_SAVED_ERROR = (
    "Student {} is already saved as {} for session {}, not {}. "
    "The saved record is kept; correct it in Manage Attendance."
)
STATUS_CONFLICT_FILE_ERROR = (
    "Student {} is already {} for session {} earlier in this file (row {}), not {}. "
    "The first row is kept."
)
DUPLICATE_SAVED_REASON = "Already saved with the same status."
DUPLICATE_FILE_REASON = "Repeats row {}."


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


def is_date_in_period(date_text, start_date, end_date):
    """Return True if date_text is between start_date and end_date, both included.

    All dates are 'YYYY-MM-DD' text, so comparing the text also compares the dates.
    A start_date or end_date of None means there is no limit on that side.
    Used for enrollment dates (BR-15) and course dates (BR-16).
    """
    if start_date is not None and date_text < start_date:
        return False

    if end_date is not None and date_text > end_date:
        return False

    return True


def is_in_enrollment_window(session_date, start_date, end_date):
    """Return True if a student is expected at a session on session_date (BR-15)."""
    return is_date_in_period(session_date, start_date, end_date)


def are_period_dates_valid(start_date, end_date):
    """Return True unless both dates are set and the end is before the start."""
    if start_date is None or end_date is None:
        return True
    return end_date >= start_date


def are_enrollment_dates_valid(start_date, end_date):
    """Return True unless both dates are set and the end is before the start (BR-15)."""
    return are_period_dates_valid(start_date, end_date)


def is_enrollment_in_course_period(start_date, end_date, course_start, course_end):
    """Return True if an enrollment period fits inside its course period (BR-17).

    The start must be on or before the end, and each set date must be inside the
    course period. None means no limit, for the enrollment and for the course.
    """
    if not are_period_dates_valid(start_date, end_date):
        return False

    if start_date is not None:
        if not is_date_in_period(start_date, course_start, course_end):
            return False

    if end_date is not None:
        if not is_date_in_period(end_date, course_start, course_end):
            return False

    return True


def simplify_enrollment_dates(start_date, end_date, course_start, course_end):
    """Return the enrollment dates to store: a date equal to the course's becomes None (BR-17).

    None means "follow the course", so the enrollment moves with the course
    if the course dates change later.
    """
    if start_date is not None and start_date == course_start:
        start_date = None
    if end_date is not None and end_date == course_end:
        end_date = None
    return start_date, end_date


def describe_course_period(start_date, end_date):
    """Return text like 'from 2026-09-07 to 2026-12-18' for a course's dates (BR-16)."""
    if start_date is not None and end_date is not None:
        return f"from {start_date} to {end_date}"
    if start_date is not None:
        return f"from {start_date}"
    if end_date is not None:
        return f"until {end_date}"
    return "with no set dates"


def normalize_status(status):
    """Return 'Present', 'Late', 'Excused' or 'Absent', or None if not accepted (BR-07)."""
    status = status.strip().lower()

    if status in ("p", "present"):
        return "Present"

    if status in ("l", "late"):
        return "Late"

    if status in ("e", "excused"):
        return "Excused"

    if status in ("a", "absent"):
        return "Absent"

    return None
