# Phase 5 / Step 5A — Completion Report

**Project:** Hometsy — Room Intelligence Studio
**Step:** 5A — Deterministic furniture placement engine
**Date:** 2026-11-15
**Status:** Implementation complete. Stopped, awaiting approval.

---

## 1. Objective

Place the furniture recommended by the AI Design Advisor into the room geometry
using Python only, deterministically, and have the existing spatial engine decide
whether the resulting layout is acceptable. AI continues to make no geometric
decisions; the placement engine makes no validity decisions.

---

## 2. Implementation summary

### 2.1 Responsibility split

| Question | Answered by |
|---|---|
| Where could each item go? | `core/placement_engine.py` (new) |
| Is this layout acceptable? | `core/spatial_engine.py` (unchanged) |
| Which items could not be placed, and why? | `core/placement_engine.py` |
| Are the catalog references valid? | `core/validation.py` (unchanged) |

No geometry rule was re-implemented. Candidate filtering *reuses* the spatial
engine's primitives (`rect_inside_room`, `rects_overlap`,
`opening_clearance_rect`, `effective_size_cm`, `make_footprint`), and the chosen
layout is validated by `validate_placement` and converted with
`to_spatial_validation` and `placement_findings`. The spatial engine's report is
the only statement about validity that leaves the new module.

### 2.2 Inputs

- Room dimensions and door/window geometry, in the existing coordinate system
  (origin south-west; `width_cm` along +x, `length_cm` along +y).
- Furniture recommendations; `position_x_cm`/`position_y_cm` are ignored
  entirely, so the advisor's `null` coordinates are normal input.
- Catalog dimensions; every footprint uses the catalog's real `width_cm` and
  `depth_cm`.
- Selected concept context: not consumed. The concept influences *which* items
  the advisor recommends, and the engine has no field for it. Making it affect
  geometry would be an invented requirement, so it was not added.

### 2.3 Candidate generation

For each of four wall-preference strategies (`north-first`, `east-first`,
`south-first`, `west-first`):

1. Items are sorted by footprint area, largest first — the items with the fewest
   legal positions are placed while the room is emptiest. Ties break on
   `item_id`, so the order is total and stable.
2. Each copy is offered every candidate position in a fixed order: wall anchors
   at 20 cm steps along each wall in the strategy's wall order, then an interior
   grid at 40 cm steps. Both ends of every span and the centre are always
   included, so an item can sit flush in a corner or exactly mid-wall.
3. Only rotations that the geometry supports are generated: the requested angle
   and its quarter turn, both normalised through `normalize_rotation`. A quarter
   turn is skipped when it does not fit the room.
4. A candidate is rejected outright if it leaves the room, touches the door
   clearance zone, or overlaps an already-placed footprint. It is never merely
   penalised.

All steps are constants, so identical inputs produce identical candidates in an
identical order, which the tests assert directly.

### 2.4 Scoring

Layout criteria and weights (sum 1.0):

| Criterion | Weight | Why |
|---|---|---|
| `boundary_fit` | 0.15 | Legality. Kept in the score so a generation bug lowers a candidate instead of hiding behind it. |
| `door_access` | 0.20 | The doorway is the only mandatory circulation point; a layout that crowds it is worse than one that does not. |
| `window_clearance` | 0.15 | Daylight matters, but the existing engine classifies obstruction as a warning, so this is scored, not forbidden. |
| `overlap_free` | 0.15 | Legality, scored for the same reason as `boundary_fit`. |
| `circulation` | 0.20 | Free floor is the second functional requirement after the doorway. Zero below 25 % free, full marks at 55 %. |
| `placement_quality` | 0.15 | Mean per-item quality: wall anchoring, spacing, position along the wall. |

While *generating*, a per-item figure is used with three additional terms:
`anchor` (the item's longest edge truly lies on a wall), `position` (how central
the item is along that wall, so corners are not chosen by default) and
`wall_preference` (a small tiebreaker for the strategy's wall). Seating, storage
and sleeping weight anchoring heavily; tables, lighting and decor are scored on
centrality, because a coffee table belongs in the middle of the room.

The layout score itself is deliberately **strategy-neutral**:
`QUALITY_WEIGHTS` and `FREE_STANDING_QUALITY_WEIGHTS` contain no
`wall_preference` term, so one layout can never win merely because a different
wall order was used to build it. A test asserts this.

Candidates are ranked by placed-copy count, then score, then strategy order.

### 2.5 Validation

The best candidate's footprints go through `core.spatial_engine.validate_placement`
and `to_spatial_validation`. If that report contains any error, the result is
`FAILED` and `candidate` is `None`, so a rejected layout cannot be drawn. The same
report is exposed as `core.validation` findings so the interface can merge it with
room, catalog and budget findings without a second conversion.

### 2.6 Failure handling

Three distinct statuses, no silent repair anywhere:

| Status | Meaning | `candidate` |
|---|---|---|
| `COMPLETE` | Every requested copy placed, validator accepts | set |
| `PARTIAL` | Some copies placed and validated, others not | set (validated), plus a `partial_placement` note |
| `FAILED` | Nothing placed, or the validator rejected the best candidate | `None` |

Unplaced items are reported as `UnplacedFurniture` with a `count`, a
`reason_code` (`unknown_catalog_item`, `unsupported_rotation`,
`no_valid_position`) and a sentence naming the item, its dimensions and the
obstacle ("does not fit inside the 100 × 150 cm room", "every candidate
overlapped the door clearance zone …, although 1.20 m² of floor is still free").
Partially placed layouts are never reported as success.

### 2.7 Write-back

`apply_placements(recommendations, result)` is the single place a coordinate is
written onto `FurnitureRecommendation`, so the persisted geometry is exactly the
geometry that was validated. Unplaced recommendations keep `None`; no coordinate
is invented. The existing Phase 3 path (`validate_recommendations`) then agrees
with the engine's own verdict — asserted by a test.

---

## 3. Files created or modified

| File | Change |
|---|---|
| `core/placement_engine.py` | **New** — 1 340 lines (878 code, 215 docstring, 46 comment, 229 blank). |
| `tests/test_placement_engine.py` | **New** — 55 tests, 1 130 lines. |
| `core/__init__.py` | Docstring updated to mention `core.placement_engine` and the propose/validate split. |

Nothing else was touched. `core/spatial_engine.py`, `core/room_engine.py`,
`core/validation.py`, `models/`, `workflow/state.py`, `ai/`, `ui/`, `app.py` and
every data file are unchanged.

---

## 4. The twelve required scenarios

All twelve are covered; the mapping is in `TEST_REPORT.md` §3.

## 5. Realistic scenario outcome

400 × 520 cm living room, south door (x 60–150), north window (x 120–280),
six recommended items and **no coordinates** supplied:

```text
status   complete          strategy north-first      score 0.990954
boundary_fit 1.000 · door_access 1.000 · window_clearance 1.000
overlap_free 1.000 · circulation 1.000 · placement_quality 0.9397

Three-seat sofa   rot  90   x 310-400   y 150-370    90 x 220
Coffee table      rot   0   x 150-250   y 240-300   100 x  60
TV unit           rot  90   x   0- 40   y 240-420    40 x 180
Armchair          rot   0   x 240-320   y   0- 80    80 x  80
Floor lamp        rot   0   x 240-280   y 160-200    40 x  40
Bookshelf         rot   0   x 280-370   y 485-520    90 x  35
```

- All six items placed; no unplaced items, no errors, no warnings.
- Occupied floor 4.42 m² of 20.8 m² (21.2 %), so circulation is comfortable.
- The sofa sits against the east wall with its long edge, the TV unit against
  the west wall facing it, the coffee table between them, the armchair on the
  south wall well clear of the doorway, the bookshelf on the north wall clear of
  the window, and the floor lamp beside the sofa.
- Writing the coordinates back and running the existing Phase 3 path
  (`validate_recommendations`) reproduces the identical footprints with
  `is_valid = True`, and the `unplaced_item` warning that all four earlier AI
  steps produced is gone because the coordinates now exist.
- 68.5 ms (median of five runs) for the whole six-item placement on this machine.

---

## 6. Known limitations

1. **One stored position per recommendation.** The engine places every copy
   (e.g. four dining chairs), but `FurnitureRecommendation` holds a single
   `position_x_cm`/`position_y_cm`, so the write-back collapses them and the
   Phase 3 validator reports `quantity_collapsed`. This is a data-model
   limitation outside this step's scope; it is asserted by a test so it cannot
   change silently. Items with `quantity = 1` — everything the advisor currently
   returns in practice — are unaffected.
2. **Greedy, single-pass placement.** An early item that takes a good position is
   never reconsidered. The four strategies mitigate this without searching the
   whole space; a better global arrangement may exist for some inputs.
3. **Rectangles only.** A large area rug is treated as solid furniture, so it is
   usually reported unplaced next to a full seating group.
4. **No front-face reasoning.** A half turn is geometrically identical to the
   requested orientation in this model, so 180°/270° are not generated as
   separate candidates. The stored rotation is the one actually used.
5. **Wall anchoring prefers the longest edge.** Correct for sofas, beds and
   storage; wrong for a deliberately free-standing desk.
6. **Placement quality is a heuristic**, not a design judgement: the engine
   cannot reason about sightlines, focal points or a room's front face.
7. **Room-type suitability is not checked here.** That is
   `core.validation.validate_catalog_references`' job; the engine places whatever
   the catalog resolves.
8. **Large-room cost.** A 2000 × 2000 cm room with 40 copies takes ~16.4 s
   because the grid grows with the room. Realistic residential rooms (up to
   ~800 × 800 cm) take 0.05–0.21 s. No V1 input reaches the slow case.
9. **Not wired into the workflow yet.** `workflow/state.py` was to be left
   unchanged, so nothing calls `place_furniture` in the running application.
   That connection belongs to a later step.

---

## 7. Scope deviations

None. Specifically:

- No new dependency (`core/placement_engine.py` imports only the standard library
  and existing project modules).
- No Streamlit work, no PDF work, no changes to the AI services, the data models,
  `workflow/state.py` or the existing geometry engine.
- The selected concept is *not* used as a placement input, because the approved
  models carry no field through which it could legitimately affect geometry.
- `core/__init__.py` needed a docstring update only because it enumerates the
  package's modules.

## 8. Recommended next action

Await approval of Step 5A. When approved, the natural next step is to connect the
engine to the workflow: call `place_furniture` when recommendations exist,
persist the write-back `FurnitureRecommendation` list, record
`SpatialValidation` through the existing `state.record_spatial`, and show the
unplaced items and the score breakdown on the layout screen.
