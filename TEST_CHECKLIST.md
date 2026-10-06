# Attendance V2: Full Test Checklist

**Before every round:** run `.venv\Scripts\python seed_demo.py`, restart Streamlit, refresh the browser.
Starting point is always: **63 Present, 9 Absent, 4 Unknown, 87.50%, 94.74%**.

✔ = I already ran this case on a copy of your database, and the expected result below is what the code actually does.

**Seed data, so you know what's there:**
- Courses: **DS102** (Data Science Basics, runs 2026-09-09 to 2026-12-18), **PY101** (Programming with Python, runs 2026-09-07 to 2026-12-18)
- PY101 students: 001 to 010. DS102 students: 004 to 012. (004 to 010 are in both.)
- Sessions: PY101-W1 to W4 (09-07, 09-14, 09-21, 09-28), DS102-W1 to W4 (09-09, 09-16, 09-23, 09-30)
- The 4 Unknowns: 003 in PY101-W2, 008 in DS102-W3, 012 in DS102-W3, 010 in PY101-W4

---

## 0. Fixed: message when a saved status is cleared

| # | Do | Expected |
|---|---|---|
| 0.1 | Record Attendance → pick a session → **clear** a student who is already Present (empty the cell) → Save | ✔ **Fixed.** The record is kept (still Present), and a warning says *"1 saved status(es) were cleared on screen but kept. To delete a record, use Manage Attendance > Edit & Delete."* Only students who had no saved status are reported as *"left blank. They stay Unknown."* |

The fix prompt that was used is kept at the end of this file for reference.

---

## 1. Startup and saved data

| # | Do | Expected |
|---|---|---|
| 1.1 | Start the app | 4 tabs: Dashboard, Manage Attendance, Import & Validate, Reports. No Deploy button. |
| 1.2 | Add a course, close the app (Ctrl+C), start it again | The course is still there (**saved in SQLite**). |
| 1.3 | Run `seed_demo.py` | **Everything you added is deleted** and the demo data comes back. Never run it on real data. |
| 1.4 | Delete `attendance.db`, start the app | No crash. Empty tables are created. Dashboard says there's no data yet. |
| 1.5 | Run `.venv\Scripts\python -m unittest` | All tests OK. |

## 2. Manage → Courses

| # | Do | Expected |
|---|---|---|
| 2.1 | Create `ML201` / `Machine Learning` | Success. |
| 2.2 | Create `ml201` again | Error: already exists (codes become UPPERCASE, so `ml201` = `ML201`). |
| 2.3 | Codes `P`, `12345`, `PY-101`, `PY 101`, `ABCDEFGHIJK` (11) | Each rejected with the course-code message. |
| 2.4 | Empty course name, or 81+ characters | Rejected. |
| 2.5 | Two different codes with the **same name** | Allowed. Only the code must be unique. |
| 2.6 | Can I rename or delete a course? | **Yes**, in Manage → **Edit & Delete** (see section 11). The code never changes; a course can only be deleted when it has no sessions and no students. |
| 2.7 | Create a course: look at "Start date" and "End date" | ✔ Start defaults to today, end to 16 weeks later. |
| 2.8 | Create a course with the end **before** the start | ✔ Error: "The end date must be on or after the start date." |
| 2.9 | Courses sub-tab, below the form | ✔ A list of every course with its start and end date. |
| 2.10 | Any course dropdown (Record, Sessions, sidebar…) | ✔ Labels show the period: `PY101 - Programming with Python (2026-09-07 to 2026-12-18)`. |

## 3. Manage → Students (search, add, enroll)

| # | Do | Expected |
|---|---|---|
| 3.1 | Search ID `001` | Nadia Hirwa, courses PY101. |
| 3.2 | Search ID `004` | Shows **DS102, PY101** (in two courses). |
| 3.3 | Search ID `099` | "No student found". |
| 3.4 | Search ID `1`, `12A`, `٠٠١` | ID error message (not "not found"). |
| 3.5 | Search name `nadia   HIRWA` | Finds 001 (spaces cleaned, case ignored). |
| 3.6 | Search name `Nadia` (partial) | **No result.** Search is exact full name only (by design; partial search is Future Work). |
| 3.7 | Add `013` / `Emile Uwase` (the form has only ID and name) | ✔ "Student 013 - Emile Uwase added. Enroll them in a course below." Search for 013 shows **Not enrolled**. |
| 3.7b | Enroll a student in a course: 013 → PY101, dates left as they are | ✔ The dates start as PY101's period (2026-09-07 to 2026-12-18) and cannot go outside it. Success. |
| 3.8 | Add `013` again with another name | Error: ID already used. |
| 3.9 | Add `014` / `NADIA HIRWA` | **Warning** (same name as 001). Tick the box, submit again → saved, with no course yet. |
| 3.10 | Names `-Nadia`, `Nadia-`, `Jean--Paul`, `Jean - Paul`, `O''Neil`, `Nadia123`, `@`, spaces only | Each rejected. |
| 3.11 | Name `O’Neil` (curly apostrophe) | Saved as `O'Neil`. |
| 3.12 | Name `Émile` | Accepted. |
| 3.13 | Name with 51 letters | Rejected. 50 is accepted. |
| 3.14 | Enroll 001 in DS102, dates left at DS102's period | Success. 001 is Unknown for all 4 DS102 sessions (Dashboard Unknown 4 → 8). With "Enrolled from" = `2026-09-23` instead (a late joiner), only W3 and W4 are expected (Unknown 4 → 6). |
| 3.14b | Switch the Course box from PY101 to DS102 before enrolling | ✔ "Enrolled from" / "Enrolled until" jump to DS102's dates (2026-09-09 / 2026-12-18), and dates outside DS102 cannot be picked. |
| 3.15 | Enroll 001 in DS102 again | Error: already enrolled. |
| 3.16 | Can I add a student without a course? | **Yes.** Add Student only saves the ID and name. Enroll them afterwards with "Enroll a student in a course", the only manual way to enroll. |
| 3.17 | Can I edit a name, delete a student, or un-enroll? | **Yes**, in Manage → **Edit & Delete** (see section 11). The student ID never changes. |

## 4. Manage → Sessions

| # | Do | Expected |
|---|---|---|
| 4.1 | Create `PY101-W5`, PY101, `2026-10-05` | Success. All 10 PY101 students are now **Unknown** for it, so completeness drops. |
| 4.2 | Create `py101-w5` again | Error: already exists (uppercased). |
| 4.3 | Same session ID under another course | Error. Session IDs are unique across **all** courses. |
| 4.4 | Dates `2026-02-30`, `05/10/2026`, `2026-9-5`, empty | Rejected. |
| 4.5 | Date `2099-01-01` or `1990-01-01` for PY101 | ✔ **Refused**: "PY101 runs from 2026-09-07 to 2026-12-18. Choose a date in that period." (A course with no dates would accept them.) |
| 4.5b | PY101 session on `2026-12-18` (the last day) or `2026-09-07` (the first day) | ✔ Accepted: both end dates are inside the period. |
| 4.6 | Session `DS102-X` created under PY101 | Accepted. The ID isn't tied to the course name (known limitation). |
| 4.7 | Two courses, sessions on the **same date** | Both saved. Two separate bars in the charts. |

## 5. Manage → Record Attendance

| # | Do | Expected |
|---|---|---|
| 5.1 | PY101 → PY101-W2 | 10 students. 003 is blank (Unknown). |
| 5.2 | Set 003 to Present → Save | "1 new". Dashboard Unknown 4 → 3, completeness → 96.05%. |
| 5.3 | Change a Present student to Absent → Save | "1 changed". Rate goes down. |
| 5.4 | Save again without changes | "0 new, 0 changed, N unchanged" (nothing rewritten). |
| 5.5 | Clear a saved status → Save | ✔ **Fixed (0.1).** The record is kept, and a warning says it was cleared on screen but kept; to delete it, use Edit & Delete. Clearing a cell never deletes. |
| 5.6 | Course with a session but no students | Message: no students enrolled. |
| 5.7 | Course with no sessions | Message: create a session first. |
| 5.8 | Can I record for a student who isn't enrolled? | **No.** Only enrolled students are listed, and the database refuses it too (`not_enrolled`, BR-09). ✔ |
| 5.9 | Can there be two records for one student in one session? | **No.** The primary key (student_id, session_id) prevents it, so saving again edits. ✔ |

## 6. Import & Validate: the file itself

| # | Upload | Expected |
|---|---|---|
| 6.1 | Columns in a **different order**, headers in CAPITALS, an extra `notes` column | ✔ Works. Columns are matched by name, not position. Extra columns ignored. |
| 6.2 | `status` column missing | ✔ Whole file rejected: "missing required column(s): status". |
| 6.3 | Semicolon-separated file (`;`) | ✔ Whole file rejected: all columns "missing". Must be comma-separated. |
| 6.4 | Empty file (0 bytes) | ✔ Whole file rejected (missing columns). |
| 6.5 | Header only, no rows | ✔ "The file has the right columns but no data rows." |
| 6.6 | Row with **fewer** cells | ✔ That row only is rejected (empty name). |
| 6.7 | Row with **more** cells | ✔ Extra cells ignored, row accepted. |
| 6.8 | Blank lines in the middle | ✔ Skipped. Row numbers still match the file. |
| 6.9 | Spaces around values, lowercase codes, `present` | ✔ Cleaned and accepted. |
| 6.10 | Saved from Excel as **"CSV (Comma delimited)"** with `Émile` | ✔ Whole file rejected: "not UTF-8, save as CSV UTF-8". |
| 6.11 | Saved from Excel as **"CSV UTF-8"** | ✔ Accepted (BOM handled). |
| 6.12 | File **opened and saved in Excel** | ⚠ Excel turns `001` into `1` and may turn dates into `01/10/2026`. ✔ Both are rejected with a reason. **Edit CSVs in Notepad or VS Code, not Excel.** |
| 6.13 | A `.xlsx` file | Not accepted by the uploader (CSV only). |
| 6.14 | Upload, Validate, then switch to a different file | The old result is cleared. Validate again. |

## 7. Import & Validate: how it combines with saved data

| # | Upload | Expected |
|---|---|---|
| 7.1 | `messy_import.csv` → Validate | 5 accepted, 2 skipped, 10 rejected. **Nothing saved yet.** |
| 7.2 | Check Dashboard before Confirm | Numbers unchanged (63 / 9 / 4). |
| 7.3 | Confirm | Success message. Confirm button disappears (can't import twice). |
| 7.4 | Upload the **same file again** → Validate | ✔ Previously accepted rows are now "Already saved with the same status". 0 accepted, so **no Confirm button**. |
| 7.5 | Row for an **existing** student and session that was Unknown | ✔ Fills the gap: Unknown 4 → 3, completeness 94.74% → 96.05%. |
| 7.6 | Row with the **same** status as saved | ✔ Skipped as duplicate. |
| 7.7 | Row with a **different** status from saved | ✔ Rejected. The saved record is kept (correct it in Manage). |
| 7.8 | Existing ID with a **different name** | ✔ Rejected (name conflict). |
| 7.9 | Existing ID, same name in **different case** (`NADIA HIRWA`) | ✔ Accepted. The saved spelling `Nadia Hirwa` is kept. |
| 7.10 | **New** ID with the same name as an existing student | ✔ Accepted **without a warning** (the warning exists only in the Add Student form). Know this answer. |
| 7.11 | **New student** | ✔ Created and enrolled automatically, **from their earliest session date in the file** for that course. They are **not** Unknown for that course's earlier sessions. |
| 7.12 | **New session** with only a few students in the file | ✔ Created. **Every other enrolled student is Unknown for it.** In the test: Unknown 4 → 18, completeness 94.74% → 80.22%. This is correct: their attendance really wasn't recorded. |
| 7.13 | Existing student in a course they're **not in yet** | ✔ Enrolled automatically from their earliest session date in the file, so they are Unknown only for that course's **later** sessions without a record. |
| 7.13b | Row for a student whose enrollment starts later (e.g. enrolled from 2026-09-14, row dated 2026-09-07) | ✔ Rejected: "Student … is enrolled in PY101 from 2026-09-14, not on 2026-09-07." |
| 7.14 | Unknown course `BIO200` | ✔ Rejected. Courses are never created by import. |
| 7.14b | PY101 row dated `2027-01-05` (after the course ends) | ✔ Rejected: "Row N: PY101 runs from 2026-09-07 to 2026-12-18, not on 2027-01-05." |
| 7.15 | Session ID that exists with a different date or course | ✔ Rejected. |
| 7.16 | Same student twice in the file, different names | ✔ First row kept, later row rejected. |
| 7.17 | If saving fails halfway | Nothing at all is saved (one transaction), and an error asks you to validate again. |
| 7.18 | Download rejected rows | CSV with a `reason` column. Fix the rows and upload only those. |
| 7.19 | Download template | Header only, the 6 columns. |
| 7.20 | In the Reports attendance data, where did a record come from? | Each record stores its `source` (filename or `manual`). It's in the database but **not shown on screen**. Know this answer. |

## 8. Dashboard

| # | Do | Expected |
|---|---|---|
| 8.1 | All courses, full date range | Students 12, Sessions 8, Present 63, Absent 9, Unknown 4, 87.50%, 94.74%. |
| 8.2 | Course PY101 | Only PY101 numbers, the caption says "PY101". The date range jumps to PY101's period, **2026-09-07 to 2026-12-18**. |
| 8.2b | Back to All courses | The date range goes back to the first and last session dates (2026-09-07 to 2026-09-30). |
| 8.3 | Date range with no sessions (e.g. one day in August) | Info message, no empty charts. |
| 8.4 | Pick only a start date | "Choose an end date" message. |
| 8.5 | Rate chart | One bar per session, date order, coloured by course, 0 to 100 axis, readable labels. |
| 8.6 | Status chart | Stacked Present (blue), Absent (orange), Unknown (grey). Each bar = enrolled students in that course. |
| 8.7 | Status filter: untick Present and Absent | Only grey parts. Colours don't change. |
| 8.8 | Untick everything | Info message, not an empty chart. |
| 8.9 | Threshold 75% | ✔ 3 students: **002 (25%), 011 (50%), 012 (66.67%)**, lowest first. |
| 8.10 | Threshold 50% | ✔ Only 002. **011 at exactly 50% is not listed**: "below" means strictly less than. |
| 8.11 | Threshold 0% | "No students are below 0%." |
| 8.12 | A new student with no records yet | Not enrolled: not on the Dashboard at all. Enrolled for the course period: listed separately as "no recorded sessions" (rate N/A), never as 0%. |
| 8.13 | A course with a session but **no students** | Doesn't appear on the Dashboard at all (nothing expected). |

## 9. Reports

| # | Do | Expected |
|---|---|---|
| 9.1 | "All students" | Overall metrics, per-student table, attendance records table, 2 downloads. |
| 9.2 | Download both CSVs, open them | Same rows and numbers as on screen. |
| 9.3 | Student 012 | ✔ 2 Present, 1 Absent, 1 Unknown, 66.67%, 75.00%. History shows DS102-W3 as **Unknown**. |
| 9.4 | Student 008 | ✔ 7 / 0 / 1, 100.00%, 87.50%. "By course" table appears (two courses). |
| 9.5 | Student 012 + course PY101 | Info message (012 isn't in PY101). |
| 9.6 | Student 002 | 25.00%: the lowest. Good example for the threshold. |
| 9.7 | Change filters while a student is selected | Their report follows the filters. |

## 10. Robustness

| # | Do | Expected |
|---|---|---|
| 10.1 | Refresh the browser in the middle of anything | No crash. Unsaved form input is lost, saved data stays. |
| 10.2 | Two browser tabs open at the same time | Both work. Refresh to see changes from the other tab. |
| 10.3 | Type `' OR 1=1 --` as a name or search | Rejected by validation. Even if it weren't, SQL uses `?` parameters (no SQL injection). |
| 10.4 | OneDrive syncing while the app runs | Risk of "database is locked". **Pause OneDrive during the presentation.** |

## 11. Manage → Edit & Delete (FR-22, FR-23)

Run `seed_demo.py` before this section; each row starts from the seed data.

| # | Do | Expected |
|---|---|---|
| 11.1 | Rename student 002 without changing the name | ✔ "No change: the new name is the same as the current one." |
| 11.2 | Rename 002 to `-Jean` | ✔ Name error (same rules as Add Student). |
| 11.3 | Rename 002 to `nadia hirwa` | ✔ **Warning** (same name as 001). Tick the box, submit again → saved. |
| 11.4 | Rename 002 to `Jean-Paul Mugisha Habimana` | ✔ Success. The ID stays 002; the new name shows everywhere. |
| 11.5 | Rename course PY101 to `Python Programming` | ✔ Success. The code stays PY101; sessions and students are unchanged. |
| 11.6 | Rename a course to an empty name | Course name error. |
| 11.7 | Any delete: look at the Delete button before ticking the box | ✔ Greyed out. Works only after ticking "I understand this cannot be undone". |
| 11.8 | Delete one record: PY101 → PY101-W1 → 001 (Present) | ✔ Preview: 1 attendance record. After: Dashboard **62 Present, 9 Absent, 5 Unknown, 87.32%, 93.42%**. 001 is Unknown for PY101-W1. |
| 11.9 | Delete one record: PY101 → PY101-W1 → 002 (Absent) | ✔ Dashboard **63 Present, 8 Absent, 5 Unknown, 88.73%**. |
| 11.10 | Un-enroll 004 from DS102 | ✔ Preview: 4 attendance records, 1 enrollment. After: 004 is still in PY101 with its 4 PY101 records. |
| 11.11 | Un-enroll 012 from DS102 | ✔ 3 attendance records (DS102-W3 was never recorded), 1 enrollment. |
| 11.12 | Delete student 004 | ✔ Preview: 8 attendance records, 2 enrollments, 1 student. 004 disappears from every list. |
| 11.13 | After 11.12, add a new student `004` | ✔ Allowed. The new 004 has no old records and no course until enrolled. |
| 11.19 | Change enrollment dates: 001 in PY101, start `2026-09-14` | ✔ Refused: 1 saved record (PY101-W1) would fall outside. |
| 11.20 | Change enrollment dates: 010 in PY101, end `2026-09-21` | ✔ Allowed. 010 is no longer expected at PY101-W4: Dashboard Unknown 4 → 3, completeness 96.00%. |
| 11.21 | Add student 013, enroll in PY101 from `2026-09-21`, then Record Attendance → PY101-W1 | ✔ 013 is not listed at W1 (listed at W3 and W4). Dashboard Unknown 4 → 6. |
| 11.24 | Change enrollment dates: 013 → the Course box | ✔ Lists only 013's courses, with full labels. The dates are pre-filled (a date not set shows the course's) and limited to the course period. |
| 11.25 | Enroll 013 in DS102 until `2026-11-30`, then change DS102 to end `2026-11-01` | ✔ Refused: "1 enrollment(s) in DS102 would fall outside them." |
| 11.22 | Change course dates: PY101 start `2026-09-10` | ✔ Refused: 1 session (PY101-W1) would fall outside. |
| 11.23 | Change course dates: PY101 to `2026-09-01` .. `2027-01-31` | ✔ Allowed. Labels and the Courses list show the new period. Dashboard numbers do not change. |
| 11.14 | Delete session DS102-W3 | ✔ Preview: 7 attendance records, 1 session. After: Dashboard **57 Present, 8 Absent, 2 Unknown**, 7 sessions. |
| 11.15 | Delete course PY101 | ✔ Error: "still has 4 session(s) and 10 enrolled student(s)". Nothing is deleted. |
| 11.16 | Create course `ML300`, then delete it | ✔ Allowed: 1 course removed. |
| 11.17 | `ML300` with one enrolled student (or one session), then delete | ✔ Refused until the student is un-enrolled (or the session deleted). |
| 11.18 | Record Attendance: clear a saved status → Save | ✔ The record is **kept**, and the warning says to use Edit & Delete to remove it. Clearing a cell never deletes. |

---

## Answers to have ready ("why" questions)

- **Why doesn't import create courses?** A typo like `PY11` would silently create a fake course. Courses are created on purpose.
- **Is a new student Unknown for old sessions?** Only if you enroll them for those dates. Each enrollment has an optional start and end date (BR-15), inside the course period (BR-17), and a student is only expected at sessions inside those dates. The Enroll form starts with the full course period; move "Enrolled from" later for a late joiner. An import starts a new enrollment at the student's earliest session in the file. Old enrollments have no dates, so they count from the first session, as before.
- **Why skip duplicates but reject conflicts?** A duplicate changes nothing, so it's safe to skip. A conflict means one of the two values is wrong, so a person must decide. The system never overwrites silently.
- **Why does a new session lower completeness?** Every enrolled student is expected. If the file lists 3 of 10, 7 really are unrecorded.
- **Why "below" is strictly less than?** Someone exactly at the threshold has met it.
- **How is delete made safe?** Every delete shows what will be removed, with counts, and needs a ticked "cannot be undone" box. Each one runs in a single transaction, so it never half-finishes. A course in use cannot be deleted at all.
- **Can a session have any date?** No. Each course has a start and end date (BR-16), and a session must fall inside them. A course with no dates (an old database) has no limit. Course dates never change who is expected; that is what enrollment dates do (BR-15).

---

## Fix prompt for bug 0.1 (already applied, kept for reference)

```
Small fix, no other changes. In Record Attendance (app.py, save_attendance_table and
show_save_result): if a student already has a saved status and the user clears it, the app
says "left blank. They stay Unknown." but the saved record is kept. That message is wrong.

Records cannot be deleted in this version. Count "cleared a saved status" separately from
"was blank and stays blank", keep the saved record, and show:
"N saved status(es) were cleared on screen but kept. Records cannot be deleted in this version."
Only students with no saved status should be reported as staying Unknown.
Add a test if the counting logic moves into a testable function.
Use .venv\Scripts\python. Run the tests, run seed_demo.py, then commit with the message
"Fix misleading message when a saved status is cleared".
Do not add a Co-Authored-By line or any mention of yourself in the commit.
```
