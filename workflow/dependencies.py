"""The single definition of what becomes stale when something changes.

Every rule of the form "when this changes, that can no longer be trusted" lives
here and nowhere else. A second copy in a Streamlit page would eventually
disagree with this one, and the disagreement would surface as a concept priced
against furniture the user has already replaced.

The table is **exact, not transitive**
--------------------------------------
``INVALIDATES[key]`` lists precisely what is discarded when ``key`` changes. It
is deliberately not expanded to its transitive closure, for two reasons:

1. *Geometry does not depend on money.* Editing the budget must not throw away a
   measured, still-correct layout. A closure walk (budget → concepts → selection
   → spatial) would delete it for no reason, which the step brief explicitly
   forbids: only the affected results may be cleared, and independent valid
   results must survive.
2. *The chain re-forms by itself.* A result that is left in place but whose
   prerequisite is now missing is not a stale value presented as current: the
   workflow's ``is_complete`` is derived from data plus prerequisites, so such a
   result is unusable until the missing step runs again. And when that step does
   run, its own edge fires and clears the leftover at exactly the right moment.

So ``room`` is a user input and is never invalidated; ``spatial`` survives a
budget edit; ``materials`` survive a furniture change. Each of those is
deliberate, and each is covered by a test.

Table source: the dependency rules in the Phase 5 / Step 1 brief, transcribed
one row per key.
"""

from __future__ import annotations

from enum import Enum
from typing import Mapping

# --------------------------------------------------------------------------- #
# Keys
# --------------------------------------------------------------------------- #


class DataKey(str, Enum):
    """Every value whose freshness the workflow tracks.

    The first six are user input; the rest are captured results.
    """

    # --- User input ------------------------------------------------------- #
    ROOM_TYPE = "room_type"
    ROOM_DIMENSIONS = "room_dimensions"
    ROOM_OPENINGS = "room_openings"
    PREFERENCES = "preferences"
    REQUIREMENTS = "requirements"
    BUDGET = "budget"

    # --- Results ---------------------------------------------------------- #
    BRIEF = "brief"
    CONCEPTS = "concepts"
    SELECTED_CONCEPT = "selected_concept"
    FURNITURE = "furniture"
    MATERIALS = "materials"
    SPATIAL = "spatial"
    BUDGET_ANALYSIS = "budget_analysis"
    EVALUATION = "evaluation"


#: Fixed order used whenever keys are reported, so output never depends on
#: dictionary or set iteration order.
DATA_KEY_ORDER: tuple[DataKey, ...] = tuple(DataKey)

#: User input. These are replaced by the user, never cleared by invalidation.
INPUT_KEYS: frozenset[DataKey] = frozenset(
    {
        DataKey.ROOM_TYPE,
        DataKey.ROOM_DIMENSIONS,
        DataKey.ROOM_OPENINGS,
        DataKey.PREFERENCES,
        DataKey.REQUIREMENTS,
        DataKey.BUDGET,
    }
)


def _keys(*names: str) -> frozenset[DataKey]:
    """Readable construction of a key set from the table below."""

    return frozenset(DataKey[name] for name in names)


#: What each change discards. One row per key, transcribed from the step brief.
#:
#: Reading a row: "if this changes, these are no longer valid". A key never
#: lists itself; replacing a value refreshes it rather than invalidating it.
INVALIDATES: Mapping[DataKey, frozenset[DataKey]] = {
    # --- Room facts ------------------------------------------------------- #
    # Any room change reaches every AI answer, because every prompt carries the
    # room. A dimension or type change also reaches the price; an opening does
    # not, because a door width does not change what a sofa costs.
    DataKey.ROOM_DIMENSIONS: _keys(
        "BRIEF",
        "CONCEPTS",
        "SELECTED_CONCEPT",
        "FURNITURE",
        "MATERIALS",
        "SPATIAL",
        "BUDGET_ANALYSIS",
        "EVALUATION",
    ),
    DataKey.ROOM_TYPE: _keys(
        "BRIEF",
        "CONCEPTS",
        "SELECTED_CONCEPT",
        "FURNITURE",
        "MATERIALS",
        "SPATIAL",
        "BUDGET_ANALYSIS",
        "EVALUATION",
    ),
    DataKey.ROOM_OPENINGS: _keys(
        "BRIEF",
        "CONCEPTS",
        "SELECTED_CONCEPT",
        "FURNITURE",
        "MATERIALS",
        "SPATIAL",
        "EVALUATION",
    ),
    # --- Preferences and requirements ------------------------------------- #
    # These shape every AI answer. They do not touch measured geometry or a
    # computed total directly: those follow when the furniture is replaced.
    DataKey.PREFERENCES: _keys(
        "BRIEF",
        "CONCEPTS",
        "SELECTED_CONCEPT",
        "FURNITURE",
        "MATERIALS",
        "EVALUATION",
    ),
    DataKey.REQUIREMENTS: _keys(
        "BRIEF",
        "CONCEPTS",
        "SELECTED_CONCEPT",
        "FURNITURE",
        "MATERIALS",
        "EVALUATION",
    ),
    # --- Budget ----------------------------------------------------------- #
    # Money reaches the brief, the concepts, the advice and the total. It does
    # not reach the selection or the layout: a cheaper basket is still the same
    # room with the same furniture already measured.
    DataKey.BUDGET: _keys(
        "BRIEF",
        "CONCEPTS",
        "FURNITURE",
        "MATERIALS",
        "BUDGET_ANALYSIS",
        "EVALUATION",
    ),
    # --- Results ---------------------------------------------------------- #
    DataKey.BRIEF: _keys(
        "CONCEPTS",
        "SELECTED_CONCEPT",
        "FURNITURE",
        "MATERIALS",
        "EVALUATION",
    ),
    DataKey.CONCEPTS: _keys(
        "SELECTED_CONCEPT",
        "FURNITURE",
        "MATERIALS",
        "EVALUATION",
    ),
    DataKey.SELECTED_CONCEPT: _keys(
        "FURNITURE",
        "MATERIALS",
        "SPATIAL",
        "BUDGET_ANALYSIS",
        "EVALUATION",
    ),
    # A different basket invalidates its layout and its price. It says nothing
    # about the material palette, which is why materials are a separate key.
    DataKey.FURNITURE: _keys(
        "SPATIAL",
        "BUDGET_ANALYSIS",
        "EVALUATION",
    ),
    # Materials carry no geometry in V1, so a material change leaves the spatial
    # result valid. They can move the total, because the budget engine accepts a
    # material subtotal.
    DataKey.MATERIALS: _keys(
        "BUDGET_ANALYSIS",
        "EVALUATION",
    ),
    # The two deterministic results are recomputed independently, and each feeds
    # the evaluation that interpreted it.
    DataKey.SPATIAL: _keys("EVALUATION"),
    DataKey.BUDGET_ANALYSIS: _keys("EVALUATION"),
    # The evaluation is terminal: the report is built from it, not derived
    # through a key.
    DataKey.EVALUATION: frozenset(),
}

#: Inverse of :data:`INVALIDATES`, built from it so the two cannot disagree.
#: Answers "what change would explain this being stale?".
SOURCES: Mapping[DataKey, frozenset[DataKey]] = {
    key: frozenset(
        source for source, targets in INVALIDATES.items() if key in targets
    )
    for key in DataKey
}


def _ordered(keys: set[DataKey]) -> tuple[DataKey, ...]:
    """Sort keys into the declared order for stable reporting."""

    return tuple(key for key in DATA_KEY_ORDER if key in keys)


def invalidated_by(*changed: DataKey) -> tuple[DataKey, ...]:
    """Everything discarded when ``changed`` no longer applies.

    A union of the table's rows, not a closure walk — see the module docstring.
    A changed key never appears in its own result: it is being replaced.

    An unknown key raises ``KeyError`` at the point of use rather than silently
    invalidating nothing, because a missing row is a correctness bug that would
    otherwise hide behind a plausible-looking result.
    """

    dropped: set[DataKey] = set()
    for key in changed:
        dropped.update(INVALIDATES[key])
    dropped.difference_update(changed)
    return _ordered(dropped)


def depends_on(key: DataKey) -> tuple[DataKey, ...]:
    """Inputs and results whose change would invalidate ``key``.

    Used to explain a reset in the interface ("this layout was cleared because
    the selection changed") and to assert the table's shape in tests.
    """

    return _ordered(set(SOURCES[key]))


__all__ = [
    "DATA_KEY_ORDER",
    "INPUT_KEYS",
    "INVALIDATES",
    "SOURCES",
    "DataKey",
    "depends_on",
    "invalidated_by",
]
