# Next Session — Phase 5 / Step 6 → Phase 6

**Read this file first.** Everything else is in
`reports/phase-5-step-6/COMPLETION_REPORT.md`.

---

## Where the project stands

* Phases 0–4 complete and approved.
* Phase 5 Steps 1–6 complete. **996 tests pass, 0 failed, 0 skipped.**
* The whole V1 workflow now exists except the PDF report:
  Room Setup → Design Preferences → Input Review → Brief Analysis → Concept
  Selection → Furniture, Materials & Plan → **Design Evaluation** → **Budget
  Analysis**.

## What Step 6 added

| File | What it is |
|---|---|
| `ui/budget.py` | The one seam over `core.budget_engine`. `compute_estimate`, `matches`, `MATERIALS_NOTE`, `INDICATIVE_NOTE`, `INCOMPLETE_NOTE`, `usage_text`, `unpriced_errors`. No arithmetic. |
| `ui/pages_evaluation.py` | AI operation 4. Button-only, engine verdicts printed above the AI prose, six schema fields and nothing else. |
| `ui/pages_budget.py` | Total → limit → remaining/overrun, item table, subtotals, errors, unpriced materials, Matplotlib bar chart. Never calculates. |
| `ui/ai_actions.py` | `evaluate_design(...)` added (lazy `ai` import). |
| `ui/pages_plan.py` | `_place_and_store` also records the estimate; forward button to the evaluation. |
| `ui/session.py`, `ui/shell.py`, `app.py` | Two screen ids, stage remap, routing. |
| `tests/test_ui_evaluation.py`, `tests/test_ui_budget.py` | 25 + 24 tests, mock-only. |

## Decisions that must not be undone casually

1. **The estimate is recorded on the plan step.** `STEP_PREREQUISITES` makes the
   evaluation require both `SPATIAL_VALIDATION` and `BUDGET_ANALYSIS`, but the
   budget *screen* comes last. The plan step therefore prices the basket it just
   placed. Do not "fix" this by reordering the screens or by editing the
   prerequisite table.
2. **`ui.shell.STAGES`** puts `DESIGN_EVALUATION` and `BUDGET_ANALYSIS` under
   "Design Plan" and leaves "Final Report" = `(FINAL_RESULT,)`. That is why
   exactly one stage reads "Not available yet".
3. **The evaluation screen shows no score and no verdict.** `DesignEvaluation`
   has no such field. If the project owner wants one, that is a schema change to
   approve first.
4. **Materials stay unpriced.** There is no material price list; never cost them
   at zero or guess a figure.
5. **`ui/budget.py` and `ui/pages_budget.py` must stay arithmetic-free.** All
   money comes from `core.budget_engine`.

## Running things

```powershell
cd "[PROJECT_ROOT]"
& ".venv\Scripts\python.exe" -m pytest -q                      # 996 pass
& ".venv\Scripts\python.exe" -m streamlit run app.py
```

Note: `pytest` and `streamlit` must come from `.venv` (Python 3.13.18). The global
3.15.2 interpreter is not configured for this project.

## Open issue, unrelated to Step 6

The **brief step fails against the live provider**: the response is truncated
before the JSON closes ("The AI answer was cut off before it finished…"). It was
reproduced twice. Nothing is stored, the error copy is correct, and the defect is
in the approved Step 4 configuration (`MAX_TOKENS`), not in the interface. This
blocks any live end-to-end run, including the new screens. Worth resolving before
or alongside Phase 6, since the PDF needs a complete project.

## Next stage

**Phase 6 — PDF Report Generation.**

* `WorkflowState.finalize()` already returns a complete `ProjectResult`.
* `FINAL_RESULT` is the only incomplete step; the stage strip already reserves
  "Final Report" for it.
* ReportLab is in the approved stack and installed.
* The screenshots required by `DESIGN_SYSTEM.md` / `AGENTS.md` §14 belong to
  Phase 9; `docs/screenshots/` is still empty and nothing was added to it.
