"""Deterministic calculation engines.

Every module in this package is pure Python: no Streamlit, no network, no AI.
Import the specific module you need (``core.room_engine``,
``core.spatial_engine``, ``core.placement_engine``, ``core.budget_engine``,
``core.validation``) rather than relying on re-exports, so that dependency
direction stays obvious.

``core.spatial_engine`` validates geometry; ``core.placement_engine`` proposes a
layout and delegates its validation to the spatial engine. Neither re-implements
the other's rules.
"""
