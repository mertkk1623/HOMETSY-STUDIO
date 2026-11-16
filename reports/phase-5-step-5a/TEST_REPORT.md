# Phase 5 / Step 5A — Test Report

**Project:** Hometsy — Room Intelligence Studio
**Step:** 5A — Deterministic furniture placement engine
**Date:** 2026-11-15
**Environment:** Python 3.13.18 in `.venv` (project interpreter)
**Working directory:** `[PROJECT_ROOT]`

---

## 1. Commands executed

```powershell
cd "[PROJECT_ROOT]"
& ".venv\Scripts\python.exe" -m pytest tests/test_placement_engine.py -q
& ".venv\Scripts\python.exe" -m pytest tests/test_spatial_engine.py tests/test_room_engine.py tests/test_validation.py -q
& ".venv\Scripts\python.exe" -m pytest tests/test_placement_engine.py tests/test_spatial_engine.py tests/test_room_engine.py tests/test_validation.py -q
& ".venv\Scripts\python.exe" -m pytest -q
```

Every result below is from an actual run in this session. Nothing is estimated.

---

## 2. Results

### 2.1 New test file

```text
tests/test_placement_engine.py ....................................................... [100%]
55 passed in 1.25s
```

| | Count |
|---|---|
| Collected | 55 |
| Passed | 55 |
| Failed | 0 |
| Skipped | 0 |
| Errors | 0 |

### 2.2 Related existing geometry tests

```text
tests/test_spatial_engine.py tests/test_room_engine.py tests/test_validation.py
........................................................................ [ 56%]
........................................................                 [100%]
128 passed in 0.11s
```

| File | Tests | Result |
|---|---|---|
| `tests/test_spatial_engine.py` | 45 | all passed |
| `tests/test_room_engine.py` | 48 | all passed |
| `tests/test_validation.py` | 35 | all passed |
| **geometry only** | **128** | **128 passed** |

Running the new file together with those three in one command gives **183
passed** (55 + 128), confirming that the new module does not disturb the engines
it reuses.

### 2.3 Full suite

```text
........................................................................ [ 88%]
........................................................................ [ 96%]
..............................                                           [100%]
894 passed in 17.05s
```

| | Count |
|---|---|
| Collected | 894 |
| Passed | 894 |
| Failed | 0 |
| Skipped | 0 |
| xfail / xpass | 0 |
| Errors | 0 |
| Duration | 17.05 s |

Previous baseline was **839 passed**. The difference is **+55**, exactly the new
file. No pre-existing test was modified, weakened, skipped or deleted.

### 2.4 Per-file breakdown (post-change)

| File | Tests |
|---|---|
| `test_ai_client` | 58 |
| `test_ai_config` | 30 |
| `test_ai_parsing` | 112 |
| `test_ai_prompt` | 38 |
| `test_ai_services` | 70 |
| `test_budget_engine` | 34 |
| `test_data_library` | 34 |
| `test_models` | 54 |
| **`test_placement_engine`** | **55 (new)** |
| `test_room_engine` | 48 |
| `test_spatial_engine` | 45 |
| `test_ui_ai_flow` | 38 |
| `test_ui_app` | 32 |
| `test_ui_commits` | 40 |
| `test_ui_presentation` | 22 |
| `test_ui_session` | 22 |
| `test_validation` | 35 |
| `test_workflow_dependencies` | 35 |
| `test_workflow_integration` | 9 |
| `test_workflow_state` | 83 |
| **Total** | **894** |

---

## 3. The twelve required scenarios

| # | Requirement | Test(s) | What the test proves |
|---|---|---|---|
| 1 | Valid simple room layout | `test_single_item_is_placed_and_validated`, `test_placement_uses_catalog_dimensions_not_recommendation_fields`, `test_null_coordinates_are_normal_input` | An item is placed, its size comes from the catalog, the advice's coordinates are ignored, and the shared validator accepts the result. |
| 2 | Determinism | `test_same_inputs_produce_identical_layouts`, `test_candidate_order_is_stable_and_follows_the_declared_strategies`, `test_ranking_prefers_more_placed_items_then_higher_score` | Two runs give byte-identical footprints and candidates, in the same order, ranked by the documented key. |
| 3 | Boundary violations prevented | `test_no_footprint_ever_leaves_the_room`, `test_room_too_small_for_any_item_is_reported_not_forced` (×3), `test_an_item_wider_than_the_room_is_reported_as_unplaceable` | Every footprint is inside the room; a room that cannot hold the item yields `FAILED` with a reason, never a forced placement. |
| 4 | Overlaps prevented | `test_placed_footprints_never_overlap`, `test_touching_edge_to_edge_is_allowed_and_reported_as_no_overlap` | No pair overlaps for a five-item layout; edge-to-edge contact is allowed and is not an error. |
| 5 | Door access preserved | `test_door_clearance_zone_stays_empty`, `test_a_room_whose_only_free_floor_is_the_doorway_places_nothing` | The clearance zone is empty; when it is the only free floor the engine refuses rather than blocking the doorway. |
| 6 | Window clearance preserved | `test_window_clearance_is_preferred_even_though_it_is_only_a_warning`, `test_window_obstruction_lowers_the_score_instead_of_failing` | Clearance is achieved when possible; when forced, the layout stays valid but `window_clearance` drops below 1.0. |
| 7 | Unsupported rotations rejected | `test_supported_rotations_are_accepted` (×4), `test_rotation_candidates_only_contain_right_angles`, `test_non_right_angle_rotation_is_reported_as_unplaced`, `test_every_placed_footprint_uses_a_supported_rotation` | All four supported angles work; 45° is reported as `unsupported_rotation` even when constructed past the Pydantic validator; every stored rotation is a right angle. |
| 8 | Missing-catalog item reported | `test_unknown_catalog_item_is_reported_by_name`, `test_only_unknown_items_means_the_placement_fails`, `test_unknown_item_quantity_is_counted_in_the_report` | Unknown ids appear in `unplaced` with `unknown_catalog_item`, are counted per copy, and never prevent a known item from being placed. |
| 9 | Unplaceable item reported explicitly | `test_quantity_beyond_the_available_floor_is_reported_per_copy`, `test_unplaceable_reason_mentions_the_free_area_when_floor_remains` | The exact number of unplaced copies is reported, with a sentence naming the item, its dimensions and the obstacle. |
| 10 | Partial placement not shown as success | `test_partial_placement_has_its_own_status`, `test_partial_layout_still_makes_the_spatial_engine_pass`, `test_status_properties_agree_with_the_enum` | `PARTIAL` is its own status with `is_complete == False`, a `partial_placement` note, and a still-validated layout. |
| 11 | Integration with the existing Spatial Engine | `test_engine_never_bypasses_the_shared_validator`, `test_result_carries_the_spatial_validation_model`, `test_footprints_match_what_the_spatial_engine_recomputes`, `test_findings_use_the_shared_validation_vocabulary`, `test_placement_findings_are_empty_for_a_clean_layout` | Forcing the shared validator to report an error turns the result into `FAILED` with `candidate is None`; an independent re-validation reproduces the same footprints; findings use the `core.validation` vocabulary. |
| 12 | Realistic multi-furniture room | `test_realistic_living_room_is_furnished_completely`, `test_realistic_room_scores_every_criterion`, `test_a_bedroom_scenario_places_the_bed_against_a_wall` | Six items placed with no error and no warning, occupied area under the circulation target, every requested item represented in request order; a bedroom scenario keeps the bed on a wall. |

### Additional coverage beyond the twelve

| Test | Purpose |
|---|---|
| `test_wall_strategies_produce_different_layouts` | The four strategies are more than cosmetic; wall preference genuinely changes the outcome. |
| `test_layout_score_does_not_depend_on_the_generation_strategy` | The score is a property of the layout, not of the wall order that built it. |
| `test_seating_is_anchored_to_a_wall_not_floating` | A sofa touches a wall with its long edge, not merely near one. |
| `test_declared_weight_sets_are_normalised` | Every weight set sums to 1.0, so a score is always in `0..1`. |
| `test_written_coordinates_survive_the_shared_recommendation_path` | `apply_placements` output re-validates identically through the Phase 3 path, with no `unplaced_item` warning. |
| `test_unplaced_recommendations_keep_their_null_coordinates` | No coordinate is invented for an item that was not placed. |
| `test_apply_placements_on_a_failed_result_changes_nothing` | A failed result is write-back safe. |
| `test_placement_is_idempotent_through_the_write_back` | Re-running on the engine's own output moves nothing (no rounding drift). |
| `test_multiple_copies_are_a_known_write_back_limitation` | Pins the documented quantity limitation instead of hiding it. |
| `test_empty_recommendation_list_yields_no_layout`, `test_generator_input_is_accepted`, `test_empty_catalog_places_nothing` | Input hygiene: empty inputs fail cleanly, any sequence is accepted. |
| `test_custom_clearance_values_are_honoured` | A caller's clearance values are respected, not silently replaced by defaults. |
| `test_room_fixture_is_itself_valid` | Guards the whole file: a broken fixture would invalidate every claim. |

---

## 4. Manual verification beyond pytest

Run against the real catalog with the real `room` fixture (400 × 520 cm):

| Check | Result |
|---|---|
| Six-item living room, no coordinates | `COMPLETE`, score 0.990954, 0 errors, 0 warnings, 4.42 / 20.8 m² occupied |
| Write-back then Phase 3 `validate_recommendations` | Identical footprints, `is_valid = True`, no `unplaced_item` warning |
| Determinism across `PYTHONHASHSEED=1` and `PYTHONHASHSEED=99` | Identical coordinates, identical rotation, identical placement order |
| Partial case (230 × 230, bed + sofa + coffee table) | `PARTIAL`, 2 placed, sofa reported with a reason |
| Quota case (240 × 240, six sofas) | `PARTIAL`, 1 placed, `count = 5` reported |
| Forced window obstruction (170 × 200, TV unit) | `COMPLETE`, `window_obstructed` warning, `window_clearance` 0.854 |
| Doorway-only room (100 × 120, armchair) | `FAILED`, reason names the door clearance zone |
| Door on west/east/north walls | `COMPLETE` in each case, no issues |
| Large rooms | 800 × 800 → 0.21 s; 2000 × 2000 → 1.15 s (six items), 16.35 s (40 copies) |

---

## 5. Safety checks

| Check | Result |
|---|---|
| API key present in new source, tests or reports | **No.** Grepped for `DEPLOY_API_KEY`, `api_key`, `urllib`, `http`, `requests`, `secrets` in both new files: no match other than the `_Request`/`requests` local variable names in the engine. |
| Network access in tests | **None.** The only `monkeypatch` use replaces `core.placement_engine.validate_placement` with a local wrapper, in-process. |
| New runtime dependency | **None.** Imports are `dataclasses`, `enum`, `typing` plus existing project modules. |
| Randomness / clock in the engine | **None.** No `random`, no `time`, no `datetime` in `core/placement_engine.py`. |
| Determinism under hash randomisation | Verified with two `PYTHONHASHSEED` values; identical output. |
| Existing tests modified or weakened | **None.** Only `tests/test_placement_engine.py` was added. |
| Git / commit / push / deploy | **None performed.** The workspace is not a Git repository and nothing was published. |

---

## 6. Quality checks

| Check | Result |
|---|---|
| Line length (88 columns) — `core/placement_engine.py` | Longest line 85 characters |
| Line length (88 columns) — `tests/test_placement_engine.py` | Longest line 87 characters |
| Unused imports (AST scan, both files) | None (only `from __future__ import annotations`) |
| Streamlit / AI imports in `core/placement_engine.py` | None |
| `workflow/state.py`, `ai/`, `ui/`, `models/`, data files | Unchanged |
