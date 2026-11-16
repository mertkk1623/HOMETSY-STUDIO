# Phase 5 / Step 5B — Completion Report

**Project:** Hometsy — Room Intelligence Studio
**Step:** 5B — Furniture Advisor and Spatial Validation UI
**Date:** 2026-11-15
**Status:** Implementation complete. Stopped, awaiting approval.

---

## 1. Objective

Make the deterministic and AI halves of the design decision visible in one
screen. The user presses a button, the Design Advisor chooses catalog items for
the selected concept, Python places them, the spatial engine judges the result,
and the screen reports what actually happened — including when nothing could be
placed.

The step had to satisfy one constraint above all others: **geometry stays on
Python's side and validity stays the spatial engine's verdict.** The interface is
allowed to explain a result; it is not allowed to compute or soften one.

---

## 2. Implementation summary

### 2.1 Responsibility split

| Question | Answered by | Where the screen gets it |
|---|---|---|
| Which catalogs items suit this concept? | `ai/design_advisor.py` | `ui.ai_actions.recommend_furniture` |
| Where does each copy go? | `core/placement_engine.py` | `ui.layout.analyse_layout` |
| Is the layout acceptable? | `core/spatial_engine.py` | `PlacementResult.validation` |
| How good is it, heuristically? | `core/placement_engine` scoring | `PlacementOutcome.score` |
| What is stored, and what goes stale? | `workflow/state.py` | `record_recommendation`, `record_spatial` |

`ui/pages_plan.py` computes no geometry and no score. `ui/layout.py` is the only
place the screen touches the engines, and it does nothing but call them and pass
their output through.

### 2.2 Quantity integrity — the model extension (§5 of the brief)

This was the substantive problem of the step, and it was not hypothetical: the
first end-to-end probe showed a seven-piece plan while the stored basket recorded
**zero** coordinates, because `FurnitureRecommendation` could express only one
position per recommendation.

Two distinct defects were involved.

**(a) A recommendation could not describe more than one placed copy.** With
`quantity = 2` the engine placed two armchairs, `apply_placements` wrote the first
one, and Phase 3's validator reported `quantity_collapsed`. The stored project
therefore disagreed with the drawing.

The fix is a minimal, architecture-consistent extension:

| Addition | Purpose |
|---|---|
| `FurniturePosition` (`position_x_cm`, `position_y_cm`, `rotation_degrees`) | One placed copy, in centimetres, in the existing coordinate system. |
| `FurnitureRecommendation.positions: list[FurniturePosition]` | One entry per copy the engine actually placed; empty means "not placed". |
| `model_validator` `_positions_never_exceed_quantity` | `len(positions) > quantity` is rejected at construction, so the model cannot claim more copies than were asked for. |

`position_x_cm` / `position_y_cm` / `rotation_degrees` remain on the
recommendation and now mirror `positions[0]`. That keeps every existing reader
(the budget engine, the Phase 3 validator, the AI parser) working unchanged.

`core.spatial_engine.build_footprints` became copy-aware: it emits one footprint
per placed copy and, when `len(positions) < quantity`, reports
`unplaced_copies` as a **warning** — the layout is still geometrically valid; it
is simply short of what was requested. `quantity_collapsed` no longer exists,
because the condition it described can no longer occur.

**(b) The coordinates were computed and then thrown away.** The probe showed
`state.furniture` with zero `positions` while `state.placement` held seven
footprints. `finalize()` builds `ProjectResult.recommendations` from
`state.furniture`, so a later PDF would have described the request and lost the
room. `record_spatial` now takes an optional `placements` argument and writes the
annotated basket through the same invalidation path:

```python
state.record_spatial(analysis.validation, analysis.outcome, analysis.placements)
```

It is written under `DataKey.SPATIAL`, not `DataKey.FURNITURE`, because items,
quantities and prices are unchanged — only the placement annotation is added — and
discarding a computed price to record a coordinate would be wrong. A test asserts
that `BUDGET_ANALYSIS` is not invalidated by placing.

Symmetrically, `_clear(DataKey.SPATIAL)` now strips coordinates via
`unplace_recommendation`, so a stored position never outlives the validation that
justified it. A room-dimension change removes the layout and its coordinates
together.

### 2.3 Basket identity — what counts as "a new request"

Once coordinates live on the stored basket, comparing whole
`FurnitureRecommendation` objects would make an *unchanged* answer look new on the
next advisor run, needlessly discarding the layout and recomputing an identical
price. `record_recommendation` now compares through `_basket_requests()`:

```python
(item_id, quantity, rationale)
```

Coordinates and `rotation_degrees` are excluded because `apply_placements` writes
both — the engine's chosen orientation replaces the advisor's hint. They annotate
a placement; they do not define a request. Two tests pin both directions: an
unchanged request drops nothing, a changed quantity drops the layout.

### 2.4 The advisor call is button-only

`ui/ai_actions.recommend_furniture` is called only inside
`if st.button(...)`, and only through `state.attempt(WorkflowStep.RECOMMENDATIONS,
...)`. That gives three guarantees, each tested:

- opening the screen, or any later rerun, makes no request;
- a failure records nothing, so a timeout cannot become a stored result;
- the previous valid plan survives a failed regeneration.

The screen reaches the AI layer lazily; `app.py` still imports no `ai` module.

### 2.5 The usability gate

The advisor rejects a basket containing an item that is not in the catalog, or not
offered for this room type. A *stored* basket could still be unusable — a reloaded
project, a changed room type — and the screen would then have said "no layout was
calculated" while offering a "Calculate the layout" button that produces nothing.

`_blocking_basket_findings` reuses `core.validation.validate_catalog_references`
(errors only) rather than restating the rule. When it reports anything, the screen
shows an error badge, the untouched basket and the findings, and offers no
placement button. The identifier is never silently rewritten.

### 2.6 The plan

`ui/diagram.py` gained a second drawing rather than reusing the illustrative room
diagram:

| Element | Source |
|---|---|
| Room boundary and dimensions | `RoomInput` (`width_cm` × `length_cm`) |
| Door and window | opening wall, offset and width |
| Furniture blocks | `PlacementOutcome.placed` only |
| Labels and sizes | each footprint's own `label`, `width_cm`, `depth_cm` |
| Legend | `plan_legend()` — placed furniture, door, window, room boundary |

The scale is derived once in `_plan_geometry`; block coordinates are converted
from centimetres and never recomputed. A test derives the expected pixel values
from the module's own documented rule and asserts an exact match, so the drawing
cannot quietly start inventing geometry.

The drawing is hand-written SVG (no Matplotlib), rendered inside
`theme.html_block`, and scaled with `width:100%`, so it fits a narrow viewport
without a horizontal scrollbar.

Status handling is explicit:

| Status | Badge | Plan | Score |
|---|---|---|---|
| `COMPLETE` | success | full validated layout | shown |
| `PARTIAL` | warning | placed copies only, labelled "Partial plan" | shown |
| `FAILED` | error | **not drawn** — "No plan drawn", with the reason | `None` by construction |

`_status_copy` is asserted to produce three distinct badges and three distinct
sentences, and the failure sentence never contains a placed count.

### 2.7 Presentation rules (§7)

- The score is labelled **"Quality heuristic, not a validity check."** Geometric
  validity is a separate tile reading "Valid" / "Not valid" and is decided by
  `SpatialValidation.is_valid` alone. A test asserts both labels are present.
- Blocking findings (`boundary_violations`, `overlaps`) and `warnings` are
  rendered in separate sections, blocking first, with the sentence "Warnings do
  not block the layout." A test asserts the ordering, so a warning cannot be
  filed as an error.
- Unplaced copies are named with the engine's own reason sentence, and a note
  states that they remain in the basket (so the budget still includes them)
  while not being in the room.
- The door/window clearance rules actually applied are stated in centimetres,
  with the consequence spelled out: blocking the doorway is an error, standing
  in the window band is a warning.
- The plan legend says the drawing is illustrative, not a construction or
  building-code drawing.

### 2.8 Materials (§8)

Materials get their own section. `MaterialRecommendation` has no price field, so
the screen states the absence per material — "Not priced: materials have no
catalog cost in this application." A test asserts the string appears once per
material, that no currency symbol or `TRY` appears in the section, and that the
model itself has no price-like field to render.

### 2.9 State (§9)

No new state system. `WorkflowState` gained one field
(`placement: PlacementOutcome | None`), stored and cleared together with
`spatial` under `DataKey.SPATIAL`. `PlacementStatus`, `PlacementOutcome`,
`PlacedFootprint`, `UnplacedItem` and `ScoreTerm` live in `models/schemas.py`
rather than `core` so that a result can be stored; `core.placement_engine`
imports `PlacementStatus` from there instead of defining a second enum.

Staleness comes from the existing dependency graph, not from screen logic:

- changing the concept clears furniture → spatial (`placement` and coordinates
  go with it);
- changing a room dimension clears spatial and strips coordinates;
- a failed AI call changes nothing.

---

## 3. Files created or modified

### Created

| File | Lines | Purpose |
|---|---|---|
| `ui/layout.py` | 114 | The engine seam: `analyse_layout`, `LayoutAnalysis`. |
| `ui/pages_plan.py` | 743 | The Design Plan screen. |
| `tests/test_ui_advisor_flow.py` | 1 058 | 28 screen tests, the 14 required scenarios. |
| `tests/test_ui_layout.py` | 229 | 11 engine-seam tests. |

### Modified

| File | Change |
|---|---|
| `models/schemas.py` | `FurniturePosition`; `positions` field; `_positions_never_exceed_quantity`; `PlacementStatus`, `PlacedFootprint`, `UnplacedItem`, `ScoreTerm`, `PlacementOutcome`; `__all__`. |
| `core/placement_engine.py` | `PlacementStatus` imported from `models` (local duplicate removed); `PlacementResult.to_outcome()`; `apply_placements` writes every placed copy. |
| `core/spatial_engine.py` | `_positioned_copies`; `build_footprints` copy-aware, reporting `unplaced_copies`. |
| `workflow/state.py` | `placement` field; `record_spatial(spatial, placement=None, placements=None)`; `_clear(SPATIAL)` strips coordinates; `_basket_requests`; `unplace_recommendation`. |
| `ui/ai_actions.py` | `recommend_furniture` wrapper (lazy `ai` import, unchanged error mapping). |
| `ui/references.py` | `load_catalog()`, `catalog_note()`. |
| `ui/diagram.py` | `placement_plan_svg`, `plan_legend`, `furniture_block_svg`; legend spacing fixed in both legends. |
| `ui/theme.py` | `warning_badge`, `error_badge`, `score_line`, plan CSS block. |
| `ui/session.py` | `SCREEN_PLAN`. |
| `ui/shell.py` | "Design Plan" added to `AVAILABLE_STAGES`. |
| `ui/pages_concepts.py` | Forward button now "Continue to the design plan". |
| `app.py` | Routes `SCREEN_PLAN` to `pages_plan.render`. |
| `tests/test_ui_presentation.py` | 12 plan-drawing tests added (22 → 34). |
| `tests/test_placement_engine.py` | Quantity write-back tests rewritten for `positions` (55 → 56). |
| `tests/test_spatial_engine.py` | `unplaced_copies` assertion (45 → 46). |
| `tests/test_ui_app.py`, `tests/test_ui_ai_flow.py` | Stage count and forward-button label. |

No file was deleted. No dependency was added.

---

## 4. The fourteen required scenarios

All fourteen are covered; the mapping table is in `TEST_REPORT.md` §4.

---

## 5. Realistic scenario outcome

400 × 520 cm living room, south door (x 60–150), north window (x 120–280), six
recommended items, no coordinates supplied — measured through
`ui.layout.analyse_layout` against the real catalog:

```text
status   complete          score 0.990954        median 70.5 ms (7 runs)
placed   6 / 6             unplaced 0            occupied 4.42 of 20.80 m²

boundary_fit 0.150/1.0  door_access 0.200/1.0  window_clearance 0.150/1.0
overlap_free 0.150/1.0  circulation 0.200/1.0  placement_quality 0.150/0.9397
```

Every `positions` list is length 1 for a quantity of 1, and the written positions
equal the drawn footprints exactly.

End-to-end screen probe (through `AppTest`, advisor stubbed at one call, the real
engines running):

| Check | Result |
|---|---|
| Screen reached | `plan`, one advisor call, 0 exceptions |
| Basket | sofa 1, coffee table 1, TV unit 1, **armchair 2**, floor lamp 1, bookshelf 1 |
| Stored `positions` | `1, 1, 1, 2, 1, 1` — the pair of armchairs keeps two distinct coordinates |
| Outcome | `COMPLETE`, score 0.990853, spatial `is_valid = True`, no warnings |
| Drawing | exactly one `<svg>`, seven blocks |
| Completion | `RECOMMENDATIONS` and `SPATIAL_VALIDATION` both complete |
| Rerun | advisor call count stays at 1 |

---

## 6. Known limitations

1. **Greedy, single-pass placement.** Inherited from Step 5A. Arises from the
   engine, not this step.
2. **Rectangles only.** A large rug is treated as solid furniture and is usually
   reported unplaced beside a full seating group.
3. **No front-face reasoning.** 180°/270° are not separate candidates, so the
   stored rotation is the one used rather than a preference.
4. **One layout, no alternatives.** The screen shows the best candidate. The
   engine computes several strategies; exposing a choice is not in V1.
5. **The quality score is a heuristic about walls, spacing and free floor.** It
   cannot judge sightlines, focal points or whether a room feels right. The
   interface says so, but the number is still only as good as the weighting.
6. **Materials are unpriced by design.** V1 has no material cost list, so the
   budget covers furniture only. The screen states this rather than estimating.
7. **The basket gate covers catalog references only.** It does not predict
   whether a valid basket will fit; that is what the placement engine is for, and
   a `FAILED` result is shown as a failure.
8. **Large rooms are slow.** 2000 × 2000 cm with 40 copies takes ~16 s in the
   engine. Realistic residential rooms take 0.05–0.21 s; the screen shows a
   spinner while it works.
9. **No responsive breakpoint testing in a real device.** The screen uses fluid
   widths, a flex-wrapping legend and a `width:100%` SVG, and was checked at
   desktop width and at a narrow viewport; no browser matrix was run.
10. **The evaluation and PDF stages are named but not built.** The screen states
    plainly that they are the next development stage.

---

## 7. Scope deviations

One, and it was analysed before it was made: **`models/schemas.py` and
`workflow/state.py` were modified**, which the step's own wording treated as a
change needing approval.

The justification is §5 of the brief, which forbids losing data or claiming
copies were placed when they were not. The data loss was demonstrated by a probe,
not assumed:

- the stored basket held zero coordinates while the plan showed seven pieces;
- `finalize()` assembles `ProjectResult.recommendations` from that basket, so the
  loss reached the final result;
- a quantity of two could not be expressed at all.

The alternatives were considered and rejected: merging copies into one coordinate
(fabricates geometry), dropping the second copy (loses requested furniture), or
storing the layout only in `PlacementOutcome` (leaves the persisted project
without it). The chosen extension is additive, defaults to empty, keeps every
existing field working, and touches no model outside
`FurnitureRecommendation`/`FurniturePosition`.

Nothing else deviates:

- no new dependency — the SVG is hand-written, so Matplotlib and ReportLab remain
  unused in this step;
- no new AI provider, model, endpoint or credential;
- no change to the four AI services or the prompt;
- no Git, commit, push or deployment;
- Design Evaluation, PDF, Turkish localisation, 3D, drag-and-drop and live pricing
  were not started.

---

## 8. Recommended next action

Await approval of Step 5B.

On approval, the remaining Phase 5 work is the Design Evaluation screen (the
fourth AI service is already implemented and live-validated in Step 3, but no
screen calls it), followed by wiring the budget analysis into the interface. Both
are prerequisites for the Phase 6 PDF, which needs a finalised `ProjectResult`.
