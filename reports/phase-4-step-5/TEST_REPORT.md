# Phase 4 / Step 5 — Test Report

**Project:** Hometsy — Room Intelligence Studio
**Date:** 2026-11-14
**Python:** 3.13.18 (`.venv\Scripts\python.exe`)
**Test framework:** pytest

All results below are copied from actual command output run in this session.
No live API call was made.

---

## 1. Test Commands

Run from the project root `[PROJECT_ROOT]`.

| # | Command | Purpose |
|---|---|---|
| 1 | `& ".venv\Scripts\python.exe" -m pytest tests/test_ai_prompt.py -q` | New shared-layer tests |
| 2 | `& ".venv\Scripts\python.exe" -m pytest tests/test_ai_services.py -q` | New four-service tests |
| 3 | `& ".venv\Scripts\python.exe" -m pytest tests/test_ai_parsing.py -q` | Regression on the modified correction loop |
| 4 | `& ".venv\Scripts\python.exe" -m pytest tests/test_ai_prompt.py tests/test_ai_services.py -q` | Both new files together |
| 5 | `& ".venv\Scripts\python.exe" -m pytest -q` | Full suite |
| 6 | `& ".venv\Scripts\python.exe" -m pytest --collect-only -q` | Per-file collection counts |
| 7 | `& ".venv\Scripts\python.exe" -c "<AppTest script>"` | Streamlit render check |

---

## 2. Test Counts

### Before this step

| File | Tests |
|---|---:|
| `tests/test_ai_client.py` | 58 |
| `tests/test_ai_config.py` | 30 |
| `tests/test_ai_parsing.py` | 110 |
| `tests/test_budget_engine.py` | 34 |
| `tests/test_data_library.py` | 34 |
| `tests/test_models.py` | 54 |
| `tests/test_room_engine.py` | 48 |
| `tests/test_spatial_engine.py` | 45 |
| `tests/test_validation.py` | 35 |
| **Total** | **448** |

### Added in this step

| File | Tests |
|---|---:|
| `tests/test_ai_prompt.py` (new) | 38 |
| `tests/test_ai_services.py` (new) | 70 |
| `tests/test_ai_parsing.py` (2 added) | +2 |
| **Added** | **110** |

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
| **Total** | **558** |

**448 → 558 (+110).**

---

## 3. Results

### New test files (command 4)

```
........................................................................ [ 66%]
....................................                                     [100%]
108 passed in 0.14s
```

108 = 38 (`test_ai_prompt.py`) + 70 (`test_ai_services.py`).

### Modified file regression (command 3)

```
........................................................................ [ 64%]
........................................                                 [100%]
112 passed in 0.08s
```

### Full suite (command 5, run twice)

First run:

```
........................................................................ [ 90%]
......................................................                   [100%]
558 passed in 0.58s
```

Second run (stability check):

```
........................................................................ [ 90%]
......................................................                   [100%]
558 passed in 0.58s
```

### Summary

| Metric | Value |
|---|---:|
| Total tests | 558 |
| Passed | 558 |
| Failed | **0** |
| Errors | **0** |
| Skipped | **0** |
| Warnings | 0 |
| Runtime | ~0.6 s |

No test was skipped, deselected, or marked xfail. No test was weakened to pass.

---

## 4. Coverage of Step 5 Requirements

Each requirement from the step brief mapped to the tests that prove it.

### 4.1 Valid output from all four functions

| Requirement | Test |
|---|---|
| Brief returns a validated model | `test_analyze_brief_returns_a_validated_model` |
| Concepts return a validated model | `test_generate_concepts_returns_exactly_three` |
| Advisor returns a validated model | `test_recommend_furniture_returns_a_validated_model` |
| Evaluator returns a validated model | `test_evaluate_design_returns_a_validated_model` |
| Models are the expected Pydantic classes | `isinstance` assertions in each of the above |
| `analyze_brief_with_prompt` returns brief + prompt | `test_analyze_brief_with_prompt_returns_both` |

### 4.2 Prompt inputs are passed correctly

| Requirement | Test |
|---|---|
| Brief prompt carries requirements, style, palette, budget, materials | `test_brief_prompt_contains_every_user_input` |
| Brief prompt carries the Python-computed area | `test_brief_prompt_supplies_the_calculated_area` |
| Brief prompt forbids designing the room | `test_brief_prompt_forbids_designing_the_room` |
| Brief prompt states the exact output keys | `test_brief_prompt_requires_the_exact_output_keys` |
| Concept prompt carries the brief | `test_concept_prompt_carries_the_brief` |
| Advisor prompt lists only room-compatible items | `test_advisor_prompt_lists_only_usable_catalog_items` |
| Evaluator prompt carries calculated figures | `test_evaluator_prompt_contains_the_calculated_results` |
| Evaluator prompt carries spatial problems | `test_evaluator_sees_blocking_problems` |
| Evaluator told when the budget is incomplete | `test_evaluator_is_told_when_the_budget_is_incomplete` |
| Room facts computed by Python, not the model | `test_room_facts_come_from_the_model_not_the_llm` |
| Catalog values rendered from the catalog | `test_catalogue_entry_exposes_catalog_values` |

### 4.3 Exactly three concepts

| Requirement | Test |
|---|---|
| Three concepts returned | `test_generate_concepts_returns_exactly_three` |
| Names are distinct | `test_concepts_are_distinct` |
| Two concepts rejected, then corrected | `test_two_concepts_are_rejected_and_corrected` |
| Four concepts rejected | `test_four_concepts_are_rejected` |
| Duplicate names rejected | `test_duplicate_concept_names_are_rejected` |
| Prompt demands substantive difference | `test_concept_prompt_asks_for_three_distinct_directions` |

### 4.4 Correction-call discipline

| Requirement | Test |
|---|---|
| Valid first answer → no correction | `test_valid_first_answer_needs_one_request` (`call_count == 1`) |
| Invalid JSON → exactly one correction | `test_invalid_first_answer_triggers_exactly_one_correction` (`call_count == 2`) |
| Schema failure → also corrected | `test_schema_failure_is_also_correctable` |
| Second failure → correct error raised | `test_two_failures_raise_a_correction_error` |
| No third request ever sent | `test_two_failures_never_loop` |
| Correction states the original problem | `test_correction_receives_the_diagnosis` |
| Correction restates context and contract | `test_correction_messages_repeat_the_same_context_and_contract` |
| Correction does not echo the bad answer | `test_correction_messages_do_not_echo_the_previous_answer` |
| Correction keeps the same token limit | `test_correction_keeps_the_same_token_limit` |
| Per-service correction works | `test_brief_missing_summary_triggers_correction`, `test_evaluator_bad_output_is_corrected` |

### 4.5 Catalog validation

| Requirement | Test |
|---|---|
| Unknown `item_id` reported | `test_unknown_item_id_is_reported` (`unknown_catalog_item`) |
| Unknown id is **not** substituted | `test_unknown_item_is_not_replaced` |
| Room-type mismatch reported | `test_room_type_mismatch_is_reported` (`unsupported_room_type`) |
| A correct room type is accepted | `test_bedroom_room_accepts_a_wardrobe` |
| Uses the Phase 3 rule, not a copy | `test_catalog_check_uses_the_phase_three_rule` |
| Catalog error is a finding, not a crash | `test_catalog_error_does_not_raise` |
| Unknown item invalidates the total | `test_unknown_item_does_not_produce_a_trustworthy_total` |

### 4.6 AI-supplied prices and dimensions are not trusted

| Requirement | Test |
|---|---|
| Model-supplied price cannot change the subtotal | `test_model_supplied_prices_are_ignored` |
| Model-supplied width cannot change pricing | `test_model_supplied_dimensions_are_ignored` |
| Subtotal equals the catalog figure (18500 + 4900 = 23400) | `test_subtotal_comes_from_the_catalog_not_the_model` |
| Model-supplied position does not affect the advisor | `test_geometry_fields_are_not_accepted_from_the_model` |
| Advisor makes no geometry claims | `test_advisor_makes_no_geometry_claims` |
| Evaluator sees catalog names, not model names | `test_evaluator_uses_catalog_names_not_model_names` |
| Unknown item reached the evaluator as unknown | `test_unknown_item_reaches_the_evaluator_as_unknown` |
| Prompt forbids prices, dimensions, positions | `test_advisor_prompt_forbids_prices_and_dimensions` |
| Proposed concept rejected as forbidden by evaluator | `test_evaluator_prompt_forbids_recalculation` |

### 4.7 Transport and authentication errors

| Requirement | Test |
|---|---|
| Auth error propagates — brief | `test_authentication_error_propagates_from_brief` |
| Auth error propagates — concepts | `test_authentication_error_propagates_from_concepts` |
| Auth error propagates — advisor | `test_authentication_error_propagates_from_advisor` |
| Auth error propagates — evaluator | `test_authentication_error_propagates_from_evaluator` |
| Timeout propagates, no retry | `test_timeout_propagates_from_brief` (`call_count == 1`) |
| Truncation propagates from the evaluator | `test_truncation_propagates_from_evaluator` |
| No service retries a transport error | `test_no_service_retries_a_transport_error` |
| Transport error → **no** correction (parametrised) | `test_transport_error_is_raised_without_a_correction` |
| Timeout during the correction stays a timeout | `test_correction_transport_failure_is_not_disguised` |
| Truncation during the correction stays truncation | `test_correction_truncation_is_not_disguised` |
| Truncated concept answer is not corrected | `test_truncated_concept_answer_is_not_corrected` |

### 4.8 Token limits

| Requirement | Test |
|---|---|
| Constants equal 2000 / 6000 / 4000 / 3000 | `test_application_token_limits_match_the_approved_values` |
| Each service sends its own limit | `test_each_service_uses_its_own_limit` (parametrised, 4 cases) |
| Limit forwarded unchanged | `test_first_request_uses_the_service_token_limit` |
| Temperature 0.0 requested | `test_zero_temperature_is_requested` |
| Timeout forwarded | `test_timeout_is_forwarded` |

### 4.9 Credential containment

| Requirement | Test |
|---|---|
| No service puts the key in a prompt (4 cases) | `test_no_service_puts_the_key_in_its_prompt` |
| Error messages do not contain the key | `test_service_error_messages_do_not_contain_the_key` |
| Prompt module contains no credential read | `test_prompt_module_reads_no_credentials` |
| No AI module reads `os.environ` / `DEPLOY_API_KEY` | `test_ai_service_modules_do_not_read_credentials` (5 modules) |

### 4.10 Architectural boundaries

| Requirement | Test |
|---|---|
| No AI module imports Streamlit (5 modules) | `test_ai_service_modules_do_not_import_streamlit` |
| `ai/prompt.py` imports no Streamlit | `test_prompt_module_does_not_import_streamlit` |
| `ai/prompt.py` performs no HTTP | `test_prompt_module_has_no_http_of_its_own` |
| Services do not call each other | `test_services_do_not_call_each_other` |
| Fake completer returns a real `ChatCompletion` | `test_fake_completer_returns_a_chat_completion` |

### 4.11 Serialisation correctness

| Requirement | Test |
|---|---|
| Models render as JSON | `test_json_block_renders_models_as_json` |
| Enums render as their values | `test_json_block_renders_enums_as_their_values` |
| `Decimal` renders as a string (no float rounding) | `test_json_block_renders_decimals_as_strings` |
| Output is deterministic | `test_json_block_is_deterministic` |
| Nested structures supported | `test_json_block_supports_nested_structures` |
| System prompt includes shared rules | `test_system_prompt_contains_the_shared_rules` |
| Rules forbid invented data and arithmetic | `test_shared_rules_forbid_invented_data_and_arithmetic` |
| Room-type filter works | `test_items_for_room_filters_by_room_type` |

---

## 5. Bugs Found and Fixed During This Step

Real defects discovered by writing the tests, not test adjustments.

| # | Defect | Fix | Guarding test |
|---|---|---|---|
| 1 | A transport error raised during the correction attempt was wrapped as `AICorrectionFailedError`, reporting a network fault as a formatting problem | Added `except AIError: raise` in `parse_with_correction` | `test_corrector_raising_a_transport_error_keeps_it_visible`, `test_corrector_raising_a_truncation_error_keeps_it_visible` |
| 2 | `catalogue_entry` rendered `indicative_unit_cost` inconsistently (`18500` vs `18500.00`), making prompt text unstable | Format as `f"{Decimal(...):.2f}"` | `test_catalogue_entry_exposes_catalog_values` |
| 3 | `AdvisorResult` stored only `BudgetAnalysis`, discarding `is_trustworthy`, so a partial sum could be presented as the total | Store the full `BudgetResult`; `is_usable` now requires `is_trustworthy` | `test_unknown_item_does_not_produce_a_trustworthy_total` |
| 4 | `room_facts` derived wall keys from `type(room.door.wall)` instead of the `Wall` enum | Import `Wall` and iterate it | `test_room_facts_come_from_the_model_not_the_llm` |
| 5 | Stray trailing `"` characters left at line ends inside two prompt contracts | Rewrote the contract blocks | Prompt-content tests plus a manual read |

Two test-side issues were also corrected: `FakeCompleter.queue` was added so
tests do not touch a private attribute, and a shell `-replace` pass that
mangled multi-line calls was fixed by hand.

---

## 6. End-to-End Probe (not a pytest test)

A throwaway script exercised all four services in sequence with one fake
completer each, plus an invalid-catalog case. Output as recorded:

```
1 brief      : A calm living room with seating for four and a readi | requests 1
2 concepts   : ['Quiet Oak', 'Soft Contrast', 'Warm Studio'] | requests 1
3 advisor    : gold usable True | subtotal 23400.00 | requests 1
3b bad item  : usable False | codes ['unknown_catalog_item'] | trustworthy total False
4 evaluation : ['Reading corner is implied'] | requests 1
key leak     : none in prompts
```

This confirms the composition path: each service sent exactly one request, the
subtotal matched the catalog (18500 + 4900), an unknown id produced a finding
and an untrustworthy total, and the API key appeared in no prompt.

Script location: `C:\Users\[LOCAL_USER]\AppData\Local\Temp\opencode\probe_services.py`
(outside the project; not a deliverable, not part of the suite).

---

## 7. Non-Test Verification

### 7.1 Streamlit render

`streamlit.testing.v1.AppTest.from_file("app.py").run()`:

```
real key in project files: NONE
app exceptions: 0
exit code was: 0
```

The application still renders with zero exceptions. The landing page is
unchanged from Phase 1; no AI code is wired into it yet.

### 7.2 Credential scan

Every project file outside `.venv`, `__pycache__` and `.pytest_cache`, under
5 MB, was read and searched for the literal value of `DEPLOY_API_KEY` from the
process environment:

```
real key in project files: NONE
```

Zero matches. The key is present in the environment (so the app can use it) and
absent from every file on disk.

### 7.3 Quality checks

| Check | Result |
|---|---|
| Unused imports in all new/edited modules | 0 |
| Lines over 88 characters in all new/edited files | 0 |
| Import smoke test of all five AI modules | `imports OK` |
| Pre-existing long line `models/schemas.py:228` | Not introduced here, not modified |

`models/__init__.py` is reported by a naive AST scan as having 20 "unused"
imports; they are the intended re-exports listed in its `__all__`, which is a
false positive, not a defect.

---

## 8. What These Tests Do Not Prove

Stated plainly so the pass count is not read as more than it is:

1. **No request reached the real provider.** Every answer came from a fake.
   Real JSON compliance, real instruction-following and real correction
   behaviour are unverified.
2. **Real token headroom is unknown.** 6000 for concepts is unmeasured against
   this model's actual output.
3. **Real error shapes are unverified.** 401/429/5xx payload mapping was built
   in Step 3 from documented shapes and is unit-tested, but never seen live.
4. **Prompt quality is not asserted.** Tests check that inputs appear and
   forbidden instructions exist; they cannot check that the model produces a
   good design concept.
5. **`DesignEvaluation` content quality is out of scope.** Only shape and
   validation are tested.
