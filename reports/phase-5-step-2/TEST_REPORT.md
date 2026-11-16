# Phase 5 / Step 2 — Test Report

**Project:** Hometsy — Room Intelligence Studio
**Phase:** 5 — Complete Application Workflow
**Step:** 2 — Deterministic Streamlit Workflow
**Date:** 2026-11-15

---

## 1. Command

All results below come from:

```
cd "[PROJECT_ROOT]"
& ".venv\Scripts\python.exe" -m pytest -q
```

Environment: Python 3.13.18 in `.venv`, pytest configured through `pytest.ini`
(`testpaths = tests`, `pythonpath = .`, `addopts = -ra`).

---

## 2. Headline Result

```
801 passed in 10.36s
```

| Metric | Value |
|---|---|
| Collected | 801 |
| Passed | 801 |
| Failed | 0 |
| Errors | 0 |
| Skipped | 0 |
| xfail / xpass | 0 |
| Warnings that affect correctness | 0 |

Baseline before this step was **685 passed**. This step adds **116 tests** and
modifies none of the existing ones.

---

## 3. Per-File Breakdown

| Test file | Tests | Status |
|---|---:|---|
| `test_ai_client.py` | 58 | pass |
| `test_ai_config.py` | 30 | pass |
| `test_ai_parsing.py` | 112 | pass |
| `test_ai_prompt.py` | 38 | pass |
| `test_ai_services.py` | 70 | pass |
| `test_budget_engine.py` | 34 | pass |
| `test_data_library.py` | 34 | pass |
| `test_models.py` | 54 | pass |
| `test_room_engine.py` | 48 | pass |
| `test_spatial_engine.py` | 45 | pass |
| `test_ui_app.py` | **32** | pass (new) |
| `test_ui_commits.py` | **40** | pass (new) |
| `test_ui_presentation.py` | **22** | pass (new) |
| `test_ui_session.py` | **22** | pass (new) |
| `test_validation.py` | 35 | pass |
| `test_workflow_dependencies.py` | 35 | pass |
| `test_workflow_integration.py` | 9 | pass |
| `test_workflow_state.py` | 83 | pass |
| **Total** | **801** | **all pass** |

New in this step: 116 tests (`32 + 40 + 22 + 22`).

---

## 4. The Core Suite Needs No API Key

The whole suite was re-run in a child process with `DEPLOY_API_KEY` removed from
the environment:

```
without DEPLOY_API_KEY: 801 passed in 9.77s    (exit code 0)
```

This confirms the rule in `AGENTS.md` §12 — the core test suite must not require a
live API key. No test in this step reads any credential, opens a socket, or
imports an AI service for the application path.

---

## 5. What the New Tests Cover

### 5.1 `tests/test_ui_commits.py` — 40 tests

Pure conversion tests; no Streamlit runtime is needed.

- Valid room accepted, typed numbers preserved, name trimmed.
- Blank name, whitespace-only name, under-minimum and over-maximum dimensions
  rejected with a sentence.
- Door overflow and window overflow rejected **by the model**, with the wall span
  named in the message.
- Door/window overlap on one wall rejected; exactly touching openings allowed.
- A model-level geometry error is attributed to "Room", not to an empty label
  (regression guard for the `": The door does not fit..."` bug).
- The commit path agrees with `core.validation` about a room either of them
  rejects — the interface does not invent its own geometry.
- Budget stored as `Decimal`; a typed `0.1` stays `0.1`, not `0.10000000000000001`.
- Three-decimal budget rejected, never rounded; negative rejected; zero accepted
  because the approved model has no lower bound and the widget must not invent one.
- Unparseable budget rejected without a traceback.
- Requirements/materials trimmed, blanks dropped, case-insensitive duplicates
  removed, original capitalisation and order kept.
- Notes trimmed; over-length notes rejected.
- `overall_warnings` silent until all four inputs exist, then reports a thin brief.
- `format_money` grouping (`45.000,00 TRY`).
- No returned message contains "traceback", "validationerror" or "pydantic".

### 5.2 `tests/test_ui_session.py` — 22 tests

Run through `AppTest.from_function`, because the adapter needs a real session.

- `get_workflow()` returns the **same object** twice, and the object survives a
  rerun with its room intact (the identity assertion that catches a per-rerun
  `WorkflowState()`).
- `has_workflow()` does not create state as a side effect.
- Unknown screens are rejected; a junk stored screen falls back to room.
- Entering/leaving the workflow changes only the view, not the project.
- A flash message is shown once and then forgotten.
- Invalidation copy: empty for no drop, correct singular and plural phrasing,
  every clearable key has a label.
- The first save says nothing was lost; a real edit names only what existed.
- `present_keys()` reads through `WorkflowState.data_for`, not through widgets.
- Reset replaces the state, clears `hmw_*` keys, clears the flash, returns to
  room, bumps the generation counter, and leaves unrelated keys alone.
- Seeding: sets once, never overwrites the user's edit, follows a changed stored
  value after a commit, and falls back when never set.
- `inputs_are_complete()` agrees with `WorkflowState.is_complete`.

### 5.3 `tests/test_ui_app.py` — 32 tests

The real `app.py` under `AppTest`, exercising widgets, forms, commits, session
state, navigation and rendering together.

- The app opens on the landing page with no exception and creates no workflow
  state until the user starts.
- The landing page does not claim unimplemented stages are ready.
- Entering the workflow creates the state exactly once, and a rerun keeps it.
- A valid room is stored, the step reports complete, and the app moves on with a
  success message.
- A room without a name is refused; nothing is stored; the user stays on the form
  with a sentence.
- A door that no longer fits is refused by geometry.
- A door and window on the same stretch are refused.
- An invalid edit does not destroy the room and preferences already saved.
- Preferences, requirements, notes and budget are stored from the form; the step
  reports complete; the app moves to review.
- Clicking a style card changes the stored selection and updates both indicators;
  the change is not committed until the form is submitted.
- The budget is stored exactly as typed (`"1234.56"`, not a float artefact).
- A budget the model cannot accept is refused by the commit path, not rounded.
- The review screen shows the four inputs, the money in Turkish grouping, the
  blocking-check result, and an explicit "no API call has been made" statement.
- The review screen offers no button for an unimplemented stage.
- Starting a new project clears the project and returns to an empty room form.
- A first save confirms the save rather than claiming a loss.
- A real edit reports the results it actually cleared.
- Changing the room clears every derived result and tells the user in words.
- Renaming the room alone clears **nothing** — a name is presentation only.
- Moving only the door keeps the budget analysis and clears only geometry-derived
  results (the one-hop rule, observed through the UI).
- Editing preferences keeps the room and clears only the AI results.
- A retained evaluation whose prerequisites are gone is **not** reported complete
  and is never rendered as an achieved result.
- The stage strip names its states in words; exactly two stages read "Complete"
  and three read "Not available yet".
- Advisory findings are shown **once**, not twice.
- A stored input that breaks validation surfaces as an error on the review screen.
- The whole workflow runs in a **child process** and asserts
  `sys.modules` contains no `ai` or `ai.*` entry afterwards — structural proof
  that no API call happened, not a promise in a comment.
- `app.py` contains no `import ai` / `from ai` line.
- No module under `workflow/` imports Streamlit.

### 5.4 `tests/test_ui_presentation.py` — 22 tests

- The diagram is a self-contained SVG with no remote reference, marked as an
  illustration for screen readers.
- Every wall combination draws; zero dimensions do not divide by zero; an opening
  wider than its wall is clipped rather than drawn off-canvas.
- The legend names both openings as separate words (regression guard for
  "DoorWindow") and states the offset convention and the not-to-scale caveat.
- The colour swatches are marked `aria-hidden`, because the label carries the
  meaning.
- `escape()` neutralises markup.
- Every hex value in the stylesheet belongs to the approved token set.
- `.streamlit/config.toml` matches those tokens.
- Every CSS rule is scoped under `.hm-page` or an at-rule.
- No `@import` and no remote `url()` in the stylesheet.
- Every status has a word, not only a colour.
- The reference library covers every approved style and palette exactly once, all
  images exist and are non-empty, all are local paths, every card has a name and
  description, and every palette exposes six-digit hex swatches.
- Removing an entry from the reference data raises `ReferenceError` at load time
  instead of rendering a card with a hole in it.

---

## 6. Tests Deliberately Not Weakened

No existing test was changed, skipped, marked xfail, or deleted. The Phase 3 core
tests, the Phase 4 AI tests and the Phase 5 Step 1 workflow tests all run exactly
as they did before this step:

| Group | Tests | Before | After |
|---|---:|---:|---:|
| Core engines (`room`, `spatial`, `budget`, `validation`) | 162 | pass | pass |
| Models and data library | 88 | pass | pass |
| AI layer | 308 | pass | pass |
| Workflow layer (Step 1) | 127 | pass | pass |

---

## 7. Failures Observed and Fixed During Development

The failures below were genuinely observed while building this step. Each was
fixed in the implementation, not worked around in the test.

| # | Failure | Root cause | Resolution |
|---:|---|---|---|
| 1 | `': The door does not fit...'` | Pydantic reports model-level validator errors with an empty `loc`, so the field label was empty | `issues_from_validation_error(..., fallback_label=...)` attributes them to the model name |
| 2 | `'Total budget: Decimal input should have no more than 2 decimal places'` | Mapped type is `decimal_max_places`, not `decimal_places` | Both types mapped to "Use at most two decimal places." |
| 3 | First save announced "Earlier results no longer apply and were cleared" | The invalidation message described the rule table, not a real loss | `previously_present` snapshot; `None` means "don't filter" |
| 4 | Every advisory warning rendered twice | Commit stored a copy of the findings **and** the review screen recomputed them | Stored copy removed; `validate_inputs` is the single source |
| 5 | Legend extracted as `DoorWindow` | `display:flex` on the parent discarded the inter-item whitespace | Inline-flex items with a literal space between them |
| 6 | Header read "Step 0 of 10 complete" | Counter labelled every step "Step" | "0 of 10 steps complete", using `STEP_ORDER` |

Two test-authoring mistakes were also corrected, and are noted for honesty:

- A test asserted a small-room advisory from `validate_room_input`; that warning
  actually belongs to `validate_inputs`, which describes the combination. The test
  now pins the real division between the two gates.
- A test assumed a form's widget values would survive an intermediate `run()`.
  Streamlit forms only report their values on submit; the test now sets every
  value before submitting, which is also how a user behaves.

---

## 8. Manual Verification

The application was run with `streamlit run app.py` and driven in a real browser
(a live HTTP session, not AppTest). The following were confirmed against the
running server:

1. Landing page renders the brand lockup, capabilities and V1/V2/V3 roadmap.
2. **Start Room Setup** opens the room form; the SVG diagram and its legend
   render, with "Door" and "Window" as separate words.
3. Saving a valid room shows "Room information saved.", advances the step counter
   to "1 of 10 steps complete", and opens the preferences screen.
4. All six style and four palette cards render with their reference images,
   descriptions and swatches; the current selection shows both a badge and a
   "Selected" button.
5. Clicking a style card moves the badge and the button label to that card.
6. Adding a functional requirement through the free-entry field works.
7. Saving preferences lands on the review screen with all four inputs, the money
   in `45.000,00 TRY` form, "All blocking checks passed.", and the advisory shown
   **once**.
8. Returning to the room form pre-fills it from the saved room.
9. Submitting an empty room name is refused with "Nothing was saved. 1 problem
   needs attention:" plus "- Room name: give the room a name."; the saved room and
   preferences survive and the step counter stays at "2 of 10 steps complete".

Server logs during the whole manual pass contained no unhandled exception and no
traceback.

Screenshots could **not** be captured: the browser session has no visible desktop
window, so the screenshot tool declines to run. Rendering was therefore verified
through the live page's text content. `docs/screenshots/` remains empty, which is
consistent with the Phase 9 documentation task and is not a defect in this step.

---

## 9. Reproducing These Results

```
cd "[PROJECT_ROOT]"
& ".venv\Scripts\python.exe" -m pytest -q
```

Individual groups:

```
& ".venv\Scripts\python.exe" -m pytest tests/test_ui_commits.py -q        # 40
& ".venv\Scripts\python.exe" -m pytest tests/test_ui_session.py -q       # 22
& ".venv\Scripts\python.exe" -m pytest tests/test_ui_presentation.py -q  # 22
& ".venv\Scripts\python.exe" -m pytest tests/test_ui_app.py -q           # 32
```

Run the application:

```
& ".venv\Scripts\python.exe" -m streamlit run app.py
```

---

## 10. Summary

| Claim | Evidence |
|---|---|
| 801 tests pass, 0 fail | §2, §3 |
| 116 tests added, 0 existing tests changed | §3, §6 |
| Suite passes with no API key present | §4 |
| No AI call is possible from this path | `test_the_whole_workflow_runs_without_importing_the_ai_layer`, `test_app_py_does_not_import_the_ai_layer` |
| The workflow layer is framework-free | `test_ui_package_is_the_only_streamlit_importer` |
| The interface works in a real browser | §8 |
| Six real defects were found and fixed | §7 |
