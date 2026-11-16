# Phase 7 — QA Test Report

**Project:** Hometsy — Room Intelligence Studio
**Phase:** 7 (Quality assurance and interface polish)
**Date:** 16 November 2026
**Model under test:** `deepseek-ai/deepseek-v4.1-flash-1017`

All commands below were executed in this workspace. Nothing in this report is
projected, estimated or carried over as if it had been run again.

---

## 1. Headline result

| Metric | Result |
|---|---|
| Full suite | **1098 passed, 0 failed, 0 skipped** in 51.65 s |
| Phase 6 baseline | 1076 passed |
| Delta | **+22 tests** |
| Environment | Python 3.13.18, pytest 9.2.0 |
| Repeats | Two consecutive full runs, identical result |

Per-file versions in use: Streamlit 1.67.0, Pydantic 2.14.3, ReportLab 4.5.1,
Matplotlib 3.11.2.

**No existing test was deleted, weakened, skipped or retuned.** Every baseline
test name was checked against the current collection; all are present.

---

## 2. Accounting for the +22 delta

The delta is fully attributed. It is not a rounding artefact.

| Origin | Files | Tests |
|---|---|---|
| Earlier Phase 7 work (this phase, before the final session) | `test_ui_presentation.py` (+6 SVG text alternatives, +1 responsive CSS, +1 image alt text), `test_report_generator.py` (+2 heading), `test_ui_report.py` (+2 budget guard) | **12** |
| Final session (this report) | `test_ui_presentation.py` (+2 partial plan wording), `test_budget_engine.py` (+2 money format), `test_ai_services.py` (+5 evaluator prompt), `test_ui_evaluation.py` (+1 placement wiring) | **10** |
| **Total** | | **22** |

Cross-check against the Phase 6 per-file figures: `test_report_generator.py`
46→48, `test_ui_report.py` 25→27, `test_ai_services.py` 79→84 (all five of those
are from this session).

Per-file counts at time of writing:

| File | Tests |
|---|---|
| `tests/test_ui_presentation.py` | 44 |
| `tests/test_ui_report.py` | 27 |
| `tests/test_report_generator.py` | 48 |
| `tests/test_budget_engine.py` | 36 |
| `tests/test_ai_services.py` | 84 |
| `tests/test_ui_evaluation.py` | 26 |

---

## 3. Section results

Verdicts are evidence-based. "Re-run" means the command was executed in this
session; "earlier" means it was executed earlier in Phase 7 and is recorded here
with its original evidence, not re-executed without cause.

| # | Section | Result | Verdict | Evidence |
|---|---|---|---|---|
| A | Architecture audit | clean | **PASS** | earlier in Phase 7; no layering violation introduced by later work (verified by re-reading imports of every touched module) |
| B | Live Brief Analyzer | 5/5 | **PASS** | earlier in Phase 7; plus 4 further live brief analyses in the final session (see §5) |
| C | State integrity | 39/39 | **PASS** | earlier in Phase 7 |
| D | Placement / spatial | 39/39 | **PASS** | earlier in Phase 7 |
| E | Budget / evaluation | 41/41 | **PASS** | earlier in Phase 7; extended by the fixes in §6 |
| F | PDF structural | 35/35 | **PASS** | earlier in Phase 7 |
| F | PDF edge cases | 58/58 | **PASS** | earlier in Phase 7 |
| G | Accessibility probe | 38/38 | **PASS** | earlier in Phase 7 |
| H | PARTIAL placement | 1/3 live, 17/17 PDF | **PASS** | re-run live this session (§4.1) |
| H | Unpriced furniture | 18/18 | **PASS** | re-run this session (§4.2) |
| H | Long names / Turkish | 20/20 PDF, live UI clean | **PASS** | re-run this session (§4.3) |
| H | PDF regeneration / stale | live + 9 tests | **PASS** | re-run live this session (§4.4) |
| — | Responsive CSS | fixture only | **PARTIAL** | only 404 px is live-measurable; see §7 |
| — | UI/PDF comparison | 32/32 | **PASS** | earlier in Phase 7 |
| — | Live PDF validation | 28/28 | **PASS** | earlier in Phase 7 |
| — | Full regression | 1098/1098 | **PASS** | re-run twice this session |

---

## 4. Section H — completed in the final session

### 4.1 PARTIAL placement (live application)

Produced through the real interface, not a fixture: a 100 × 100 × 240 cm room
(`Küçük Oda`), Contemporary + Warm Neutral, 60.000 TRY, first concept.

The interface reported:

- `PARTIAL LAYOUT`, **1 of 3 requested items placed**, layout score 0.74
- `GEOMETRIC VALIDITY: Valid` — correct and independent of completeness
- `PARTIAL PLAN` badge, with the explanation that only placed items are drawn
- exactly **1** plan SVG, containing only the placed Bookshelf
- the two unplaced items (`Armchair`, `Floor lamp`) each reported with
  `copies_not_placed = 1`, its size, and the reason plus free floor area
- a note that unplaced copies stay in the basket, so the budget still counts them

Defect found and fixed here: the plan SVG's accessible title said *"Scaled plan
of the validated furniture layout"* for a partial plan, contradicting the
`PARTIAL PLAN` badge in the same view. Fixed in `ui/diagram.py` by adding a
`partial` flag; `ui/pages_plan.py` now passes `outcome.is_partial`. Verified
live: the title now reads *"Scaled plan of the partly placed furniture
layout"* and the description states that some requested items could not be
placed (§6.3).

### 4.2 Unpriced furniture

`probe_unpriced.py` — **18/18**.

| Surface | Finding |
|---|---|
| Budget engine | `is_trustworthy == False`; `unpriced_errors == ("ghost_sofa",)`; the unpriced reference produces **no** zero-cost line; no line total is zero |
| Totals | the subtotal covers only the priced item; the error names the reference that was not priced |
| AI evaluation input | `"is_complete": false`; no `material_subtotal` key; the materials note states the cost is unknown; the contract forbids calling materials free |
| PDF | states "The estimate is incomplete", "not a final figure", names `ghost_sofa`, marks the entry "Not priced · Excluded", and contains **no standalone zero-amount money figure** |

The PDF's rendered text was read back directly:
`Not priced — excluded from furniture cost total. The application has no
material price list, so material cost is unknown rather than zero`.

### 4.3 Long names, long brief, Turkish characters

`probe_long_turkish.py` — **20/20**, plus live UI verification.

| Value | Length | Result |
|---|---|---|
| Room name | 76 chars (limit 80) | renders in full, wraps to two lines, no clipping at 404 px |
| Brief (notes) | 383 chars | stored and rendered in full; last words `geçiş yolu.` present |
| Turkish glyphs | `Şişli`, `Küçük`, `Çalışma`, `İğdırlı`, `Güneş`, `meşe`, `keten`, `yün` | all survive into the PDF text layer; **no** U+FFFD replacement characters |
| Longest token | measured with ReportLab metrics | narrower than the printable frame |

The bundled DejaVu faces are registered at generation time, and the report
raises a clear error if they are missing, so Turkish is covered by design rather
than by luck. A hostile room name containing `<script>` and quotes also produced
a readable PDF with the literal text preserved.

### 4.4 PDF regeneration and stale artefacts

Live sequence in the running application:

1. Generated a report → **78,181 bytes, 14 pages**, download offered, message
   "The PDF has been generated (78,181 bytes)".
2. Changed the budget **60.000 → 45.000 TRY** in Design Preferences.
3. The workflow cascaded **from 10 of 10 steps back to 2 of 10**, the stored
   result was discarded, and the Final Report screen went back to `NOT STARTED`.
4. The download button and the generated message were **gone**; the old file was
   no longer presented as current.
5. Walking forward to the report screen again required regenerating the project.

No needless regeneration: `test_a_rerun_does_not_generate_a_second_pdf` asserts
`generator.call_count == 1` across two extra reruns and byte-identical output;
the live run confirmed the file on disk was not rewritten by navigation.

---

## 5. Live API results (kept separate from mocked tests)

All automated tests are mock-only and open no socket. The live calls below were
made deliberately, through the real interface, against
`deepseek-ai/deepseek-v4.1-flash-1017`.

| # | Operation | Input | Result |
|---|---|---|---|
| 1–5 | Brief analysis | five Section B scenarios | earlier in Phase 7, 5/5 |
| 6 | Brief analysis | Şişli salonu | earlier in Phase 7 |
| 7 | Brief analysis | Şişli, over-budget variant | earlier in Phase 7 |
| 8 | Brief analysis | Küçük Oda (100×100) | earlier in Phase 7 |
| 9 | Brief analysis | 383-char Turkish brief | **PASS**, ~28 s, no truncation |
| 10 | Concept generation | same project | **PASS**, 3 concepts specific to the Turkish brief |
| 11 | Furniture advisor | same project | **PASS**, 7 catalog items, all references valid |
| 12 | Design evaluation | same project | **PASS**, produced honest critique and the corrected materials wording |

Every live run returned schema-valid output on the first attempt; none required
the correction path. **The four live calls in this session were made from the
real UI; no credentials are stored in or printed by any test.**

---

## 6. Defects found and fixed

### 6.1 Engine warnings used a different money format from the UI

**Symptom.** `core/budget_engine.py` formatted overruns as `{abs(remaining):.2f}`,
producing `3400.00 TRY`, while the same screen rendered `3.400,00 TRY` beside it.
`st.warning()` prints engine text verbatim, so one screen showed two formats.

**Fix.** Added `format_money` to `core/budget_engine.py`; both
`ui/commits.format_money` and `core/report_generator.format_money` now delegate
to it, so there is one implementation instead of three. The two warning
sentences use it.

**Tests.** `test_the_overrun_warning_states_its_figure_in_the_ui_format`,
`test_a_zero_budget_overrun_states_its_figure_in_the_ui_format`.
**Mutation:** reverting to `{abs(remaining):.2f}` fails the new test and only the
new test (1 failed, 35 passed).

### 6.2 The evaluation implied materials were free

**Symptom.** The evaluator prompt sent `"material_subtotal": "0.00"`. A live run
wrote: *"the material subtotal of 0.00 means those finishes are not yet
represented in the costed scheme"* — reading as a settled zero, not an absence of
pricing. This is precisely the wording `AGENTS.md` §8 forbids.

**Fix.** The zero subtotal is no longer sent. `_budget_block` replaces it with
`materials_pricing: <note>` stating the cost is unknown rather than zero, and
keeps `material_subtotal` only when it is genuinely non-zero. The contract gains
an explicit rule, and the role text already forbids arithmetic by the model.

**Tests.** `test_evaluator_is_told_materials_are_not_priced_rather_than_zero`,
`test_a_real_material_cost_is_still_reported` (guards the opposite mistake).

**Live confirmation.** The regenerated evaluation now reads: *"Materials and
finishes are not priced by this application, so their cost is unknown and is not
part of the 36,800.00 TRY figure."* The string `material subtotal of 0.00` does
not occur.

### 6.3 The plan SVG overclaimed validation for a partial layout

**Symptom.** `ui/diagram.py` always emitted `<title>Scaled plan of the validated
furniture layout`, including when the page showed a `PARTIAL PLAN` badge.

**Fix.** Added a keyword-only `partial` flag; the title becomes *"Scaled plan of
the partly placed furniture layout"* and the description adds a sentence stating
that some requested items could not be placed. Geometry is untouched.

**Tests.** `test_a_partial_plan_describes_itself_as_partly_placed_not_validated`,
`test_a_complete_plan_is_not_described_as_partial`.
**Mutation:** forcing the validated wording fails exactly the new test
(1 failed, 43 passed), then restores byte-identically.

### 6.4 The evaluator was never told a layout was incomplete

**Symptom.** A live evaluation called a one-of-three layout *"buildable as
calculated"*. The evaluator received the geometry verdict but not the placement
verdict, and a geometrically valid layout can still be missing furniture.

**Fix.** Added a `PlacementOutcome` block to the prompt (status, whether every
requested item was placed, placed/requested counts, and each unplaced item with
its reason), threaded `placement=` from `pages_evaluation` through
`ui.ai_actions`, and added a contract rule not to call an incomplete layout fully
buildable. When no outcome is stored the block says `recorded: false` rather than
implying completeness.

**Tests.** `test_evaluator_is_told_when_the_layout_left_items_out`,
`test_a_complete_layout_is_not_flagged_as_incomplete`,
`test_an_unrecorded_layout_is_stated_as_unrecorded`,
`test_the_stored_layout_outcome_is_sent_to_the_evaluator`.
**Mutation:** removing `placement=state.placement` from the page fails exactly
the new UI test (1 failed, 25 passed).

---

## 7. Known limitations of this QA

1. **Only one viewport could be measured live.** The desktop browser exposes no
   resize control, and the Playwright relay at `127.0.0.1:19988` was unreachable,
   so the live application was measured at **404 px only** (`clientWidth` 404,
   `pageOverflow` 0). Wider and intermediate widths were measured on an
   HTTP-served CSS fixture on port 8513. That fixture evidence is **not** a real
   browser test and is not presented as one.
2. **The hot-reload `TypeError` is a development artefact, not a product defect.**
   Editing a `.py` file while Streamlit runs can leave the session holding a
   stale `WorkflowState` class, producing
   `The session contains a value that is not a WorkflowState under
   'hm_workflow_state'`. It reproduced twice immediately after source edits and
   never in a fresh process; a restart cleared it every time. No released code
   path can trigger it.
3. **`\x7f` bytes in extracted PDF text.** The text extractor returns 0x7F where
   the PDF uses a private-use bullet glyph. The count was identical (62) in a
   report generated before today's changes, so this is pre-existing extraction
   behaviour, not a regression.
4. **Live API tests are not part of `pytest`.** They are manual, deliberate runs
   reported in §5, because the suite must not require a credential.

---

## 8. Commands used

```text
# Full regression (run twice)
.venv\Scripts\python.exe -m pytest -q
  -> 1098 passed in 51.65 s

# Targeted groups
.venv\Scripts\python.exe -m pytest tests/test_report_generator.py \
    tests/test_ui_report.py tests/test_ui_presentation.py \
    tests/test_ai_services.py tests/test_ui_evaluation.py \
    tests/test_budget_engine.py -q
  -> 265 passed in 16.90 s

# Section H probes
.venv\Scripts\python.exe -X utf8 <temp>\probe_failed_heading.py    -> 17/17
.venv\Scripts\python.exe -X utf8 <temp>\probe_unpriced.py          -> 18/18
.venv\Scripts\python.exe -X utf8 <temp>\probe_long_turkish.py      -> 20/20
.venv\Scripts\python.exe -X utf8 <temp>\probe_live_long_pdf.py     -> 12/12
```

Streamlit start check: server on port 8512, log clean, no traceback.
Browser smoke: title correct, `pageOverflow` 0, media query present, no
`Traceback` in the page.
