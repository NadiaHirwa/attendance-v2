# Attendance V3: Full Test Checklist

**Before every section:** run `.venv\Scripts\python seed_demo.py`, restart Streamlit, refresh the browser.
Every row starts from the seed data unless it says otherwise.

✔ = confirmed by running the code (on a copy of the database or by an automated test). Run `.venv\Scripts\python -m unittest`: **308 tests, all OK**.

Dates are shown as **DD/MM/YYYY** everywhere on screen and in downloads (BR-23).

## Key numbers to remember

| Situation | Present | Late | Excused | Absent | Unknown | Attendance rate | Completeness |
|---|---|---|---|---|---|---|---|
| **Seed data** (505 expected) | 477 | 10 | 4 | 10 | 4 | **97.99%** | **99.21%** |
| After importing `messy_import.csv`, no suggestions accepted (522 expected) | 479 | 11 | 6 | 11 | 15 | 97.80% | 97.13% |
| After importing `messy_import.csv`, all 7 suggestions accepted (554 expected) | 485 | 11 | 6 | 11 | 41 | 97.83% | 92.60% |
| After importing `clean_import.csv` (510 expected) | 482 | 11 | 5 | 10 | 2 | 98.01% | 99.61% |
| Week 2 (07/09–11/09), all courses | | | | | | **98.73%** | **98.76%** |
| **002 in PY101** (17 expected) | 10 | 2 | 0 | 5 | 0 | **70.59%** | 100.00% |

**002 in PY101 loses 12 marks** (2 Late x 1 + 5 Absent x 2). ✔

**Formulas:** attendance rate = (Present + Late) ÷ (Present + Late + Absent). Completeness = all recorded ÷ expected. Excused is recorded but left out of the rate. Unknown is never stored. Deducted marks = Late x late deduction + Absent x absent deduction (settings, default **1** and **2**); Present, Excused and Unknown deduct nothing; Unknown is flagged "N not recorded"; no maximum.

**Seed data (Version 3):**
- Block **B1-2627** "Block 1, 2026-27", Monday 31/08/2026 to Friday 18/09/2026.
- Courses **PY101** Programming with Python, **DS102** Data Science Basics, **MA103** Mathematics for Data Science, all for the whole block.
- Class days: every weekday, 15 per course. **DS102 has no class on 09/09** (holiday), so 14.
- Tutorials: PY101 03/09 and **Saturday 12/09**; DS102 04/09 and 17/09; MA103 **two on 16/09** (T1 and T2).
- Students 001 to 012. PY101: all 12. DS102: all except 003 and 007. MA103: all except 011 and 012.
- **010 joins late** (from 07/09) and **012 leaves early** (until 11/09), in all their courses.
- The 4 Unknowns: 003 PY101 09/09, 011 PY101 tutorial 12/09, 008 DS102 tutorial 17/09, 007 MA103 18/09.
- Absence alert: **009 in PY101**, absent on 17/09 and 18/09 (current streak 2). 002 had 3 in a row (14-16/09) but came back.

---

## 1. Startup and saved data

| # | Do | Expected |
|---|---|---|
| 1.1 | Start the app | 4 tabs: Dashboard, Manage Attendance, Import & Validate, Reports. No Deploy button. |
| 1.2 | Add a student, close the app (Ctrl+C), start it again | The student is still there (saved in SQLite). |
| 1.3 | Run `seed_demo.py` | **Everything you added is deleted** and the demo data comes back. Never run it on real data. |
| 1.4 | Delete `attendance.db`, start the app | ✔ No crash. The demo data is created automatically (97.99%, 99.21%). |
| 1.5 | Start the app on an **old** database (before blocks) | ✔ Upgraded automatically: old courses show "No block", old sessions become Class days. No record is lost. |

## 2. Manage → Blocks & Courses

| # | Do | Expected |
|---|---|---|
| 2.1 | Create block `b2-2627` / `Block 2, 2026-27` starting **Tuesday** 22/09/2026 | ✔ Error: "A block must start on a Monday; 22/09/2026 is a Tuesday." |
| 2.2 | Same block starting **Monday** 21/09/2026 | ✔ "Block B2-2627 created, running from 21/09/2026 to 09/10/2026." The end is calculated (Friday of week 3). |
| 2.3 | Block IDs `B`, `B1 2627`, 11 characters | Rejected with the block-ID message. |
| 2.4 | Create course `ST104` / `Statistics` in B1-2627 | ✔ "…running from 31/08/2026 to 18/09/2026, with 15 class days (every weekday)." |
| 2.5 | Same, with **Shorter period** ticked, start 07/09/2026 | ✔ "…running from 07/09/2026 to 18/09/2026, with 10 class days." The date inputs only allow dates inside the block. |
| 2.6 | Create `py101` again | Error: already exists (codes become UPPERCASE). |
| 2.7 | Codes `P`, `12345`, `PY-101`, `PY 101`, `ABCDEFGHIJK` (11); empty name or 81+ characters | Each rejected with its message. |
| 2.8 | Blocks list | ✔ B1-2627 with its dates and courses "DS102, MA103, PY101". |
| 2.9 | Any course dropdown | ✔ Full label: `PY101 - Programming with Python (31/08/2026 to 18/09/2026)`. |
| 2.10 | Course details → B1-2627 → MA103 | ✔ "10 student(s) enrolled", each with their period (010 "joined late"). |
| 2.11 | Rename MA103 without changing the name / to `Maths for Data Science` | "No change" / renamed; the code stays MA103. |
| 2.12 | Change PY101 dates: start 07/09/2026 | ✔ **Refused:** "66 saved attendance record(s) of PY101 are on days outside the new period and would be lost." (11 students x 6 week-1 sessions.) |
| 2.13 | Change PY101 dates: start 24/08/2026 | ✔ Refused: "must stay inside the block". |
| 2.14 | Delete course MA103: look at the preview, then tick and delete | ✔ "15 class day(s), 2 tutorial(s), 10 enrollment(s), 164 attendance record(s), 1 course(s)". Delete is greyed out until ticked. Afterwards: **317 / 9 / 2 / 9 / 3, 97.31%, 99.12%**. |
| 2.17 | **Edit a block** → B1-2627: rename to `First block`, same start | ✔ "Block B1-2627 (First block) now runs from 31/08/2026 to 18/09/2026: 0 class day(s) added, 0 session(s) removed." |
| 2.18 | Edit B1-2627: start **Tuesday** 01/09/2026 | ✔ Refused: "A block must start on a Monday; 01/09/2026 is a Tuesday." |
| 2.19 | Edit B1-2627 (seed data): start Monday 07/09/2026 | ✔ **Refused:** "Block B1-2627 cannot run from 07/09/2026 to 25/09/2026: 54 saved attendance record(s) in DS102 would fall outside the new dates. Delete them first, or choose another start date." Nothing changes. |
| 2.20 | Fresh block with a course and no attendance: move it one week earlier | ✔ The course follows the block; 5 class days added, 5 removed. A removed holiday still inside the block stays removed; a course shorter than the block keeps its length and moves by the same days. |
| 2.15 | Delete block B1-2627 | ✔ Refused: "it still has 3 course(s). Delete those courses first." |
| 2.16 | Delete an empty block (for example B2-2627 from 2.2) | ✔ Allowed. |

## 3. Manage → Students (search, profile, add)

| # | Do | Expected |
|---|---|---|
| 3.1 | Search ID `002` | ✔ "1 match, showing 002 in the profile below." The profile is titled **002 - Jean-Paul Mugisha**: PY101 70.59%, **12** marks deducted; DS102 and MA103 100.00%, 0. |
| 3.2 | Search ID `004` | Courses **DS102, MA103, PY101**. |
| 3.3 | Search ID `099` | "No student found". |
| 3.4 | Search ID `1`, `12A`, `٠٠١` | ID error message (not "not found"). |
| 3.5 | Search name `nadia   HIRWA` | Finds 001 (spaces cleaned, case ignored). |
| 3.6 | Search name `Nadia` (partial) | **No result.** Exact full name only (partial search is Future Work). |
| 3.7 | Add `013` / `Emile Uwase` | ✔ Under "Add a student": "Only enrolled students appear in Record attendance, the Dashboard and the class register. Enroll the new student in a course from their profile." The form has only ID and name. "…added. Enroll them in a course in their profile above." Their profile opens: "Not enrolled in any course yet." |
| 3.8 | Add `013` again | Error: ID already used. |
| 3.9 | Add `014` / `NADIA HIRWA` | **Warning** (same name as 001). Tick the box, submit again → saved. |
| 3.10 | Names `-Nadia`, `Nadia-`, `Jean--Paul`, `Jean - Paul`, `O''Neil`, `Nadia123`, `@`, spaces only | Each rejected. |
| 3.11 | Name `O’Neil` (curly apostrophe) / `Émile` / 50 letters / 51 letters | Saved as `O'Neil` / accepted / accepted / rejected. |
| 3.12 | Profile of 013 → Enroll in PY101 | ✔ "013 enrolled in PY101 for the full course period (31/08/2026 to 18/09/2026)." Unknown **4 → 21** (17 sessions). |
| 3.13 | Enroll 001 in PY101 again | Error: already enrolled. |
| 3.14 | Profile of 003 → enroll in DS102, then **Late start or early leave**: from 14/09/2026 | ✔ Unknown 4 → **20** → **10** (only the last 10 DS102 sessions are expected). |
| 3.15 | Profile of 001 → Late start 07/09/2026 in PY101 | ✔ **Refused:** 6 saved records would fall outside. |
| 3.16 | Profile of 009 → Early leave 16/09/2026 in PY101 | ✔ **Refused:** 2 saved records (17/09 and 18/09) would fall outside. |
| 3.17 | Profile → Late start or early leave: look at the form | ✔ Only that student's courses. Dates pre-filled, limited to the course period. "Current: … (full course period)" or "(joined late)". |
| 3.18 | Profile of 002 → Rename to `-Jean` / unchanged / `nadia hirwa` | ✔ Name error / "No change" / same-name warning (tick and submit → saved). |
| 3.19 | Profile of 004 → Un-enroll from DS102 | ✔ Removes **16** records + 1 enrollment. 004 keeps PY101 and MA103. |
| 3.21 | Profile of 002: look at the sections | ✔ Every title names the student: "Enroll 002 - Jean-Paul Mugisha in a course", "Late start or early leave: 002 - …", "Rename 002 - Jean-Paul Mugisha", "Un-enroll 002 - … from a course", "Delete 002 - …". |
| 3.22 | Add `014` / `NADIA HIRWA` (after 3.9), then search name `Nadia Hirwa` | ✔ "2 matches, showing 001; choose another in the Student box." |
| 3.20 | Profile of 004 → Delete the student | ✔ Removes **50** records, 3 enrollments, 1 student. Then a new `004` can be added, with no old data. |

## 4. Manage → Class days & Tutorials

| # | Do | Expected |
|---|---|---|
| 4.1 | B1-2627 → PY101 | ✔ "15 class days and 2 tutorials". Columns **Date, Day, Type, Records saved, Not recorded**, no session IDs. Tutorials show as "Tutorial T1". Wed 09/09: 11 saved, 1 not recorded. |
| 4.2 | B1-2627 → DS102 | 14 class days: **no 09/09** (the holiday). |
| 4.3 | Add a tutorial to PY101 on **Saturday** 05/09/2026, twice | ✔ "Sat 05/09/2026 - Tutorial T1", then **T2**. Weekends are allowed for tutorials. |
| 4.4 | Add a tutorial on 23/09/2026 (after the course) | ✔ Refused: "PY101 runs from 31/08/2026 to 18/09/2026. Choose a date in that period." |
| 4.5 | Remove PY101 "Wed 09/09/2026 - Class": look at the preview | ✔ "…and delete **11** attendance record(s) saved for it." (12 students, 003 has no record.) |
| 4.6 | Remove DS102 "Wed 16/09/2026 - Class" (tick, delete) | ✔ 9 records removed. Dashboard **468 / 10 / 4 / 10 / 4, 97.95%, 99.19%**, "12 students · 43 class days · 6 tutorials". |

## 5. Manage → Record attendance

| # | Do | Expected |
|---|---|---|
| 5.1 | Block → Course → Day | The Day box starts on **today** when today is a class day of that course; otherwise on the first day. Labels like "Thu 03/09/2026 - Tutorial T1". |
| 5.2 | PY101 → Wed 09/09/2026 | 12 students; 003 is blank (Unknown). Choices: Present, Late, Excused, Absent. |
| 5.3 | **Mark all Present** → Save | ✔ Only 003 is filled in: "1 new", the 11 saved records are **not rewritten**. Unknown 4 → 3, completeness **99.41%**. |
| 5.4 | 002 on Tue 01/09/2026: Absent → **Excused** → Save | ✔ Rate goes **up** to **98.19%** (Excused is left out), completeness stays 99.21%. |
| 5.5 | 001 on Mon 31/08/2026: Present → **Late** → Save | ✔ Rate unchanged **97.99%** (Late counts as attended). |
| 5.6 | Save again without changes | "0 new, 0 changed, N unchanged" (nothing rewritten). |
| 5.7 | Clear a saved status → Save | ✔ The record is **kept**; a warning says to use "Delete one attendance record" below. Clearing never deletes. |
| 5.8 | Delete one attendance record: Mon 31/08/2026 → 001 (Present) | ✔ **476 / 10 / 4 / 10 / 5, 97.98%, 99.01%**. 001 is Unknown that day. |
| 5.9 | Delete one attendance record: Tue 01/09/2026 → 002 (Absent) | ✔ **477 / 10 / 4 / 9 / 5, 98.19%, 99.01%**. |
| 5.10 | DS102 → a day before 07/09 | 010 (late joiner) is **not listed**. PY101 after 11/09: 012 (early leaver) is not listed. ✔ |
| 5.11 | Two records for one student on one day? | **No.** Primary key (student_id, session_id): saving again edits. ✔ |

## 6. Manage → Settings

| # | Do | Expected |
|---|---|---|
| 6.1 | Open Settings | ✔ Late deduction **1**, Absent deduction **2**, and the rule: "Late x 1 + Absent x 2 … There is no maximum." |
| 6.2 | Save Late 3, Absent **11** | ✔ Refused: "Invalid Absent deduction "11". Expected a whole number from 0 to 10." Nothing is saved (Late stays 1). |
| 6.3 | Save Late **-1** | ✔ Refused with the same kind of message. |
| 6.4 | Save Late 0 and Absent 10 | ✔ Accepted (both limits are allowed). |
| 6.5 | Save Late **2**, Absent **3** | ✔ "Settings saved … Every report now uses these values." 002's profile, the per-student summary and the PY101 export all show **19** for 002 (2 x 2 + 5 x 3). |
| 6.6 | Save without changing anything | "No change". |
| 6.7 | Reset demo data (sidebar) | ✔ The settings go back to 1 and 2. |

## 7. Import & Validate: the file itself

Columns: `course_code, date, student_id, full_name, status`, optional `type` (Class or Tutorial). `session_id` is no longer used.

| # | Upload | Expected |
|---|---|---|
| 7.1 | Columns in a **different order**, CAPITAL headers, an extra `notes` column | ✔ Works. Columns matched by name. Extras ignored. |
| 7.2 | `status` column missing | ✔ Whole file rejected: "missing required column(s): status". |
| 7.3 | A Version 2 file (`session_id, session_date, …`) | ✔ Whole file rejected: "missing required column(s): date". |
| 7.4 | Semicolon-separated file / empty file / header only | ✔ Rejected / rejected / "The file has the right columns but no data rows." |
| 7.5 | Row with **fewer** / **more** cells, blank lines in the middle | ✔ That row rejected / extra cells ignored / skipped (row numbers still match the file). |
| 7.6 | Dates `16/09/2026`, `7/9/2026` and `2026-09-16` | ✔ All accepted. `16/09/2026` is the normal form (BR-23) and is **not** an auto-fix; `7/9/2026` and `2026-09-16` are listed under **Auto-fixed** as → `07/09/2026` / `16/09/2026` (FR-31). `07/09/2026` means 7 September. `2026-02-30`, `31/02/2026`, `31/9/2026`, `2026-9-5` rejected. |
| 7.7 | Spaces around values, lowercase codes, `present`, `tutorial`, `tut`, `CLASS`, `Grace O’Neil` | ✔ Accepted; each change listed under **Auto-fixed** as row, column, before → after, why. |
| 7.8 | Excel "CSV (Comma delimited)" with `Émile` / "CSV UTF-8" | ✔ Rejected ("save as CSV UTF-8") / accepted. |
| 7.9 | File opened and saved in Excel | ⚠ `001` becomes `1`: ✔ auto-fixed to `001` (also `04` → `004`). `0` and `00` are **not** fixed and are rejected. **Still best to edit CSVs in Notepad or VS Code.** |
| 7.10 | Status `L`, `late`, `E`, `Excused` | ✔ Accepted, saved as Late / Excused. `maybe` is rejected. |
| 7.11 | Type `Lab` | ✔ Rejected: "Expected Class or Tutorial (or leave it empty for Class)." |
| 7.12 | Name `eric niyonzima` for a new student | ✔ Kept as typed: names are never changed except spaces and apostrophes. |

## 8. Import & Validate: combining with saved data

| # | Upload | Expected |
|---|---|---|
| 8.1 | `messy_import.csv` → Validate | ✔ Metrics: **Auto-fixes 39, Accepted suggestions 0 of 7, Accepted 6, Skipped duplicates 2, Rejected 11.** Every suggestion unticked; S4 shows "Keep saved Absent". Nothing saved yet; Dashboard unchanged. |
| 8.2 | Confirm without accepting anything | ✔ "Edited by you: 0. Auto-fixes: 39. Accepted suggestions: 0. Saved: 6. Skipped duplicates: 2. Rejected: 11." Dashboard **479 / 11 / 6 / 11 / 15, 97.80%, 97.13%**. 002 on 01/09 stays **Absent**. The new MA103 Saturday tutorial (12/09) is created. |
| 8.3 | Fresh seed: Validate, tick all six boxes, choose "Use file: Present" → **Apply suggestions** | ✔ **Accepted suggestions 7 of 7, Accepted 13, Skipped duplicates 2, Rejected 4.** Still nothing saved. |
| 8.4 | Confirm | ✔ "Edited by you: 0. Auto-fixes: 39. Accepted suggestions: 7. Saved: 13. Skipped duplicates: 2. Rejected: 4." Dashboard **485 / 11 / 6 / 11 / 41, 97.83%, 92.60%**. 002 on 01/09 is **Present**, source `messy_import.csv`. New students **013 Fabrice Gasana** (PY101 from 14/09) and **015 Alice Kayitesi** (MA103 from 15/09). New tutorials PY101 Sat 05/09 and DS102 Wed 09/09 (S5). |
| 8.5 | Row 12 (S1): `004, eric niyonzimma` | ✔ "Use saved name Eric Niyonzima". Accepted → saved under 004 Eric Niyonzima. |
| 8.6 | Rows 13 and 14 (S2): `011, Fabrice Gasana` (saved 011 is Claudine Umutoni) | ✔ Both rows: "Assign next free ID 013 as a new student" (the same pair always gets the same ID). |
| 8.7 | Row 16 (S3): `014` again as Alice Kayitesi (row 15 is Alice Uwimana) | ✔ "Assign next free ID 015 as a new student": 013 is already proposed, 014 is in the file. |
| 8.8 | Row 17 (S4): 002 PY101 01/09 `P` (saved Absent) | ✔ Default "Keep saved Absent" → rejected, saved record kept. "Use file: Present" → updated in the same transaction as the import. |
| 8.9 | Download cleaned file (after 8.3) | ✔ 15 rows (13 accepted + 2 duplicates) in file order, Version 3 columns, auto-fixes, edits and suggestions applied, dates as DD/MM/YYYY; rows 9 and 10 have type Tutorial. Rejected rows stay in their own download. |
| 8.10 | The **original** messy file again after 8.4 | ⚠ The S2/S3 rows get new IDs proposed (013 and 015 are now saved). Import the cleaned file instead. |
| 8.11 | `clean_import.csv` → Confirm (fresh seed) | ✔ 7 accepted. Dashboard **482 / 11 / 5 / 10 / 2, 98.01%, 99.61%**. |
| 8.12 | Class row on a Saturday (row 9) | ✔ Rejected: "Row 9: PY101 has no class on Saturday 05/09/2026. Suggestion: "Import as tutorial on that date"…" (S5). Accepted → a new tutorial PY101 05/09 T1, created at Confirm. |
| 8.13 | Class row on the DS102 holiday (row 10) | ✔ Rejected: "Row 10: DS102 has no class on Wednesday 09/09/2026 (class day removed)." with the same S5 suggestion. A weekday with no class in an older course without dates gets no suggestion. |
| 8.14 | Tutorial rows on a new date | ✔ One new tutorial (T1) is planned and shared by every row of that date (rows 12 and 20); created only at Confirm. |
| 8.15 | Row filling an existing Unknown | ✔ Gap filled (rows 2 to 5). |
| 8.16 | Same status as saved | ✔ Skipped as duplicate (row 18); a row repeating an earlier row (row 19) too. |
| 8.17 | Existing ID, same name in different case | ✔ Accepted, saved spelling kept. |
| 8.18 | New student | ✔ Created and enrolled **from their earliest date in the file**, so not Unknown for earlier sessions. |
| 8.19 | Row before a late joiner's start (e.g. DS102 31/08 for 010) | ✔ Rejected: "Student 010 is enrolled in DS102 from 07/09/2026, not on 31/08/2026." |
| 8.20 | Row outside the course period | ✔ Rejected: "Row 11: PY101 runs from 31/08/2026 to 18/09/2026, not on 25/09/2026." |
| 8.21 | Unknown course `BIO200` / status `maybe` / ID `0` | ✔ Rejected (rows 8, 7, 6). Import never creates courses. |
| 8.22 | One student and session with two statuses in the file | ✔ First row kept, later row rejected (no suggestion). |
| 8.22b | Saved Present; file rows `L` then `A` for the same student and day → accept all | ✔ Only the first row has S4. The second is rejected: "Student 001 already has Late for PY101 on Monday 31/08/2026 earlier in this file (row 2), not Absent. The first row is kept." Confirm saves one update, to **Late**. |
| 8.25 | Rejected table: change row 7's status `maybe` to `P` → **Re-check** | ✔ Auto-fixed lists "row 7, status, maybe → P, edited by you: maybe -> P" (plus the P → Present auto-fix: 40). Row 7 moves to **Skipped duplicates** (001 is already Present on 31/08): 6 / 3 / 10. Still nothing saved; the cleaned file has the edited row. Confirm: "Edited by you: 1. Auto-fixes: 40. …" |
| 8.26 | Re-check, then Apply suggestions (or the reverse) | ✔ Both are kept: edits stay by row number, accepted suggestions stay ticked. **Validate** starts again with neither. |
| 8.27 | Rejected table: the `row` and `reason` columns | Read-only. |
| 8.28 | Every import table and reason | ✔ No session IDs: a status conflict names "PY101 on Tuesday 01/09/2026" (a tutorial adds "(Tutorial T1)"). |
| 8.23 | Saving fails halfway | Nothing saved (one transaction); an error asks you to validate again. |
| 8.24 | Download rejected rows / template | CSV with a `reason` column / header-only template with the Version 3 columns. |

## 9. Dashboard

| # | Do | Expected |
|---|---|---|
| 9.1 | All blocks, all courses | ✔ Five bordered cards: **Attendance rate 97.99%, Completeness 99.21%, Deducted marks 30, Students below threshold 0, Need attention 2**. Under them ● Present 477, ● Late 10, ● Excused 4, ● Absent 10, ● Not recorded 4 (dots in the chart colours) and "12 students · 44 class days · 6 tutorials". Caption "Showing: All blocks, All courses, from 31/08/2026 to 18/09/2026." |
| 9.1b | Sidebar with All blocks | ✔ Block, Course and only a **Custom dates** box (no Week box). |
| 9.1c | Charts with All blocks | ✔ The demo has only one block, so the charts are "Attendance rate by course" and "Recording status by course": PY101 **96.30%**, DS102 **98.63%**, MA103 **99.38%**. |
| 9.1d | Add a second block with a course, an enrolled student and one record; All blocks | ✔ "Attendance rate by block": one bar per block (B1-2627 97.99%). Choosing a block goes back to one bar per course. |
| 9.2 | Block → B1-2627 | ✔ The Course box lists only DS102, MA103 and PY101. A **Week** box: All weeks, Week 1 (31/08–04/09), Week 2 (07/09–11/09), Week 3 (14/09–18/09). Charts "by course": DS102 **98.63%**, MA103 **99.38%**, PY101 **96.30%**. |
| 9.2b | B1-2627 → Week 2 | ✔ Caption "Showing: B1-2627, All courses, Week 2 (07/09–11/09)." Cards 98.73%, 98.76%, Deducted marks 8, alerts 0. The PY101 Saturday tutorial 12/09 is in week 2. |
| 9.3 | B1-2627 → PY101, All weeks | ✔ 177 / 5 / 1 / 7 / 2 under the cards, 96.30%, 98.96%, "12 students · 15 class days · 2 tutorials". Charts "by week": **98.48%, 98.53%, 90.91%**. |
| 9.3b | Turn on **Show by day** | ✔ "Attendance rate by day": 16 bars (Mon 31/08 … Fri 18/09 and Sat 12/09; the 03/09 tutorial shares Thursday's bar). Mon 14/09 is 90.91%. |
| 9.4 | Tick **Custom dates** | ✔ A date range appears, starting at the chosen week or period. A range with no sessions gives an info message, no empty charts; only a start date gives "Choose an end date". |
| 9.5 | Rate chart | ✔ Each bar labelled with its %, axis 0 to 100. |
| 9.6 | Status chart | Stacked Present (blue), Late (light blue), Excused (pink), Absent (orange), Unknown (grey), at the same level as the rate chart. |
| 9.7 | Status filter: keep only Unknown / untick everything | Only grey parts, colours unchanged / info message. |
| 9.8 | Threshold 75% | ✔ "No students are below 75%." Card: 0. |
| 9.9 | Threshold 97% | ✔ **002 (90.00%), 009 (96.00%), 011 (96.88%), 010 (96.97%)**, lowest first. Card: **4**. |
| 9.10 | **Students needing attention**, default rules (2 / 3 / 75 / 10) | ✔ Exactly two rows: **002 PY101** "5 absences · Below 75% (70.59%) · 12 marks lost" (last absence 16/09/2026), then **009 PY101** "Absent the last 2 days" (18/09/2026). Card "Need attention": 2. |
| 9.11 | Absences at least **6** | ✔ 002's reasons become "Below 75% (70.59%) · 12 marks lost". |
| 9.11b | Absent the last **1** day | ✔ Only 009 has the recent reason (002 was Present on 17/09 and 18/09). |
| 9.11c | Attendance rate below **100** | ✔ 002, 009 (88.24%), 010 DS102 (90.00%), 005 MA103 (93.33%), 011 DS102 (93.75%). Pairs with only Lates (001, 004, 006, 012) stay at 100% and are not listed: Late counts as attended. |
| 9.11d | Rules nobody meets (9 / 9 / 0 / 99) | ✔ "No students need attention with these rules." Card: 0. |
| 9.11e | Sidebar: B1-2627 → PY101 → Week 3 | ✔ 002 "3 absences · Below 75% (40.00%)" and 009 "Absent the last 2 days": only the filtered days count. |
| 9.12 | Why is 002 not "absent recently"? | ✔ 002's longest streak in PY101 is 3 (14-16/09), but the **current** streak is 0 (Present on 17/09 and 18/09). |
| 9.13 | Excused or Unknown between two absences | ✔ Ends the streak: Absent, Excused, Absent = longest 1. |
| 9.14 | Settings: Late 2, Absent 3 | ✔ The Deducted marks card shows **50** (10 x 2 + 10 x 3). |

## 10. Reports

| # | Do | Expected |
|---|---|---|
| 10.1 | "All students" | Overall metrics, per-student table with **Deducted marks** and **Note**, attendance records (columns Student ID, Full name, Course, **Date, Day, Type**, Status; no session IDs), the deductions export; every table has a download (dates as DD/MM/YYYY). |
| 10.2 | Download the CSVs, open them | Same rows and numbers as on screen, including Deducted marks. |
| 10.3 | Student 002 | ✔ **43 / 2 / 0 / 5 / 0, 90.00%** overall, **Deducted marks 12**; By course: PY101 70.59%, deducted 12, longest streak 3. |
| 10.4 | Student 008 | ✔ 48 / 0 / 1 / 0 / 1, 100.00%, 98.00%. Deducted 0, Note **"1 not recorded"** (DS102 tutorial 17/09 is Unknown). |
| 10.4b | Deductions export → PY101 | ✔ 12 rows sorted by ID; columns Student ID, Full name, Late, Absent, Excused, Not recorded, Deducted marks; 002 = **12**. Downloads as `deductions_PY101.csv`. |
| 10.4c | Deductions export → DS102 | ✔ 008: Not recorded **1**, Deducted **0** (missing records never deduct). |
| 10.5 | Student 010 (late joiner) | ✔ 33 expected: 32 Present, 1 Absent, **96.97%**. "Enrolled from 07/09/2026"; the history (Course, Date, Day, Type, Status) starts on 07/09. |
| 10.6 | Student 012 (early leaver) | ✔ 21 expected: 20 Present, 1 Late, 100.00%. "Enrolled until 11/09/2026". |
| 10.4d | **Class register** → B1-2627 → PY101 | ✔ One row per student (sorted by ID); columns "Mon 31/08" … with "Tut 03/09" and "Tut 12/09" in date order; cells P / L / E / A / ?; then Present, Late, Excused, Absent, Unknown, Rate, Deducted. 002: **70.59%, 12**. |
| 10.4e | Register: 010 and 012 | ✔ 010 (late joiner) is "—" in week 1; 012 (early leaver) is "—" after 11/09, including the Saturday tutorial. |
| 10.4f | Register → DS102 | ✔ No "Wed 09/09" column (holiday). |
| 10.4g | Register → MA103 → Week 3 | ✔ Only 14/09 to 18/09, including "Tut 16/09" and "Tut 16/09 (T2)" (005: E, E). Totals count that week only (002 in PY101 week 3: 3 Absent, 6 deducted). The download equals the table. |
| 10.4h | Student 002 → **Weekly view** → PY101 | ✔ Week 1: ✅ ❌ 🕐 ✅ ✅, tutorials "03/09 ✅"; week 2: ✅ ❌ ✅ 🕐 ✅, "12/09 ✅"; week 3: ❌ ❌ ❌ ✅ ✅. Under it: 70.59%, Deducted marks **12**. The CSV uses words (Present, Absent, …, No class). |
| 10.4i | Weekly view: 010 in PY101, 001 in DS102, 005 in MA103, 003 in PY101 | ✔ 010's week 1 is all "—"; DS102 week 2 Wednesday is "—" (holiday); MA103 week 3 tutorials "16/09 📝, 16/09 (T2) 📝"; 003's Wed 09/09 is ❔. |
| 10.7 | Student 003 + course DS102 | Info message (003 isn't in DS102). |
| 10.8 | Change filters while a student is selected | The report follows the filters. |

## 11. Robustness

| # | Do | Expected |
|---|---|---|
| 11.1 | Refresh the browser mid-task | No crash. Unsaved input lost, saved data stays. |
| 11.2 | Two browser tabs at once | Both work. Refresh to see the other tab's changes. |
| 11.3 | Type `' OR 1=1 --` as a name or search | Rejected by validation. SQL uses `?` parameters anyway. |
| 11.4 | OneDrive syncing during the demo | Risk of "database is locked". **Pause OneDrive.** |

---

## Answers to have ready

- **Why are class days generated?** At AIMS every course meets every weekday of its block. Generating them means tutors never type session IDs, and a class can't be put on a weekend by mistake. Holidays are removed; tutorials are added by date.
- **How are marks deducted?** Late x 1 + Absent x 2 per course by default; both values are settings (0 to 10). Excused and Present deduct nothing. A missing record deducts nothing but is flagged "not recorded", so the tutor fixes the data before the grade sheet. There is no maximum, because the rule as given has none. Tutorials count like classes.
- **Why is Excused not in the attendance rate?** The student was allowed to miss it: counting it as absent is unfair, counting it as present is untrue. It still counts for completeness because it is recorded. Late counts as attended.
- **Why is Unknown not Absent?** Missing data isn't evidence of absence. 7 Present, 2 Absent, 1 Unknown = 77.78% attendance and 90% completeness, not 70%.
- **Why do alerts use the current streak?** An alert should point to a student who is absent *now*. 002 had 3 absences in a row but came back; 009 is absent on the last two days.
- **Course dates vs enrollment dates?** Course dates say when class days happen (inside the block). Enrollment dates say when a particular student is expected. Most students follow the course; late start or early leave is the exception.
- **Why does "Mark all Present" not overwrite saved records?** It fills only the students with no status yet, so a saved Absent can't be lost by one click. Change the exceptions, then save.
- **Why doesn't import create courses?** A typo like `PY11` would silently create a fake course.
- **Why skip duplicates but reject conflicts?** A duplicate changes nothing. A conflict means one value is wrong, so a person must decide. Nothing is overwritten silently.
- **How is delete made safe?** Every delete previews what it removes, with counts, needs a "cannot be undone" tick, and runs in one transaction. A block can only be deleted when it has no courses.
- **What happens to an old database?** `create_tables()` upgrades it: new tables and columns are added, old sessions become Class days, old courses show "No block", and every record is kept.
- **Why "below" is strictly less than?** Someone exactly at the threshold has met it.
