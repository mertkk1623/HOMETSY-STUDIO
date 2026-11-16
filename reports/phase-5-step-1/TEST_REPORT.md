# Phase 5 / Step 1 — Test Report

**Project:** Hometsy — Room Intelligence Studio
**Date:** 2026-11-14
**Python:** 3.13.18 (`.venv\Scripts\python.exe`)
**Test framework:** pytest

All results below are copied from actual command output run in this session.
No live API call was made and no socket opened.

---

## 1. Test Commands

Run from the project root `[PROJECT_ROOT]`.

| # | Command | Purpose |
|---|---|---|
| 1 | `& ".venv\Scripts\python.exe" -m pytest tests/test_workflow_dependencies.py -q` | Dependency table |
| 2 | `& ".venv\Scripts\python.exe" -m pytest tests/test_workflow_state.py -q` | State behaviour |
| 3 | `& ".venv\Scripts\python.exe" -m pytest tests/test_workflow_integration.py -q` | Workflow ↔ AI seam |
| 4 | `& ".venv\Scripts\python.exe" -m pytest -q` | Full suite |
| 5 | `& ".venv\Scripts\python.exe" -m pytest --collect-only -q` | Per-file counts |
| 6 | `& ".venv\Scripts\python.exe" -c "<AppTest script>"` | Streamlit render check |

---

## 2. Test Counts

### Before this step

| File | Tests |
|---|---:|
| `tests/test_ai_client.py` | 58 |
| `tests/test_ai_config.py` | 30 |
| `tests/test_ai_parsing.py` | 112 |
| `tests/test_ai_prompt.py` | 38 |
| `tests/test_ai_services.py` | 70 |
| `tests/test_budget_engine.py` | 34 |
| `tests/test_data_library.py` | 34 |
| `tests/test_models.py` | 54 |
| `tests/test_room_engine.py` | 48 |
| `tests/test_spatial_engine.py` | 45 |
| `tests/test_validation.py` | 35 |
| **Total** | **558** |

### Added in this step

| File | Tests |
|---|---:|
| `tests/test_workflow_dependencies.py` (new) | 35 |
| `tests/test_workflow_state.py` (new) | 83 |
| `tests/test_workflow_integration.py` (new) | 9 |
| **Added** | **127** |

### After this step

| File | Tests |
|---|---:|
| `tests/test_ai_client.py` | 58 |
| `tests/test_ai_config.py` | 30 |
| `tests/test_ai_parsing.py` | 112 |
| `tests/test_ai_prompt.py` | 38 |
| `tests/test_ai_services.py` | 70 |
| `tests/test_budget_engine.py` | 34 |
| `tests/test_data_library.py` | 34 |
| `tests/test_models.py` | 54 |
| `tests/test_room_engine.py` | 48 |
| `tests/test_spatial_engine.py` | 45 |
| `tests/test_validation.py` | 35 |
| `tests/test_workflow_dependencies.py` | 35 |
| `tests/test_workflow_integration.py` | 9 |
| `tests/test_workflow_state.py` | 83 |
| **Total** | **685** |

**558 → 685 (+127).**

---

## 3. Results

### New test files

```
.................................                                        [100%]
35 passed in 0.03s          # test_workflow_dependencies.py

........................................................................ [ 86%]
...........                                                              [100%]
83 passed in 0.09s          # test_workflow_state.py

.........                                                                [100%]
9 passed in 0.04s           # test_workflow_integration.py
```

### Full suite

```
........................................................................ [ 94%]
.....................................                                    [100%]
685 passed in 0.68s
```

### Summary

| Metric | Value |
|---|---:|
| Total tests | 685 |
| Passed | 685 |
| Failed | **0** |
| Errors | **0** |
| Skipped | **0** |
| Deselected / xfail | **0** |
| Runtime | ~0.7 s |

No test was skipped, deselected or marked xfail. No test was weakened to pass.

---

## 4. Coverage of Step 1 Requirements

Each required scenario from the brief, mapped to the tests that prove it.

### 4.1 Initial state creation

| Requirement | Test |
|---|---|
| A fresh state is empty | `test_fresh_state_is_empty` |
| A fresh state starts at step 1 | `test_fresh_state_starts_at_room_information` |
| A fresh state is not finished | `test_fresh_state_is_not_finished` |
| Only step 1 is runnable at the start | `test_only_the_first_step_is_runnable_on_a_fresh_state` |
| Step order matches the approved workflow | `test_step_order_matches_the_approved_workflow` |
| First input assignment invalidates nothing | `test_first_room_assignment_invalidates_nothing` |

### 4.2 Steps advance in the correct order

| Requirement | Test |
|---|---|
| All ten steps advance in sequence | `test_steps_advance_in_order` |
| Completed steps are contiguous from the start | `test_completed_steps_are_contiguous_from_the_start` |
| Spatrial and budget are independent siblings | `test_spatial_and_budget_are_independent_of_each_other` |
| Outstanding steps are listed in order | `test_outstanding_steps_lists_everything_remaining` |

### 4.3 A step without prerequisites is blocked

| Requirement | Test |
|---|---|
| Brief blocked without inputs | `test_brief_cannot_be_recorded_without_inputs` |
| Concepts blocked without a brief | `test_concepts_cannot_be_recorded_without_a_brief` |
| Selection blocked without concepts | `test_selection_cannot_happen_without_concepts` |
| Recommendations blocked without a selection | `test_recommendation_requires_a_selection` |
| Spatial blocked without recommendations | `test_spatial_requires_recommendations` |
| Budget analysis blocked without recommendations | `test_budget_analysis_requires_recommendations` |
| Evaluation needs *both* deterministic results | `test_evaluation_requires_both_deterministic_results` |
| Evaluation blocked with only one result | `test_evaluation_is_blocked_when_only_one_result_exists` |
| The refusal names the missing step | `test_prerequisite_error_names_the_missing_step` |
| `attempt()` also guards | `test_attempt_still_guards_prerequisites` |

### 4.4 A room dimension change invalidates everything dependent

| Requirement | Test |
|---|---|
| All eight downstream results drop | `test_room_dimension_change_invalidates_everything_downstream` |
| User inputs survive | `test_room_dimension_change_keeps_the_user_inputs` |
| Room type also reaches the budget | `test_room_type_change_invalidates_the_budget_analysis` |
| Ceiling height counts as a dimension | `test_ceiling_height_counts_as_a_dimension_change` |
| A rename invalidates nothing | `test_renaming_the_room_invalidates_nothing` |
| Re-submitting the same room is a no-op | `test_resubmitting_the_same_room_invalidates_nothing` |
| Facet detection is precise | `test_room_change_keys_detects_each_facet`, `test_a_change_touching_two_facets_reports_both` |
| Openings do not reach the budget | `test_opening_change_keeps_the_budget_analysis`, `test_openings_do_not_invalidate_the_budget` |
| Openings do reach concepts and layout | `test_opening_change_keeps_concepts_invalid_by_the_rule` |

### 4.5 A preferences change invalidates the affected results

| Requirement | Test |
|---|---|
| Brief, concepts, furniture, evaluation drop | `test_preference_change_invalidates_ai_results_but_not_geometry` |
| The selection is cleared | `test_preference_change_clears_the_selection` |
| Spatial and budget analysis survive | same test, plus `test_preferences_do_not_invalidate_the_layout` |
| Requirements invalidate the brief and concepts | `test_requirement_change_invalidates_the_brief_and_concepts` |
| Requirements do not reach the budget analysis | `test_requirements_do_not_invalidate_the_budget_analysis` |
| An identical value is a no-op | `test_identical_preferences_invalidate_nothing`, `test_identical_requirements_invalidate_nothing` |

### 4.6 Budget-only change preserves independent geometric data

| Requirement | Test |
|---|---|
| The layout and the selection survive | `test_budget_change_keeps_spatial_and_selection` |
| Room facts survive | `test_budget_change_preserves_the_room_facts` |
| A surviving layout is not presented as current | `test_preserved_spatial_result_is_not_presented_as_current` |
| The table's budget row is exact | `test_budget_does_not_invalidate_the_layout` |
| An identical budget is a no-op | `test_identical_budget_invalidates_nothing` |

### 4.7 A new selected concept invalidates old recommendations

| Requirement | Test |
|---|---|
| Furniture, materials, spatial, budget, evaluation drop | `test_changing_the_selected_concept_clears_advice_and_checks` |
| Selecting the same concept is a no-op | `test_selecting_the_same_concept_invalidates_nothing` |
| A concept outside the collection is refused | `test_selecting_a_concept_outside_the_collection_is_refused` |
| An unknown name is refused | `test_selecting_an_unknown_name_is_refused` |
| Selection by name is case-insensitive | `test_selection_by_name_is_case_insensitive` |
| New concepts clear the old selection | `test_different_concepts_invalidate_selection_and_advice` |

### 4.8 New furniture invalidates spatial and budget results

| Requirement | Test |
|---|---|
| Spatial, budget, evaluation drop | `test_new_furniture_invalidates_spatial_budget_and_evaluation` |
| Materials survive | `test_new_furniture_keeps_the_materials`, `test_furniture_does_not_invalidate_the_materials` |
| A material-only change keeps the layout | `test_material_only_change_keeps_the_layout`, `test_materials_do_not_invalidate_the_layout` |
| An identical recommendation is a no-op | `test_identical_recommendation_invalidates_nothing` |
| Materials without furniture is refused | `test_setting_materials_without_furniture_is_refused` |

### 4.9 State integrity on failure

| Requirement | Test |
|---|---|
| A failed step records nothing | `test_failed_step_records_nothing` |
| Previously valid results survive a failure | `test_failed_step_preserves_previously_valid_results` |
| No partial application | `test_failed_step_does_not_partially_apply` |
| The original exception is preserved | `test_step_failed_preserves_the_original_exception` |
| `attempt()` returns what was recorded | `test_attempt_returns_the_recorded_value` |
| A real AI timeout is not recorded | `test_timeout_is_not_recorded` |
| Truncated concepts are not recorded | `test_truncated_concepts_are_not_recorded` |

### 4.10 No needless invalidation with identical inputs

Every `set_*`/`record_*` short-circuits on equality. Tests:
`test_identical_budget_invalidates_nothing`,
`test_identical_preferences_invalidate_nothing`,
`test_identical_requirements_invalidate_nothing`,
`test_identical_recommendation_invalidates_nothing`,
`test_selecting_the_same_concept_invalidates_nothing`,
`test_resubmitting_the_same_room_invalidates_nothing`,
`test_selecting_the_same_concept...`, `test_no_op_changes_do_not_log`.

### 4.11 Dependency table structure

| Requirement | Test |
|---|---|
| Every key has a row | `test_every_key_has_a_row` |
| No key invalidates itself | `test_no_key_invalidates_itself` |
| Inputs are never invalidated | `test_inputs_are_never_invalidated_by_anything` |
| The evaluation is terminal | `test_the_evaluation_is_terminal` |
| No cycles | `test_no_self_referential_cycle_exists` |
| The inverse table agrees | `test_sources_is_the_exact_inverse` |
| All 14 rows match the brief exactly | `test_row_matches_the_approved_rule` (14 parametrised cases) |
| Applied one hop, not transitively | `test_invalidated_by_is_not_transitive` |
| An unknown key fails loudly | `test_unknown_key_fails_loudly_instead_of_invalidating_nothing` |
| Every result has a source | `test_result_keys_are_all_covered_by_a_source` |
| Stable ordering | `test_invalidated_by_returns_declared_order` |

### 4.12 Architectural boundaries

| Requirement | Test |
|---|---|
| No Streamlit import (3 modules) | `test_workflow_modules_do_not_import_streamlit` |
| No `ai` import (3 modules) | `test_workflow_modules_do_not_import_the_ai_layer` |
| No HTTP (2 modules) | `test_workflow_modules_perform_no_http` |
| No credential access (2 modules) | `test_workflow_modules_read_no_credentials` |
| No arithmetic of its own | `test_workflow_state_performs_no_arithmetic` |

### 4.13 Finalisation and stored-report staleness

| Requirement | Test |
|---|---|
| `finalize()` stores the result | `test_finalize_stores_the_result` |
| `finalize()` requires completion | `test_finalize_requires_a_complete_workflow` |
| Editing after finalising clears the report | `test_editing_after_finalising_clears_the_stored_report` |
| The report matches the current state | `test_finalised_report_matches_the_current_state` |
| The result passes `core.validation` consistency | `test_project_result_from_state_is_self_consistent` |
| `FINAL_RESULT` is not complete pre-finalise | `test_final_result_step_is_not_complete_before_finalize` |
| `build_result()` refuses a partial project | `test_build_result_refuses_a_partial_project` |

### 4.14 Workflow ↔ AI seam

| Requirement | Test |
|---|---|
| Brief service result is recorded | `test_brief_service_result_is_recorded` |
| Concept service returns three and they are stored | `test_concept_service_returns_three_and_records_them` |
| Advisor result is recorded and priced by Python | `test_advisor_result_is_recorded_and_priced_by_python` |
| The recorded recommendation equals what the service returned | `test_recommendation_records_exactly_what_the_advisor_returned` |
| The evaluator runs only after both engine results | `test_evaluation_service_is_recorded_after_both_engine_results` |
| A full workflow reaches a `ProjectResult` | `test_full_workflow_reaches_a_project_result` |
| An unusable catalog reference is recorded *and* reported | `test_unusable_catalog_reference_does_not_block_recording_but_is_reported` |

---

## 5. Design Decisions Verified by Tests

Three behaviours are counter-intuitive enough that they are pinned explicitly,
so a future refactor cannot quietly change them.

1. **Invalidation is not transitive** —
   `test_invalidated_by_is_not_transitive`, `test_budget_does_not_invalidate_the_layout`.
2. **A surviving result can be inert** —
   `test_preserved_spatial_result_is_not_presented_as_current` asserts that the
   spatial result is retained as data, is *not* a completed step, moves
   `next_step` back to the brief, and is cleared once the basket is re-recorded.
3. **`FINAL_RESULT` needs a deliberate action** —
   `test_final_result_step_is_not_complete_before_finalize` and
   `test_editing_after_finalising_clears_the_stored_report`.

---

## 6. Bugs Found and Fixed During This Step

Real defects found while writing the tests, not test adjustments.

| # | Defect | Fix | Guarding test |
|---|---|---|---|
| 1 | `FINAL_RESULT` was derived from "all data present", so it could never be the next step and the workflow could never be *finished* | Added a stored `result` and a `finalize()` method; `build_result()` no longer stores | `test_steps_advance_in_order`, `test_finalize_stores_the_result` |
| 2 | `record_brief` passed a bare `DataKey` to `_replace`, which expects a sequence — since `DataKey` is a `str` enum, iterating it would have walked its characters | Pass `(DataKey.BRIEF,)` | Covered by every brief test; the bug was caught by an immediate `KeyError` on `"b"` |
| 3 | `record_recommendation` assigned fields *before* calling `_replace`, so invalidation could clear the value just written | Moved the assignment into the `assign` callback | `test_new_furniture_invalidates_spatial_budget_and_evaluation` |
| 4 | A narrative-only change was silently dropped, so `color_direction` edits were lost | Compare narrative fields separately and assign without invalidation when only prose moved | `test_identical_recommendation_invalidates_nothing` plus the advisor tests |
| 5 | Storing furniture and materials in one `DesignRecommendation` made a material swap discard a valid layout | Split them into separate keys with separate dependents | `test_material_only_change_keeps_the_layout` |

Two test-side issues were also corrected: `test_project_result_from_state_is_self_consistent`
was building a catalog from `FurnitureRecommendation` instead of `FurnitureItem`,
and two duplicated `_spatial` helpers had been left in the integration file.

---

## 7. Non-Test Verification

### 7.1 Streamlit render

`streamlit.testing.v1.AppTest.from_file("app.py").run()`:

```
app exceptions: 0
```

The application still renders with zero exceptions. `app.py` is unchanged from
Phase 1; nothing imports `workflow` yet.

### 7.2 Credential scan

Every project file outside `.venv`, `__pycache__` and `.pytest_cache`, under
5 MB, was read and searched for the literal value of `DEPLOY_API_KEY`:

```
key in env        : True
key in project    : NONE
```

Zero matches. The key is available to the application and absent from every file
on disk.

### 7.3 Scope checks

| Check | Result |
|---|---|
| `requirements.txt` | Unchanged |
| `opencode.json` | Unchanged |
| `ai/*`, `core/*`, `models/*` | Unchanged |
| `app.py` | Unchanged |
| Git repository | Still absent |
| Unused imports in new files | 0 |
| Lines over 88 characters in new files | 0 |

---

## 8. What These Tests Do Not Prove

Stated plainly so the pass count is not read as more than it is:

1. **The state has never been driven by a real interface.** It is exercised by
   direct method calls in tests; a Streamlit rerun may expose ordering problems
   that unit tests cannot.
2. **No live API call was made.** The four AI services are reached through
   injected fake completers, so the seam is proven but the provider is not.
3. **Session continuity across reruns is untested.** Nothing is serialised, and
   Streamlit's session state is not involved yet.
4. **The dependency table is only as good as its transcription.** Tests assert it
   matches the brief's table; they cannot prove the brief's table is complete
   for a feature that does not exist yet.
5. **Concurrency and multi-session behaviour are out of scope** for V1 and
   untested.
