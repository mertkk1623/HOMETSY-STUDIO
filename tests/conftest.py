"""Shared pytest fixtures for the Phase 1 model tests."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from ai.client import ChatCompletion
from ai.config import AIConfig
from models.schemas import (
    BudgetAnalysis,
    BudgetInput,
    ConceptCollection,
    DesignBrief,
    DesignConcept,
    DesignEvaluation,
    DesignPreferences,
    DesignStyle,
    FurnitureItem,
    FurnitureRecommendation,
    OpeningInput,
    PaletteDirection,
    ProjectResult,
    RoomInput,
    RoomType,
    SpatialValidation,
    UserRequirements,
    Wall,
)

#: Repository root, used to locate the local data files.
PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def room() -> RoomInput:
    return RoomInput(
        room_type=RoomType.LIVING_ROOM,
        name="Living Room",
        width_cm=400,
        length_cm=520,
        ceiling_height_cm=270,
        door=OpeningInput(wall=Wall.SOUTH, offset_cm=60, width_cm=90),
        window=OpeningInput(wall=Wall.NORTH, offset_cm=120, width_cm=160),
    )


@pytest.fixture
def preferences() -> DesignPreferences:
    return DesignPreferences(
        style=DesignStyle.JAPANDI,
        palette=PaletteDirection.WARM_NEUTRAL,
        material_preferences=["oak", "linen"],
    )


@pytest.fixture
def requirements() -> UserRequirements:
    return UserRequirements(
        functional_requirements=["Seating for four", "Reading corner"],
        notes="Keep the window side open.",
    )


@pytest.fixture
def budget() -> BudgetInput:
    return BudgetInput(total_budget=Decimal("45000.00"))


def make_concept(name: str) -> DesignConcept:
    return DesignConcept(
        name=name,
        description=f"{name} concept description.",
        design_direction="Quiet, low-contrast composition.",
        color_and_material_direction="Warm neutrals with oak and linen.",
        furniture_approach="Low-profile seating with a slim media unit.",
        functional_rationale="Keeps the circulation path along the window clear.",
        budget_suitability="Fits the stated budget with room to spare.",
    )


@pytest.fixture
def concepts() -> ConceptCollection:
    return ConceptCollection(
        concepts=[
            make_concept("Quiet Oak"),
            make_concept("Soft Contrast"),
            make_concept("Warm Studio"),
        ]
    )


@pytest.fixture
def project_result(
    room: RoomInput,
    preferences: DesignPreferences,
    requirements: UserRequirements,
    budget: BudgetInput,
    concepts: ConceptCollection,
) -> ProjectResult:
    return ProjectResult(
        room=room,
        preferences=preferences,
        requirements=requirements,
        budget=budget,
        brief=DesignBrief(
            summary="A calm living room for four people with a reading corner.",
            functional_priorities=["Seating for four"],
            constraints=["One door and one window"],
            ambiguities=[],
            warnings=[],
        ),
        concepts=concepts,
        selected_concept=concepts.concepts[0],
        recommendations=[
            # Phase 3 introduced catalog-aware validation, so the fixture now
            # references a real catalog id (``sofa_three_seat``) rather than the
            # arbitrary ``sofa_3_seat`` placeholder used before the catalog was
            # part of the validated surface.
            FurnitureRecommendation(
                item_id="sofa_three_seat",
                quantity=1,
                rationale="Main seating.",
            )
        ],
        spatial_validation=SpatialValidation(
            is_valid=True,
            boundary_violations=[],
            overlaps=[],
            warnings=[],
        ),
        budget_analysis=BudgetAnalysis(
            furniture_subtotal=Decimal("21000.00"),
            total_estimated=Decimal("21000.00"),
            remaining_budget=Decimal("24000.00"),
        ),
        evaluation=DesignEvaluation(
            requirement_compatibility="Seating for four is satisfied.",
            style_consistency="Consistent with Japandi.",
            functional_suitability="Circulation remains clear.",
            budget_suitability="Within budget.",
        ),
    )


# --------------------------------------------------------------------------- #
# AI-layer fixtures (Phase 4 Steps 5)
# --------------------------------------------------------------------------- #

#: A fake credential. Not a real key; safe to appear in test files.
AI_TEST_KEY = "test-key-0123456789abcdef"


@pytest.fixture
def ai_config() -> AIConfig:
    """A configuration that never leaves the process."""

    return AIConfig(api_key=AI_TEST_KEY)


@pytest.fixture
def catalog() -> list[FurnitureItem]:
    """The real local furniture catalog."""

    path = PROJECT_ROOT / "data" / "furniture_catalog.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [FurnitureItem.model_validate(entry) for entry in payload["items"]]


@pytest.fixture
def fake_completer() -> FakeCompleter:
    """A completer that returns a queued content string per call."""

    return FakeCompleter()


class FakeCompleter:
    """Stand-in for :func:`ai.client.complete`.

    Records every call so tests can assert how many requests were made and what
    they contained, without opening a socket.
    """

    def __init__(self, *contents: str) -> None:
        self._contents = list(contents)
        self.calls: list[dict[str, object]] = []

    def __call__(
        self,
        config: AIConfig,
        messages: list[dict[str, str]],
        *,
        max_tokens: int,
        temperature: float = 0.0,
        timeout: float | None = None,
    ) -> ChatCompletion:
        self.calls.append(
            {
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "timeout": timeout,
            }
        )
        if not self._contents:
            raise AssertionError(
                "The service made more requests than the test expected."
            )
        result = self._contents.pop(0)
        if isinstance(result, BaseException):
            raise result
        return ChatCompletion(
            content=result,
            model=config.model,
            finish_reason="stop",
        )

    @property
    def call_count(self) -> int:
        return len(self.calls)

    def queue(self, *contents: str | BaseException) -> FakeCompleter:
        """Add answers to the queue; an exception instance is raised instead."""

        self._contents.extend(contents)
        return self

    def prompt_text(self, index: int = 0) -> str:
        """All message content of one call, joined for substring assertions."""

        messages = self.calls[index]["messages"]
        return "\n".join(
            message["content"] for message in messages  # type: ignore[union-attr]
        )
