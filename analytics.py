"""Attendance calculations (BR-10 to BR-12).

Functions return numbers and DataFrames only. They never print and
never use Streamlit, so every calculation can be tested.
"""

import pandas as pd

import validation

PRESENT = "Present"
LATE = "Late"
EXCUSED = "Excused"
ABSENT = "Absent"
UNKNOWN = "Unknown"
# The count columns of every summary table, in this order (FR-26).
COUNT_COLUMNS = [PRESENT, LATE, EXCUSED, ABSENT, UNKNOWN]
NOT_AVAILABLE = "N/A"
ALL_COURSES = "All courses"
DEFAULT_THRESHOLD = 75
CHART_VALUE_COLUMN = "Attendance rate (%)"
CHART_LABEL_COLUMN = "Session"
CHART_COURSE_COLUMN = "Course"
CHART_STATUS_COLUMN = "Status"
CHART_COUNT_COLUMN = "Students"
CHART_ORDER_COLUMN = "Stack order"
DEFAULT_STREAK_ALERT = 2
# Deduction columns (BR-22, FR-29). The deductions themselves are settings.
DEDUCTED_COLUMN = "Deducted marks"
# The count of missing records in the deductions export, and the flag on screens.
NOT_RECORDED_COLUMN = "Not recorded"
NOT_RECORDED_FLAG_COLUMN = "Note"
# Columns that hold dates in the tables shown on screen and downloaded (BR-23).
DATE_COLUMNS = ["Date", "Enrolled from", "Enrolled until", "Last absence", "date",
                "Start date", "End date"]
CURRENT_STREAK_COLUMN = "Current absence streak"
LONGEST_STREAK_COLUMN = "Longest absence streak"
LAST_ABSENCE_COLUMN = "Last absence"
# Order of the parts of each stacked bar, from the bottom up.
STATUS_ORDER = [PRESENT, LATE, EXCUSED, ABSENT, UNKNOWN]

RECORD_COLUMNS = [
    "student_id",
    "full_name",
    "course_code",
    "session_id",
    "session_date",
    "status",
]
ENROLLMENT_COLUMNS = ["enrollment_start", "enrollment_end"]
ENROLLED_FROM_COLUMN = "Enrolled from"
ENROLLED_UNTIL_COLUMN = "Enrolled until"
# Shown instead of an empty date (BR-15).
NO_START_TEXT = "start"
NO_END_TEXT = "now"


def calculate_rates(present, late, excused, absent, unknown):
    """Return the counts, attendance rate and completeness for one group.

    Attendance rate = (Present + Late) / (Present + Late + Absent) x 100 (BR-10).
    Excused is not in the rate: the student was not expected to come.
    Completeness = (Present + Late + Excused + Absent) / Expected x 100 (BR-11).
    A rate is None when its denominator is 0, so there is no division error.
    """
    attended = present + late
    counted_in_rate = present + late + absent
    recorded = present + late + excused + absent
    expected = recorded + unknown

    if counted_in_rate == 0:
        attendance_rate = None
    else:
        attendance_rate = round(attended / counted_in_rate * 100, 2)

    if expected == 0:
        completeness = None
    else:
        completeness = round(recorded / expected * 100, 2)

    return {
        "present": present,
        "late": late,
        "excused": excused,
        "absent": absent,
        "unknown": unknown,
        "expected": expected,
        "attendance_rate": attendance_rate,
        "completeness": completeness,
    }


def format_rate(rate):
    """Return a rate as text like '77.78%', or 'N/A' when it is None."""
    if rate is None or pd.isna(rate):
        return NOT_AVAILABLE
    return f"{rate:.2f}%"


def build_records_frame(records):
    """Turn expected records from the database into a DataFrame.

    A missing status becomes 'Unknown'. It is computed here, never stored (BR-12).
    The enrollment dates are kept for the student report (FR-24).
    """
    frame = pd.DataFrame(records, columns=RECORD_COLUMNS + ENROLLMENT_COLUMNS)
    frame["status"] = frame["status"].fillna(UNKNOWN)
    return frame


def count_statuses(frame):
    """Return the number of Present, Late, Excused, Absent and Unknown rows."""
    present = int((frame["status"] == PRESENT).sum())
    late = int((frame["status"] == LATE).sum())
    excused = int((frame["status"] == EXCUSED).sum())
    absent = int((frame["status"] == ABSENT).sum())
    unknown = int((frame["status"] == UNKNOWN).sum())
    return present, late, excused, absent, unknown


def summarize_frame(frame):
    """Return calculate_rates() for all rows of a records frame."""
    present, late, excused, absent, unknown = count_statuses(frame)
    return calculate_rates(present, late, excused, absent, unknown)


def build_summary_row(labels, group):
    """Return one summary row: the group's labels plus its counts and rates."""
    rates = summarize_frame(group)
    row = dict(labels)
    row[PRESENT] = rates["present"]
    row[LATE] = rates["late"]
    row[EXCUSED] = rates["excused"]
    row[ABSENT] = rates["absent"]
    row[UNKNOWN] = rates["unknown"]
    row["attendance_rate"] = rates["attendance_rate"]
    row["completeness"] = rates["completeness"]
    return row


def build_student_summary(frame):
    """Return one row per student with the five counts, rate and completeness."""
    columns = (
        ["student_id", "full_name"] + COUNT_COLUMNS + ["attendance_rate", "completeness"]
    )
    rows = []

    for student_id, group in frame.groupby("student_id", sort=True):
        labels = {
            "student_id": student_id,
            "full_name": group["full_name"].iloc[0],
        }
        rows.append(build_summary_row(labels, group))

    return pd.DataFrame(rows, columns=columns)


def build_session_summary(frame):
    """Return one row per session in date order, with counts and rates."""
    columns = (
        ["session_id", "course_code", "session_date"] + COUNT_COLUMNS
        + ["attendance_rate", "completeness"]
    )
    rows = []

    for session_id, group in frame.groupby("session_id"):
        labels = {
            "session_id": session_id,
            "course_code": group["course_code"].iloc[0],
            "session_date": group["session_date"].iloc[0],
        }
        rows.append(build_summary_row(labels, group))

    summary = pd.DataFrame(rows, columns=columns)
    return summary.sort_values(["session_date", "session_id"], ignore_index=True)


# ---------- Filters (FR-12) ----------

def get_date_bounds(frame):
    """Return the earliest and latest session dates as text, or (None, None) if there are none."""
    if frame.empty:
        return None, None
    return frame["session_date"].min(), frame["session_date"].max()


def get_default_date_range(frame, course_code, course_start, course_end):
    """Return the default (start, end) of the date filter (FR-12, FR-25).

    For All courses: the earliest and latest session dates.
    For one course: the course's start and end dates; a side with no date uses that
    course's session dates, and if it has none either, all sessions' dates.
    """
    earliest, latest = get_date_bounds(frame)
    if course_code == ALL_COURSES:
        return earliest, latest

    course_frame = frame[frame["course_code"] == course_code]
    course_earliest, course_latest = get_date_bounds(course_frame)

    start = course_start
    if start is None:
        start = course_earliest
    if start is None:
        start = earliest

    end = course_end
    if end is None:
        end = course_latest
    if end is None:
        end = latest

    return start, end


def filter_records(frame, course_code, start_date, end_date):
    """Return the rows for one course (or all courses) between two dates, both included.

    Dates are 'YYYY-MM-DD' text, so comparing the text also compares the dates.
    """
    keep = (frame["session_date"] >= start_date) & (frame["session_date"] <= end_date)

    if course_code != ALL_COURSES:
        keep = keep & (frame["course_code"] == course_code)

    return frame[keep].reset_index(drop=True)


# ---------- Dashboard (FR-13 to FR-15) ----------

def calculate_dashboard_metrics(frame):
    """Return the number of students and sessions plus the counts and rates."""
    metrics = summarize_frame(frame)
    metrics["students"] = frame["student_id"].nunique()
    metrics["sessions"] = frame["session_id"].nunique()
    return metrics


def make_session_label(session_date, session_id, include_year):
    """Return a short chart label like '07/09 PY101' or '10/09 PY101-T1' (BR-23).

    A generated session ID already contains the date ('PY101-2026-09-07'), so the
    date is taken out of it to keep the label short. With include_year, the date is
    shown in full: '07/09/2026 PY101'.
    """
    short_id = session_id.replace("-" + session_date, "")
    display_date = validation.format_date(session_date)
    if not include_year:
        # 'DD/MM/YYYY'[:5] keeps only 'DD/MM'.
        display_date = display_date[:5]
    return f"{display_date} {short_id}"


def labels_need_year(session_summary):
    """Return True if the sessions are in more than one year, so labels must show the year."""
    # The first 4 characters of 'YYYY-MM-DD' are the year.
    first_year = session_summary["session_date"].min()[:4]
    last_year = session_summary["session_date"].max()[:4]
    return first_year != last_year


def build_rate_chart_data(frame):
    """Return one row per session (label, course, rate) in date order for the chart (FR-14).

    Sessions on the same date are ordered by session ID.
    Sessions with no recorded status have no rate, so they are left out.
    Labels show the year only when the sessions are in more than one year.
    """
    columns = [CHART_LABEL_COLUMN, CHART_COURSE_COLUMN, CHART_VALUE_COLUMN]
    session_summary = build_session_summary(frame)
    if session_summary.empty:
        return pd.DataFrame(columns=columns)

    include_year = labels_need_year(session_summary)
    rows = []
    for index, row in session_summary.iterrows():
        if pd.isna(row["attendance_rate"]):
            continue
        label = make_session_label(row["session_date"], row["session_id"], include_year)
        rows.append({
            CHART_LABEL_COLUMN: label,
            CHART_COURSE_COLUMN: row["course_code"],
            CHART_VALUE_COLUMN: row["attendance_rate"],
        })

    return pd.DataFrame(rows, columns=columns)


def build_status_chart_data(frame):
    """Return one row per session (label, course and the five counts) in date order (FR-20).

    Uses the same labels and order as build_rate_chart_data(). Sessions where
    nothing was recorded are kept: their whole bar is Unknown.
    """
    columns = [CHART_LABEL_COLUMN, CHART_COURSE_COLUMN] + STATUS_ORDER
    session_summary = build_session_summary(frame)
    if session_summary.empty:
        return pd.DataFrame(columns=columns)

    include_year = labels_need_year(session_summary)
    rows = []
    for index, row in session_summary.iterrows():
        label = make_session_label(row["session_date"], row["session_id"], include_year)
        chart_row = {
            CHART_LABEL_COLUMN: label,
            CHART_COURSE_COLUMN: row["course_code"],
        }
        for status in STATUS_ORDER:
            chart_row[status] = row[status]
        rows.append(chart_row)

    return pd.DataFrame(rows, columns=columns)


def make_status_chart_long(status_chart_data):
    """Return one row per session and status, the shape a stacked bar chart needs (FR-20).

    The 'Stack order' column puts Present at the bottom, then Absent, then Unknown on top.
    """
    rows = []
    for index, row in status_chart_data.iterrows():
        for position, status in enumerate(STATUS_ORDER):
            rows.append({
                CHART_LABEL_COLUMN: row[CHART_LABEL_COLUMN],
                CHART_STATUS_COLUMN: status,
                CHART_COUNT_COLUMN: row[status],
                CHART_ORDER_COLUMN: position,
            })

    columns = [CHART_LABEL_COLUMN, CHART_STATUS_COLUMN, CHART_COUNT_COLUMN, CHART_ORDER_COLUMN]
    return pd.DataFrame(rows, columns=columns)


def keep_statuses(status_chart_long, statuses):
    """Return only the rows of the long status chart table whose status is in statuses."""
    keep = status_chart_long[CHART_STATUS_COLUMN].isin(statuses)
    return status_chart_long[keep].reset_index(drop=True)


def split_by_threshold(student_summary, threshold):
    """Return (students below the threshold sorted by rate, students with no rate) (FR-15)."""
    has_rate = student_summary["attendance_rate"].notna()

    with_rate = student_summary[has_rate]
    below = with_rate[with_rate["attendance_rate"] < threshold]
    below = below.sort_values(["attendance_rate", "student_id"], ignore_index=True)

    no_rate = student_summary[~has_rate].reset_index(drop=True)
    return below, no_rate


# ---------- Reports (FR-16, FR-17) ----------

def build_attendance_report(frame):
    """Return the filtered attendance table with readable column names (FR-16)."""
    report = frame.sort_values(["session_date", "session_id", "student_id"], ignore_index=True)
    report = report[RECORD_COLUMNS]
    return report.rename(columns={
        "student_id": "Student ID",
        "full_name": "Full name",
        "course_code": "Course",
        "session_id": "Session",
        "session_date": "Date",
        "status": "Status",
    })


def format_summary_table(summary):
    """Return a copy of a student or course summary with rates as text like '87.50%' or 'N/A'.

    The screen and the CSV download both use this table, so they match exactly (FR-17).
    """
    table = summary.copy()
    rate_texts = []
    completeness_texts = []

    for index, row in table.iterrows():
        rate_texts.append(format_rate(row["attendance_rate"]))
        completeness_texts.append(format_rate(row["completeness"]))

    table["attendance_rate"] = rate_texts
    table["completeness"] = completeness_texts
    return table.rename(columns={
        "student_id": "Student ID",
        "full_name": "Full name",
        "course_code": "Course",
        "attendance_rate": "Attendance rate",
        "completeness": "Completeness",
    })


# ---------- Single student report (FR-19) ----------

def filter_student(frame, student_id):
    """Return only the rows of one student."""
    return frame[frame["student_id"] == student_id].reset_index(drop=True)


def format_enrollment_date(date_text, empty_text):
    """Return an enrollment date, or empty_text ('start' or 'now') when there is none."""
    if date_text is None or pd.isna(date_text):
        return empty_text
    return date_text


def build_course_summary(frame):
    """Return one row per course with the enrollment dates, the five counts,
    rate, completeness and the absence streaks (FR-19, FR-21, FR-24, FR-26).

    Meant for one student's records, so each course has one enrollment.
    """
    columns = [
        "course_code", ENROLLED_FROM_COLUMN, ENROLLED_UNTIL_COLUMN,
    ] + COUNT_COLUMNS + [
        "attendance_rate", "completeness", LONGEST_STREAK_COLUMN, CURRENT_STREAK_COLUMN,
    ]
    rows = []

    for course_code, group in frame.groupby("course_code", sort=True):
        labels = {
            "course_code": course_code,
            ENROLLED_FROM_COLUMN: format_enrollment_date(
                group["enrollment_start"].iloc[0], NO_START_TEXT
            ),
            ENROLLED_UNTIL_COLUMN: format_enrollment_date(
                group["enrollment_end"].iloc[0], NO_END_TEXT
            ),
        }
        row = build_summary_row(labels, group)
        longest, current = calculate_streaks(statuses_in_session_order(group))
        row[LONGEST_STREAK_COLUMN] = longest
        row[CURRENT_STREAK_COLUMN] = current
        rows.append(row)

    return pd.DataFrame(rows, columns=columns)


# ---------- Absence streaks and alerts (BR-14, FR-21) ----------

def calculate_streaks(statuses):
    """Return (longest streak, current streak) for statuses listed in session order (BR-14).

    Consecutive 'Absent' statuses form a streak. Every other status ends it:
    'Present', 'Late', 'Excused', and also 'Unknown' (a missing record is not an
    absence and does not join two absences).
    The current streak is the run of 'Absent' at the end of the list.
    """
    longest = 0
    run = 0

    for status in statuses:
        if status == ABSENT:
            run = run + 1
            if run > longest:
                longest = run
        else:
            run = 0

    # After the loop, run is the streak counted back from the most recent session.
    return longest, run


def statuses_in_session_order(group):
    """Return a group's statuses sorted by session date, then session ID."""
    ordered = group.sort_values(["session_date", "session_id"])
    return list(ordered["status"])


def find_last_absence_date(group):
    """Return the latest session date with status 'Absent', or None if there is none."""
    absent_rows = group[group["status"] == ABSENT]
    if absent_rows.empty:
        return None
    return absent_rows["session_date"].max()


def build_streak_table(frame):
    """Return one row per student per course with current and longest streaks (FR-21).

    Only the sessions in frame are used, so the filters are respected.
    """
    columns = [
        "student_id", "full_name", "course_code",
        CURRENT_STREAK_COLUMN, LONGEST_STREAK_COLUMN, LAST_ABSENCE_COLUMN,
    ]
    rows = []

    for (student_id, course_code), group in frame.groupby(["student_id", "course_code"]):
        longest, current = calculate_streaks(statuses_in_session_order(group))
        rows.append({
            "student_id": student_id,
            "full_name": group["full_name"].iloc[0],
            "course_code": course_code,
            CURRENT_STREAK_COLUMN: current,
            LONGEST_STREAK_COLUMN: longest,
            LAST_ABSENCE_COLUMN: find_last_absence_date(group),
        })

    return pd.DataFrame(rows, columns=columns)


def find_streak_alerts(streak_table, minimum):
    """Return the rows whose current streak is at least minimum, highest streak first.

    Ties are ordered by student ID, then course, so the list is always in the same order.
    The columns get readable names for the screen.
    """
    alerts = streak_table[streak_table[CURRENT_STREAK_COLUMN] >= minimum]
    alerts = alerts.sort_values(
        [CURRENT_STREAK_COLUMN, "student_id", "course_code"],
        ascending=[False, True, True],
        ignore_index=True,
    )
    return alerts.rename(columns={
        "student_id": "Student ID",
        "full_name": "Full name",
        "course_code": "Course",
    })


def build_student_history(frame):
    """Return one student's sessions in date order: session, course, date and status.

    Sessions with no record already have the status 'Unknown' (see build_records_frame).
    """
    history = frame.sort_values(["session_date", "session_id"], ignore_index=True)
    history = history[["session_id", "course_code", "session_date", "status"]]
    return history.rename(columns={
        "session_id": "Session",
        "course_code": "Course",
        "session_date": "Date",
        "status": "Status",
    })


# ---------- Dates on screen (BR-23) ----------

def format_date_columns(table):
    """Return a copy of a table with every date column shown as DD/MM/YYYY (BR-23).

    The screen and the CSV download both use the returned table, so they match.
    Values that are not dates ('start', 'now', empty) are left as they are.
    """
    formatted = table.copy()
    for column in DATE_COLUMNS:
        if column not in formatted.columns:
            continue
        new_values = []
        for value in formatted[column]:
            new_values.append(validation.format_date(value))
        formatted[column] = new_values
    return formatted


# ---------- Mark deductions (BR-22, FR-29) ----------

def calculate_deduction(late, absent, late_deduction, absent_deduction):
    """Return the marks deducted: Late x late_deduction + Absent x absent_deduction (BR-22).

    This is the only place the formula lives. The two deductions come from the settings
    table, so every screen and download uses the current settings.
    Present and Excused deduct nothing. Unknown deducts nothing (it is flagged instead).
    There is no maximum.
    """
    return late * late_deduction + absent * absent_deduction


def describe_not_recorded(unknown):
    """Return the flag for records that are missing, like '2 not recorded', or ''."""
    if unknown > 0:
        return f"{unknown} not recorded"
    return ""


def add_deduction_columns(table, late_deduction, absent_deduction):
    """Return a copy of a summary table with "Deducted marks" and the "Not recorded" flag.

    The table needs Late, Absent and Unknown columns (a per-student summary, a
    by-course table or a student profile).
    """
    with_deductions = table.copy()
    deducted = []
    flags = []
    for index, row in with_deductions.iterrows():
        deducted.append(
            calculate_deduction(row[LATE], row[ABSENT], late_deduction, absent_deduction)
        )
        flags.append(describe_not_recorded(row[UNKNOWN]))
    with_deductions[DEDUCTED_COLUMN] = deducted
    with_deductions[NOT_RECORDED_FLAG_COLUMN] = flags
    return with_deductions


def build_deductions_table(frame, late_deduction, absent_deduction):
    """Return one row per student per course with Late, Absent, Excused, Unknown and
    the deducted marks."""
    columns = ["student_id", "full_name", "course_code", LATE, ABSENT, EXCUSED, UNKNOWN,
               DEDUCTED_COLUMN]
    rows = []

    for (student_id, course_code), group in frame.groupby(["student_id", "course_code"]):
        present, late, excused, absent, unknown = count_statuses(group)
        rows.append({
            "student_id": student_id,
            "full_name": group["full_name"].iloc[0],
            "course_code": course_code,
            LATE: late,
            ABSENT: absent,
            EXCUSED: excused,
            UNKNOWN: unknown,
            DEDUCTED_COLUMN: calculate_deduction(late, absent, late_deduction, absent_deduction),
        })

    return pd.DataFrame(rows, columns=columns)


def build_course_deductions(frame, course_code, late_deduction, absent_deduction):
    """Return the deductions export of one course, ready for the grade sheet (FR-29).

    Columns: Student ID, Full name, Late, Absent, Excused, Not recorded, Deducted marks.
    Sorted by student ID.
    """
    deductions = build_deductions_table(frame, late_deduction, absent_deduction)
    course_rows = deductions[deductions["course_code"] == course_code]
    course_rows = course_rows.sort_values("student_id", ignore_index=True)
    export = course_rows[["student_id", "full_name", LATE, ABSENT, EXCUSED, UNKNOWN,
                          DEDUCTED_COLUMN]]
    return export.rename(columns={
        "student_id": "Student ID",
        "full_name": "Full name",
        UNKNOWN: NOT_RECORDED_COLUMN,
    })


def build_student_profile(frame, late_deduction, absent_deduction):
    """Return one student's courses: enrollment period, counts, rates, streaks, the
    deducted marks per course and the "not recorded" flag (Section 6.1, FR-29).

    frame holds the records of one student.
    """
    return add_deduction_columns(build_course_summary(frame), late_deduction, absent_deduction)
