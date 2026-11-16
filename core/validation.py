"""Consolidated deterministic validation.

The room, spatial and budget engines each answer one question. This module is
the single place that answers "is this project acceptable, and what should the
user be told?".

Errors block progress; warnings do not. Nothing here calls the AI layer, the
network or Streamlit, so the whole report is reproducible from its inputs.

Scope note: these checks are structural and geometric. They do not claim
ergonomic, accessibility, structural or building-code compliance.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Sequence

from core.budget_engine import BudgetResult, compute_budget
from core.room_engine import (
    opening_conflict_messages,
    room_metrics,
    validate_room,
)
from core.spatial_engine import (
    DEFAULT_DOOR_CLEARANCE_CM,
    DEFAULT_WINDOW_CLEARANCE_CM,
    PlacementReport,
    validate_recommendations,
)
from models.schemas import (
    BudgetInput,
    DesignPreferences,
    FurnitureItem,
    FurnitureRecommendation,
    ProjectResult,
    RoomInput,
    SpatialValidation,
    UserRequirements,
)

#: Severity labels, kept as plain strings to match ``PlacementIssue``.
ERROR = "error"
WARNING = "warning"

#: Stages, used to group findings for the interface without string literals
#: scattered through the callers.
STAGE_ROOM = "room"
STAGE_CATALOG = "catalog"
STAGE_PLACEMENT = "placement"
STAGE_BUDGET = "budget"
STAGE_CONSISTENCY = "consistency"


@dataclass(frozen=True)
class ValidationFinding:
    """One message produced by a validation rule."""

    stage: str
    severity: str
    code: str
    message: str

    @property
    def is_error(self) -> bool:
        return self.severity == ERROR


@dataclass(frozen=True)
class ValidationReport:
    """Everything the interface needs to decide whether to continue."""

    findings: tuple[ValidationFinding, ...] = ()

    @property
    def errors(self) -> tuple[ValidationFinding, ...]:
        return tuple(f for f in self.findings if f.severity == ERROR)

    @property
    def warnings(self) -> tuple[ValidationFinding, ...]:
        return tuple(f for f in self.findings if f.severity == WARNING)

    @property
    def is_valid(self) -> bool:
        """True only when no blocking finding exists."""

        return not self.errors

    def messages(self, stage: str | None = None) -> list[str]:
        """Messages in insertion order, optionally for one stage only."""

        return [
            f.message
            for f in self.findings
            if stage is None or f.stage == stage
        ]

    def error_messages(self, stage: str | None = None) -> list[str]:
        return [f.message for f in self.errors if stage is None or f.stage == stage]

    def warning_messages(self, stage: str | None = None) -> list[str]:
        return [
            f.message for f in self.warnings if stage is None or f.stage == stage
        ]


def _finding(
    stage: str, severity: str, code: str, message: str
) -> ValidationFinding:
    return ValidationFinding(
        stage=stage, severity=severity, code=code, message=message
    )


# --------------------------------------------------------------------------- #
# Input validation
# --------------------------------------------------------------------------- #


def validate_room_input(room: RoomInput) -> list[ValidationFinding]:
    """Room dimensions, opening fit and door/window collisions."""

    findings = [
        _finding(STAGE_ROOM, ERROR, "invalid_room", message)
        for message in validate_room(room)
    ]
    findings.extend(
        _finding(STAGE_ROOM, ERROR, "opening_conflict", message)
        for message in opening_conflict_messages(room)
    )
    return findings


def validate_budget_input(budget: BudgetInput) -> list[ValidationFinding]:
    """A defined, non-negative budget is required before anything is priced."""

    findings: list[ValidationFinding] = []
    if not isinstance(budget.total_budget, Decimal):
        findings.append(
            _finding(
                STAGE_BUDGET,
                ERROR,
                "invalid_budget",
                "The budget must be expressed as a decimal money amount.",
            )
        )
    elif budget.total_budget < 0:
        findings.append(
            _finding(
                STAGE_BUDGET,
                ERROR,
                "invalid_budget",
                "The budget cannot be negative.",
            )
        )
    return findings


def validate_inputs(
    room: RoomInput,
    preferences: DesignPreferences,
    requirements: UserRequirements,
    budget: BudgetInput,
) -> list[ValidationFinding]:
    """Validate the four user-input models as one unit.

    The Pydantic models already constrain shape, so this function concentrates
    on cross-model facts and on producing user-facing messages.
    """

    findings = validate_room_input(room)
    findings.extend(validate_budget_input(budget))

    if (
        not preferences.material_preferences
        and not requirements.functional_requirements
    ):
        findings.append(
            _finding(
                STAGE_ROOM,
                WARNING,
                "thin_brief",
                "No material preferences or functional requirements were given, "
                "so the brief analysis will rely on style and palette alone.",
            )
        )

    # Only measurable when the dimensions are positive; a broken room is already
    # reported as an error above, so the area warning is simply skipped.
    if room.width_cm > 0 and room.length_cm > 0:
        area_sqm = room_metrics(room).area_sqm
        if area_sqm < 6.0:
            findings.append(
                _finding(
                    STAGE_ROOM,
                    WARNING,
                    "small_room",
                    f"The room is only {area_sqm:.1f} m², so usable floor area is "
                    "limited and fewer items will fit.",
                )
            )

    return findings


# --------------------------------------------------------------------------- #
# Catalog reference validation
# --------------------------------------------------------------------------- #


def validate_catalog_references(
    room: RoomInput,
    recommendations: Sequence[FurnitureRecommendation],
    catalog: Sequence[FurnitureItem],
) -> list[ValidationFinding]:
    """Every recommendation must point at a catalog item suited to this room."""

    by_id = {item.item_id: item for item in catalog}
    findings: list[ValidationFinding] = []

    for index, recommendation in enumerate(recommendations):
        item = by_id.get(recommendation.item_id)
        if item is None:
            findings.append(
                _finding(
                    STAGE_CATALOG,
                    ERROR,
                    "unknown_catalog_item",
                    f"Recommendation {index + 1} references unknown catalog item "
                    f"'{recommendation.item_id}'.",
                )
            )
            continue

        if room.room_type not in item.supported_room_types:
            findings.append(
                _finding(
                    STAGE_CATALOG,
                    ERROR,
                    "unsupported_room_type",
                    f"'{item.name}' is not part of the catalog selection for a "
                    f"{room.room_type.value}.",
                )
            )

    return findings


# --------------------------------------------------------------------------- #
# Adapters for engine results
# --------------------------------------------------------------------------- #


def placement_findings(report: PlacementReport) -> list[ValidationFinding]:
    """Lift placement issues into the shared finding vocabulary."""

    return [
        _finding(
            STAGE_PLACEMENT,
            issue.severity,
            issue.code,
            issue.message,
        )
        for issue in report.issues
    ]


def spatial_validation_findings(
    validation: SpatialValidation,
) -> list[ValidationFinding]:
    """Read a persisted ``SpatialValidation`` back into findings.

    Used when the interface resumes a project: the validation model does not
    preserve codes, so generic ones are used while the severity is preserved.
    """

    findings: list[ValidationFinding] = [
        _finding(STAGE_PLACEMENT, ERROR, "outside_room", message)
        for message in validation.boundary_violations
    ]
    findings.extend(
        _finding(STAGE_PLACEMENT, ERROR, "furniture_overlap", message)
        for message in validation.overlaps
    )
    findings.extend(
        _finding(STAGE_PLACEMENT, WARNING, "placement_warning", message)
        for message in validation.warnings
    )

    if validation.is_valid and (validation.boundary_violations or validation.overlaps):
        findings.append(
            _finding(
                STAGE_CONSISTENCY,
                ERROR,
                "inconsistent_spatial_validation",
                "The spatial result is marked valid but still lists blocking "
                "problems.",
            )
        )

    return findings


def budget_findings(result: BudgetResult) -> list[ValidationFinding]:
    """Lift budget errors and warnings into the shared vocabulary."""

    findings: list[ValidationFinding] = [
        _finding(STAGE_BUDGET, ERROR, error.code, error.message)
        for error in result.errors
    ]
    findings.extend(
        _finding(STAGE_BUDGET, WARNING, "budget_notice", warning)
        for warning in result.warnings
    )
    return findings


# --------------------------------------------------------------------------- #
# Stored-result consistency
# --------------------------------------------------------------------------- #


def validate_result_consistency(
    result: ProjectResult, catalog: Sequence[FurnitureItem]
) -> list[ValidationFinding]:
    """Check that a stored ``ProjectResult`` agrees with its own inputs.

    Stored results can outlive their inputs (session state, a reloaded report),
    so the recorded arithmetic and flags are recomputed rather than trusted.
    """

    findings: list[ValidationFinding] = []
    analysis = result.budget_analysis

    expected_total = (
        analysis.furniture_subtotal
        + analysis.material_subtotal
        + analysis.other_expenses
    )
    if expected_total != analysis.total_estimated:
        findings.append(
            _finding(
                STAGE_CONSISTENCY,
                ERROR,
                "budget_total_mismatch",
                "The recorded budget total does not equal the sum of its "
                "components.",
            )
        )

    expected_remaining = result.budget.total_budget - analysis.total_estimated
    if expected_remaining != analysis.remaining_budget:
        findings.append(
            _finding(
                STAGE_CONSISTENCY,
                ERROR,
                "budget_remaining_mismatch",
                "The recorded remaining budget does not match the budget minus "
                "the estimate.",
            )
        )

    expected_over = analysis.total_estimated > result.budget.total_budget
    if expected_over != analysis.is_over_budget:
        findings.append(
            _finding(
                STAGE_CONSISTENCY,
                ERROR,
                "budget_flag_mismatch",
                "The recorded over-budget flag contradicts the recorded totals.",
            )
        )

    findings.extend(
        validate_catalog_references(
            result.room, result.recommendations, catalog
        )
    )

    if result.spatial_validation.is_valid and analysis.is_over_budget:
        findings.append(
            _finding(
                STAGE_CONSISTENCY,
                WARNING,
                "over_budget_but_spatially_valid",
                "The layout is geometrically valid but exceeds the stated budget.",
            )
        )

    return findings


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #


#: Codes that have one authoritative stage. When several engines report the
#: same problem (a missing catalog item is visible to the catalog, spatial and
#: budget engines at once), only the authoritative stage's finding is shown, so
#: the user is not told the same thing three times. The engines' own reports
#: still carry their detail for debugging.
_AUTHORITATIVE_STAGE: dict[str, str] = {
    "unknown_catalog_item": STAGE_CATALOG,
    "unsupported_room_type": STAGE_CATALOG,
}


def _resolve_duplicates(
    findings: Iterable[ValidationFinding],
) -> list[ValidationFinding]:
    """Keep one finding per authoritative code, preferring its owning stage."""

    ordered = list(findings)
    reported_authoritatively = {
        finding.code
        for finding in ordered
        if _AUTHORITATIVE_STAGE.get(finding.code) == finding.stage
    }

    resolved: list[ValidationFinding] = []
    for finding in ordered:
        owner = _AUTHORITATIVE_STAGE.get(finding.code)
        if owner is not None and owner != finding.stage:
            if finding.code in reported_authoritatively:
                continue
            # The owning stage said nothing: keep the finding rather than lose
            # a real problem just because it came from a later engine.
        resolved.append(finding)
    return resolved


def run_validation(
    room: RoomInput,
    preferences: DesignPreferences,
    requirements: UserRequirements,
    budget: BudgetInput,
    recommendations: Sequence[FurnitureRecommendation],
    catalog: Sequence[FurnitureItem],
    *,
    material_subtotal: Decimal | int | float | str = Decimal("0.00"),
    other_expenses: Decimal | int | float | str = Decimal("0.00"),
    door_clearance_cm: float = DEFAULT_DOOR_CLEARANCE_CM,
    window_clearance_cm: float = DEFAULT_WINDOW_CLEARANCE_CM,
) -> tuple[ValidationReport, PlacementReport, BudgetResult]:
    """Run every deterministic check for one candidate layout.

    Returns the consolidated report together with the two engine results, so
    the caller can persist ``SpatialValidation`` and ``BudgetAnalysis`` without
    recomputing anything.
    """

    findings: list[ValidationFinding] = validate_inputs(
        room, preferences, requirements, budget
    )
    findings.extend(validate_catalog_references(room, recommendations, catalog))

    placement, _ = validate_recommendations(
        room,
        recommendations,
        catalog,
        door_clearance_cm=door_clearance_cm,
        window_clearance_cm=window_clearance_cm,
    )
    findings.extend(placement_findings(placement))

    budget_result = compute_budget(
        budget,
        recommendations,
        catalog,
        material_subtotal=material_subtotal,
        other_expenses=other_expenses,
    )
    findings.extend(budget_findings(budget_result))

    return (
        ValidationReport(findings=tuple(_resolve_duplicates(findings))),
        placement,
        budget_result,
    )


def merge_findings(
    *groups: Iterable[ValidationFinding],
) -> ValidationReport:
    """Combine findings from several sources into one report.

    Uses the same de-duplication as :func:`run_validation`, so merging engine
    output never repeats one problem more than once.
    """

    merged: list[ValidationFinding] = []
    for group in groups:
        merged.extend(group)
    return ValidationReport(findings=tuple(_resolve_duplicates(merged)))


__all__ = [
    "ERROR",
    "STAGE_BUDGET",
    "STAGE_CATALOG",
    "STAGE_CONSISTENCY",
    "STAGE_PLACEMENT",
    "STAGE_ROOM",
    "WARNING",
    "ValidationFinding",
    "ValidationReport",
    "budget_findings",
    "merge_findings",
    "placement_findings",
    "run_validation",
    "spatial_validation_findings",
    "validate_budget_input",
    "validate_catalog_references",
    "validate_inputs",
    "validate_result_consistency",
    "validate_room_input",
]
