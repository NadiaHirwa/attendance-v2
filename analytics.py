"""Attendance calculations (BR-10 to BR-12).

Functions return numbers and DataFrames only. They never print and
never use Streamlit, so every calculation can be tested.
"""

import pandas as pd

PRESENT = "Present"
ABSENT = "Absent"
UNKNOWN = "Unknown"
NOT_AVAILABLE = "N/A"

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
