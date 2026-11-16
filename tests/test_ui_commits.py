"""Tests for the pure widget-to-model conversions in :mod:`ui.commits`.

These functions are the seam between the Streamlit widgets and the validated
models, so they are exactly where a wrong value could enter the project. They
are tested directly — no Streamlit runtime, no AppTest — because nothing in this
module should need one.

Three properties are protected here:

**Two gates.** Pydantic rejects shape violations; ``core.validation`` adds the
cross-field checks. A value must pass both before a page can store it. In
particular, geometry is never re-implemented in the interface: a door that does
not fit its wall is caught by the model that already owns that rule.

**No silent repair.** A budget with three decimals is rejected, not rounded, and
a duplicate requirement is de-duplicated but never rewritten into something the
user did not type.

**No traceback in a message.** A blocking issue is a sentence. Nothing returned
from this module may contain a Pydantic type name or a stack trace.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from core.validation import validate_room_input
from models.schemas import (
    DesignStyle,
    PaletteDirection,
    RoomType,
    Wall,
)
from ui.commits import (
    Outcome,
    build_budget,
    build_preferences,
    build_requirements,
    build_room,
    clean_entries,
    format_money,
    issues_from_validation_error,
    overall_warnings,
    room_summary_rows,
)

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

#: A room that passes both gates, used as the base for one-change-at-a-time
#: assertions so a failure is attributable to the change under test.
VALID_ROOM = {
    "room_type": RoomType.LIVING_ROOM,
    "name": "Living Room",
    "width_cm": 400.0,
    "length_cm": 520.0,
    "ceiling_height_cm": 270.0,
    "door_wall": Wall.SOUTH,
    "door_offset_cm": 60.0,
    "door_width_cm": 90.0,
    "window_wall": Wall.NORTH,
    "window_offset_cm": 120.0,
    "window_width_cm": 160.0,
}


def room_outcome(**overrides: object) -> Outcome:
    """Build a room outcome from the valid baseline plus overrides."""

    payload = {**VALID_ROOM, **overrides}
    return build_room(**payload)  # type: ignore[arg-type]


def messages(outcome: Outcome) -> str:
    return " | ".join(issue.message for issue in outcome.issues)


# --------------------------------------------------------------------------- #
# The outcome type
# --------------------------------------------------------------------------- #


def test_outcome_with_a_value_and_no_issues_is_ok() -> None:
    outcome = build_budget(1000)
    assert outcome.is_ok
    assert outcome.value is not None
    assert outcome.issues == ()


def test_outcome_with_issues_is_never_ok_even_if_a_value_exists() -> None:
    value = build_budget(1000).value
    assert value is not None
    # ``is_ok`` requires both halves; a value alone is not permission to commit.
    assert Outcome(value=value, issues=(object(),)).is_ok is False


# --------------------------------------------------------------------------- #
# Room: the happy path
# --------------------------------------------------------------------------- #


def test_valid_room_is_accepted_and_keeps_the_typed_numbers() -> None:
    outcome = room_outcome()
    assert outcome.issues == ()
    assert outcome.value is not None
    assert outcome.value.width_cm == 400.0
    assert outcome.value.length_cm == 520.0
    assert outcome.value.door.wall is Wall.SOUTH


def test_room_name_is_trimmed_before_it_is_stored() -> None:
    outcome = room_outcome(name="  Lounge  ")
    assert outcome.value is not None
    assert outcome.value.name == "Lounge"


def test_room_outcome_reports_no_warning_for_an_ordinary_room() -> None:
    outcome = room_outcome()
    assert outcome.warnings == ()


def test_small_room_is_accepted_and_flagged_as_a_warning_downstream() -> None:
    """A small room is legal, so the room commit must not block it.

    The advisory itself belongs to ``validate_inputs``, which describes the
    combination of all four inputs; the room gate only reports blocking
    problems. This test pins that division rather than the wording.
    """

    # 250 x 200 cm is 5.0 m², below the 6 m² advisory threshold but valid.
    outcome = room_outcome(width_cm=250.0, length_cm=200.0, window_width_cm=100.0)
    assert outcome.issues == ()
    assert outcome.value is not None

    room = outcome.value
    preferences = build_preferences(
        style=DesignStyle.JAPANDI,
        palette=PaletteDirection.WARM_NEUTRAL,
        material_preferences=["oak"],
    ).value
    requirements = build_requirements(
        functional_requirements=["Seating for two"], notes=""
    ).value
    budget = build_budget(45000).value

    warnings = overall_warnings(room, preferences, requirements, budget)
    assert any("m²" in warning for warning in warnings)
    assert not any("m²" in warning for warning in outcome.warnings)


# --------------------------------------------------------------------------- #
# Room: rejected input
# --------------------------------------------------------------------------- #


def test_blank_room_name_is_rejected_before_pydantic() -> None:
    outcome = room_outcome(name="   ")
    assert outcome.value is None
    assert len(outcome.issues) == 1
    assert "name" in outcome.issues[0].message.lower()
    assert "traceback" not in messages(outcome).lower()


def test_room_name_whitespace_only_is_rejected_not_stored_as_a_space() -> None:
    outcome = room_outcome(name="\t\n ")
    assert outcome.value is None
    assert outcome.issues


def test_dimension_below_the_approved_minimum_is_rejected() -> None:
    outcome = room_outcome(width_cm=50.0)
    assert outcome.value is None
    assert "width" in messages(outcome).lower()


def test_dimension_above_the_approved_maximum_is_rejected() -> None:
    outcome = room_outcome(length_cm=5000.0)
    assert outcome.value is None
    assert "length" in messages(outcome).lower()


def test_door_that_overflows_its_wall_is_rejected_by_the_model() -> None:
    # 450 + 90 = 540 cm on a 400 cm wall.
    outcome = room_outcome(door_offset_cm=450.0)
    assert outcome.value is None
    assert "door" in messages(outcome).lower()
    assert "400" in messages(outcome)


def test_door_overflow_message_does_not_start_with_a_bare_colon() -> None:
    # A model-level validator reports an empty location; attributing that to a
    # nameless field once produced ": The door does not fit...".
    outcome = room_outcome(door_offset_cm=450.0)
    assert not messages(outcome).startswith(":")


def test_window_that_overflows_its_wall_is_rejected_by_the_model() -> None:
    outcome = room_outcome(window_offset_cm=300.0)
    assert outcome.value is None
    assert "window" in messages(outcome).lower()


def test_door_and_window_overlapping_on_one_wall_are_rejected() -> None:
    outcome = room_outcome(
        window_wall=Wall.SOUTH,
        window_offset_cm=100.0,
        window_width_cm=90.0,
    )
    assert outcome.value is None
    assert "overlap" in messages(outcome).lower()


def test_touching_openings_on_one_wall_are_allowed() -> None:
    # Door occupies 60..150 cm, so a window starting at 150 exactly touches it.
    outcome = room_outcome(
        window_wall=Wall.SOUTH,
        window_offset_cm=150.0,
        window_width_cm=90.0,
    )
    assert outcome.issues == ()
    assert outcome.value is not None


def test_every_blocking_issue_is_reported_not_just_the_first() -> None:
    outcome = room_outcome(width_cm=50.0, length_cm=9000.0)
    assert outcome.value is None
    assert len(outcome.issues) >= 2


# --------------------------------------------------------------------------- #
# Room: the UI does not re-implement geometry
# --------------------------------------------------------------------------- #


def test_rejection_matches_core_validation_when_the_model_accepts() -> None:
    """The commit path must agree with the engine that owns the rules.

    Geometry is checked twice by design — the model enforces fit, the engine
    enforces the cross-field rules — and this test pins that the two do not
    disagree about a room either of them rejects.
    """

    outcome = room_outcome(
        window_wall=Wall.SOUTH,
        window_offset_cm=60.0,
        window_width_cm=90.0,
    )
    assert outcome.value is None
    # The engine would say the same thing if it were given this room.
    from models.schemas import OpeningInput, RoomInput

    room = RoomInput(
        room_type=RoomType.LIVING_ROOM,
        name="Overlap",
        width_cm=400.0,
        length_cm=520.0,
        door=OpeningInput(wall=Wall.SOUTH, offset_cm=60.0, width_cm=90.0),
        window=OpeningInput(wall=Wall.SOUTH, offset_cm=60.0, width_cm=90.0),
    )
    engine_codes = {finding.code for finding in validate_room_input(room)}
    assert "opening_conflict" in engine_codes


def test_room_summary_rows_use_the_model_area_and_add_no_arithmetic() -> None:
    room = room_outcome().value
    assert room is not None
    rows = dict(room_summary_rows(room))
    assert rows["Width × length"] == "400 × 520 cm"
    assert rows["Floor area"] == f"{room.area_sqm:.2f} m²"
    assert rows["Floor area"] == "20.80 m²"
    assert rows["Door"].startswith("south wall")


# --------------------------------------------------------------------------- #
# Budget
# --------------------------------------------------------------------------- #


def test_budget_is_stored_as_a_decimal() -> None:
    outcome = build_budget(45000.0)
    assert outcome.value is not None
    assert isinstance(outcome.value.total_budget, Decimal)
    assert outcome.value.total_budget == Decimal("45000.0")


def test_budget_keeps_the_typed_value_instead_of_a_binary_approximation() -> None:
    outcome = build_budget(0.1)
    assert outcome.value is not None
    assert outcome.value.total_budget == Decimal("0.1")


def test_budget_with_more_than_two_decimals_is_rejected_not_rounded() -> None:
    outcome = build_budget(10.005)
    assert outcome.value is None
    assert "two decimal places" in messages(outcome).lower()
    assert "10.00" not in messages(outcome)


def test_negative_budget_is_rejected() -> None:
    outcome = build_budget(-5)
    assert outcome.value is None
    assert "minimum" in messages(outcome).lower()


def test_zero_budget_is_accepted_because_it_is_a_defined_amount() -> None:
    # The engine, not the widget, decides whether zero is workable. There is no
    # lower bound in the approved model, so the commit must not invent one.
    outcome = build_budget(0)
    assert outcome.issues == ()
    assert outcome.value is not None
    assert outcome.value.total_budget == Decimal("0")


def test_unparseable_budget_is_rejected_without_a_traceback() -> None:
    outcome = build_budget("not money")
    assert outcome.value is None
    assert "valid amount" in messages(outcome).lower()


def test_budget_currency_defaults_to_the_only_supported_value() -> None:
    outcome = build_budget(1000)
    assert outcome.value is not None
    assert outcome.value.currency == "TRY"


# --------------------------------------------------------------------------- #
# Preferences and requirements
# --------------------------------------------------------------------------- #


def test_preferences_accept_the_stored_enums_and_any_materials() -> None:
    outcome = build_preferences(
        style=DesignStyle.JAPANDI,
        palette=PaletteDirection.WARM_NEUTRAL,
        material_preferences=["pale oak", "linen"],
    )
    assert outcome.issues == ()
    assert outcome.value is not None
    assert outcome.value.style is DesignStyle.JAPANDI
    assert outcome.value.palette is PaletteDirection.WARM_NEUTRAL


def test_material_preferences_are_optional() -> None:
    outcome = build_preferences(
        style=DesignStyle.INDUSTRIAL,
        palette=PaletteDirection.COOL_MODERN,
        material_preferences=[],
    )
    assert outcome.issues == ()
    assert outcome.value is not None
    assert outcome.value.material_preferences == []


def test_requirements_keep_order_while_removing_blanks_and_duplicates() -> None:
    outcome = build_requirements(
        functional_requirements=["Seating for four", "  ", "seating FOR four", " Reading corner "],
        notes="",
    )
    assert outcome.value is not None
    # Case-insensitive duplicate removed, original capitalisation of the first
    # entry preserved, blank dropped, order kept.
    assert outcome.value.functional_requirements == [
        "Seating for four",
        "Reading corner",
    ]


def test_notes_are_trimmed() -> None:
    outcome = build_requirements(functional_requirements=[], notes="  Keep it open.  ")
    assert outcome.value is not None
    assert outcome.value.notes == "Keep it open."


def test_notes_longer_than_the_approved_limit_are_rejected() -> None:
    outcome = build_requirements(functional_requirements=[], notes="x" * 2001)
    assert outcome.value is None
    assert outcome.issues
    assert "notes" in messages(outcome).lower()


def test_clean_entries_respects_the_limit_rather_than_growing_the_prompt() -> None:
    entries = [f"item {index}" for index in range(30)]
    assert len(clean_entries(entries, limit=5)) == 5
    assert clean_entries(entries, limit=5)[0] == "item 0"


def test_clean_entries_leaves_ordinary_text_alone() -> None:
    # No stemming, no case folding of the value itself: only trim/blank/dedupe.
    assert clean_entries(["Brushed Brass"], limit=10) == ["Brushed Brass"]


# --------------------------------------------------------------------------- #
# Combined warnings
# --------------------------------------------------------------------------- #


def test_overall_warnings_are_silent_until_all_four_inputs_exist() -> None:
    room = room_outcome().value
    preferences = build_preferences(
        style=DesignStyle.JAPANDI,
        palette=PaletteDirection.WARM_NEUTRAL,
        material_preferences=[],
    ).value
    assert overall_warnings(room, preferences, None, None) == ()
    assert overall_warnings(None, None, None, None) == ()


def test_overall_warnings_report_a_thin_brief_once_everything_is_present() -> None:
    room = room_outcome().value
    preferences = build_preferences(
        style=DesignStyle.JAPANDI,
        palette=PaletteDirection.WARM_NEUTRAL,
        material_preferences=[],
    ).value
    requirements = build_requirements(
        functional_requirements=[], notes=""
    ).value
    budget = build_budget(45000).value
    warnings = overall_warnings(room, preferences, requirements, budget)
    assert any("material preferences" in warning.lower() for warning in warnings)


def test_overall_warnings_disappear_when_the_brief_has_content() -> None:
    room = room_outcome().value
    preferences = build_preferences(
        style=DesignStyle.JAPANDI,
        palette=PaletteDirection.WARM_NEUTRAL,
        material_preferences=["oak"],
    ).value
    requirements = build_requirements(
        functional_requirements=["Seating for four"], notes=""
    ).value
    budget = build_budget(45000).value
    assert overall_warnings(room, preferences, requirements, budget) == ()


# --------------------------------------------------------------------------- #
# Message rendering
# --------------------------------------------------------------------------- #


def test_format_money_groups_thousands_in_the_turkish_convention() -> None:
    assert format_money(Decimal("45000.00")) == "45.000,00 TRY"
    assert format_money(Decimal("1250.5")) == "1.250,50 TRY"
    assert format_money(Decimal("0")) == "0,00 TRY"


def test_format_money_accepts_an_explicit_currency() -> None:
    assert format_money(Decimal("100"), "EUR") == "100,00 EUR"


def test_issues_from_validation_error_maps_a_known_type_to_a_sentence() -> None:
    from pydantic import ValidationError

    from models.schemas import BudgetInput

    try:
        BudgetInput(total_budget=Decimal("1.234"))
    except ValidationError as error:
        issues = issues_from_validation_error(error)
    else:  # pragma: no cover - the model rejects this
        pytest.fail("The budget model accepted three decimal places.")

    assert len(issues) == 1
    assert "two decimal places" in issues[0].message.lower()
    # The label is the field's human name, not Pydantic's path.
    assert issues[0].field == "Total budget"


def test_model_level_errors_are_attributed_to_the_fallback_label() -> None:
    from pydantic import ValidationError

    from models.schemas import OpeningInput, RoomInput

    try:
        RoomInput(
            room_type=RoomType.LIVING_ROOM,
            name="Overflow",
            width_cm=400,
            length_cm=520,
            door=OpeningInput(wall=Wall.SOUTH, offset_cm=350, width_cm=90),
            window=OpeningInput(wall=Wall.NORTH, offset_cm=100, width_cm=100),
        )
    except ValidationError as error:
        issues = issues_from_validation_error(error, fallback_label="Room")
    else:  # pragma: no cover - the model rejects this
        pytest.fail("The room model accepted a door that overflows the wall.")

    assert issues[0].field == "Room"
    assert issues[0].message.startswith("Room: ")


def test_no_message_ever_contains_a_traceback_or_a_type_name() -> None:
    outcomes = [
        room_outcome(name=""),
        room_outcome(width_cm=10.0),
        room_outcome(door_offset_cm=900.0),
        build_budget("nonsense"),
        build_budget(1.234),
        build_requirements(functional_requirements=[], notes="x" * 3000),
    ]
    for outcome in outcomes:
        assert outcome.value is None
        for issue in outcome.issues:
            lowered = issue.message.lower()
            assert "traceback" not in lowered
            assert "validationerror" not in lowered
            assert "pydantic" not in lowered
            assert issue.message.strip()
