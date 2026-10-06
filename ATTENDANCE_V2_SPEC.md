# Attendance Management and Analytics System: Version 2

| Item | Detail |
|---|---|
| Version | 2.0 (scope FROZEN for the presentation) |
| Author | Nadia Iradukunda Hirwa |
| Course | Programming with Python, AIMS Rwanda, 2026-2027 |
| Replaces | SRS Version 1.0 (single-session console tracker) |
| Stack | Python 3, Streamlit, Pandas, sqlite3 (standard library), unittest |

---

## 1. Purpose and scope

Version 1 recorded attendance for one session and lost everything on exit.
Version 2 records attendance for **several courses and sessions**, **saves it permanently**,
**imports CSV files safely**, and **summarizes attendance** with filters, a chart, and downloads.

**In scope:** courses, students, enrollments, sessions, Present/Absent recording and correction,
search, CSV import with validation, dashboard, reports, CSV downloads, SQLite storage.

**Out of scope (Future Work):** login/roles, Late/Excused,
conflict-resolution screens, import history tab, multi-file upload,
student self-service view (requires login and roles).

## 2. Assumptions

- A1. One trusted operator uses the app on one computer.
- A2. Student IDs stay in the V1 format (3 ASCII digits, 001 to 999) and identify a person across courses.
- A3. A student enrolled in a course is expected at **every** session of that course
  inside their enrollment dates (BR-15). With no dates, that is every session.
- A4. The system checks format and consistency, not truth.

## 3. Data model (SQLite file `attendance.db`)

```sql
courses     (course_code TEXT PRIMARY KEY, course_name TEXT NOT NULL,
             start_date  TEXT,                       -- YYYY-MM-DD or NULL (BR-16)
             end_date    TEXT)                       -- YYYY-MM-DD or NULL (BR-16)
students    (student_id  TEXT PRIMARY KEY, full_name TEXT NOT NULL)
enrollments (student_id  TEXT NOT NULL REFERENCES students,
             course_code TEXT NOT NULL REFERENCES courses,
             start_date  TEXT,                       -- YYYY-MM-DD or NULL (BR-15)
             end_date    TEXT,                       -- YYYY-MM-DD or NULL (BR-15)
             PRIMARY KEY (student_id, course_code))
sessions    (session_id  TEXT PRIMARY KEY,
             course_code TEXT NOT NULL REFERENCES courses,
             session_date TEXT NOT NULL)            -- YYYY-MM-DD
attendance  (student_id  TEXT NOT NULL REFERENCES students,
             session_id  TEXT NOT NULL REFERENCES sessions,
             status      TEXT NOT NULL CHECK (status IN ('Present', 'Absent')),
             source      TEXT NOT NULL,              -- 'manual' or the CSV filename
             recorded_at TEXT NOT NULL,              -- ISO timestamp
             PRIMARY KEY (student_id, session_id))
```

- `PRAGMA foreign_keys = ON` runs on **every** connection (inside `get_connection()`).
- **Unknown is never stored.** It is calculated: an enrolled student with no attendance row for a session of their course inside their enrollment dates (BR-15).
- `create_tables()` adds `start_date` and `end_date` to the `courses` and `enrollments` tables of an older `attendance.db` that lacks them (`ALTER TABLE ... ADD COLUMN`); old rows get NULL dates and behave as before.

## 4. Business rules

| ID | Rule |
|---|---|
| BR-01 | **Student ID:** exactly 3 ASCII digits, 001 to 999, stored as text (V1 rule). |
| BR-02 | **Full name:** V1 rules. Clean (collapse spaces, `’` to `'`, Unicode NFC), then letters/spaces/hyphens/apostrophes only, at least one letter, `-` and `'` need a letter on both sides, max 50 characters. |
| BR-03 | **Course code:** 2 to 10 ASCII letters or digits, at least one letter, stored UPPERCASE (`py101` becomes `PY101`). |
| BR-04 | **Course name:** 1 to 80 characters after trimming. |
| BR-05 | **Session ID:** 1 to 20 ASCII letters, digits, or hyphens, stored UPPERCASE. Unique across all courses. |
| BR-06 | **Session date:** a real calendar date in `YYYY-MM-DD` format (`2026-02-30` is rejected). |
| BR-07 | **Status:** accept `P`, `A`, `Present`, `Absent` in any case; store `Present` or `Absent`. |
| BR-08 | **One record per student per session.** Recording again for the same pair is an **edit**, not a new record. |
| BR-09 | Attendance can be recorded only for a student **enrolled** in the session's course. |
| BR-10 | **Attendance rate** = Present / (Present + Absent) x 100, 2 decimals. Shown as `N/A` when Present + Absent = 0. |
| BR-11 | **Recording completeness** = (Present + Absent) / Expected x 100, where Expected = sessions x enrolled students. `N/A` when Expected = 0. |
| BR-12 | **Unknown** = Expected - Present - Absent. Unknown is never counted as Absent. |
| BR-13 | Every error message states what was wrong and what is expected. |
| BR-14 | **Absence streak:** counted per student per course, over that course's sessions in date order (then session ID), using only sessions inside the current filters. Consecutive Absent records form a streak; Present ends it, and Unknown also ends it (Unknown is not an absence and does not join two absences). **Longest streak** = the longest run anywhere. **Current streak** = the run of Absent counted back from the student's most recent session in that course (0 if that session is not Absent). |
| BR-15 | **Enrollment dates:** an enrollment has an optional `start_date` and `end_date` (`YYYY-MM-DD`). A student is **expected** at a session only if the session date is on or after `start_date` (when set) and on or before `end_date` (when set); both dates are included. NULL start = from the course's first session; NULL end = still enrolled. The end must not be before the start. Attendance can only be recorded for an expected session. |
| BR-16 | **Course dates:** a course has an optional `start_date` and `end_date` (`YYYY-MM-DD`); NULL means no limit on that side. A session's date must be inside its course's period (both dates included). The end must not be before the start. Course dates do **not** change who is expected at a session (that is BR-15). |
| BR-17 | **Enrollment inside course:** an enrollment's start must be on or before its end, and each set date must be inside the course period. A date equal to the course's start (or end) is stored as NULL, so the enrollment follows the course if the course dates change later. A course's dates cannot be changed so that an enrollment with its own dates falls outside them. Enforced in `validation.py` and `database.py`, not only in the date inputs. |

**Worked example (use in a test and on a slide):** 7 Present, 2 Absent, 1 Unknown, so Attendance = 77.78% and Completeness = 90.00%.

## 5. CSV import rules

**Required columns** (any order, header names case-insensitive, extra columns ignored):

```
session_id,course_code,session_date,student_id,full_name,status
```

| ID | Rule |
|---|---|
| IR-01 | File must be readable as UTF-8 (BOM allowed) and contain all required columns. Otherwise the **whole file** is rejected with a message naming the missing columns. |
| IR-02 | Each row is validated with BR-01 to BR-07. An invalid row is **rejected with a reason** (for example `Row 7: invalid student ID "12A", expected 3 digits 001-999`). |
| IR-03 | `course_code` must already exist. Otherwise: rejected, `Unknown course "BIO200", create it first`. |
| IR-04 | A new `student_id` creates the student. An existing ID with a **different name** (case-insensitive) is rejected as a conflict. |
| IR-05 | A new `session_id` creates the session. An existing session with a **different course or date** is rejected as a conflict. |
| IR-06 | The student is enrolled in the course automatically if not already enrolled. |
| IR-07 | **Exact duplicate** (same student, session, and status already saved, or repeated earlier in the file): **skipped and counted**. |
| IR-08 | **Conflicting status** (same student and session, different status): **rejected**. The existing record is **kept**. |
| IR-09 | Workflow: **Upload, Preview, Validate, Review issues, Confirm, Result.** Nothing is written before Confirm. |
| IR-10 | Saved rows record the filename in `source`. |
| IR-11 | The result shows counts: accepted, skipped duplicates, rejected. Rejected rows can be downloaded as CSV with a `reason` column. |

## 6. Functional requirements

| ID | Tab | The system shall... |
|---|---|---|
| FR-01 | All | Show 4 tabs: Dashboard, Manage Attendance, Import & Validate, Reports. |
| FR-02 | All | Keep all data in `attendance.db` so it survives closing the app. |
| FR-03 | Manage | Create a course (BR-03, BR-04). Duplicate course codes are rejected. |
| FR-04 | Manage | Add a student (BR-01, BR-02): student ID and full name only. A repeated name shows a warning and needs confirmation (V1 rule). A new student starts with no course ("Not enrolled" in search). |
| FR-05 | Manage | "Enroll a student in a course" is the only manual way to enroll: Student, Course, "Enrolled from" and "Enrolled until". The dates default to the chosen course's start and end and are limited to its period (BR-17); with no course period, there are no limits and "Enrolled from" defaults to today. |
| FR-06 | Manage | Create a session for a course (BR-05, BR-06). |
| FR-07 | Manage | Record attendance for a session: list every enrolled student with a Present/Absent choice, save all at once. |
| FR-08 | Manage | Correct attendance: re-open a session, change statuses, save. Unchanged rows are not rewritten. |
| FR-09 | Manage | Search students by exact ID or by exact cleaned name (case-insensitive); show all matches with their courses. |
| FR-10 | Import | Implement the import workflow in Section 5. |
| FR-11 | Import | Offer a downloadable empty CSV template with the required columns. |
| FR-12 | Dashboard | Filter by course (or All courses) and date range. Show the active filters. |
| FR-13 | Dashboard | Show metrics: students, sessions, Present, Absent, Unknown, attendance rate, completeness. |
| FR-14 | Dashboard | Show one chart: attendance rate by session, in date order. |
| FR-15 | Dashboard | List students below a chosen threshold (slider, default 75%), sorted by rate. |
| FR-16 | Reports | A "Student" selector at the top defaults to "All students", which shows the overall Present, Absent, Unknown, rate and completeness, a per-student summary (Present, Absent, Unknown, rate, completeness), and the filtered attendance table (student, course, session, date, status). |
| FR-17 | Reports | Download both tables as CSV. **Downloads match exactly what is on screen.** |
| FR-18 | All | Show a clear message instead of an empty table or chart when there is no data. |
| FR-19 | Reports | Single student report: choosing a student ("ID - Name") in the FR-16 selector replaces the All students view; using the course and date filters, show their Present, Absent, Unknown, attendance rate and completeness, a per-course breakdown when they are in more than one course, and their session history (session, course, date, status) in date order with missing records shown as Unknown. The history can be downloaded as CSV, matching the screen. |
| FR-20 | Dashboard | Show a second chart below the FR-14 chart, "Recording status by session": one stacked bar per session with its Present (blue), Absent (orange) and Unknown (grey) counts, using the same filters, labels and session order as FR-14. Sessions with no records are included as all Unknown. Each bar's total equals the students enrolled in that session's course. |
| FR-21 | Dashboard, Reports | **Absence alerts** (Dashboard, below the threshold list): a number input "Alert when current streak is at least" (default 2, minimum 1) lists every student and course whose current streak (BR-14) reaches it, with student ID, name, course, current streak, longest streak and date of last absence, highest current streak first. If nobody matches, a success message says so. In the Reports single-student view, the "By course" table (shown even for one course) adds the longest and current absence streak per course. |
| FR-22 | Manage (Edit & Delete) | **Rename** a student's full name (BR-02 cleaning and validation, and the same-name warning with confirmation as in FR-04, ignoring the student's own name) or a course's name (BR-04). Student IDs and course codes never change. If the new value equals the old one, show "No change". |
| FR-23 | Manage (Edit & Delete) | **Delete**, each in one database transaction that returns the counts removed: one attendance record (the student becomes Unknown for that session); an enrollment, with the student's records for that course's sessions; a student, with all their records and enrollments (the ID can be used again); a session, with its records; a course, only when it has no sessions and no enrolled students (otherwise an error says how many sessions and students must be removed first). Every delete first shows what will be removed, with counts, and the Delete button works only after ticking "I understand this cannot be undone". |
| FR-24 | Manage, Import, Reports | **Enrollment dates (BR-15).** The Enroll form (FR-05) asks for "Enrolled from" and "Enrolled until" inside the course period (BR-17). Record Attendance lists only students expected at the session, and `record_attendance()` returns `outside_enrollment` without saving for a date outside the window. Edit & Delete has "Change enrollment dates" (only the student's courses, pre-filled with the current dates, a date not set shown as the course's, limited to the course period), refused (with the number of records affected) if saved attendance would fall outside the new dates. Import: a new enrollment starts at the student's earliest session date for that course in the accepted rows; for an existing enrollment, a row outside its dates is rejected (for example `Row 7: Student 004 is enrolled in PY101 from 2026-09-14, not on 2026-09-07.`). The Reports "By course" table shows "Enrolled from" and "Enrolled until" ("start" / "now" when not set). The seed data has no dates. |
| FR-25 | Manage, Import, Dashboard, Reports | **Course dates (BR-16).** Create course asks for "Start date" and "End date" and refuses an end before the start. Create session refuses a date outside the period (`PY101 runs from 2026-09-07 to 2026-12-18. Choose a date in that period.`); import rejects such a row (`Row 7: PY101 runs from 2026-09-07 to 2026-12-18, not on 2027-01-05.`). Edit & Delete has "Change course dates", refused (with the number affected) if a session or an enrollment with its own dates (BR-17) would fall outside the new period. Every date input shows dates as `YYYY-MM-DD`. The Courses sub-tab lists every course with its period, and course labels show it (`PY101 - Programming with Python (2026-09-07 to 2026-12-18)`). When one course is chosen in the Dashboard/Reports filters, the date range starts as that course's period (or its session dates where the period is not set). The seed data runs PY101 2026-09-07 to 2026-12-18 and DS102 2026-09-09 to 2026-12-18. |

## 7. Non-functional requirements

| ID | Requirement |
|---|---|
| NFR-01 | No input or uploaded file may crash the app; errors appear as messages. |
| NFR-02 | All rules and calculations live in modules with **no Streamlit code**, so they can be tested. |
| NFR-03 | PEP 8, single-purpose functions with docstrings, constants at the top of each module. |
| NFR-04 | All SQL uses `?` parameters, never string formatting (prevents SQL injection). |
| NFR-05 | `python -m unittest` passes before the demo. |

## 8. Project structure

```
attendance_v2/
├── validation.py      # pure functions: is_valid_student_id, clean_name, is_valid_name,
│                      #   normalize_course_code, is_valid_session_id, parse_date, normalize_status
├── database.py        # get_connection, create_tables, and one function per query/insert
├── analytics.py       # calculate_rates, build_student_summary, build_session_summary (Pandas, no UI)
├── importer.py        # read_csv, validate_rows -> (accepted, duplicates, rejected), apply_import
├── app.py             # Streamlit UI only: 4 tabs that call the modules above
├── seed_demo.py       # creates a clean demo database
├── demo_data/
│   ├── clean_import.csv
│   └── messy_import.csv   # contains every kind of rejection and a duplicate
├── tests/
│   ├── test_validation.py
│   ├── test_analytics.py
│   └── test_importer.py
├── requirements.txt   # streamlit, pandas
└── TRACEABILITY.md    # requirement -> function -> test
```

## 9. Known limitations

- No login: anyone at the computer can change records.
- Accented and unaccented names (`Émile` / `Emile`) are different.
- Validation checks format and consistency, not truth.
- A session ID is not tied to its course name: `PY101-W5` can be created for course DS102.

## 10. Minimum tests

| Test | Checks | Req |
|---|---|---|
| T01 | `001`, `999` valid; `000`, `1`, `1000`, `12A`, `+01`, `٠٠١` invalid | BR-01 |
| T02 | `Jean-Paul`, `O’Neil` (to `O'Neil`) valid; `-Nadia`, `Jean--Paul`, `Jean - Paul`, 51 letters invalid | BR-02 |
| T03 | `py101` becomes `PY101`; `1`, `123`, `PY 101` invalid | BR-03 |
| T04 | `2026-09-15` valid; `2026-02-30`, `15/09/2026`, empty invalid | BR-06 |
| T05 | `p`, `PRESENT`, ` a ` accepted; `late`, `x` rejected | BR-07 |
| T06 | 7 Present, 2 Absent, 1 Unknown gives 77.78% and 90.00% | BR-10, BR-11 |
| T07 | 0 records gives `N/A`, no division error | BR-10, BR-11 |
| T08 | CSV missing `status` column: whole file rejected, names the column | IR-01 |
| T09 | Unknown course: row rejected with reason | IR-03 |
| T10 | Same row twice: one accepted, one skipped | IR-07 |
| T11 | Different status for saved record: rejected, existing kept | IR-08 |
| T12 | Existing ID with a different name: rejected | IR-04 |
| T13 | Recording twice for the same student and session updates instead of duplicating | BR-08 |
| T14 | Foreign keys on: attendance for a missing session raises an error | Section 3 |

Tests use a **temporary database** (`:memory:` or a temp file), never `attendance.db`.

## 11. Implementation decisions

Decisions made while building, where the sections above did not say what to do.

| Topic | Decision |
|---|---|
| BR-08, FR-08 | `record_attendance()` returns `inserted`, `updated`, `unchanged` or `not_enrolled`. An unchanged status is not rewritten. |
| BR-09 | `record_attendance()` checks enrollment itself and returns `not_enrolled` without saving. A missing session is left to the foreign key, which raises an error (T14). |
| FR-07 | A student left blank in the recording table is not saved and stays Unknown. |
| FR-04 | The same-name confirmation is a checkbox in the Add student form. |
| FR-06 | The session date is typed as `YYYY-MM-DD` text and checked with BR-06. |
| IR-02 | Row numbers match the file as seen in a spreadsheet: the header is row 1, the first data row is row 2. Format errors quote the value found. |
| IR-04, IR-05, IR-08 | Consistency is also checked **inside the file**: a new student ID with two names, a new session ID with two courses or dates, or one student and session with two statuses. The first row is kept and the later one is rejected. |
| IR-07 | Duplicates are listed with their reason (`Repeats row N` or `Already saved with the same status`). |
| IR-09 | Confirm saves all accepted rows in **one transaction**: if any row fails, nothing is saved and the user is asked to validate again. Validation only reads the database. The validation result is kept in `st.session_state` and cleared after a successful import, so Confirm cannot run twice. |
| FR-12 | The course and date filters are in the sidebar and apply to both the Dashboard and Reports. The date range defaults to the earliest and latest session dates. |
| FR-14 | Sessions with no recorded status have no rate and are left out of the chart. |
| FR-15 | "Below the threshold" means strictly lower than it. Students with no recorded sessions (rate N/A) are listed in a separate table. |
| NFR-03 | Lines are at most 99 characters (PEP 8 allows 99 when a project agrees on it). |

---

# Build plan: 4 hours

**Before starting:** copy the current `attendance_app.py` (tkinter) to a `backup/` folder and do not touch it.
It already does Add, View, Search, Edit, and Summary. **It is your fallback demo.**

| Time | Stage | Done when |
|---|---|---|
| 0:00 to 0:15 | Setup: venv, `pip install streamlit pandas`, `streamlit hello` works | Browser opens |
| 0:15 to 1:15 | **Stage 1:** validation, database, analytics, tests | `python -m unittest` passes |
| 1:15 to 2:00 | **Stage 2:** Manage Attendance tab, seed_demo.py | Can create course, student, session, record, edit |
| 2:00 to 2:45 | **Stage 3:** importer + Import tab + demo CSVs | Messy file shows every rejection type |
| 2:45 to 3:20 | **Stage 4:** Dashboard + Reports | Numbers match a hand calculation |
| 3:20 to 4:00 | **Stage 5:** full demo run, fix bugs, TRACEABILITY.md, screenshots | Demo works twice in a row from `seed_demo.py` |

**Copy the folder after each stage** (`stage1/`, `stage2/`, ...).

**If you fall behind, cut in this order:** threshold list (FR-15), then the Reports tab
(keep one download button on the Dashboard), then FR-05. **Never cut the tests or the demo rehearsal.**

**After every stage, ask Claude:** "Explain each function in the files you just wrote in simple words,
and tell me what question an examiner might ask about it." You present this tomorrow.

---

# Prompts for Claude in VS Code

Put this file in the project folder first. Send **one prompt per stage**. Do not send the next prompt
until the current stage's "Done when" is true.

### Prompt 1: core and tests

```
Read ATTENDANCE_V2_SPEC.md. It is the frozen specification. Build STAGE 1 only:
validation.py, database.py, analytics.py, and tests/test_validation.py and tests/test_analytics.py,
plus requirements.txt.

Rules:
- No Streamlit imports in these modules.
- database.py: get_connection(path) must run PRAGMA foreign_keys = ON every time; create_tables()
  uses the exact schema in Section 3; all SQL uses ? parameters.
- Recording attendance for an existing (student_id, session_id) must update it (BR-08).
- analytics.py returns numbers and DataFrames only, never prints. Unknown is computed, never stored.
- Tests use a temporary database, cover T01 to T07, T13, T14 from Section 10, and each test's
  docstring names its requirement ID.
- Keep functions short, with docstrings. Prefer simple code I can explain over clever code.
Then run python -m unittest and fix any failures. Do not start the UI.
```

### Prompt 2: Manage Attendance

```
Stage 1 is done and tests pass. Build STAGE 2 from ATTENDANCE_V2_SPEC.md:
app.py with all 4 tabs (only Manage Attendance working; the other 3 show "Coming soon"),
and seed_demo.py, which deletes and recreates attendance.db with 2 courses, about 12 students,
4 sessions per course, and a few deliberately missing records so Unknown is not zero.

Manage Attendance must cover FR-03 to FR-09. Use st.form for inputs. For recording, use
st.data_editor with a Present/Absent selectbox column for every enrolled student.
Show st.error messages with the BR-13 style. app.py must call validation/database/analytics
functions and must not contain SQL or validation rules itself.
```

### Prompt 3: Import & Validate

```
Build STAGE 3 from ATTENDANCE_V2_SPEC.md: importer.py, the Import & Validate tab,
tests/test_importer.py (T08 to T12), and demo_data/clean_import.csv and demo_data/messy_import.csv.

The messy file must include: a bad student ID, a bad name, a bad date, a bad status,
an unknown course, a student ID with a different name, a session with a different date,
an exact duplicate, and a conflicting status. Every rejected row needs a clear reason.
Follow the IR-09 workflow exactly: nothing is written to the database before the Confirm button.
Keep the validation result in st.session_state so Confirm does not re-read the file.
Run python -m unittest afterwards.
```

### Prompt 4: Dashboard and Reports

```
Build STAGE 4 from ATTENDANCE_V2_SPEC.md: the Dashboard tab (FR-12 to FR-15) and the
Reports tab (FR-16, FR-17). Filters are a course selectbox (with "All courses") and a
date range. Show the active filters as a caption. Use st.metric for the numbers and
st.bar_chart or st.line_chart for attendance rate by session. Downloads must be built
from the same DataFrame shown on screen. Handle empty data with st.info (FR-18).
All calculations come from analytics.py.
```

### Prompt 5: verification

```
Run python -m unittest. Then review app.py, importer.py, analytics.py and database.py against
every requirement in ATTENDANCE_V2_SPEC.md and list any requirement not met, with file and line.
Then create TRACEABILITY.md: a table of requirement ID -> function(s) -> test ID or
"manual demo step". Do not add new features.
```

---

# Demo script (about 5 minutes)

1. `python seed_demo.py`, then `streamlit run app.py`.
2. **Dashboard:** pick a course and date range. Point at Unknown and completeness: *"Missing is not the same as Absent."*
3. **Manage:** add a student with name `-Nadia`: error. Fix it. Add `NADIA HIRWA` when `Nadia Hirwa` exists: warning.
4. **Manage:** record a session, then correct one student's status.
5. **Import:** upload `messy_import.csv`. Walk through the rejection reasons. Confirm. Show accepted/skipped/rejected counts.
6. **Dashboard:** the numbers changed. Download the report, open it, and show it matches the screen.
7. Terminal: `python -m unittest` shows all tests passing.
8. Close the app, reopen it: **data is still there** (the main V1 limitation, now solved).

**Demo safety:** if Streamlit asks for an email on first run, press Enter.
Run the full demo once tonight on the presentation laptop. Keep screenshots of every step as a backup.
