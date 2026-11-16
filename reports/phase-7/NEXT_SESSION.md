# Phase 7 → Next Session

**Handover date:** 16 November 2026
**State:** Phase 7 QA complete. Full suite **1098 passed, 0 failed, 0 skipped**.
**Decision:** ready for Phase 8; **not** ready for portfolio publication.

---

## 1. Read these first, in order

1. `reports/phase-7/RELEASE_READINESS.md` — the verdict and the four open items.
2. `reports/phase-7/TEST_REPORT.md` — evidence for every category.
3. `reports/phase-7/COMPLETION_REPORT.md` — what changed and why.
4. `AGENTS.md` — the approval rule still applies: stop after each phase.

---

## 2. Environment state at handover

| Item | Value |
|---|---|
| Working directory | `[PROJECT_ROOT]` |
| Virtualenv | `.venv` (Python 3.13.18) |
| Streamlit | running on `http://localhost:8512` |
| CSS fixture server | `http://127.0.0.1:8513` |
| Git | **no repository**; nothing committed |
| Secrets | `DEPLOY_API_KEY` in the process environment; never written to disk |

PIDs change on every restart. Always re-check rather than trusting this file:

```powershell
Get-NetTCPConnection -LocalPort 8512 -State Listen | Select-Object LocalPort, OwningProcess
```

**The machine was left running at the end of this session.** No shutdown,
restart, sleep, hibernate or sign-out was executed, per the final instruction.

---

## 3. Non-obvious things that will save you time

### 3.1 Editing a `.py` file invalidates the live Streamlit session

The running process can keep a stale `WorkflowState` class, producing:

```text
TypeError: The session contains a value that is not a WorkflowState under 'hm_workflow_state'
```

This is a **development hot-reload artefact, proven twice**: it appears
immediately after a source edit and never in a fresh process. **Restart the
server after source changes and open a fresh browser session.** Do not "fix" it
in product code.

```powershell
$p = (Get-NetTCPConnection -LocalPort 8512 -State Listen).OwningProcess
Stop-Process -Id $p -Force
# then start again:
.venv\Scripts\python.exe -m streamlit run app.py --server.port 8512 `
    --server.headless true --browser.gatherUsageStats false
```

### 3.2 Reading PDF text

Streams are Flate-compressed and fonts are Identity-H with 2-byte CIDs, so
`pdftotext`-style assumptions fail. Use the helpers that already work:

```python
from tests.test_report_generator import pdf_pages, pdf_text, page_count
```

Known artefact: extracted text contains `\x7f` where the PDF uses a private-use
bullet glyph. 62 of them in both old and new reports — pre-existing, ignore.

### 3.3 Producing a PARTIAL layout reliably

A **100 × 100 cm** room reliably yields 1 of 3 placed. Room name, dimensions and
budget are enough; the AI is not needed to reproduce placement behaviour if you
build the models directly (see the probes below).

### 3.4 Streamlit widget recipes that actually work

- **Number/text inputs:** focus the element, use the native value setter from
  `Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')`,
  then dispatch both `input` and `change`, then blur.
- **Multiselect:** focus → native setter → `input` event → type a letter → press
  `Enter` to commit the "Add: X" option.
- **Card selection:** find `[class*="st-key-<key>"]`, click its `Choose` button,
  then verify via the `.hm-badge` text equalling `SELECTED`.
- **Clicks race reruns.** Click, then wait for the expected text before the next
  action. A click returning `ok` is not proof the rerun finished.

### 3.5 QA probes are outside the repository

In `C:\Users\[LOCAL_USER]\AppData\Local\Temp\opencode\`:

| File | Purpose | Last result |
|---|---|---|
| `probe_failed_heading.py` | COMPLETE / PARTIAL / FAILED headings from real PDF text | 17/17 |
| `probe_unpriced.py` | unpriced furniture across engine, prompt, PDF | 18/18 |
| `probe_long_turkish.py` | long names, long brief, Turkish glyphs in the PDF | 20/20 |
| `probe_live_long_pdf.py` | reads back the live-generated PDF | 12/12 |

They are deliberately not in `tests/`: they are instruments, not product
assertions. If a scenario becomes a permanent guarantee, write it as a pytest
test in the right file instead.

---

## 4. What Phase 7 changed (so you do not undo it)

| Area | Change | Guarded by |
|---|---|---|
| Money formatting | one `format_money` in `core.budget_engine`; `ui.commits` and `core.report_generator` delegate | `test_budget_engine.py` ×2, `test_ui_commits.py`, `test_report_generator.py` parity test |
| Evaluator materials | the zero `material_subtotal` is withheld; a note says cost is unknown | `test_ai_services.py` ×2 |
| Evaluator completeness | a placement block is sent; unplaced items and reasons included | `test_ai_services.py` ×3, `test_ui_evaluation.py` ×1 |
| Partial plan wording | `placement_plan_svg(partial=…)`; no "validated" for a partial plan | `test_ui_presentation.py` ×2 |
| PDF headings | three-way plan heading and cover phrase | `test_report_generator.py` ×2 |
| Budget snapshot guard | the PDF refuses to build when recomputed costs disagree | `test_ui_report.py` ×2 |

If you change any of these, the tests are designed to stop you. Do not retune
them without a spec change.

---

## 5. Suggested next actions

1. **Answer the two PARTIALs first**, because they are the only categories that
   are not fully verified:
   - real multi-viewport run at 320 / 768 / 1024 / 1440 px;
   - a real accessibility pass (screen reader and/or `axe`) on the plan and
     report screens.
2. **Then Phase 8** per `DEVELOPMENT_PLAN.md`: interface polish and final
   validation.
3. **Then Phase 9**: `README.md`, `README.tr.md`, real screenshots in
   `docs/screenshots/`, licence records for the reference images.

Do not start Phase 8 without the project owner's explicit approval — `AGENTS.md`
§4 requires a stop and review between phases.

---

## 6. Open questions for the project owner

1. Should `material_subtotal` be removed from `BudgetAnalysis` in a later phase?
   It is always zero in V1 and, although every surface now describes it
   correctly, its presence still invites the misreading that Phase 7 fixed at the
   wording level. Removing it is a model change and needs approval.
2. Is a CSS-fixture responsive measurement acceptable evidence for publication,
   or must every claim rest on a live browser at each width? The current
   recommendation is the latter.
3. Which reference-image licences are already cleared? `AGENTS.md` §11 requires
   source, licence, attribution and filename, and no image may ship without them.
