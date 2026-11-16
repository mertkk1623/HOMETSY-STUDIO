"""Workflow state for the V1 interior design pipeline.

This package coordinates the user journey: it records what the user entered,
what each AI step produced, and — most importantly — makes sure a result can
never outlive the input it was derived from.

It contains no Streamlit, no HTTP and no calculations of its own. Geometry lives
in ``core``, pricing in ``core``, prompt construction and transport in ``ai``.

Dependency direction, which the tests enforce:

    app / pages  ->  workflow  ->  core, models
                         |
                         x  no import of ``ai``  (the caller supplies results)
                         x  no import of ``streamlit``
"""

from __future__ import annotations

__all__: list[str] = []
