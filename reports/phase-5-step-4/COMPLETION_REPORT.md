# Phase 5 / Step 4 — Completion Report

**Project:** Hometsy — Room Intelligence Studio
**Phase:** 5 — Complete Application Workflow
**Step:** 4 — AI Brief Analysis & Concept Generation UI
**Date:** 2026-11-15
**Status:** Implemented, tested with mocks, visually reviewed; awaiting approval.

---

## 1. Objective

Make the first AI-assisted path usable end to end inside Streamlit:

1. the user analyses a design brief from the input already saved,
2. reads the brief,
3. generates exactly three design concepts from it,
4. compares them,
5. selects one,
6. and has that selection stored in `WorkflowState` so the next phase can build
   on it.

The constraints that shaped the implementation were mostly about restraint:
one request per click, no request on a rerun, no failed call recorded as a
result, no concept without a current brief, no invented model fields, and no
suggestion that a reference photograph is AI output.

---

## 2. How the integration was built

### 2.1 One new bridge module: `ui/ai_actions.py`

The screens must not build prompts, choose models or read credentials, and
`app.py` must not import `ai` (a property `tests/test_ui_app.py` asserts
structurally, in a child process). `ui/ai_actions.py` is the single place those
two requirements meet:

- it holds the only calls to `ai.brief_analyzer.analyze_brief` and
  `ai.concept_generator.generate_concepts`;
- it imports `ai` **inside** those functions, so importing the interface does not
  load the AI package. The deterministic screens are still provably AI-free, and
  the AI layer is loaded only in the rerun where a button was actually pressed;
- it owns the error copy, in one table keyed by the stable `category` attribute
  the existing exception classes already expose;
- it resolves configuration through the existing `ai.config.load_config`,
  passing `st.secrets["DEPLOY_API_KEY"]` only as a fallback for deployments that
  configure secrets there. The environment variable is still checked first, by
  `ai.config` itself.

It deliberately does **not** retry, does not alter a prompt, does not change a
token limit, and does not choose a model.

### 2.2 Brief screen — `ui/pages_brief.py`

- Uses only the four stored inputs; no new data fields were invented. The
  "What will be sent" table is read back from `RoomInput`, `DesignPreferences`,
  `UserRequirements` and `BudgetInput`.
- The request happens inside `if st.button(...)`, so it is an event, not a render
  side effect. A rerun with no click reaches the render branch and stops.
- The write goes through `WorkflowState.attempt(step, produce, record)`, which
  records only what `produce` returned. There is no code path from a failed call
  to a stored brief.
- A spinner states what is happening and roughly how long it takes.
- The brief is presented with every field the model has: summary, functional
  priorities, constraints, ambiguities, and `warnings` (labelled "Risks worth
  knowing"). Every string is escaped by `ui.theme` before it reaches HTML.
- A stored-but-not-current brief is shown as "Out of date" rather than as a
  result, because currentness is `state.is_complete(BRIEF_ANALYSIS)`, never
  `brief is not None`.
- Rebuilding is a separate, clearly labelled action with a note explaining that
  concepts derived from the old brief will be cleared.

### 2.3 Concepts screen — `ui/pages_concepts.py`

- Redirects to the brief screen (with an explanation) when
  `is_complete(BRIEF_ANALYSIS)` is false, rather than offering a button the
  workflow's own guard would refuse.
- Three cards in one row on a wide window, stacking on a narrow one.
- Only fields that exist on `DesignConcept` are shown: name, description, design
  direction, colour and material direction, furniture approach, functional
  rationale, budget suitability. There is no "Style characteristics" block,
  because the model has no such field; style is also fixed by the user's own
  preference, so showing it per concept would be misleading.
- Selection is signalled twice — a "Selected" badge and a button whose label is
  "Selected" and which is disabled — so it never depends on colour alone.
- Selection goes through `state.select_concept`, which refuses any concept that
  is not a member of the current collection. A stale concept from an earlier set
  cannot be selected by name or by object.
- After a selection, the screen reports what the change cleared, using
  `session.invalidation_message` and the existing dependency table.

### 2.4 Reference imagery

`data/design_references.json` holds one approved local image per style and per
palette; `ui/references.py` already exposes them. The concepts screen shows:

- **one** style image — the user's own chosen style — and the palette's colour
  swatches, drawn once in a strip above the cards;
- a caption stating that these are local reference images, that they were not
  generated for these concepts, that they are not shown to the AI, and that they
  do not depict the concepts.

No image is repeated per card, no image is downloaded, and no image is generated.
The mapping is exact for all six styles and all four palettes: each concept set
belongs to one style, so one reference image is the honest maximum. There is no
case in this step where a suitable reference was unavailable, so nothing had to
be reported as unmatchable.

### 2.5 Workflow state

- `workflow/state.py` and `workflow/dependencies.py` were **not modified**. The
  step used `record_brief`, `record_concepts`, `select_concept`, `attempt`,
  `StepFailed`, `is_complete` and `guard` exactly as Step 1 defined them.
- AI results live in the one `WorkflowState` that `ui/session.py` keeps under the
  single key `hm_workflow_state`. No new session keys were added.
- No screen tests `value is not None` for freshness.
- A failed call leaves the previous valid result in place: `attempt` only records
  a return value.

### 2.6 Navigation and stage display

- `ui/session.py` gained two screens, `brief` and `concepts`, in `SCREEN_ORDER`
  and `SCREEN_TITLES`.
- `ui/shell.py` now lists "Design Concepts" as an available stage, and reports a
  stage as "In progress" when some but not all of its steps are complete — which
  is the state the Concepts stage occupies between generating a brief and
  choosing a concept.
- `ui/pages_review.py` replaced its "not part of this development stage" note
  with a "Continue to design brief" button. Reaching the brief screen still
  makes no model call.
- `app.py` routes to the two new screens and still does not import `ai`.

---

## 3. API call control

| Requirement | How it is guaranteed |
|---|---|
| No call without a click | Both requests sit inside `if st.button(...)`; there is no call on a render path |
| No repeat call on rerun | A rerun with no click never enters the button body; tested by three consecutive `at.run()` cycles |
| One call per click | `attempt` invokes `produce` exactly once and there is no retry anywhere in the path |
| Failure cannot become a result | `attempt` wraps the exception in `StepFailed` and records nothing |
| Previous result preserved on failure | The stored value is only replaced by `record(...)`, which a failure never reaches |
| No call before the input is valid | `attempt` calls `guard(step)` first; the screens also refuse to render the button |
| No credential on screen or in logs | Error copy is written by this application and never includes provider text; `ai.config` and `ai.client` already redact |

Error mapping uses the existing classes' `category` values
(`authentication_error`, `rate_limit`, `timeout`, `network_error`,
`truncated_response`, `server_error`, `invalid_json`, `schema_validation_error`,
`correction_failed`, `empty_response`, `response_format_error`,
`request_error`), plus a dedicated message for `AIConfigurationError` naming
`DEPLOY_API_KEY`, plus one generic fallback sentence. Provider wording is never
surfaced.

---

## 4. Files created and modified

### Created (3)

| File | Lines | Purpose |
|---|---:|---|
| `ui/ai_actions.py` | 219 | The only caller of the two AI services; lazy `ai` imports; error copy table |
| `ui/pages_brief.py` | 251 | The Design Brief screen (AI operation 1) |
| `ui/pages_concepts.py` | 321 | The Design Concepts screen (AI operation 2 and selection) |
| `tests/test_ui_ai_flow.py` | 921 | 38 new tests, all with a fake AI |

### Modified (7)

| File | Change |
|---|---|
| `ui/session.py` | Added `SCREEN_BRIEF` / `SCREEN_CONCEPTS` to order, titles and `__all__` |
| `ui/shell.py` | "Design Concepts" added to `AVAILABLE_STAGES`; `stage_statuses` reports partial completion as in progress |
| `ui/theme.py` | Scoped CSS for brief/concept/reference blocks; seven new escaped HTML helpers; `Sequence` import |
| `ui/pages_review.py` | "Continue to design brief" replaces the unavailable note |
| `ui/__init__.py` | Module map updated |
| `app.py` | Two screens added to `_SCREENS`; docstring updated to describe the lazy AI import |
| `tests/test_ui_app.py` | Three assertions updated to the new scope (see §6) |

### Not modified

`workflow/state.py`, `workflow/dependencies.py`, `ai/*`, `core/*`, `models/*`,
`data/*`, `assets/*`, `requirements*.txt`, `.streamlit/config.toml`.

---

## 5. Visual review

The application was run locally against a temporary preview harness that
substituted fixed AI answers, so the screens could be inspected in a browser
without contacting the provider. The harness was deleted afterwards; it is not
part of the deliverable.

Observed and confirmed:

- Brief screen empty state, populated state, and the rebuild affordance.
- The failure state: a red, readable sentence — "The AI provider did not answer
  in time. Nothing was saved. Try again when the connection is stable." — with
  zero `stException` elements and no provider text anywhere in the page body.
- Concept cards side by side, all seven model fields present, no invented field.
- Selection: the chosen card shows a "Selected" badge and a disabled "Selected"
  button; the other two still offer "Select this concept".
- Mobile at 390 × 844: stage chips wrap, cards stack, the document does not
  overflow horizontally (`scrollWidth == innerWidth == 390`).
- The reference strip draws exactly one image, with its caption.

One presentational defect was found and fixed during this review: the brief
screen's input table read "Living Room · Living Room", because the default room
name equals the room type. The type is now appended only when the name does not
already contain it.

Note for the record: the "Japandi" label visible over the reference image is
baked into the approved Phase 2 asset itself, not drawn by this step's code. It
is the same image the preferences screen already used.

---

## 6. Changes to existing tests

Three assertions in `tests/test_ui_app.py` encoded the *previous* scope — that no
AI stage existed at all. They were updated to the new approved scope, and their
intent was preserved rather than weakened:

| Test | Before | After |
|---|---|---|
| `test_the_review_screen_shows_the_four_inputs_and_no_ai_claim` | required "not part of this development stage" | requires "nothing has been sent to a model yet" — the same claim, in the copy that now exists |
| `..._offers_no_button_that_pretends_a_stage_exists` (renamed `..._only_offers_screens_that_exist`) | allowed four buttons | allows five, adding "Continue to design brief"; still an exhaustive allow-list |
| `test_stage_indicator_never_marks_an_unimplemented_stage_complete` | `>= 3` unavailable | `== 2` unavailable — stricter, since exactly two stages remain unbuilt |
| `test_a_retained_result_without_its_prerequisite_is_not_reported_complete` | "not part of this development stage" or "not available" | "not available yet" |

No test was deleted, and no assertion was weakened.

---

## 7. Known limitations

1. **Highlighting compares by name, not by identity.** The card compares
   `selected.name == concept.name` because equal-value concepts are
   indistinguishable in a frozen model. This is safe: `ConceptCollection`
   validates that the three names are distinct (case-insensitive), so at most one
   card can match. `select_concept` itself compares by value and refuses anything
   outside the current set.
2. **Recommendations are not built.** The screen honestly reports that the
   furniture and material recommendations are the next development stage.
3. **Streamlit's own image element is used unmodified**, so the reference image
   keeps the fullscreen-expand affordance Streamlit adds. Restyling Streamlit
   internals is out of bounds by `AGENTS.md` §10.
4. **No concept-level imagery.** The three concepts are text-only by design: this
   step has no image generation, and the approved library has one image per
   style, not one per concept.
5. **A rebuild always re-requests.** If the new brief is identical to the old one
   the concepts survive (`record_brief` returns early on equality); the API call
   has still been spent, because the application cannot know the answer in
   advance.
6. **Real-provider behaviour of this flow was not re-exercised here.** See §8.

---

## 8. Provider validation status — stated explicitly

**Real provider validation was performed in Phase 5 Step 3**, where all four AI
services were run against the live provider and every answer was checked for
valid JSON, schema conformance and business-rule compliance. That is recorded in
`reports/phase-5-step-3/`.

**Every automated test in this step uses mocks.** No test in
`tests/test_ui_ai_flow.py` opens a socket or reads a credential; the two services
are replaced by a `FakeAI` fixture that records its arguments and can be told to
raise. The full suite runs with no network access and no key present.

Consequently, what this step proves is the *wiring* — that a click causes exactly
one call with the right arguments, that a failure cannot be stored, and that no
rerun calls anything — not that the provider still answers as it did in Step 3.
The services themselves were not modified in this step.

---

## 9. Scope compliance

Implemented: brief analysis screen, concept generation screen, exactly three
comparable concept cards, single selection stored in `WorkflowState`,
invalidation on selection change, local reference imagery, human-readable errors.

Not implemented, as instructed: Furniture Advisor screen, furniture placement,
coordinates from the AI, spatial validation screen, Design Evaluation screen, PDF
reporting, Turkish localization, new AI model or provider, database, new
dependency, Git operations.

No new dependency was added; `streamlit`, `pydantic`, `matplotlib`, `reportlab`
and `pytest` are unchanged, and the HTTP path remains `urllib.request` from the
standard library.

---

## 10. Recommended next action

Approve this step, then proceed to Phase 5 / Step 5: the Furniture & Material
Advisor screen and the spatial validation screen, which consume
`WorkflowState.selected_concept` — the value this step now produces.
