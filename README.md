# Attendance Management and Analytics System (Version 2)

A Streamlit app that records Present/Absent attendance for several courses and sessions,
saves it permanently in SQLite, imports CSV files safely, and summarizes attendance with
filters, a chart, and CSV downloads.

Built for *Programming with Python*, AIMS Rwanda, 2026-2027.
The full requirements are in [ATTENDANCE_V2_SPEC.md](ATTENDANCE_V2_SPEC.md), and
[TRACEABILITY.md](TRACEABILITY.md) links each requirement to its code and tests.

## Install

Requires Python 3 on Windows. From the project folder:

```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

Commands below call `.venv\Scripts\python` directly, so the virtual environment
does not need to be activated.

## Create the demo data

```
.venv\Scripts\python seed_demo.py
```

This deletes `attendance.db` and recreates it with 2 courses, 12 students, 4 sessions per
course, and 4 missing records (so Unknown is not zero). Expected totals: 63 Present,
9 Absent, 4 Unknown, attendance rate 87.50%, completeness 94.74%.

## Run the app

```
.venv\Scripts\python -m streamlit run app.py
```

The app opens in the browser with four tabs:

- **Dashboard**: metrics, attendance rate by session, and students below a threshold.
- **Manage Attendance**: create courses, students and sessions, enroll students,
  record and correct attendance, and search students.
- **Import & Validate**: upload a CSV file, review accepted, duplicate and rejected rows,
  then confirm. Try `demo_data/clean_import.csv` and `demo_data/messy_import.csv`.
- **Reports**: the filtered attendance table and per-student summary, with CSV downloads.

The course and date filters for the Dashboard and Reports are in the sidebar.

## Run the tests

```
.venv\Scripts\python -m unittest
```

The tests use a temporary in-memory database and never touch `attendance.db`.

## Project files

| File | Purpose |
|---|---|
| `validation.py` | Rules for IDs, names, codes, dates and statuses, and the error messages |
| `database.py` | SQLite connection, tables, and every query |
| `analytics.py` | Rates, summaries, filters and report tables (no Streamlit) |
| `importer.py` | CSV reading, validation and import |
| `app.py` | Streamlit screens only |
| `seed_demo.py` | Creates the demo database |
| `demo_data/` | A clean and a messy CSV file for the import demo |
| `tests/` | Unit tests |
| `backup/attendance_app.py` | The Version 1 app, kept as a fallback demo |
