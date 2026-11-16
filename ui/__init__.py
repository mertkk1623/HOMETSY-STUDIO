"""Streamlit presentation layer.

This package is the only part of the application that imports ``streamlit``. It
is an adapter: it renders widgets, collects values and forwards them to the
workflow layer. Every decision — what is valid, what is stale, what may run next
— belongs to ``workflow`` and ``core``; nothing here restates those rules.

Module map:

``ui.theme``        design tokens, the central stylesheet and small HTML helpers
``ui.commits``      pure functions turning widget values into validated models
``ui.session``      the Streamlit session-state adapter around ``WorkflowState``
``ui.references``   the local style and palette reference library
``ui.ai_actions``   the only caller of the AI services; imports ``ai`` lazily
``ui.pages_*``      the workflow screens, in the order the user walks them
"""

from __future__ import annotations

__all__: list[str] = []
