"""Tests for the Streamlit session adapter in :mod:`ui.session`.

The adapter is the only place where session state and the workflow object meet,
so this file protects the two failure modes that would silently destroy a user's
project:

**A new state per rerun.** If ``get_workflow`` ever returned a fresh
``WorkflowState``, every Streamlit interaction would wipe the project while the
widgets kept showing the old values. The object identity across reruns is
therefore asserted directly.

**A duplicated key.** Invalidation is owned by ``workflow``. If the adapter kept
per-field copies of the project, a commit would have to invalidate them by hand.
The tests pin that one key holds the project and that a reset clears the widget
keys around it.

The scripts run under ``AppTest`` because the adapter needs a real session state.
None of them touch the workflow rules themselves — those are covered by
``tests/test_workflow_state.py``.
"""

from __future__ import annotations

from streamlit.testing.v1 import AppTest

from ui import session
from workflow.dependencies import DataKey

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def run(script) -> AppTest:  # noqa: ANN001 - AppTest wants a bare callable
    """Execute one script under a fresh AppTest session."""

    at = AppTest.from_function(script, default_timeout=60).run()
    assert list(at.exception) == [], [e.message for e in at.exception]
    return at


def observation(at: AppTest) -> dict:
    return at.session_state["observed"]


# --------------------------------------------------------------------------- #
# One state per session
# --------------------------------------------------------------------------- #


def test_get_workflow_creates_one_state_and_reuses_it() -> None:
    def script() -> None:
        import streamlit as st

        from ui import session

        first = session.get_workflow()
        second = session.get_workflow()
        st.session_state["observed"] = {
            "same_object": first is second,
            "stored": isinstance(st.session_state[session.STATE_KEY], type(first)),
        }

    result = observation(run(script))
    assert result == {"same_object": True, "stored": True}


def test_the_project_survives_a_rerun_without_being_recreated() -> None:
    def script() -> None:
        import streamlit as st

        from ui import session

        state = session.get_workflow()
        seen = st.session_state.setdefault("seen", [])
        seen.append(id(state))
        if not state.room:
            from models.schemas import OpeningInput, RoomInput, RoomType, Wall

            state.set_room(
                RoomInput(
                    room_type=RoomType.LIVING_ROOM,
                    name="Living Room",
                    width_cm=400,
                    length_cm=520,
                    door=OpeningInput(wall=Wall.SOUTH, offset_cm=60, width_cm=90),
                    window=OpeningInput(wall=Wall.NORTH, offset_cm=120, width_cm=160),
                )
            )
        st.session_state["observed"] = {"ids": list(seen), "room": state.room.name}

    at = AppTest.from_function(script, default_timeout=60)
    at.run()
    at.run()

    result = observation(at)
    # Two executions, one object, and the room written in the first run is still
    # there in the second. A per-rerun construction would fail both assertions.
    assert len(result["ids"]) == 2
    assert result["ids"][0] == result["ids"][1]
    assert result["room"] == "Living Room"


def test_has_workflow_does_not_create_state_as_a_side_effect() -> None:
    def script() -> None:
        import streamlit as st

        from ui import session

        before = session.has_workflow()
        created = session.STATE_KEY in st.session_state
        st.session_state["observed"] = {"before": before, "created": created}

    assert observation(run(script)) == {"before": False, "created": False}


# --------------------------------------------------------------------------- #
# Navigation
# --------------------------------------------------------------------------- #


def test_current_screen_defaults_to_room_and_ignores_a_junk_value() -> None:
    def script() -> None:
        import streamlit as st

        from ui import session

        default = session.current_screen()
        st.session_state[session.SCREEN_KEY] = "somewhere-else"
        after_junk = session.current_screen()
        st.session_state["observed"] = {"default": default, "after_junk": after_junk}

    assert observation(run(script)) == {"default": "room", "after_junk": "room"}


def test_go_to_rejects_a_screen_that_is_not_part_of_the_flow() -> None:
    def script() -> None:
        import streamlit as st

        from ui import session

        try:
            session.go_to("admin")
        except ValueError as error:
            st.session_state["observed"] = {"raised": True, "text": str(error)}
        else:
            st.session_state["observed"] = {"raised": False, "text": ""}

    result = observation(run(script))
    assert result["raised"] is True
    assert "admin" in result["text"]


def test_entering_and_leaving_the_workflow_is_only_a_view_change() -> None:
    def script() -> None:
        import streamlit as st

        from ui import session

        state = session.get_workflow()
        state.room = None
        session.enter_workflow()
        inside = session.has_entered()
        session.leave_workflow()
        outside = session.has_entered()
        st.session_state["observed"] = {
            "inside": inside,
            "outside": outside,
            "state_kept": st.session_state[session.STATE_KEY] is state,
        }

    assert observation(run(script)) == {
        "inside": True,
        "outside": False,
        "state_kept": True,
    }


# --------------------------------------------------------------------------- #
# Feedback
# --------------------------------------------------------------------------- #


def test_a_flash_message_is_shown_once_and_then_forgotten() -> None:
    def script() -> None:
        import streamlit as st

        from ui import session

        session.set_flash("Saved.", tone="success")
        first = session.take_flash()
        second = session.take_flash()
        st.session_state["observed"] = {"first": first, "second": second}

    assert observation(run(script)) == {
        "first": {"message": "Saved.", "tone": "success"},
        "second": None,
    }


def test_invalidation_message_is_empty_when_nothing_was_cleared() -> None:
    assert session.invalidation_message(()) == ""


def test_invalidation_message_names_one_result() -> None:
    message = session.invalidation_message((DataKey.BRIEF,))
    assert message == (
        "Earlier results no longer apply and were cleared: the design brief."
    )


def test_invalidation_message_reads_as_a_list_for_several_results() -> None:
    message = session.invalidation_message((DataKey.BRIEF, DataKey.CONCEPTS))
    assert message == (
        "Earlier results no longer apply and were cleared: the design brief and "
        "the design concepts."
    )


def test_invalidation_message_covers_every_clearable_result() -> None:
    """Every key a commit can drop must have a sentence, or the flash is vague."""

    clearable = (
        DataKey.BRIEF,
        DataKey.CONCEPTS,
        DataKey.SELECTED_CONCEPT,
        DataKey.FURNITURE,
        DataKey.MATERIALS,
        DataKey.SPATIAL,
        DataKey.BUDGET_ANALYSIS,
        DataKey.EVALUATION,
    )
    message = session.invalidation_message(clearable)
    assert message.startswith("Earlier results no longer apply")
    for key in clearable:
        # The label table is private, so the assertion is on the rendered words.
        assert session._KEY_LABELS[key]  # noqa: SLF001 - the mapping is the point
        assert session._KEY_LABELS[key] in message  # noqa: SLF001


def test_invalidation_message_says_nothing_was_lost_when_nothing_existed() -> None:
    """The first save must not announce that results were cleared.

    ``set_preferences`` correctly reports every dependent key, because the rule
    is "this result no longer applies". On a first save none of those results
    was ever generated, so the confirmation must be a plain acknowledgement
    rather than a claim that the user's work was discarded.
    """

    dropped = (DataKey.BRIEF, DataKey.CONCEPTS, DataKey.BUDGET_ANALYSIS)
    assert session.invalidation_message(dropped, previously_present=frozenset()) == ""
    assert (
        session.invalidation_message(
            dropped, previously_present=frozenset({DataKey.PREFERENCES})
        )
        == ""
    )
    # ``None`` opts out of filtering, which is what the plain "what did this
    # rule invalidate?" case wants.
    assert session.invalidation_message(dropped) != ""


def test_invalidation_message_names_only_what_actually_existed() -> None:
    dropped = (DataKey.BRIEF, DataKey.CONCEPTS, DataKey.BUDGET_ANALYSIS)
    message = session.invalidation_message(
        dropped, previously_present=frozenset({DataKey.BRIEF})
    )
    assert message == (
        "Earlier results no longer apply and were cleared: the design brief."
    )
    # A result that never existed is not named, so the user is not told about a
    # loss they did not suffer.
    assert "budget analysis" not in message


def test_present_keys_reads_the_workflow_rather_than_the_widgets() -> None:
    def script() -> None:
        import streamlit as st

        from models.schemas import (
            BudgetInput,
            DesignPreferences,
            DesignStyle,
            OpeningInput,
            PaletteDirection,
            RoomInput,
            RoomType,
            Wall,
        )
        from ui import session
        from workflow.dependencies import DataKey

        state = session.get_workflow()
        empty = session.present_keys(state)

        state.set_room(
            RoomInput(
                room_type=RoomType.LIVING_ROOM,
                name="Living Room",
                width_cm=400,
                length_cm=520,
                door=OpeningInput(wall=Wall.SOUTH, offset_cm=60, width_cm=90),
                window=OpeningInput(wall=Wall.NORTH, offset_cm=120, width_cm=160),
            )
        )
        with_room = session.present_keys(state)

        state.set_preferences(
            DesignPreferences(
                style=DesignStyle.JAPANDI,
                palette=PaletteDirection.WARM_NEUTRAL,
                material_preferences=[],
            )
        )
        st.session_state["observed"] = {
            "empty": sorted(key.name for key in empty),
            "with_room": sorted(key.name for key in with_room),
            "has_preferences": DataKey.PREFERENCES in session.present_keys(state),
        }

    result = observation(run(script))
    assert result["empty"] == []
    # All three room keys resolve to the room object, because that is what the
    # workflow stores; none of the result keys appear.
    assert result["with_room"] == [
        "ROOM_DIMENSIONS",
        "ROOM_OPENINGS",
        "ROOM_TYPE",
    ]
    assert result["has_preferences"] is True


# --------------------------------------------------------------------------- #
# Reset
# --------------------------------------------------------------------------- #


def test_reset_workflow_replaces_the_state_and_clears_its_widgets() -> None:
    def script() -> None:
        import streamlit as st

        from models.schemas import OpeningInput, RoomInput, RoomType, Wall
        from ui import session

        state = session.get_workflow()
        state.set_room(
            RoomInput(
                room_type=RoomType.LIVING_ROOM,
                name="Living Room",
                width_cm=400,
                length_cm=520,
                door=OpeningInput(wall=Wall.SOUTH, offset_cm=60, width_cm=90),
                window=OpeningInput(wall=Wall.NORTH, offset_cm=120, width_cm=160),
            )
        )
        st.session_state[session.widget_key("room_name")] = "Living Room"
        st.session_state[session.widget_key("seed:room_name")] = (0, "'Living Room'")
        session.set_flash("old message")

        session.reset_workflow()

        st.session_state["observed"] = {
            "room": session.get_workflow().room,
            "widgets": sorted(
                key
                for key in st.session_state
                if str(key).startswith(session.WIDGET_PREFIX)
            ),
            "flash": st.session_state.get(session.FLASH_KEY),
            "screen": st.session_state[session.SCREEN_KEY],
        }

    result = observation(run(script))
    assert result["room"] is None
    assert result["widgets"] == []
    assert result["flash"] is None
    assert result["screen"] == session.SCREEN_ROOM


def test_reset_workflow_bumps_the_generation_so_forms_reseed() -> None:
    def script() -> None:
        import streamlit as st

        from ui import session

        session.get_workflow()
        session.reset_workflow()
        first = st.session_state[session.GENERATION_KEY]
        session.reset_workflow()
        second = st.session_state[session.GENERATION_KEY]
        st.session_state["observed"] = {"first": first, "second": second}

    result = observation(run(script))
    assert result["second"] > result["first"] > 0


def test_reset_workflow_leaves_unrelated_session_keys_alone() -> None:
    def script() -> None:
        import streamlit as st

        from ui import session

        st.session_state["unrelated"] = "keep me"
        session.get_workflow()
        session.reset_workflow()
        st.session_state["observed"] = st.session_state["unrelated"]

    assert observation(run(script)) == "keep me"


# --------------------------------------------------------------------------- #
# Widget seeding
# --------------------------------------------------------------------------- #


def test_seed_sets_the_initial_value_once() -> None:
    def script() -> None:
        import streamlit as st

        from ui import session

        session.seed("room_name", "Living Room")
        st.session_state["observed"] = st.session_state[session.widget_key("room_name")]

    assert observation(run(script)) == "Living Room"


def test_seed_does_not_overwrite_what_the_user_typed() -> None:
    def script() -> None:
        import streamlit as st

        from ui import session

        session.seed("room_name", "Living Room")
        # The user edits the field, and an unrelated rerun happens: the stored
        # room is still "Living Room", so the field must keep the new text.
        st.session_state[session.widget_key("room_name")] = "Lounge"
        session.seed("room_name", "Living Room")
        st.session_state["observed"] = st.session_state[session.widget_key("room_name")]

    assert observation(run(script)) == "Lounge"


def test_seed_applies_a_new_stored_value_after_a_commit() -> None:
    def script() -> None:
        import streamlit as st

        from ui import session

        session.seed("room_name", "Living Room")
        # A commit changed the stored value, so the field follows it.
        session.seed("room_name", "Lounge")
        st.session_state["observed"] = st.session_state[session.widget_key("room_name")]

    assert observation(run(script)) == "Lounge"


def test_value_of_falls_back_when_the_widget_never_ran() -> None:
    def script() -> None:
        import streamlit as st

        from ui import session

        st.session_state["observed"] = session.value_of("room_name", "fallback")

    assert observation(run(script)) == "fallback"


# --------------------------------------------------------------------------- #
# Input completeness
# --------------------------------------------------------------------------- #


def test_inputs_are_complete_follows_the_workflow_not_the_fields() -> None:
    def script() -> None:
        from decimal import Decimal

        import streamlit as st

        from models.schemas import (
            BudgetInput,
            DesignPreferences,
            DesignStyle,
            OpeningInput,
            PaletteDirection,
            RoomInput,
            RoomType,
            UserRequirements,
            Wall,
        )
        from ui import session
        from workflow.state import WorkflowStep

        state = session.get_workflow()
        empty = session.inputs_are_complete()

        state.set_room(
            RoomInput(
                room_type=RoomType.LIVING_ROOM,
                name="Living Room",
                width_cm=400,
                length_cm=520,
                door=OpeningInput(wall=Wall.SOUTH, offset_cm=60, width_cm=90),
                window=OpeningInput(wall=Wall.NORTH, offset_cm=120, width_cm=160),
            )
        )
        room_only = session.inputs_are_complete()

        state.set_preferences(
            DesignPreferences(
                style=DesignStyle.JAPANDI,
                palette=PaletteDirection.WARM_NEUTRAL,
                material_preferences=[],
            )
        )
        state.set_requirements(
            UserRequirements(functional_requirements=[], notes="")
        )
        state.set_budget(BudgetInput(total_budget=Decimal("45000.00")))

        st.session_state["observed"] = {
            "empty": empty,
            "room_only": room_only,
            "complete": session.inputs_are_complete(),
            "workflow_says": state.is_complete(WorkflowStep.DESIGN_PREFERENCES),
        }

    result = observation(run(script))
    assert result["empty"] is False
    assert result["room_only"] is False
    assert result["complete"] is True
    assert result["complete"] == result["workflow_says"]
