# Phase 5 / Step 5B — Next Session Handover

**Project:** Hometsy — Room Intelligence Studio
**Written at the end of:** Phase 5 Step 5B — Furniture Advisor and Spatial Validation UI
**Date:** 2026-11-15
**Status:** Step 5B complete. Implementation stopped, awaiting approval.

---

## 1. Read these first

In this order:

1. `PROJECT_BRIEF.md`
2. `TECHNICAL_ARCHITECTURE.md`
3. `DESIGN_SYSTEM.md`
4. `DEVELOPMENT_PLAN.md`
5. `AGENTS.md`
6. `reports/phase-5-step-5b/COMPLETION_REPORT.md`
7. `reports/phase-5-step-5b/TEST_REPORT.md`
8. `reports/phase-5-step-5a/COMPLETION_REPORT.md` — still valid for the placement engine
9. `reports/phase-5-step-4/COMPLETION_REPORT.md` — still valid for the UI layer
10. `reports/phase-5-step-3/NEXT_SESSION.md` — still valid for provider behaviour and
    token budgeting; **do not undo §3 of that document**

`AGENTS.md` §4 requires explicit approval between phases. Do not proceed on your
own.

---

## 2. What this step established

The design decision is now visible end to end, and the split between the layers
is enforced in code and tests.

| Concern | Where it lives |
|---|---|
| Choosing catalog items | `ai/design_advisor.py`, reached only through `ui.ai_actions` |
| Calling the engines once and passing their output through | `ui/layout.py` — the only seam |
| Drawing the validated layout | `ui/diagram.placement_plan_svg` |
| Presenting status, score, errors and warnings | `ui/pages_plan.py` |
| Deciding what is stale | `workflow/state.py` + `workflow/dependencies.py` |

The invariant this step added: **the screen draws only what
`PlacementOutcome.placed` contains, and shows a score only when the engine
achieved one.** A `FAILED` outcome carries `placed = []` and `score = None` by
construction, so there is no code path from a rejected candidate to a drawn plan.

---

## 3. Decisions worth remembering

1. **`FurnitureRecommendation.positions` exists and must be used.** One entry per
   placed copy; `position_x_cm` / `position_y_cm` mirror `positions[0]` for older
   readers. `len(positions) > quantity` is rejected by a validator. Do not revert
   to a single pair — `test_every_placed_copy_gets_its_own_position` and
   `test_multiple_copies_survive_the_write_back` depend on it.
2. **`record_spatial` takes `placements`.** The annotated basket is written under
   `DataKey.SPATIAL`, not `FURNITURE`, so a coordinate never invalidates a price.
   `_clear(SPATIAL)` strips coordinates with `unplace_recommendation`. Removing
   either half re-introduces the data loss this step fixed.
3. **Basket identity is `(item_id, quantity, rationale)`.** `_basket_requests`
   deliberately excludes coordinates *and* `rotation_degrees`, because
   `apply_placements` writes both. Including them makes an unchanged answer look
   new and needlessly discards the layout and the price.
4. **The advisor is button-only.** `ui/ai_actions.recommend_furniture` is called
   inside `if st.button(...)` and nowhere else, and every result goes through
   `state.attempt`. A rerun must never make a request; a failure must never store
   anything.
5. **`_blocking_basket_findings` reuses `core.validation.validate_catalog_references`.**
   Do not add a screen-local catalog rule. A basket the catalog rejects must not
   be offered a "Calculate the layout" button.
6. **`ui/diagram.py` is hand-written SVG, two drawings.** `room_diagram_svg`
   illustrates the room on the input screens; `placement_plan_svg` draws the
   validated layout. They are separate on purpose: the second must never be able
   to display a footprint it was not given. `_plan_geometry` is the only place the
   scale is computed.
7. **Statuses have three distinct copies.** `_status_copy` must keep returning
   three distinct badges and three distinct sentences. The failure sentence must
   never contain a placed count — a test asserts this.
8. **Materials are unpriced, permanently in V1.** `MaterialRecommendation` has no
   cost field. The screen states "Not priced". Do not add a price field to make
   the screen prettier.

---

## 4. Known limitations to carry forward

1. **Greedy, single-pass placement.** An early item's position is never
   reconsidered. Inherited from Step 5A.
2. **Rectangles only.** A large rug is treated as solid furniture and is usually
   unplaced beside a full seating group.
3. **No front-face reasoning.** 180°/270° are not separate candidates.
4. **One layout shown.** Several strategies are computed; only the best is
   exposed. Offering a choice is not in V1.
5. **The score is a heuristic** about walls, spacing and free floor. It says
   nothing about sightlines or focal points.
6. **Materials have no budget line.** The estimate covers furniture only.
7. **The basket gate predicts catalog validity, not fit.** Whether a valid basket
   fits is the placement engine's answer, and a failure is shown as a failure.
8. **Large rooms are slow.** 2000 × 2000 cm with 40 copies takes ~16 s. Realistic
   rooms take 0.05–0.21 s. A spinner covers the wait.
9. **No real-device responsive matrix.** Fluid widths and a wrapping legend were
   checked at desktop and narrow widths only.
10. **Evaluation and PDF are named but not built.** The screen says so.

---

## 5. Suggested next step (for approval, not yet started)

**Phase 5 Step 6 — Design Evaluation screen.** This is the last AI surface V1
needs, and the fourth service already exists and was live-validated in Step 3.

1. Add `evaluate_design` to `ui/ai_actions.py`, mirroring `recommend_furniture`
   exactly: lazy `ai` import, catalogue/config factory, unchanged
   `failure_message` mapping. No new error taxonomy.
2. Create `ui/pages_evaluation.py` and register `SCREEN_EVALUATION` in
   `ui/session.py` and `app.py`. Add the stage to `AVAILABLE_STAGES`.
3. The evaluation needs the design, the basket, the validated placement and the
   budget. **It must be gated** on `SPATIAL_VALIDATION` being complete, and the
   prompt must be given the *validated* outcome, not a re-derived one.
4. Record through `state.attempt(WorkflowStep.DESIGN_EVALUATION, ...)` →
   `state.record_evaluation`. A failure stores nothing and keeps the previous
   evaluation, exactly as the plan screen does.
5. Whatever the evaluation says must be presented as an opinion. It must not be
   allowed to contradict the geometric verdict: an AI that praises a `FAILED`
   layout is a bug, not a feature. Decide and state the rule before coding —
   suggested: the evaluation screen shows the spatial verdict verbatim beside the
   AI text, and refuses to evaluate a `FAILED` layout.
6. Then wire the budget analysis screen (deterministic, no AI):
   `compute_budget` → `state.record_budget_analysis`, with the line items, usage
   percentage and any `BudgetLineError` shown as errors rather than skipped.

Do not start any of this before the user approves Step 5B.

---

## 6. Commands

```powershell
cd "[PROJECT_ROOT]"

# The new suites
& ".venv\Scripts\python.exe" -m pytest tests/test_ui_advisor_flow.py `
    tests/test_ui_layout.py tests/test_ui_presentation.py -q

# Everything the plan screen can break
& ".venv\Scripts\python.exe" -m pytest tests/test_ui_advisor_flow.py `
    tests/test_ui_layout.py tests/test_ui_presentation.py tests/test_ui_app.py `
    tests/test_ui_ai_flow.py tests/test_ui_session.py tests/test_ui_commits.py `
    tests/test_workflow_state.py tests/test_workflow_integration.py `
    tests/test_workflow_dependencies.py tests/test_placement_engine.py `
    tests/test_spatial_engine.py -q

# Full suite
& ".venv\Scripts\python.exe" -m pytest -q
```

Expected: `73 passed`, `434 passed`, `947 passed`.

Use `.venv\Scripts\python.exe` (Python 3.13.18). Do not use the global Python
3.15.2.

---

## 7. Traps this step hit (so the next one does not)

| Trap | What happened | Rule |
|---|---|---|
| A probe is not optional | The first end-to-end run showed 7 blocks drawn and 0 stored coordinates. Tests alone would not have found it. | Run a scripted `AppTest` pass over any new screen before declaring it done. |
| Flash messages are not markdown | `assert "timed out" in text` failed because `render_flash` writes to `at.error`, a separate collection. | Search `at.error` / `at.warning` / `at.success` / `at.info`, not only `at.markdown`. |
| Test fixtures must respect the catalog | A basket with `dining_chair` in a living room is gated by `validate_catalog_references`, and the test failed for the right reason. | Check `data/furniture_catalog.json` `supported_room_types` before choosing test items. |
| A replaced key is not in its own invalidation list | `assert DataKey.FURNITURE in dropped` failed; `record_recommendation` refreshes that key rather than clearing it. | Assert on the *dependents* (`SPATIAL`, `BUDGET_ANALYSIS`). |
| The room form rejects impossible openings | A 150 cm room cannot take the default 160 cm window, so the form never submitted and the widget keys vanished. | Set small openings in the harness so one fixture serves every room size. |
| SVG legend spacing is real | The flex legend produced "Placed furnitureDoorWindow" and the test caught it. | Fix the renderer, never the assertion, when the output is genuinely wrong for a reader. |

---

## 8. Workspace state

- No Git repository; nothing committed, pushed or deployed.
- No API key written to any project file, test or report. `DEPLOY_API_KEY`
  exists only in the process environment.
- No test reaches the network; the suite runs without an API key.
- The temporary probe harness lives outside the repository, under
  `C:\Users\[LOCAL_USER]\AppData\Local\Temp\opencode\hm_plan_probe\`, and is not part of
  the project. It can be deleted.
- `docs/screenshots/` is still empty (Phase 9).
