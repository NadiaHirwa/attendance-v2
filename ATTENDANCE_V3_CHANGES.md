# Attendance System: Version 3 Changes (tutor feedback)

| Item | Detail |
|---|---|
| Version | 3.0, scope FROZEN after tutor feedback |
| Author | Nadia Iradukunda Hirwa |
| Builds on | `ATTENDANCE_V2_SPEC.md`, now renamed `ATTENDANCE_SPEC.md` (every rule there stays unless changed here) |
| Source | Tutor comments, October 2026 |
| Status | **Built.** Stages 0 to 6 complete; all merged into `ATTENDANCE_SPEC.md` and released (Stage 6: verification for Version 3). **Version 3.1** (Stage 7, tutor review): week filter, KPI cards, drill-down charts, student titles, no session IDs on screen, fix rejected rows in place and S5; released. |

This file lists only what **changes or is added**. Stage 0 merges it into the main specification.
After Stage 0 it is kept as the **change log** for Version 3; `ATTENDANCE_SPEC.md` is the full specification.

> **Numbering note (Stage 0):** FR-26 was already used in Version 2 (Late and Excused statuses),
> so the new requirements were renumbered one up: weekly view **FR-27**, class register **FR-28**,
> deductions **FR-29**, dashboard filter **FR-30**, import auto-fix **FR-31**. The stage prompts
> below use the new numbers. The business rules BR-18 to BR-24 are unchanged.

---

## 1. Why Version 3

At AIMS, teaching is organised in **blocks**: a block lasts **3 weeks**, contains **2 to 4 courses**, and every course meets **every weekday** (Monday to Friday) of the block. There are also **tutorials**, which can happen on any date inside the course period. Lateness and absence cost marks: **Late −1, Absent −2, per course**.

Version 2 used free-form "sessions" with typed IDs. Version 3 uses the school's real structure, so tutors type less and the system makes fewer assumptions.

---

## 2. Data model changes

```sql
blocks   (block_id TEXT PRIMARY KEY,         -- e.g. B1-2627, stored uppercase
          block_name TEXT NOT NULL,          -- e.g. "Block 1, 2026-27"
          start_date TEXT NOT NULL,          -- always a Monday
          end_date   TEXT NOT NULL)          -- calculated: Friday of week 3

courses  (+ block_id TEXT REFERENCES blocks)  -- required for new courses;
          start_date / end_date stay, default = block dates (exception: narrower, inside the block)

sessions (+ session_type TEXT NOT NULL CHECK (session_type IN ('Class', 'Tutorial')))
          session_id is generated, never typed:
            Class:    PY101-2026-09-07
            Tutorial: PY101-2026-09-10-T1  (T1, T2... if several on the same date)
          UNIQUE (course_code, session_date) for Class sessions

settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)
          late_deduction = 1, absent_deduction = 2
```

- **Upgrade of an old database:** add the new columns and tables. Old sessions become type `Class`. Old courses keep working with `block_id` NULL (shown as "No block"). Seed totals are recalculated from the new demo data (section 9).

---

## 3. Business rules

| ID | Rule |
|---|---|
| BR-18 | **Block:** ID 2 to 10 letters, digits or hyphens (uppercase). Start date must be a **Monday**. End date = start + 18 days (Friday of week 3), calculated, never typed. Constant `BLOCK_WEEKS = 3`. |
| BR-19 | **Course in a block:** course dates default to the block dates. Exception: they may be narrowed, but must stay inside the block. |
| BR-20 | **Class days are generated:** when a course is created (or its dates change), one `Class` session is created for **every Monday to Friday** in the course period. Weekends never get class days. Removing a class day (holiday) is allowed, with confirmation; its records go with it. |
| BR-21 | **Tutorials:** added by hand, any date (weekends allowed) inside the course period. Several per week and several per date are allowed (numbered T1, T2...). Tutorials count exactly like classes for attendance, rates and deductions. |
| BR-22 | **Deductions:** per student per course: `Late × late_deduction + Absent × absent_deduction`. Defaults 1 and 2. **Excused and Present deduct 0. Unknown deducts 0 but is flagged** ("N not recorded"). **No maximum.** Both values are settings, editable on screen (whole numbers 0 to 10). |
| BR-23 | **Dates on screen and in downloads use DD/MM/YYYY.** Stored as YYYY-MM-DD. Files may use DD/MM/YYYY or YYYY-MM-DD. `07/09/2026` always means 7 September. |
| BR-24 | **Student ID rule lives in one function** (`validation.is_valid_student_id`). It stays 3 digits for now. Future AIMS format: `AIMS` + academic year (4 digits, e.g. 2627) + 5 digits, e.g. `AIMS262766658`. |

---

## 4. Manage Attendance: new sub-tabs

The separate "Edit & Delete" sub-tab is **removed**. Everything about a thing lives in its own sub-tab.

| Sub-tab | Contains |
|---|---|
| **Blocks & Courses** | Create block (start Monday → end calculated). Create course in a block (dates default to the block; optional narrower period). List of blocks with their courses. Per course: rename, change period (inside block, class days regenerate), enrolled students, delete (rules from FR-23). Delete block only when it has no courses. |
| **Students** | Search first. Selecting a student opens a **student profile**: courses with enrollment period, attendance counts, rate, completeness, **deducted marks per course**, rename, enroll / un-enroll, late start or early leave, delete. Below: Add student. |
| **Class days & Tutorials** | Pick a course: list of class days (DD/MM/YYYY, weekday) and tutorials. Add tutorial (date inside course period). Remove a class day or tutorial (holiday), with confirmation and record count. |
| **Record attendance** | Pick block → course → day. **Defaults to today** if today is a class day. Button **"Mark all Present"**, then change the exceptions. Statuses as before. |
| **Settings** | Late deduction and Absent deduction (whole numbers 0 to 10). |

---

## 5. New views

**FR-27 Weekly view (Reports):** select a student and a course. Grid:

| Week | Mon | Tue | Wed | Thu | Fri | Tutorials |
|---|---|---|---|---|---|---|
| Week 1 (07/09) | ✅ Present | 🕐 Late | ✅ | ✅ | ❌ Absent | 10/09 ✅ |

- Cell symbols: ✅ Present, 🕐 Late, 📝 Excused, ❌ Absent, ❔ Not recorded, — no class (removed day, or outside the enrollment period).
- Tutorials column lists every tutorial that week as `DD/MM symbol`.
- Under the grid: Present, Late, Excused, Absent, Unknown, rate, completeness, **deducted marks**. CSV download.

**FR-28 Class register (Reports):** select a course (and optionally a week). Rows = enrolled students, columns = every class day and tutorial (`Mon 07/09`, `Tut 10/09`), cells = P / L / E / A / ?, then totals and **Deducted** column. Sorted by student ID. CSV download.

**FR-29 Deductions everywhere:** "Deducted marks" column in the per-student summary, the student profile, the student report and all downloads. **Deductions export:** one CSV per course with student ID, name, Late, Absent, deducted marks, ready for the grade sheet.

**FR-30 Dashboard filter:** Block → Course (course list limited to the chosen block) → date range (defaults to the block or course period).

---

## 6. CSV import changes

**New columns:** `course_code, date, student_id, full_name, status` and optional `type` (`Class` default, or `Tutorial`). `session_id` is no longer used (ignored if present).

| Rule | Behaviour |
|---|---|
| Class row | Must match an existing class day of that course. Weekend or removed day → rejected: "Row 7: PY101 has no class on Saturday 12/09/2026." |
| Tutorial row | Creates the tutorial if none exists on that date, inside the course period. |
| Other rules | Duplicates, conflicts, enrollment periods, unknown course: as in Version 2. |

### FR-31 Auto-fix and suggested fixes

**The program never invents a new identity on its own.** It repairs what is safe and proposes the rest for a person to accept.

| Problem | Action |
|---|---|
| Spaces, capitals, `p` / `absent`, curly apostrophes | **Auto-fix** (as before) |
| ID `4` or `04` (Excel removed zeros) | **Auto-fix** to `004`, listed as a fix |
| Date `7/9/2026` or `07/09/2026` | **Auto-fix** to the stored form, listed as a fix |
| Saved ID, **similar** name (difflib ratio ≥ 0.8, e.g. `Eric Niyonzimana` vs `Eric Niyonzima`) | **Suggest:** "Use saved name Eric Niyonzima" (Accept / Reject) |
| Saved ID, **different** name | **Suggest:** "Assign next free ID 013 as a new student" (Accept / Reject) |
| Same new ID twice in the file with different names | **Suggest** the next free ID for the later rows |
| Status differs from the saved record | **Suggest:** "Keep saved Absent" (default) or "Use file: Present" |

- Review screen shows three lists: **Auto-fixed** (read-only, with before → after), **Suggestions** (checkbox per row, all unticked by default), **Rejected** (with reasons).
- **Apply suggestions** re-validates. Nothing is saved before **Confirm**, and Confirm still uses one transaction.
- **Download cleaned file:** the file with all auto-fixes and accepted suggestions applied, in the new column format.
- Every fix and accepted suggestion is listed in the result, so the tutor can see exactly what changed.

---

## 7. Known limitations (updated)

- No login (unchanged).
- Student IDs are 3 digits, not yet the AIMS format.
- One Class session per course per day.
- A course belongs to exactly one block.

## 8. Future work (updated)

Login and roles; AIMS ID format; school holiday calendar; email alerts; shared server database.

## 9. Demo data (rebuild)

- Block `B1-2627`, "Block 1, 2026-27", 07/09/2026 to 25/09/2026.
- 3 courses: PY101 Programming with Python, DS102 Data Science Basics, MA103 Mathematics for Data Science.
- 12 students. Most in all three courses, a few in two, one **late joiner** (from week 2) and one **early leaver**.
- 15 class days per course, **one removed as a holiday** in one course, and **2 tutorials per course**.
- A realistic mix of Present, Late, Excused and Absent, a few Unknown, at least one student with 2+ absences in a row, at least one with deductions over 10.
- Fixed data: every run gives the same numbers. `seed_demo.py` prints the totals **and the deductions per student per course**. Verify at least two students by hand and put them in tests.
- `demo_data/messy_import.csv` and `clean_import.csv` rewritten for the new columns. The messy file must trigger every auto-fix and every suggestion type, plus the usual rejections.

---

# Prompts for Claude in VS Code

**Rules for every stage:** one stage per prompt; wait for its report; restart Streamlit; check; then the next.
**Commit after each stage, but do NOT push** (pushing redeploys the live app). Push once, at the end of Stage 6.

### Stage 0: merge the specification

```
Read ATTENDANCE_V3_CHANGES.md. Merge it into the main specification: rename ATTENDANCE_V2_SPEC.md to
ATTENDANCE_SPEC.md (git mv), add every new and changed rule (BR-18 to BR-24, FR-27 to FR-31, the new
Manage sub-tabs, import columns, limitations, future work, demo data), and mark what Version 3 replaces.
Keep ATTENDANCE_V3_CHANGES.md as the change log. Update README references. No code changes.
Commit: "Version 3 specification from tutor feedback". Do not push.
No Co-Authored-By line or mention of yourself in any commit.
```

### Stage 1: blocks, class days, tutorials, dates

```
Build Stage 1 of ATTENDANCE_SPEC.md (Version 3): data model and rules only, plus the minimum screens
to use them. BR-18, BR-19, BR-20, BR-21, BR-23 and the new import columns (without auto-fix, that is
Stage 5).
- blocks table, courses.block_id, sessions.session_type, generated session IDs, database upgrade of
  an old attendance.db (old sessions become Class, old courses keep working with no block).
- Generating class days: every Monday to Friday in the course period; regenerate when the period
  changes, refusing (with counts) if saved records would be lost.
- Tutorials: add by date, numbered T1, T2...
- Display every date as DD/MM/YYYY (one helper function in validation.py); accept DD/MM/YYYY and
  YYYY-MM-DD in files; store YYYY-MM-DD.
- Rebuild seed_demo.py with the Version 3 demo data (section 9), and print totals and deductions.
- Update tests: new rules, upgrade test, and seed totals verified by hand for at least two students.
Simple, readable code as before. Use .venv\Scripts\python. Run all tests. Commit:
"Stage 1: blocks, class days and tutorials". Do not push. No Co-Authored-By line.
Tell me the new seed totals and two students' numbers you checked by hand.
```

### Stage 2: Manage tab reorganised

```
Build Stage 2 of ATTENDANCE_SPEC.md: the new Manage Attendance sub-tabs (section 4 of
ATTENDANCE_V3_CHANGES.md): Blocks & Courses, Students (search + student profile), Class days &
Tutorials, Record attendance (default today, "Mark all Present"), Settings. Remove the "Edit & Delete"
sub-tab: move each rename/delete/date form into the sub-tab of the thing it changes. Keep every existing
rule and confirmation. No new calculations except what the profile needs from analytics.py.
Update TEST_CHECKLIST.md sections for Manage. Run all tests. Commit:
"Stage 2: Manage tab grouped by blocks, students, class days". Do not push. No Co-Authored-By line.
```

### Stage 3: mark deductions

```
Build Stage 3 of ATTENDANCE_SPEC.md: BR-22 and FR-29. settings table with late_deduction = 1 and
absent_deduction = 2, editable in Manage > Settings (whole numbers 0 to 10). Deducted marks in
analytics.py (one function), shown in the per-student summary, student profile, student report and
all downloads; "N not recorded" flag for Unknown. Deductions export per course (CSV).
Tests: a worked example by hand (e.g. 2 Late + 3 Absent = 8 with defaults, 13 with Late 2 / Absent 3),
Excused deducts 0, Unknown deducts 0 and is flagged, tutorials count, no maximum, and two seed students.
Run all tests. Commit: "Stage 3: mark deductions". Do not push. No Co-Authored-By line.
```

### Stage 4: weekly view and class register

```
Build Stage 4 of ATTENDANCE_SPEC.md: FR-27 weekly view and FR-28 class register in the Reports tab,
and FR-30 Block -> Course dashboard filter. Grids built in analytics.py as DataFrames (testable), app.py
only displays them. Symbols and "—" rules exactly as in the specification; DD/MM/YYYY dates.
Tests: a student with a removed holiday, a late joiner (— before the start), two tutorials in one week,
and totals/deductions under the grid matching Stage 3. CSV downloads equal what is shown.
Run all tests. Commit: "Stage 4: weekly view and class register". Do not push. No Co-Authored-By line.
```

### Stage 5: import auto-fix and suggested fixes

```
Build Stage 5 of ATTENDANCE_SPEC.md: FR-31. Auto-fix and suggestions live in importer.py as plain
functions (no Streamlit), each returning what changed and why. Review screen: Auto-fixed (before ->
after), Suggestions (checkbox per row, unticked by default), Rejected; "Apply suggestions" re-validates;
Confirm saves in one transaction; "Download cleaned file". Never create a new ID without an accepted
suggestion. Rewrite demo_data/messy_import.csv so it triggers every auto-fix and every suggestion type.
Tests for each auto-fix, each suggestion, the next-free-ID choice, "keep saved" as default for status
conflicts, and that nothing is written before Confirm.
Run all tests. Commit: "Stage 5: import auto-fix and suggested fixes". Do not push. No Co-Authored-By line.
```

### Stage 6: verify and redeploy

```
Stage 6: verification only, no new features.
1. Run all tests and report the count.
2. Review every module against ATTENDANCE_SPEC.md and list any requirement not met (file and line);
   fix only real failures.
3. Update TRACEABILITY.md, TEST_CHECKLIST.md (with the new key numbers from seed_demo.py) and README.md.
4. Run seed_demo.py. Commit: "Stage 6: verification for Version 3".
5. Then push to origin main (this redeploys the live app) and tell me when it is pushed.
No Co-Authored-By line or mention of yourself in any commit.
```

**Stage 6 fixes (done):** zero-padded `DD/MM/YYYY` is the normal import form and is not listed as an auto-fix (only forms such as `24/9/2026` or `2026-09-24` are); the cleaned file writes `DD/MM/YYYY`. A class row on a removed weekday says "(class day removed)"; a weekend keeps the plain message. The review also found that an import stored an enrollment start equal to the course start instead of NULL (BR-17); fixed.
