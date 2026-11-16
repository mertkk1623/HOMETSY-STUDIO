"""AI integration layer.

Modules here talk to the language model and nothing else: no Streamlit import,
no geometry, no budget arithmetic. The deterministic calculations live in
``core`` and must stay authoritative.

Import direction is one-way:

    app / pages  ->  ai  ->  (network)
                     \\
                      ->  models (Pydantic schemas)

Structure
---------
``ai.config``
    Resolves the endpoint, model and credential.
``ai.client``
    The single place where HTTP happens. Returns the assistant's raw text.
``ai.parsing``
    Turns that text into a validated Pydantic model, with one correction.
``ai.prompt``
    Builds prompts and runs the request/parse/correct flow for all services.
``ai.brief_analyzer``
    AI operation 1: structured design brief.
``ai.concept_generator``
    AI operation 2: exactly three distinct concepts.
``ai.design_advisor``
    AI operation 3: catalog furniture plus materials, priced by Python.
``ai.design_evaluator``
    AI operation 4: assessment against Python's spatial and budget results.

The four service modules are independent: none imports another. Composing them
into a workflow belongs to the application layer (Phase 5).
"""

from __future__ import annotations

__all__: list[str] = []
