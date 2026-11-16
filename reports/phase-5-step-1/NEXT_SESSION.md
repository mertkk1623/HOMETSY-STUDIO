# Phase 5 / Step 1 — Next Session Handover

**Written:** 2026-11-14
**Purpose:** Resume work tomorrow without re-deriving context.

---

## 1. Exact Stopping Point

**Phase 5, Step 1 is complete in code and tests, and is awaiting user approval.**

Nothing is half-written. No file is in a broken or intermediate state. The full
test suite passes (**685/685**) and the Streamlit app still renders with zero
exceptions.

**Step 2 has not been started.** `app.py` is still the Phase 1 landing page and
imports nothing from `workflow`.

---

## 2. What Phase 5 Has Completed

| Step | Scope | Status |
|---|---|---|
| 1 | `workflow/` package: dependency table, workflow state, 127 tests | **Complete, awaiting approval** |
| 2 | Streamlit wiring — room and design preferences | Not started |

### Step 1 deliverables

| File | Lines | Purpose |
|---|---:|---|
| `workflow/__init__.py` | 20 | Package docstring + import-direction contract |
| `workflow/dependencies.py` | 255 | `DataKey`, `INVALIDATES`, `SOURCES`, `INPUT_KEYS`, `invalidated_by`, `depends_on` |
| `workflow/state.py` | 779 | `WorkflowState`, `WorkflowStep`, `STEP_ORDER`, `STEP_PREREQUISITES`, `STEP_LABELS`, errors, `guard`, `attempt`, `finalize`, `build_result`, `room_change_keys` |
| `tests/test_workflow_dependencies.py` | 291 | 35 tests, incl. 14 parametrised row assertions |
| `tests/test_workflow_state.py` | 1054 | 83 behaviour tests |
| `tests/test_workflow_integration.py` | 539 | 9 tests on the workflow ↔ AI seam |

**No existing file was modified.** `ai/*`, `core/*`, `models/*`, `app.py`,
`requirements.txt`, `opencode.json`, `.gitignore` are all untouched.

---

## 3. Baseline State to Resume From

```
685 passed in ~0.7s   (was 558 before this step; +127)
```

Per-file breakdown:

| File | Tests |
|---|---:|
| `test_ai_client.py` | 58 |
| `test_ai_config.py` | 30 |
| `test_ai_parsing.py` | 112 |
| `test_ai_prompt.py` | 38 |
| `test_ai_services.py` | 70 |
| `test_budget_engine.py` | 34 |
| `test_data_library.py` | 34 |
| `test_models.py` | 54 |
| `test_room_engine.py` | 48 |
| `test_spatial_engine.py` | 45 |
| `test_validation.py` | 35 |
| `test_workflow_dependencies.py` | 35 |
| `test_workflow_integration.py` | 9 |
| `test_workflow_state.py` | 83 |

Run with:

```powershell
cd "[PROJECT_ROOT]"
& ".venv\Scripts\python.exe" -m pytest -q
```

Python **3.13.18** in `.venv`. The global interpreter (3.15.2) must not be used.

---

## 4. The Public Surface of `workflow`

Resume by reading these signatures, not by re-reading the whole file.

```python
from workflow.dependencies import (
    DataKey,          # 14 keys: 6 inputs + 8 results
    INVALIDATES,      # Mapping[DataKey, frozenset[DataKey]] — the only rule table
    SOURCES,          # its exact inverse, built from it
    INPUT_KEYS,       # the six user-input keys
    DATA_KEY_ORDER,   # fixed ordering for stable reporting
    invalidated_by,   # (*changed) -> tuple[DataKey, ...], one hop, never a closure
    depends_on,       # (key) -> tuple[DataKey, ...]
)

from workflow.state import (
    WorkflowStep, STEP_ORDER, STEP_PREREQUISITES, STEP_LABELS,
    WorkflowState, room_change_keys,
    WorkflowError, PrerequisiteError, IncompleteWorkflowError, StepFailed,
)
```

`WorkflowState` methods:

| Kind | Methods |
|---|---|
| Inputs | `set_room`, `set_preferences`, `set_requirements`, `set_budget` |
| Results | `record_brief`, `record_concepts`, `select_concept`, `select_concept_by_name`, `record_recommendation`, `set_materials`, `record_spatial`, `record_budget_analysis`, `record_evaluation` |
| Running | `guard`, `attempt(step, produce, record)` |
| Views | `data_for`, `is_complete`, `completed_steps`, `next_step`, `is_finished`, `missing_prerequisites`, `outstanding_steps`, `as_recommendation` |
| Finalising | `build_result()` (does not store), `finalize()` (stores, completes) |

Every `set_*` / `record_*` returns `tuple[DataKey, ...]` — the keys it dropped.
The interface can use that return value to say *what* was reset and *why*.

---

## 5. Three Decisions a Future Session Must Not Undo

These are easy to "fix" into bugs. All three are pinned by tests.

1. **`INVALIDATES` is applied one hop, not transitively.**
   `invalidated_by()` unions the rows; it does not walk a closure. A closure
   would make a budget edit delete a still-correct spatial result, which the
   step brief explicitly forbids. Pinned by
   `test_invalidated_by_is_not_transitive` and
   `test_budget_does_not_invalidate_the_layout`.

2. **A retained result can be inert, and that is correct.**
   After a budget change the spatial result survives as data, but its furniture
   prerequisite is gone, so `is_complete(SPATIAL_VALIDATION)` is `False` and
   `next_step` returns to the brief. When the basket is re-recorded, the
   furniture edge clears the leftover. Pinned by
   `test_preserved_spatial_result_is_not_presented_as_current`.
   **UI consequence: always branch on `is_complete(step)`, never on
   `value is not None`.**

3. **`build_result()` and `finalize()` are different.**
   `build_result()` assembles without storing. `finalize()` stores a
   `ProjectResult` in `state.result` and completes step 10. Any later edit
   clears `state.result` through `_clear`, so a PDF can never describe a version
   of the project the user has already changed.

---

## 6. Known Issues and Carry-Over

### From Step 1

1. **No Streamlit integration.** No page imports `workflow`. `app.py` unchanged.
2. **`invalidation_log` grows unbounded.** UI explanation only; not an audit log.
3. **No serialisation.** No `to_dict`/`from_dict`. State is in-memory only, so
   session continuity across a Streamlit rerun is unproven.
4. **No concurrency handling.** One state per session assumed; V1 has no workers.
5. **`ProjectResult` cannot carry materials.** `recommendations` is
   `list[FurnitureRecommendation]` only — a Phase 1 model decision. Materials
   live in the state and need a separate path into the Phase 6 PDF.
6. **The table encodes the brief, not physics.** If Phase 6 finds that, say,
   ceiling height reaches the plan renderer, add a row *deliberately*, with a
   test — do not infer it at call time.

### Carried from Phase 4

7. **The four prompts have never reached the real provider.** Only Step 2 of
   Phase 4 made one live call (a compatibility probe). Concept generation at
   6000 output tokens is the truncation risk.
8. **Provider limits remain unverified**: output ceiling, context window,
   429 behaviour.

### Carried from Phase 2 (affects Phase 7)

9. **Mixed reference-image aspect ratios** — 4 styles ~0.51 portrait, 2 newer
   styles ~1.50, palettes 0.75 vs 1.17. Handle with fixed-ratio
   `object-fit: cover` cards.

---

## 7. Suggested Step 2 Scope

**Do not start this until the user approves Step 1.**

Wire only the deterministic half of the workflow into Streamlit:

- App shell with the step indicator driven by `WorkflowState.next_step`.
- **Room information page** — the form, `RoomInput` construction, findings from
  `core.validation.validate_room_input`, and a `set_room()` call.
- **Design preferences page** — style, palette, material preferences,
  requirements, budget; `core.validation.validate_inputs`; the four `set_*`
  calls.
- State kept in `st.session_state` under one key; a helper module (e.g.
  `ui/state.py` or `pages/…`) that owns the `WorkflowState` instance.
- When a step is re-entered after an edit, show `invalidation_log` output so the
  user understands what was cleared.

Explicitly **out of scope for Step 2**: any AI call, any progress beyond step 3,
the 2D plan, the PDF.

The first UI file should be a thin adapter with no business rules in it — all
rules already live in `workflow` and `core`.

---

## 8. First Action for the Next Session

```powershell
cd "[PROJECT_ROOT]"
& ".venv\Scripts\python.exe" -m pytest -q          # expect: 685 passed
& ".venv\Scripts\python.exe" -c "import workflow.state as s; print(s.STEP_ORDER)"
```

If those two commands agree with §3, the workspace is exactly where this
handover says it is, and Step 2 can begin on approval.

---

## 9. Environment Facts Worth Re-Learning

- `DEPLOY_API_KEY` is present in the process environment and verified absent
  from every project file. Never print it, never write it to disk.
- No Git repository exists. Nothing has been committed, pushed or deployed.
- `Select-String` pipelines can return exit code 1 even on success; check
  Python script exit codes separately (`raise SystemExit(0)` + `$LASTEXITCODE`).
- `models/schemas.py:228` has a pre-existing line over 88 characters. Not
  introduced by Phase 4 or 5; leave it alone unless the file is being edited for
  another reason.
- `core.spatial_engine.validate_recommendations` returns
  `(PlacementReport, ...)`; use `to_spatial_validation()` to get the stored
  `SpatialValidation`. Passing the report to `record_spatial` fails.
- `core.validation.validate_result_consistency` takes the `FurnitureItem`
  catalog, not `FurnitureRecommendation`s.
