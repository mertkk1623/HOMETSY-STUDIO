"""The deterministic half of the Final Report step.

Plain Python: no Streamlit, no AI, no session state. This module is the one seam
between the workflow/reporting layers and the report screen, so the screen can
stay presentation-only and the rules about *when* a report may exist are written
once.

What it does not do
-------------------
No arithmetic, no geometry, no finalization. It finalizes through
:meth:`workflow.state.WorkflowState.finalize` — the only place a
``ProjectResult`` is created — and then asks ``core.report_generator`` to lay the
result out.

Why the file is kept in the session
-----------------------------------
:class:`ReportArtifact` records the file that was produced *and* the result it
was produced from. A rerun must not regenerate the PDF (``AGENTS.md`` §10: a
rerun is not an action), so the artifact is what the download button points at,
and it is discarded as soon as the finalized result it describes is no longer
current. Comparing identity rather than content is deliberate: the state clears
``result`` on any invalidation, so "same object" and "still current" are the same
question.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core import report_generator
from core.budget_engine import BudgetResult
from core.report_generator import ReportGenerationError
from models.schemas import FurnitureItem, ProjectResult
from workflow.state import WorkflowState, WorkflowStep

from ui import budget as budget_view


@dataclass(frozen=True)
class ReportArtifact:
    """A generated PDF and the exact result it was generated from."""

    path: Path
    result: ProjectResult
    filename: str

    @property
    def size_bytes(self) -> int:
        try:
            return self.path.stat().st_size
        except OSError:
            return 0


def is_current(artifact: ReportArtifact | None, state: WorkflowState) -> bool:
    """True when the artifact still describes the project as it stands."""

    return (
        artifact is not None
        and state.result is not None
        and artifact.result is state.result
    )


def can_finalize(state: WorkflowState) -> bool:
    """True when every step before the report is complete.

    Asked through ``missing_prerequisites`` rather than by inspecting fields, so
    the workflow's own table stays the single rule for what finalization needs.
    """

    return not state.missing_prerequisites(WorkflowStep.FINAL_RESULT)


def finalize_and_build(
    state: WorkflowState,
    *,
    catalog: list[FurnitureItem] | tuple[FurnitureItem, ...] | None = None,
    output_dir: Path | None = None,
) -> ReportArtifact:
    """Finalize the project, then write its PDF.

    Two separate failures are kept apart on purpose:

    * finalization raising means the project is not complete, so no PDF is
      attempted at all and no ``ProjectResult`` is stored;
    * report generation raising happens *after* ``state.result`` exists, so the
      finalized result survives and the report can simply be generated again.

    The caller shows a message in both cases; neither is reported as a success.

    The estimate is re-derived from the stored basket because the report needs
    per-line detail the stored ``BudgetAnalysis`` only summarises. That second
    computation is only sound while it reproduces the figures the project was
    finalised with, so it is checked against them here rather than assumed:
    a PDF quoting one snapshot's line items beside another snapshot's totals
    would be worse than no PDF. A mismatch can only come from a caller passing
    a different catalog, and it fails loudly instead of producing the file.
    """

    result = state.finalize()
    estimate = estimate_for(state, catalog)
    if estimate.analysis != result.budget_analysis:
        raise ReportGenerationError(
            "The cost figures could not be reproduced for the report, so no "
            "file was produced. Your project data is unchanged and the report "
            "can be generated again."
        )
    path = report_generator.generate_report(
        result,
        catalog=tuple(catalog) if catalog is not None else _default_catalog(),
        budget=estimate,
        output_dir=output_dir,
    )
    return ReportArtifact(
        path=path,
        result=result,
        filename=path.name,
    )


def estimate_for(
    state: WorkflowState,
    catalog: list[FurnitureItem] | tuple[FurnitureItem, ...] | None = None,
) -> BudgetResult:
    """The itemised budget for the stored basket.

    The report needs the per-line table and the priced-line list, which the
    stored :class:`models.schemas.BudgetAnalysis` only summarises. Re-running
    ``core.budget_engine`` is not new arithmetic: it is the same deterministic
    function on the same inputs, and :func:`ui.budget.matches` asserts the stored
    analysis agrees with it before the report screen is reachable.
    """

    assert state.budget is not None
    return budget_view.compute_estimate(
        state.budget,
        state.furniture,
        catalog if catalog is not None else _default_catalog(),
    )


def _default_catalog() -> tuple[FurnitureItem, ...]:
    from ui import references

    return references.load_catalog()


def report_error_message(error: BaseException) -> str:
    """A sentence for the user. Never a traceback, never provider wording."""

    if isinstance(error, ReportGenerationError):
        return str(error)
    return (
        "The PDF report could not be generated, so no file was produced. Your "
        "project data is unchanged and the report can be generated again."
    )


__all__ = [
    "ReportArtifact",
    "can_finalize",
    "estimate_for",
    "finalize_and_build",
    "is_current",
    "report_error_message",
]
