# Phase 5 / Step 5A — Next Session Handover

**Project:** Hometsy — Room Intelligence Studio
**Written at the end of:** Phase 5 Step 5A — Deterministic Furniture Placement Engine
**Date:** 2026-11-15
**Status:** Step 5A complete. Implementation stopped, awaiting approval.

---

## 1. Read these first

In this order:

1. `PROJECT_BRIEF.md`
2. `TECHNICAL_ARCHITECTURE.md`
3. `DESIGN_SYSTEM.md`
4. `DEVELOPMENT_PLAN.md`
5. `AGENTS.md`
6. `reports/phase-5-step-5a/COMPLETION_REPORT.md`
7. `reports/phase-5-step-5a/TEST_REPORT.md`
8. `reports/phase-5-step-4/COMPLETION_REPORT.md` — still valid for the UI layer
9. `reports/phase-5-step-3/NEXT_SESSION.md` — still valid for provider behaviour
   and token budgeting; **do not undo §3 of that document**

`AGENTS.md` §4 requires explicit approval between phases. Do not proceed on your
own.

---

## 2. What this step established

A pure, deterministic placement engine now exists, and the split between
"propose" and "validate" is enforced in code and in tests.

| Concern | Where it now lives |
|---|---|
| Choosing coordinates | `core.placement_engine.py` — the only module that writes a position |
| Deciding whether a layout is acceptable | `core.spatial_engine.py` — unchanged, still the sole validator |
| Reporting which items could not be placed | `core.placement_engine.UnplacedFurniture` |
| Turning a placement report into interface findings | `core.validation.placement_findings` |
| Writing coordinates back onto the persisted model | `core.placement_engine.apply_placements` |

The important invariant: **the engine never decides that its own layout is
valid.** It always asks `validate_placement`, and if that reports any error the
result is `FAILED` with `candidate = None`. A test
(`test_engine_never_bypasses_the_shared_validator`) forces the validator to reject
a layout and confirms the engine honours it.

---

## 3. Decisions worth remembering

1. **`null` coordinates are normal.** The advisor never supplies them. The engine
   ignores `position_x_cm`/`position_y_cm` even when they are present, so a stale
   or invented coordinate cannot leak into the layout. Tested.
2. **Rotation is a hint, not an instruction.** The requested angle and its
   quarter turn are both tried; the better-scoring one is stored on the
   footprint. `180`/`270` are not separate candidates because V1 has no front
   face, so they would be geometric duplicates. See the module docstring.
3. **Invalid candidates are excluded, not penalised.** A candidate that leaves
   the room, touches the door clearance zone, or overlaps anything is dropped
   before scoring. Tests 3, 4, 5 depend on this.
4. **Four strategies exist so the greedy pass has alternatives.** The layout
   score is strategy-neutral (`QUALITY_WEIGHTS` has no `wall_preference` term);
   only per-item generation uses it. Removing that distinction would let a
   layout win because of how it was built rather than what it looks like, and
   `test_layout_score_does_not_depend_on_the_generation_strategy` would fail.
5. **Three statuses, not two.** `PARTIAL` is a first-class outcome with
   `is_complete == False`. Never present it as success.
6. **Unplaced items carry a reason, not just a count.** The reason names the
   item, its dimensions and the obstacle. A future interface can show it
   verbatim.
7. **The selected concept is not a placement input.** The approved models carry
   no field through which it could legitimately affect geometry. Do not invent
   one; the concept already influences placement by determining *which* items
   the advisor recommends.

---

## 4. Known limitations to carry forward

1. **One stored position per recommendation.** `apply_placements` writes the
   first copy; `quantity > 1` therefore collapses on write-back and the Phase 3
   validator reports `quantity_collapsed`. The engine itself places all copies.
   Fixing this needs a change to `FurnitureRecommendation` (a list of positions),
   which is a **data-model change requiring explicit approval**.
2. Greedy single-pass placement; no backtracking.
3. Rectangular footprints only — a large rug is treated as solid furniture.
4. Wall anchoring prefers the longest edge (wrong for a free-standing desk).
5. Placement quality is a heuristic about walls, spacing and free floor, not a
   design judgement.
6. Large rooms are slower: 2000 × 2000 cm with 40 copies takes ~15.8 s.
   Residential sizes are 0.05–0.16 s.
7. **Nothing calls the engine yet.** `workflow/state.py` was to be left
   unchanged, so the running application still produces `unplaced_item`
   warnings from `build_footprints`.

---

## 5. Suggested next step (for approval, not yet started)

Connect the engine to the workflow, which is the piece that makes the placement
visible in the product:

1. In `ui/ai_actions.py` (the existing single AI bridge) or a sibling module, call
   `place_furniture` once recommendations exist — **not** inside an AI call.
2. Persist via `apply_placements`, then record the result with the existing
   `state.record_spatial(...)` using `result.validation`. No change to
   `workflow/state.py` should be needed; if one seems necessary, report it before
   coding.
3. Surface three things on the layout screen: the unplaced items with their
   reasons, the score breakdown (`LAYOUT_WEIGHTS`), and the fact that the plan is
   illustrative rather than a construction drawing.
4. Consider (separately, with approval) whether `FurnitureRecommendation` should
   carry a list of positions so `quantity > 1` survives write-back.

Do not start any of this before the user approves Step 5A.

---

## 6. Commands

```powershell
cd "[PROJECT_ROOT]"

# New tests only
& ".venv\Scripts\python.exe" -m pytest tests/test_placement_engine.py -q

# Related geometry tests
& ".venv\Scripts\python.exe" -m pytest tests/test_spatial_engine.py `
    tests/test_room_engine.py tests/test_validation.py -q

# Both together
& ".venv\Scripts\python.exe" -m pytest tests/test_placement_engine.py `
    tests/test_spatial_engine.py tests/test_room_engine.py `
    tests/test_validation.py -q

# Full suite
& ".venv\Scripts\python.exe" -m pytest -q
```

Expected: `55 passed`, `128 passed`, `183 passed`, `894 passed`.

Use `.venv\Scripts\python.exe` (Python 3.13.18). Do not use the global Python
3.15.2.

---

## 7. Workspace state

- No Git repository; nothing committed, pushed or deployed.
- No API key written to any project file, test or report. `DEPLOY_API_KEY`
  exists only in the process environment.
- No test reaches the network; the suite runs without an API key.
- No temporary files, preview harnesses or test servers remain from this step.
- `docs/screenshots/` is still empty (Phase 9).
