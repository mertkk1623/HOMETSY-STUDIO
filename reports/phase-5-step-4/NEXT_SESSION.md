# Phase 5 / Step 4 — Next Session Handover

**Project:** Hometsy — Room Intelligence Studio
**Written at the end of:** Phase 5 Step 4 — AI Brief Analysis & Concept Generation UI
**Date:** 2026-11-15
**Status:** Step 4 complete. Implementation stopped, awaiting approval.

---

## 1. Read these first

In this order:

1. `PROJECT_BRIEF.md`
2. `TECHNICAL_ARCHITECTURE.md`
3. `DESIGN_SYSTEM.md`
4. `DEVELOPMENT_PLAN.md`
5. `AGENTS.md`
6. `reports/phase-5-step-4/COMPLETION_REPORT.md`
7. `reports/phase-5-step-4/TEST_REPORT.md`
8. `reports/phase-5-step-3/NEXT_SESSION.md` — still valid for provider behaviour and token budgeting; **do not undo §3 of that document**

`AGENTS.md` §4 requires explicit approval between phases. Do not proceed on your
own.

---

## 2. What this step established

The first AI-assisted user path now works end to end, and the eleven behaviours
the step brief listed are each covered by a test that fails if the behaviour is
removed.

| Concern | Where it now lives |
|---|---|
| The only calls to `analyze_brief` / `generate_concepts` | `ui/ai_actions.py` |
| Brief screen | `ui/pages_brief.py` |
| Concepts screen and selection | `ui/pages_concepts.py` |
| Screen constants and titles | `ui/session.py` |
| Stage strip and stage-to-step map | `ui/shell.py` |
| AI-block CSS and escaped HTML helpers | `ui/theme.py` |
| Tests | `tests/test_ui_ai_flow.py` (38) |

Full suite: **839 passed**. Baseline: 801. No test deleted.

---

## 3. Architectural decisions that must not be undone

### 3.1 `ai` is imported lazily, inside functions

`ui/ai_actions.py` imports `ai` **inside** `analyze_brief`, `generate_concepts`,
`failure_message`, `is_configuration_failure` and `load_config` — never at module
level. Two reasons, both load-bearing:

1. `app.py` must not import `ai`. `tests/test_ui_app.py` asserts this in a child
   process with an empty module table, so "no AI call was made" stays a structural
   fact rather than a promise.
2. The AI package is loaded only in the rerun where a button was pressed. A
   session that never presses one never loads it.

If someone moves those imports to the top of `ai_actions.py`,
`test_the_whole_workflow_runs_without_importing_the_ai_layer` will fail. That
failure is correct.

### 3.2 Requests are events, not renders

Both requests sit inside `if st.button(...)`. This is the entire defence against
Streamlit re-sending a request on an unrelated rerun. Do not "optimise" it into a
render-time `if not is_complete(...): call()` — that would re-spend tokens on
every interaction and could overwrite a result the user is reading.

### 3.3 A failure cannot be stored

Both screens route through `WorkflowState.attempt(step, produce, record)`.
`attempt` calls `guard(step)`, then `produce()`, then `record(value)`. If
`produce` raises, the exception is wrapped in `StepFailed` and `record` is never
reached. There is no code path from a failed call to a stored result, and the
previous valid result survives a failed retry.

### 3.4 Currentness means `is_complete`, never `is not None`

Three places depend on this: the brief screen (a stored-but-out-of-date brief is
shown as "Out of date"), the concepts screen (it redirects when
`is_complete(BRIEF_ANALYSIS)` is false), and the stage strip. The workflow may
retain a value whose prerequisite has gone; presenting it as current is the bug
`is_complete` exists to prevent.

### 3.5 Reference imagery is never per concept

One style image plus palette swatches, drawn once above the cards, captioned as a
local reference that was not generated for these concepts, is not shown to the
AI, and does not depict them. The approved library has one image per style, so
one image per concept would necessarily reuse the same file three times and imply
it was AI output. `test_one_reference_image_is_not_reused_three_times` guards it.

### 3.6 No invented concept fields

`DesignConcept` has exactly seven fields. The cards show those seven. There is no
"Style characteristics" block, because the model has no such field, and style is
already fixed by the user's own preference — showing it per concept would
misrepresent what varies between concepts.

---

## 4. Established facts worth not rediscovering

- **`ConceptCollection` enforces exactly three concepts** (`min_length` ==
  `max_length` == `REQUIRED_CONCEPT_COUNT`) **and distinct names,
  case-insensitively**. A wrong-sized or duplicate-named answer cannot be
  constructed, so a bad provider response fails at validation rather than in the
  UI.
- **`select_concept` refuses anything outside the current set**, comparing by
  value. `record_concepts` clears the selection when the new collection differs,
  and returns early — invalidating nothing — when it is equal.
- **`DataKey.SELECTED_CONCEPT` invalidates exactly** furniture, materials,
  spatial, budget analysis and evaluation. The brief and the concepts survive a
  selection change; only the derived plan results are cleared.
- **`record_brief` clear-on-change**: a different brief discards the concepts and
  the selection derived from the old one. A rebuild that returns an identical
  brief clears nothing, though the API call has already been spent.
- **Streamlit 1.67.0 `AppTest` accessor names**: `at.get("image")`, not
  `at.get("imgs")` — `imgs` is the protobuf field name.
- **`AppTest` rewrites image sources** to a content-hashed `/mock/media/...` URL,
  so an image's file cannot be identified from the element tree. To assert which
  file was drawn, record the argument passed to `st.image` (the test script runs
  in the same interpreter, so a `monkeypatch` is visible to it).
- **The "Japandi" pill over the style reference image is baked into the Phase 2
  asset**, not drawn by the UI. It is the same file the preferences screen
  already used.
- **Form submit keys** (unchanged): `FormSubmitter:hm_room_form-Save room
  information` and `FormSubmitter:hm_preferences_form-Save preferences and
  budget`.
- **Test-module caveat**: a test module that imports `ai.client` for error
  classes cannot also assert `sys.modules` is AI-free. That structural assertion
  belongs in a child process, which is where it already is.

---

## 5. What is deliberately still missing

- The Furniture & Material Advisor screen (`recommend_furniture`).
- The spatial validation screen — and therefore any furniture placement. The
  advisor legitimately returns `position_x_cm = null`, so placement belongs to
  this later work, not to the model.
- The Design Evaluation screen (`evaluate_design`).
- PDF reporting, and `docs/screenshots/` (both Phase 9 concerns).
- Turkish localization, by explicit instruction.

`ui/pages_concepts.py` states that the recommendations built on the selected
concept are the next development stage and are not available yet. Keep that
honest until they exist.

---

## 6. Recommended next action

**Phase 5 / Step 5: the Furniture & Material Advisor and spatial validation
screens**, consuming `WorkflowState.selected_concept` — the value this step now
produces. The same three rules apply: calls behind buttons, results through
`attempt`, and freshness through `is_complete`.

Before that step, decide explicitly how coordinates are produced, since the
advisor does not return them and `AGENTS.md` §7 forbids asking the model to
compute geometry.

---

## 7. Standing constraints (unchanged)

- Never shut down or restart the computer; it stays on.
- No Git initialisation, commit, push or deploy without explicit approval.
- Do not change the AI model, provider, endpoint or token limits without
  approval.
- Do not add a dependency without a stated technical requirement and approval.
- Keep `DEPLOY_API_KEY` out of source, logs, error messages, screenshots and
  reports.
- Real-provider validation happened in Phase 5 Step 3. This step's tests are
  mock-only; do not represent them as a fresh live validation.
