# Phase 5 / Step 2 — Completion Report

**Project:** Hometsy — Room Intelligence Studio
**Phase:** 5 — Complete Application Workflow
**Step:** 2 — Deterministic Streamlit Workflow
**Date:** 2026-11-15
**Status:** Implementation and tests complete; awaiting approval before Step 3.

---

## 1. Objective

Put the Step 1 workflow layer on screen. The goal for this step was stated in the
approved brief as *"the user can build a valid design input without making an AI
call"*, so this step implements exactly the three input screens — room
information, design preferences, and a review of what has been collected — and
stops there.

No AI call is made, no AI code is imported, and no result is invented.

---

## 2. What Was Built

### 2.1 A new `ui/` package

All Streamlit code now lives in one package, which is also the only part of the
application allowed to import Streamlit. The workflow layer stays framework-free,
so the rules it owns can be tested without a UI runtime.

| Module | Lines | Responsibility |
|---|---:|---|
| `ui/theme.py` | 433 | Design tokens, the single stylesheet, HTML helpers |
| `ui/commits.py` | 407 | Pure widget-value → validated-model builders |
| `ui/session.py` | 345 | The session-state adapter around `WorkflowState` |
| `ui/pages_room.py` | 301 | Room information screen |
| `ui/pages_preferences.py` | 329 | Style, palette, requirements and budget screen |
| `ui/pages_review.py` | 172 | Input review and validation findings |
| `ui/shell.py` | 188 | Stage strip, brand line, flash and issue rendering |
| `ui/pages_landing.py` | 170 | Landing page (kept from Phase 1) |
| `ui/references.py` | 177 | Local style/palette reference library |
| `ui/diagram.py` | 162 | Illustrative floor diagram for the room form |
| `ui/__init__.py` | 19 | Package documentation |
| `app.py` (rewritten) | 70 | Screen router; imports no AI module |

### 2.2 The three screens

**Room information** — room type, name, width, length, optional ceiling height,
and exactly one door and one window described by wall, offset and width. A live
illustrative diagram follows the form while it is being filled in.

**Design preferences** — one of six approved styles and one of four approved
palettes, each shown as a local reference image card; optional material
preferences; functional requirements as separate entries; free-form notes; and a
budget amount in TRY.

**Input review** — the four stored values, the findings `core.validation`
produces for them, the workflow's own view of completeness, and an explicit
statement that the AI stages are not part of this development step.

### 2.3 What this step deliberately does not contain

- No concept cards, furniture lists, budget breakdown or PDF export.
- No AI request, and no module that could make one: `app.py` never imports `ai`.
- No button that pretends a later stage exists. The three later stages are
  labelled **Not available yet** in the stage strip.

---

## 3. Architecture Decisions

### 3.1 One central session key

The whole project lives under a single key, `hm_workflow_state`, holding one
`WorkflowState` object. The alternative — one session key per field — would have
required the interface to re-implement invalidation by hand, which is exactly the
duplicated rule table Phase 5 Step 1 exists to prevent. Keeping one object also
makes "a rerun did not recreate the state" a testable identity assertion.

The other keys are view concerns and are clearly separated:

| Key | Purpose |
|---|---|
| `hm_workflow_state` | The project |
| `hm_screen` | Which screen is open |
| `hm_workflow_entered` | Whether the user left the landing page |
| `hm_flash` | One message to show on the next render |
| `hm_generation` | Bumped on reset so forms re-seed |
| `hmw_*` | Widget values, namespaced for clean reset |

### 3.2 Forms, not live widgets

The room and preference screens are `st.form`s with an explicit submit. A live
form would commit a partial room on every keystroke, and every such commit would
invalidate the user's downstream work — a half-typed width of 4 cm would wipe a
finished concept stage. Explicit submission is what makes *"invalidation happens
because the user changed something"* true rather than *"invalidation happens
because the user typed"*.

### 3.3 Two gates, and no third

`ui/commits.py` builds the Pydantic model first, then runs `core.validation`.
The interface never restates a rule. A door that does not fit its wall is
rejected by `RoomInput`'s own validator; a door/window collision is rejected by
`core.room_engine`, reached through `validate_room_input`. A failed conversion
returns an `Outcome` with no value, so a page can only call `set_room()` with
something that already passed both gates.

### 3.4 Freshness is asked, never inferred

Every screen asks `WorkflowState.is_complete(step)`. No screen tests
`value is not None`. That is what keeps a retained-but-prerequisite-less result
from being shown as current, and it is pinned by
`test_a_retained_result_without_its_prerequisite_is_not_reported_complete`.

### 3.5 Five user-facing stages over ten workflow steps

`DESIGN_SYSTEM.md` §6.2 defines five stages; the workflow has ten steps. The
mapping lives in `ui/shell.py` as a display concern. Only the first two stages
are in `AVAILABLE_STAGES`; the rest render as "Not available yet".

### 3.6 Selection is never conveyed by colour alone

Reference cards show selection twice — a "Selected" badge in the card and the
card's button label changing to "Selected" — per `DESIGN_SYSTEM.md` §7. The
stage strip likewise names its own state in words ("Complete", "In progress",
"Not started", "Not available yet").

### 3.7 The stylesheet is scoped

`ui/theme.py` holds the only stylesheet. Every rule is qualified under `.hm-page`,
a class the application renders itself, and nothing targets Streamlit's internal
DOM. `tests/test_ui_presentation.py` asserts that scoping mechanically, so a
future rule cannot leak into the host page. Base page colours come from
`.streamlit/config.toml` and are checked against the same token set.

---

## 4. Defects Found and Fixed During This Step

Four real problems were found by driving the actual interface, not by reading the
code. All four are now covered by tests.

1. **A bare colon in front of a geometry message.** Pydantic reports a
   model-level validator error with an empty location, so the field label came
   out empty and the user saw `": The door does not fit..."`. Model-level errors
   now take a `fallback_label` naming the model ("Room", "Preferences",
   "Requirements").
2. **A three-decimal budget said nothing useful.** Pydantic's type is
   `decimal_max_places`, not `decimal_places`, so the message fell through to
   raw Pydantic text. Both types are now mapped to a sentence.
3. **The first save falsely claimed work had been cleared.** `set_preferences`
   correctly reports every dependent key, but on a first save none of those
   results had ever existed. The confirmation now describes what the user
   actually lost, using a snapshot of the pre-edit state. A real edit still names
   exactly the results it cleared.
4. **Every advisory warning appeared twice on the review screen.** The commit
   path stored a copy of the advisory findings and the review screen also
   recomputed them. The stored copy is gone; `validate_inputs` is the one source.

Two smaller copy/layout defects were also fixed: the diagram legend read
"DoorWindow" because a flex parent discarded the space between the two labels,
and the header said "Step 0 of 10 complete" instead of "0 of 10 steps complete".

---

## 5. Files Created and Modified

### Created

| File | Lines |
|---|---:|
| `ui/__init__.py` | 19 |
| `ui/theme.py` | 433 |
| `ui/commits.py` | 407 |
| `ui/session.py` | 345 |
| `ui/shell.py` | 188 |
| `ui/diagram.py` | 162 |
| `ui/references.py` | 177 |
| `ui/pages_landing.py` | 170 |
| `ui/pages_room.py` | 301 |
| `ui/pages_preferences.py` | 329 |
| `ui/pages_review.py` | 172 |
| `tests/test_ui_commits.py` | 512 |
| `tests/test_ui_session.py` | 532 |
| `tests/test_ui_app.py` | 789 |
| `tests/test_ui_presentation.py` | 251 |
| `reports/phase-5-step-2/COMPLETION_REPORT.md` | — |
| `reports/phase-5-step-2/TEST_REPORT.md` | — |
| `reports/phase-5-step-2/NEXT_SESSION.md` | — |

### Modified

| File | Change |
|---|---|
| `app.py` | Rewritten as a router over the `ui` screens (was a Phase 1 single page) |

### Untouched

`ai/*`, `core/*`, `models/*`, `workflow/*`, `data/*`, `.streamlit/config.toml`,
`requirements.txt`, `opencode.json` and every existing test file. No dependency
was added. No AI prompt, endpoint, model or credential was changed.

---

## 6. Requirements Coverage

| Requirement | Where it is satisfied |
|---|---|
| Room type, name, width, length, ceiling | `ui/pages_room.py`, `commits.build_room` |
| Exactly one door and one window | Fixed door + window fields; models have no list |
| Wall, offset and width per opening | Per-opening wall/offset/width controls |
| Six styles, four palettes | `ui/references.py`, `ui/pages_preferences.py` |
| Palette selection | Palette card group |
| Optional material preferences | Free-entry multiselect, stored as free text |
| Functional requirements | Free-entry multiselect |
| Notes | Free-text area |
| Budget amount and currency | Numeric field; TRY fixed as the only V1 currency |
| Inputs survive a rerun | Single `WorkflowState` in session state |
| One central state key | `hm_workflow_state` |
| Old AI results never mix with new input | Step 1 invalidation, exercised end to end |
| Freshness via `is_complete` | `ui/shell.py`, `ui/pages_review.py` |
| Workflow layer Streamlit-independent | Enforced by `test_ui_package_is_the_only_streamlit_importer` |
| Pydantic first, then `core.validation` | `ui/commits.py` |
| Door/window geometry checked | Model validator + `opening_conflict_messages` |
| Clear errors, no tracebacks | `issues_from_validation_error`, `render_issues` |
| Invalid input not saved as complete | Commit returns no value on failure |
| Design system followed | `ui/theme.py`, scoped CSS, tokens checked by tests |
| Desktop and mobile usable | Single-column form groups; wrapping card row |
| No concept/AI/PDF screens | Three screens only; later stages labelled unavailable |

---

## 7. How the Step Was Verified

Beyond the automated suite, the application was run under
`streamlit run app.py` and driven in a real browser:

1. Landing page rendered with the V1/V2/V3 roadmap intact.
2. **Start Room Setup** opened the room form; the diagram and legend rendered.
3. A valid room was saved and the app moved to preferences with a success
   message.
4. Style cards changed the selection and updated both indicators.
5. A requirement chip was added through the free-entry field.
6. Saving preferences landed on the review screen with all four inputs shown,
   "All blocking checks passed", and a single advisory warning.
7. Returning to the room form showed the **saved** room, not an empty one.
8. Submitting an empty room name was refused with a readable sentence, and the
   previously saved room and preferences survived untouched.

Step 7 and 8 are the two behaviours most likely to regress silently, which is why
they are also pinned by AppTest cases rather than only by manual inspection.

---

## 8. Known Limitations

1. **The four AI prompts have still never been sent to the real provider.** This
   step makes no AI call by design, so this Phase 4 carry-over remains open.
2. **No screenshots could be captured for the report.** The browser session has
   no visible desktop window, so the screenshot tool refuses to run. The
   rendering was verified through the live page's text content instead, and
   `docs/screenshots/` remains empty. Capturing approved screenshots is a Phase 9
   task and is not blocked by this step.
3. **The stage strip counts workflow steps, not the five stages.** "2 of 10 steps
   complete" is accurate but mixes granularity with the five-stage strip above
   it. Worth revisiting when the later stages exist.
4. **The budget widget caps at 10,000,000 TRY.** The model has no upper bound; the
   widget does, to keep the control usable. A value above the cap cannot be typed
   through the interface.
5. **Material preferences and functional requirements are free text.** By design
   in this step — they are notes for the brief, not catalog selections — but that
   means no spell-check, no normalisation beyond trim/de-duplicate, and no link to
   the furniture catalog.
6. **Reference images have mixed aspect ratios** (portrait styles, landscape
   palettes). They are fitted into a fixed 4:3 frame with `object-fit: cover`, so
   some source images are cropped. This is the Phase 2 carry-over and is visual
   only.
7. **The illustrative diagram is not to scale and does not validate anything.** It
   is labelled as such on screen. The geometric authority remains
   `core.room_engine`.
8. **Single-user, in-memory only.** A page reload starts a new project. That is
   within the approved V1 scope (no persistence, no authentication) but it means
   the workflow state is lost on refresh.

---

## 9. Scope Deviations

None. No feature outside the approved V1 was added, no excluded feature was
implemented, no dependency was introduced, and no AI provider, model, endpoint or
configuration was changed.

One presentation decision is worth naming explicitly because it is visible to the
user: the landing page's primary button now enters the workflow instead of
announcing that room setup does not exist yet. That sentence was true in Phase 1
and is no longer true; `AGENTS.md` §10 forbids presenting implemented features as
planned. The landing page's other content is unchanged.

---

## 10. Recommended Next Action

Proceed to **Phase 5 / Step 3: AI Brief Analysis and Concept Generation**, which
would wire `workflow.attempt()` to the four existing AI services and add the
concept and selection screens.

That step should begin by resolving the oldest open risk in the project: the four
prompts have never been sent to the real provider. A single manual probe against
`deepseek-ai/deepseek-v4.1-flash-1017` — concept generation especially, at 6000
tokens — would establish real token limits and truncation behaviour before any
screen depends on them.

Awaiting explicit approval before starting.
