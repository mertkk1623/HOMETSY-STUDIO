# Phase 8 — Completion Report

**Project:** Hometsy — Room Intelligence Studio
**Phase:** 8 — Interface polish and release preparation
**Completed:** 16 November 2026
**Scope:** Close the two Phase 7 evidence gaps (real multi-viewport browser
measurement, real accessibility scan), implement the five highest-impact UX
fixes, and prepare the portfolio release (README, screenshots).

---

## 1. Verdict

> **PASS**, with one item recorded as **NOT VERIFIED** by design.

Every Phase 8 objective was met and evidenced. The one item that cannot be
claimed is real screen-reader verification (§7.1): no assistive technology was
driven, so the report says so instead of overstating the automated axe result.

The two Phase 7 PARTIALs are now **PASS**:

| Phase 7 item | Was | Now |
|---|---|---|
| Responsive layout | PARTIAL — 404 px live, wider widths from a CSS fixture | **PASS** — 7 widths measured in the real browser |
| Accessibility | PARTIAL — 38 structural probes, no real audit | **PASS** (automated) — real axe-core, 0 violations on 9 screens |

---

## 2. Objective

The Phase 7 `RELEASE_READINESS.md` verdict was *"ready for Phase 8, not yet
ready for portfolio publication"*, on the grounds that both remaining gaps were
**evidence** gaps rather than known defects. Phase 8 had to produce that
evidence, then improve the interface using what the evidence showed, then
prepare the release artefacts.

Phase 8 had four work items:

- **A1** — real multi-viewport measurement at 1440, 1024, 768, 430, 404, 390,
  360 px, recorded separately from any CSS-fixture evidence.
- **A2** — a real axe-core (or equivalent) accessibility scan, manually
  triaged, with no blind fixing of false positives and no WCAG certification
  claim.
- **B** — exactly five highest-impact UX problems, identified from the live
  interface, planned, and **implemented** with targeted tests.
- **C** — `README.md` / `README.tr.md` with equivalent content, and real
  screenshots in `docs/screenshots/`.

---

## 3. A1 — Responsive behaviour: PASS

### Instrument

The Phase 7 report recorded that "the desktop browser exposes no resize control
and the Playwright relay at `127.0.0.1:19988` was unreachable". That was
re-diagnosed and disproved this phase: the relay **does** support
`page.setViewportSize()`. Verified by
1440 → `innerWidth` 1440 and 390 → `innerWidth` 390, with `outerWidth`
unchanged — i.e. a real viewport change, not a CSS zoom.

No dependency was added. The measurement runs against the live application on
`http://127.0.0.1:8512`.

### Measurement

Measured on the **design plan screen**, which is the widest and most complex
layout in the product (SVG plan, two wide tables, metric cards, stage strip).

| Viewport | Page overflow | `<main>` overflow | Elements outside plan frame | Frame width | Drawing width | Scale | Label size | Frame scrolls | Focusable |
|---|---|---|---|---|---|---|---|---|---|
| 1440 | no | no | 0 | 999 | 973 | 1.52 | 13.68 px | no | `tabindex=0` |
| 1024 | no | no | 0 | 583 | 640 | 1.00 | 9.00 px | yes | `tabindex=0` |
| 768 | no | no | 0 | 447 | 640 | 1.00 | 9.00 px | yes | `tabindex=0` |
| 430 | no | no | 0 | 390 | 640 | 1.00 | 9.00 px | yes | `tabindex=0` |
| 404 | no | no | 0 | 364 | 640 | 1.00 | 9.00 px | yes | `tabindex=0` |
| 390 | no | no | 0 | 350 | 640 | 1.00 | 9.00 px | yes | `tabindex=0` |
| 360 | no | no | 0 | 320 | 640 | 1.00 | 9.00 px | yes | `tabindex=0` |

**No horizontal page scroll at any width.** The zero "elements outside plan
frame" column is the important one: the drawing is wider than its frame below
1024 px, but that overflow is contained inside the frame's own scroll box, so
nothing pushes the page.

### What changed to achieve this

1. **Plan label legibility.** The drawing is a 640-unit viewBox. Scaling it to a
   350 px phone frame rendered 9-unit labels at **4.56 px** — unreadable.
   `.hm-plan-frame` now keeps the drawing at a 640 px floor and scrolls
   sideways inside itself. Labels render at **9.00 px** instead of 4.56 px.
2. **Scrollable-region focusability.** The new scroll box triggered a real axe
   violation (`scrollable-region-focusable`). The frame now carries
   `tabindex="0" role="group"` and an `aria-label` that tells the user it
   scrolls.
3. **Mobile stage strip.** Five stacked stage cards took 221 px of an 844 px
   viewport (26%) before the page title appeared. A `max-width: 640px` block
   turns the strip into a 2-column grid.
4. **Money value wrapping.** A metric value broke after the decimal comma
   ("41.800," / "00 TRY") because a comma is a permitted line-break. The value
   is now `white-space: nowrap`, with a 21 px size in the narrow-screen block so
   it cannot overflow its card.

### Evidence type

These are **real browser measurements**, not CSS-fixture measurements. The
fixture from Phase 7 is no longer used as evidence. Two screenshot pairs
captured at phone width are in `docs/screenshots/`:
`19-plan-mobile-390.png` and `20-budget-mobile-390.png`.

---

## 4. A2 — Accessibility: PASS (automated); NOT VERIFIED (screen reader)

### Instrument

axe-core 4.10.2, injected into the live page and run with the WCAG 2.0/2.1 A +
AA and `best-practice` rule sets, on **nine distinct screens** in the states that
matter:

landing · room · preferences · review · brief (before AI / after AI) ·
concepts (before / generated / selected) · plan (before advisor / built) ·
evaluation (before AI / after AI) · budget · report.

The tool is an **external QA instrument** at
`C:\Users\[LOCAL_USER]\AppData\Local\Temp\opencode\axe.min.js`. It is **not** a project
dependency and is not installed into the repository.

### Baseline (before Phase 8 fixes)

Real violations, not theoretical:

| Rule | Impact | Screens | Detail |
|---|---|---|---|
| `color-contrast` | serious | 4 | `success` token `#66816A` at **3.62:1**; `text_secondary` `#6E7069` at **4.25:1** — both under the 4.5:1 AA minimum, on 11 px uppercase badge text that gets no large-text exemption. (axe reported 3.61 and 4.24; the gap is rounding between two implementations of the same WCAG formula.) |
| `image-alt` | serious | 1 (budget) | The Matplotlib cost chart rendered as a bare `<img>` with no `alt` |
| `scrollable-region-focusable` | serious | 1 (plan) | Introduced by my own 640 px scroll rule; caught and fixed |

### Final state

**Zero violations on all nine screens**, every state.

### Fixes

**Contrast.** Both palettes — `ui/theme.py:COLORS` and
`core/report_generator.py:PALETTE` — now use:

| Token | Before | After | Ratio on muted surface |
|---|---|---|---|
| `text_secondary` | `#6E7069` (4.25:1) | `#5A5C56` | 5.73:1 |
| `success` | `#66816A` (3.62:1) | `#4F6A53` | 5.05:1 |
| `warning` | — | `#8A602C` | 4.69:1 |
| `error` | — | `#A44A40` | 4.89:1 |

A test asserts that the two palettes are **equal**, so the PDF cannot drift from
the screen.

**Chart alternative text.** `ui/pages_budget.distribution_alt_text()` is a
separate, importable function that names the chart type, the currency and every
bar's value, then points at the table holding the same figures. It is passed to
`st.pyplot(..., alt=...)`.

### Manual triage

Findings were triaged rather than blindly fixed. Specifically **not** changed:

- **Streamlit's own chrome** (the sidebar collapse control, the "Press Enter to
  apply" hint). Vendor UI; not our markup to restyle, and the violations were in
  `color-contrast` on vendor elements that disappeared once our palette changed.
- **`region` best-practice warnings** on the vendor top bar. Streamlit owns that
  landmark structure.
- **Decorative swatches and the plan legend.** They are correctly marked
  `aria-hidden="true"` because the adjacent text carries the meaning; axe agreed
  once the pattern was consistent.
- **The 45×45 cm unlabelled block.** Not a defect: the block is too small for
  text at plan scale, and the full name is in the table.

### What is still not verified

**No real screen reader was driven.** No NVDA, JAWS, VoiceOver or TalkBack
session is part of this evidence. axe-core checks structure, names, roles and
contrast; it does not check whether the announcement *order* or the *wording* is
usable. That remains a genuine gap and is recorded as such in
`RELEASE_READINESS.md` §7.1 and in both READMEs.

**No WCAG conformance is claimed.** "Zero axe violations across nine screens" is
what the evidence supports. It is not a certification, and the reports never
say otherwise.

---

## 5. B — Five UX problems, identified and fixed

The five problems were chosen from the live interface, written up in
`reports/phase-8/UI_PLAN.md`, and then **implemented**. The plan is not a
wishlist; each item has code and a test behind it.

### 1. Contradictory progress vocabulary *(fixed)*

**Problem.** One screen showed three different progress counts. The header said
"1 of 10 steps complete" (internal model), the room page said "Step 1 of 2",
the brief page said "Design Concepts · step 1". A reviewer could not tell what
"step" meant, or which one they were on.

**Fix.** `ui/shell.py` gained `stage_position()`, `stage_eyebrow()` and a single
`STAGES` table. The header now reports "N of 5 stages complete"; every one of the
nine pages uses `stage_eyebrow(<stage>) + " · <sub-label>"`. The internal
`STEP_ORDER` import was removed from the presentation layer.

**Verified live:** "1 of 5 stages complete" beside "STAGE 2 OF 5 · INPUTS".

**Tests:** `test_the_shell_reports_stages_not_internal_steps`,
`test_every_workflow_screen_numbers_itself_with_the_same_vocabulary`,
`test_no_page_still_numbers_itself_against_internal_steps` (asserts the old
strings are gone from the source, not merely unused).

### 2. Stale landing copy *(fixed)*

**Problem.** The first page a reviewer reads claimed "the concept, plan and
report stages follow in later development steps" — about three stages that all
work. The hero also advertised a *four*-step journey while the shell shows
*five* named stages. `AGENTS.md` §10 forbids presenting implemented features as
planned.

**Fix.** The start note was rewritten to describe what actually happens, and the
hero flow line is now generated from `ui.shell.STAGES`, so the landing page
cannot advertise a journey the product does not walk.

**Verified live:** hero reads "Room Setup → Design Preferences → Design Concepts
→ Design Plan → Final Report".

**Tests:** `test_the_landing_page_does_not_call_implemented_stages_future_work`,
`test_the_landing_page_advertises_the_journey_the_shell_actually_walks`.

### 3. Real contrast failures *(fixed)*

Covered in §4 above. This was a genuine WCAG AA failure on 11 px text, found by
a real scan, not a stylistic preference.

**Tests:** `test_the_status_tokens_clear_the_aa_contrast_minimum` (a real WCAG
luminance implementation, parameterised over four tokens × three surfaces),
`test_the_text_primary_and_primary_tokens_also_clear_the_minimum`,
`test_the_pdf_palette_matches_the_interface_palette`.

### 4. Unlabelled chart *(fixed)*

The Matplotlib cost chart was a bare `<img>`. A screen-reader user heard an
unnamed graphic and every figure in it was unreachable. Covered in §4.

**Tests:** `test_the_cost_chart_carries_alternative_text_naming_every_bar`,
`test_the_cost_chart_alt_text_states_a_value_for_each_bar`.

### 5. Illegible plan labels *(fixed)*

**Problem.** Two separate defects, both found by looking at the drawing:

- At 390 px the labels rendered at **4.56 px** because the whole 640-unit
  drawing was scaled down into a 350 px frame.
- Where a block was narrow, the label was **truncated to its first word**. The
  result was "Floor", "Coffee", "Side" — each of which names a *different piece
  of furniture* than the one drawn.

**Fix, part 1 — legibility.** The frame keeps the drawing at its own scale and
scrolls (see §3).

**Fix, part 2 — meaning.** `ui/diagram.py` now has `_wrap_label()` and
`_label_for(available=, max_lines=)`. A name that does not fit on one line
wraps onto a second `<tspan>`; only a name needing more lines than the block
allows gets no label. **Labels are never truncated to a fragment.** The label
decision is made from the *drawn* width in user units, not from the physical
centimetres, because the same 90 cm sofa is drawn at different widths in a small
and a large room.

**Verified live** at 1440 px: `Two-seat sofa`, `Armchair`, `Coffee/table`,
`Side/table`, `Floor/lamp`, `Large area rug` — every block that can hold a
label is labelled, and no label is a bare first word.

**Test:** `test_the_drawn_label_never_overruns_its_block_at_phone_scale` is the
end-to-end assertion — every drawn line, at every block, fits the block drawn
for it.

### Deliberately not changed

Recorded so the omissions are decisions, not oversights:

- Streamlit's vendor chrome.
- The single-column 1440 px layout — it is a deliberate reading-width choice, not
  an unfinished grid.
- The five summary cards on the plan screen — they answer five different
  questions and are not a decorative row.
- `st.multiselect` free-text entry for materials — the alternative was a
  hardcoded list, which would have narrowed the user's expression.
- The 10-step internal model — it is the correct internal vocabulary; only the
  *presentation* was wrong.
- A 45×45 cm block with no label — correct behaviour at plan scale.

### The "Next:" hint, kept but conditioned

A `next_action_hint()` was drafted to name the next outstanding step. It was
**kept and wired in**, but suppressed when the outstanding step belongs to the
stage already on screen — otherwise it would put a generic "Next: Budget
analysis." above a budget screen that already says something more specific. What
remains is the case the pages cannot cover themselves: the user has moved ahead
while an earlier stage went stale.

**Verified live:** it appears as "Next: Brief analysis." on the review screen and
"Next: Furniture and material recommendations." on concepts-after-selection, and
correctly disappears on each stage's own pages.

---

## 6. C — Release artefacts

### Screenshots

20 screenshots captured from the **running application**, in
`docs/screenshots/` (1.93 MB total):

| File | Screen |
|---|---|
| `01-landing.png` | Landing page |
| `02-room-setup.png` | Room setup |
| `03-design-preferences.png` | Design preferences |
| `04-project-review.png` | Project review |
| `05-brief-before-ai.png` | Brief, before analysis |
| `06-brief-analysed.png` | Brief, analysed |
| `07-concepts-before-ai.png` | Concepts, before generation |
| `08-design-concepts.png` | Three concepts |
| `09-concept-selected.png` | Concept selected |
| `10-plan-before-advisor.png` | Plan, before the advisor |
| `11-design-plan.png` | Design plan |
| `12-plan-drawing.png` | Plan drawing, to scale |
| `13-spatial-validation.png` | Spatial validation |
| `14-evaluation-before-ai.png` | Evaluation, before AI |
| `15-design-evaluation.png` | Design evaluation |
| `16-budget-analysis.png` | Budget analysis |
| `17-cost-distribution.png` | Cost distribution chart |
| `18-final-report.png` | Final report, PDF ready |
| `19-plan-mobile-390.png` | Plan at 390 px |
| `20-budget-mobile-390.png` | Budget at 390 px |

**No mockups and no fabricated images.** Every file is a browser capture of
`http://127.0.0.1:8512` against the final build. The whole set is from one
continuous session, so the data is consistent across screens (room "Sisli Living
Room", 400 × 500 cm, Japandi, 42.200,00 TRY) and is real output from a real live
AI run during this phase. `01-landing.png` was recaptured after the roadmap badge
fix (§7.2); the rest of the set was unaffected by it.

### README

`README.md` (19,560 B) and `README.tr.md` (20,828 B), both UTF-8, LF, no BOM.
They contain equivalent information: purpose, features, screenshots,
architecture, the AI/Python split, stack, installation, configuration, running,
workflow and invalidation, tests, data and asset licensing, known limitations,
accessibility and responsive status, and the V1/V2/V3 roadmap.

Every claim in them was checked against the code:

- The stack table matches `requirements.txt` and the installed versions.
- The test count (1,123) matches the final full-suite run.
- The "no Streamlit in `core`/`ai`/`workflow`/`models`" claim was verified by
  scanning the imports: only `pydantic` and `reportlab` appear as non-stdlib,
  and the single `streamlit` string in `workflow/__init__.py` is a docstring
  describing its *absence*.
- The catalog (20 items) and the style/palette counts (6/4) were read from
  `data/*.json`.
- The asset licensing statement matches `assets/source_manifest.json` and
  `data/asset_replacements.json`.
- All 14 screenshot links resolve to real files.

---

## 7. Deviations, and why

### 7.1 No real screen-reader session — NOT VERIFIED

The Phase 8 brief asked for a real accessibility scan "or equivalent". axe-core
was available and was used, but a real screen-reader session was not run. Rather
than skip accessibility or overstate the automated result, accessibility is
recorded as **PASS (automated, zero violations) + NOT VERIFIED (screen reader)**,
and both READMEs state the same.

### 7.2 Three additional defects were found and fixed

The brief named five UX problems. Three further real defects surfaced during
verification and were fixed rather than shipped:

- **`scrollable-region-focusable`** — my own 640 px scroll rule created a scroll
  container no keyboard user could pan. Fixed with `tabindex="0"`.
- **Money value breaking after the decimal comma** — "41.800," on one line and
  "00 TRY" on the next, because Unicode permits a break at a comma. Fixed with
  `white-space: nowrap` plus a smaller size on narrow screens.
- **The roadmap called the finished release unfinished.** While re-reading the
  captured landing screenshot it was still badged **"In development"**, with the
  note "V1 is the only version under development" — after V1 had been completed,
  documented as complete in both READMEs, and assessed as release-ready. This is
  the same stale-copy defect class as problem 2, one section further down the
  same page, and it was missed when problem 2 was fixed. The V1 card now reads
  **"Complete"**, V2 and V3 read **"Planned"**, the badge text comes from a
  `BADGE_LABELS` mapping keyed by the card's own state, and
  `test_the_roadmap_does_not_call_the_finished_version_unfinished` pins the
  absence of both old phrasings.

All three were found by looking at the rendered product, all three have
regression tests, and none expands scope. `01-landing.png` was recaptured so the
published screenshot shows the corrected badge rather than the stale one.

### 7.3 The plan caption was corrected

The caption still said labels "are shortened on small blocks" after the
truncate-to-first-word behaviour was replaced with wrapping. The caption in both
`ui/diagram.py` and `core/report_generator.py` now describes what the renderer
actually does. A test pins it.

### 7.4 No dependency was added

Phase 8 added **no** runtime or test dependency. axe-core is an external QA
instrument outside the repository. `requirements.txt` is unchanged.

### 7.5 No architecture, AI-contract or engine change

The AI contract, the four operations, the deterministic geometry and the budget
arithmetic are untouched. Every Phase 8 change is in `ui/` presentation, plus
two palette literals and two caption strings.

---

## 8. Phase 7 fixes — regression check

All five Phase 7 fixes were re-verified as still in place:

| Fix | Status |
|---|---|
| Single `format_money` in `core/budget_engine` | intact |
| Evaluator withholds the zero material subtotal | intact |
| Evaluator receives a placement block | intact |
| `placement_plan_svg(partial=...)` never says "validated" | intact |
| Three-way PDF plan heading | intact |
| Budget-snapshot guard | intact |

---

## 9. Files created and modified

### Created

| File | Purpose |
|---|---|
| `README.md` | Portfolio README (English) |
| `README.tr.md` | Portfolio README (Turkish, equivalent) |
| `docs/screenshots/` (20 files) | Real application screenshots |
| `reports/phase-8/UI_PLAN.md` | The five problems and the plan |
| `reports/phase-8/COMPLETION_REPORT.md` | This report |
| `reports/phase-8/TEST_REPORT.md` | Test evidence |
| `reports/phase-8/RELEASE_READINESS.md` | Final release verdict |
| `reports/phase-8/NEXT_SESSION.md` | The one outstanding item and the Phase 9 handover |

### Modified

| File | Change |
|---|---|
| `ui/shell.py` | `STAGES`-based `stage_position`, `stage_eyebrow`, conditioned `next_action_hint`; header reports stages |
| `ui/theme.py` | Contrast `COLORS`; `.hm-plan-frame` scroll + 640 px floor; narrow-screen stage grid; metric `nowrap` + phone size |
| `ui/diagram.py` | `_wrap_label`, `_label_for(available=, max_lines=)`, `<tspan>` rendering, corrected caption |
| `ui/pages_plan.py` | Focusable plan frame (`tabindex`, `role`, `aria-label`) |
| `ui/pages_budget.py` | `distribution_alt_text()`; `st.pyplot(..., alt=...)` |
| `ui/pages_landing.py` | Corrected start note; hero flow from `ui.shell.STAGES`; roadmap badges from `BADGE_LABELS` (V1 now "Complete") |
| `ui/pages_*.py` (9 files) | Unified `stage_eyebrow` vocabulary |
| `core/report_generator.py` | `PALETTE` mirrors `ui.theme.COLORS`; corrected plan caption |
| `DESIGN_SYSTEM.md` | §3 palette table carries the Phase-8 contrast note |
| `tests/test_ui_presentation.py` | +22 tests (contrast, plan frame, labels, metric wrapping, caption) |
| `tests/test_ui_app.py` | +6 tests (stage vocabulary, landing copy, roadmap status) |
| `tests/test_ui_budget.py` | +2 tests (chart alt text) |

### Not modified

`ai/`, `core/` engines (geometry, placement, spatial, budget), `models/`,
`workflow/`, `requirements.txt`, `.streamlit/config.toml`, all `data/` and
`assets/`.

---

## 10. Known issues and limitations

1. **No real screen-reader verification.** See §7.1.
2. **AI truncation is a live-model property.** During this phase the advisor call
   was truncated once ("The AI answer was cut off before it finished"). The
   application reported it as an error and stored nothing — correct behaviour —
   and the retry succeeded. This is model-side variance, not an application
   defect; `max_tokens` was **not** raised, because that is an AI-contract change
   requiring owner approval.
3. **Blocked from title in the middle viewport range.** The plan drawing keeps
   its 640 px scale below 1024 px, so between 640 and 1024 px the frame is wider
   than the drawing needs and shows some empty margin. This is a deliberate
   trade: legibility over density.
4. **The plan is illustrative.** Not a construction or building-code drawing.
5. **Prices are indicative.** Not verified market prices, no retailer data.
6. **No Git repository.** Nothing was committed, pushed or deployed.

---

## 11. Recommended next action

Phase 8 closes the release-preparation scope. The remaining work is **Phase 9,
documentation and portfolio presentation**, and it is small:

1. Run one real screen-reader pass (NVDA on Windows is sufficient) over the
   nine screens and record it against the axe result. This is the only
   outstanding evidence item.
2. Optionally, review the plan frame's empty margin between 640 and 1024 px.
3. Record the asset-provenance decision in the project documentation if the
   repository is published, since the reference images are project-generated.

**No further code change is required for the V1 release.** The product passes,
the suite passes, and the release artefacts exist.

---

## 12. Final state

| Item | Result |
|---|---|
| Responsive, 7 widths, real browser | **PASS** — no page overflow anywhere |
| Accessibility, real axe-core, 9 screens | **PASS** — 0 violations |
| Accessibility, screen reader | **NOT VERIFIED** — no AT session run |
| Five UX problems | **PASS** — all implemented, all tested |
| README / README.tr | **PASS** — equivalent, claims verified |
| Screenshots | **PASS** — 20 real captures, recaptured after the roadmap badge fix |
| Full test suite | **PASS** — 1,123 passed, 0 failed, 0 skipped |
| PDF | **PASS** — 13 pages, generated live twice (73,610 B and 74,948 B), probes verified in both |
| Secrets | **PASS** — none in source, reports, screenshots or logs |
| Git | **N/A** — no repository; nothing committed |
