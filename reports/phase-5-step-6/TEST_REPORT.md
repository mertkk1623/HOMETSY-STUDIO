# Phase 5 / Step 6 — Test Report

**Project:** Hometsy — Room Intelligence Studio
**Step:** 6 — Design Evaluation and Budget Analysis UI
**Date:** 2026-11-15
**Environment:** Python 3.13.18 in `.venv` (project interpreter)
**Working directory:** `[PROJECT_ROOT]`

---

## 1. Commands executed

```powershell
cd "[PROJECT_ROOT]"

# New evaluation suite
& ".venv\Scripts\python.exe" -m pytest tests/test_ui_evaluation.py -q

# New budget suite
& ".venv\Scripts\python.exe" -m pytest tests/test_ui_budget.py -q

# The three screens that share this state
& ".venv\Scripts\python.exe" -m pytest tests/test_ui_budget.py `
    tests/test_ui_evaluation.py tests/test_ui_advisor_flow.py -q

# Every directly affected area together
& ".venv\Scripts\python.exe" -m pytest tests/test_ui_advisor_flow.py `
    tests/test_ui_ai_flow.py tests/test_ui_app.py -q

# Full suite
& ".venv\Scripts\python.exe" -m pytest -q

# Collection count per file
& ".venv\Scripts\python.exe" -m pytest --collect-only -q
```

Every result below is from an actual run in this session. Nothing is estimated.

---

## 2. Results

### 2.1 New suites

```text
tests/test_ui_evaluation.py .........................   [100%]
25 passed in 6.19s

tests/test_ui_budget.py ........................         [100%]
24 passed in 8.56s
```

### 2.2 Combined, after the final cleanup

```text
tests/test_ui_budget.py tests/test_ui_evaluation.py
tests/test_ui_advisor_flow.py
......................................................... [100%]
77 passed in 17.75s
```

### 2.3 The three pre-existing screen suites (regression check)

```text
tests/test_ui_advisor_flow.py tests/test_ui_ai_flow.py tests/test_ui_app.py
........................................................................ [ 73%]
..........................                                               [100%]
98 passed in 19.59s
```

### 2.4 Full suite

```text
........................................................................ [ 86%]
........................................................................ [ 93%]
............................................................             [100%]
996 passed in 33.95s
```

| | Count |
|---|---|
| Collected | 996 |
| Passed | 996 |
| Failed | 0 |
| Skipped | 0 |
| xfail / xpass | 0 |
| Errors | 0 |
| Warnings promoted to errors | 0 |
| Duration | 33.95 s |

### 2.5 Delta against the 947 baseline

| Change | Tests |
|---|---|
| New `tests/test_ui_evaluation.py` | +25 |
| New `tests/test_ui_budget.py` | +24 |
| **Total** | **+49** |

**947 → 996.** No test was deleted, skipped, weakened, or retuned to fit the new
behaviour. Every pre-existing file has the identical count it had at the 947
baseline:

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
| `test_placement_engine` | 56 | — |
| `test_room_engine` | 48 | — |
| `test_spatial_engine` | 46 | — |
| `test_ui_advisor_flow` | 28 | — |
| `test_ui_ai_flow` | 38 | — |
| `test_ui_app` | 32 | — |
| **`test_ui_budget`** | **24** | **+24 (new)** |
| `test_ui_commits` | 40 | — |
| **`test_ui_evaluation`** | **25** | **+25 (new)** |
| `test_ui_layout` | 11 | — |
| `test_ui_presentation` | 34 | — |
| `test_ui_session` | 22 | — |
| `test_validation` | 35 | — |
| `test_workflow_dependencies` | 35 | — |
| `test_workflow_integration` | 9 | — |
| `test_workflow_state` | 83 | — |
| **Total** | **996** | **+49** |

---

## 3. Test design

### 3.1 The evaluation suite is mock-only

`ui.ai_actions.evaluate_design` is replaced by a `FakeEvaluator` that records its
keyword arguments and replays a queued answer or exception. Therefore:

* no HTTP request is made;
* the suite runs with no API key present;
* the recorded call proves *what* the screen passed, which is the security-relevant
  half of the contract.

The placement, spatial and budget engines are **not** stubbed. They are
deterministic and they are the verdicts the screen exists to protect.

### 3.2 The budget suite mocks nothing arithmetic

`core.budget_engine.compute_budget` runs for real through the screen. Only the
advisor is stubbed, so a basket can be installed without a model. Every expected
figure is recomputed by the engine in the test and compared to what the screen
shows — the test never re-implements the arithmetic it is checking.

### 3.3 Screens are exercised through the real router

Both suites drive `app.py` with `streamlit.testing.v1.AppTest`, so the screen, the
router, the session adapter and `WorkflowState` are all real.

---

## 4. Required scenarios

### 4.1 Design Evaluation (§7.1)

| # | Requirement | Test(s) | What it proves |
|---|---|---|---|
| 1 | Evaluation only on an explicit press | `test_opening_the_evaluation_screen_makes_no_request`, `test_a_rerun_after_an_evaluation_does_not_call_the_model_again` | Opening the screen: 0 calls, "This design has not been evaluated yet." Two reruns after a press leave the count at 1. |
| 2 | No prerequisite → no button | `test_the_screen_refuses_to_run_without_a_layout`, `test_the_screen_refuses_to_run_without_a_budget_result`, `test_a_started_project_cannot_reach_the_evaluation_early` | Missing layout → redirect to `plan`, no button. Layout but no price → same. Fresh project → `room`. 0 calls in all three. |
| 3 | Only current, validated inputs | `test_the_evaluator_receives_the_stored_data_and_no_calculated_figure` | `room`, `preferences`, `budget`, `brief`, `concept`, `recommendations`, `spatial`, `analysis` all compare equal to the stored objects; `budget_is_complete is True`. |
| 4 | `SPATIAL FAILED` ⇒ never "spatially applicable" | `test_a_failed_layout_is_never_presented_as_spatially_applicable` | 3 sofas in a 150 × 150 room → "layout failed", "cannot be presented as spatially applicable", "not valid", no `<svg>`. **Also asserted after the model answers as if the design were fine** — the engine's text is still there. |
| 5 | `PARTIAL` stated plainly | `test_a_partial_layout_is_stated_as_partial` | 2 sofas in 220 × 200 → "partial layout", "only partly buildable", "1 of 2 requested items were placed". |
| 6 | Warnings and errors stay separate | `test_blocking_problems_and_warnings_stay_separate` | Both messages present under their own headings, `hm-issue--error` and `hm-issue--warning` both present, and "a warning is not a blocking problem". |
| 7 | Over budget is a real risk | `test_an_over_budget_design_is_reported_as_a_real_risk` | 500 TRY budget → "Over budget by" with the engine's figure; no raw field name leaks into the copy. |
| 8 | Missing price data ⇒ scope stated | `test_an_incomplete_estimate_is_announced_as_incomplete` | `ghost_sofa` basket → `budget_is_complete is False` reaches the service; the screen shows "ESTIMATE INCOMPLETE" and the engine's error. |
| 9 | No AI-computed figure | `test_the_evaluation_screen_never_calculates_a_price_itself` | Every money string on screen equals `commits.format_money` of a stored field. |
| 10 | Failure preserves the previous result | `test_a_failed_call_keeps_the_previous_evaluation` | After a timeout the stored evaluation is identical, the step is still complete, the error is shown, and the earlier text is still readable. |
| 11 | Failed *first* call stores nothing | `test_a_failed_first_call_stores_nothing` | `evaluation is None`, step incomplete, button still offered. |
| 12 | Only the schema's fields | `test_every_schema_field_is_shown_and_no_other_is_invented` | All four judgements and both lists are rendered; no score, no verdict, no strengths; the opinion and schema notes are present. |
| 13 | Invalidation | `test_an_edit_that_clears_the_plan_clears_the_evaluation_too`, `test_a_new_brief_clears_the_evaluation`, `test_a_new_selection_clears_the_evaluation`, `test_a_new_spatial_verdict_clears_only_the_evaluation`, `test_a_recomputed_budget_clears_the_evaluation` | Brief / selection / basket / spatial / price each drop `EVALUATION`; a spatial change does **not** drop `BUDGET_ANALYSIS`. |
| 14 | Nothing stale is shown as current | `test_a_retained_evaluation_without_its_prerequisites_is_not_shown` | A retained evaluation with its price removed renders nothing and redirects. |
| 15 | Navigation and no request from the plan | `test_the_evaluation_screen_offers_the_budget_step`, `test_the_plan_screen_reaches_the_evaluation_once_it_can`, `test_the_plan_screen_makes_no_evaluation_request` | Both directions work; reaching the screen from the plan makes 0 calls. |
| 16 | `finalize()` integrity | `test_the_finalised_result_carries_the_new_results` | The assembled `ProjectResult` carries the new evaluation, budget, spatial and recommendations; `FINAL_RESULT` is complete. |

### 4.2 Budget Analysis (§7.2)

| # | Requirement | Test(s) | What it proves |
|---|---|---|---|
| 1 | Only the engine's figures | `test_the_screen_shows_the_engines_own_figures`, `test_the_screen_never_recomputes_a_total_itself` | Total, limit and remaining each equal a `BudgetAnalysis` field; the stored analysis equals a fresh engine run. |
| 2 | Quantities in the arithmetic | `test_quantity_multiplies_the_line_total`, `test_the_item_table_lists_every_priced_line_with_its_subtotal` | 3 armchairs → `unit × 3` in the subtotal and in the table; a two-line basket shows each line total. |
| 3 | Unpriced item ≠ zero | `test_an_unpriced_item_is_reported_and_never_costed_at_zero` | Subtotal is exactly the priced item; `unpriced_errors == ("ghost_sofa",)`; "excluded from the total, not costed at zero"; "not a final figure". |
| 4 | Wholly unpriced basket | `test_a_wholly_unpriced_basket_has_no_item_table` | "no item in the basket could be priced" + "Estimate incomplete"; no zero total is presented as a quote. |
| 5 | Overrun | `test_an_overrun_is_reported_with_the_engines_own_figure` | "Over budget by" the engine's absolute figure, "Over budget", "not affordable as priced". |
| 6 | Remaining budget | `test_a_remaining_budget_is_reported_as_remaining` | "Remaining budget", "Within budget", the engine's figure. |
| 7 | Zero budget | `test_a_zero_budget_does_not_report_a_percentage` | Usage is stated as unavailable rather than computed as ∞ or 0 %. |
| 8 | Materials excluded and shown unpriced | `test_materials_are_listed_as_unpriced_and_outside_the_total` | `material_subtotal == 0.00`, `total == furniture_subtotal`, "Not priced — excluded from the total", "No materials were recommended". |
| 9 | Indicative, not a quote | `test_the_screen_states_that_the_estimate_is_indicative` | "indicative", "not verified market prices", and the catalog's own disclaimer as a prefix. |
| 10 | Recording | `test_the_screen_records_nothing_until_the_user_recalculates`, `test_recalculating_stores_the_same_deterministic_result` | Two reruns change nothing in state or in the invalidation log; a press stores an identical result and flashes. |
| 11 | Stale stored analysis | `test_a_stale_stored_analysis_is_not_shown_as_current` | A figure that could not come from this basket is refused: "Recalculation needed", the wrong figure is absent from the page, and recalculating repairs it. |
| 12 | Plan step records the estimate | `test_the_estimate_is_recorded_by_the_plan_step_not_the_budget_screen` | After the plan step both `BUDGET_ANALYSIS` and `SPATIAL_VALIDATION` are complete — the evaluation's prerequisites. |
| 13 | Invalidation | `test_changing_the_budget_limit_invalidates_the_stored_analysis`, `test_changing_the_basket_invalidates_the_stored_analysis`, `test_recording_coordinates_does_not_invalidate_the_price` | Limit and basket both drop the analysis (the *layout* survives a limit change); coordinates alone drop nothing. |
| 14 | Prerequisites and navigation | `test_the_budget_screen_refuses_to_run_without_a_basket`, `test_the_budget_screen_refuses_to_run_without_an_estimate`, `test_the_budget_screen_links_back_to_the_evaluation` | Each guard redirects and hides the action; "Back to the evaluation" exists; the PDF is described as unavailable rather than offered. |
| 15 | No AI on this screen | `test_the_budget_screen_makes_no_ai_call` | All four AI entry points are replaced by stubs that raise — the screen loads and recalculates with zero calls. |
| 16 | Chart adds nothing | `test_the_distribution_chart_repeats_the_table_and_adds_nothing`, `test_a_single_priced_line_does_not_get_a_chart` | Two lines → chart heading present; one line → no chart. |

---

## 5. Manual verification beyond pytest

| Check | Result |
|---|---|
| Full suite after the final cleanup | 996 passed, 33.95 s |
| Line length (88 columns) | 0 violations in all ten new/changed files |
| Unused imports (AST scan) | 0. Two were found and removed during cleanup: `Decimal` in `ui/pages_budget.py`, `BudgetInput` in `tests/test_ui_budget.py`. |
| Live app, landing → review | Correct; 2 of 10 steps complete |
| Live app, brief step | Real API returned a truncated response twice; error copy shown; **nothing stored** (still 2 of 10). Correct failure behaviour, but no live AI stage could be driven. |
| Evaluation screen, seeded real state, desktop | Renders; no overflow; one primary button |
| Evaluation, FAILED / PARTIAL / incomplete-estimate / no-evaluation | All four states behave as specified |
| Budget screen, priced / overbudget / unpriced | All three render the engine's figures; no recomputation |
| "Recalculate the estimate" in the browser | Success flash, identical figures |
| Mobile 390 px, both screens | `scrollWidth == clientWidth == 390`; no horizontal scrolling; tables fit |
| Console errors during QA | 0 |

---

## 6. Safety checks

| Check | Result |
|---|---|
| Network access in tests | None. Every AI call is a stub; no socket is opened. |
| API key required | No. The suite runs without `DEPLOY_API_KEY`. |
| Key referenced in new code or tests | No. The only credential-adjacent name is the existing `ai_actions.load_config()`. |
| `app.py` imports `ai` | No — the new screens import `ai_actions`, which imports `ai` lazily inside the function. The existing child-process test still passes. |
| `ai/design_evaluator.py` changed | No. |
| `core/budget_engine.py` changed | No. |
| `workflow/dependencies.py` changed | No. |
| `ui/budget.py` contains arithmetic | No — it passes `material_subtotal=ZERO` and compares models. |
| `ui/pages_budget.py` contains money arithmetic | No — no `Decimal`, no operators on money. |
| New dependency | None. Matplotlib and pandas were already installed and already approved. |
| `random` / `time` / `datetime` in the new modules | Not used. |

---

## 7. Known test limitations

1. `test_a_partial_layout_is_stated_as_partial` depends on the placement engine
   producing `PARTIAL` for 2 sofas in a 220 × 200 room. That was verified to be
   the engine's real behaviour in this session; a future change to placement
   heuristics would fail the test rather than silently skipping it.
2. The evaluation's "model says the design is fine while the layout failed" case
   is asserted by feeding a contradictory answer, not by a real model response.
   A real model cannot be relied on to be wrong on demand.
3. No test asserts the *visual* layout; that was checked in the browser and is
   documented in §5, not in pytest.
