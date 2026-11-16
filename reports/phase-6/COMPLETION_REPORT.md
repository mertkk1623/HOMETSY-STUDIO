# Phase 6 — Completion Report

**Project:** Hometsy — Room Intelligence Studio
**Phase:** 6 — Brief Analyzer Reliability, PDF Report Generation, End-to-End QA
**Date:** 2026-11-15
**Status:** COMPLETE
**Full test suite:** 1076 passed, 0 failed, 0 skipped (baseline 996, delta **+80**)

---

## 1. Objective

Phase 6 had three parts, in a fixed order:

1. **A — Brief Analyzer reliability.** Diagnose the intermittent
   truncated-response failure before changing anything, then fix its actual
   cause.
2. **B — PDF report generation.** Produce a professional multi-page A4 report
   from `ProjectResult`, downloadable from the Final Report screen.
3. **C — End-to-end QA.** Walk the whole workflow and verify the delivered
   application, not the intended one.

The phase is only COMPLETE when both A and B are done. Both are.

Constraints honoured throughout: no rewritten working code, no new
dependencies, no refactoring for its own sake, no Git operations.

---

## 2. Part A — the Brief Analyzer failure

### 2.1 Diagnosis, not assumption

The reported symptom was an intermittent failure on "Analyse the brief" that
produced a structured-output error. Two very different causes fit that
description:

| Cause | Shape | Correct response |
|---|---|---|
| Malformed JSON | `finish_reason = "stop"`, unparseable text | one correction attempt |
| Truncated response | `finish_reason = "length"`, incomplete payload | more tokens, **no** retry |

The architecture already separated these: `ai.client` raises
`AITruncatedResponseError` (category `truncated_response`) when the provider
reports `length`, and `ai.prompt.run_structured_request` deliberately does not
correct it. So the failure had to be either a genuine formatting problem or a
token ceiling. Guessing would have been cheap and wrong.

**Measurement.** A probe (`probe_brief.py`) called the real provider with the
real Brief Analyzer prompt and recorded only measured facts — prompt tokens,
completion tokens, `finish_reason`, wall time, and whether the answer validated.
No key, no prompt text, no response text was printed.

At the then-current cap of **2000**:

| Run | Prompt | Completion | Finish | Result |
|---|---|---|---|---|
| 1 | 766 | — | `length` | `AITruncatedResponseError` |
| 2 | 766 | — | `length` | `AITruncatedResponseError` |
| 3 | 766 | 1675 | `stop` | success |

**2 of 3 truncated.** The brief's own completion length was 1675 tokens at
minimum, against a 2000 ceiling — the cap was the cause, and the intermittency
was a race between the model's verbosity and that ceiling.

### 2.2 The fix

`ai/brief_analyzer.py`:

```python
# Measured in Phase 6: the brief's JSON completion is 1 675-3 351 tokens, so the
# previous 2 000 cap truncated 2 of 3 live answers (finish_reason="length").
# 8 000 leaves the same headroom as the advisor and the evaluator, and every
# live run at this cap finished with finish_reason="stop".
MAX_TOKENS = 8000
```

One constant, raised to match the two sibling services that were already at
8000. Nothing else in the file changed: same prompt, same JSON contract, same
Pydantic validation, same `urllib.request` transport, same at-most-one
correction.

**Verification at 8000** — same probe, three live runs:

| Run | Prompt | Completion | Finish | JSON | Seconds |
|---|---|---|---|---|---|
| 1 | 766 | 3351 | `stop` | valid | 21.63 |
| 2 | 766 | 2520 | `stop` | valid | 17.12 |
| 3 | 766 | 2517 | `stop` | valid | 14.50 |

**3 of 3 succeeded**, all `stop`, all schema-valid. The measured completion
range (2517–3351) sits well above the old 2000 cap and comfortably below 8000.

### 2.3 What was deliberately *not* done

* No retry loop on the same bad response — truncation is never retried.
* No token-limit parameter invented: `max_tokens` is output-only here, and the
  reasoning tokens are charged against it, which is exactly why the ceiling
  mattered.
* No provider parameters that the provider does not document.
* No change to the output schema, so no migration of stored briefs.
* A failed request still leaves the previous valid brief in the workflow; a
  partial `DesignBrief` is never constructed, because the service either
  returns a validated model or raises.

---

## 3. Part B — PDF report generation

### 3.1 Architecture

`core/report_generator.py` is a **presentation** layer. It performs no
financial arithmetic and no geometry:

```
WorkflowState.finalize()
        │  (the only place a ProjectResult is created)
        ▼
ProjectResult ──────────────┐
                            │   ui/report.py  (no Streamlit, no AI)
BudgetResult ───────────────┤   finalize_and_build()
loaded catalog ─────────────┘          │
                                       ▼
                          core.report_generator.generate_report()
                                       │
                                       ▼
                     output/reports/hometsy-{safe-name}-report.pdf
                                       │
                                       ▼
                          st.download_button (explicit press only)
```

* **No recalculation.** Every figure printed is a field of the already-validated
  `BudgetAnalysis`. Every rectangle is a `PlacedFootprint` the placement engine
  produced. The generator never re-runs the budget engine and never re-derives a
  coordinate.
* **No parallel finalization.** `ui.report.finalize_and_build` calls the same
  `WorkflowState.finalize()` the workflow uses; there is one creator of a
  `ProjectResult`, not two.
* **A PDF failure cannot destroy the project.** Finalization happens first;
  generation second. If ReportLab raises, `state.result` is untouched and the
  Generate button remains, so the report is regenerable in one click.
* **No regeneration on rerun.** The artifact is stored in session state under
  `hm_report_artifact` and held current by object identity against
  `state.result`. Streamlit reruns on every widget interaction; none of them
  writes a file.
* **Stale reports are withdrawn.** `WorkflowState` clears `result` on any
  upstream invalidation, and the identity check then fails. The withdrawal runs
  at the *top* of `pages_report.render()`, before any early `return`, so a
  redirect cannot leave a stale file downloadable.

### 3.2 The one additive model change

`ProjectResult` previously omitted four things the report needs, because they
had only ever been reachable through `WorkflowState`:

```python
materials: list[MaterialRecommendation] = Field(default_factory=list)
color_direction: str = ""
design_rationale: str = ""
placement: PlacementOutcome | None = None
```

All four are defaulted, so every previously-constructed `ProjectResult` remains
valid. The alternative — having the report read `WorkflowState` — would have
coupled `core` to the workflow layer, and re-running geometry inside the report
would have violated the separation rule. This is the smallest change that keeps
the report a pure function of a finished result.

### 3.3 Sections

| | Section | Source |
|---|---|---|
| A | Cover | room name, type, area, date |
| B | Project overview | room, openings, preferences, budget |
| C | Design brief | stored `DesignBrief`, all five fields |
| D | Selected design concept | stored `DesignConcept` + the rejected names |
| E | Furniture and materials | catalog items, quantities, engine's line totals; materials marked "Not priced" |
| F | Validated 2D room plan | `PlacementOutcome` footprints, drawn to scale |
| G | Spatial validation | stored `SpatialValidation`, placement status, the score *and* its framing |
| H | Budget analysis | stored `BudgetAnalysis` + engine errors |
| I | AI design evaluation | stored `DesignEvaluation`, framed as opinion |
| J | Limitations and disclaimer | scope limits, indicative pricing, no compliance claim |

Rules enforced in the generator:

* **`FAILED` is never drawn as a plan.** The plan flowable is replaced by an
  explicit statement that no layout was produced, plus the engine's reasons.
* **`PARTIAL` draws only what was actually placed** and states the shortfall
  ("7 of 10 requested items were placed") on the same page as the drawing.
* **No invented score or verdict.** The heuristic layout score is printed with
  the engine's own framing — "a heuristic layout score, not a design-quality
  rating" — and no pass/fail badge is synthesised.
* **AI opinion is never engineering approval.** The evaluation section carries
  the same "not an engineering approval" framing as the screen.
* **An unpriced item is named, labelled "Not priced" and "Excluded",** and never
  appears in the itemised cost table, so the table cannot be misread as "this
  item costs nothing".

### 3.4 Typography and Turkish characters

Base-14 PDF fonts cannot render `ğ Ğ ş Ş ı İ ö Ö ü Ü ç Ç`. The report therefore
embeds **DejaVu Sans** (regular + bold) from `assets/fonts/`, registered as
`HometsySans`:

* `DejaVuSans.ttf`, `DejaVuSans-Bold.ttf` — Bitstream Vera / public-domain
  DejaVu licence, reproduced in `assets/fonts/DejaVu-LICENSE.txt`.
* Locally available TTF; **no external download at runtime**.
* A test asserts both faces contain every Turkish letter, and another asserts
  the finished PDF contains `/FontFile2` (a real embedded face, not a base-14
  reference) and that Turkish text survives into the extractable text layer.

### 3.5 Filenames

`report_filename(project_name)` produces
`hometsy-{sanitized-project-name}-report.pdf`: Turkish letters are folded
(`ş→s`, `ı→i`, `ğ→g`, `ü→u`, `ö→o`, `ç→c`), spaces become dashes, and every
other character other than `[a-z0-9-]` is dropped. The output path is composed
from a fixed output directory plus that name, so **the project name cannot
control the path**; a test feeds a name containing `..\\` and traversal
characters and asserts the file still lands inside the output directory.

---

## 4. Part C — End-to-end QA

### 4.1 Live workflow, real browser, real API

The app was run with `streamlit run app.py` and driven through a real Chromium
session at a 404 px viewport (mobile width):

| Step | Result |
|---|---|
| Landing → Room Setup | ok |
| Room `Şişli Salonu`, 400 × 520 cm, 20.80 m² | saved; Turkish name intact |
| Preferences (Industrial, Warm Neutral) | saved |
| Input review | "All blocking checks passed" |
| **Brief Analyzer (live API)** | **succeeded**; Turkish text intact |
| Concepts (live API) | 3 concepts, 5 of 10 steps |
| Concept selected | "Window-Facing Lounge Spine" |
| Plan / advisor (live API) | 10 of 10 placed, all blocking spatial checks passed |
| 2D plan | SVG renders with furniture labels and dimensions |
| Evaluation (live API) | succeeded, 9 of 10 |
| Budget | 58.600,00 TRY, deterministic |
| Final Report | 10 of 10 steps complete |
| **Generate PDF** | 76 312 bytes, "The PDF report is ready to download." |
| Download offered | yes |
| Console errors | **0** at every screen |

### 4.2 The downloaded file, verified over HTTP

The download was fetched from the URL Streamlit served:

```
GET /media/176eaf7bf7c61e40584bfa702f2728e7.pdf  →  HTTP 200
Content-Type:        application/pdf
Content-Disposition: attachment; filename="hometsy-sisli-salonu-report.pdf"
bytes:               76312
magic:               %PDF-1.4
```

So the safe Turkish-folded filename reaches the HTTP header, and the payload is
a real PDF.

### 4.3 Rerun does not regenerate

After generating, the page was rerun three times (sidebar interactions). The
file's `LastWriteTimeUtc` did not change and no new file appeared. This is the
behaviour the tests assert, confirmed in the running app.

---

## 5. Files created

| File | Purpose |
|---|---|
| `core/report_generator.py` | The PDF layer (sections A–J, fonts, plan flowable, pagination) |
| `ui/report.py` | Deterministic seam: `ReportArtifact`, `can_finalize`, `is_current`, `finalize_and_build`, `report_error_message` |
| `ui/pages_report.py` | The Final Report screen |
| `assets/fonts/DejaVuSans.ttf` | Regular face |
| `assets/fonts/DejaVuSans-Bold.ttf` | Bold face |
| `assets/fonts/DejaVu-LICENSE.txt` | Licence and attribution |
| `tests/test_report_generator.py` | 46 tests, including a self-contained PDF reader |
| `tests/test_ui_report.py` | 25 tests over the seam and the screen |
| `reports/phase-6/sample/hometsy-sisli-salonu-report.pdf` | The documented sample |

## 6. Files modified

| File | Change |
|---|---|
| `ai/brief_analyzer.py` | `MAX_TOKENS` 2000 → 8000, with the measured rationale |
| `models/schemas.py` | `ProjectResult` + `materials`, `color_direction`, `design_rationale`, `placement` (all defaulted) |
| `workflow/state.py` | `build_result` populates those four fields |
| `ui/session.py` | `SCREEN_REPORT`, order, title, `__all__` |
| `ui/shell.py` | `AVAILABLE_STAGES` gains "Final Report" (5 stages) |
| `app.py` | Report screen in the registry |
| `ui/pages_budget.py` | "Continue to the final report" |
| `tests/test_ai_services.py` | +9 reliability tests → 79 |
| `tests/test_ui_app.py` | 2 tests updated for the 5th stage |
| `tests/test_ui_ai_flow.py` | 1 test updated for the 5th stage |
| `tests/test_ui_budget.py` | 1 test updated for the 5th stage |
| `.gitignore` | `output/reports/` (runtime-generated, reproducible) |

---

## 7. Test results

**Full suite: 1076 passed, 0 failed, 0 skipped** in 44.72 s (baseline 996,
**+80**).

Targeted: `tests/test_report_generator.py tests/test_ui_report.py
tests/test_ai_services.py` → **150 passed**.

See `TEST_REPORT.md` for the case-by-case detail.

---

## 8. Known limitations

1. **No PDF library is installed**, so the tests parse the PDF with a small
   reader written for the suite (ASCII85 + Flate, `/ToUnicode` cmaps). It
   verifies the text layer, pagination, header repetition and font embedding,
   but it is not a general conformance validator.
2. **Tables overflow slightly at 404 px** on the app screens (a `right` edge
   about 22 px past the viewport on one table). The page itself does not scroll
   horizontally; the table is clipped inside its container. Cosmetic, app-side,
   not a PDF issue.
3. **`reports/phase-6/sample/` is committed** as the documented sample, while
   `output/reports/` is ignored. The test fixture writes into `tmp_path`, so a
   test run leaves no files behind.
4. **The stage strip no longer has any "Not available yet" stage**, because
   Phase 6 added the final one. Four existing tests were updated for that spec
   change.
5. **Browser QA covered one project** (Industrial / Warm Neutral, 400 × 520,
   fully placed). The `PARTIAL` and `FAILED` plan renderings are covered by
   unit tests, not by a live project.

---

## 9. Scope deviations

**None.** No V1 scope was added or removed; no excluded feature was touched; no
dependency was introduced; no architecture was changed. The four `ProjectResult`
fields are additive and defaulted, and are justified in §3.2.

---

## 10. Recommended next action

Proceed to **Phase 7 — Final QA**, per `DEVELOPMENT_PLAN.md`, once this phase is
approved. `NEXT_SESSION.md` lists the specific items to carry forward.
