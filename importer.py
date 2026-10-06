"""CSV import for the attendance system (Section 5, IR-01 to IR-14).

The workflow has three steps that the app calls in order:
1. read_csv() turns the uploaded bytes into rows (IR-01).
2. review_rows() auto-fixes the rows, suggests fixes for name and status
   conflicts (FR-31) and sorts rows into accepted, duplicates and rejected.
   It finds the class day or tutorial of each row (IR-12, IR-13), and checks the
   course's dates (BR-16) and an existing enrollment's dates (BR-15).
   It reads the database but never writes to it (IR-09).
3. apply_import() saves the accepted rows in one transaction, only after Confirm.
"""

import csv
import difflib
import io

import pandas as pd

import database
import validation

REQUIRED_COLUMNS = [
    "course_code",
    "date",
    "student_id",
    "full_name",
    "status",
]
# Optional column: 'Class' (the default when missing or empty) or 'Tutorial'.
TYPE_COLUMN = "type"
FILE_COLUMNS = REQUIRED_COLUMNS + [TYPE_COLUMN]
ROW_COLUMN = "row"
FIX_COLUMNS = [ROW_COLUMN, "column", "before", "after", "why"]
# S1: a saved name and a file name this alike (0 to 1, ignoring case) are the same person.
SIMILAR_NAME_RATIO = 0.8
WEEKEND_DAYS = ("Saturday", "Sunday")
REASON_COLUMN = "reason"
# Row 1 of the file is the header, so the first data row is row 2, like in a spreadsheet.
FIRST_DATA_ROW = 2


# ---------- Step 1: read the file ----------

def find_missing_columns(header):
    """Return the required columns that are not in the header (case-insensitive)."""
    present = []
    for name in header:
        present.append(name.strip().lower())

    missing = []
    for column in REQUIRED_COLUMNS:
        if column not in present:
            missing.append(column)
    return missing


def read_csv(file_bytes):
    """Return (rows, error). Each row has a 'row' number, the five required columns and type.

    The error is None when the file can be used. Otherwise the whole file is
    rejected and rows is empty (IR-01). Other columns (such as an old session_id)
    are ignored. A file without a type column gets an empty type, which means Class.
    """
    try:
        # "utf-8-sig" also accepts a BOM, which Excel adds to "CSV UTF-8" files.
        text = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        return [], validation.FILE_NOT_UTF8_ERROR

    try:
        reader = csv.reader(io.StringIO(text))
        all_lines = list(reader)
    except csv.Error:
        return [], validation.FILE_NOT_CSV_ERROR

    if not all_lines:
        header = []
    else:
        header = all_lines[0]

    missing = find_missing_columns(header)
    if missing:
        message = validation.MISSING_COLUMNS_ERROR.format(
            ", ".join(missing), ", ".join(REQUIRED_COLUMNS)
        )
        return [], message

    # Remember which position each column has in this file.
    positions = {}
    for index, name in enumerate(header):
        positions[name.strip().lower()] = index

    rows = []
    row_number = FIRST_DATA_ROW
    for line in all_lines[1:]:
        if is_blank_line(line):
            row_number += 1
            continue

        row = {ROW_COLUMN: row_number}
        for column in FILE_COLUMNS:
            row[column] = ""
            if column in positions and positions[column] < len(line):
                row[column] = line[positions[column]]
        rows.append(row)
        row_number += 1

    return rows, None


def is_blank_line(line):
    """Return True if every cell of a CSV line is empty."""
    for cell in line:
        if cell.strip() != "":
            return False
    return True


# ---------- Step 2a: auto-fixes (FR-31) ----------

def describe_fix(before, after, main_why):
    """Return why a value changed: extra spaces, capitals, or main_why for anything else."""
    whys = []
    trimmed = " ".join(before.split())
    if trimmed != before:
        whys.append(validation.FIX_SPACES)

    if trimmed == after:
        pass
    elif trimmed.casefold() == after.casefold():
        whys.append(validation.FIX_CAPITALS)
    else:
        whys.append(main_why)
    return " ".join(whys)


def fix_student_id(value):
    """Return (fixed ID, why). '4' and '04' become '004'; '0', '00' and '12A' are not fixed."""
    return validation.pad_student_id(value), validation.FIX_STUDENT_ID


def fix_full_name(value):
    """Return (fixed name, why). Only spaces and apostrophes change, never the letters."""
    if "’" in value:
        return validation.clean_name(value), validation.FIX_APOSTROPHE
    return validation.clean_name(value), validation.FIX_SPACES


def fix_course_code(value):
    """Return (fixed code, why). A code that is still invalid is left as it was."""
    return validation.normalize_course_code(value), validation.FIX_CAPITALS


def fix_date(value):
    """Return (fixed date, why). D/M/YYYY and YYYY-MM-DD become DD/MM/YYYY (BR-23).

    DD/MM/YYYY is the normal form of the file, so it is not a fix; clean_row stores
    every date as YYYY-MM-DD later.
    """
    stored = validation.parse_date(value)
    if stored is None:
        stored = validation.parse_short_date(value)
    if stored is None:
        return None, validation.FIX_DATE
    return validation.format_date(stored), validation.FIX_DATE


def fix_type(value):
    """Return (fixed type, why). 'tut', 'tutorial' and 'class' in any case are fixed.

    An empty type stays empty; it already means Class.
    """
    if value.strip() == "":
        return value, validation.FIX_TYPE
    return validation.normalize_session_type(value), validation.FIX_TYPE


def fix_status(value):
    """Return (fixed status, why). P/L/E/A and full words in any case are fixed."""
    return validation.normalize_status(value), validation.FIX_STATUS


FIXERS = [
    ("course_code", fix_course_code),
    ("date", fix_date),
    ("student_id", fix_student_id),
    ("full_name", fix_full_name),
    ("status", fix_status),
    (TYPE_COLUMN, fix_type),
]


def auto_fix_row(raw_row):
    """Return (fixed row, fixes) for one row of the file (FR-31).

    Each fix is a dict with the row, the column, the value before and after, and why.
    A value that cannot be fixed is left as it was, so it is rejected later with
    the original text in its reason.
    """
    fixed_row = dict(raw_row)
    fixes = []
    for column, fixer in FIXERS:
        before = raw_row[column]
        after, main_why = fixer(before)
        if after is None or after == before:
            continue
        fixed_row[column] = after
        fixes.append({
            ROW_COLUMN: raw_row[ROW_COLUMN],
            "column": column,
            "before": before,
            "after": after,
            "why": describe_fix(before, after, main_why),
        })
    return fixed_row, fixes


# ---------- Step 2b: validate the rows ----------

def make_reason(row_number, message):
    """Return a reason like 'Row 7: Invalid student ID. ...'."""
    return f"Row {row_number}: {message}"


def make_format_reason(row_number, message, value):
    """Return a reason for a badly formatted value, quoting what the file contained."""
    return f'Row {row_number}: {message} Got "{value}".'


def clean_row(raw_row):
    """Check BR-01 to BR-07 and BR-23 for one row. Return (cleaned row, None) or (None, reason).

    The cleaned date is stored as 'YYYY-MM-DD'. The session_id is found later.
    """
    row_number = raw_row[ROW_COLUMN]

    raw_student_id = raw_row["student_id"]
    student_id = raw_student_id.strip()
    if not validation.is_valid_student_id(student_id):
        message = validation.STUDENT_ID_ERROR
        return None, make_format_reason(row_number, message, raw_student_id)

    full_name = validation.clean_name(raw_row["full_name"])
    if not validation.is_valid_name(full_name):
        message = validation.NAME_ERROR
        return None, make_format_reason(row_number, message, raw_row["full_name"])

    course_code = validation.normalize_course_code(raw_row["course_code"])
    if course_code is None:
        message = validation.COURSE_CODE_ERROR
        return None, make_format_reason(row_number, message, raw_row["course_code"])

    session_date = validation.parse_date(raw_row["date"])
    if session_date is None:
        message = validation.DATE_ERROR
        return None, make_format_reason(row_number, message, raw_row["date"])

    session_type = validation.normalize_session_type(raw_row[TYPE_COLUMN])
    if session_type is None:
        message = validation.TYPE_ERROR
        return None, make_format_reason(row_number, message, raw_row[TYPE_COLUMN])

    status = validation.normalize_status(raw_row["status"])
    if status is None:
        message = validation.STATUS_ERROR
        return None, make_format_reason(row_number, message, raw_row["status"])

    cleaned = {
        ROW_COLUMN: row_number,
        "course_code": course_code,
        "date": session_date,
        "student_id": student_id,
        "full_name": full_name,
        "status": status,
        TYPE_COLUMN: session_type,
        "session_id": None,
    }
    return cleaned, None


# ---------- Step 2c: suggestions (FR-31) ----------

def is_similar_name(first_name, second_name):
    """Return True if two names are at least 80% alike, ignoring case (S1)."""
    ratio = difflib.SequenceMatcher(None, first_name.casefold(), second_name.casefold()).ratio()
    return ratio >= SIMILAR_NAME_RATIO


def find_next_free_id(taken_ids):
    """Return the lowest 3-digit student ID that is not taken, or None if all are."""
    for number in range(1, 1000):
        student_id = f"{number:03d}"
        if student_id not in taken_ids:
            return student_id
    return None


def propose_new_id(new_ids, student_id, full_name):
    """Return the proposed new ID for a (file ID, name) pair (S2, S3).

    new_ids has 'taken' (saved IDs, IDs in the file and IDs already proposed) and
    'proposals'. The same pair always gets the same ID, so every row of that
    student moves together.
    """
    key = (student_id, full_name.casefold())
    if key not in new_ids["proposals"]:
        new_id = find_next_free_id(new_ids["taken"])
        if new_id is None:
            return None
        new_ids["proposals"][key] = new_id
        new_ids["taken"].add(new_id)
    return new_ids["proposals"][key]


def make_suggestion(row, kind, text, keep_text=None):
    """Return a suggestion for one row. keep_text is the default choice of S4."""
    return {
        "key": f"{row[ROW_COLUMN]}-{kind}",
        ROW_COLUMN: row[ROW_COLUMN],
        "kind": kind,
        "student_id": row["student_id"],
        "full_name": row["full_name"],
        "text": text,
        "keep_text": keep_text,
        "accepted": False,
    }


def check_student(connection, row, file_students, new_ids, accepted_keys):
    """Check the student ID and name (IR-04). Return (reason, suggestion).

    S1: a saved ID with a similar name may use the saved name.
    S2: a saved ID with a different name may move to the next free ID.
    S3: a new ID already used in this file with another name: the later name may
    move to the next free ID. An accepted suggestion changes the row and the reason
    is None; otherwise the row is rejected and the reason mentions the suggestion.
    """
    student_id = row["student_id"]
    full_name = row["full_name"]
    saved_student = database.get_student(connection, student_id)

    if saved_student is not None:
        saved_name = saved_student["full_name"]
        if saved_name.casefold() == full_name.casefold():
            return None, None
        message = validation.NAME_CONFLICT_SAVED_ERROR.format(student_id, saved_name, full_name)
        if is_similar_name(saved_name, full_name):
            text = validation.USE_SAVED_NAME_SUGGESTION.format(saved_name)
            suggestion = make_suggestion(row, "S1", text)
            change = ("full_name", saved_name)
        else:
            suggestion = None
            kind = "S2"
    elif student_id in file_students:
        first_name, first_row = file_students[student_id]
        if first_name.casefold() == full_name.casefold():
            return None, None
        message = validation.NAME_CONFLICT_FILE_ERROR.format(
            student_id, first_row, first_name, full_name
        )
        suggestion = None
        kind = "S3"
    else:
        return None, None

    if suggestion is None:
        new_id = propose_new_id(new_ids, student_id, full_name)
        if new_id is None:
            return make_reason(row[ROW_COLUMN], message), None
        text = validation.NEW_ID_SUGGESTION.format(new_id)
        suggestion = make_suggestion(row, kind, text)
        change = ("student_id", new_id)

    if suggestion["key"] in accepted_keys:
        suggestion["accepted"] = True
        column, value = change
        row[column] = value
        return None, suggestion

    message += validation.SUGGESTION_REASON.format(text)
    return make_reason(row[ROW_COLUMN], message), suggestion


def check_course_period(connection, row):
    """Return a reason if the row's date is outside its course's dates (BR-16)."""
    course = database.get_course(connection, row["course_code"])
    start_date = course["start_date"]
    end_date = course["end_date"]

    if validation.is_date_in_period(row["date"], start_date, end_date):
        return None

    message = validation.ROW_OUTSIDE_COURSE_ERROR.format(
        row["course_code"],
        validation.describe_course_period(start_date, end_date),
        validation.format_date(row["date"]),
    )
    return make_reason(row[ROW_COLUMN], message)


def is_removed_class_day(connection, course_code, session_date):
    """Return True if a weekday has no class although the course's class days were generated.

    A course with dates got a class day on every weekday (BR-20), so a missing one was
    removed (for example a holiday). A course without dates is an older course whose
    class days were added by hand, so nothing can be said about a missing day.
    """
    if validation.weekday_name(session_date) in WEEKEND_DAYS:
        return False
    course = database.get_course(connection, course_code)
    return course["start_date"] is not None and course["end_date"] is not None


def find_session(connection, row, file_tutorials, accepted_keys=()):
    """Set row['session_id'] to the class day or tutorial of the row. Return (reason, suggestion).

    Class (IR-12): the course must have a class on that date; a weekend or a removed
    day has none, and gets suggestion S5 "Import as tutorial on that date" (Stage 7).
    Tutorial (IR-13): the first tutorial on that date is used; if there is none, a new
    tutorial ID is planned, and later rows for the same date share it.
    """
    course_code = row["course_code"]
    session_date = row["date"]
    suggestion = None

    if row[TYPE_COLUMN] == validation.CLASS:
        class_session = database.get_class_session(connection, course_code, session_date)
        if class_session is not None:
            row["session_id"] = class_session["session_id"]
            return None, None

        removed = is_removed_class_day(connection, course_code, session_date)
        weekend = validation.weekday_name(session_date) in WEEKEND_DAYS
        message = validation.NO_CLASS_ERROR
        if removed:
            message = validation.CLASS_DAY_REMOVED_ERROR
        message = message.format(
            course_code,
            validation.weekday_name(session_date),
            validation.format_date(session_date),
        )
        if not removed and not weekend:
            return make_reason(row[ROW_COLUMN], message), None

        suggestion = make_suggestion(row, "S5", validation.TUTORIAL_SUGGESTION)
        if suggestion["key"] not in accepted_keys:
            message += validation.SUGGESTION_REASON.format(suggestion["text"])
            return make_reason(row[ROW_COLUMN], message), suggestion
        suggestion["accepted"] = True
        row[TYPE_COLUMN] = validation.TUTORIAL

    tutorials = database.get_tutorials_on_date(connection, course_code, session_date)
    if tutorials:
        row["session_id"] = tutorials[0]["session_id"]
        return None, suggestion

    key = (course_code, session_date)
    if key not in file_tutorials:
        planned_ids = list(file_tutorials.values())
        file_tutorials[key] = database.next_tutorial_id(
            connection, course_code, session_date, planned_ids
        )
    row["session_id"] = file_tutorials[key]
    return None, suggestion


def describe_row_session(row):
    """Return the row's session without its ID, like 'PY101 on Tuesday 08/09/2026 (Class)'."""
    session_type = validation.CLASS
    if row[TYPE_COLUMN] == validation.TUTORIAL:
        session_type = f"Tutorial {row['session_id'].split('-')[-1]}"
    return (
        f"{row['course_code']} on {validation.weekday_name(row['date'])} "
        f"{validation.format_date(row['date'])} ({session_type})"
    )


def check_enrollment_dates(connection, row):
    """Return a reason if the row's date is outside an existing enrollment (BR-15), else None.

    A student who is not enrolled yet gets a new enrollment at Confirm, so there is
    nothing to check for them.
    """
    student_id = row["student_id"]
    course_code = row["course_code"]
    session_date = row["date"]

    enrollment = database.get_enrollment(connection, student_id, course_code)
    if enrollment is None:
        return None

    start_date = enrollment["start_date"]
    end_date = enrollment["end_date"]
    if validation.is_in_enrollment_window(session_date, start_date, end_date):
        return None

    if start_date is not None and session_date < start_date:
        message = validation.ENROLLED_FROM_ERROR.format(
            student_id, course_code,
            validation.format_date(start_date), validation.format_date(session_date),
        )
    else:
        message = validation.ENROLLED_UNTIL_ERROR.format(
            student_id, course_code,
            validation.format_date(end_date), validation.format_date(session_date),
        )
    return make_reason(row[ROW_COLUMN], message)


def check_status(connection, row, file_statuses, accepted_keys):
    """Compare the row with saved and earlier records for the same student and session.

    Returns (result, reason, suggestion). The result is 'new', 'duplicate' (IR-07),
    'conflict' (IR-08) or 'update'. A status that differs from the saved record gets
    suggestion S4: 'Keep saved' is the default (the row is rejected), and an accepted
    'Use file' makes the result 'update', so Confirm changes the saved record.
    """
    student_id = row["student_id"]
    session_id = row["session_id"]
    status = row["status"]

    saved_status = database.get_status(connection, student_id, session_id)
    if saved_status is not None:
        if saved_status == status:
            reason = make_reason(row[ROW_COLUMN], validation.DUPLICATE_SAVED_REASON)
            return "duplicate", reason, None
        text = validation.USE_FILE_STATUS_CHOICE.format(status)
        keep_text = validation.KEEP_SAVED_STATUS_CHOICE.format(saved_status)
        suggestion = make_suggestion(row, "S4", text, keep_text)
        if suggestion["key"] in accepted_keys:
            suggestion["accepted"] = True
            return "update", None, suggestion
        message = validation.STATUS_CONFLICT_SAVED_ERROR.format(
            student_id, saved_status, describe_row_session(row), status
        )
        message += validation.SUGGESTION_REASON.format(text)
        return "conflict", make_reason(row[ROW_COLUMN], message), suggestion

    pair = (student_id, session_id)
    if pair in file_statuses:
        first_status, first_row = file_statuses[pair]
        if first_status == status:
            message = validation.DUPLICATE_FILE_REASON.format(first_row)
            return "duplicate", make_reason(row[ROW_COLUMN], message), None
        message = validation.STATUS_CONFLICT_FILE_ERROR.format(
            student_id, first_status, describe_row_session(row), first_row, status
        )
        return "conflict", make_reason(row[ROW_COLUMN], message), None

    return "new", None, None


def reject(raw_row, reason):
    """Return a copy of the original row with the reason added."""
    rejected_row = dict(raw_row)
    rejected_row[REASON_COLUMN] = reason
    return rejected_row


def find_taken_ids(connection, fixed_rows):
    """Return the saved student IDs and every valid student ID in the file."""
    taken_ids = set()
    for student in database.get_all_students(connection):
        taken_ids.add(student["student_id"])
    for row in fixed_rows:
        student_id = row["student_id"].strip()
        if validation.is_valid_student_id(student_id):
            taken_ids.add(student_id)
    return taken_ids


def apply_edits(rows, edits):
    """Return (rows with the user's edits, the list of edits) (Stage 7).

    edits maps a row number to {column: new value}, typed in the Rejected table. Each
    edit is listed like an auto-fix, with why 'edited by you: before -> after'. An edit
    equal to the file's value is not a change and is not listed.
    """
    edited_rows = []
    edit_list = []
    for row in rows:
        row_edits = edits.get(row[ROW_COLUMN], {})
        edited = dict(row)
        for column in FILE_COLUMNS:
            if column not in row_edits or row_edits[column] == row[column]:
                continue
            edited[column] = row_edits[column]
            edit_list.append({
                ROW_COLUMN: row[ROW_COLUMN],
                "column": column,
                "before": row[column],
                "after": row_edits[column],
                "why": validation.EDITED_BY_YOU.format(row[column], row_edits[column]),
            })
        edited_rows.append(edited)
    return edited_rows, edit_list


def clean_cell(value):
    """Return a table cell as text; an empty cell (None or NaN) becomes ''."""
    if value is None or (isinstance(value, float) and value != value):
        return ""
    return str(value)


def collect_edits(edits, shown_rows, edited_rows):
    """Return the edits merged with the cells changed in the Rejected table (Stage 7).

    edits maps a row number to {column: value}. shown_rows are the rejected rows as
    they were shown, edited_rows the same rows after the user typed; both are lists
    of dicts with 'row' and the file columns. Earlier edits are kept.
    """
    merged = {}
    for row_number, row_edits in edits.items():
        merged[row_number] = dict(row_edits)

    for shown, edited in zip(shown_rows, edited_rows):
        row_number = int(shown[ROW_COLUMN])
        for column in FILE_COLUMNS:
            new_value = clean_cell(edited[column])
            if new_value != clean_cell(shown[column]):
                merged.setdefault(row_number, {})[column] = new_value
    return merged


def review_rows(connection, rows, accepted_keys=(), edits=None):
    """Auto-fix, validate and suggest fixes for the rows, without writing (FR-31, IR-09).

    accepted_keys holds the keys of the suggestions the user accepted; edits holds the
    values typed in the Rejected table (see apply_edits, Stage 7). Returns a dict:
    'edits', 'fixes' (every auto-fix), 'suggestions' (with 'accepted' set), and the
    'accepted', 'duplicates' and 'rejected' rows. Rejected rows show the values after
    the edits. Accepted rows that change a saved status have 'update' set to True.
    """
    accepted_keys = set(accepted_keys)
    rows, edit_list = apply_edits(rows, edits or {})
    fixes = []
    fixed_rows = []
    for raw_row in rows:
        fixed_row, row_fixes = auto_fix_row(raw_row)
        fixed_rows.append(fixed_row)
        fixes.extend(row_fixes)

    result = {
        "edits": edit_list,
        "fixes": fixes,
        "suggestions": [],
        "accepted": [],
        "duplicates": [],
        "rejected": [],
    }

    # What the accepted rows of this file say so far.
    file_students = {}    # student_id -> (full_name, row number)
    file_tutorials = {}   # (course_code, date) -> planned new tutorial ID
    file_statuses = {}    # (student_id, session_id) -> (status, row number)
    new_ids = {"taken": find_taken_ids(connection, fixed_rows), "proposals": {}}

    for raw_row, fixed_row in zip(rows, fixed_rows):
        row, reason = clean_row(fixed_row)
        if row is None:
            result["rejected"].append(reject(raw_row, reason))
            continue

        if not database.course_exists(connection, row["course_code"]):
            message = validation.UNKNOWN_COURSE_ERROR.format(row["course_code"])
            result["rejected"].append(reject(raw_row, make_reason(row[ROW_COLUMN], message)))
            continue

        reason = check_course_period(connection, row)
        if reason is None:
            reason, suggestion = find_session(connection, row, file_tutorials, accepted_keys)
            if suggestion is not None:
                result["suggestions"].append(suggestion)
        if reason is None:
            reason, suggestion = check_student(
                connection, row, file_students, new_ids, accepted_keys
            )
            if suggestion is not None:
                result["suggestions"].append(suggestion)
        if reason is None:
            reason = check_enrollment_dates(connection, row)
        if reason is not None:
            result["rejected"].append(reject(raw_row, reason))
            continue

        status_result, reason, suggestion = check_status(
            connection, row, file_statuses, accepted_keys
        )
        if suggestion is not None:
            result["suggestions"].append(suggestion)
        if status_result == "conflict":
            result["rejected"].append(reject(raw_row, reason))
            continue
        if status_result == "duplicate":
            result["duplicates"].append(reject(row, reason))
            continue

        row["update"] = status_result == "update"
        result["accepted"].append(row)
        row_number = row[ROW_COLUMN]
        if row["student_id"] not in file_students:
            file_students[row["student_id"]] = (row["full_name"], row_number)
        file_statuses[(row["student_id"], row["session_id"])] = (row["status"], row_number)

    return result


def validate_rows(connection, rows, accepted_keys=()):
    """Sort rows into (accepted, duplicates, rejected) without writing to the database.

    Earlier rows of the file count too: if a new student appears twice with
    different names, the first row is kept and the later one is rejected unless
    its suggestion is accepted.
    """
    result = review_rows(connection, rows, accepted_keys)
    return result["accepted"], result["duplicates"], result["rejected"]


def count_accepted_suggestions(suggestions):
    """Return how many suggestions were accepted."""
    count = 0
    for suggestion in suggestions:
        if suggestion["accepted"]:
            count += 1
    return count


# ---------- Step 3: save after Confirm ----------

def find_enrollment_starts(accepted):
    """Return the earliest date per (student_id, course_code) in the accepted rows.

    A new enrollment created by the import starts on that date (BR-15), so the
    student is not expected at the course's earlier sessions.
    """
    starts = {}
    for row in accepted:
        key = (row["student_id"], row["course_code"])
        if key not in starts or row["date"] < starts[key]:
            starts[key] = row["date"]
    return starts


def apply_import(connection, accepted, filename):
    """Save the accepted rows in one transaction, with the filename as source (IR-10).

    Rows with an accepted 'Use file' choice (S4) update the saved record.
    """
    enrollment_starts = find_enrollment_starts(accepted)
    return database.import_records(connection, accepted, filename, enrollment_starts)


# ---------- Tables and downloads ----------

def make_table(rows, with_reason):
    """Return the rows as a DataFrame with the row number first and an optional reason."""
    columns = [ROW_COLUMN] + FILE_COLUMNS
    if with_reason:
        columns.append(REASON_COLUMN)
    return pd.DataFrame(rows, columns=columns)


def make_template_csv():
    """Return an empty CSV template with the required columns and the optional type (FR-11)."""
    return ",".join(FILE_COLUMNS) + "\n"


def make_fixes_table(fixes):
    """Return the auto-fixes as a DataFrame: row, column, before, after, why (FR-31)."""
    return pd.DataFrame(fixes, columns=FIX_COLUMNS)


def make_cleaned_csv(accepted, duplicates):
    """Return every valid row after fixes and accepted suggestions as CSV text (FR-31).

    Accepted rows and duplicates are listed in file order, in the Version 3 columns,
    with dates as DD/MM/YYYY (BR-23), so importing the cleaned file again needs no
    auto-fixes. Rejected rows are not included.
    """
    rows = sorted(accepted + duplicates, key=lambda row: row[ROW_COLUMN])
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(FILE_COLUMNS)
    for row in rows:
        values = []
        for column in FILE_COLUMNS:
            value = row[column]
            if column == "date":
                value = validation.format_date(value)
            values.append(value)
        writer.writerow(values)
    return output.getvalue()
