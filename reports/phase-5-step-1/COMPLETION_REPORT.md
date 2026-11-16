# Phase 5 / Step 1 — Completion Report

**Project:** Hometsy — Room Intelligence Studio
**Phase:** 5 — Complete Application Workflow
**Step:** 1 — Workflow State Management
**Date:** 2026-11-14
**Status:** Implementation and tests complete; awaiting approval before Step 2.

---

## 1. Objective

Create the layer that coordinates the end-to-end workflow: hold the user's input
and the results derived from it, track which steps are complete, refuse to run a
step whose prerequisites are missing, and make sure a result is discarded when
the input it came from changes.

---

## 2. Completed Work

1. **`workflow/dependencies.py`** — the one and only definition of what becomes
   stale when something changes, plus the `DataKey` vocabulary.
2. **`workflow/state.py`** — `WorkflowState`, the ten `WorkflowStep` values,
   prerequisite rules, ten guarded `record_*`/`set_*` methods, `attempt()` as the
   bridge to the AI layer, `finalize()` and `build_result()`.
3. **`workflow/__init__.py`** — package documentation and the dependency
   direction the tests enforce.
4. **Tests** — 127 new tests across three files, all passing.

No existing module was modified. `ai/*`, `core/*`, `models/*`, `app.py`,
`requirements.txt` and `opencode.json` are untouched.

---

## 3. Files Created and Modified

### Created

| File | Lines | Purpose |
|---|---:|---|
| `workflow/__init__.py` | 20 | Package docstring and import-direction contract |
| `workflow/dependencies.py` | 255 | `DataKey`, `INVALIDATES`, `SOURCES`, `invalidated_by`, `depends_on` |
| `workflow/state.py` | 779 | `WorkflowState`, `WorkflowStep`, prerequisite rules, mutation and finalisation |
| `tests/test_workflow_dependencies.py` | 291 | 35 tests on the dependency table |
| `tests/test_workflow_state.py` | 1054 | 83 tests on state behaviour |
| `tests/test_workflow_integration.py` | 539 | 9 tests on the workflow ↔ AI seam |
| `reports/phase-5-step-1/COMPLETION_REPORT.md` | — | This report |
| `reports/phase-5-step-1/TEST_REPORT.md` | — | Test evidence |
| `reports/phase-5-step-1/NEXT_SESSION.md` | — | Handover notes |

### Modified

None. This step is purely additive.

---

## 4. The Workflow

Ten steps, in the order the approved brief defines them:

| # | Step | Prerequisites |
|---:|---|---|
| 1 | Room information | — |
| 2 | Design preferences and requirements | Room information |
| 3 | Brief analysis | Room information, design preferences |
| 4 | Concept generation | Brief analysis |
| 5 | Concept selection | Concept generation |
| 6 | Furniture and material recommendations | Concept selection |
| 7 | Spatial validation | Recommendations |
| 8 | Budget analysis | Recommendations |
| 9 | Design evaluation | Spatial validation, budget analysis |
| 10 | Final project result | Design evaluation |

Steps 7 and 8 are siblings, not a chain: once a basket exists, a layout can be
measured and a total worked out in either order. A test exercises both orders.

### Completion is derived, not stored

There is no `completed_steps` flag to drift out of sync. `is_complete(step)` asks
two questions: does this step's own data exist, and are all its prerequisites
complete? Invalidation therefore needs no bookkeeping — clearing data is enough.

A consequence worth stating: a result can survive a change without being
*presented* as current. When the budget changes, the approved table keeps the
spatial result (geometry does not depend on money), but the furniture it
described is cleared, so `is_complete(SPATIAL_VALIDATION)` is false and
`next_step` returns to the brief. The retained layout is inert until the basket
is regenerated — at which point the furniture edge fires and clears it properly.
`test_preserved_spatial_result_is_not_presented_as_current` pins this down.

---

## 5. Dependency Invalidation

### One table, applied exactly

`workflow/dependencies.py` holds `INVALIDATES: Mapping[DataKey, frozenset[DataKey]]`,
transcribed one row per key from the step brief. Nothing else in the application
restates these rules; the state module only calls `invalidated_by()`.

| Changed | Invalidated |
|---|---|
| Room dimensions | Brief, concepts, selection, furniture, materials, spatial, budget, evaluation |
| Room type | same as above |
| Door / window | Brief, concepts, selection, furniture, materials, spatial, evaluation — **not** budget |
| Design preferences | Brief, concepts, selection, furniture, materials, evaluation |
| User requirements | same as above |
| Budget | Brief, concepts, furniture, materials, budget analysis, evaluation — **not** selection, **not** spatial |
| Brief | Concepts, selection, furniture, materials, evaluation |
| Concepts | Selection, furniture, materials, evaluation |
| Selected concept | Furniture, materials, spatial, budget, evaluation |
| Furniture | Spatial, budget, evaluation — **not** materials |
| Materials | Budget, evaluation — **not** spatial |
| Spatial | Evaluation |
| Budget analysis | Evaluation |
| Evaluation | nothing (terminal) |

Three asymmetries are deliberate and each is tested:

1. **Openings do not reach the budget.** A door width does not change what a
   sofa costs.
2. **The budget does not reach the layout.** A cheaper basket is still the same
   room with the same furniture already measured. A transitive closure would
   delete that layout for no reason.
3. **Furniture does not reach materials.** They arrive in one
   `DesignRecommendation` but decay separately; materials carry no geometry.

### Why the table is not walked to a closure

The step brief requires that only affected results are cleared and that
independent valid results survive. A closure walk (budget → concepts → selection
→ spatial) would violate the second condition by discarding a still-correct
layout. The chain re-forms on its own instead: a leftover result whose
prerequisite is gone is not usable, because completion is derived from data plus
prerequisites — and when that step runs again, its own edge clears the leftover
at exactly the right moment. `test_invalidated_by_is_not_transitive` documents
this explicitly so it cannot change by accident.

### A room change is inspected, not assumed

`room_change_keys()` compares the two `RoomInput` values and reports which facets
moved: type, dimensions, openings. Renaming the room therefore invalidates
nothing, and moving a door does not touch the budget.

---

## 6. State Management

### Structure

```
WorkflowState
├── inputs      room, preferences, requirements, budget
├── results     brief, concepts, selected_concept,
│               furniture, materials, color_direction, design_rationale,
│               spatial, budget_analysis, evaluation
├── result      the finalised ProjectResult (only after finalize())
└── invalidation_log   what was cleared and why (for the UI, never for decisions)
```

### Rules enforced

| Requirement | How |
|---|---|
| A step cannot run before its prerequisites | `guard()` on every `record_*`; `PrerequisiteError` names the missing step |
| Completed steps are trackable | `completed_steps`, `next_step`, `is_finished`, `outstanding_steps()` |
| Missing/invalid steps are detectable | `missing_prerequisites(step)` |
| Re-running a step is controlled | `guard()` plus an idempotence check: an identical value is a no-op |
| Old AI results never mix with new input | Invalidation on every accepted change |
| A failed AI call is never stored | `attempt()` wraps the failure in `StepFailed` before any write |
| State matches the existing Pydantic models | It stores `DesignBrief`, `ConceptCollection`, `DesignConcept`, `FurnitureRecommendation`, `MaterialRecommendation`, `SpatialValidation`, `BudgetAnalysis`, `DesignEvaluation`, `ProjectResult` as-is |

### Why furniture and materials are stored separately

They arrive together in `DesignRecommendation`, but `INVALIDATES` gives them
different dependents. Keeping one field would force both to be dropped together,
so a material swap would needlessly discard a valid layout. The state stores the
parts plus the narrative, and `as_recommendation()` rebuilds the model when the
UI or the evaluator needs one.

### The AI bridge

`attempt(step, produce, record)` is the whole integration point:

```python
state.attempt(
    WorkflowStep.BRIEF_ANALYSIS,
    lambda: analyze_brief(config, room, prefs, reqs, budget),
    state.record_brief,
)
```

The state never imports `ai`, never touches credentials, and never performs
HTTP. If `produce()` raises — timeout, truncation, failed correction — the state
is untouched and `StepFailed` carries the original exception as its cause.

### Finalisation is its own step

`build_result()` assembles a `ProjectResult` without storing it; `finalize()`
stores it and completes the workflow. Keeping them apart means "the data is all
there" and "the report has been produced" are different facts — and any later
edit clears the stored report, so a PDF can never describe a previous version of
the project.

---

## 7. Architectural Boundaries

| Constraint | Status |
|---|---|
| Independent of Streamlit | No `streamlit` import; asserted by tests |
| Does not re-implement AI services | No `ai` import at all; results arrive through callables |
| No HTTP | Asserted by tests |
| No re-implemented geometry or budget arithmetic | No arithmetic at all; the module contains no `Decimal(` call, asserted by test |
| Existing AI and core modules unchanged | Yes |
| No new dependency | `requirements.txt` untouched |
| No database | Nothing persisted |
| No Git, commit, push, deploy | The directory is still not a Git repository |
| No Streamlit UI work | `app.py` unchanged |

---

## 8. Known Limitations

1. **Not wired to the interface yet.** No page imports `workflow`; `app.py` is
   still the Phase 1 landing page. Session State integration is Step 2.
2. **`invalidation_log` grows without bound.** It is a list on the state object,
   cleared only by discarding the state. Fine for a session-sized workflow; it
   is not a durable audit trail and must not be treated as one.
3. **The table is exact, so a surviving result can be inert.** This is by design
   and tested, but it does mean the UI must branch on `is_complete(step)` rather
   than "is this value not None". A page that only checks for `None` would show a
   stale layout as current.
4. **Concurrency is not addressed.** One state object is assumed to be owned by
   one session. There is no locking, because Streamlit reruns are sequential and
   V1 has no background workers.
5. **No serialisation.** `WorkflowState` is a plain dataclass holding Pydantic
   models, so it could be dumped, but no `to_dict`/`from_dict` exists yet. A
   reload story would need one; V1 keeps state in memory.
6. **`ProjectResult` cannot express material recommendations.** The approved
   model carries `recommendations: list[FurnitureRecommendation]` only. Materials
   live in the state and reach the PDF through a separate path in Phase 6. This
   is a pre-existing Phase 1 model decision, not something this step changes.
7. **Step 6 remains a single step.** "Recommendations" covers furniture and
   materials together, matching the brief's numbering; the two results are
   tracked separately underneath.
8. **The dependency table encodes the brief, not physics.** If Phase 6 reveals
   that, say, the ceiling height reaches the plan renderer, a row must be added
   deliberately — with a test — rather than inferred at call time.

---

## 9. Deviations and Decisions Requiring Note

1. **The table is applied as written, not transitively.** Explained in §5; it is
   required by the "do not needlessly delete independent valid results" rule.
2. **`FINAL_RESULT` is a real step backed by a stored `ProjectResult`**, rather
   than a derived "everything is present" flag. Without this, step 10 could
   never be the next step and the workflow could never be *finished*, only
   *complete*. This adds one field to the state and one method, `finalize()`.
3. **`requirements` is included in the brief's and concepts' invalidation sets**,
   matching the brief's own row. Requirements are also an input to the advisor
   prompt, so they reach furniture and materials too — the table already says so.
4. **Materials are separated from furniture inside the state.** The approved
   `DesignRecommendation` model is unchanged; the state simply keeps the pieces
   apart so their different dependents can be honoured.
5. **`invalidation_log` was added** so the interface can explain a reset rather
   than silently emptying a panel. It is excluded from `repr` and never consulted
   when deciding what to clear.

---

## 10. Recommended Next Action

Review this step. If approved, Phase 5 Step 2 can wire the deterministic half of
the workflow into Streamlit — room setup and design preferences — calling
`core.room_engine` and `core.validation` through `WorkflowState`, with no AI
involved. That proves the state layer against a real interface before any
provider call is added.
