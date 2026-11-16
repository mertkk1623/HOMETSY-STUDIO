# Phase 5 / Step 2 — Next Session Handover

**Written:** 2026-11-15
**Purpose:** Resume work without re-deriving context.

---

## 1. Exact Stopping Point

**Phase 5, Step 2 is complete in code and tests, and is awaiting user approval.**

Nothing is half-written. No file is in a broken or intermediate state. The full
test suite passes (**801/801**), and the application was driven end to end in a
real browser on a live `streamlit run app.py`.

**Step 3 has not been started.** No AI call is reachable from the application:
`app.py` does not import `ai`, and a test asserts that in a child process.

The machine was **not** shut down (the user cancelled that request). No Git
operation of any kind was performed; there is still no repository.

---

## 2. Where Phase 5 Stands

| Step | Scope | Status |
|---|---|---|
| 1 | `workflow/` package: dependency table, workflow state, 127 tests | **Complete, approved** |
| 2 | Deterministic Streamlit workflow: room + preferences + review, 116 tests | **Complete, awaiting approval** |
| 3 | AI brief analysis, concept generation and selection | Not started |

### Step 2 deliverables

| File | Lines | Purpose |
|---|---:|---|
| `ui/__init__.py` | 19 | Package documentation |
| `ui/theme.py` | 433 | Design tokens, the only stylesheet, HTML helpers |
| `ui/commits.py` | 407 | Pure widget value → validated model builders |
| `ui/session.py` | 345 | Session-state adapter around `WorkflowState` |
| `ui/pages_preferences.py` | 329 | Style, palette, requirements and budget screen |
| `ui/pages_room.py` | 301 | Room information screen |
| `ui/shell.py` | 188 | Stage strip, brand line, flash and issue rendering |
| `ui/references.py` | 177 | Local style/palette reference library loader |
| `ui/pages_review.py` | 172 | Input review and validation findings |
| `ui/pages_landing.py` | 170 | Landing page |
| `ui/diagram.py` | 162 | Illustrative SVG room diagram + legend |
| `app.py` (rewritten) | 70 | Screen router |

Tests added: `tests/test_ui_commits.py` (40), `tests/test_ui_session.py` (22),
`tests/test_ui_app.py` (32), `tests/test_ui_presentation.py` (22).

**No existing file was modified** apart from `app.py`. `ai/*`, `core/*`,
`models/*`, `workflow/*`, `data/*`, `.streamlit/config.toml`, `requirements.txt`
and every pre-existing test are untouched.

---

## 3. Baseline State to Resume From

```
801 passed in ~10s   (was 685 before this step; +116)
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
| `test_ui_app.py` | 32 |
| `test_ui_commits.py` | 40 |
| `test_ui_presentation.py` | 22 |
| `test_ui_session.py` | 22 |
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

## 4. The `ui` Public Surface

Resume by reading these signatures, not by re-reading whole files.

```python
from ui import session, shell, commits, theme, diagram, references

session.STATE_KEY        # "hm_workflow_state" — the whole project
session.SCREEN_KEY       # "hm_screen"
session.ENTERED_KEY      # "hm_workflow_entered"
session.FLASH_KEY        # "hm_flash"
session.GENERATION_KEY   # "hm_generation"
session.WIDGET_PREFIX    # "hmw_"
session.SCREEN_ORDER     # ("room", "preferences", "review")
session.SCREEN_TITLES

session.get_workflow()          # create-or-reuse; never a new state per rerun
session.has_workflow()          # no side effect
session.current_screen() / session.go_to(screen) / session.enter_workflow() / session.leave_workflow()
session.set_flash(msg, tone=) / session.take_flash()
session.invalidation_message(dropped, *, previously_present=None)
session.present_keys(state)
session.reset_workflow()
session.seed(name, value) / session.widget_key(name) / session.value_of(name, fallback)
session.inputs_are_complete()

commits.build_room(**kw) / build_preferences(...) / build_requirements(...) / build_budget(...)
commits.Outcome(value, issues, warnings) with .is_ok
commits.issues_from_validation_error(error, fallback_label=...)
commits.room_summary_rows(room) / format_money(amount, currency) / clean_entries(...)
commits.overall_warnings(room, preferences, requirements, budget)
```

`shell.STAGES` maps the five user-facing stages onto the ten workflow steps;
`shell.AVAILABLE_STAGES` currently holds only `{"Room Setup", "Design
Preferences"}`. Adding a stage to that set is the visible change Step 3 must
make.

---

## 5. Decisions a Future Session Must Not Undo

All are pinned by tests in `tests/test_ui_*.py`.

1. **One central session key.** The whole project is `hm_workflow_state`. Do not
   split it into per-field keys — that reintroduces hand-written invalidation,
   which is exactly what Step 1 removed.

2. **`invalidation_message(dropped, previously_present=...)`.** `None` means
   "do not filter" (report the rule table). A set — *including an empty one* —
   restricts the message to what the user actually lost. A truthiness check here
   was a real bug that made the first save claim earlier results were cleared,
   so the distinction is deliberate. Pinned by
   `test_invalidation_message_says_nothing_was_lost_when_nothing_existed`.

3. **The advisory findings are not stored.** `ui/pages_review.py` recomputes
   them with `core.validation.validate_inputs` from the stored models. Storing a
   copy at commit time produced every warning twice on the review screen.

4. **Room and preferences are forms with explicit submit.** A live widget would
   commit a partial room on every keystroke and clear the user's downstream
   work. Do not "improve" these into live inputs.

5. **Freshness is `is_complete(step)`.** No screen may test `value is not None`.
   A retained result whose prerequisite is gone is inert, not current.

6. **`app.py` must not import `ai`.** `test_the_whole_workflow_runs_without_importing_the_ai_layer`
   runs the full workflow in a child process and asserts `sys.modules` contains
   no `ai` entry. When Step 3 wires the AI, it must call
   `WorkflowState.attempt()` from a page module — not import `ai` into the
   router, unless the test's intent is revisited **deliberately**.

7. **Only `ui/` imports Streamlit.** `workflow/` must stay framework-free;
   `test_ui_package_is_the_only_streamlit_importer` enforces it.

---

## 6. Known Issues and Carry-Over

### From Step 2

1. **No screenshots.** The browser session has no visible desktop window, so the
   screenshot tool refuses to run. Rendering was verified through live page text.
   `docs/screenshots/` is still empty — that is a Phase 9 task.
2. **The four AI prompts have still never reached the real provider.** This step
   makes no AI call by design, so the Phase 4 carry-over stays open.
3. **The step counter mixes granularities.** The header says "2 of 10 steps
   complete" while the strip above it shows five stages. Accurate but slightly
   awkward; worth revisiting when later stages exist.
4. **The budget widget caps at 10,000,000 TRY.** The model has no upper bound; the
   widget does, to stay usable.
5. **Material preferences and functional requirements are free text.** No
   normalisation beyond trim and case-insensitive de-duplication, and no link to
   the furniture catalog — intentional for this step.
6. **In-memory only.** A browser refresh starts a new project. Within approved V1
   scope (no persistence, no auth), but it means no recovery after reload.
7. **Mixed reference-image aspect ratios** (Phase 2 carry-over) are fitted into a
   4:3 frame with `object-fit: cover`, so some source images are cropped.

### Carried from Phase 4 / Step 1

8. **Provider limits remain unverified**: output ceiling, context window, 429
   behaviour. Concept generation at 6000 output tokens is the truncation risk.
9. **`ProjectResult` cannot carry materials.** Materials live in the state and
   need a separate path into the Phase 6/7 PDF.
10. **`invalidation_log` grows unbounded.** UI explanation only, not an audit log.

---

## 7. Suggested Step 3 Scope

**Do not start this until the user approves Step 2.**

Phase 5 / Step 3 — *AI Brief Analysis and Concept Generation*:

- **First task, before any screen work:** send one probe per prompt to
  `deepseek-ai/deepseek-v4.1-flash-1017` and record real latency, token usage and
  truncation behaviour. Concept generation at 6000 tokens is the known risk, and
  every later screen depends on that answer.
- Wire `workflow.attempt(BRIEF_ANALYSIS, ...)` and
  `attempt(CONCEPT_GENERATION, ...)` to `ai.brief_analyzer` and
  `ai.concept_generator`.
- A concept screen showing three concepts, with selection through
  `select_concept_by_name`, and a working "generate again" path that invalidates
  correctly.
- Add `"Design Concepts"` to `shell.AVAILABLE_STAGES` only when the stage really
  works end to end.
- Introduce an API-key boundary in the UI layer (`st.secrets` as fallback for
  `DEPLOY_API_KEY`) — the AI modules must never import Streamlit.

Explicitly **out of scope for Step 3**: furniture recommendations, spatial
validation, budget analysis, evaluation, the 2D plan and the PDF.

---

## 8. First Action for the Next Session

```powershell
cd "[PROJECT_ROOT]"
& ".venv\Scripts\python.exe" -m pytest -q          # expect: 801 passed
& ".venv\Scripts\python.exe" -c "from workflow.state import STEP_ORDER; print(STEP_ORDER)"
```

If both agree with §3, the workspace is exactly where this handover says it is.

---

## 9. Environment Facts Worth Re-Learning

- `DEPLOY_API_KEY` is present in the process environment and verified absent from
  every project file. Never print it, never write it to disk.
- `Select-String` pipelines can return exit code 1 even on success; check Python
  script exit codes separately.
- **Streamlit 1.67.0 / AppTest specifics:**
  - Form submit keys are `FormSubmitter:hm_room_form-Save room information` and
    `FormSubmitter:hm_preferences_form-Save preferences and budget`.
  - `set_value` on a widget **inside a form** does not survive an intermediate
    `run()`. Set every value, then submit.
  - `st.multiselect(options=[], accept_new_options=True)` must be seeded through
    `st.session_state` before the widget; `default=` raises.
  - `AppTest.from_function` extracts the function's source, so closures are not
    captured — import inside the script body.
- Base page colours live in `.streamlit/config.toml`, not in `APP_CSS`
  (`ui/theme.py` holds only the scoped rules).
- `models/schemas.py:228` has a pre-existing line over 88 characters. Not
  introduced by Phase 4 or 5; leave it unless editing that file for another
  reason.
- `core.spatial_engine.validate_recommendations` returns
  `(PlacementReport, ...)`; use `to_spatial_validation()` before
  `record_spatial`. Passing the report fails.
- `WorkflowState` method names: `record_recommendation(DesignRecommendation)`,
  `select_concept_by_name`, `record_spatial`, `record_budget_analysis`,
  `record_evaluation`. There is no `record_furniture`, `record_selection` or
  `record_recommendations`.
- `MaterialRecommendation` fields: `name`, `category`, `color_direction`,
  `rationale`, `quantity_note`.
