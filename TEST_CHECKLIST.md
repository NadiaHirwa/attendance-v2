# Attendance V2: Full Test Checklist

**Before every section:** run `.venv\Scripts\python seed_demo.py`, restart Streamlit, refresh the browser.
Every row starts from the seed data unless it says otherwise.

✔ = confirmed by running the code (on a copy of the database or by an automated test). Run `.venv\Scripts\python -m unittest`: **151 tests, all OK**.

## Key numbers to remember

| Situation | Present | Late | Excused | Absent | Unknown | Attendance rate | Completeness |
|---|---|---|---|---|---|---|---|
| **Seed data** | 63 | 0 | 0 | 9 | 4 | **87.50%** | **94.74%** |
| After importing `messy_import.csv` | 66 | 0 | 0 | 11 | 9 | 85.71% | 89.53% |
| After importing `clean_import.csv` | 73 | 1 | 1 | 11 | 1 | 87.06% | 98.85% |

**Formulas:** attendance rate = (Present + Late) ÷ (Present + Late + Absent). Completeness = all recorded ÷ expected. Excused is recorded but left out of the rate. Unknown is never stored.

**Seed data:**
- Courses: **PY101** Programming with Python (2026-09-07 to 2026-12-18), **DS102** Data Science Basics (2026-09-09 to 2026-12-18)
- PY101 students: 001 to 010. DS102 students: 004 to 012. (004 to 010 are in both.) All enrolled for the full course period.
- Sessions: PY101-W1 to W4 (09-07, 09-14, 09-21, 09-28), DS102-W1 to W4 (09-09, 09-16, 09-23, 09-30)
- The 4 Unknowns: 003 in PY101-W2, 008 in DS102-W3, 012 in DS102-W3, 010 in PY101-W4
- Lowest rates: 002 (25%), 011 (50%), 012 (66.67%). Absence streak: 002 has 2 in a row in PY101.

---

## 1. Startup and saved data

| # | Do | Expected |
|---|---|---|
| 1.1 | Start the app | 4 tabs: Dashboard, Manage Attendance, Import & Validate, Reports. No Deploy button. |
| 1.2 | Add a course, close the app (Ctrl+C), start it again | The course is still there (saved in SQLite). |
| 1.3 | Run `seed_demo.py` | **Everything you added is deleted** and the demo data comes back. Never run it on real data. |
| 1.4 | Delete `attendance.db`, start the app | No crash. Empty tables are created. Dashboard says there's no data yet. |
| 1.5 | Start the app on an **old** database (before Late/Excused or dates) | ✔ Upgraded automatically. No record is lost. |

## 2. Manage → Courses

| # | Do | Expected |
|---|---|---|
| 2.1 | Create `ML201` / `Machine Learning` with a start and end date | Success. It appears in the course list with its period. |
| 2.2 | Create `ml201` again | Error: already exists (codes become UPPERCASE). |
| 2.3 | Codes `P`, `12345`, `PY-101`, `PY 101`, `ABCDEFGHIJK` (11) | Each rejected with the course-code message. |
| 2.4 | Empty course name, or 81+ characters | Rejected. |
| 2.5 | End date **before** start date | ✔ Error: "The end date must be on or after the start date." |
| 2.6 | Two different codes with the **same name** | Allowed. Only the code must be unique. |
| 2.7 | Any course dropdown | ✔ Full label: `PY101 - Programming with Python (2026-09-07 to 2026-12-18)`. |

## 3. Manage → Students (search and add)

| # | Do | Expected |
|---|---|---|
| 3.1 | Search ID `001` | Nadia Hirwa, course PY101. |
| 3.2 | Search ID `004` | Courses **DS102, PY101**. |
| 3.3 | Search ID `099` | "No student found". |
| 3.4 | Search ID `1`, `12A`, `٠٠١` | ID error message (not "not found"). |
| 3.5 | Search name `nadia   HIRWA` | Finds 001 (spaces cleaned, case ignored). |
| 3.6 | Search name `Nadia` (partial) | **No result.** Exact full name only (partial search is Future Work). |
| 3.7 | Add `013` / `Emile Uwase` | ✔ The form has only ID and name. "Student 013 - Emile Uwase added. Enroll them in a course below." Search shows **Not enrolled**. |
| 3.8 | Add `013` again | Error: ID already used. |
| 3.9 | Add `014` / `NADIA HIRWA` | **Warning** (same name as 001). Tick the box, submit again → saved. |
| 3.10 | Names `-Nadia`, `Nadia-`, `Jean--Paul`, `Jean - Paul`, `O''Neil`, `Nadia123`, `@`, spaces only | Each rejected. |
| 3.11 | Name `O’Neil` (curly apostrophe) | Saved as `O'Neil`. |
| 3.12 | Name `Émile` | Accepted. |
| 3.13 | 50 letters / 51 letters | 50 accepted, 51 rejected. |

## 4. Enrollment (Students sub-tab and Edit & Delete)

| # | Do | Expected |
|---|---|---|
| 4.1 | Enroll 013 in PY101 | ✔ Only Student and Course. "013 enrolled in PY101 for the full course period (2026-09-07 to 2026-12-18)." Dashboard Unknown **4 → 8** (013 expected at 4 sessions). |
| 4.2 | Enroll 001 in PY101 again | Error: already enrolled. |
| 4.3 | Edit & Delete → **Late start or early leave**: look at the form | ✔ Course box lists only that student's courses. Dates pre-filled, limited to the course period. "Current: … (full course period)". |
| 4.4 | Enroll 001 in DS102, then Late start: from `2026-09-23` | Late joiner: only DS102-W3 and W4 expected. Unknown 4 → 8 → **6**. |
| 4.5 | 010 in PY101: early leave until `2026-09-21` | ✔ Allowed. 010 no longer expected at PY101-W4: Unknown **4 → 3**, completeness 96.00%. |
| 4.6 | 001 in PY101: late start `2026-09-14` | ✔ **Refused**: 1 saved record (PY101-W1) would fall outside. |
| 4.7 | Record Attendance → PY101-W1 after 4.4-style late start for a student | The late joiner is **not listed** at sessions before their start. |
| 4.8 | Can an enrollment go outside the course period? | **No.** The date inputs are limited, and the database code checks it too. |

## 5. Manage → Sessions

| # | Do | Expected |
|---|---|---|
| 5.1 | Create `PY101-W5`, PY101, `2026-10-05` | Success. All 10 PY101 students are **Unknown** for it, so completeness drops. |
| 5.2 | Create `py101-w5` again | Error: already exists (uppercased). |
| 5.3 | Same session ID under another course | Error. Session IDs are unique across all courses. |
| 5.4 | Dates `2026-02-30`, `05/10/2026`, `2026-9-5`, empty | Rejected. |
| 5.5 | PY101 session on `2027-01-05` or `2026-01-01` | ✔ **Refused**: "PY101 runs from 2026-09-07 to 2026-12-18. Choose a date in that period." |
| 5.6 | PY101 session on `2026-09-07` or `2026-12-18` (first / last day) | ✔ Accepted. |
| 5.7 | Session `DS102-X` created under PY101 | Accepted. The ID isn't tied to the course name (known limitation). |
| 5.8 | Two courses, sessions on the **same date** | Both saved. Two separate bars in the charts. |

## 6. Manage → Record Attendance

| # | Do | Expected |
|---|---|---|
| 6.1 | PY101 → PY101-W2 | 10 students. 003 is blank (Unknown). Choices: Present, Late, Excused, Absent. |
| 6.2 | 003 → **Present** → Save | "1 new". Unknown 4 → 3, rate 87.67%, completeness 96.05%. |
| 6.3 | 003 → **Late** → Save | ✔ Same as Present for the rate: **87.67%**, completeness 96.05%, Late 1. |
| 6.4 | 003 → **Excused** → Save | ✔ Rate stays **87.50%** (left out), completeness **96.05%** (it is recorded), Excused 1. |
| 6.5 | 002 in PY101-W1: Absent → **Excused** | ✔ Rate goes **up** to **88.73%**, completeness unchanged 94.74%. |
| 6.6 | 001 in PY101-W1: Present → **Late** | ✔ Rate unchanged **87.50%**. |
| 6.7 | Save again without changes | "0 new, 0 changed, N unchanged" (nothing rewritten). |
| 6.8 | Clear a saved status → Save | ✔ The record is **kept**; a warning says to use Edit & Delete to remove it. Clearing never deletes. |
| 6.9 | Can I record for a student who isn't enrolled, or outside their enrollment dates? | **No.** They aren't listed, and the database refuses it (`not_enrolled`, `outside_enrollment`). ✔ |
| 6.10 | Two records for one student in one session? | **No.** Primary key (student_id, session_id): saving again edits. ✔ |

## 7. Import & Validate: the file itself

| # | Upload | Expected |
|---|---|---|
| 7.1 | Columns in a **different order**, CAPITAL headers, an extra `notes` column | ✔ Works. Columns matched by name. Extras ignored. |
| 7.2 | `status` column missing | ✔ Whole file rejected: "missing required column(s): status". |
| 7.3 | Semicolon-separated file | ✔ Whole file rejected (all columns "missing"). Must be comma-separated. |
| 7.4 | Empty file | ✔ Whole file rejected. |
| 7.5 | Header only | ✔ "The file has the right columns but no data rows." |
| 7.6 | Row with **fewer** cells | ✔ That row only is rejected. |
| 7.7 | Row with **more** cells | ✔ Extra cells ignored, row accepted. |
| 7.8 | Blank lines in the middle | ✔ Skipped. Row numbers still match the file. |
| 7.9 | Spaces around values, lowercase codes, `present` | ✔ Cleaned and accepted. |
| 7.10 | Excel "CSV (Comma delimited)" with `Émile` | ✔ Whole file rejected: "save as CSV UTF-8". |
| 7.11 | Excel "CSV UTF-8" | ✔ Accepted. |
| 7.12 | File opened and saved in Excel | ⚠ `001` becomes `1`, dates may become `01/10/2026`. ✔ Rejected with reasons. **Edit CSVs in Notepad or VS Code.** |
| 7.13 | A `.xlsx` file | Not accepted by the uploader. |
| 7.14 | Status `L`, `late`, `E`, `Excused` | ✔ Accepted, saved as Late / Excused. `maybe` is rejected. |

## 8. Import & Validate: combining with saved data

| # | Upload | Expected |
|---|---|---|
| 8.1 | `messy_import.csv` → Validate | ✔ **5 accepted, 2 skipped, 10 rejected.** Nothing saved yet; Dashboard unchanged. |
| 8.2 | Confirm | ✔ Dashboard: **66 / 0 / 0 / 11 / 9, 85.71%, 89.53%**. Confirm button disappears. |
| 8.3 | Same file again → Validate | ✔ Accepted rows are now "Already saved with the same status". No Confirm button. |
| 8.4 | `clean_import.csv` → Confirm | ✔ 14 accepted. Dashboard **73 / 1 / 1 / 11 / 1, 87.06%, 98.85%**. |
| 8.5 | Row filling an existing Unknown | ✔ Gap filled: Unknown 4 → 3. |
| 8.6 | Same status as saved | ✔ Skipped as duplicate. |
| 8.7 | Different status from saved | ✔ Rejected. Saved record kept. |
| 8.8 | Existing ID, different name | ✔ Rejected (name conflict). |
| 8.9 | Existing ID, same name in different case | ✔ Accepted. Saved spelling kept. |
| 8.10 | New ID with the same name as an existing student | ✔ Accepted **without a warning** (the warning is only in Add Student). |
| 8.11 | New student | ✔ Created and enrolled **from their earliest session date in the file**, so not Unknown for earlier sessions. |
| 8.12 | Row before a student's enrollment start | ✔ Rejected: "Student … is enrolled in PY101 from …, not on …". |
| 8.13 | Row outside the course period (e.g. `2027-01-05`) | ✔ Rejected: "PY101 runs from 2026-09-07 to 2026-12-18, not on 2027-01-05." |
| 8.14 | New session with only some students | ✔ Every other enrolled student is Unknown for it (correct: not recorded). |
| 8.15 | Unknown course `BIO200` | ✔ Rejected. Import never creates courses. |
| 8.16 | Session ID that exists with a different date or course | ✔ Rejected. |
| 8.17 | Same student twice in the file with different names | ✔ First row kept, later row rejected. |
| 8.18 | Saving fails halfway | Nothing saved (one transaction); an error asks you to validate again. |
| 8.19 | Download rejected rows / template | CSV with a `reason` column / header-only template. |
| 8.20 | Where did a record come from? | Each record stores its `source` (filename or `manual`), in the database, not on screen. |

## 9. Dashboard

| # | Do | Expected |
|---|---|---|
| 9.1 | All courses, full range | ✔ Students 12, Sessions 8, **63 / 0 / 0 / 9 / 4, 87.50%, 94.74%**. |
| 9.2 | Course PY101 | Only PY101 numbers. Date range jumps to **2026-09-07 to 2026-12-18**. |
| 9.3 | Back to All courses | Date range returns to the first and last session dates. |
| 9.4 | Date range with no sessions | Info message, no empty charts. |
| 9.5 | Only a start date picked | "Choose an end date" message. |
| 9.6 | Rate chart | One bar per session, date order, coloured by course, 0 to 100 axis. |
| 9.7 | Status chart | ✔ Stacked Present (blue), Late (light blue), Excused (pink), Absent (orange), Unknown (grey). Caption: Excused is not counted in the rate. |
| 9.8 | Status filter: keep only Unknown | Only grey parts. Colours don't change. |
| 9.9 | Untick everything | Info message, not an empty chart. |
| 9.10 | Threshold 75% | ✔ **002 (25%), 011 (50%), 012 (66.67%)**, lowest first. |
| 9.11 | Threshold 50% | ✔ Only 002. **011 at exactly 50% is not listed** (strictly below). |
| 9.12 | Threshold 0% | "No students are below 0%." |
| 9.13 | **Absence alerts**, minimum 2 | ✔ Only **002, PY101: current streak 2, longest 2, last absence 2026-09-28**. |
| 9.14 | Absence alerts, minimum 1 | ✔ **002 (2), 009 PY101 (1), 012 DS102 (1)**, highest first. |
| 9.15 | Absence alerts, minimum 3 | ✔ "No students have 3 or more absences in a row." |
| 9.16 | Why isn't 011 an alert? | ✔ 011's longest streak in DS102 is 2, but the **current** streak is 0 (attended the last session). Alerts use the current streak. |
| 9.17 | Excused or Unknown between two absences | ✔ Ends the streak: Absent, Excused, Absent = longest 1. |
| 9.18 | A course with a session but no students | Doesn't appear (nothing expected). |

## 10. Reports

| # | Do | Expected |
|---|---|---|
| 10.1 | "All students" | Overall metrics (incl. Late and Excused), per-student table, attendance records, 2 downloads. |
| 10.2 | Download both CSVs, open them | Same rows and numbers as on screen. |
| 10.3 | Student 012 | ✔ 2 Present, 1 Absent, 1 Unknown, 66.67%, 75.00%. History shows DS102-W3 as **Unknown**. |
| 10.4 | Student 008 | ✔ 7 / 0 / 1, 100.00%, 87.50%. By-course table with both courses, enrollment period and streaks. |
| 10.5 | Student 002 | 25.00%, current streak 2 in PY101. |
| 10.6 | Student 012 + course PY101 | Info message (012 isn't in PY101). |
| 10.7 | Change filters while a student is selected | The report follows the filters. |

## 11. Manage → Edit & Delete

| # | Do | Expected |
|---|---|---|
| 11.1 | Rename 002 without changing the name | ✔ "No change". |
| 11.2 | Rename 002 to `-Jean` | ✔ Name error. |
| 11.3 | Rename 002 to `nadia hirwa` | ✔ Same-name warning; tick and submit → saved. |
| 11.4 | Rename course PY101 to `Python Programming` | ✔ Code stays PY101; nothing else changes. |
| 11.5 | Change PY101 dates: start `2026-09-10` | ✔ Refused: 1 session (PY101-W1) would fall outside. |
| 11.6 | Change PY101 dates to `2026-09-01` .. `2027-01-31` | ✔ Allowed. Numbers don't change. |
| 11.7 | Any delete before ticking "I understand this cannot be undone" | ✔ Delete button greyed out. |
| 11.8 | Delete record: PY101-W1 → 001 (Present) | ✔ **62 / 9 / 5, 87.32%, 93.42%**. 001 is Unknown there. |
| 11.9 | Delete record: PY101-W1 → 002 (Absent) | ✔ **63 / 8 / 5, 88.73%**. |
| 11.10 | Un-enroll 004 from DS102 | ✔ Removes 4 records + 1 enrollment. 004 keeps PY101. |
| 11.11 | Delete student 004 | ✔ Removes 8 records, 2 enrollments, 1 student. |
| 11.12 | Then add a new `004` | ✔ Allowed, with no old data. |
| 11.13 | Delete session DS102-W3 | ✔ Removes 7 records + 1 session. Dashboard **57 / 8 / 2**, 7 sessions. |
| 11.14 | Delete course PY101 | ✔ Refused: "still has 4 session(s) and 10 enrolled student(s)". |
| 11.15 | Create `ML300`, then delete it | ✔ Allowed. |

## 12. Robustness

| # | Do | Expected |
|---|---|---|
| 12.1 | Refresh the browser mid-task | No crash. Unsaved input lost, saved data stays. |
| 12.2 | Two browser tabs at once | Both work. Refresh to see the other tab's changes. |
| 12.3 | Type `' OR 1=1 --` as a name or search | Rejected by validation. SQL uses `?` parameters anyway. |
| 12.4 | OneDrive syncing during the demo | Risk of "database is locked". **Pause OneDrive.** |

---

## Answers to have ready

- **Why is Excused not in the attendance rate?** The student was allowed to miss it: counting it as absent is unfair, counting it as present is untrue. It still counts for completeness because it is recorded. Late counts as attended.
- **Why is Unknown not Absent?** Missing data isn't evidence of absence. 7 Present, 2 Absent, 1 Unknown = 77.78% attendance and 90% completeness, not 70%.
- **Why do alerts use the current streak?** An alert should point to a student who is absent *now*. 011 had 2 absences in a row earlier but came back.
- **Course dates vs enrollment dates?** Course dates say when sessions can happen. Enrollment dates say when a particular student is expected. Most students follow the course; late start or early leave is the exception.
- **Why doesn't import create courses?** A typo like `PY11` would silently create a fake course.
- **Why skip duplicates but reject conflicts?** A duplicate changes nothing. A conflict means one value is wrong, so a person must decide. Nothing is overwritten silently.
- **How is delete made safe?** A preview with counts, a "cannot be undone" tick box, one transaction, and a course in use can't be deleted.
- **What happens to an old database?** `create_tables()` upgrades it: new columns are added, and the attendance table is rebuilt to allow Late/Excused, copying every row in one transaction.
- **Why "below" is strictly less than?** Someone exactly at the threshold has met it.
