# Phase 8 — Release Readiness

**Project:** Hometsy — Room Intelligence Studio
**Assessed:** 16 November 2026
**Scope assessed:** the approved V1, as defined in `PROJECT_BRIEF.md` and
constrained by `AGENTS.md` §3.
**Supersedes:** `reports/phase-7/RELEASE_READINESS.md`

---

## 1. Decision

> **Ready for portfolio publication.**

The two Phase 7 PARTIALs — responsive layout and accessibility — are now backed
by real evidence: seven viewport widths measured in a live browser, and a real
axe-core scan reporting **zero violations on nine screens**. The five UX problems
identified from the live interface were implemented and tested, and the release
artefacts (`README.md`, `README.tr.md`, twenty real screenshots) exist.

One item remains **NOT VERIFIED** and is stated as such rather than glossed:
**no real screen-reader session was run.** That is a residual evidence gap, not a
known defect, and it does not block a portfolio release — but it does mean the
project must not claim WCAG conformance, and it does not.

---

## 2. Category verdicts

| Category | Verdict | Evidence |
|---|---|---|
| Core workflow (room → preferences → brief → concepts → plan → evaluation → budget → PDF) | **PASS** | complete live end-to-end runs this phase, including a live AI truncation handled correctly |
| Deterministic engines (room, spatial, placement, budget) | **PASS** | 48/48 room, 46/46 spatial, 56/56 placement, 36/36 budget; all arithmetic in Python `Decimal` |
| AI integration (4 operations, structured + validated) | **PASS** | live calls during this phase; schema-validated; a truncated response became an error, not a result |
| PDF report | **PASS** | 48/48 structural; 13-page live artefact, generated twice this phase (73,610 B and 74,948 B), all probe strings present in both |
| Honesty of claims (no overclaiming) | **PASS** | validated / partial / not-drawn headings intact; unpriced ≠ zero; corrected plan caption |
| Interface presentation | **PASS** | 5 UX problems fixed; 20 real screenshots; PDF palette equals UI palette (asserted) |
| **Responsive layout** | **PASS** | **7 widths in a real browser**, no page overflow anywhere — see §3 |
| **Accessibility (automated)** | **PASS** | **real axe-core on 9 screens, 0 violations** — see §4 |
| **Accessibility (screen reader)** | **NOT VERIFIED** | no NVDA/JAWS/VoiceOver session run — see §7.1 |
| Test suite health | **PASS** | 1,123 passed, 0 failed, 0 skipped; +25 tests; none deleted or weakened |
| Documentation for release | **PASS** | `README.md` + `README.tr.md`, equivalent, every claim verified; 20 screenshots |
| Security / secrets | **PASS** | no credential in source, tests, logs, reports or screenshots — see §6 |
| Version control | **N/A** | no Git repository exists; nothing committed, pushed or deployed |

---

## 3. Responsive behaviour — PASS

### Method

The Phase 7 report said the relay at `127.0.0.1:19988` was unreachable and that
the desktop browser exposed no resize control. **That finding was wrong.**
`page.setViewportSize()` works: 1440 → `innerWidth` 1440, 390 → `innerWidth` 390,
with `outerWidth` unchanged. No new dependency was needed.

Measured against the live application on the widest, most complex screen (design
plan: SVG drawing, two wide tables, metric cards, stage strip).

### Results

| Viewport | Page overflow | `<main>` overflow | Outside plan frame | Label size | Drawing | Frame scrolls |
|---|---|---|---|---|---|---|
| 1440 | none | none | 0 | 13.68 px | 973 px | no |
| 1024 | none | none | 0 | 9.00 px | 640 px | yes |
| 768 | none | none | 0 | 9.00 px | 640 px | yes |
| 430 | none | none | 0 | 9.00 px | 640 px | yes |
| 404 | none | none | 0 | 9.00 px | 640 px | yes |
| 390 | none | none | 0 | 9.00 px | 640 px | yes |
| 360 | none | none | 0 | 9.00 px | 640 px | yes |

Verified additionally on the budget screen at 390 px: money values render at
21 px with `white-space: nowrap`, `overflowsCard: false`, `docOverflow: false`.

### Why this is now PASS and was PARTIAL

Phase 7 proved the *stylesheet* at 404 px and inferred the rest from a CSS
fixture that did not exercise Streamlit's own containers. Phase 8 measures the
*composed application* at all seven priority widths. The fixture is no longer
cited as evidence.

### Residual behaviour worth naming

Between 640 and 1024 px the plan frame is wider than the 640 px drawing needs, so
some empty margin is visible inside the frame. This is a deliberate trade —
label legibility is kept over density — and not a layout defect. No page
overflow results from it at any width.

---

## 4. Accessibility — PASS (automated)

### Method

axe-core 4.10.2 injected into the live page, run with
`wcag2a, wcag2aa, wcag21a, wcag21aa, best-practice`, on nine screens in the
states that matter:

landing · room · preferences · review · brief (before/after AI) · concepts
(before/generated/selected) · plan (before/built) · evaluation (before/after AI) ·
budget · report.

The tool lives outside the repository in the temp directory. It is an external QA
instrument, **not a project dependency**, and `requirements.txt` is unchanged.

### Baseline → final

| Rule | Impact | Baseline | Final |
|---|---|---|---|
| `color-contrast` | serious | 4 screens | **0** |
| `image-alt` | serious | 1 screen (budget chart) | **0** |
| `scrollable-region-focusable` | serious | 1 screen (plan) | **0** |
| **Any violation** | — | **3 rule types / 6 screens** | **0 / 0** |

### Final per-screen result

| Screen | Violations |
|---|---|
| Landing | 0 |
| Room setup | 0 |
| Design preferences | 0 |
| Project review | 0 |
| Brief (before AI) | 0 |
| Brief (after AI) | 0 |
| Concepts (before) | 0 |
| Concepts (generated) | 0 |
| Concepts (selected) | 0 |
| Plan (before advisor) | 0 |
| Plan (built) | 0 |
| Evaluation (before AI) | 0 |
| Evaluation (after AI) | 0 |
| Budget | 0 |
| Report | 0 |

### How the three rule types were closed

- **`color-contrast`** — four tokens adjusted so every coloured token clears
  4.5:1 on all three product surfaces. A test now enforces it, so the fix cannot
  silently regress. The PDF palette is asserted equal to the UI palette.
- **`image-alt`** — the Matplotlib chart receives real alternative text naming
  every bar and its value.
- **`scrollable-region-focusable`** — this one was **introduced by Phase 8's own
  scroll fix** and caught by the scan. The plan frame is now
  `tabindex="0" role="group" aria-label="Room plan drawing. Scroll sideways to
  see the whole plan."`, so a keyboard user can reach and pan it.

### Manual triage — what was deliberately not changed

- **Streamlit vendor chrome** (sidebar collapse control, keyboard hint). Not our
  markup; restyling it would be fragile and is exactly what `AGENTS.md` §10 warns
  against.
- **`region` best-practice warnings** on the vendor top bar — Streamlit owns that
  landmark structure.
- **Decorative swatches and the plan legend** — correctly `aria-hidden="true"`
  because adjacent text carries the meaning.
- **The 45×45 cm unlabelled block** — correct behaviour at plan scale; the name,
  size and position are in the table beneath, and the caption says so.

Findings were fixed where they were ours and correct, and documented where they
were not. Nothing was suppressed.

---

## 5. The five UX problems — all implemented

Identified from the live interface, planned in `UI_PLAN.md`, then implemented
with tests. Details in `COMPLETION_REPORT.md` §5.

| # | Problem | Fix | Test |
|---|---|---|---|
| 1 | Three contradictory progress vocabularies on one screen | `STAGES`-driven `Stage n of 5` everywhere; header counts stages | 3 tests incl. a source scan |
| 2 | Landing page claimed working stages were future work; 4-step hero vs 5-stage product | Corrected copy; hero generated from `STAGES` | 2 tests |
| 3 | Real WCAG AA contrast failures (3.62:1, 4.25:1) | Four tokens adjusted in both palettes | 3 tests incl. WCAG maths |
| 4 | Cost chart was an unlabelled `<img>` | `distribution_alt_text()` with every figure | 2 tests |
| 5 | Plan labels at 4.56 px on phones; labels truncated to misleading first words | 640 px floor + internal scroll; wrap instead of truncate | 10 tests incl. end-to-end fit |

Two further defects were found during verification and fixed rather than shipped:
the scroll-container focusability violation, and money values breaking after the
decimal comma ("41.800," / "00 TRY").

A third was found late, while re-reading the captured landing screenshot: the
roadmap still badged the finished V1 as **"In development"** and said V1 was
"the only version under development". The card now reads **"Complete"** (V2 and
V3 stay "Planned"), and the capture was retaken. It is the same stale-copy class
as problem 2, one section further down the same page.

---

## 6. Security and secrets — PASS

| Check | Result |
|---|---|
| Credential in source code | none — read from `DEPLOY_API_KEY` at runtime only |
| Credential in test files | none — AI tests are fully mocked |
| Credential in reports | none |
| Credential in screenshots | none — no screenshot shows a key or config screen |
| Credential in logs | none — the key is `repr=False` and stripped from every error message |
| Credential printed during this phase | never — checked as `bool`/`len` only |
| `.streamlit/secrets.toml` | absent; documented as excluded from version control |
| `.streamlit/config.toml` | contains theme and server settings only, no secrets |

`ai/config.py` is the single resolution point and deliberately excludes the key
from `repr` and from error text, so an accidental `print(config)` or a logged
exception cannot leak it.

---

## 7. What is still not verified

### 7.1 Real screen-reader use — NOT VERIFIED

No NVDA, JAWS, VoiceOver or TalkBack session was run. axe-core verifies structure,
accessible names, roles, and contrast; it does **not** verify whether the
announcement order is sensible or whether the wording is understandable when
spoken.

**Consequences, stated honestly:**

- The project may say "automated scans report zero violations on nine screens".
- The project may **not** say "WCAG 2.1 AA conformant", "accessible", or
  "screen-reader compatible".
- Both READMEs say the axe result is "a strong automated result, **not** a WCAG
  conformance certification, and it is not a substitute for testing with real
  assistive technology."

This is the single outstanding evidence item. It is recommended as the first task
of Phase 9.

### 7.2 PDF layout is verified structurally, not visually

The PDF is checked by page count, extracted text and probe strings. A pixel-level
layout comparison is not performed, so a subtle visual drift (a heading sitting
too low, a table split awkwardly) would not be caught automatically. The live
artefact was opened and inspected manually this phase.

### 7.3 Live AI behaviour is inherently variable

During this phase one advisor call was truncated by the provider. The
application reported it as an error and stored nothing — the correct behaviour —
and an immediate retry succeeded. This is a provider-side property, not an
application defect. `max_tokens` was **not** raised, because that is an
AI-contract change requiring owner approval under `AGENTS.md` §15.

### 7.4 Not a commercial product

Illustrative prices, no accounts, no database, no live pricing, no retailer
integration, single room, no 3D. These are the approved V1 boundaries, documented
as limitations in both READMEs, not gaps.

---

## 8. Release artefacts

| Artefact | Location | State |
|---|---|---|
| English README | `README.md` (19,560 B) | complete, UTF-8, LF, no BOM |
| Turkish README | `README.tr.md` (20,828 B) | equivalent content, same encoding |
| Screenshots | `docs/screenshots/` (20 files, 1.93 MB) | all from the running application |
| Phase 8 completion | `reports/phase-8/COMPLETION_REPORT.md` | complete |
| Phase 8 tests | `reports/phase-8/TEST_REPORT.md` | complete |
| Phase 8 UX plan | `reports/phase-8/UI_PLAN.md` | complete |
| Release readiness | this document | complete |

### README claim verification

Each substantive claim was checked against the code rather than asserted:

| Claim | Verification |
|---|---|
| Stack versions | matched against installed distributions |
| 1,123 tests | matched the final full-suite run and `--collect-only` |
| No Streamlit in `core`/`ai`/`workflow`/`models` | import scan: only `pydantic` and `reportlab` are non-stdlib; the single `streamlit` string in `workflow/__init__.py` is a docstring asserting its *absence* |
| 20 catalog items | read from `data/furniture_catalog.json` |
| 6 styles, 4 palettes | read from `data/design_references.json` |
| Asset provenance | read from `assets/source_pack/asset_manifest.json` and `data/asset_replacements.json` |
| All 14 screenshot links | each path checked to exist |
| Workflow invalidation table | read from `workflow/dependencies.py` |

### Screenshot provenance

Every screenshot is a browser capture of `http://127.0.0.1:8512` against the
final build. The whole set comes from **one continuous session**, so the figures
are consistent across the screenshots: room "Sisli Living Room", 400 × 500 cm,
Japandi, Warm Neutral, 42.200,00 TRY, 7 of 7 placed. That is real output from a
live AI run during this phase. **No mockup, no fabricated image, no doctored
screenshot.**

The live model does not return an identical basket every time, so a later
end-to-end run in the same phase produced a different but equally valid total
(41.800,00 TRY) and a 74,948 B PDF. Both are correct; the reports quote the
screenshot session's figures because those are the ones a reader can see.

---

## 9. Test suite health — PASS

| Metric | Value |
|---|---|
| Tests | **1,123** |
| Passed | **1,123** |
| Failed | 0 |
| Skipped | 0 |
| Deleted | 0 |
| Weakened | 0 |
| Runtime | 54.86 s |
| Needs a live API key | no |

Full detail, including the six development-time failures and how each was
resolved, is in `TEST_REPORT.md`. In no case was an assertion relaxed to obtain
a green run.

---

## 10. Phase 7 fixes — no regression

| Fix | Status |
|---|---|
| Single `format_money` in `core/budget_engine` | intact |
| Evaluator withholds the zero material subtotal | intact |
| Evaluator receives a placement block | intact |
| `placement_plan_svg(partial=...)` never says "validated" | intact |
| Three-way PDF plan heading | intact |
| Budget-snapshot guard | intact |

---

## 11. Final state and recommended next action

### Final state

| Item | Result |
|---|---|
| Responsive, 7 widths, real browser | **PASS** |
| Accessibility, real axe-core, 9 screens | **PASS** — 0 violations |
| Accessibility, screen reader | **NOT VERIFIED** |
| Five UX problems | **PASS** — all implemented and tested |
| README / README.tr | **PASS** |
| Screenshots | **PASS** — 20 real captures |
| Full test suite | **PASS** — 1,123 / 0 / 0 |
| PDF | **PASS** — 13 pages, live-generated |
| Secrets | **PASS** |
| Version control | **N/A** — nothing committed, pushed or deployed |

### Recommended next action

**Portfolio publication may proceed.** The remaining work is Phase 9
(documentation and portfolio presentation), and it is small:

1. **Run one real screen-reader pass** (NVDA on Windows is sufficient) over the
   nine screens and record the result next to the axe result. This closes §7.1 —
   the only outstanding evidence item — and would allow the accessibility verdict
   to move from "PASS (automated) / NOT VERIFIED (AT)" to a single PASS.
2. Optionally review the plan frame's empty margin between 640 and 1024 px.
3. Before publishing, decide whether the generated reference images are
   redistributable under the applicable platform terms; the manifest already
   flags this.

**No further code change is required for the V1 release.**
