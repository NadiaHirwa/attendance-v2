"""CSV import for the attendance system (Section 5, IR-01 to IR-14).

The workflow has three steps that the app calls in order:
1. read_csv() turns the uploaded bytes into rows (IR-01).
2. validate_rows() sorts rows into accepted, duplicates and rejected.
   It finds the class day or tutorial of each row (IR-12, IR-13), and checks the
   course's dates (BR-16) and an existing enrollment's dates (BR-15).
   It reads the database but never writes to it (IR-09).
3. apply_import() saves the accepted rows in one transaction, only after Confirm.
"""

import csv
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


# ---------- Step 2: validate the rows ----------

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


def check_student(connection, row, file_students):
    """Return a conflict reason if the student ID has a different name (IR-04), else None."""
    student_id = row["student_id"]
    full_name = row["full_name"]

    saved_student = database.get_student(connection, student_id)
    if saved_student is not None:
        if saved_student["full_name"].casefold() != full_name.casefold():
            message = validation.NAME_CONFLICT_SAVED_ERROR.format(
                student_id, saved_student["full_name"], full_name
            )
            return make_reason(row[ROW_COLUMN], message)
        return None

    if student_id in file_students:
        first_name, first_row = file_students[student_id]
        if first_name.casefold() != full_name.casefold():
            message = validation.NAME_CONFLICT_FILE_ERROR.format(
                student_id, first_row, first_name, full_name
            )
            return make_reason(row[ROW_COLUMN], message)

    return None


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


def find_session(connection, row, file_tutorials):
    """Set row['session_id'] to the class day or tutorial of the row. Return a reason or None.

    Class (IR-12): the course must have a class on that date; a weekend or a removed
    day has none. Tutorial (IR-13): the first tutorial on that date is used; if there
    is none, a new tutorial ID is planned, and later rows for the same date share it.
    """
    course_code = row["course_code"]
    session_date = row["date"]

    if row[TYPE_COLUMN] == validation.CLASS:
        class_session = database.get_class_session(connection, course_code, session_date)
        if class_session is None:
            message = validation.NO_CLASS_ERROR.format(
                course_code,
                validation.weekday_name(session_date),
                validation.format_date(session_date),
            )
            return make_reason(row[ROW_COLUMN], message)
        row["session_id"] = class_session["session_id"]
        return None

    tutorials = database.get_tutorials_on_date(connection, course_code, session_date)
    if tutorials:
        row["session_id"] = tutorials[0]["session_id"]
        return None

    key = (course_code, session_date)
    if key not in file_tutorials:
        planned_ids = list(file_tutorials.values())
        file_tutorials[key] = database.next_tutorial_id(
            connection, course_code, session_date, planned_ids
        )
    row["session_id"] = file_tutorials[key]
    return None


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


def check_status(connection, row, file_statuses):
    """Compare the row with saved and earlier records for the same student and session.

    Returns (result, reason) where result is 'new', 'duplicate' (IR-07) or 'conflict' (IR-08).
    """
    student_id = row["student_id"]
    session_id = row["session_id"]
    status = row["status"]

    saved_status = database.get_status(connection, student_id, session_id)
    if saved_status is not None:
        if saved_status == status:
            return "duplicate", make_reason(row[ROW_COLUMN], validation.DUPLICATE_SAVED_REASON)
        message = validation.STATUS_CONFLICT_SAVED_ERROR.format(
            student_id, saved_status, session_id, status
        )
        return "conflict", make_reason(row[ROW_COLUMN], message)

    pair = (student_id, session_id)
    if pair in file_statuses:
        first_status, first_row = file_statuses[pair]
        if first_status == status:
            message = validation.DUPLICATE_FILE_REASON.format(first_row)
            return "duplicate", make_reason(row[ROW_COLUMN], message)
        message = validation.STATUS_CONFLICT_FILE_ERROR.format(
            student_id, first_status, session_id, first_row, status
        )
        return "conflict", make_reason(row[ROW_COLUMN], message)

    return "new", None


def reject(raw_row, reason):
    """Return a copy of the original row with the reason added."""
    rejected_row = dict(raw_row)
    rejected_row[REASON_COLUMN] = reason
    return rejected_row


def validate_rows(connection, rows):
    """Sort rows into (accepted, duplicates, rejected) without writing to the database.

    Earlier rows of the file count too: if a new student appears twice with
    different names, the first row is kept and the later one is rejected.
    """
    accepted = []
    duplicates = []
    rejected = []

    # What the accepted rows of this file say so far.
    file_students = {}    # student_id -> (full_name, row number)
    file_tutorials = {}   # (course_code, date) -> planned new tutorial ID
    file_statuses = {}    # (student_id, session_id) -> (status, row number)

    for raw_row in rows:
        row, reason = clean_row(raw_row)
        if row is None:
            rejected.append(reject(raw_row, reason))
            continue

        if not database.course_exists(connection, row["course_code"]):
            message = validation.UNKNOWN_COURSE_ERROR.format(row["course_code"])
            rejected.append(reject(raw_row, make_reason(row[ROW_COLUMN], message)))
            continue

        reason = check_course_period(connection, row)
        if reason is None:
            reason = find_session(connection, row, file_tutorials)
        if reason is None:
            reason = check_student(connection, row, file_students)
        if reason is None:
            reason = check_enrollment_dates(connection, row)
        if reason is not None:
            rejected.append(reject(raw_row, reason))
            continue

        result, reason = check_status(connection, row, file_statuses)
        if result == "conflict":
            rejected.append(reject(raw_row, reason))
            continue
        if result == "duplicate":
            duplicates.append(reject(row, reason))
            continue

        accepted.append(row)
        row_number = row[ROW_COLUMN]
        if row["student_id"] not in file_students:
            file_students[row["student_id"]] = (row["full_name"], row_number)
        file_statuses[(row["student_id"], row["session_id"])] = (row["status"], row_number)

    return accepted, duplicates, rejected


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
    """Save the accepted rows in one transaction, with the filename as source (IR-10)."""
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
