"""Attendance calculations (BR-10 to BR-12).

Functions return numbers and DataFrames only. They never print and
never use Streamlit, so every calculation can be tested.
"""

import pandas as pd

PRESENT = "Present"
ABSENT = "Absent"
UNKNOWN = "Unknown"
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
CURRENT_STREAK_COLUMN = "Current absence streak"
LONGEST_STREAK_COLUMN = "Longest absence streak"
LAST_ABSENCE_COLUMN = "Last absence"
# Order of the parts of each stacked bar, from the bottom up.
STATUS_ORDER = [PRESENT, ABSENT, UNKNOWN]

RECORD_COLUMNS = [
    "student_id",
    "full_name",
    "course_code",
    "session_id",
    "session_date",
    "status",
]


def calculate_rates(present, absent, unknown):
    """Return the counts, attendance rate and completeness for one group.

    Attendance rate = Present / (Present + Absent) x 100 (BR-10).
    Completeness = (Present + Absent) / Expected x 100 (BR-11).
    A rate is None when its denominator is 0, so there is no division error.
    """
    recorded = present + absent
    expected = present + absent + unknown

    if recorded == 0:
        attendance_rate = None
    else:
        attendance_rate = round(present / recorded * 100, 2)

    if expected == 0:
        completeness = None
    else:
        completeness = round(recorded / expected * 100, 2)

    return {
        "present": present,
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
    """
    frame = pd.DataFrame(records, columns=RECORD_COLUMNS)
    frame["status"] = frame["status"].fillna(UNKNOWN)
    return frame


def count_statuses(frame):
    """Return the number of Present, Absent and Unknown rows in a records frame."""
    present = int((frame["status"] == PRESENT).sum())
    absent = int((frame["status"] == ABSENT).sum())
    unknown = int((frame["status"] == UNKNOWN).sum())
    return present, absent, unknown


def summarize_frame(frame):
    """Return calculate_rates() for all rows of a records frame."""
    present, absent, unknown = count_statuses(frame)
    return calculate_rates(present, absent, unknown)


def build_summary_row(labels, group):
    """Return one summary row: the group's labels plus its counts and rates."""
    rates = summarize_frame(group)
    row = dict(labels)
    row["Present"] = rates["present"]
    row["Absent"] = rates["absent"]
    row["Unknown"] = rates["unknown"]
    row["attendance_rate"] = rates["attendance_rate"]
    row["completeness"] = rates["completeness"]
    return row


def build_student_summary(frame):
    """Return one row per student with Present, Absent, Unknown, rate and completeness."""
    columns = [
        "student_id", "full_name", "Present", "Absent", "Unknown",
        "attendance_rate", "completeness",
    ]
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
    columns = [
        "session_id", "course_code", "session_date", "Present", "Absent",
        "Unknown", "attendance_rate", "completeness",
    ]
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
    """Return a short chart label like '09-07 PY101-W1', or '2026-09-07 PY101-W1' with the year."""
    if include_year:
        return f"{session_date} {session_id}"
    # session_date is 'YYYY-MM-DD', so [5:] keeps only 'MM-DD'.
    return f"{session_date[5:]} {session_id}"


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
    """Return one row per session (label, course, Present, Absent, Unknown) in date order (FR-20).

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
        rows.append({
            CHART_LABEL_COLUMN: label,
            CHART_COURSE_COLUMN: row["course_code"],
            PRESENT: row["Present"],
            ABSENT: row["Absent"],
            UNKNOWN: row["Unknown"],
        })

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


def build_course_summary(frame):
    """Return one row per course with Present, Absent, Unknown, rate, completeness and
    the longest and current absence streaks (FR-19, FR-21)."""
    columns = [
        "course_code", "Present", "Absent", "Unknown", "attendance_rate", "completeness",
        LONGEST_STREAK_COLUMN, CURRENT_STREAK_COLUMN,
    ]
    rows = []

    for course_code, group in frame.groupby("course_code", sort=True):
        labels = {"course_code": course_code}
        row = build_summary_row(labels, group)
        longest, current = calculate_streaks(statuses_in_session_order(group))
        row[LONGEST_STREAK_COLUMN] = longest
        row[CURRENT_STREAK_COLUMN] = current
        rows.append(row)

    return pd.DataFrame(rows, columns=columns)


# ---------- Absence streaks and alerts (BR-14, FR-21) ----------

def calculate_streaks(statuses):
    """Return (longest streak, current streak) for statuses listed in session order (BR-14).

    Consecutive 'Absent' statuses form a streak. 'Present' ends it, and so does
    'Unknown': a missing record is not an absence and does not join two absences.
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
