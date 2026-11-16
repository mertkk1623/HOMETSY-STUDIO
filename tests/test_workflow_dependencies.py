"""Tests for workflow dependency rules.

The table in ``workflow/dependencies.py`` is the specification. These tests
assert its shape and its exact contents, because a silently missing edge means a
result that looks current but was derived from an input the user has changed.
"""

from __future__ import annotations

import pytest

from workflow.dependencies import (
    DATA_KEY_ORDER,
    INVALIDATES,
    INPUT_KEYS,
    SOURCES,
    DataKey,
    depends_on,
    invalidated_by,
)

RESULTS = tuple(key for key in DataKey if key not in INPUT_KEYS)


# --------------------------------------------------------------------------- #
# Structural invariants
# --------------------------------------------------------------------------- #


def test_every_key_has_a_row() -> None:
    assert set(INVALIDATES) == set(DataKey)


def test_every_key_appears_exactly_once_in_the_ordering() -> None:
    assert len(DATA_KEY_ORDER) == len(DataKey)
    assert set(DATA_KEY_ORDER) == set(DataKey)


def test_no_key_invalidates_itself() -> None:
    # A key is replaced, not invalidated; listing itself would make every write
    # clear the value it just stored.
    for key, targets in INVALIDATES.items():
        assert key not in targets, key


def test_inputs_are_never_invalidated_by_anything() -> None:
    # User input only leaves the state when the user replaces it.
    for source, targets in INVALIDATES.items():
        overlap = set(targets) & INPUT_KEYS
        assert not overlap, f"{source} invalidates input {overlap}"


def test_the_evaluation_is_terminal() -> None:
    assert INVALIDATES[DataKey.EVALUATION] == frozenset()


def test_no_self_referential_cycle_exists() -> None:
    # A cycle would make invalidation non-terminating if it were ever walked.
    # The table is applied one hop at a time, but a cycle would still mean two
    # results that each claim to be derived from the other.
    def reachable(start: DataKey) -> set[DataKey]:
        seen: set[DataKey] = set()
        stack = [start]
        while stack:
            for target in INVALIDATES[stack.pop()]:
                if target not in seen:
                    seen.add(target)
                    stack.append(target)
        return seen

    for key in DataKey:
        assert key not in reachable(key), f"cycle through {key}"


def test_sources_is_the_exact_inverse() -> None:
    for source, targets in INVALIDATES.items():
        for target in targets:
            assert source in SOURCES[target]
    for target, sources in SOURCES.items():
        for source in sources:
            assert target in INVALIDATES[source]


def test_depends_on_matches_the_inverse_table() -> None:
    for key in DataKey:
        assert depends_on(key) == tuple(
            item for item in DATA_KEY_ORDER if item in SOURCES[key]
        )


# --------------------------------------------------------------------------- #
# Exact rows, transcribed from the step brief
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        (
            DataKey.ROOM_DIMENSIONS,
            {
                DataKey.BRIEF,
                DataKey.CONCEPTS,
                DataKey.SELECTED_CONCEPT,
                DataKey.FURNITURE,
                DataKey.MATERIALS,
                DataKey.SPATIAL,
                DataKey.BUDGET_ANALYSIS,
                DataKey.EVALUATION,
            },
        ),
        (
            DataKey.ROOM_TYPE,
            {
                DataKey.BRIEF,
                DataKey.CONCEPTS,
                DataKey.SELECTED_CONCEPT,
                DataKey.FURNITURE,
                DataKey.MATERIALS,
                DataKey.SPATIAL,
                DataKey.BUDGET_ANALYSIS,
                DataKey.EVALUATION,
            },
        ),
        (
            DataKey.ROOM_OPENINGS,
            {
                DataKey.BRIEF,
                DataKey.CONCEPTS,
                DataKey.SELECTED_CONCEPT,
                DataKey.FURNITURE,
                DataKey.MATERIALS,
                DataKey.SPATIAL,
                DataKey.EVALUATION,
            },
        ),
        (
            DataKey.PREFERENCES,
            {
                DataKey.BRIEF,
                DataKey.CONCEPTS,
                DataKey.SELECTED_CONCEPT,
                DataKey.FURNITURE,
                DataKey.MATERIALS,
                DataKey.EVALUATION,
            },
        ),
        (
            DataKey.REQUIREMENTS,
            {
                DataKey.BRIEF,
                DataKey.CONCEPTS,
                DataKey.SELECTED_CONCEPT,
                DataKey.FURNITURE,
                DataKey.MATERIALS,
                DataKey.EVALUATION,
            },
        ),
        (
            DataKey.BUDGET,
            {
                DataKey.BRIEF,
                DataKey.CONCEPTS,
                DataKey.FURNITURE,
                DataKey.MATERIALS,
                DataKey.BUDGET_ANALYSIS,
                DataKey.EVALUATION,
            },
        ),
        (
            DataKey.BRIEF,
            {
                DataKey.CONCEPTS,
                DataKey.SELECTED_CONCEPT,
                DataKey.FURNITURE,
                DataKey.MATERIALS,
                DataKey.EVALUATION,
            },
        ),
        (
            DataKey.CONCEPTS,
            {
                DataKey.SELECTED_CONCEPT,
                DataKey.FURNITURE,
                DataKey.MATERIALS,
                DataKey.EVALUATION,
            },
        ),
        (
            DataKey.SELECTED_CONCEPT,
            {
                DataKey.FURNITURE,
                DataKey.MATERIALS,
                DataKey.SPATIAL,
                DataKey.BUDGET_ANALYSIS,
                DataKey.EVALUATION,
            },
        ),
        (
            DataKey.FURNITURE,
            {DataKey.SPATIAL, DataKey.BUDGET_ANALYSIS, DataKey.EVALUATION},
        ),
        (DataKey.MATERIALS, {DataKey.BUDGET_ANALYSIS, DataKey.EVALUATION}),
        (DataKey.SPATIAL, {DataKey.EVALUATION}),
        (DataKey.BUDGET_ANALYSIS, {DataKey.EVALUATION}),
        (DataKey.EVALUATION, set()),
    ],
)
def test_row_matches_the_approved_rule(key: DataKey, expected: set[DataKey]) -> None:
    assert INVALIDATES[key] == frozenset(expected)


# --------------------------------------------------------------------------- #
# Independence, stated explicitly
# --------------------------------------------------------------------------- #


def test_openings_do_not_invalidate_the_budget() -> None:
    # Moving a door does not change what a sofa costs.
    assert DataKey.BUDGET_ANALYSIS not in INVALIDATES[DataKey.ROOM_OPENINGS]


def test_budget_does_not_invalidate_the_layout() -> None:
    # The measured layout is still correct when only the money changes. This is
    # the case a transitive closure would get wrong.
    assert DataKey.SPATIAL not in INVALIDATES[DataKey.BUDGET]
    assert DataKey.SELECTED_CONCEPT not in INVALIDATES[DataKey.BUDGET]


def test_preferences_do_not_invalidate_the_layout() -> None:
    assert DataKey.SPATIAL not in INVALIDATES[DataKey.PREFERENCES]
    assert DataKey.BUDGET_ANALYSIS not in INVALIDATES[DataKey.PREFERENCES]


def test_materials_do_not_invalidate_the_layout() -> None:
    # Materials carry no geometry in V1.
    assert DataKey.SPATIAL not in INVALIDATES[DataKey.MATERIALS]


def test_furniture_does_not_invalidate_the_materials() -> None:
    # They arrive together but decay separately.
    assert DataKey.MATERIALS not in INVALIDATES[DataKey.FURNITURE]


def test_requirements_do_not_invalidate_the_budget_analysis() -> None:
    assert DataKey.BUDGET_ANALYSIS not in INVALIDATES[DataKey.REQUIREMENTS]


# --------------------------------------------------------------------------- #
# invalidated_by
# --------------------------------------------------------------------------- #


def test_invalidated_by_is_the_union_of_the_rows() -> None:
    combined = invalidated_by(DataKey.PREFERENCES, DataKey.BUDGET)
    assert set(combined) == (
        INVALIDATES[DataKey.PREFERENCES] | INVALIDATES[DataKey.BUDGET]
    )


def test_invalidated_by_never_reports_a_changed_key() -> None:
    result = invalidated_by(DataKey.FURNITURE)
    assert DataKey.FURNITURE not in result


def test_invalidated_by_returns_declared_order() -> None:
    result = invalidated_by(DataKey.ROOM_TYPE)
    assert result == tuple(item for item in DATA_KEY_ORDER if item in set(result))


def test_invalidated_by_with_no_arguments_is_empty() -> None:
    assert invalidated_by() == ()


def test_invalidated_by_is_not_transitive() -> None:
    # Documented behaviour, asserted so it cannot change by accident.
    one_hop = invalidated_by(DataKey.BUDGET)
    assert DataKey.SPATIAL not in one_hop
    assert DataKey.SELECTED_CONCEPT not in one_hop


def test_unknown_key_fails_loudly_instead_of_invalidating_nothing() -> None:
    with pytest.raises(KeyError):
        invalidated_by("not_a_key")  # type: ignore[arg-type]


def test_result_keys_are_all_covered_by_a_source() -> None:
    # Every result must be reachable from some change, or it could never be
    # cleared and would outlive its inputs forever.
    for key in RESULTS:
        assert SOURCES[key], f"{key} has no source and can never be invalidated"
