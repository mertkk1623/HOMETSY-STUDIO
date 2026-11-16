"""Workflow state: what the user entered, what was derived, and what is stale.

The state is a plain Python object. It holds validated Pydantic models, records
results the caller produced, and drops anything whose inputs changed. It never
calls the AI, never touches the network, and never computes geometry or money.

Two rules shape the whole design:

**A step cannot run before its prerequisites are complete.** :meth:`guard`
refuses, and every ``record_*`` method guards first, so an impossible state
cannot be stored even if the interface has a bug.

**A result cannot outlive what it came from.** Every mutation compares the new
value with the old one, stores it, and invalidates everything downstream via
:func:`workflow.dependencies.invalidated_by`. Re-entering an identical value is
a no-op, so a widget that fires on every rerun does not destroy the user's work.

Failures are the caller's problem to report, not the state's to remember: if an
AI call raises, the caller never reaches ``record_*`` and the state is exactly
as it was. :meth:`attempt` makes that contract explicit.

Furniture and materials are stored separately on purpose. They arrive in one
:class:`models.schemas.DesignRecommendation`, but they have different
dependents: replacing the basket invalidates the layout and the price, while
swapping a material leaves a measured layout perfectly valid. Keeping them in
one field would force both to be discarded together.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence, TypeVar

from models.schemas import (
    BudgetAnalysis,
    BudgetInput,
    ConceptCollection,
    DesignBrief,
    DesignConcept,
    DesignEvaluation,
    DesignPreferences,
    DesignRecommendation,
    FurnitureRecommendation,
    MaterialRecommendation,
    PlacementOutcome,
    ProjectResult,
    RoomInput,
    SpatialValidation,
    UserRequirements,
)
from workflow.dependencies import DataKey, invalidated_by

#: Return type of :meth:`WorkflowState.attempt`.
ResultT = TypeVar("ResultT")


# --------------------------------------------------------------------------- #
# Steps
# --------------------------------------------------------------------------- #


class WorkflowStep(str, Enum):
    """The ten stages of the V1 journey, in the order the user walks them.

    Values are stable identifiers; :data:`STEP_LABELS` carries the interface
    text so that renaming a label never changes a stored or asserted value.
    """

    ROOM_INFORMATION = "room_information"
    DESIGN_PREFERENCES = "design_preferences"
    BRIEF_ANALYSIS = "brief_analysis"
    CONCEPT_GENERATION = "concept_generation"
    CONCEPT_SELECTION = "concept_selection"
    RECOMMENDATIONS = "recommendations"
    SPATIAL_VALIDATION = "spatial_validation"
    BUDGET_ANALYSIS = "budget_analysis"
    DESIGN_EVALUATION = "design_evaluation"
    FINAL_RESULT = "final_result"


#: Fixed order, matching the approved workflow in ``PROJECT_BRIEF.md`` §5.
STEP_ORDER: tuple[WorkflowStep, ...] = tuple(WorkflowStep)

STEP_LABELS: dict[WorkflowStep, str] = {
    WorkflowStep.ROOM_INFORMATION: "Room information",
    WorkflowStep.DESIGN_PREFERENCES: "Design preferences and requirements",
    WorkflowStep.BRIEF_ANALYSIS: "Brief analysis",
    WorkflowStep.CONCEPT_GENERATION: "Concept generation",
    WorkflowStep.CONCEPT_SELECTION: "Concept selection",
    WorkflowStep.RECOMMENDATIONS: "Furniture and material recommendations",
    WorkflowStep.SPATIAL_VALIDATION: "Spatial validation",
    WorkflowStep.BUDGET_ANALYSIS: "Budget analysis",
    WorkflowStep.DESIGN_EVALUATION: "Design evaluation",
    WorkflowStep.FINAL_RESULT: "Final project result",
}

#: Each step's *direct* prerequisites. Whole-order correctness follows from the
#: chain, and ``is_complete`` recurses through it.
STEP_PREREQUISITES: dict[WorkflowStep, tuple[WorkflowStep, ...]] = {
    WorkflowStep.ROOM_INFORMATION: (),
    WorkflowStep.DESIGN_PREFERENCES: (WorkflowStep.ROOM_INFORMATION,),
    WorkflowStep.BRIEF_ANALYSIS: (
        WorkflowStep.ROOM_INFORMATION,
        WorkflowStep.DESIGN_PREFERENCES,
    ),
    WorkflowStep.CONCEPT_GENERATION: (WorkflowStep.BRIEF_ANALYSIS,),
    WorkflowStep.CONCEPT_SELECTION: (WorkflowStep.CONCEPT_GENERATION,),
    WorkflowStep.RECOMMENDATIONS: (WorkflowStep.CONCEPT_SELECTION,),
    # Geometry and price are independent of each other: once a basket exists, a
    # layout can be measured and a total worked out in either order.
    WorkflowStep.SPATIAL_VALIDATION: (WorkflowStep.RECOMMENDATIONS,),
    WorkflowStep.BUDGET_ANALYSIS: (WorkflowStep.RECOMMENDATIONS,),
    WorkflowStep.DESIGN_EVALUATION: (
        WorkflowStep.SPATIAL_VALIDATION,
        WorkflowStep.BUDGET_ANALYSIS,
    ),
    WorkflowStep.FINAL_RESULT: (WorkflowStep.DESIGN_EVALUATION,),
}


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #


class WorkflowError(Exception):
    """Base class for refusals raised by the workflow layer."""


class PrerequisiteError(WorkflowError):
    """A step was requested before the steps it depends on were complete."""

    def __init__(self, step: WorkflowStep, missing: tuple[WorkflowStep, ...]) -> None:
        self.step = step
        self.missing = missing
        listed = ", ".join(STEP_LABELS[item] for item in missing)
        super().__init__(
            f"Cannot run '{STEP_LABELS[step]}' yet: it needs {listed} first."
        )


class IncompleteWorkflowError(WorkflowError):
    """A final result was requested while steps were still outstanding."""

    def __init__(self, missing: tuple[WorkflowStep, ...]) -> None:
        self.missing = missing
        listed = ", ".join(STEP_LABELS[item] for item in missing)
        super().__init__(f"The workflow is not complete yet: {listed} remain.")


class StepFailed(WorkflowError):
    """A step's work raised. The state was not modified.

    The original exception is chained, so the interface can show the real cause
    (a timeout, an unusable answer) rather than a generic failure.
    """

    def __init__(self, step: WorkflowStep, cause: BaseException) -> None:
        self.step = step
        self.cause = cause
        super().__init__(
            f"'{STEP_LABELS[step]}' failed and nothing was saved: {cause}"
        )


# --------------------------------------------------------------------------- #
# Room change detection
# --------------------------------------------------------------------------- #


def _basket_requests(
    recommendations: Sequence[FurnitureRecommendation],
) -> tuple[tuple[str, int, str], ...]:
    """The part of a basket the user actually asked for.

    Coordinates and rotation are excluded because ``apply_placements`` writes
    both onto the stored copy: the engine's chosen orientation replaces the
    advisor's hint. They annotate a placement, they do not define a request, so
    comparing them would make an unchanged basket look new.
    """

    return tuple(
        (item.item_id, item.quantity, item.rationale)
        for item in recommendations
    )


def unplace_recommendation(
    recommendation: FurnitureRecommendation,
) -> FurnitureRecommendation:
    """The same recommendation with the engine's coordinates removed.

    The basket's identity is its items, quantities and rationale; the
    coordinates are an annotation produced by one placement run. When that run
    stops applying — the room changed, a different concept was selected — the
    annotation has to go with it, or a stored position would outlive the
    validation that justified it. Everything the budget depends on is kept.
    """

    if (
        recommendation.positions == []
        and recommendation.position_x_cm is None
        and recommendation.position_y_cm is None
    ):
        return recommendation
    return recommendation.model_copy(
        update={
            "position_x_cm": None,
            "position_y_cm": None,
            "positions": [],
        }
    )


def room_change_keys(before: RoomInput, after: RoomInput) -> frozenset[DataKey]:
    """Which room facts actually differ between two versions.

    Splitting the room into three keys is what lets a door move without
    invalidating the budget: openings do not reach a price. Comparing whole
    ``RoomInput`` objects would invalidate everything on any edit.
    """

    changed: set[DataKey] = set()

    if before.room_type is not after.room_type:
        changed.add(DataKey.ROOM_TYPE)

    if (
        before.width_cm != after.width_cm
        or before.length_cm != after.length_cm
        or before.ceiling_height_cm != after.ceiling_height_cm
    ):
        changed.add(DataKey.ROOM_DIMENSIONS)

    if before.door != after.door or before.window != after.window:
        changed.add(DataKey.ROOM_OPENINGS)

    return frozenset(changed)


# --------------------------------------------------------------------------- #
# State
# --------------------------------------------------------------------------- #


@dataclass
class WorkflowState:
    """The whole project, in memory, with staleness enforced.

    Construct with no arguments for a fresh project, or by keyword to resume
    one. Inputs are optional because a user starts with nothing typed; results
    are optional because they exist only after their step has actually run.
    """

    # --- User input ------------------------------------------------------- #
    room: RoomInput | None = None
    preferences: DesignPreferences | None = None
    requirements: UserRequirements | None = None
    budget: BudgetInput | None = None

    # --- Captured results ------------------------------------------------- #
    brief: DesignBrief | None = None
    concepts: ConceptCollection | None = None
    selected_concept: DesignConcept | None = None

    #: Recommended catalog items, with the advisor's narrative. Stored apart
    #: from materials because the two invalidate different things.
    furniture: tuple[FurnitureRecommendation, ...] = ()
    materials: tuple[MaterialRecommendation, ...] = ()
    color_direction: str = ""
    design_rationale: str = ""

    spatial: SpatialValidation | None = None
    #: The layout that produced :attr:`spatial`, in a drawable form. Stored under
    #: the same ``DataKey.SPATIAL`` because a layout and its verdict are one fact:
    #: keeping them as two keys would let a validated plan outlive its geometry.
    placement: PlacementOutcome | None = None
    budget_analysis: BudgetAnalysis | None = None
    evaluation: DesignEvaluation | None = None

    #: The finalised snapshot, produced by :meth:`finalize`. Holding it is what
    #: makes ``FINAL_RESULT`` a real step rather than a derived side effect: the
    #: report is generated on purpose, once, from a complete workflow.
    result: ProjectResult | None = None

    #: History of what each mutation discarded, newest last. Kept so the
    #: interface can explain a reset ("your recommendations were cleared because
    #: the room changed") and for tests. Never used to make decisions.
    invalidation_log: list[tuple[DataKey, tuple[DataKey, ...]]] = field(
        default_factory=list, repr=False
    )

    # ------------------------------------------------------------------ #
    # Completeness
    # ------------------------------------------------------------------ #

    def data_for(self, key: DataKey) -> object | None:
        """The stored value behind a key, or ``None`` when absent."""

        mapping: dict[DataKey, object | None] = {
            DataKey.ROOM_TYPE: self.room,
            DataKey.ROOM_DIMENSIONS: self.room,
            DataKey.ROOM_OPENINGS: self.room,
            DataKey.PREFERENCES: self.preferences,
            DataKey.REQUIREMENTS: self.requirements,
            DataKey.BUDGET: self.budget,
            DataKey.BRIEF: self.brief,
            DataKey.CONCEPTS: self.concepts,
            DataKey.SELECTED_CONCEPT: self.selected_concept,
            DataKey.FURNITURE: self.furniture or None,
            DataKey.MATERIALS: self.materials or None,
            DataKey.SPATIAL: self.spatial,
            DataKey.BUDGET_ANALYSIS: self.budget_analysis,
            DataKey.EVALUATION: self.evaluation,
        }
        return mapping[key]

    def is_complete(self, step: WorkflowStep) -> bool:
        """True when the step's own data exists and its prerequisites are done.

        Derived rather than stored, so invalidation cannot leave a stale
        "completed" flag behind: there is only one source of truth.
        """

        if not self._has_step_data(step):
            return False
        return all(self.is_complete(item) for item in STEP_PREREQUISITES[step])

    def _has_step_data(self, step: WorkflowStep) -> bool:
        own_data: dict[WorkflowStep, bool] = {
            WorkflowStep.ROOM_INFORMATION: self.room is not None,
            WorkflowStep.DESIGN_PREFERENCES: all(
                value is not None
                for value in (self.preferences, self.requirements, self.budget)
            ),
            WorkflowStep.BRIEF_ANALYSIS: self.brief is not None,
            WorkflowStep.CONCEPT_GENERATION: self.concepts is not None,
            WorkflowStep.CONCEPT_SELECTION: self.selected_concept is not None,
            WorkflowStep.RECOMMENDATIONS: bool(self.furniture),
            WorkflowStep.SPATIAL_VALIDATION: self.spatial is not None,
            WorkflowStep.BUDGET_ANALYSIS: self.budget_analysis is not None,
            WorkflowStep.DESIGN_EVALUATION: self.evaluation is not None,
            WorkflowStep.FINAL_RESULT: self.result is not None,
        }
        return own_data[step]

    @property
    def completed_steps(self) -> tuple[WorkflowStep, ...]:
        return tuple(step for step in STEP_ORDER if self.is_complete(step))

    @property
    def next_step(self) -> WorkflowStep | None:
        """The first incomplete step, or ``None`` when the project is finished."""

        for step in STEP_ORDER:
            if not self.is_complete(step):
                return step
        return None

    @property
    def is_finished(self) -> bool:
        return self.next_step is None

    def missing_prerequisites(self, step: WorkflowStep) -> tuple[WorkflowStep, ...]:
        """Direct prerequisites of ``step`` that are not satisfied yet."""

        return tuple(
            item for item in STEP_PREREQUISITES[step] if not self.is_complete(item)
        )

    def guard(self, step: WorkflowStep) -> None:
        """Refuse to run ``step`` unless everything it needs is in place."""

        missing = self.missing_prerequisites(step)
        if missing:
            raise PrerequisiteError(step, missing)

    # ------------------------------------------------------------------ #
    # Mutation core
    # ------------------------------------------------------------------ #

    def _replace(
        self, keys: Sequence[DataKey], assign: Callable[[], None]
    ) -> tuple[DataKey, ...]:
        """Assign new value(s) and discard everything derived from the old ones.

        ``assign`` performs the write; the caller has already established that
        the value genuinely changed. Returns the keys that were discarded, in
        declared order. A key that is itself being replaced is not reported as
        invalidated: it was refreshed, not thrown away.
        """

        assign()
        dropped: set[DataKey] = set()
        for key in keys:
            dropped.update(invalidated_by(key))
        dropped.difference_update(keys)

        ordered = tuple(item for item in DataKey if item in dropped)
        for stale in ordered:
            self._clear(stale)
        if ordered:
            self.invalidation_log.append((keys[0], ordered))
        return ordered

    def _clear(self, key: DataKey) -> None:
        """Drop one derived value. Inputs are never cleared by invalidation."""

        # The finalised snapshot depends on everything, so any invalidation
        # makes it stale. Clearing it here keeps that fact in one place.
        self.result = None

        if key is DataKey.BRIEF:
            self.brief = None
        elif key is DataKey.CONCEPTS:
            self.concepts = None
        elif key is DataKey.SELECTED_CONCEPT:
            self.selected_concept = None
        elif key is DataKey.FURNITURE:
            # Materials deliberately survive: the table in the step brief lists
            # only spatial, budget and evaluation as dependents of furniture.
            self.furniture = ()
            self.color_direction = ""
            self.design_rationale = ""
        elif key is DataKey.MATERIALS:
            self.materials = ()
        elif key is DataKey.SPATIAL:
            self.spatial = None
            self.placement = None
            # The coordinates were the layout's. Keeping them on the basket
            # would leave a stored position that no current validation covers,
            # so they are stripped with the verdict they belong to. Items,
            # quantities and prices are untouched.
            self.furniture = tuple(
                unplace_recommendation(item) for item in self.furniture
            )
        elif key is DataKey.BUDGET_ANALYSIS:
            self.budget_analysis = None
        elif key is DataKey.EVALUATION:
            self.evaluation = None
        else:  # pragma: no cover - guards against a future graph mistake
            raise WorkflowError(
                f"'{key.value}' is user input and cannot be cleared by invalidation."
            )

    # ------------------------------------------------------------------ #
    # Inputs
    # ------------------------------------------------------------------ #

    def set_room(self, room: RoomInput) -> tuple[DataKey, ...]:
        """Store the room and invalidate what the change affects.

        A door moving on the same wall invalidates the layout but not the price.
        Re-submitting an identical room invalidates nothing at all.
        """

        if self.room == room:
            return ()

        previous = self.room
        if previous is None:
            self.room = room
            return ()

        changed = room_change_keys(previous, room)
        if not changed:  # name-only edit; nothing derived depends on the label
            self.room = room
            return ()

        self.room = room
        dropped: set[DataKey] = set()
        for key in changed:
            dropped.update(invalidated_by(key))
        dropped.difference_update(changed)

        ordered = tuple(item for item in DataKey if item in dropped)
        for stale in ordered:
            self._clear(stale)
        if ordered:
            for key in DataKey:
                if key in changed:
                    self.invalidation_log.append((key, ordered))
        return ordered

    def set_preferences(
        self, preferences: DesignPreferences
    ) -> tuple[DataKey, ...]:
        """Store style, palette and material preferences."""

        if self.preferences == preferences:
            return ()
        return self._replace(
            (DataKey.PREFERENCES,),
            lambda: setattr(self, "preferences", preferences),
        )

    def set_requirements(
        self, requirements: UserRequirements
    ) -> tuple[DataKey, ...]:
        """Store functional requirements and notes."""

        if self.requirements == requirements:
            return ()
        return self._replace(
            (DataKey.REQUIREMENTS,),
            lambda: setattr(self, "requirements", requirements),
        )

    def set_budget(self, budget: BudgetInput) -> tuple[DataKey, ...]:
        """Store the budget.

        The budget reaches the brief, the concepts, the advisor and the total,
        but never the room geometry: a spatial check stays valid when only the
        money changes.
        """

        if self.budget == budget:
            return ()
        return self._replace(
            (DataKey.BUDGET,), lambda: setattr(self, "budget", budget)
        )

    # ------------------------------------------------------------------ #
    # Results
    # ------------------------------------------------------------------ #

    def record_brief(self, brief: DesignBrief) -> tuple[DataKey, ...]:
        """Store the analysed brief.

        Raises :class:`PrerequisiteError` when the room or the preferences are
        still missing, so a brief can never describe a project with no inputs.
        """

        self.guard(WorkflowStep.BRIEF_ANALYSIS)
        if self.brief == brief:
            return ()
        return self._replace(
            (DataKey.BRIEF,), lambda: setattr(self, "brief", brief)
        )

    def record_concepts(
        self, concepts: ConceptCollection
    ) -> tuple[DataKey, ...]:
        """Store three generated concepts and clear any previous selection."""

        self.guard(WorkflowStep.CONCEPT_GENERATION)
        if self.concepts == concepts:
            return ()
        return self._replace(
            (DataKey.CONCEPTS,), lambda: setattr(self, "concepts", concepts)
        )

    def select_concept(self, concept: DesignConcept) -> tuple[DataKey, ...]:
        """Record the user's choice, which must come from the current collection.

        Accepting an arbitrary ``DesignConcept`` would let a stale concept from
        a previous generation be selected by name. The collection is the only
        legitimate source, so membership is checked by value.
        """

        self.guard(WorkflowStep.CONCEPT_SELECTION)
        if self.concepts is None:  # pragma: no cover - guard guarantees this
            raise WorkflowError("No concepts have been generated yet.")
        if concept not in self.concepts.concepts:
            names = ", ".join(item.name for item in self.concepts.concepts)
            raise WorkflowError(
                f"'{concept.name}' is not one of the generated concepts ({names})."
            )
        if self.selected_concept == concept:
            return ()
        return self._replace(
            (DataKey.SELECTED_CONCEPT,),
            lambda: setattr(self, "selected_concept", concept),
        )

    def select_concept_by_name(self, name: str) -> tuple[DataKey, ...]:
        """Select by name, case-insensitively, for a radio button's label."""

        self.guard(WorkflowStep.CONCEPT_SELECTION)
        if self.concepts is None:  # pragma: no cover - guard guarantees this
            raise WorkflowError("No concepts have been generated yet.")
        wanted = name.strip().casefold()
        for concept in self.concepts.concepts:
            if concept.name.casefold() == wanted:
                return self.select_concept(concept)
        names = ", ".join(item.name for item in self.concepts.concepts)
        raise WorkflowError(f"No concept is named '{name}' ({names}).")

    def record_recommendation(
        self, recommendation: DesignRecommendation
    ) -> tuple[DataKey, ...]:
        """Store the advisor's answer, invalidating only what actually changed.

        Furniture and materials are separate keys with separate dependents, so a
        materials-only edit keeps a valid layout.

        Two baskets are compared by *what was asked for* — items, quantities,
        rotation hints and rationale — not by the coordinates the placement engine
        wrote onto the stored copy. Otherwise re-running the advisor on an
        unchanged request would look like a new basket, discard the layout and
        recompute a budget that had not changed.
        """

        self.guard(WorkflowStep.RECOMMENDATIONS)
        incoming_furniture = tuple(recommendation.furniture)
        incoming_materials = tuple(recommendation.materials)

        changed: list[DataKey] = []
        if _basket_requests(incoming_furniture) != _basket_requests(self.furniture):
            changed.append(DataKey.FURNITURE)
        if incoming_materials != self.materials:
            changed.append(DataKey.MATERIALS)

        narrative_changed = (
            recommendation.color_direction != self.color_direction
            or recommendation.design_rationale != self.design_rationale
        )

        if not changed and not narrative_changed:
            return ()

        def assign() -> None:
            self.furniture = incoming_furniture
            self.materials = incoming_materials
            self.color_direction = recommendation.color_direction
            self.design_rationale = recommendation.design_rationale

        if not changed:
            # Only the prose moved; nothing downstream is invalidated by wording.
            assign()
            return ()

        return self._replace(tuple(changed), assign)

    def set_materials(
        self, materials: Sequence[MaterialRecommendation]
    ) -> tuple[DataKey, ...]:
        """Replace materials while keeping the furniture and the narrative."""

        self.guard(WorkflowStep.RECOMMENDATIONS)
        if not self.furniture:
            raise WorkflowError(
                "There are no furniture recommendations yet, so materials "
                "cannot be set on their own."
            )
        incoming = tuple(materials)
        if incoming == self.materials:
            return ()
        return self._replace(
            (DataKey.MATERIALS,), lambda: setattr(self, "materials", incoming)
        )

    def record_spatial(
        self,
        spatial: SpatialValidation,
        placement: PlacementOutcome | None = None,
        placements: Sequence[FurnitureRecommendation] | None = None,
    ) -> tuple[DataKey, ...]:
        """Store the deterministic geometry result and the layout it describes.

        ``placement`` is optional so an existing caller that only has a verdict
        keeps working, but the plan screen always passes both: a score or a set
        of footprints without its validation would be a claim the engine never
        made. The two are stored together under ``SPATIAL`` because invalidating
        one without the other would leave a drawable layout that no longer has a
        verdict.

        ``placements`` is the basket with the engine's coordinates written in
        (``core.placement_engine.apply_placements``). Recording it here rather
        than leaving it in the caller is what stops the geometry from being lost:
        the finalised report is assembled from :attr:`furniture`, so a basket
        without coordinates would describe the request but not the room. It is
        written under ``SPATIAL``, not ``FURNITURE``, because the items,
        quantities and prices are unchanged — only the placement annotation is
        added — and invalidating the price for a coordinate would be wrong.
        """

        self.guard(WorkflowStep.SPATIAL_VALIDATION)
        incoming = None if placements is None else tuple(placements)
        unchanged = self.spatial == spatial and self.placement == placement
        if incoming is not None and incoming != self.furniture:
            unchanged = False
        if unchanged:
            return ()

        def assign() -> None:
            self.spatial = spatial
            self.placement = placement
            if incoming is not None:
                self.furniture = incoming

        return self._replace((DataKey.SPATIAL,), assign)

    def record_budget_analysis(
        self, analysis: BudgetAnalysis
    ) -> tuple[DataKey, ...]:
        """Store the deterministic budget result.

        Only a computed ``BudgetAnalysis`` may be stored: this method performs no
        arithmetic, it records what ``core.budget_engine`` produced.
        """

        self.guard(WorkflowStep.BUDGET_ANALYSIS)
        if self.budget_analysis == analysis:
            return ()
        return self._replace(
            (DataKey.BUDGET_ANALYSIS,),
            lambda: setattr(self, "budget_analysis", analysis),
        )

    def record_evaluation(
        self, evaluation: DesignEvaluation
    ) -> tuple[DataKey, ...]:
        """Store the AI evaluation of the chosen concept."""

        self.guard(WorkflowStep.DESIGN_EVALUATION)
        if self.evaluation == evaluation:
            return ()
        return self._replace(
            (DataKey.EVALUATION,), lambda: setattr(self, "evaluation", evaluation)
        )

    # ------------------------------------------------------------------ #
    # Running a step
    # ------------------------------------------------------------------ #

    def attempt(
        self,
        step: WorkflowStep,
        produce: Callable[[], ResultT],
        record: Callable[[ResultT], object],
    ) -> ResultT:
        """Run one step's work and record the result, or leave the state alone.

        This is the bridge between the workflow and the AI layer without either
        importing the other: the caller passes the call that performs the work,
        so no HTTP, prompt or credential handling enters this module.

        If ``produce`` raises — a timeout, a truncated answer, a failed
        correction — the exception is wrapped in :class:`StepFailed` and nothing
        is recorded. There is no code path from a failed call to a stored value,
        so a failure cannot be mistaken for a successful result.
        """

        self.guard(step)
        try:
            value = produce()
        except Exception as exc:  # noqa: BLE001 - re-raised with its cause
            raise StepFailed(step, exc) from exc
        record(value)
        return value

    # ------------------------------------------------------------------ #
    # Views and final result
    # ------------------------------------------------------------------ #

    def as_recommendation(self) -> DesignRecommendation | None:
        """The advisor's answer rebuilt from the stored pieces."""

        if not self.furniture:
            return None
        return DesignRecommendation(
            furniture=list(self.furniture),
            materials=list(self.materials),
            color_direction=self.color_direction,
            design_rationale=self.design_rationale,
        )

    def _can_build_result(self) -> bool:
        """True when every step except the finalisation itself has data."""

        return all(
            self.is_complete(step)
            for step in STEP_ORDER
            if step is not WorkflowStep.FINAL_RESULT
        )

    def outstanding_steps(self) -> tuple[WorkflowStep, ...]:
        """Steps that are not complete, in workflow order."""

        return tuple(step for step in STEP_ORDER if not self.is_complete(step))

    def finalize(self) -> ProjectResult:
        """Assemble and store the final result, completing the workflow.

        Separate from :meth:`build_result` so that "the data is all there" and
        "the project has been finalised" are different facts. A user may look at
        the evaluation without producing a report, and a later edit must not
        leave a stale report claiming to describe the new project.
        """

        self.guard(WorkflowStep.FINAL_RESULT)
        result = self.build_result()
        self.result = result
        return result

    def build_result(self) -> ProjectResult:
        """Assemble the consolidated result the reporting layer consumes.

        Raises :class:`IncompleteWorkflowError` rather than returning a partial
        object: a report missing its evaluation is not a project result, and
        letting one through would put placeholder text in a PDF.

        Does not store anything; use :meth:`finalize` to complete the workflow.
        """

        outstanding = tuple(
            step
            for step in STEP_ORDER
            if step is not WorkflowStep.FINAL_RESULT and not self.is_complete(step)
        )
        if outstanding:
            raise IncompleteWorkflowError(outstanding)

        room = self.room
        preferences = self.preferences
        requirements = self.requirements
        budget = self.budget
        brief = self.brief
        concepts = self.concepts
        selected = self.selected_concept
        spatial = self.spatial
        analysis = self.budget_analysis
        evaluation = self.evaluation

        if any(
            value is None
            for value in (
                room,
                preferences,
                requirements,
                budget,
                brief,
                concepts,
                selected,
                spatial,
                analysis,
                evaluation,
            )
        ):  # pragma: no cover - unreachable while outstanding_steps is empty
            raise IncompleteWorkflowError(outstanding)

        return ProjectResult(
            room=room,
            preferences=preferences,
            requirements=requirements,
            budget=budget,
            brief=brief,
            concepts=concepts,
            selected_concept=selected,
            recommendations=list(self.furniture),
            spatial_validation=spatial,
            budget_analysis=analysis,
            evaluation=evaluation,
            # The advisor's non-furniture half and the layout, both of which were
            # previously reachable only through ``WorkflowState``. Copying them
            # here is what lets the reporting layer work from the result alone.
            materials=list(self.materials),
            color_direction=self.color_direction,
            design_rationale=self.design_rationale,
            placement=self.placement,
        )


__all__ = [
    "STEP_LABELS",
    "STEP_ORDER",
    "STEP_PREREQUISITES",
    "IncompleteWorkflowError",
    "PrerequisiteError",
    "StepFailed",
    "WorkflowError",
    "WorkflowState",
    "WorkflowStep",
    "room_change_keys",
    "unplace_recommendation",
]
