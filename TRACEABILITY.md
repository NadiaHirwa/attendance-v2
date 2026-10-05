# Traceability: requirement -> code -> test

Each requirement in [ATTENDANCE_V2_SPEC.md](ATTENDANCE_V2_SPEC.md) with the function(s)
that implement it and the test(s) or demo step that check it.
Test names refer to methods in `tests/test_validation.py`, `tests/test_analytics.py`,
`tests/test_importer.py`, `tests/test_database.py` and `tests/test_enrollment_dates.py`.

## Data model (Section 3)

| Requirement | Function(s) | Test or check |
|---|---|---|
| Schema exactly as Section 3 | `database.SCHEMA`, `database.create_tables` | Every database test creates the tables with it |
| Older `attendance.db` gets the enrollment date columns | `database.create_tables`, `database.add_enrollment_date_columns` | `test_old_database_gets_date_columns` |
| `PRAGMA foreign_keys = ON` on every connection | `database.get_connection` | T14: `test_t14_foreign_keys_pragma`, `test_t14_foreign_keys_are_on` |
| Unknown is never stored | `database.get_expected_records`, `analytics.build_records_frame` | `test_unknown_is_not_stored` |

## Business rules (Section 4)

| Requirement | Function(s) | Test or check |
|---|---|---|
| BR-01 Student ID | `validation.is_valid_student_id` | T01: `test_t01_student_id` |
| BR-02 Full name | `validation.clean_name`, `validation.is_valid_name` | T02: `test_t02_valid_names`, `test_t02_invalid_names`, `test_t02_clean_name_collapses_spaces` |
| BR-03 Course code | `validation.normalize_course_code` | T03: `test_t03_course_code` |
| BR-04 Course name | `validation.clean_course_name` | Manual demo step: create a course with an empty name |
| BR-05 Session ID | `validation.is_valid_session_id`, `validation.normalize_session_id` | Manual demo step: create a session with an invalid ID such as `W 1` |
| BR-06 Session date | `validation.parse_date` | T04: `test_t04_session_date`; `test_format_errors_name_the_value` |
| BR-07 Status | `validation.normalize_status` | T05: `test_t05_status` |
| BR-08 One record per student per session | `database.record_attendance` | T13: `test_t13_recording_twice_updates`, `test_t13_same_status_is_not_rewritten` |
| BR-09 Only enrolled students | `database.record_attendance`, `database.import_records` (enrolls first) | `test_not_enrolled_is_not_saved`, `test_new_student_is_enrolled_and_saved` |
| BR-10 Attendance rate | `analytics.calculate_rates`, `analytics.format_rate` | T06: `test_t06_worked_example`, `test_t06_worked_example_from_database`; T07: `test_t07_no_records` |
| BR-11 Completeness | `analytics.calculate_rates` | T06, T07 (same tests) |
| BR-12 Unknown | `analytics.build_records_frame`, `analytics.count_statuses` | `test_t06_worked_example_from_database`, `test_unknown_is_not_stored` |
| BR-13 Error messages | Message constants in `validation.py` | `test_format_errors_name_the_value`, `test_t09_unknown_course`; manual demo step: `-Nadia` |
| BR-14 Absence streaks | `analytics.calculate_streaks`, `analytics.statuses_in_session_order` | `test_absent_absent_present_absent`, `test_unknown_breaks_the_streak`, `test_no_records`, `test_ends_with_present`, `test_ends_with_unknown`, `test_streaks_respect_filters` |
| BR-15 Enrollment dates | `validation.is_in_enrollment_window`, `validation.are_enrollment_dates_valid`, `database.get_expected_records`, `database.get_session_attendance`, `database.record_attendance` | `test_window_with_no_dates`, `test_window_start_and_end_are_included`, `test_window_outside`, `test_end_before_start_is_invalid`, `test_null_dates_behave_like_before`, `test_late_joiner`, `test_student_who_left`, `test_start_and_end`, `test_outside_window_is_not_saved`, `test_on_start_date_is_saved` |

## CSV import rules (Section 5)

| Requirement | Function(s) | Test or check |
|---|---|---|
| IR-01 UTF-8 and required columns | `importer.read_csv`, `importer.find_missing_columns` | T08: `test_t08_missing_status_column`; `test_headers_any_case_and_extra_columns`, `test_not_utf8` |
| IR-02 Row validation with reason | `importer.clean_row`, `importer.make_format_reason` | `test_format_errors_name_the_value` |
| IR-03 Unknown course | `importer.validate_rows`, `database.course_exists` | T09: `test_t09_unknown_course` |
| IR-04 Student name conflict | `importer.check_student` | T12: `test_t12_saved_id_with_different_name`, `test_t12_name_case_is_ignored`, `test_new_id_with_two_names_in_file` |
| IR-05 Session conflict | `importer.check_session` | `test_saved_session_with_different_date`, `test_new_session_with_two_courses_in_file` |
| IR-06 Automatic enrollment | `database.import_records` | `test_new_student_is_enrolled_and_saved` |
| IR-07 Exact duplicates skipped | `importer.check_status` | T10: `test_t10_same_row_twice`, `test_t10_already_saved` |
| IR-08 Conflicting status rejected | `importer.check_status` | T11: `test_t11_conflicting_status` |
| IR-09 Nothing written before Confirm | `importer.validate_rows` (read only), `importer.apply_import`, `database.import_records` (one transaction), `app.show_import_tab`, `app.confirm_import` | `test_validation_never_writes`, `test_failure_saves_nothing`; manual demo step 5 |
| IR-10 Filename as source | `importer.apply_import`, `database.import_records` | `test_new_student_is_enrolled_and_saved` |
| IR-11 Result counts and rejected download | `app.show_review`, `app.show_last_import_result`, `importer.make_table` | Manual demo step 5 |

## Functional requirements (Section 6)

| Requirement | Function(s) | Test or check |
|---|---|---|
| FR-01 Four tabs | `app.main` | Manual demo step 1 |
| FR-02 Data kept in `attendance.db` | `database.get_connection`, `database.DB_PATH` | Manual demo step 8 (close and reopen) |
| FR-03 Create a course | `app.show_add_course`, `database.add_course`, `database.course_exists` | T03; manual demo step 3 |
| FR-04 Add and enroll a student, same-name warning | `app.show_add_student`, `database.add_student`, `database.find_students_by_name` | T01, T02; manual demo step 3 (`-Nadia`, `NADIA HIRWA`) |
| FR-05 Enroll in another course | `app.show_enroll_student`, `database.enroll_student`, `database.is_enrolled` | Manual demo step |
| FR-06 Create a session | `app.show_add_session`, `database.add_session` | T04; manual demo step |
| FR-07 Record attendance | `app.show_record_attendance`, `app.save_attendance_table`, `database.get_session_attendance`, `database.record_attendance` | T13; manual demo step 4 |
| FR-08 Correct attendance | `app.save_attendance_table`, `database.record_attendance` | `test_t13_recording_twice_updates`, `test_t13_same_status_is_not_rewritten`; manual demo step 4 |
| FR-09 Search students | `app.find_students`, `app.show_search_students`, `database.get_student`, `database.find_students_by_name`, `database.get_student_courses` | Manual demo step |
| FR-10 Import workflow | `app.show_import_tab`, `importer.read_csv`, `importer.validate_rows`, `importer.apply_import` | T08 to T12; manual demo step 5 |
| FR-11 Empty CSV template | `importer.make_template_csv`, `app.show_template_download` | `test_template_has_required_columns` |
| FR-12 Course and date filters | `app.show_filters`, `analytics.filter_records`, `analytics.get_date_bounds` | `test_seed_totals_all_courses_full_range`, `test_filter_one_course`, `test_filter_date_range_includes_both_ends`; manual demo step 2 |
| FR-13 Dashboard metrics | `app.show_metrics`, `analytics.calculate_dashboard_metrics` | `test_seed_totals_all_courses_full_range`, `test_filter_one_course` |
| FR-14 Rate by session chart | `app.show_rate_chart`, `analytics.build_rate_chart_data`, `analytics.build_session_summary` | `test_chart_data_in_date_order` |
| FR-15 Students below threshold | `app.show_threshold_list`, `analytics.split_by_threshold`, `analytics.build_student_summary` | `test_students_below_threshold_sorted`, `test_student_without_records_listed_separately` |
| FR-16 Report tables | `app.show_reports_tab`, `app.show_all_students_report`, `app.show_summary_metrics`, `analytics.build_attendance_report`, `analytics.format_summary_table` | `test_reports_tables` |
| FR-17 Downloads match the screen | `app.show_table_with_download` (one DataFrame for both) | Manual demo step 6 |
| FR-18 Message instead of empty data | `app.has_data_to_show`, `app.show_rate_chart`, info messages in each Manage section | `test_filter_with_no_sessions`, `test_t07_empty_frame`; manual demo step |
| FR-19 Single student report | `app.show_reports_tab`, `app.show_single_student_report`, `app.show_summary_metrics`, `analytics.filter_student`, `analytics.summarize_frame`, `analytics.build_course_summary`, `analytics.build_student_history`, `analytics.format_summary_table`, `app.show_table_with_download` | `test_two_course_student_by_hand`, `test_course_breakdown_by_hand`, `test_all_three_statuses_by_hand`, `test_history_in_date_order_with_unknown`, `test_student_report_respects_filters`, `test_student_outside_filters_is_empty` |
| FR-20 Recording status chart | `app.show_status_chart`, `analytics.build_status_chart_data`, `analytics.make_status_chart_long`, `analytics.keep_statuses`, `analytics.labels_need_year`, `analytics.make_session_label` | `test_status_chart_counts_add_up_to_enrolled`, `test_status_chart_by_hand`, `test_status_chart_same_labels_and_order_as_rate_chart`, `test_status_chart_keeps_unrecorded_session`, `test_status_chart_long_shape`, `test_status_chart_keep_statuses` |
| FR-21 Absence alerts and streaks per course | `app.show_absence_alerts`, `app.show_single_student_report`, `analytics.build_streak_table`, `analytics.find_streak_alerts`, `analytics.find_last_absence_date`, `analytics.build_course_summary`, `analytics.calculate_streaks` | `test_seed_streaks_by_hand`, `test_seed_alerts_default`, `test_seed_alerts_sorted_highest_first`, `test_streaks_respect_filters`, `test_course_summary_has_streaks`, `test_empty_records_give_no_alerts` |
| FR-22 Rename a student or course | `app.show_rename_student`, `app.show_rename_course`, `database.rename_student`, `database.rename_course`, `database.get_course_name`, `validation.clean_name`, `validation.is_valid_name`, `validation.clean_course_name` | `test_rename_student`, `test_rename_course`, `test_rename_values_are_validated`; manual demo step: "No change" and the same-name warning |
| FR-23 Delete with confirmation | `app.show_delete_attendance_record`, `app.show_unenroll_student`, `app.show_delete_student`, `app.show_delete_session`, `app.show_delete_course`, `app.ask_to_confirm`, `database.delete_attendance_record`, `database.unenroll_student`, `database.delete_student`, `database.delete_session`, `database.delete_course`, `database.count_unenroll`, `database.count_delete_student`, `database.count_delete_session`, `database.get_course_usage` | `test_delete_present_record`, `test_delete_absent_record`, `test_unenroll_removes_course_records_only`, `test_unenroll_with_missing_record`, `test_delete_student_removes_everything`, `test_deleted_id_can_be_used_again`, `test_delete_session`, `test_refused_with_sessions_and_students`, `test_refused_with_only_a_student`, `test_refused_with_only_a_session`, `test_empty_course_is_deleted` |
| FR-24 Enrollment dates on screens and in import | `app.show_enrollment_date_inputs`, `app.show_add_student`, `app.show_enroll_student`, `app.show_record_attendance`, `app.show_change_enrollment_dates`, `database.enroll_student`, `database.get_enrollment`, `database.update_enrollment_dates`, `database.count_records_outside_window`, `database.import_records`, `importer.check_enrollment_dates`, `importer.find_enrollment_starts`, `analytics.build_course_summary`, `analytics.format_enrollment_date` | `test_seed_dates_are_null_and_totals_unchanged`, `test_record_attendance_list_follows_dates`, `test_change_refused_when_records_fall_outside`, `test_change_allowed_when_no_records_outside`, `test_new_student_starts_at_earliest_row`, `test_existing_student_new_course_starts_at_row`, `test_row_before_start_is_rejected`, `test_row_after_end_is_rejected`, `test_by_course_shows_start_and_now`, `test_by_course_shows_dates` |

## Non-functional requirements (Section 7)

| Requirement | Function(s) | Test or check |
|---|---|---|
| NFR-01 No crash on any input | All validation returns `None` or `False` instead of raising; `importer.read_csv` catches decoding and CSV errors; `app.confirm_import` catches database errors | `test_not_utf8`, `test_t08_missing_status_column`, `test_failure_saves_nothing`; manual demo step 5 |
| NFR-02 Rules and calculations without Streamlit | `validation.py`, `database.py`, `analytics.py`, `importer.py` | All unit tests import these modules without Streamlit running |
| NFR-03 PEP 8, docstrings, constants at the top | Every module | Code review (lines at most 99 characters, see spec Section 11) |
| NFR-04 SQL uses `?` parameters | Every query in `database.py` | Code review |
| NFR-05 `python -m unittest` passes | `tests/` | Manual demo step 7 |
