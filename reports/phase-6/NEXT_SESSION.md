# Phase 6 → Phase 7 — Next Session Handoff

**Project:** Hometsy — Room Intelligence Studio
**Written at the end of:** Phase 6 (COMPLETE)
**Next:** Phase 7 — Final QA

---

## 1. State at handoff

| Item | Value |
|---|---|
| Full test suite | **1076 passed**, 0 failed, 0 skipped |
| Baseline entering Phase 6 | 996 |
| New tests | +80 (46 PDF, 25 report screen, 9 brief reliability) |
| Working tree | no Git repository; nothing committed, pushed or deployed |
| Runtime server | stopped |
| Sample PDF | `reports/phase-6/sample/hometsy-sisli-salonu-report.pdf` (68 116 B, 11 pp) |

Phase 6 deliverables are all in place: the Brief Analyzer token ceiling is
diagnosed and fixed, the PDF report exists and is downloadable, and the whole
workflow has been walked end to end in a real browser against the live API.

---

## 2. What Phase 7 should verify

`DEVELOPMENT_PLAN.md` defines Phase 7 as Final QA. The following are the
specific, known surfaces to attack.

### 2.1 Repeated live runs (the bug class that just bit us)

The Brief Analyzer failure was **intermittent**, caused by a completion length
that varied run to run (1675–3351 tokens). A single green run proves little.

* Run the brief analysis several times on the same input and confirm every run
  succeeds. Live evidence so far: 3 of 3 at cap 8000.
* Confirm the other three AI operations are equally stable across repeats.
* If any operation shows variance near its cap, measure its completion length
  the same way the brief was measured rather than raising the cap blindly.

### 2.2 Plan states other than COMPLETE

Browser QA covered exactly one project, and it placed **10 of 10**. The
`PARTIAL` and `FAILED` plan renderings exist and are unit-tested, but have not
been seen in a running app or a PDF produced through the UI.

* Build a project whose basket cannot be fully placed (an over-large item, or a
  basket competing for the same wall) and walk it to a PDF.
* Confirm the report draws only the placed items and states the shortfall, and
  that the `FAILED` case produces no drawing at all.

### 2.3 The over-budget and unpriced paths

Both are unit-tested; neither has been exercised through the UI.

* A basket exceeding the budget limit.
* A recommendation referencing a catalog item that cannot be priced.

### 2.4 Mobile layout

At a 404 px viewport one table's right edge overran its container by about
22 px. The page did not scroll horizontally — the table was clipped. This is
cosmetic and app-side (not PDF), but it should either be fixed or explicitly
accepted and documented.

---

## 3. Known limitations to carry forward

1. **No PDF library installed.** The report tests use a small reader written for
   the suite. It checks the text layer, pagination, header repetition, font
   embedding and coordinates, but it is not a conformance validator. If Phase 7
   wants independent PDF verification, that is a new dependency decision for the
   project owner — it was deliberately not taken here.
2. **`ProjectResult` gained four fields** (`materials`, `color_direction`,
   `design_rationale`, `placement`). All are defaulted and legacy results still
   render, but any code constructing a `ProjectResult` by hand should populate
   them or the report will be thinner than the screen.
3. **`ui/report.py` re-runs the budget engine** via `ui.budget.compute_estimate`
   to obtain per-line detail, because the stored `BudgetAnalysis` is
   summary-only. This is the identical deterministic function on identical
   inputs, not a second source of truth — but it is a coupling to be aware of if
   the budget model ever changes.
4. **The stage strip has no "Not available yet" stage.** Four existing tests
   were updated for this spec change.
5. **Screenshots.** `docs/screenshots/` is still empty. Phase 6 captured browser
   screenshots for verification but did not add them to the repository, because
   `AGENTS.md` §14 assigns approved screenshots to Phase 9 and requires them to
   come from the running application.

---

## 4. Commands

```powershell
# Full suite
cd "[PROJECT_ROOT]"
& ".venv\Scripts\python.exe" -m pytest -q

# Targeted
& ".venv\Scripts\python.exe" -m pytest tests/test_report_generator.py tests/test_ui_report.py tests/test_ai_services.py -q

# Run the app
& ".venv\Scripts\python.exe" -m streamlit run app.py --server.port 8511 --server.headless true

# Check the collected PDF sample
& ".venv\Scripts\python.exe" -X utf8 <script using tests/test_report_generator.py helpers>
```

Notes for the next session:

* Use `.venv` (Python 3.13.18). The global 3.15.2 must not be used.
* `output/reports/` is gitignored and created on demand; a test run leaves it
  absent.
* Live AI calls need `DEPLOY_API_KEY` in the environment. Never print it.
* Streamlit emits harmless `missing ScriptRunContext!` warnings under AppTest.

---

## 5. Discipline reminders (from `AGENTS.md`, still binding)

* Stop after Phase 7's deliverables and wait for explicit approval before
  Phase 8.
* Do not add excluded V1 features (3D, images, vision, live pricing, auth,
  multi-room, microservices).
* Do not introduce dependencies without a stated technical requirement,
  including for "better testing".
* Do not weaken or retune a failing test to make an implementation look
  complete. Four tests were updated in Phase 6, each for a stated spec change,
  each recorded in `TEST_REPORT.md` §6.
* Git operations, commits, pushes and deployment all require explicit approval.
  None has been performed.

---

## 6. Suggested first action

Re-run the full suite to confirm the 1076 baseline, then run the brief analysis
three times live on the same input. That is the cheapest test of the one defect
this phase existed to fix, and it is the failure that was hardest to see.
