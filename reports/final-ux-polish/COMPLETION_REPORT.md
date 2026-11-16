# Final UX polish — Completion Report

**Project:** Hometsy — Room Intelligence Studio
**Task:** A final, focused interface polish pass before first GitHub publication
**Completed:** 16 November 2026
**Scope:** Five genuine UX improvements, identified from the live running
application and implemented without changing workflow logic, AI contracts,
calculation engines or the design system.

---

## 1. Objective

The nine-screen journey was already complete, tested and released as V1. This
pass had one job: read the real running interface the way a first-time visitor
reads it, find the small number of places where it genuinely gets in the way,
and fix those — without redesigning what already works.

The brief set five constraints that shaped every decision:

- keep the existing visual identity, whitespace discipline and typography;
- add no dependencies, no V2 features and no component rewrites;
- change no workflow logic, AI prompt, response contract, geometry, placement
  or budget code;
- leave strong areas alone;
- prove each change in a real browser, not from reading the code.

**No workflow, AI, geometry, placement or budget module was modified.** Every
change is in `ui/` presentation code.

---

## 2. How the five were chosen

Each screen was walked in the live application at 1440 × 900 and 1000 × 700,
with real DeepSeek calls, through all nine steps: room setup → preferences →
review → brief → concepts → selection → plan → evaluation → budget → report.

Five problems survived the filter of "does this actually cost the reader
something". Everything else was left alone — the room form, the preference
cards, the review screen, the brief blocks, the shell's stage strip and the
navigation columns were all judged to be working and were not touched.

A sixth, smaller change is recorded in §3.6: on the concept cards the
description is now set at body size rather than label size. It is documented
separately because it is a typographic adjustment inside an already-working
card, not one of the five problems above.

| # | Screen | Problem observed live | Fix |
|---|---|---|---|
| 1 | Landing | The only start button sat in the closing section, **3 sections down and below the fold** at 1000 × 700 — the one thing `DESIGN_SYSTEM.md` §6.1 names as required ("Primary start action") | Moved under the hero, with a short note on what starting involves |
| 2 | Design plan | The result — score, drawing, validation — began at **y ≈ 2,776 px**, *after* the basket table and six full-height material cards | Reordered: result → plan → placed pieces → validation → score → clearances, then the basket and materials |
| 3 | Budget | Usage was the caption of the **remaining-budget** card, so "96.3% of the limit" sat under the one figure it does not describe | Full-width proportion meter under all three totals, with the percentage beneath |
| 4 | Design evaluation | Ten bullets across two lists were set identically to the four written judgements they qualify | The lists moved into subordinate panels; the four judgements stay primary |
| 5 | Everywhere | Repeat-run AI actions ("Generate concepts again", "Run the advisor again", "Evaluate the design again", "Generate the report again") rendered as primary buttons **beside** the forward action | Repeat actions demoted to secondary once a result exists; forward navigation carries the emphasis |

---

## 3. The changes

### 3.1 Landing — the primary action moved above the fold

`ui/pages_landing.py`

The start action now follows the hero. The closing "Start a project" section
keeps its explanation of what the first two screens ask for, but no longer
repeats the button — two identically labelled primary buttons on one page is
the ambiguity this pass removes elsewhere.

A duplicate `Resume current project` button was removed for the same reason
(it would have rendered twice and raised `StreamlitDuplicateElementId`).

**Before / after (1440 × 900)**: `before` state in `docs/screenshots/01-landing.png`;
`evidence/after-01-landing-1440x900.png`.

**Measured**: the button's bottom edge moved from below the fold to **565 px**
in a 900 px viewport, and to **576 px** in a 700 px viewport. It is above the
fold at both sizes.

Spacing: the new `.hm-cta-note` sets the note at 13 px on a 78-character
measure, and `.hm-cta-close` inserts a 32 px band between the button and the
"What it does" heading, which the button previously touched.

### 3.2 Design plan — the result no longer sits under the materials

`ui/pages_plan.py`

The screen exists to answer "does this room work?". The answer, the drawing,
the coordinates and the verdict now render before the basket table and the six
material cards that produced them. The basket block moved into a new
`_render_basket_block` helper so the four states ("current", "unusable",
"out of date", "none") stay together and cannot drift apart.

**Measured in the live DOM**, before → after:

| Section | Before (y) | After (y) |
|---|---|---|
| Result | 2,776 | **566** |
| Room plan | 3,010 | **800** |
| Placed pieces | 4,162 | **1,952** |
| Spatial validation | 4,560 | **2,316** |
| Furniture and materials | 566 | 3,070 |
| Materials and finishes | 1,125 | 3,866 |

The result moved up by **2,210 px**. Nothing was removed or reworded; the order
changed.

`DESIGN_SYSTEM.md` §6.7 asks that spatial warnings be easy to distinguish from
informational notes. A verdict that a reader reaches only after scrolling past
ten material cards was not easy to distinguish from anything.

### 3.3 Budget — usage belongs under all three totals

`ui/pages_budget.py`, `ui/theme.py` (`usage_meter`, `status_row`)

The percentage was attached to the "Remaining budget" card in the before state,
although it describes the relation between the total and the limit — the two
other cards. It is now a full-width proportion meter beneath all three figures,
with the figure printed beneath it.

The meter is decorative and marked `role="presentation"`: the percentage is
printed as text beside it, so the value is never carried by length or colour
alone (`DESIGN_SYSTEM.md` §7). The fill clamps at 100 % because an overrun is
reported as a figure, and a bar that overflowed its own track would misstate
how far over it is.

The status badge and its sentence now share one baseline (`.hm-status-row`)
instead of stacking as two unrelated statements.

**Before / after**: `evidence/before-05-budget-totals.png` →
`evidence/after-05-budget-totals.png`.

### 3.4 Design evaluation — judgements lead, commentary follows

`ui/pages_evaluation.py`, `ui/theme.py` (`aside`)

The four written judgements — requirement compatibility, style consistency,
functional suitability, budget suitability — remain exactly as the schema
defines them. The two lists ("Limitations and risks", "Improvement suggestions")
now render inside `.hm-aside` panels: same words, same order, same `h3`
headings, visibly subordinate.

Nothing was truncated, collapsed or hidden. Both lists are still fully readable;
they no longer outweigh the four sentences they comment on.

**Before / after**: `evidence/before-04-evaluation-fields.png` →
`evidence/after-04-evaluation-fields.png`.

### 3.5 One primary action per screen

`ui/pages_concepts.py`, `ui/pages_plan.py`, `ui/pages_evaluation.py`,
`ui/pages_budget.py`, `ui/pages_report.py`

Once a result exists, generating it again is a repeat action, not the way
forward. Each repeat button is now `type="secondary"` when its result exists,
and the forward action carries the primary emphasis.

Two ordering dependencies had to be handled, because they would otherwise have
produced two primaries:

- **Evaluation** — the budget estimate is computed with the layout, so
  "Continue to budget analysis" unlocks immediately. Keying its *emphasis* on
  the budget would have put it beside "Evaluate the design" as a second primary.
  Its emphasis now follows the evaluation itself.
- **Budget** — on the stale-estimate branch, "Recalculate the estimate" is the
  screen's own action, so the forward button is secondary there.

**Verified by probe** (Streamlit `AppTest`, reading `button.proto.type`) —
exactly one primary per state:

| Screen | State | Primary |
|---|---|---|
| Landing | — | `Start Room Setup` |
| Concepts | no set | `Generate three concepts` |
| Concepts | set exists | *none* — three equal "Select this concept" choices |
| Plan | no basket | `Recommend furniture and build the plan` |
| Plan | plan current | `Continue to the design evaluation` |
| Evaluation | no result | `Evaluate the design` |
| Evaluation | result | `Continue to budget analysis` |
| Budget | current | `Continue to the final report` |
| Budget | stale estimate | `Recalculate the estimate` |
| Report | not generated | `Generate the PDF report` |
| Report | generated | *none* — the download is the way forward |

The concepts and report screens deliberately have no primary in their final
state: on concepts the user must choose between three equal options, and on
report the download button is the action.

### 3.6 Concept cards — the description leads

`ui/pages_concepts.py`, `ui/theme.py` (`concept_field(..., lead=True)`)

The three alternatives are read against each other, so the one field that states
the whole proposition in a sentence is set at reading size (14 px) instead of the
13 px used by the supporting fields. The literal "Description" label is retained
— a test requires that exact string — and `concept_field` gained an optional
`lead` argument that adds the `.hm-concept-lead` class alongside the existing
`.hm-concept-value`. The other five fields are unchanged.

---

## 4. Files changed

**Modified — presentation only (7 files):**

| File | Change |
|---|---|
| `ui/theme.py` | New helpers `usage_meter`, `status_row`, `aside`, plus `concept_field(..., lead=)`; nine CSS classes — `.hm-meter`, `.hm-meter-fill`, `.hm-meter-fill--error`, `.hm-meter-caption`, `.hm-status-row`, `.hm-aside`, `.hm-concept-lead`, `.hm-cta-note`, `.hm-cta-close` |
| `ui/pages_landing.py` | Start action under the hero; duplicate resume button removed |
| `ui/pages_plan.py` | Result block before basket/materials; `_render_basket_block` helper; advisor demoted when current |
| `ui/pages_budget.py` | Usage meter + status row; forward nav emphasis gated on `current` |
| `ui/pages_evaluation.py` | Judgements lead, lists in aside panels; forward nav emphasis gated on `evaluated` |
| `ui/pages_concepts.py` | Description leads; "Generate concepts again" demoted |
| `ui/pages_report.py` | "Generate the report again" demoted when current |

**Created (21 files, all under `reports/final-ux-polish/`):**

- `COMPLETION_REPORT.md` (this file)
- `evidence/` — 20 real browser screenshots: 13 "after", 7 "before"

**Unchanged, deliberately:** `ui/pages_room.py`, `ui/pages_preferences.py`,
`ui/pages_brief.py`, `ui/pages_review.py`, `ui/shell.py`, `ui/diagram.py`,
`ui/report.py`, `ui/budget.py`, and every module under `core/`, `ai/`,
`models/`, `workflow/`, `data/`.

`DESIGN_SYSTEM.md`, `README.md`, `README.tr.md`, `COPYRIGHT.md`, `AGENTS.md`,
`PROJECT_BRIEF.md`, `TECHNICAL_ARCHITECTURE.md`, `DEVELOPMENT_PLAN.md` and every
file under `docs/` were **not modified**. All 30 existing screenshots retain
their previous bytes.

No dependency was added or removed. `requirements.txt` is unchanged.

---

## 5. Verification

### 5.1 Test suite

Full suite, run once at the end after the final code edit:

```
.venv\Scripts\python.exe -m pytest -q
```

| Measure | Result |
|---|---|
| Passed | **1,149** |
| Failed | **0** |
| Skipped | **0** |
| Errors | **0** |
| Duration | 45.10 s |

The baseline was 1,149 passed / 0 failed / 0 skipped. **Preserved exactly** — no
test was added, removed, edited or skipped, and no existing assertion was
weakened.

Focused runs during the work (the eight UI modules touched or adjacent):

```
tests/test_ui_presentation.py tests/test_ui_headings.py tests/test_ui_app.py
tests/test_ui_ai_flow.py tests/test_ui_advisor_flow.py tests/test_ui_budget.py
tests/test_ui_evaluation.py tests/test_ui_report.py
→ 270 passed
```

### 5.2 Design-system compliance

Re-checked programmatically after the last edit:

- every hex literal in `APP_CSS` is in the approved token set — **0 violations**;
- every new selector is qualified under `.hm-page` — no rule targets Streamlit's
  internal DOM;
- all nine new CSS classes and three new helpers (`usage_meter`, `status_row`,
  `aside`) are present and referenced; `concept_field` gained its optional
  `lead` argument and is used with it.

### 5.3 Live browser verification

Every changed screen was re-walked in the real running application after the
changes, with real DeepSeek calls:

- **Landing** — one `Start Room Setup` button, above the fold at 1440 × 900
  (565 px) and 1000 × 700 (576 px); four `h2` sections intact.
- **Concepts** — three cards, description leads, "Generate concepts again"
  secondary.
- **Plan** — result at 566 px, drawing then coordinates then validation then
  score then clearances, basket and materials after.
- **Evaluation** — four judgements, then two aside panels with all bullets
  present.
- **Budget** — meter under all three totals, percentage 98.8 %, badge and
  sentence on one baseline.
- **Report** — generated, downloaded, verified.

### 5.4 PDF generation

The report UI changed (`Generate the PDF report` demoted after generation), so
a real PDF was produced end-to-end:

```
output/reports/hometsy-studio-living-room-report.pdf
74,181 bytes | header: %PDF-1.4
```

The UI reported **"Report ready"** and the same byte count (74,181), and the
file's header confirms a valid PDF. `output/reports/` remains excluded from
version control.

### 5.5 Documentation and screenshot preservation

Confirmed by timestamp sweep: within this pass, the only files written were the
seven `ui/` modules and the 21 new files under `reports/final-ux-polish/`. No
existing document or screenshot was touched.

---

## 6. Publication inventory impact

The frozen pre-Git inventory was **196 files / 7.60 MB**. This pass added 21
files under `reports/final-ux-polish/` (1.47 MB of PNG evidence plus this
report) and changed no tracked file count elsewhere.

| Measure | Before | After |
|---|---|---|
| Tracked files | 196 | **217** |
| Tracked size | 7.60 MB | **9.08 MB** (see §11) |
| `reports/` files | 45 | **66** |
| `ui/` files | 21 | 21 (7 modified, 0 added) |

**This superseded the 196-file figure in
`reports/github-release/FINAL_PRE_GIT_CHECKLIST.md` §1 and §7**, which has since
been updated to **217** along with the verification command and the pre-flight
checklist item. The exclusions, security status, image decision, licensing and
Git-identity blocker were unaffected by the change.

The evidence was pruned deliberately: 8 captures that duplicated each other or
showed unmodified screens were deleted before finalising, taking the set from
29 files (2.53 MB) to 20 files (1.47 MB).

---

## 7. Known limitations

| Item | Status |
|---|---|
| Screen-reader listening session | **NOT VERIFIED** — NVDA absent and deliberately not installed. No WCAG conformance claim is made or implied. |
| Axe-core scan | Not re-run; this pass changed spacing, order and button emphasis, and added no new semantic structure. The Phase 8 automated result stands as recorded, not as re-verified now. |
| Mobile | Only desktop widths were measured this pass (1440 × 900, 1000 × 700). The existing 390 px captures in `docs/screenshots/` were not re-taken and may not reflect the reordered plan screen. |
| Plan reordering | Verified at 1440 px only; at narrow widths the six material cards are long, so the basket moves further down than the measurement above. |
| Concept description size | Set via a CSS class, so it does not respond to the browser's font-size preference independently of the rest of the card copy. |
| Budget meter | Clamps the fill at 100 % on an overrun; the overrun amount is stated as a figure, not as bar length. |
| Git | No repository, no identity, no commit. Unchanged by this pass. |

---

## 8. Scope deviations

**None in product scope.** No V2 feature was added, no dependency was
introduced, no AI prompt or response contract was modified, and no
geometry/placement/budget arithmetic was touched.

Two deviations are worth recording explicitly:

1. **Item 5 required two changes that were not in the plan.** "Recalculate the
   layout" on the plan screen was already untyped (secondary) and needed nothing.
   But the evaluation and budget forward buttons each needed conditional emphasis
   once their screen's own action was identified — without that, each would have
   rendered two primaries side by side, which is the exact problem item 5 exists
   to remove. These are a consequence of item 5, not a new feature.

2. **The evidence set and this report are new tracked files.** The task said to
   preserve the existing 196-file inventory and to capture before/after
   screenshots; those two instructions conflict, and capturing the evidence was
   the specific requirement. The inventory change is documented in §6 above and
   flagged for the pre-Git checklist rather than left to be discovered at
   `git add`.

---

## 9. Recommended next action

1. ~~**Update the two inventory figures** in
   `reports/github-release/FINAL_PRE_GIT_CHECKLIST.md` (§1 table and §7
   verification comment) from 196 to 217.~~ **Done** — see §11.
2. ~~**Optionally re-capture `docs/screenshots/11-design-plan.png` and
   `13-spatial-validation.png`** if the reordered plan screen should appear in
   the public documentation.~~ **Done** — see §11.
3. **Supply the Git identity**, which remains the only publication blocker, then
   follow the checklist's §7 sequence with the corrected file count (**217**).

---

## 10. Bottom line

Five genuine interface problems were found by walking the real application and
fixed in presentation code only:

- the start action is above the fold;
- the plan's verdict is 2,210 px closer to the reader;
- budget usage sits under the figures it describes;
- the evaluation's judgements outrank its commentary;
- every screen has one primary action.

**1,149 tests still pass, no documentation or existing screenshot was altered,
no product logic changed, and the PDF still generates and downloads.**

The interface is a little calmer in five specific places. Nothing else moved.

---

## 11. Addendum — final publication consistency

**Added:** 16 November 2026, after the polish pass was reviewed.

Three follow-up items were required before publication, and all three are now
complete. This section records them so the inventory above and the two release
documents agree.

### 11.1 Inventory figures reconciled

| Document | Was | Now |
|---|---|---|
| `FINAL_PRE_GIT_CHECKLIST.md` §1, §7, §9 | 196 files / 7.60 MB | **217 files / 9.08 MB** |
| `GITHUB_PREPARATION.md` §1, §3, §6, §7, §8, §12.3, §13, §14 | 196 files / 7.60 MB | **217 files / 9.08 MB** |

The size settled at **9.08 MB**, not the 9.10 MB quoted earlier. The difference is
the two re-captured screenshots below: each new capture is smaller than the file it
replaced, which offsets part of the 1.49 MB of evidence. The figure was measured
against the filesystem after every document edit, not carried forward.

Both documents now carry an explicit note distinguishing the audit-era 196-file
count from the current one, and
`FINAL_PRE_GIT_CHECKLIST.md` §1.1 itemises the 21-file difference: this report plus
the 20 evidence screenshots.

### 11.2 Two screenshots re-captured

`docs/screenshots/11-design-plan.png` and `13-spatial-validation.png` showed the
**previous** plan order — `11` led with "Furniture and materials", the block that
now follows the result. Both were re-captured from the running application at the
same **1440 × 1000** size as the originals, with real DeepSeek calls:

| File | Shows now | Bytes (before → after) |
|---|---|---|
| `11-design-plan.png` | Result → score/items/validity → Room plan | 89,815 → 67,855 |
| `13-spatial-validation.png` | Drawing → Placed pieces → Spatial validation → score | 70,890 → 71,351 |

The other **18 originals were not touched** and retain their timestamps. The
10-image portfolio selection in `docs/screenshots/portfolio/` was likewise left
untouched, which has a consequence worth stating plainly: the portfolio files
`05-furniture-recommendations.png` and `07-spatial-validation.png` are now the only
two of the ten that no longer match their originals byte-for-byte. That is
deliberate — the portfolio set is a frozen narrative selection, and silently
rewriting it to match would have been a bigger change than the one requested.

### 11.3 Verification recorded

| Check | Result |
|---|---|
| Image references in `README.md`, `README.tr.md`, `PORTFOLIO_CASE_STUDY.md` | **34 found, 22 distinct, 0 missing** |
| README link totals (re-derived, not trusted) | `README.md` 30/30, `README.tr.md` 30/30, case study 12/12 |
| H2/H3 parity between READMEs | **15 / 12 each** — unchanged |
| Portfolio selection | **10 files present**, unchanged membership and bytes |
| UX evidence | **20 files** (13 after, 7 before), 1,502 KB |
| `.gitignore` required patterns | **all 12 present**, including `!.env.example` |
| Longest tracked path | **71 relative / 108 absolute** (limit 260) |
| Files over 1 MB | **0**; largest remains `DejaVuSans.ttf` at 738 KB |
| Local paths or secrets introduced | **none** in any file written this task |
| Git state | no `.git`, no staging, no commit, identity unchanged |

The full test suite was **not** re-run: this task changed no Python source and no
test file. The 1,149-passing result recorded in §5.1 stands.

### 11.4 Files changed by this addendum

| File | Change |
|---|---|
| `reports/github-release/FINAL_PRE_GIT_CHECKLIST.md` | §1 inventory + new §1.1; by-area table; included/excluded lists; path lengths; §7 command and pre-flight list; §9 bottom line |
| `reports/github-release/GITHUB_PREPARATION.md` | §1 decision; §2 path lengths; §3 structure and file-type profile; §6 large files and duplication note; §7 `reports/` listing; §8.1 exclusions; §12.3 inventory; §13 done-list; §14 figure |
| `docs/screenshots/11-design-plan.png` | Re-captured, 1440 × 1000 |
| `docs/screenshots/13-spatial-validation.png` | Re-captured, 1440 × 1000 |
| `reports/final-ux-polish/COMPLETION_REPORT.md` | This addendum; §6 size corrected; §9 marked done |

No Python source, test, asset, AI prompt, geometry, budget or workflow file was
modified. No screenshot was deleted.
