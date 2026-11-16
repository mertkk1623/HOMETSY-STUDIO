# Phase 5 / Step 5B — Test Report

**Project:** Hometsy — Room Intelligence Studio
**Step:** 5B — Furniture Advisor and Spatial Validation UI
**Date:** 2026-11-15
**Environment:** Python 3.13.18 in `.venv` (project interpreter)
**Working directory:** `[PROJECT_ROOT]`

---

## 1. Commands executed

```powershell
cd "[PROJECT_ROOT]"

# New screen suite
& ".venv\Scripts\python.exe" -m pytest tests/test_ui_advisor_flow.py -q

# New engine-seam suite
& ".venv\Scripts\python.exe" -m pytest tests/test_ui_layout.py -q

# Drawing tests
& ".venv\Scripts\python.exe" -m pytest tests/test_ui_presentation.py -q

# Every directly affected area together
& ".venv\Scripts\python.exe" -m pytest tests/test_ui_advisor_flow.py `
    tests/test_ui_layout.py tests/test_ui_presentation.py tests/test_ui_app.py `
    tests/test_ui_ai_flow.py tests/test_ui_session.py tests/test_ui_commits.py `
    tests/test_workflow_state.py tests/test_workflow_integration.py `
    tests/test_workflow_dependencies.py tests/test_placement_engine.py `
    tests/test_spatial_engine.py -q

# Full suite
& ".venv\Scripts\python.exe" -m pytest -q
```

Every result below is from an actual run in this session. Nothing is estimated.

---

## 2. Results

### 2.1 New and extended test files

```text
tests/test_ui_advisor_flow.py ............................ [100%]
28 passed in 8.08s

tests/test_ui_layout.py ...........                        [100%]
11 passed in 0.45s

tests/test_ui_presentation.py .................................. [100%]
34 passed in 0.05s
```

### 2.2 Related subset

```text
........................................................................ [ 66%]
........................................................................ [ 82%]
........................................................................ [ 99%]
..                                                                       [100%]
434 passed in 27.02s
```

### 2.3 Full suite

```text
........................................................................ [ 91%]
........................................................................ [ 98%]
...........                                                              [100%]
947 passed in 27.83s
```

| | Count |
|---|---|
| Collected | 947 |
| Passed | 947 |
| Failed | 0 |
| Skipped | 0 |
| xfail / xpass | 0 |
| Errors | 0 |
| Duration | 27.83 s |

Previous baseline was **894 passed**. The difference is **+53**:

| Change | Tests |
|---|---|
| New `test_ui_advisor_flow.py` | +28 |
| New `test_ui_layout.py` | +11 |
| `test_ui_presentation.py` plan-drawing tests | +12 |
| `test_placement_engine.py` quantity tests | +1 (55 → 56) |
| `test_spatial_engine.py` `unplaced_copies` | +1 (45 → 46) |
| **Total** | **+53** |

No pre-existing test was deleted, skipped or weakened. Three existing tests were
*updated* because the behaviour they described changed by design:

| Test | Change | Why |
|---|---|---|
| `test_multiple_copies_are_a_known_write_back_limitation` | Replaced by `test_multiple_copies_survive_the_write_back` and `test_a_partly_placed_quantity_does_not_claim_missing_copies` | It pinned a limitation that no longer exists. Asserting it would now be false. |
| `test_ui_app` stage count / forward label | Label is now "Continue to the design plan"; stage list includes "Design Plan" | The workflow gained a stage. |
| `test_ui_ai_flow` | Same forward-button label | Same reason. |

### 2.4 Per-file breakdown (post-change)

| File | Tests | Change |
|---|---|---|
| `test_ai_client` | 58 | — |
| `test_ai_config` | 30 | — |
| `test_ai_parsing` | 112 | — |
| `test_ai_prompt` | 38 | — |
| `test_ai_services` | 70 | — |
| `test_budget_engine` | 34 | — |
| `test_data_library` | 34 | — |
| `test_models` | 54 | — |
| `test_placement_engine` | 56 | +1 |
| `test_room_engine` | 48 | — |
| `test_spatial_engine` | 46 | +1 |
| **`test_ui_advisor_flow`** | **28** | **+28 (new)** |
| `test_ui_ai_flow` | 38 | — (assertions updated) |
| `test_ui_app` | 32 | — (assertions updated) |
| `test_ui_commits` | 40 | — |
| **`test_ui_layout`** | **11** | **+11 (new)** |
| `test_ui_presentation` | 34 | +12 |
| `test_ui_session` | 22 | — |
| `test_validation` | 35 | — |
| `test_workflow_dependencies` | 35 | — |
| `test_workflow_integration` | 9 | — |
| `test_workflow_state` | 83 | — |
| **Total** | **947** | **+53** |

---

## 3. Test design

Every test in the new files is mock-only. `ui.ai_actions.recommend_furniture` is
replaced by a stub that records its calls and replays a queued answer or
exception, so:

- no HTTP request is made;
- the suite runs with no API key present;
- the `ai` package is still exercised through its real dataclasses
  (`AdvisorResult`, `CatalogCheck`), so a test cannot pass against a shape the
  real service does not produce.

The placement and spatial engines are **not** stubbed. They are deterministic,
they are what the screen exists to display, and stubbing them would let the screen
and the drawing drift apart without any test noticing.

`ui/pages_plan.py` render functions are exercised through
`streamlit.testing.v1.AppTest`, i.e. the real screen, the real router and the real
session state.

---

## 4. The fourteen required scenarios

| # | Requirement | Test(s) | What the test proves |
|---|---|---|---|
| 1 | The advisor runs only on a button press | `test_opening_the_plan_screen_makes_no_request` | Opening the screen makes 0 calls, offers no "Run the advisor again" button, and says no furniture has been recommended. |
| 2 | It never runs without a valid concept | `test_the_plan_screen_refuses_to_run_without_a_selected_concept`, `test_the_plan_screen_plays_no_part_in_starting_a_project` | With concepts but no selection the screen redirects to `concepts` and renders no advisor button. Reaching `plan` without a room redirects to `room`. Neither path calls the advisor. |
| 3 | A failed call preserves the previous valid state | `test_a_failed_advisor_call_keeps_the_previous_plan`, `test_a_failed_advisor_call_stores_nothing_when_there_was_no_plan` | After a timeout, furniture / placement / spatial are byte-identical to before, the score is unchanged, the plan is still drawn and the error is reported. With no prior plan, nothing is stored and `RECOMMENDATIONS` stays incomplete. |
| 4 | Catalog references are preserved, never rewritten | `test_the_stored_basket_keeps_every_catalog_reference`, `test_an_unusable_catalog_reference_is_not_planned`, `test_an_unplannable_basket_is_never_offered_for_planning` | Item ids and order survive the write-back; an unknown id is stored as returned (not substituted), reported with the shared `core.validation` message, and its basket cannot be planned. |
| 5 | The placement engine is integrated, not re-implemented | `test_the_screen_uses_the_engine_rather_than_its_own_geometry`, `test_the_analysis_returns_the_engines_own_validation`, `test_the_same_inputs_produce_the_same_layout` | Calling `ui.layout.analyse_layout` on the stored inputs reproduces the stored footprints coordinates exactly; the validation is the engine's own object; two runs are identical. |
| 6 | COMPLETE / PARTIAL / FAILED are presented distinctly | `test_a_complete_layout_is_presented_as_complete_and_drawn`, `test_a_failed_layout_draws_no_plan_and_claims_no_score`, `test_a_partial_layout_draws_only_the_placed_copies`, `test_the_three_statuses_cannot_be_confused_by_their_wording` | Each status shows its own badge and sentence; the three badges are distinct; the failure sentence contains no placed count and says there is no plan. |
| 7 | The plan uses the engine's real coordinates | `test_the_plan_draws_the_engine_coordinates`, `test_the_coordinates_are_written_into_the_basket`, `test_the_placement_and_the_drawing_agree`, `test_the_plan_uses_the_footprint_coordinates_it_is_given` | Each footprint's name, x-range and `width × depth` appear in the table beside the drawing; the drawing's pixel values match the module's documented scale rule exactly for given centimetres. |
| 8 | A FAILED candidate is never drawn | `test_a_failed_layout_draws_no_plan_and_claims_no_score`, `test_a_room_too_small_for_everything_fails_without_a_plan`, `test_a_failed_analysis_never_synthesises_a_valid_verdict` | In a 150 × 150 room the outcome is `FAILED` with `placed == []` and `score is None`; the markup contains no `<svg`; the reason names the item that did not fit. A failed analysis never yields a valid verdict. |
| 9 | A PARTIAL plan draws only the validated placements | `test_a_partial_layout_draws_only_the_placed_copies`, `test_a_partial_analysis_reports_the_shortfall` | Twenty armchairs yield `PARTIAL`; the drawn block count **equals** `placed_count` and is less than 20; the screen says "Partial plan" and names the unplaced copies with the engine's reason. |
| 10 | Quantities survive the write-back | `test_every_placed_copy_gets_its_own_position`, `test_quantity_is_measured_copy_by_copy`, `test_multiple_copies_survive_the_write_back`, `test_a_partly_placed_quantity_does_not_claim_missing_copies` | Two armchairs record two `positions` and five placed copies give five **distinct** coordinate pairs; `quantity` stays 4 so the budget is unaffected; a partially placed quantity records only the copies actually placed and reports `unplaced_copies` as a warning. |
| 11 | Spatial errors and warnings stay separate | `test_blocking_errors_and_warnings_are_reported_separately`, `test_door_and_window_clearance_rules_are_stated` | "Blocking problems" precedes "Warnings"; the boundary message sits under the blocking heading and the window message under warnings; "Warnings do not block the layout." is present; the clearance rules state that a door block is an error and a window-band intrusion a warning. |
| 12 | No material price is invented | `test_materials_are_shown_in_their_own_unpriced_section`, `test_no_material_price_field_exists_to_render` | Each material carries "Not priced: materials have no catalog cost"; no `₺` or `TRY` appears in the material section; `MaterialRecommendation` has no price-like field. |
| 13 | A rerun makes no request | `test_a_rerun_after_the_advisor_does_not_call_it_again`, `test_a_later_rerun_keeps_the_stored_plan` | Two plain reruns leave the call count at 1 and the placement object equal. |
| 14 | The AI-free start of the workflow still works | `test_the_first_screens_still_make_no_advisor_call`, `test_the_whole_workflow_runs_without_importing_the_ai_layer` (existing, `test_ui_app`) | Completing room + preferences and navigating shows no advisor call; the app imports no `ai` module in a child process. |

### Additional coverage beyond the fourteen

| Test | Purpose |
|---|---|
| `test_the_advisor_receives_the_stored_inputs_and_the_selected_concept` | The wrapper is passed the stored room, preferences, budget, brief and the *selected* concept — not a stale or default one. |
| `test_changing_the_concept_makes_the_old_plan_stale` | Selecting a different concept clears furniture, placement and validation, and the old plan stops being drawn. |
| `test_a_room_dimension_change_strips_the_stored_coordinates` | A width change removes the layout **and** the coordinates together; nothing invents a new position for the new room. |
| `test_recording_coordinates_does_not_invalidate_the_budget` | Placement is an annotation; `BUDGET_ANALYSIS` is not dropped when coordinates are recorded. |
| `test_repeating_the_same_advice_keeps_the_layout_and_the_price` | An unchanged request (no coordinates, different engine rotation) is not a new basket. |
| `test_a_changed_request_still_invalidates_the_layout` | A changed quantity invalidates the layout; the replaced key is not listed in its own invalidation. |
| `test_an_unknown_item_is_reported_and_never_placed`, `test_an_empty_basket_is_not_a_valid_layout` | Engine sanitation: an unknown id yields no footprint and keeps its id; an empty basket is a failure, not an empty success. |
| `test_a_rejected_candidate_is_not_offered_as_a_placed_layout` | Across three too-small rooms, an invalid verdict never coexists with an unstored placed layout. |
| `test_the_plan_is_a_self_contained_svg`, `test_the_plan_escapes_a_hostile_label` | Offline: no `http`, no `<image>`; a hostile label is escaped. |
| `test_a_small_block_gets_a_shortened_label`, `test_a_block_too_small_for_text_still_draws` | A long name in a narrow block is shortened; a block too small for any text still renders. |
| `test_the_plan_legend_labels_are_separated_for_text_extraction` | The flex legend emits real text spaces, so a screen reader hears "Placed furniture Door Window", not "Placed furnitureDoorWindow". **This failed on first run and the renderer was fixed, not the test.** |

---

## 5. Manual verification beyond pytest

| Check | Result |
|---|---|
| End-to-end screen probe (`AppTest`, advisor stubbed, real engines) | `plan` screen, 1 advisor call, 0 exceptions, exactly one `<svg>` |
| Stored `positions` after placement | `1, 1, 1, 2, 1, 1` — the armchair pair keeps two coordinates |
| Stored outcome | `COMPLETE`, score 0.990853, `is_valid = True`, 0 warnings |
| Advisor call count after a rerun | still 1 |
| `is_complete` | `RECOMMENDATIONS` True, `SPATIAL_VALIDATION` True |
| Realistic six-item room through `analyse_layout` | `complete`, score 0.990954, 6 placed / 0 unplaced, median 70.5 ms, occupied 4.42 of 20.80 m² |
| Score terms | boundary_fit 0.150/1.0, door_access 0.200/1.0, window_clearance 0.150/1.0, overlap_free 0.150/1.0, circulation 0.200/1.0, placement_quality 0.150/0.9397 |
| Write-back then `validate_recommendations` | identical footprints, `quantity_collapsed` absent |

---

## 6. Safety checks

| Check | Result |
|---|---|
| Network access in tests | None. Every AI call is a stub; no socket is opened. |
| API key required | No. The suite runs without `DEPLOY_API_KEY`. |
| Key referenced in new code or tests | No. A content scan for `DEPLOY_API_KEY`, `api_key`, `urllib`, `requests`, `secrets` over the new and changed files found only local variable names. |
| `app.py` imports `ai` | No — verified by import inspection, and asserted by the existing child-process test. |
| `core`, `ui.layout`, `ui.diagram` import `streamlit` | No — verified by import inspection. |
| New dependency | None. |
| `random`, `datetime`, `time` in the new modules | Not used; placement is deterministic. |

---

## 7. Quality checks

| Check | Result |
|---|---|
| Line length (88 columns) | 0 violations in every new and changed file. `models/schemas.py` has one pre-existing 104-character line (`ConceptCollection.concepts`, untouched by this step); it was left alone rather than reformatted outside scope. |
| Unused imports (AST scan) | None in `ui/pages_plan.py`, `ui/layout.py`, `ui/diagram.py`, `workflow/state.py`, `core/placement_engine.py`, `core/spatial_engine.py`, `tests/test_ui_advisor_flow.py`, `tests/test_ui_layout.py`, `tests/test_ui_presentation.py`. |
| Dead branches | One `# pragma: no cover` defensive branch in `_render_metrics` was removed: `PlacementOutcome` cannot carry a score when `FAILED`, so the branch was unreachable and its message described a case that cannot occur. |
| Silent exception handling | None added. The only `try/except` on the screen path is `except StepFailed` to report a failure; it does not swallow. |
| Turkish characters | Not applicable; the interface is English. The report files use `×`, `²` and `₺` only in prose. |
