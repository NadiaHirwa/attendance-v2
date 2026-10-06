"""Validation rules for the attendance system (BR-01 to BR-07, BR-18 to BR-23).

Every function here is pure: it takes text and returns a result.
There is no database and no Streamlit code, so all rules can be tested.
"""

import unicodedata
from datetime import datetime, timedelta

MAX_NAME_LENGTH = 50
MIN_COURSE_CODE_LENGTH = 2
MAX_COURSE_CODE_LENGTH = 10
MAX_COURSE_NAME_LENGTH = 80
MAX_SESSION_ID_LENGTH = 20
MIN_BLOCK_ID_LENGTH = 2
MAX_BLOCK_ID_LENGTH = 10
# Dates are stored as YYYY-MM-DD and shown as DD/MM/YYYY (BR-23).
DATE_FORMAT = "%Y-%m-%d"
DISPLAY_DATE_FORMAT = "%d/%m/%Y"
# A block lasts 3 weeks, Monday of week 1 to Friday of week 3 (BR-18).
BLOCK_WEEKS = 3
WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
CLASS = "Class"
TUTORIAL = "Tutorial"
# Marks deducted per Late and per Absent (BR-22): the defaults of the settings table.
DEFAULT_LATE_DEDUCTION = 1
DEFAULT_ABSENT_DEDUCTION = 2
MIN_DEDUCTION = 0
MAX_DEDUCTION = 10

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
DATE_ERROR = (
    "Invalid date. Expected a real date as DD/MM/YYYY or YYYY-MM-DD "
    "(for example 15/09/2026)."
)
TYPE_ERROR = "Invalid type. Expected Class or Tutorial (or leave it empty for Class)."
BLOCK_ID_ERROR = (
    "Invalid block ID. Expected 2 to 10 letters, digits or hyphens (for example B1-2627)."
)
BLOCK_NAME_ERROR = "Invalid block name. Expected 1 to 80 characters."
BLOCK_START_ERROR = "Invalid block start. A block must start on a Monday; {} is a {}."
BLOCK_EXISTS_ERROR = "Block {} already exists. Enter a different block ID."
BLOCK_IN_USE_ERROR = (
    "Block {} cannot be deleted: it still has {} course(s). Delete those courses first."
)
COURSE_OUTSIDE_BLOCK_ERROR = (
    "Invalid course dates. {} is in block {}, which runs {}. "
    "The course dates must stay inside the block."
)
RECORDS_ON_REMOVED_DAYS_ERROR = (
    "Cannot change the dates: {} saved attendance record(s) of {} are on days outside "
    "the new period and would be lost. Delete those records first or choose a wider period."
)
NO_CLASS_ERROR = "{} has no class on {} {}."
CLASS_DAY_REMOVED_ERROR = "{} has no class on {} {} (class day removed)."
DEDUCTION_ERROR = "Invalid {} deduction {}. Expected a whole number from 0 to 10."
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
    "Change those in Late start or early leave first, or choose a wider period."
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
STATUS_CONFLICT_SAVED_ERROR = (
    "Student {} is already saved as {} for session {}, not {}. "
    "The saved record is kept; correct it in Manage Attendance."
)
STATUS_CONFLICT_FILE_ERROR = (
    "Student {} is already {} for session {} earlier in this file (row {}), not {}. "
    "The first row is kept."
)
SUGGESTION_REASON = ' Suggestion: "{}". Choose it under Suggestions and click Apply suggestions.'
# FR-31 suggestions (S1 to S4).
USE_SAVED_NAME_SUGGESTION = "Use saved name {}"
NEW_ID_SUGGESTION = "Assign next free ID {} as a new student"
KEEP_SAVED_STATUS_CHOICE = "Keep saved {}"
USE_FILE_STATUS_CHOICE = "Use file: {}"
# FR-31 auto-fixes: why each value was changed.
FIX_SPACES = "Removed extra spaces."
FIX_APOSTROPHE = "Replaced a curly apostrophe."
FIX_CAPITALS = "Standard capitals."
FIX_STUDENT_ID = "Padded the student ID to 3 digits."
FIX_DATE = "Changed the date to DD/MM/YYYY."
FIX_STATUS = "Changed to the full status word."
FIX_TYPE = "Changed to the standard type."
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


def pad_student_id(student_id):
    """Return a 1- or 2-digit ASCII student ID padded to 3 digits ('4' -> '004').

    Anything else is returned unchanged, so '0', '00' and '12A' are still rejected
    by is_valid_student_id (FR-31).
    """
    student_id = student_id.strip()
    if len(student_id) in (1, 2) and student_id.isascii() and student_id.isdigit():
        if int(student_id) > 0:
            return student_id.zfill(3)
    return student_id


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
    """Return the date as 'YYYY-MM-DD' text, or None if it is not a real date (BR-06, BR-23).

    Accepts 'YYYY-MM-DD' and 'DD/MM/YYYY'. '07/09/2026' always means 7 September.
    """
    date_text = date_text.strip()

    # strptime alone would accept '2026-9-15' or '7/9/2026', so check the exact shape first.
    if len(date_text) != 10:
        return None

    if date_text[4] == "-" and date_text[7] == "-":
        pattern = DATE_FORMAT
    elif date_text[2] == "/" and date_text[5] == "/":
        pattern = DISPLAY_DATE_FORMAT
    else:
        return None

    try:
        parsed = datetime.strptime(date_text, pattern)
    except ValueError:
        return None

    return parsed.strftime(DATE_FORMAT)


def format_date(date_text):
    """Return a stored 'YYYY-MM-DD' date as 'DD/MM/YYYY' for screens and downloads (BR-23).

    Anything that is not a real stored date (None, 'start', 'now', or a bad value from
    a file such as '2026-02-30') is returned unchanged.
    """
    if date_text is None or not isinstance(date_text, str):
        return date_text
    if len(date_text) != 10 or date_text[4] != "-" or date_text[7] != "-":
        return date_text

    try:
        parsed = datetime.strptime(date_text, DATE_FORMAT)
    except ValueError:
        return date_text
    return parsed.strftime(DISPLAY_DATE_FORMAT)


def weekday_name(date_text):
    """Return the weekday of a 'YYYY-MM-DD' date in English, like 'Monday'."""
    parsed = datetime.strptime(date_text, DATE_FORMAT)
    return WEEKDAY_NAMES[parsed.weekday()]


# ---------- Blocks, class days and tutorials (BR-18 to BR-21) ----------

def normalize_block_id(block_id):
    """Return the block ID in uppercase, or None if it is invalid (BR-18)."""
    block_id = block_id.strip()
    length = len(block_id)

    if length < MIN_BLOCK_ID_LENGTH or length > MAX_BLOCK_ID_LENGTH:
        return None

    for character in block_id:
        if not character.isascii():
            return None
        if not character.isalnum() and character != "-":
            return None

    return block_id.upper()


def is_monday(date_text):
    """Return True if a 'YYYY-MM-DD' date is a Monday (BR-18)."""
    return weekday_name(date_text) == "Monday"


def calculate_block_end(start_date):
    """Return the Friday of week 3 for a block starting on a Monday (BR-18).

    Monday + 18 days = Friday of week 3 (two full weeks of 7 days, then 4 more days).
    """
    start = datetime.strptime(start_date, DATE_FORMAT)
    end = start + timedelta(days=(BLOCK_WEEKS - 1) * 7 + 4)
    return end.strftime(DATE_FORMAT)


def list_class_days(start_date, end_date):
    """Return every Monday to Friday from start_date to end_date, both included (BR-20)."""
    day = datetime.strptime(start_date, DATE_FORMAT)
    last_day = datetime.strptime(end_date, DATE_FORMAT)
    class_days = []

    while day <= last_day:
        # weekday() is 0 for Monday ... 4 for Friday, 5 and 6 for the weekend.
        if day.weekday() < 5:
            class_days.append(day.strftime(DATE_FORMAT))
        day = day + timedelta(days=1)

    return class_days


def make_class_session_id(course_code, session_date):
    """Return the generated ID of a class day, like 'PY101-2026-09-07' (BR-20)."""
    return f"{course_code}-{session_date}"


def make_tutorial_session_id(course_code, session_date, number):
    """Return the generated ID of a tutorial, like 'PY101-2026-09-10-T1' (BR-21)."""
    return f"{course_code}-{session_date}-T{number}"


def normalize_session_type(session_type):
    """Return 'Class' or 'Tutorial'; an empty value means 'Class'. None if invalid."""
    session_type = session_type.strip().lower()

    if session_type in ("", "class"):
        return CLASS

    if session_type in ("tutorial", "tut"):
        return TUTORIAL

    return None


def parse_short_date(date_text):
    """Return a 'D/M/YYYY' date (one or two digits for day and month) as 'YYYY-MM-DD'.

    '7/9/2026' means 7 September 2026 (FR-31 auto-fix). Returns None if it is not
    in that shape or not a real date.
    """
    parts = date_text.strip().split("/")
    if len(parts) != 3:
        return None

    day, month, year = parts
    for part, sizes in [(day, (1, 2)), (month, (1, 2)), (year, (4,))]:
        if not part.isascii() or not part.isdigit() or len(part) not in sizes:
            return None

    return parse_date(f"{int(day):02d}/{int(month):02d}/{year}")


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
    """Return text like 'from 07/09/2026 to 25/09/2026' for a period (BR-16, BR-23)."""
    if start_date is not None and end_date is not None:
        return f"from {format_date(start_date)} to {format_date(end_date)}"
    if start_date is not None:
        return f"from {format_date(start_date)}"
    if end_date is not None:
        return f"until {format_date(end_date)}"
    return "with no set dates"


def parse_deduction(value):
    """Return a deduction setting as a whole number from 0 to 10, or None if invalid (BR-22).

    Accepts a whole number (5, 5.0) or text ('5'). Rejects -1, 11, 1.5 and other text.
    """
    if isinstance(value, bool):
        return None

    if isinstance(value, float):
        if not value.is_integer():
            return None
        value = int(value)

    if isinstance(value, str):
        text = value.strip()
        if not text.isascii() or not text.isdigit():
            return None
        value = int(text)

    if not isinstance(value, int):
        return None

    if value < MIN_DEDUCTION or value > MAX_DEDUCTION:
        return None
    return value


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
