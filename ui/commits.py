"""Pure conversions from widget values to validated models.

Every screen ends the same way: a handful of widget values have to become one
Pydantic model, and that model has to satisfy ``core.validation``. Doing that
inside a page function would put business rules in the interface, so it lives
here instead — as plain functions with no Streamlit import, which the tests can
call directly.

Two rules are enforced here:

* **Pydantic is the first gate.** A dimension outside the approved range, a door
  that does not fit its wall, an empty room name: all of it is rejected by the
  models first, because those constraints already exist and duplicating them
  would let the two drift apart.
* **``core.validation`` is the second gate.** It adds the cross-field checks and
  the user-facing wording. Its errors block the commit; its warnings do not,
  but they are returned so the screen can show them.

A failed conversion never produces a model, so a page can only call
``set_room()`` with something that already passed both gates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Generic, Sequence, TypeVar

from core.validation import (
    ValidationFinding,
    validate_budget_input,
    validate_inputs,
    validate_room_input,
)
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

T = TypeVar("T")


# --------------------------------------------------------------------------- #
# Result type
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class FieldIssue:
    """One reason a field, or the form as a whole, cannot be accepted."""

    field: str
    message: str


@dataclass(frozen=True)
class Outcome(Generic[T]):
    """Either a validated model, or the reasons it could not be built.

    ``warnings`` are advisory: the value is usable, but the user should know.
    """

    value: T | None = None
    issues: tuple[FieldIssue, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def is_ok(self) -> bool:
        return self.value is not None and not self.issues


def _issue(field: str, message: str) -> FieldIssue:
    return FieldIssue(field=field, message=message)


def _from_findings(
    findings: Sequence[ValidationFinding],
) -> tuple[tuple[FieldIssue, ...], tuple[str, ...]]:
    """Split findings into blocking issues and advisory warnings."""

    issues = tuple(_issue(f.stage, f"{f.message}") for f in findings if f.is_error)
    warnings = tuple(f.message for f in findings if not f.is_error)
    return issues, warnings


# --------------------------------------------------------------------------- #
# Pydantic message mapping
# --------------------------------------------------------------------------- #

#: ``type`` values from :class:`pydantic.ValidationError` rendered as sentences a
#: person can act on. Anything not listed falls back to Pydantic's own wording,
#: which is still free of a traceback.
_MESSAGES: dict[str, str] = {
    "string_too_short": "This field cannot be empty.",
    "string_too_long": "This entry is too long.",
    "missing": "This field is required.",
    "greater_than_equal": "This value is below the allowed minimum.",
    "less_than_equal": "This value is above the allowed maximum.",
    "greater_than": "This value must be greater than zero.",
    "decimal_places": "Use at most two decimal places.",
    "decimal_max_places": "Use at most two decimal places.",
    "decimal_max_digits": "This amount is too large.",
    "enum": "Choose one of the available options.",
    "literal_error": "Choose one of the available options.",
    "float_parsing": "Enter a number.",
    "decimal_parsing": "Enter a valid amount.",
    "int_parsing": "Enter a whole number.",
    "value_error": "",  # the message already reads as a sentence
}

#: Human names for model fields, so a message names the screen's label.
_FIELD_LABELS: dict[str, str] = {
    "name": "Room name",
    "width_cm": "Room width",
    "length_cm": "Room length",
    "ceiling_height_cm": "Ceiling height",
    "room_type": "Room type",
    "door.width_cm": "Door width",
    "door.offset_cm": "Door offset",
    "window.width_cm": "Window width",
    "window.offset_cm": "Window offset",
    "total_budget": "Total budget",
    "style": "Design style",
    "palette": "Colour palette",
}


def _label(location: tuple[object, ...], fallback: str = "Form") -> str:
    if not location:
        return fallback
    dotted = ".".join(str(part) for part in location)
    if dotted in _FIELD_LABELS:
        return _FIELD_LABELS[dotted]
    last = str(location[-1])
    return _FIELD_LABELS.get(last, last.replace("_", " ").capitalize())


def issues_from_validation_error(
    error: object, *, fallback_label: str = "Form"
) -> tuple[FieldIssue, ...]:
    """Turn a Pydantic error into readable field messages.

    The raw object is never surfaced: it contains input values and a type name,
    neither of which belongs in front of a user. A model-level validator reports
    an empty location, so those messages are attributed to the model's own name
    rather than to a nameless field.
    """

    collected: list[FieldIssue] = []
    for detail in getattr(error, "errors", lambda: [])():
        location = tuple(detail.get("loc", ()))
        kind = str(detail.get("type", ""))
        mapped = _MESSAGES.get(kind, "")
        text = mapped or str(detail.get("msg", "")).replace("Value error, ", "")
        # Pydantic repeats the field name inside validator messages; the label
        # already tells the user which field it was.
        prefix = _label(location, fallback_label)
        collected.append(_issue(prefix, f"{prefix}: {text}" if text else prefix))
    if not collected:  # pragma: no cover - every ValidationError has details
        collected.append(
            _issue(fallback_label, "The entered values could not be accepted.")
        )
    return tuple(collected)


# --------------------------------------------------------------------------- #
# Room
# --------------------------------------------------------------------------- #


def build_room(
    *,
    room_type: RoomType,
    name: str,
    width_cm: float,
    length_cm: float,
    ceiling_height_cm: float,
    door_wall: Wall,
    door_offset_cm: float,
    door_width_cm: float,
    window_wall: Wall,
    window_offset_cm: float,
    window_width_cm: float,
) -> Outcome[RoomInput]:
    """Validate one room submission.

    The name is trimmed before validation so a space-only entry is rejected as
    empty rather than accepted as a one-character name. Nothing else is
    normalised: the numbers the user typed are the numbers that get stored, and
    ``core.room_engine`` is the only thing allowed to judge their plausibility.
    """

    from pydantic import ValidationError

    cleaned_name = name.strip()
    if not cleaned_name:
        return Outcome(
            issues=(_issue("Room name", "Room name: give the room a name."),)
        )

    try:
        room = RoomInput(
            room_type=room_type,
            name=cleaned_name,
            width_cm=width_cm,
            length_cm=length_cm,
            ceiling_height_cm=ceiling_height_cm,
            door=OpeningInput(
                wall=door_wall, offset_cm=door_offset_cm, width_cm=door_width_cm
            ),
            window=OpeningInput(
                wall=window_wall,
                offset_cm=window_offset_cm,
                width_cm=window_width_cm,
            ),
        )
    except ValidationError as error:
        return Outcome(
            issues=issues_from_validation_error(error, fallback_label="Room")
        )

    issues, warnings = _from_findings(validate_room_input(room))
    if issues:
        return Outcome(issues=issues, warnings=warnings)
    return Outcome(value=room, warnings=warnings)


# --------------------------------------------------------------------------- #
# Preferences, requirements, budget
# --------------------------------------------------------------------------- #


def clean_entries(entries: Sequence[str], *, limit: int) -> list[str]:
    """Trim, drop blanks and de-duplicate while keeping the user's order.

    Material preferences and functional requirements are free text in the model,
    so the interface is the only place that can stop a stray empty string from
    reaching the brief prompt.
    """

    seen: set[str] = set()
    cleaned: list[str] = []
    for entry in entries:
        text = str(entry).strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(text)
        if len(cleaned) == limit:
            break
    return cleaned


def build_preferences(
    *,
    style: DesignStyle,
    palette: PaletteDirection,
    material_preferences: Sequence[str],
) -> Outcome[DesignPreferences]:
    """Validate a style, one palette and any material notes."""

    from pydantic import ValidationError

    try:
        preferences = DesignPreferences(
            style=style,
            palette=palette,
            material_preferences=clean_entries(material_preferences, limit=10),
        )
    except ValidationError as error:
        return Outcome(
            issues=issues_from_validation_error(error, fallback_label="Preferences")
        )
    return Outcome(value=preferences)


def build_requirements(
    *, functional_requirements: Sequence[str], notes: str
) -> Outcome[UserRequirements]:
    """Validate the functional requirements and the free-form notes."""

    from pydantic import ValidationError

    try:
        requirements = UserRequirements(
            functional_requirements=clean_entries(
                functional_requirements, limit=20
            ),
            notes=notes.strip(),
        )
    except ValidationError as error:
        return Outcome(
            issues=issues_from_validation_error(error, fallback_label="Requirements")
        )
    return Outcome(value=requirements)


def build_budget(amount: float | int | Decimal | str) -> Outcome[BudgetInput]:
    """Validate the budget, keeping the money path in ``Decimal``.

    The widget hands over a float; converting through ``str`` keeps the value the
    user typed instead of the nearest binary approximation. No rounding is
    applied — an amount with more than two decimal places is rejected by the
    model rather than silently changed.
    """

    from pydantic import ValidationError

    try:
        decimal_amount = (
            amount if isinstance(amount, Decimal) else Decimal(str(amount))
        )
    except (InvalidOperation, ValueError):
        return Outcome(
            issues=(_issue("Total budget", "Total budget: enter a valid amount."),)
        )

    try:
        budget = BudgetInput(total_budget=decimal_amount)
    except ValidationError as error:
        return Outcome(issues=issues_from_validation_error(error))

    issues, warnings = _from_findings(validate_budget_input(budget))
    if issues:
        return Outcome(issues=issues, warnings=warnings)
    return Outcome(value=budget, warnings=warnings)


def overall_warnings(
    room: RoomInput | None,
    preferences: DesignPreferences | None,
    requirements: UserRequirements | None,
    budget: BudgetInput | None,
) -> tuple[str, ...]:
    """The advisory findings for the four inputs as a set.

    Returns nothing until all four exist, because ``validate_inputs`` describes
    the combination rather than any single value.
    """

    if None in (room, preferences, requirements, budget):
        return ()
    assert room is not None
    assert preferences is not None
    assert requirements is not None
    assert budget is not None
    findings = validate_inputs(room, preferences, requirements, budget)
    return tuple(f.message for f in findings if not f.is_error)


def room_summary_rows(room: RoomInput) -> list[tuple[str, str]]:
    """Display rows for a stored room. Formatting only, no calculation.

    The area comes from the model's own property, which is the single approved
    place where square metres are derived.
    """

    return [
        ("Room type", room.room_type.value),
        ("Name", room.name),
        ("Width × length", f"{room.width_cm:g} × {room.length_cm:g} cm"),
        ("Floor area", f"{room.area_sqm:.2f} m²"),
        ("Ceiling height", f"{room.ceiling_height_cm:g} cm"),
        (
            "Door",
            f"{room.door.wall.value} wall, {room.door.width_cm:g} cm wide, "
            f"offset {room.door.offset_cm:g} cm",
        ),
        (
            "Window",
            f"{room.window.wall.value} wall, {room.window.width_cm:g} cm wide, "
            f"offset {room.window.offset_cm:g} cm",
        ),
    ]


def format_money(amount: Decimal, currency: str = "TRY") -> str:
    """Group thousands for display. Presentation only.

    Delegates to :func:`core.budget_engine.format_money` so the screen, the
    engine's own sentences and the PDF cannot format the same amount three ways.
    """

    from core.budget_engine import format_money as _format_money

    return _format_money(amount, currency)


__all__ = [
    "FieldIssue",
    "Outcome",
    "build_budget",
    "build_preferences",
    "build_requirements",
    "build_room",
    "clean_entries",
    "format_money",
    "issues_from_validation_error",
    "overall_warnings",
    "room_summary_rows",
]
