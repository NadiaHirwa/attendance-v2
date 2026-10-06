# Attendance Management and Analytics System: Specification (Version 3)

| Item | Detail |
|---|---|
| Version | 3.1 (3.0 scope frozen after tutor feedback, October 2026; 3.1 usability polish from the tutor review, Stage 7) |
| Author | Nadia Iradukunda Hirwa |
| Course | Programming with Python, AIMS Rwanda, 2026-2027 |
| Replaces | Version 2.0 (`ATTENDANCE_V2_SPEC.md`, renamed to this file) and SRS Version 1.0 (single-session console tracker) |
| Change log | [ATTENDANCE_V3_CHANGES.md](ATTENDANCE_V3_CHANGES.md): what Version 3 changes, why, and the build prompts |
| Stack | Python 3, Streamlit, Pandas, sqlite3 (standard library), unittest |

**How to read this file.** Every Version 2 rule stays unless it is marked **[V3]**. New Version 3
rules are BR-18 to BR-24 and FR-27 to FR-31. Version 3 is built in stages (see the change log), so
until a stage is finished the app still follows the Version 2 rule it replaces.

---

## 1. Purpose and scope

Version 1 recorded attendance for one session and lost everything on exit.
Version 2 records attendance for **several courses and sessions**, **saves it permanently**,
**imports CSV files safely**, and **summarizes attendance** with filters, charts, and downloads.

Version 3 follows how AIMS really teaches. Teaching is organised in **blocks**: a block lasts
**3 weeks**, contains **2 to 4 courses**, and every course meets **every weekday** (Monday to Friday)
of the block. **Tutorials** can happen on any date inside the course period. Lateness and absence
cost marks: **Late -1, Absent -2, per course**. Version 2 used free-form sessions with typed IDs;
Version 3 generates class days from the block, so tutors type less and the system assumes less.

**In scope:** blocks, courses, students, enrollments, class days and tutorials,
Present/Late/Excused/Absent recording and correction, mark deductions, search,
CSV import with validation, auto-fix and suggested fixes, dashboard, reports (weekly view,
class register, deductions export), CSV downloads, SQLite storage.

**Out of scope (Future Work):** login and roles, the AIMS student ID format (BR-24),
a school holiday calendar, email alerts, a shared server database, import history tab,
multi-file upload, student self-service view (requires login and roles).

### What Version 3 replaces

| Version 2 | Version 3 |
|---|---|
| Sessions created by hand with a typed session ID (BR-05, FR-06) | Class days generated for every weekday of the course (BR-20); tutorials added by date (BR-21); session IDs generated, never typed |
| Courses with free start and end dates (BR-16, FR-25) | Courses belong to a block; dates default to the block and may only be narrowed inside it (BR-18, BR-19) |
| Dates shown and typed as `YYYY-MM-DD` (FR-25) | Dates shown and downloaded as `DD/MM/YYYY`; files may use either form (BR-23) |
| Import columns `session_id, course_code, session_date, ...` (Section 5) | Import columns `course_code, date, student_id, full_name, status` and optional `type` (Section 5) |
| Import rejects a saved ID with another name, an in-file ID clash and a conflicting status (IR-04, IR-08) | These become **suggestions** a person accepts or rejects; safe problems are **auto-fixed** (FR-31) |
| "Edit & Delete" sub-tab (FR-22 to FR-25) | Each rename, date change and delete lives in the sub-tab of the thing it changes (Section 6.1) |
| Dashboard filter: course and date range (FR-12) | Block, then course in that block, then date range (FR-30) |
| No mark deductions | Late and Absent deduct marks per course (BR-22, FR-29) |
| Demo data: 2 courses, 4 sessions each, totals 63 / 9 / 4 | Demo data: one block, 3 courses, 15 class days each, tutorials (Section 12); totals recalculated |

## 2. Assumptions

- A1. One trusted operator uses the app on one computer.
- A2. Student IDs stay in the V1 format (3 ASCII digits, 001 to 999) and identify a person across courses.
- A3. A student enrolled in a course is expected at **every** session of that course
  inside their enrollment dates (BR-15). With no dates, that is every session.
  **[V3]** "Every session" means every class day and every tutorial of the course (BR-20, BR-21).
- A4. The system checks format and consistency, not truth.
- A5. **[V3]** A block lasts 3 weeks and contains 2 to 4 courses; every course meets every weekday of its period.

## 3. Data model (SQLite file `attendance.db`)

```sql
blocks      (block_id    TEXT PRIMARY KEY,           -- [V3] e.g. B1-2627, stored uppercase (BR-18)
             block_name  TEXT NOT NULL,              --      e.g. "Block 1, 2026-27"
             start_date  TEXT NOT NULL,              --      always a Monday
             end_date    TEXT NOT NULL)              --      calculated: Friday of week 3
courses     (course_code TEXT PRIMARY KEY, course_name TEXT NOT NULL,
             block_id    TEXT REFERENCES blocks,     -- [V3] required for new courses (BR-19)
             start_date  TEXT,                       -- YYYY-MM-DD or NULL (BR-16); [V3] default = block dates
             end_date    TEXT)                       -- YYYY-MM-DD or NULL (BR-16); [V3] default = block dates
students    (student_id  TEXT PRIMARY KEY, full_name TEXT NOT NULL)
enrollments (student_id  TEXT NOT NULL REFERENCES students,
             course_code TEXT NOT NULL REFERENCES courses,
             start_date  TEXT,                       -- YYYY-MM-DD or NULL (BR-15)
             end_date    TEXT,                       -- YYYY-MM-DD or NULL (BR-15)
             PRIMARY KEY (student_id, course_code))
sessions    (session_id  TEXT PRIMARY KEY,           -- [V3] generated, never typed (BR-20, BR-21)
             course_code TEXT NOT NULL REFERENCES courses,
             session_date TEXT NOT NULL,             -- YYYY-MM-DD
             session_type TEXT NOT NULL              -- [V3]
                 CHECK (session_type IN ('Class', 'Tutorial')))
             -- [V3] unique (course_code, session_date) for Class sessions
attendance  (student_id  TEXT NOT NULL REFERENCES students,
             session_id  TEXT NOT NULL REFERENCES sessions,
             status      TEXT NOT NULL CHECK (status IN ('Present', 'Late', 'Excused', 'Absent')),
             source      TEXT NOT NULL,              -- 'manual' or the CSV filename
             recorded_at TEXT NOT NULL,              -- ISO timestamp
             PRIMARY KEY (student_id, session_id))
settings    (key   TEXT PRIMARY KEY,                 -- [V3] late_deduction, absent_deduction (BR-22)
             value TEXT NOT NULL)                    --      defaults 1 and 2
```

- `PRAGMA foreign_keys = ON` runs on **every** connection (inside `get_connection()`).
- **Unknown is never stored.** It is calculated: an enrolled student with no attendance row for a session of their course inside their enrollment dates (BR-15).
- `create_tables()` adds `start_date` and `end_date` to the `courses` and `enrollments` tables of an older `attendance.db` that lacks them (`ALTER TABLE ... ADD COLUMN`); old rows get NULL dates and behave as before.
- **[V3] Generated session IDs:** a class day is `PY101-2026-09-07`; a tutorial is `PY101-2026-09-10-T1` (`T1`, `T2`... when there are several on the same date).
- **[V3] Upgrade of an old database:** add the new columns and tables. Old sessions become type `Class`. Old courses keep working with `block_id` NULL (shown as "No block"). Existing records are kept.

## 4. Business rules

| ID | Rule |
|---|---|
| BR-01 | **Student ID:** exactly 3 ASCII digits, 001 to 999, stored as text (V1 rule). See BR-24. |
| BR-02 | **Full name:** V1 rules. Clean (collapse spaces, `’` to `'`, Unicode NFC), then letters/spaces/hyphens/apostrophes only, at least one letter, `-` and `'` need a letter on both sides, max 50 characters. |
| BR-03 | **Course code:** 2 to 10 ASCII letters or digits, at least one letter, stored UPPERCASE (`py101` becomes `PY101`). |
| BR-04 | **Course name:** 1 to 80 characters after trimming. |
| BR-05 | **Session ID:** 1 to 20 ASCII letters, digits, or hyphens, stored UPPERCASE. Unique across all courses. **[V3] Replaced:** session IDs are generated (BR-20, BR-21) and never typed. |
| BR-06 | **Session date:** a real calendar date in `YYYY-MM-DD` format (`2026-02-30` is rejected). **[V3] Changed:** still stored as `YYYY-MM-DD`, but files may also use `DD/MM/YYYY` and screens show `DD/MM/YYYY` (BR-23). |
| BR-07 | **Status:** accept `P`, `L`, `E`, `A`, `Present`, `Late`, `Excused`, `Absent` in any case; store the full word (`Present`, `Late`, `Excused` or `Absent`). |
| BR-08 | **One record per student per session.** Recording again for the same pair is an **edit**, not a new record. |
| BR-09 | Attendance can be recorded only for a student **enrolled** in the session's course. |
| BR-10 | **Attendance rate** = (Present + Late) / (Present + Late + Absent) x 100, 2 decimals. **Excused is not in the rate.** Shown as `N/A` when Present + Late + Absent = 0 (for example, only Excused records). |
| BR-11 | **Recording completeness** = (Present + Late + Excused + Absent) / Expected x 100, where Expected = the expected student-sessions (BR-15). `N/A` when Expected = 0. |
| BR-12 | **Unknown** = Expected - Present - Late - Excused - Absent. Unknown is never counted as Absent. |
| BR-13 | Every error message states what was wrong and what is expected. |
| BR-14 | **Absence streak:** counted per student per course, over that course's sessions in date order (then session ID), using only sessions inside the current filters. Consecutive Absent records form a streak; Present, Late and Excused end it, and Unknown also ends it (Unknown is not an absence and does not join two absences). **Longest streak** = the longest run anywhere. **Current streak** = the run of Absent counted back from the student's most recent session in that course (0 if that session is not Absent). |
| BR-15 | **Enrollment dates:** an enrollment has an optional `start_date` and `end_date` (`YYYY-MM-DD`). A student is **expected** at a session only if the session date is on or after `start_date` (when set) and on or before `end_date` (when set); both dates are included. NULL start = from the course's first session; NULL end = still enrolled. The end must not be before the start. Attendance can only be recorded for an expected session. |
| BR-16 | **Course dates:** a course has an optional `start_date` and `end_date` (`YYYY-MM-DD`); NULL means no limit on that side. A session's date must be inside its course's period (both dates included). The end must not be before the start. Course dates do **not** change who is expected at a session (that is BR-15). **[V3] Extended by BR-19:** a course in a block takes the block's dates by default. |
| BR-17 | **Enrollment inside course:** an enrollment's start must be on or before its end, and each set date must be inside the course period. A date equal to the course's start (or end) is stored as NULL, so the enrollment follows the course if the course dates change later. A course's dates cannot be changed so that an enrollment with its own dates falls outside them. Enforced in `validation.py` and `database.py`, not only in the date inputs. |
| BR-18 | **[V3] Block:** ID 2 to 10 letters, digits or hyphens (stored uppercase). Start date must be a **Monday**. End date = start + 18 days (Friday of week 3), calculated, never typed. Constant `BLOCK_WEEKS = 3`. |
| BR-19 | **[V3] Course in a block:** course dates default to the block dates. Exception: they may be narrowed, but must stay inside the block. |
| BR-20 | **[V3] Class days are generated:** when a course is created (or its dates change), one `Class` session is created for **every Monday to Friday** in the course period. Weekends never get class days. Removing a class day (holiday) is allowed, with confirmation; its records go with it. |
| BR-21 | **[V3] Tutorials:** added by hand, any date (weekends allowed) inside the course period. Several per week and several per date are allowed (numbered T1, T2...). Tutorials count exactly like classes for attendance, rates and deductions. |
| BR-22 | **[V3] Deductions:** per student per course: `Late × late_deduction + Absent × absent_deduction`. Defaults 1 and 2. **Excused and Present deduct 0. Unknown deducts 0 but is flagged** ("N not recorded"). **No maximum.** Both values are settings, editable on screen (whole numbers 0 to 10). |
| BR-23 | **[V3] Dates on screen and in downloads use `DD/MM/YYYY`.** Stored as `YYYY-MM-DD`. Files may use `DD/MM/YYYY` or `YYYY-MM-DD`. `07/09/2026` always means 7 September. |
| BR-24 | **[V3] Student ID rule lives in one function** (`validation.is_valid_student_id`). It stays 3 digits for now (BR-01). Future AIMS format: `AIMS` + academic year (4 digits, e.g. 2627) + 5 digits, e.g. `AIMS262766658`. |

**Worked example (use in a test and on a slide):** 7 Present, 2 Absent, 1 Unknown, so Attendance = 77.78% and Completeness = 90.00%.

**Worked example with Late and Excused:** 6 Present, 1 Late, 1 Excused, 1 Absent, 1 Unknown, so Attendance = (6 + 1) / (6 + 1 + 1) = 87.50% and Completeness = 9 / 10 = 90.00%.

**[V3] Worked example for deductions (BR-22):** 2 Late + 3 Absent = 2 × 1 + 3 × 2 = **8** marks with the defaults, or 2 × 2 + 3 × 3 = **13** with Late 2 / Absent 3. Excused and Unknown add 0.

## 5. CSV import rules

**Required columns, Version 2** (any order, header names case-insensitive, extra columns ignored):

```
session_id,course_code,session_date,student_id,full_name,status
```

**[V3] Replaced by these columns** (any order, case-insensitive; `session_id` is no longer used and is ignored if present):

```
course_code,date,student_id,full_name,status[,type]
```

`type` is optional: `Class` (default) or `Tutorial`. `date` may be `DD/MM/YYYY` or `YYYY-MM-DD` (BR-23).

| ID | Rule |
|---|---|
| IR-01 | File must be readable as UTF-8 (BOM allowed) and contain all required columns. Otherwise the **whole file** is rejected with a message naming the missing columns. |
| IR-02 | Each row is validated with BR-01 to BR-07. An invalid row is **rejected with a reason** (for example `Row 7: invalid student ID "12A", expected 3 digits 001-999`). |
| IR-03 | `course_code` must already exist. Otherwise: rejected, `Unknown course "BIO200", create it first`. |
| IR-04 | A new `student_id` creates the student. An existing ID with a **different name** (case-insensitive) is rejected as a conflict. **[V3] Changed by FR-31:** a similar name or a different name becomes a suggestion. |
| IR-05 | A new `session_id` creates the session. An existing session with a **different course or date** is rejected as a conflict. **[V3] Replaced by IR-12 and IR-13.** |
| IR-06 | The student is enrolled in the course automatically if not already enrolled. |
| IR-07 | **Exact duplicate** (same student, session, and status already saved, or repeated earlier in the file): **skipped and counted**. |
| IR-08 | **Conflicting status** (same student and session, different status): **rejected**. The existing record is **kept**. **[V3] Changed by FR-31:** a suggestion with "Keep saved" as the default. |
| IR-09 | Workflow: **Upload, Preview, Validate, Review issues, Confirm, Result.** Nothing is written before Confirm. |
| IR-10 | Saved rows record the filename in `source`. |
| IR-11 | The result shows counts: accepted, skipped duplicates, rejected. Rejected rows can be downloaded as CSV with a `reason` column. |
| IR-12 | **[V3] Class row:** must match an existing class day of that course. A weekend or a removed day is rejected: `Row 7: PY101 has no class on Saturday 12/09/2026.` A removed weekday says so: `Row 10: DS102 has no class on Wednesday 16/09/2026 (class day removed).` |
| IR-13 | **[V3] Tutorial row:** creates the tutorial if none exists on that date, inside the course period. |
| IR-14 | **[V3]** Duplicates, conflicts, enrollment periods and unknown courses work as in Version 2, except where FR-31 turns a rejection into a suggestion. |

### [V3] Auto-fix and suggested fixes (FR-31)

**The program never invents a new identity on its own.** It repairs what is safe and proposes the rest for a person to accept.

| Problem | Action |
|---|---|
| Spaces, capitals, `p` / `absent`, curly apostrophes | **Auto-fix** (as before) |
| ID `4` or `04` (Excel removed zeros) | **Auto-fix** to `004`, listed as a fix |
| Date `24/9/2026` or `2026-09-24` | **Auto-fix** to `24/09/2026`, listed as a fix. `DD/MM/YYYY` (zero-padded) is the normal form and is not a fix (BR-23). |
| Saved ID, **similar** name (difflib ratio ≥ 0.8, e.g. `Eric Niyonzimana` vs `Eric Niyonzima`) | **Suggest:** "Use saved name Eric Niyonzima" (Accept / Reject) |
| Saved ID, **different** name | **Suggest:** "Assign next free ID 013 as a new student" (Accept / Reject) |
| Same new ID twice in the file with different names | **Suggest** the next free ID for the later rows |
| Status differs from the saved record | **Suggest:** "Keep saved Absent" (default) or "Use file: Present" |
| **[3.1]** Class row on a weekend or a removed class day | **Suggest (S5):** "Import as tutorial on that date" (Accept / Reject) |

- The review screen shows three lists: **Auto-fixed** (read-only, with before → after), **Suggestions** (a checkbox per row, all unticked by default), **Rejected** (with reasons).
- **Apply suggestions** re-validates. Nothing is saved before **Confirm**, and Confirm still uses one transaction.
- **Download cleaned file:** the file with all auto-fixes and accepted suggestions applied, in the new column format.
- Every fix and accepted suggestion is listed in the result, so the tutor can see exactly what changed.

## 6. Functional requirements

| ID | Tab | The system shall... |
|---|---|---|
| FR-01 | All | Show 4 tabs: Dashboard, Manage Attendance, Import & Validate, Reports. |
| FR-02 | All | Keep all data in `attendance.db` so it survives closing the app. |
| FR-03 | Manage | Create a course (BR-03, BR-04). Duplicate course codes are rejected. **[V3] Changed:** a course is created in a block (BR-19), and its class days are generated (BR-20). |
| FR-04 | Manage | Add a student (BR-01, BR-02): student ID and full name only. A repeated name shows a warning and needs confirmation (V1 rule). A new student starts with no course ("Not enrolled" in search). |
| FR-05 | Manage | "Enroll a student in a course" is the only manual way to enroll: Student and Course only. The enrollment always covers the full course period (start and end stored as NULL, so it follows the course, BR-17). Success message: `001 enrolled in PY101 for the full course period (2026-09-07 to 2026-12-18).` A late start or early leave is set afterwards (FR-24). **[V3]** The period in the message uses `DD/MM/YYYY` (BR-23); enrolling moves to the student profile (Section 6.1). |
| FR-06 | Manage | Create a session for a course (BR-05, BR-06). **[V3] Replaced:** class days are generated (BR-20) and tutorials are added by date (BR-21) in the "Class days & Tutorials" sub-tab. |
| FR-07 | Manage | Record attendance for a session: list every enrolled student with a Present/Late/Excused/Absent choice (blank = Unknown), save all at once. **[V3] Changed:** pick block → course → day, defaulting to today if today is a class day, with a **"Mark all Present"** button. |
| FR-08 | Manage | Correct attendance: re-open a session, change statuses, save. Unchanged rows are not rewritten. |
| FR-09 | Manage | Search students by exact ID or by exact cleaned name (case-insensitive); show all matches with their courses. **[V3]** Selecting a match opens the student profile (Section 6.1). |
| FR-10 | Import | Implement the import workflow in Section 5. |
| FR-11 | Import | Offer a downloadable empty CSV template with the required columns. **[V3]** The template uses the Version 3 columns. |
| FR-12 | Dashboard | Filter by course (or All courses) and date range. Show the active filters. **[V3] Replaced by FR-30.** |
| FR-13 | Dashboard | Show metrics: students, sessions, Present, Late, Excused, Absent, Unknown, attendance rate, completeness. | **[3.1]** Shown as KPI cards (Section 11, Stage 7).
| FR-14 | Dashboard | Show one chart: attendance rate by session, in date order. | **[3.1]** Drill-down: by block, course, week or day (Section 11).
| FR-15 | Dashboard | List students below a chosen threshold (slider, default 75%), sorted by rate. |
| FR-16 | Reports | A "Student" selector at the top defaults to "All students", which shows the overall Present, Late, Excused, Absent, Unknown, rate and completeness, a per-student summary (the same five counts, rate, completeness), and the filtered attendance table (student, course, session, date, status). **[V3]** The per-student summary adds "Deducted marks" (FR-29). |
| FR-17 | Reports | Download both tables as CSV. **Downloads match exactly what is on screen.** |
| FR-18 | All | Show a clear message instead of an empty table or chart when there is no data. |
| FR-19 | Reports | Single student report: choosing a student ("ID - Name") in the FR-16 selector replaces the All students view; using the course and date filters, show their Present, Late, Excused, Absent, Unknown, attendance rate and completeness, a per-course breakdown, and their session history (session, course, date, status) in date order with missing records shown as Unknown. The history can be downloaded as CSV, matching the screen. **[V3]** Adds deducted marks per course (FR-29). |
| FR-20 | Dashboard | Show a second chart below the FR-14 chart, "Recording status by session": one stacked bar per session with its Present (`#0072B2`), Late (`#56B4E9`), Excused (`#CC79A7`), Absent (`#E69F00`) and Unknown (`#999999`) counts, in that order, using the same filters, labels and session order as FR-14. Sessions with no records are included as all Unknown. Each bar's total equals the students enrolled in that session's course. | **[3.1]** At the same drill-down level as FR-14.
| FR-21 | Dashboard, Reports | **Absence alerts** (Dashboard, below the threshold list): a number input "Alert when current streak is at least" (default 2, minimum 1) lists every student and course whose current streak (BR-14) reaches it, with student ID, name, course, current streak, longest streak and date of last absence, highest current streak first. If nobody matches, a success message says so. In the Reports single-student view, the "By course" table (shown even for one course) adds the longest and current absence streak per course. |
| FR-22 | Manage (Edit & Delete) | **Rename** a student's full name (BR-02 cleaning and validation, and the same-name warning with confirmation as in FR-04, ignoring the student's own name) or a course's name (BR-04). Student IDs and course codes never change. If the new value equals the old one, show "No change". **[V3]** Moves to the student profile and to Blocks & Courses (Section 6.1). |
| FR-23 | Manage (Edit & Delete) | **Delete**, each in one database transaction that returns the counts removed: one attendance record (the student becomes Unknown for that session); an enrollment, with the student's records for that course's sessions; a student, with all their records and enrollments (the ID can be used again); a session, with its records; a course, only when it has no sessions and no enrolled students (otherwise an error says how many sessions and students must be removed first) **[V3] replaced: see Section 11, Delete course**. Every delete first shows what will be removed, with counts, and the Delete button works only after ticking "I understand this cannot be undone". **[V3]** Each delete moves to the sub-tab of the thing it removes (Section 6.1); removing a class day or tutorial is in "Class days & Tutorials"; a block can be deleted only when it has no courses. |
| FR-24 | Manage, Import, Reports | **Enrollment dates (BR-15).** Enrolling (FR-05) always covers the full course period; dates are only set for exceptions. Record Attendance lists only students expected at the session, and `record_attendance()` returns `outside_enrollment` without saving for a date outside the window. Edit & Delete has "Late start or early leave", captioned "Use this only when a student joins after the course starts or leaves before it ends." (only the student's courses, pre-filled with the current dates, a date not set shown as the course's, limited to the course period), refused (with the number of records affected) if saved attendance would fall outside the new dates. Import: a new enrollment starts at the student's earliest session date for that course in the accepted rows; for an existing enrollment, a row outside its dates is rejected (for example `Row 7: Student 004 is enrolled in PY101 from 2026-09-14, not on 2026-09-07.`). The Reports "By course" table shows "Enrolled from" and "Enrolled until" ("start" / "now" when not set). **[V3]** "Late start or early leave" moves to the student profile. |
| FR-25 | Manage, Import, Dashboard, Reports | **Course dates (BR-16).** Create course asks for "Start date" and "End date" and refuses an end before the start. Create session refuses a date outside the period (`PY101 runs from 2026-09-07 to 2026-12-18. Choose a date in that period.`); import rejects such a row (`Row 7: PY101 runs from 2026-09-07 to 2026-12-18, not on 2027-01-05.`). Edit & Delete has "Change course dates", refused (with the number affected) if a session or an enrollment with its own dates (BR-17) would fall outside the new period. Every date input shows dates as `YYYY-MM-DD`. The Courses sub-tab lists every course with its period, and course labels show it (`PY101 - Programming with Python (2026-09-07 to 2026-12-18)`). When one course is chosen in the Dashboard/Reports filters, the date range starts as that course's period (or its session dates where the period is not set). **[V3] Changed:** course dates default to the block and stay inside it (BR-19); changing them regenerates class days (BR-20), refused with counts if saved records would be lost; dates are shown as `DD/MM/YYYY` (BR-23); "Change course dates" moves to Blocks & Courses. |
| FR-26 | All | **Late and Excused statuses (BR-07, BR-10 to BR-12, BR-14).** Four saved statuses: Present, Late, Excused, Absent (Unknown is still never stored). Record Attendance, import, Dashboard metrics, the recording status chart and its filter, Reports and the student report all include Late and Excused. `create_tables()` upgrades an older attendance table (whose CHECK allows only Present and Absent) by creating a new table, copying every row, dropping the old table and renaming the new one, in one transaction. |
| FR-27 | Reports | **[V3] Weekly view:** select a student and a course; show a grid with one row per week (`Week 1 (07/09)`) and columns Mon, Tue, Wed, Thu, Fri and Tutorials. Cell symbols: ✅ Present, 🕐 Late, 📝 Excused, ❌ Absent, ❔ Not recorded, — no class (removed day, or outside the enrollment period). The Tutorials column lists every tutorial that week as `DD/MM symbol`. Under the grid: Present, Late, Excused, Absent, Unknown, rate, completeness and **deducted marks**. CSV download. |
| FR-28 | Reports | **[V3] Class register:** select a course (and optionally a week). Rows = enrolled students, columns = every class day and tutorial (`Mon 07/09`, `Tut 10/09`), cells = P / L / E / A / ?, then totals and a **Deducted** column. Sorted by student ID. CSV download. |
| FR-29 | All | **[V3] Deductions everywhere (BR-22):** a "Deducted marks" column in the per-student summary, the student profile, the student report and all downloads; Unknown is flagged as "N not recorded". **Deductions export:** one CSV per course with student ID, name, Late, Absent and deducted marks, ready for the grade sheet. |
| FR-30 | Dashboard, Reports | **[V3] Filter:** Block → Course (the course list is limited to the chosen block) → date range (defaults to the block or course period). Replaces FR-12. | **[3.1]** Block → Course → Week, with "Custom dates" for the range.
| FR-31 | Import | **[V3] Auto-fix and suggested fixes:** see "Auto-fix and suggested fixes" in Section 5. |

### 6.1 [V3] Manage Attendance sub-tabs

The separate "Edit & Delete" sub-tab is **removed**. Everything about a thing lives in its own sub-tab.

| Sub-tab | Contains |
|---|---|
| **Blocks & Courses** | Create block (start Monday → end calculated). Create course in a block (dates default to the block; optional narrower period). List of blocks with their courses. Per course: rename, change period (inside block, class days regenerate), enrolled students, delete (rules from FR-23). Delete block only when it has no courses. |
| **Students** | Search first. Selecting a student opens a **student profile**: courses with enrollment period, attendance counts, rate, completeness, **deducted marks per course**, rename, enroll / un-enroll, late start or early leave, delete. Below: Add student. |
| **Class days & Tutorials** | Pick a course: list of class days (DD/MM/YYYY, weekday) and tutorials. Add tutorial (date inside course period). Remove a class day or tutorial (holiday), with confirmation and record count. |
| **Record attendance** | Pick block → course → day. **Defaults to today** if today is a class day. Button **"Mark all Present"**, then change the exceptions. Statuses as before. |
| **Settings** | Late deduction and Absent deduction (whole numbers 0 to 10). |

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
attendance/
├── ATTENDANCE_SPEC.md         # this specification (Version 3)
├── ATTENDANCE_V3_CHANGES.md   # Version 3 change log and build prompts
├── validation.py      # pure functions: is_valid_student_id, clean_name, is_valid_name,
│                      #   normalize_course_code, is_valid_session_id, parse_date, normalize_status
├── database.py        # get_connection, create_tables, and one function per query/insert
├── analytics.py       # calculate_rates, build_student_summary, build_session_summary (Pandas, no UI)
├── importer.py        # read_csv, validate_rows -> (accepted, duplicates, rejected), apply_import
├── app.py             # Streamlit UI only: 4 tabs that call the modules above
├── seed_demo.py       # creates a clean demo database
├── demo_data/
│   ├── clean_import.csv
│   └── messy_import.csv   # every auto-fix, suggestions S1 to S4, rejections, duplicates
│                          # [V3] and every auto-fix and suggestion type
├── tests/                 # one test file per module or feature
├── requirements.txt   # streamlit, pandas
├── TRACEABILITY.md    # requirement -> function -> test
└── TEST_CHECKLIST.md  # manual checks for the demo
```

## 9. Known limitations

- No login: anyone at the computer can change records.
- Accented and unaccented names (`Émile` / `Emile`) are different.
- Validation checks format and consistency, not truth.
- ~~A session ID is not tied to its course name: `PY101-W5` can be created for course DS102.~~ **[V3] Solved:** session IDs are generated from the course code and date.
- **[V3]** Student IDs are 3 digits, not yet the AIMS format (BR-24).
- **[V3]** One Class session per course per day.
- **[V3]** A course belongs to exactly one block.

## 10. Minimum tests

| Test | Checks | Req |
|---|---|---|
| T01 | `001`, `999` valid; `000`, `1`, `1000`, `12A`, `+01`, `٠٠١` invalid | BR-01 |
| T02 | `Jean-Paul`, `O’Neil` (to `O'Neil`) valid; `-Nadia`, `Jean--Paul`, `Jean - Paul`, 51 letters invalid | BR-02 |
| T03 | `py101` becomes `PY101`; `1`, `123`, `PY 101` invalid | BR-03 |
| T04 | `2026-09-15` valid; `2026-02-30`, `15/09/2026`, empty invalid. **[V3] Changes:** `15/09/2026` becomes valid input in files (BR-23). | BR-06 |
| T05 | `p`, `PRESENT`, ` a `, `L`, `late`, `e`, `EXCUSED` accepted; `maybe`, `x` rejected | BR-07 |
| T06 | 7 Present, 2 Absent, 1 Unknown gives 77.78% and 90.00% | BR-10, BR-11 |
| T07 | 0 records gives `N/A`, no division error | BR-10, BR-11 |
| T08 | CSV missing `status` column: whole file rejected, names the column | IR-01 |
| T09 | Unknown course: row rejected with reason | IR-03 |
| T10 | Same row twice: one accepted, one skipped | IR-07 |
| T11 | Different status for saved record: rejected, existing kept. **[V3] Changes:** a suggestion, "Keep saved" by default (FR-31). | IR-08 |
| T12 | Existing ID with a different name: rejected. **[V3] Changes:** a suggestion to assign the next free ID (FR-31). | IR-04 |
| T13 | Recording twice for the same student and session updates instead of duplicating | BR-08 |
| T14 | Foreign keys on: attendance for a missing session raises an error | Section 3 |

**[V3]** Each build stage adds tests for its rules (see the change log): block dates, class-day
generation, tutorials, the old-database upgrade, the deductions worked example, the weekly view
and class register, and every auto-fix and suggestion type.

Tests use a **temporary database** (`:memory:` or a temp file), never `attendance.db`.

## 11. Implementation decisions

Decisions made while building, where the sections above did not say what to do.

| Topic | Decision |
|---|---|
| BR-08, FR-08 | `record_attendance()` returns `inserted`, `updated`, `unchanged` or `not_enrolled`. An unchanged status is not rewritten. |
| BR-09 | `record_attendance()` checks enrollment itself and returns `not_enrolled` without saving. A missing session is left to the foreign key, which raises an error (T14). |
| FR-07 | A student left blank in the recording table is not saved and stays Unknown. |
| FR-04 | The same-name confirmation is a checkbox in the Add student form. |
| FR-06 | The session date is typed as `YYYY-MM-DD` text and checked with BR-06. **[V3] Replaced** (sessions are generated). |
| IR-02 | Row numbers match the file as seen in a spreadsheet: the header is row 1, the first data row is row 2. Format errors quote the value found. |
| IR-04, IR-05, IR-08 | Consistency is also checked **inside the file**: a new student ID with two names, a new session ID with two courses or dates, or one student and session with two statuses. The first row is kept and the later one is rejected. **[V3] Changed:** a new ID with two names becomes a suggestion (FR-31). |
| IR-07 | Duplicates are listed with their reason (`Repeats row N` or `Already saved with the same status`). |
| IR-09 | Confirm saves all accepted rows in **one transaction**: if any row fails, nothing is saved and the user is asked to validate again. Validation only reads the database. The validation result is kept in `st.session_state` and cleared after a successful import, so Confirm cannot run twice. |
| FR-12 | The course and date filters are in the sidebar and apply to both the Dashboard and Reports. The date range defaults to the earliest and latest session dates. **[V3]** The block filter comes first (FR-30). |
| FR-14 | Sessions with no recorded status have no rate and are left out of the chart. |
| FR-15 | "Below the threshold" means strictly lower than it. Students with no recorded sessions (rate N/A) are listed in a separate table. |
| FR-27 to FR-31 | **[V3]** Numbered one up from the tutor-feedback draft, because FR-26 was already used (see the change log). |
| BR-19, FR-03 | **[V3, Stage 2]** Create course: the dates default to the block. An optional **"Shorter period"** checkbox narrows them inside the block at creation (the date inputs are limited to the block), and class days are generated for that period only. |
| FR-23 | **[V3, Stage 2] Delete course** replaces the Version 2 "only when it has no sessions and no enrolled students" rule (class days are generated, so every course has sessions). It previews the counts of class days, tutorials, enrollments and attendance records, needs the "I understand this cannot be undone" tick, and deletes everything in one transaction. |
| Section 6.1 | **[V3, Stage 2] Delete block:** only when it has no courses; otherwise an error says how many courses must be deleted first. |
| BR-20, BR-21 | **[V3, Stage 2] Remove a class day or tutorial** (for example a holiday): previews the number of attendance records it deletes and needs the same tick. |
| FR-07 | **[V3, Stage 2]** Record attendance: pick block → course → day; the day defaults to today when today is a class day of that course. **"Mark all Present"** fills only the students who have no status yet (a saved status is never overwritten), then the exceptions are changed and saved. "Delete one attendance record" is in this sub-tab, for the chosen day. |
| FR-09, Section 6.1 | **[V3, Stage 2]** A search opens the first match in the **student profile**; adding a student opens their new profile, where they are enrolled. The profile holds enroll, late start or early leave, rename, un-enroll and delete for that student. |
| BR-22 | **[V3, Stage 3]** The deductions are stored in the `settings` table (`late_deduction`, `absent_deduction`, defaults 1 and 2; `create_tables()` adds the table and defaults to an older database). Manage > Settings saves both values together; anything that is not a whole number from 0 to 10 is refused with a BR-13 message and nothing is saved. "Reset demo data" puts the defaults back. |
| BR-22, FR-29 | **[V3, Stage 3]** The formula lives in one function, `analytics.calculate_deduction()`, which always receives the current settings. Screens add two columns: **"Deducted marks"** and **"Note"** (`N not recorded` when Unknown > 0, otherwise empty). They appear in the per-student summary, the student profile, the single-student report (as metrics and in the by-course table) and their downloads. |
| FR-27 | **[V3, Stage 4]** The **weekly view** is in the single-student report: pick one of the student's courses. It always covers the whole course (not the sidebar dates), so every week is complete. A tutorial after the first on the same date is labelled "23/09 (T2)". The CSV download uses plain words (Present, Late, Excused, Absent, Not recorded, No class) instead of symbols. |
| FR-28 | **[V3, Stage 4]** The **class register** is in the All students view, with its own Block → Course picker and a Week box ("All weeks" or one week). With one week, only that week's columns are shown and the totals, rate and deducted marks count that week only. The download is the table itself. |
| FR-30 | **[V3, Stage 4]** The sidebar filter is Block ("All blocks", each block, and "No block" for courses of an older database) → Course (that block's courses, or "All courses") → date range. The range starts as the course's period, else the block's, else the first and last session dates. The caption names the block, the course and the dates. |
| FR-29 | **[V3, Stage 3]** The **Deductions export** is in Reports (All students view): one course at a time, using the sidebar filters, with the columns Student ID, Full name, Late, Absent, Excused, Not recorded (a count) and Deducted marks, sorted by student ID; the file is named `deductions_<COURSE>.csv`. |
| FR-31 | **[V3, Stage 5] Auto-fixes** run on every row before validation (`importer.auto_fix_row()`): spaces, curly apostrophes, course/status/type capitals, P/L/E/A, IDs of 1 or 2 ASCII digits padded to 3 (`0` and `00` are not fixed), dates `D/M/YYYY` and `YYYY-MM-DD` → `DD/MM/YYYY` (**[Stage 6]** zero-padded `DD/MM/YYYY` is the normal form and is not listed; every date is still stored as `YYYY-MM-DD`), and type `tut`/`tutorial`/`class` in any case. An empty type stays empty (it already means Class). Names never change except spaces and apostrophes. Each fix is listed as row, column, before → after and why, including fixes on rows rejected later. A value that cannot be fixed keeps its original text, so the reason quotes what the file contained. Typed dates elsewhere in the app still need the exact form (`parse_date` is unchanged). |
| FR-31 | **[V3, Stage 5] Suggestions** are checked in the order of Version 2: S1/S2 (saved ID, name differs) and S3 (new ID with a second name in this file) at the student check, S4 (status differs from the saved record) at the status check. S1 needs `difflib.SequenceMatcher` ratio ≥ 0.8 on casefolded names; otherwise S2. **Next free ID** = the lowest 3-digit ID that is not saved, **not used anywhere in the file** (so a proposal cannot clash with a later row) and not already proposed. The same (file ID, casefolded name) pair always gets the same ID. A row whose suggestion is not accepted stays rejected; its reason is the Version 2 reason plus `Suggestion: "..."`. A conflict between two rows of the file about a status is still rejected with no suggestion. **Earlier rows of the file are checked before the saved record:** once a student and session appeared in the file (accepted, or with an S4 suggestion even if not accepted), a later row with the same status is a duplicate and a different status is an in-file conflict ("Student 001 already has Late for PY101 on Monday 07/09/2026 earlier in this file (row 2), not Absent. The first row is kept."). So only the first row can get S4, and two rows can never both overwrite a saved record. Because suggestions are checked in order, accepting S1 can reveal an S4 on the next Apply. |
| FR-31 | **[V3, Stage 5] Review screen:** counts (Auto-fixes, Accepted suggestions "N of M", Accepted, Skipped duplicates, Rejected), then **Auto-fixed** (read-only table), **Suggestions** (a form: a tick per S1–S3 row, a "Keep saved X" / "Use file: Y" choice per S4 row, all unaccepted by default) with **Apply suggestions**, the accepted and duplicate rows, **Download cleaned file** and **Rejected** with its own download. Validate again resets every suggestion to unaccepted. The cleaned file has the accepted and duplicate rows in file order, in the Version 3 columns, with dates as DD/MM/YYYY (BR-23), so importing it again needs no auto-fixes. Importing the **original** file again after Confirm proposes new IDs for its S2/S3 rows (the IDs proposed before are now saved), so import the cleaned file instead. **"Use file"** sets `update` on the row; `import_records()` then runs an UPDATE (status, source = filename, recorded_at) inside the same transaction as the inserts. The result message lists auto-fixes, accepted suggestions, saved rows (inserted + updated), duplicates and rejected. |
| IR-12 | **[V3, Stage 6]** A class row on a weekday with no class, in a course whose class days were generated (it has dates), ends with "(class day removed)". A weekend keeps the plain message, and so does an older course without dates, whose class days were added by hand. |
| Stage 7 (3.1) | **No rule or stored data changes.** Seed totals stay 505 expected, 477 / 10 / 4 / 10 / 4, 97.99%, 99.21%. |
| FR-30 | **[3.1] Sidebar:** Block → Course → **Week**. With one block, the Week box lists "All weeks" and "Week N (DD/MM–DD/MM)" (Monday to Friday in the label); a week filters Monday to **Sunday**, so a weekend tutorial belongs to the week before it (`analytics.build_week_options`). A **"Custom dates"** checkbox shows the date range, starting at the chosen week or period; with "All blocks" (or "No block") it is the only extra choice. The caption names the week, else the dates. |
| FR-13 | **[3.1] KPI cards:** one row of bordered cards (`st.container(border=True)`): Attendance rate, Completeness, Deducted marks (total of Late x late deduction + Absent x absent deduction for the filtered records, from the settings), Students below threshold (the threshold slider's value; the slider is further down the page, its value is read from `st.session_state`), Absence alerts (student-course rows with the current streak of at least the alert box's value). Under them a line of status counts with a dot in the chart colour (Present, Late, Excused, Absent, Not recorded) and a caption "12 students · 44 class days · 6 tutorials". `analytics.calculate_kpis()` computes them. The old "Sessions" metric is replaced by the class days and tutorials counts. |
| FR-14, FR-20 | **[3.1] Drill-down charts:** `analytics.build_drilldown_chart_data()` chooses the level from the filters (`choose_chart_level`): All blocks with **several blocks** → one bar per block (courses without a block are one "No block" bar); All blocks with **only one block** in the records (as in the demo data, where a single block bar says little), one block chosen, or "No block" → one bar per course of that block (`count_blocks`); one course → one bar per week (counted from the course's start, else the block's), or per date with the **"Show by day"** toggle (a tutorial on a class day shares that day's bar). Titles follow the level ("Attendance rate by course", "Recording status by week"). Rate bars show their % and the axis is 0–100; bars with no recorded status are left out of the rate chart but kept in the status chart. Both charts use the same bars; the status chart keeps its colours and status filter. |
| Section 6.1 | **[3.1] Students:** the profile has a title with the student ("002 - Jean-Paul Mugisha") and every section names them ("Rename 002 - Jean-Paul Mugisha"). A search says "1 match, showing 002" or "N matches, showing 002; choose another in the Student box". Under "Add a student": "Only enrolled students appear in Record attendance, the Dashboard and the class register. Enroll the new student in a course from their profile." |
| BR-20, BR-21, FR-16, FR-19 | **[3.1] No session IDs on screen or in downloads.** A session is shown as Date + Day + Type, where Type is "Class" or "Tutorial T2" (`analytics.describe_session_type`). Class days table: Date, Day, Type, Records saved, Not recorded. Attendance report: Student ID, Full name, Course, Date, Day, Type, Status. Student history: Course, Date, Day, Type, Status. Day pickers and delete previews use "Mon 07/09/2026 - Tutorial T1". Import reasons name the session by course, day and date, adding the tutorial number for a tutorial ("PY101 on Tuesday 08/09/2026", "PY101 on Thursday 10/09/2026 (Tutorial T1)"). IDs stay in the database. `get_expected_records()` now also returns the session type and the course's block. |
| FR-31 | **[3.1] Fix rejected rows in place:** the Rejected section is an editable table (course_code, date, student_id, full_name, status and type editable; row and reason read-only), showing the file's text after earlier edits. **Re-check** merges the changed cells into the edits kept in `st.session_state` by row number (`importer.collect_edits`) and validates the whole file again with them and the accepted suggestions (`review_rows(..., edits)`). Each edit is listed first in Auto-fixed as "edited by you: before -> after"; an edit back to the file's value is not listed. Edits are in the cleaned file and saved only at Confirm; Validate starts again with no edits. The result message adds "Edited by you: N". |
| FR-31 | **[3.1] S5:** a Class row on a weekend, or on a removed class day of a course with generated class days, suggests "Import as tutorial on that date". Accepted, the row's type becomes Tutorial and it uses the first tutorial on that date, or a new one planned like IR-13. A weekday with no class in an older course without dates gets no suggestion. |
| NFR-03 | Lines are at most 99 characters (PEP 8 allows 99 when a project agrees on it). |

## 12. [V3] Demo data

Replaces the Version 2 demo data (2 courses, 4 sessions each; totals 63 Present / 9 Absent / 4 Unknown,
87.50%, 94.74%; kept for the tests as `tests/v2_data.py`). **Version 3 totals (Stage 1):**
505 expected, 477 Present, 10 Late, 4 Excused, 10 Absent, 4 Unknown, attendance 97.99%,
completeness 99.21%.

- Block `B1-2627`, "Block 1, 2026-27", 07/09/2026 to 25/09/2026.
- 3 courses: PY101 Programming with Python, DS102 Data Science Basics, MA103 Mathematics for Data Science.
- 12 students. Most in all three courses, a few in two, one **late joiner** (from week 2) and one **early leaver**.
- 15 class days per course, **one removed as a holiday** in one course, and **2 tutorials per course**.
- A realistic mix of Present, Late, Excused and Absent, a few Unknown, at least one student with 2+ absences in a row, at least one with deductions over 10.
- Fixed data: every run gives the same numbers. `seed_demo.py` prints the totals **and the deductions per student per course**. At least two students are verified by hand and put in tests.
- `demo_data/messy_import.csv` and `clean_import.csv` are rewritten for the new columns. The messy file triggers every auto-fix and every suggestion type, plus the usual rejections.
- **[Stage 5, 3.1] messy_import.csv** (19 rows): 39 auto-fixes and 7 suggestions (S5 for rows 9 and 10, S1, S2 twice for the same pair → 013, S3 → 015, S4). With no suggestion accepted: 6 accepted / 2 duplicates / 11 rejected; after Confirm 479 P / 11 L / 6 E / 11 A / 15 Unknown, 522 expected, 97.80%, 97.13%. With all accepted: 13 / 2 / 4; after Confirm 485 / 11 / 6 / 11 / 41, 554 expected, 97.83%, 92.60% (S5 adds tutorials on PY101 Saturday 12/09 and the DS102 holiday 16/09).

---

# Version 2 build history

The rest of this file records how Version 2 was built. It is kept for reference; the Version 3
build prompts are in [ATTENDANCE_V3_CHANGES.md](ATTENDANCE_V3_CHANGES.md).

## Build plan: 4 hours

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

## Version 2 prompts for Claude in VS Code

These prompts used the file's old name, `ATTENDANCE_V2_SPEC.md`.

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

## Version 2 demo script (about 5 minutes)

**[V3]** This script uses the Version 2 demo data; it will be updated when Version 3 is finished.

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
