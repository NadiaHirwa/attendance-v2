# Attendance Management and Analytics System (Version 2)

A Streamlit app that records Present/Absent attendance for several courses and sessions,
saves it permanently in SQLite, imports CSV files safely, and summarizes attendance with
filters, a chart, and CSV downloads.

Built for *Programming with Python*, AIMS Rwanda, 2026-2027.
The full requirements are in [ATTENDANCE_SPEC.md](ATTENDANCE_SPEC.md) (Version 3), and
[TRACEABILITY.md](TRACEABILITY.md) links each requirement to its code and tests.
Version 3 (blocks, class days, tutorials, deductions) is being built in stages; what it changes
and why is in the change log, [ATTENDANCE_V3_CHANGES.md](ATTENDANCE_V3_CHANGES.md).

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

This deletes `attendance.db` and recreates it with the Version 3 demo data: block B1-2627
(07/09/2026 to 25/09/2026), 3 courses with a class every weekday (one holiday in DS102) and
2 tutorials each, and 12 students, including a late joiner and an early leaver.
Expected totals: 477 Present, 10 Late, 4 Excused, 10 Absent, 4 Unknown (505 expected),
attendance rate 97.99%, completeness 99.21%. The script also prints the deductions per
student per course.

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

If the database has no courses when the app starts, the demo data is created automatically.
The sidebar also has a **Reset demo data** button (tick the confirmation box first), which
replaces all data with the demo data.

## Deploy on Streamlit Community Cloud

1. Push this folder to a GitHub repository. `attendance.db` and `.venv/` are in `.gitignore`,
   so they are not uploaded.
2. Sign in at [share.streamlit.io](https://share.streamlit.io) with GitHub and click
   **Create app**.
3. Choose the repository and branch, and set **Main file path** to `app.py`.
4. Click **Deploy**. Streamlit installs the packages in `requirements.txt`
   (`streamlit`, `pandas`) and starts the app.

Things to know about the online version:

- On first start the database is empty, so the app creates the demo data by itself.
- The online storage is temporary: **data may reset** whenever the app restarts or is
  redeployed. The sidebar says so, and "Reset demo data" brings back the demo at any time.
- Anyone with the link can use the app (there is no login), so **do not enter real
  personal data**.
- `.streamlit/config.toml` is used online too, so the Deploy button stays hidden.

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
