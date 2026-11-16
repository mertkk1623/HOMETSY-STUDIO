"""The Streamlit session adapter around :class:`workflow.state.WorkflowState`.

This is the only place where Streamlit's session state and the workflow object
meet. It does three things and nothing else:

* keep exactly one ``WorkflowState`` alive for the session,
* remember which screen the user is on,
* turn the keys a commit invalidated into a sentence the user can read.

It deliberately holds no rules. "Is this step complete?" is answered by
``state.is_complete``, never by inspecting a widget, and the decision about what
becomes stale is made inside ``workflow`` by the one approved table.

Why one object rather than one key per field: a run of ``st.session_state["room"]
= ...`` assignments would have to re-implement invalidation by hand — exactly the
duplicate rule table Step 1 exists to prevent. The whole project lives under a
single key, so a rerun cannot produce two divergent copies of it.
"""

from __future__ import annotations

from typing import Final

from models.schemas import BudgetInput, DesignPreferences, RoomInput, UserRequirements
from workflow.dependencies import DataKey
from workflow.state import WorkflowState

#: The one key the project state lives under.
STATE_KEY: Final[str] = "hm_workflow_state"

#: Which screen is open. Separate from the workflow data because navigation is a
#: view concern: leaving a screen must not touch the project.
SCREEN_KEY: Final[str] = "hm_screen"

#: Whether the user has left the landing page for the workflow.
ENTERED_KEY: Final[str] = "hm_workflow_entered"

#: A message to show once on the next render, then forget.
FLASH_KEY: Final[str] = "hm_flash"

#: Bumped whenever the session is reset, so every form knows to re-seed its
#: widgets from the fresh state instead of reusing values from before.
GENERATION_KEY: Final[str] = "hm_generation"

#: Every widget key this package creates starts with this prefix, which is what
#: makes a clean reset possible without touching anything else in the session.
WIDGET_PREFIX: Final[str] = "hmw_"

SCREEN_ROOM: Final[str] = "room"
SCREEN_PREFERENCES: Final[str] = "preferences"
SCREEN_REVIEW: Final[str] = "review"
SCREEN_BRIEF: Final[str] = "brief"
SCREEN_CONCEPTS: Final[str] = "concepts"
SCREEN_PLAN: Final[str] = "plan"
SCREEN_EVALUATION: Final[str] = "evaluation"
SCREEN_BUDGET: Final[str] = "budget"
SCREEN_REPORT: Final[str] = "report"

SCREEN_ORDER: Final[tuple[str, ...]] = (
    SCREEN_ROOM,
    SCREEN_PREFERENCES,
    SCREEN_REVIEW,
    SCREEN_BRIEF,
    SCREEN_CONCEPTS,
    SCREEN_PLAN,
    SCREEN_EVALUATION,
    SCREEN_BUDGET,
    SCREEN_REPORT,
)

SCREEN_TITLES: Final[dict[str, str]] = {
    SCREEN_ROOM: "Room information",
    SCREEN_PREFERENCES: "Design preferences",
    SCREEN_REVIEW: "Project input review",
    SCREEN_BRIEF: "Design brief",
    SCREEN_CONCEPTS: "Design concepts",
    SCREEN_PLAN: "Design plan",
    SCREEN_EVALUATION: "Design evaluation",
    SCREEN_BUDGET: "Budget analysis",
    SCREEN_REPORT: "Final report",
}

#: Plain-language names for the results a change can clear, used in the message
#: shown after an edit. The wording lives here because it is interface copy, not
#: a rule; which keys appear is still decided by ``workflow``.
_KEY_LABELS: Final[dict[DataKey, str]] = {
    DataKey.BRIEF: "the design brief",
    DataKey.CONCEPTS: "the design concepts",
    DataKey.SELECTED_CONCEPT: "the selected concept",
    DataKey.FURNITURE: "the furniture recommendations",
    DataKey.MATERIALS: "the material recommendations",
    DataKey.SPATIAL: "the spatial validation",
    DataKey.BUDGET_ANALYSIS: "the budget analysis",
    DataKey.EVALUATION: "the design evaluation",
}


def get_workflow() -> WorkflowState:
    """The session's one workflow state, created on first use.

    A rerun calls this again; because the object is already in the session, the
    user's inputs survive. Creating a new ``WorkflowState`` on every rerun would
    silently discard the project, which is the bug this function exists to
    prevent.
    """

    import streamlit as st

    state = st.session_state.get(STATE_KEY)
    if state is None:
        state = WorkflowState()
        st.session_state[STATE_KEY] = state
    if not isinstance(state, WorkflowState):  # pragma: no cover - defensive
        raise TypeError(
            "The session contains a value that is not a WorkflowState under "
            f"'{STATE_KEY}'."
        )
    return state


def has_workflow() -> bool:
    """True when a state object already exists, without creating one."""

    import streamlit as st

    return isinstance(st.session_state.get(STATE_KEY), WorkflowState)


def reset_workflow() -> None:
    """Throw the project away and re-seed every form.

    Bumping the generation invalidates the widget seed markers, so the fresh
    state is reflected in the inputs instead of the values left on screen.
    """

    import streamlit as st

    st.session_state[STATE_KEY] = WorkflowState()
    st.session_state[GENERATION_KEY] = int(st.session_state.get(GENERATION_KEY, 0)) + 1
    for key in [key for key in st.session_state if key.startswith(WIDGET_PREFIX)]:
        del st.session_state[key]
    st.session_state.pop(FLASH_KEY, None)
    st.session_state[SCREEN_KEY] = SCREEN_ROOM


# --------------------------------------------------------------------------- #
# Navigation
# --------------------------------------------------------------------------- #


def current_screen() -> str:
    import streamlit as st

    screen = st.session_state.get(SCREEN_KEY, SCREEN_ROOM)
    return screen if screen in SCREEN_ORDER else SCREEN_ROOM


def go_to(screen: str) -> None:
    """Switch screens and rerun immediately.

    The rerun is what makes the switch feel atomic: without it the user would
    see the previous screen's output under the new heading for one frame.
    """

    import streamlit as st

    if screen not in SCREEN_ORDER:
        raise ValueError(f"Unknown screen: {screen}")
    st.session_state[SCREEN_KEY] = screen
    st.rerun()


def enter_workflow() -> None:
    import streamlit as st

    st.session_state[ENTERED_KEY] = True
    st.session_state.setdefault(SCREEN_KEY, SCREEN_ROOM)


def leave_workflow() -> None:
    """Return to the landing page. The project itself is kept."""

    import streamlit as st

    st.session_state[ENTERED_KEY] = False


def has_entered() -> bool:
    import streamlit as st

    return bool(st.session_state.get(ENTERED_KEY, False))


# --------------------------------------------------------------------------- #
# Feedback
# --------------------------------------------------------------------------- #


def set_flash(message: str, *, tone: str = "info") -> None:
    """Queue one message for the next render."""

    import streamlit as st

    st.session_state[FLASH_KEY] = {"message": message, "tone": tone}


def take_flash() -> dict[str, str] | None:
    """Read and clear the queued message."""

    import streamlit as st

    return st.session_state.pop(FLASH_KEY, None)


def invalidation_message(
    dropped: tuple[DataKey, ...],
    *,
    previously_present: frozenset[DataKey] | None = None,
) -> str:
    """Explain what an edit cleared, in the workflow's own ordering.

    Returns an empty string when nothing was dropped, so callers can show a
    plain confirmation instead of "nothing was cleared".

    ``previously_present`` is the set of keys that held data *before* the edit,
    and ``None`` means "do not filter". Passing a set — including an empty one —
    restricts the message to what the user actually lost. ``set_*`` correctly
    reports every key its dependency table invalidates, because the rule is
    "this result no longer applies"; but a message is about a loss, and on a
    first save nothing has been generated yet. Without the distinction the
    first save would announce that earlier results had been cleared.
    """

    reported = [
        key
        for key in dropped
        if key in _KEY_LABELS
        and (previously_present is None or key in previously_present)
    ]
    labels = [_KEY_LABELS[key] for key in reported]
    if not labels:
        return ""
    if len(labels) == 1:
        listed = labels[0]
    else:
        listed = ", ".join(labels[:-1]) + " and " + labels[-1]
    return f"Earlier results no longer apply and were cleared: {listed}."


def present_keys(state: WorkflowState) -> frozenset[DataKey]:
    """Which data keys currently hold something.

    Read through ``WorkflowState.data_for`` so this never invents its own idea
    of "empty" — an empty furniture tuple and a missing brief are the workflow's
    answers, not the interface's.
    """

    return frozenset(key for key in DataKey if state.data_for(key) is not None)


# --------------------------------------------------------------------------- #
# Widget seeding
# --------------------------------------------------------------------------- #


def widget_key(name: str) -> str:
    return f"{WIDGET_PREFIX}{name}"


def seed(name: str, value: object) -> None:
    """Give a widget its initial value, without ever overwriting the user's.

    Seeding happens once per form entry. If the workflow state already holds a
    value — because the user came back to edit a saved room — the widget starts
    from that value rather than from an empty field.
    """

    import streamlit as st

    key = widget_key(name)
    marker = widget_key(f"seed:{name}")
    generation = int(st.session_state.get(GENERATION_KEY, 0))
    token = (generation, repr(value))

    if key not in st.session_state or st.session_state.get(marker) != token:
        st.session_state[key] = value
        st.session_state[marker] = token


def value_of(name: str, default: object) -> object:
    """The current widget value, or ``default`` when it has never been set."""

    import streamlit as st

    return st.session_state.get(widget_key(name), default)


# --------------------------------------------------------------------------- #
# Read-only views of the stored inputs
# --------------------------------------------------------------------------- #


def stored_room() -> RoomInput | None:
    return get_workflow().room


def stored_preferences() -> DesignPreferences | None:
    return get_workflow().preferences


def stored_requirements() -> UserRequirements | None:
    return get_workflow().requirements


def stored_budget() -> BudgetInput | None:
    return get_workflow().budget


def inputs_are_complete() -> bool:
    """True when the four deterministic inputs are all present.

    This is a *display* convenience for the review screen; the authority on step
    completion remains ``WorkflowState.is_complete``.
    """

    from workflow.state import WorkflowStep

    return get_workflow().is_complete(WorkflowStep.DESIGN_PREFERENCES)


__all__ = [
    "ENTERED_KEY",
    "FLASH_KEY",
    "GENERATION_KEY",
    "SCREEN_BRIEF",
    "SCREEN_BUDGET",
    "SCREEN_CONCEPTS",
    "SCREEN_EVALUATION",
    "SCREEN_KEY",
    "SCREEN_ORDER",
    "SCREEN_PLAN",
    "SCREEN_PREFERENCES",
    "SCREEN_REPORT",
    "SCREEN_REVIEW",
    "SCREEN_ROOM",
    "SCREEN_TITLES",
    "STATE_KEY",
    "WIDGET_PREFIX",
    "current_screen",
    "enter_workflow",
    "get_workflow",
    "go_to",
    "has_entered",
    "has_workflow",
    "inputs_are_complete",
    "invalidation_message",
    "leave_workflow",
    "present_keys",
    "reset_workflow",
    "seed",
    "set_flash",
    "stored_budget",
    "stored_preferences",
    "stored_requirements",
    "stored_room",
    "take_flash",
    "value_of",
    "widget_key",
]
