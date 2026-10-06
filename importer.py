"""CSV import for the attendance system (Section 5, IR-01 to IR-11).

The workflow has three steps that the app calls in order:
1. read_csv() turns the uploaded bytes into rows (IR-01).
2. validate_rows() sorts rows into accepted, duplicates and rejected.
   It also checks each row against its course's dates (BR-16) and an existing
   enrollment's dates (BR-15).
   It reads the database but never writes to it (IR-09).
3. apply_import() saves the accepted rows in one transaction, only after Confirm.
"""

import csv
import io

import pandas as pd

import database
import validation

REQUIRED_COLUMNS = [
    "session_id",
    "course_code",
    "session_date",
    "student_id",
    "full_name",
    "status",
]
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
    """Return (rows, error). Each row has a 'row' number and the six required columns.

    The error is None when the file can be used. Otherwise the whole file is
    rejected and rows is empty (IR-01). Extra columns are ignored.
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

    # Remember which position each required column has in this file.
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
        for column in REQUIRED_COLUMNS:
            index = positions[column]
            if index < len(line):
                row[column] = line[index]
            else:
                row[column] = ""
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
    """Check BR-01 to BR-07 for one row. Return (cleaned row, None) or (None, reason)."""
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

    session_id = validation.normalize_session_id(raw_row["session_id"])
    if session_id is None:
        message = validation.SESSION_ID_ERROR
        return None, make_format_reason(row_number, message, raw_row["session_id"])

    session_date = validation.parse_date(raw_row["session_date"])
    if session_date is None:
        message = validation.DATE_ERROR
        return None, make_format_reason(row_number, message, raw_row["session_date"])

    status = validation.normalize_status(raw_row["status"])
    if status is None:
        message = validation.STATUS_ERROR
        return None, make_format_reason(row_number, message, raw_row["status"])

    cleaned = {
        ROW_COLUMN: row_number,
        "session_id": session_id,
        "course_code": course_code,
        "session_date": session_date,
        "student_id": student_id,
        "full_name": full_name,
        "status": status,
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


def check_session(connection, row, file_sessions):
    """Return a conflict reason if the session has a different course or date (IR-05).

    Returns None when there is no conflict.
    """
    session_id = row["session_id"]
    course_code = row["course_code"]
    session_date = row["session_date"]

    saved_session = database.get_session(connection, session_id)
    if saved_session is not None:
        same_course = saved_session["course_code"] == course_code
        same_date = saved_session["session_date"] == session_date
        if not same_course or not same_date:
            message = validation.SESSION_CONFLICT_SAVED_ERROR.format(
                session_id, saved_session["course_code"], saved_session["session_date"],
                course_code, session_date,
            )
            return make_reason(row[ROW_COLUMN], message)
        return None

    if session_id in file_sessions:
        first_course, first_date, first_row = file_sessions[session_id]
        if first_course != course_code or first_date != session_date:
            message = validation.SESSION_CONFLICT_FILE_ERROR.format(
                session_id, first_row, first_course, first_date, course_code, session_date
            )
            return make_reason(row[ROW_COLUMN], message)

    return None


def check_course_period(connection, row):
    """Return a reason if the row's session date is outside its course's dates (BR-16)."""
    course = database.get_course(connection, row["course_code"])
    start_date = course["start_date"]
    end_date = course["end_date"]

    if validation.is_date_in_period(row["session_date"], start_date, end_date):
        return None

    message = validation.ROW_OUTSIDE_COURSE_ERROR.format(
        row["course_code"],
        validation.describe_course_period(start_date, end_date),
        row["session_date"],
    )
    return make_reason(row[ROW_COLUMN], message)


def check_enrollment_dates(connection, row):
    """Return a reason if the row's date is outside an existing enrollment (BR-15), else None.

    A student who is not enrolled yet gets a new enrollment at Confirm, so there is
    nothing to check for them.
    """
    student_id = row["student_id"]
    course_code = row["course_code"]
    session_date = row["session_date"]

    enrollment = database.get_enrollment(connection, student_id, course_code)
    if enrollment is None:
        return None

    start_date = enrollment["start_date"]
    end_date = enrollment["end_date"]
    if validation.is_in_enrollment_window(session_date, start_date, end_date):
        return None

    if start_date is not None and session_date < start_date:
        message = validation.ENROLLED_FROM_ERROR.format(
            student_id, course_code, start_date, session_date
        )
    else:
        message = validation.ENROLLED_UNTIL_ERROR.format(
            student_id, course_code, end_date, session_date
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

    Earlier rows of the file count too: if a new student or session appears twice
    with different details, the first row is kept and the later one is rejected.
    """
    accepted = []
    duplicates = []
    rejected = []

    # What the accepted rows of this file say so far.
    file_students = {}   # student_id -> (full_name, row number)
    file_sessions = {}   # session_id -> (course_code, session_date, row number)
    file_statuses = {}   # (student_id, session_id) -> (status, row number)

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
            reason = check_student(connection, row, file_students)
        if reason is None:
            reason = check_session(connection, row, file_sessions)
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
        if row["session_id"] not in file_sessions:
            session_details = (row["course_code"], row["session_date"], row_number)
            file_sessions[row["session_id"]] = session_details
        file_statuses[(row["student_id"], row["session_id"])] = (row["status"], row_number)

    return accepted, duplicates, rejected


# ---------- Step 3: save after Confirm ----------

def find_enrollment_starts(accepted):
    """Return the earliest session date per (student_id, course_code) in the accepted rows.

    A new enrollment created by the import starts on that date (BR-15), so the
    student is not expected at the course's earlier sessions.
    """
    starts = {}
    for row in accepted:
        key = (row["student_id"], row["course_code"])
        if key not in starts or row["session_date"] < starts[key]:
            starts[key] = row["session_date"]
    return starts


def apply_import(connection, accepted, filename):
    """Save the accepted rows in one transaction, with the filename as source (IR-10)."""
    enrollment_starts = find_enrollment_starts(accepted)
    return database.import_records(connection, accepted, filename, enrollment_starts)


# ---------- Tables and downloads ----------

def make_table(rows, with_reason):
    """Return the rows as a DataFrame with the row number first and an optional reason."""
    columns = [ROW_COLUMN] + REQUIRED_COLUMNS
    if with_reason:
        columns.append(REASON_COLUMN)
    return pd.DataFrame(rows, columns=columns)


def make_template_csv():
    """Return an empty CSV template with only the required header (FR-11)."""
    return ",".join(REQUIRED_COLUMNS) + "\n"
