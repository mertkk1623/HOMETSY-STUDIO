# Phase 7 — Completion Report

**Project:** Hometsy — Room Intelligence Studio
**Phase:** 7 (Quality assurance and interface polish)
**Date:** 16 November 2026
**Scope:** QA only. No new features, no new dependencies, no architectural change.

---

## 1. Objective

Complete Phase 7 QA for the approved V1: finish the outstanding Section H
scenarios, resolve the two known cosmetic findings, run the full regression
against the 1076-test baseline, and record evidence-based verdicts suitable for a
release decision.

---

## 2. What was done

### 2.1 Remaining Section H scenarios — completed

| Scenario | How | Verdict |
|---|---|---|
| PARTIAL placement | real UI, 100×100 cm room → 1 of 3 placed | **PASS** |
| Unpriced furniture | engine + prompt + PDF, 18 checks | **PASS** |
| Long names / long brief / Turkish | PDF 20 checks + live UI | **PASS** |
| PDF regeneration / stale artefacts | live invalidation + existing suite | **PASS** |

### 2.2 Two known cosmetic findings — fixed

| Finding | Fix | Regression test |
|---|---|---|
| Engine warnings printed `12700.00 TRY` where the UI printed `12.700,00 TRY` | one shared `format_money` in `core.budget_engine`, delegated to by `ui.commits` and `core.report_generator` | 2 tests |
| Evaluation described unpriced materials as a `0.00` subtotal | the zero subtotal is withheld; a note says cost is unknown, not zero; contract forbids the wording | 2 tests |

### 2.3 Two further defects found during Section H — fixed

These were found by the QA rather than assumed, and each was reproduced before
being fixed:

| # | Defect | Severity | Fix |
|---|---|---|---|
| 1 | Plan SVG title said *"Scaled plan of the validated furniture layout"* for a **partial** plan, contradicting the page's own `PARTIAL PLAN` badge | medium (accessibility overclaim; same class as the PDF heading already fixed) | `partial` flag in `ui/diagram.py`, passed from `ui/pages_plan.py` |
| 2 | The evaluator was never told a layout was incomplete; a live run called a 1-of-3 layout *"buildable as calculated"* | medium (misleading AI output) | placement block added to the prompt, threaded from the page |

Defect 2 is the significant finding of this phase: the deterministic geometry
verdict was correct, and the *interpretation* of it was wrong because the
interpreter lacked the completeness fact. That separation is exactly what the
architecture is meant to protect, so the fix restores a missing input rather than
filtering output.

---

## 3. Files created or modified

### Modified — application code

| File | Change |
|---|---|
| `core/budget_engine.py` | added `format_money`; both warning sentences now use it |
| `core/report_generator.py` | `format_money` delegates to the engine implementation |
| `ui/commits.py` | `format_money` delegates to the engine implementation |
| `ui/diagram.py` | `placement_plan_svg(..., partial=False)`; title and description no longer claim validation for a partial plan |
| `ui/pages_plan.py` | passes `partial=outcome.is_partial` |
| `ai/design_evaluator.py` | materials note replaces the zero subtotal; placement block; two new contract rules; `placement` parameter |
| `ui/ai_actions.py` | `placement` parameter forwarded |
| `ui/pages_evaluation.py` | passes `state.placement` |

### Modified — tests

| File | Added |
|---|---|
| `tests/test_ui_presentation.py` | 2 (partial wording, plus negative) |
| `tests/test_budget_engine.py` | 2 (both warnings' format) |
| `tests/test_ai_services.py` | 5 (materials ×2, placement ×3) |
| `tests/test_ui_evaluation.py` | 1 (placement forwarded) |

### Created — reports

- `reports/phase-7/TEST_REPORT.md`
- `reports/phase-7/COMPLETION_REPORT.md`
- `reports/phase-7/RELEASE_READINESS.md`
- `reports/phase-7/NEXT_SESSION.md`

### Created — throwaway probes (outside the repository)

In `C:\Users\[LOCAL_USER]\AppData\Local\Temp\opencode\`:
`probe_failed_heading.py`, `probe_unpriced.py`, `probe_long_turkish.py`,
`probe_live_long_pdf.py`. These are QA instruments, deliberately kept out of the
project tree because they are not part of the product or its test suite.

---

## 4. Tests performed

| Check | Result |
|---|---|
| Targeted groups (6 files) | 265 passed |
| Full suite | **1098 passed, 0 failed, 0 skipped** (51.65 s) |
| Repeats | two consecutive full runs, identical |
| Mutation checks | 4 performed, each killed exactly the intended test |
| Streamlit start | clean, no traceback |
| Browser smoke | 404 px, `pageOverflow` 0, no traceback |
| PDF smoke | 3 placement states, 17/17 |

Mutation evidence:

| Mutation | Expected failure | Observed |
|---|---|---|
| partial title reverted to "validated" | the new wording test | 1 failed, 43 passed |
| warning reverted to `:.2f` | the new format test | 1 failed, 35 passed |
| `placement=` removed from the page | the new UI wiring test | 1 failed, 25 passed |
| heading fix reverted (earlier phase 7) | the heading tests | recorded earlier |

---

## 5. Known issues

1. **Live measurement at a single viewport.** The desktop browser cannot be
   resized and the Playwright relay was unreachable, so live layout was measured
   only at 404 px. Other widths rest on an HTTP-served CSS fixture, which is
   weaker evidence and is labelled as such. This is a limitation of the QA
   environment, not a product defect, but it does mean the responsive design is
   **not** fully verified on real hardware.
2. **No browser-based accessibility audit.** Section G was a structural probe
   (semantics, labels, alt text, unique ids), not a screen-reader or axe run.
   Accessibility is improved and structurally verified, not certified.
3. **`material_subtotal` remains in the budget model.** V1 has no material price
   list, so it is always zero from the UI path. The PDF and the evaluator now
   describe this correctly, but the field's presence still invites the
   misreading that was fixed. Removing it would change a core model and is out of
   scope for QA.

---

## 6. Scope adherence

- No feature was added; no excluded feature was introduced.
- No dependency was added.
- No core data model's shape changed. `PlacementOutcome` was already stored on the
  workflow state; it is now read by one more consumer.
- No Git repository was initialised, and nothing was committed, pushed or
  deployed.
- Existing tests were not deleted, weakened or retuned.

### Deliberate deviations

None from the approved documentation. The additional fixes in §2.3 are
corrections to behaviour that contradicted `AGENTS.md` §8 (never present
illustrative data as verified, never let AI assert what Python should decide) and
§12 (do not claim more than the evidence supports).

---

## 7. Recommended next action

Phase 8, per `DEVELOPMENT_PLAN.md`: interface polish and final validation. Before
that, the two items in `RELEASE_READINESS.md` §5 that are genuinely open — real
multi-viewport verification and a real accessibility pass — should be scheduled,
because they are the only categories that are *not* fully verified.
