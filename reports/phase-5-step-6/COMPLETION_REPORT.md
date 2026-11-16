# Phase 5 / Step 6 — Completion Report

**Project:** Hometsy — Room Intelligence Studio
**Step:** 6 — Design Evaluation and Budget Analysis UI
**Date:** 2026-11-15
**Status:** COMPLETE
**Full test suite:** 996 passed, 0 failed, 0 skipped (baseline 947, delta **+49**)

---

## 1. Objective

Wire the two remaining services of the approved workflow into the Streamlit
application, without adding a single new calculation:

1. **Design Evaluation (AI operation 4).** `ai.design_evaluator` already existed
   and was validated in Phase 5 / Step 3. It had no screen. Give it one that
   shows only what its schema supports, calls it only on an explicit press, and
   never lets its prose overrule the deterministic verdicts printed beside it.
2. **Budget Analysis.** `core.budget_engine` already existed and was validated in
   Phase 4. It had no screen either. Give it one that presents the engine's own
   figures, states the limits of those figures, and performs no arithmetic of its
   own.
3. Integrate both into `WorkflowState`: prerequisites, ordering, invalidation,
   and the finalisable result.

Out of scope and untouched: PDF generation, 3D, image work, live prices, new
catalog items, new dependencies, Git.

---

## 2. Implementation summary

### 2.1 Screen order and the prerequisite problem

`workflow/state.py` already declared, in the approved table:

```python
WorkflowStep.DESIGN_EVALUATION: (SPATIAL_VALIDATION, BUDGET_ANALYSIS)
```

The brief's target order is `... → Placement & Spatial Validation → Design
Evaluation → Budget Analysis`. Read literally, the evaluation would require a
result produced by a *later* screen, so the evaluation would be unreachable
without visiting the budget screen and coming back — a fake ordering.

**Resolution (minimal, no architecture change):** the budget estimate is
deterministic arithmetic over the basket that was just placed, so it is recorded
inside the plan screen's existing `_place_and_store`, immediately after
`record_spatial`. The *data* prerequisite is satisfied by the act that produces
the plan; the *screen* stays last, where the brief puts it. Nothing is invented:
`_place_and_store` calls `core.budget_engine` through `ui.budget`, and writes the
`BudgetAnalysis` it returned.

The user-visible consequence is honest: 9 of 10 steps complete at the budget
screen, with "Final Report" still "Not available yet".

### 2.2 `ui/budget.py` — the deterministic seam

New module, no Streamlit, no AI. It exists so that the rule about materials is
written once instead of in two screens:

* `compute_estimate(budget, recommendations, catalog)` calls
  `compute_budget(..., material_subtotal=ZERO)`. Materials carry no price in V1,
  so an explicit zero is passed **and** `MATERIALS_NOTE` says in words that this
  is "not priced", never "free".
* `matches(stored, result)` is the single definition of "the stored analysis
  still describes the current basket" — used by the budget screen's stale gate
  and by the evaluation's `budget_is_complete` hand-off.
* `usage_text`, `unpriced_errors`, `INCOMPLETE_NOTE`, `INDICATIVE_NOTE`.

`ui.budget` contains no arithmetic. `Decimal` never appears in it.

### 2.3 `ui/pages_evaluation.py` — AI operation 4

Reads, in this order:

| Block | Source | Not from |
|---|---|---|
| What will be evaluated | stored room, concept, basket, placement counts, stored total | — |
| What the spatial engine decided | `state.spatial` + `state.placement` (status badge, validity, blocking problems, warnings) | the model |
| What the budget engine calculated | `state.budget_analysis` + engine errors | the model |
| Saved evaluation | the six `DesignEvaluation` fields | anything else |

* **Prerequisites.** `RECOMMENDATIONS` complete, then a stored placement *and*
  `state.spatial`, then `state.budget_analysis`. Each missing case redirects to
  `plan` with an explanation and renders **no** evaluation button. A fresh
  project redirects to `room`.
* **Button only.** `state.attempt(WorkflowStep.DESIGN_EVALUATION, …)` runs inside
  a spinner. A rerun with no click never reaches it.
* **Failure keeps the previous result.** `attempt` stores only what the callable
  returned, so a timeout leaves the previous `DesignEvaluation` on screen and in
  state; the flash says so.
* **The engine always wins.** A `FAILED` layout prints "Layout failed" and
  "cannot be presented as spatially applicable as it stands" *above* the AI
  prose, whatever the AI wrote. `PARTIAL` prints "1 of 2 requested items were
  placed … only partly buildable". Blocking problems and warnings are separate
  `<div>` blocks with separate labels, plus "A warning is not a blocking
  problem."
* **No invented fields.** `DesignEvaluation` has four narrative judgements and
  two lists. It has no score, no verdict, no strengths. None is derived; the
  screen says so (`_SCHEMA_NOTE`) rather than leaving a gap that looks like an
  omission.
* **Incomplete estimate.** When `estimate.is_trustworthy` is False the screen
  shows "Estimate incomplete", the engine's own error strings, and states that
  the model was told the total is partial. `evaluate_design` receives
  `budget_is_complete=False`, which is the evaluator's existing contract.
* **Opinion, not approval.** `_OPINION_NOTE` states that this does not certify
  structural, ergonomic, accessibility or building-code compliance.

### 2.4 `ui/pages_budget.py` — the deterministic estimate, presented

Hierarchy is fixed: **total → budget limit → remaining/overrun**, then detail.

* Three `score_line` cards: indicative total, your budget, remaining or
  "Over budget by", each with a usage sentence from `usage_text`.
* A success/error badge plus one plain sentence: "The design is not affordable
  as priced" or "fits inside the budget you set".
* Item table: name, quantity, unit cost, line total — every figure a field of
  `BudgetResult`.
* "How the total is built": furniture subtotal, materials "Not priced —
  excluded from the total", other expenses "None recorded", total estimated,
  priced-line count.
* `BudgetLineError`s are listed as errors, clearly *apart* from the over-budget
  message, with "excluded from the total, not costed at zero".
* Materials recommended by the advisor are listed with cost "Not priced".
* A Matplotlib horizontal bar chart of line totals, drawn only when there are at
  least two priced lines (below that a bar says less than the table). Same
  numbers, no new figure.
* Coverage footnote, indicative footnote, and the catalog's own
  `cost_disclaimer` verbatim.
* Stale gate: if the stored analysis disagrees with the engine for the current
  basket, the screen shows "Recalculation needed" and hides every figure until
  the user presses "Recalculate the estimate".
* **No arithmetic in the file** — no `Decimal`, no `+`, no `*` on money.

### 2.5 State, invalidation, and what was *not* changed

Reused unchanged: `WorkflowState`, `DataKey`, `workflow/dependencies.py`,
`attempt`, `guard`, `finalize`, `ProjectResult`. **No new `DataKey` was added**
and the approved invalidation table was not edited.

The required rules already held and are now covered by tests:

| Change | Invalidates | Verified by |
|---|---|---|
| Brief | Evaluation | `test_a_new_brief_clears_the_evaluation` |
| Selected concept | Evaluation (and the plan) | `test_a_new_selection_clears_the_evaluation` |
| Basket | Budget + Evaluation | `test_changing_the_basket_invalidates_the_stored_analysis` |
| Quantity (part of basket identity) | Budget + Evaluation | same test, quantity changed |
| Budget limit | Budget + Evaluation | `test_changing_the_budget_limit_invalidates_the_stored_analysis` |
| Placement coordinates | Evaluation only — **not** the price | `test_recording_coordinates_does_not_invalidate_the_price` |
| Spatial verdict | Evaluation only — **not** the price | `test_a_new_spatial_verdict_clears_only_the_evaluation` |
| Budget analysis | Evaluation | `test_a_recomputed_budget_clears_the_evaluation` |

The Step 5B basket identity — `(item_id, quantity, rationale)`, coordinates
excluded — is untouched, so re-placing an unchanged basket neither re-prices it
nor discards the evaluation.

Non-transitivity is preserved: dropping the evaluation never drops the price and
vice versa. A retained result whose prerequisite is gone is never presented as
current (`is_complete`, not `is not None`) — `test_a_retained_evaluation_without_its_prerequisites_is_not_shown`.

### 2.6 Navigation and the stage strip

* `ui/session.py`: `SCREEN_EVALUATION = "evaluation"`, `SCREEN_BUDGET = "budget"`,
  appended to `SCREEN_ORDER`, added to `SCREEN_TITLES`, exported.
* `app.py`: both screens routed. `app.py` still never imports `ai`.
* `ui/pages_plan.py`: forward button "Continue to the design evaluation",
  gated on `SPATIAL_VALIDATION` **and** `BUDGET_ANALYSIS`. The old "the design
  evaluation and the PDF report … are not available yet" copy is gone because it
  is no longer true.
* `ui/shell.py`: `STAGES["Design Plan"]` now covers RECOMMENDATIONS,
  SPATIAL_VALIDATION, **DESIGN_EVALUATION, BUDGET_ANALYSIS**;
  `STAGES["Final Report"]` = `(FINAL_RESULT,)`. `AVAILABLE_STAGES` is unchanged
  at four, so exactly one stage — the PDF — is still "Not available yet".
* `ui/ai_actions.py`: `evaluate_design(...)` added, with the lazy `import
  ai.design_evaluator` inside the function. It is the only place the evaluation
  service is reached from the interface.

---

## 3. Files created

| File | Lines | Purpose |
|---|---|---|
| `ui/budget.py` | ~135 | Deterministic seam over `core.budget_engine`; notes; `matches`. |
| `ui/pages_evaluation.py` | ~465 | AI operation 4 screen. |
| `ui/pages_budget.py` | ~400 | Budget Analysis screen. |
| `tests/test_ui_evaluation.py` | ~660 | 25 mock-only evaluation tests. |
| `tests/test_ui_budget.py` | ~540 | 24 deterministic budget tests. |
| `reports/phase-5-step-6/COMPLETION_REPORT.md` | — | This file. |
| `reports/phase-5-step-6/TEST_REPORT.md` | — | Test evidence. |
| `reports/phase-5-step-6/NEXT_SESSION.md` | — | Handover. |

## 4. Files modified

| File | Change |
|---|---|
| `ui/ai_actions.py` | `evaluate_design` wrapper; widened model imports; `__all__`. |
| `ui/pages_plan.py` | `_place_and_store` also records the estimate; new forward button; imports `ui.budget`. |
| `ui/session.py` | Two screen constants, order, titles, exports. |
| `ui/shell.py` | Stage-to-step remap. |
| `app.py` | Router entries for both screens. |

No existing test file was modified, deleted, skipped or weakened.

---

## 5. What the AI was and was not asked to do

Sent (all of it produced by Python or by the user):

room, preferences, brief, selected concept, the recommended catalog items,
`SpatialValidation`, `BudgetAnalysis`, and `budget_is_complete`.

Received: one `DesignEvaluation` — four prose judgements, `limitations`,
`recommendations`.

Explicitly not delegated: geometry, coordinates, dimensions, areas, overlaps,
quantities, prices, totals, remaining budget, the spatial verdict, the choice of
catalog items, and whether the design is "approved". The prompt was not edited;
`ai/design_evaluator.py` is unchanged.

---

## 6. Manual QA

Performed in the in-app browser against the real application.

| Check | Result |
|---|---|
| Landing → room form → preferences → review | Correct; 2 of 10 steps complete; review figures match the inputs. |
| Brief screen reached, "Analyse the brief" pressed | **The real API returned a truncated response, twice.** The error copy appeared ("The AI answer was cut off before it finished…") and **nothing was saved** — still "2 of 10 steps complete", brief still "not analysed". Correct failure behaviour, but it blocked the live end-to-end run. |
| Evaluation screen (seeded state), desktop 1104 px | Header, eyebrow "Design Plan · step 4", five-row summary, spatial block with COMPLETE badge, budget block, six decoded evaluation fields, opinion and schema notes, one primary button, navigation. No overflow. |
| Evaluation, `FAILED` layout (150 × 150 room, 3 sofas) | "LAYOUT FAILED", "cannot be presented as spatially applicable", "Not valid", 1 blocking problem quoting the engine's own reason. |
| Evaluation, `PARTIAL` layout (220 × 200, qty 2) | "PARTIAL LAYOUT", "1 of 2 requested items were placed … only partly buildable", 1 warning about the window band, plus the separation note. |
| Evaluation, incomplete estimate (`ghost_sofa` in basket) | "ESTIMATE INCOMPLETE", engine error naming the item, "the evaluation is told that the total is partial". |
| Evaluation, no evaluation stored | "This design has not been evaluated yet." + "Evaluate the design". |
| Budget screen, `priced` | Total 34.500,00 → limit 85.000,00 → remaining 50.500,00 (40.6 %); "Within budget"; table with Bookshelf ×2 = 8.400; subtotal block; materials "Not priced"; chart with 4 bars; three disclaimers. |
| Budget screen, `overbudget` (500 TRY) | "OVER BUDGET BY 22.900,00 TRY", 4680.0 %, "The design is not affordable as priced"; engine warning also surfaced. |
| Budget screen, `unpriced` | "ESTIMATE INCOMPLETE", table holds only the priced item, "Problems in the basket" names `ghost_sofa`, "not costed at zero". |
| "Recalculate the estimate" pressed in the browser | Success flash "The estimate has been recalculated from the current basket."; figures unchanged (deterministic). |
| Mobile width 390 px, both screens | No horizontal overflow (`scrollWidth == clientWidth == 390`). Stage chips wrap to two rows, the three summary cards stack, tables fit at 350 px, the chart scales to 350 px. |
| Console errors during QA | 0. |

Screenshots were taken during QA but were not added to `docs/screenshots/`;
that directory belongs to Phase 9 and its contents must be approved.

### QA note on the harness

The evaluations/budget screens could not be reached through the live AI flow
because of the provider truncation above. They were therefore driven against a
**fully seeded real `WorkflowState`** — real models, real catalog, real
placement/spatial/budget engines — through a throwaway script kept outside the
repository (`%TEMP%\opencode\qa_preview.py`, since deleted). Nothing on either
screen was stubbed, and no screenshot was fabricated.

---

## 7. Known limitations

1. **Materials are unpriced.** There is no material price list in V1. The screen
   says so explicitly rather than costing them at zero; the furniture total is
   therefore not a whole-project total.
2. **The estimate is indicative.** Catalog unit costs are illustrative. This is
   stated three times: coverage note, indicative note, catalog disclaimer.
3. **No overall verdict.** `DesignEvaluation` has no score or verdict field, so
   the screen shows none. Adding one would be a schema change for the project
   owner to approve.
4. **The evaluation cannot be reached by a user whose layout failed *and* whose
   basket is wholly unpriced** — the price result still exists (zero lines with
   errors), so it is reachable, but the screen will show an incomplete estimate.
   This is by design: the AI is told the total is partial.
5. **The chart is a line-total bar chart only.** No pie, no cumulative curve, no
   per-category split. Categories do not exist in the catalog.
6. **Live end-to-end AI QA was not completed.** The brief step fails upstream at
   the provider (truncated response, twice). This is pre-existing Step 4
   behaviour and is reported correctly; the two new screens are downstream of it
   and were verified against real deterministic data instead.
7. **No PDF yet**, so "Start a new project" is the only exit from the budget
   screen other than going back.

---

## 8. Scope deviations

**None.** No dependency was added. No model, endpoint, prompt or credential
mechanism was changed. No catalog item was added. `ai/design_evaluator.py`,
`core/budget_engine.py` and `workflow/dependencies.py` are byte-identical to
their approved versions.

The one judgement call worth recording is §2.1: the estimate is recorded on the
plan step rather than requiring a round trip through the budget screen. It
follows the existing `STEP_PREREQUISITES` table rather than editing it, and the
screen order stays exactly as the brief specifies.

---

## 9. Recommended next action

**Phase 6 — PDF Report Generation.** `WorkflowState.finalize()` already
assembles a complete `ProjectResult` (room, preferences, brief, concepts,
selection, recommendations, spatial, budget analysis, evaluation) and
`FINAL_RESULT` is the only unfinished step. The stage strip already reserves
"Final Report" for it. ReportLab is in the approved stack and already installed.

Before that, the truncated-response failure in the brief step is worth a
separate look: it blocks the whole live flow, and it is a `MAX_TOKENS` /
response-length question rather than an interface one.
