# Phase 4 / Step 5 — Completion Report

**Project:** Hometsy — Room Intelligence Studio
**Phase:** 4 — DeepSeek AI Integration
**Step:** 5 — Four AI Functions
**Date:** 2026-11-14
**Status:** Implementation and tests complete; awaiting approval before Phase 5.

---

## 1. Objective

Implement the four approved AI operations as independent modules, each with its
own prompt, its own validated output model, and the shared
request → parse → single correction flow. Deterministic work (geometry,
dimensions, overlap, budget) must remain in Python.

---

## 2. Completed Work

1. **Shared request layer** (`ai/prompt.py`) — prompt composition plus the one
   and only call/parse/correct path used by all four services.
2. **Brief Analyzer** (`ai/brief_analyzer.py`) — operation 1.
3. **Concept Generator** (`ai/concept_generator.py`) — operation 2, exactly
   three concepts.
4. **Design Advisor** (`ai/design_advisor.py`) — operation 3, catalog
   references plus Python-owned verification and pricing.
5. **Design Evaluator** (`ai/design_evaluator.py`) — operation 4, interprets
   results Python already computed.
6. **Two new Pydantic models** (`MaterialRecommendation`,
   `DesignRecommendation`) added to `models/schemas.py`. No existing model was
   altered.
7. **Correction-loop fix in `ai/parsing.py`** — a transport error raised during
   the correction attempt now propagates as itself instead of being wrapped as
   `AICorrectionFailedError`.
8. **Test infrastructure** — `FakeCompleter` and AI fixtures in
   `tests/conftest.py`; 110 new tests across two new files.
9. **Documentation of the layer** — `ai/__init__.py` rewritten to describe the
   eight-module structure and the one-way import direction.

---

## 3. Files Created and Modified

### Created

| File | Lines | Purpose |
|---|---:|---|
| `ai/prompt.py` | 278 | `PromptSpec`, `run_structured_request`, JSON serialisation, shared prompt fragments |
| `ai/brief_analyzer.py` | 175 | `analyze_brief`, `analyze_brief_with_prompt`, `build_prompt`, `MAX_TOKENS = 2000` |
| `ai/concept_generator.py` | 156 | `generate_concepts`, `build_prompt`, `MAX_TOKENS = 6000` |
| `ai/design_advisor.py` | 275 | `recommend_furniture`, `verify_catalog_references`, `CatalogCheck`, `AdvisorResult`, `MAX_TOKENS = 4000` |
| `ai/design_evaluator.py` | 238 | `evaluate_design`, `build_prompt`, three deterministic prompt blocks, `MAX_TOKENS = 3000` |
| `tests/test_ai_prompt.py` | 430 | 38 tests for the shared layer |
| `tests/test_ai_services.py` | 1038 | 70 tests for the four services |
| `reports/phase-4-step-5/COMPLETION_REPORT.md` | — | This report |
| `reports/phase-4-step-5/TEST_REPORT.md` | — | Test evidence |
| `reports/phase-4-step-5/NEXT_SESSION.md` | — | Handover notes |

### Modified

| File | Change |
|---|---|
| `models/schemas.py` | Added `MaterialRecommendation` and `DesignRecommendation`; both added to `__all__`. No existing class, field, constraint or validator changed. |
| `models/__init__.py` | Re-exports the two new models. |
| `tests/conftest.py` | Added `PROJECT_ROOT`, `AI_TEST_KEY`, `ai_config`, `catalog`, `fake_completer` fixtures and the `FakeCompleter` class. |
| `ai/parsing.py` | Added an `except AIError: raise` branch inside `parse_with_correction` so transport failures during a correction keep their own identity. |
| `tests/test_ai_parsing.py` | Two new tests for that behaviour (110 → 112). |
| `ai/__init__.py` | Rewritten as layer documentation. |

### Deliberately untouched

`app.py`, `requirements.txt`, `opencode.json`, `.env.example`, `core/*`,
`data/*`, `assets/*`, all design documents.

---

## 4. The Four AI Functions

### 4.1 `analyze_brief(config, room, preferences, requirements, budget)`

Returns `DesignBrief`.

**Input context:** the full validated input models, plus a
`CALCULATED ROOM FACTS` block containing floor area and the four wall spans
taken from `RoomInput`. The model is told these are authoritative and must not
be recomputed.

**Output contract:** `summary`, `functional_priorities`, `constraints`,
`ambiguities`, `warnings`. Lists are capped at 10 items of ≤200 characters.

**Role boundary:** analyses intent. Explicitly told "You do not design the
room, choose furniture, or change any figure you are given."

**Extra entry point:** `analyze_brief_with_prompt()` returns a `BriefAnalysis`
(`brief` + `prompt`) for the UI's "what was sent" panel and for prompt tests.

### 4.2 `generate_concepts(config, room, preferences, requirements, budget, brief)`

Returns `ConceptCollection` containing exactly three `DesignConcept` objects.

**Distinctness enforcement — two independent layers:**

1. Prompt rules: each concept must have a different organising idea (seating
   arrangement, focal point, or use of budget); "do not submit the same concept
   under three names"; do not vary only the adjectives.
2. Schema validation: `ConceptCollection` already rejects a count other than
   three and duplicate names — so a copy-paste answer fails validation and
   consumes the single correction rather than reaching the UI.

**Truncation policy:** `finish_reason=length` surfaces as
`AITruncatedResponseError` and is **not** corrected. A half-written concept set
needs more room, not a reformat, and silently raising `max_tokens` is forbidden
by the step rules.

### 4.3 `recommend_furniture(config, room, preferences, budget, brief, concept, catalog)`

Returns `AdvisorResult` = `recommendation` (`DesignRecommendation`) +
`catalog_check` (`CatalogCheck`) + `budget` (`BudgetResult`).

**Catalog-bound prompt:** only entries whose `supported_room_types` contains the
selected room type are listed, so an unusable identifier cannot be picked from
the list. `catalogue_entry()` renders id, name, category, dimensions and
`indicative_unit_cost` — the cost formatted to two decimals so prompts are
byte-stable across runs.

**Forbidden in the answer:** prices, costs, currency amounts, widths/depths, and
positions/coordinates. `FurnitureRecommendation` has no price or dimension
field, and the schemas use `extra="forbid"`, so such an attempt fails validation
and triggers the correction. A test asserts the subtotal is still the catalog
figure after such an attempt.

**Pricing:** performed by `core.budget_engine.compute_budget` from the local
catalog. No figure from the model enters the total.

### 4.4 `evaluate_design(..., recommendations, spatial, analysis, catalog, budget_is_complete=True)`

Returns `DesignEvaluation`.

Receives finished deterministic results and interprets them:

- `_spatial_block()` — `is_valid`, blocking boundary violations, blocking
  overlaps, warnings, straight from `SpatialValidation`.
- `_budget_block()` — currency, subtotal, materials, other expenses, total,
  remaining, `is_over_budget`, plus an explicit `is_complete` flag.
- `_recommendation_block()` — item names and categories read from the local
  catalog, never from the model. An unresolved id appears as
  `"(not in catalog)"`.

**Contract rules:** the CALCULATED RESULTS section "is correct by construction";
never recalculate, never contradict, may quote exactly. If blocking problems
exist the design "is not buildable as it stands". If the budget is incomplete,
the total must not be described as final. It must not propose a different
concept.

**Why `budget_is_complete` exists:** a partial sum must never be handed to the
evaluator as if it were the project cost.

---

## 5. Prompt Architecture

```
                 ┌──────────────────────────────┐
                 │        PromptSpec            │
                 │  system   role + OUTPUT_RULES│
                 │  context  validated inputs   │
                 │  contract required JSON shape│
                 └──────────────┬───────────────┘
                                │
        messages()              │            correction_messages(error)
   [system, context+contract]   │      [system, context + reason + contract]
                                ▼
                    run_structured_request()
                       │            │
             ai.client.complete  ai.parsing.parse_with_correction
                       │            │
                       └──► validated Pydantic model
```

**Design decisions:**

- **One flow, four services.** Duplicating the request/correction sequence in
  four modules would allow them to drift; `ai/prompt.py` owns it once.
- **Context is reusable.** A correction re-sends the identical context, so the
  model repairs against the same facts instead of starting over.
- **The previous answer is never echoed.** It is untrusted text, can be
  thousands of tokens, and a correction needs the diagnosis plus the contract —
  not the broken output. A test (`test_correction_messages_do_not_echo_the_previous_answer`)
  guards this.
- **Diagnosis is content-free.** `error.original_reason` from `ai.parsing`
  describes the defect (missing field, wrong type) without reproducing
  provider output, so nothing untrusted or secret reaches a log or a prompt.
- **`OUTPUT_RULES` is repeated in every prompt** because a model has no memory
  between calls: one JSON object, no prose or fences, only contracted keys,
  never invent catalog items/prices/dimensions, never perform arithmetic,
  plain sentences in text fields.
- **`_jsonable` + `json_block`** convert models, enums and `Decimal` to stable
  JSON. Decimals become strings: a float would silently round money on the way
  into a prompt.
- **Temperature 0.0** for every operation; determinism is preferred over
  variety, and the three concepts supply the variation.
- **Prompts contain no credential.** A parametrised test asserts the key never
  appears in any prompt for any of the four services.

---

## 6. Catalog Validation Approach

The split is deliberate: **the model proposes, Python decides.**

```
DesignRecommendation.furniture      (model output, ids only)
            │
            ▼
verify_catalog_references()          ai/design_advisor.py
            │
            ▼
core.validation.validate_catalog_references()   ← the Phase 3 rule, reused
            │
            ▼
CatalogCheck.findings  →  codes: unknown_catalog_item / unsupported_room_type
```

- **Reuse, not reimplementation.** `verify_catalog_references` calls the Phase 3
  function directly, so codes and wording are identical everywhere and a test
  asserts the code sequence matches exactly.
- **Room-type support is checked**, not just existence. `wardrobe` in a living
  room yields `unsupported_room_type`.
- **Dimensions and costs come from `data/furniture_catalog.json` only.** The
  advisor has no code path that reads a number from the model.
- **No substitution.** An unknown id stays in the returned recommendation so the
  UI can show what was proposed. A test asserts `sofa_three_seat` is *not*
  inserted in place of a hallucinated id.
- **Not part of the correction loop.** Catalog facts are Python's to arbitrate;
  asking the provider to "fix" an id would let it re-guess and could mask a bad
  prompt. Validation runs afterwards and reports.
- **Failure does not raise.** A bad reference is a finding, so the interface can
  display the proposal and its defect together.
- **`AdvisorResult.is_usable` requires both** `catalog_check.is_valid` **and**
  `budget.is_trustworthy`. An unknown item makes `compute_budget` emit
  `unpriced_item`, so the total is a partial sum — and calling a partial sum
  "the total" would misstate the basket. `priced` is documented as valid only
  when `is_usable` is true.

---

## 7. Token Limits

| Function | `max_tokens` | Rationale |
|---|---:|---|
| Brief Analyzer | 2000 | One summary plus four short lists |
| Concept Generator | 6000 | Three full concepts, each with seven text fields |
| Furniture Advisor | 4000 | Up to 20 catalog references plus up to 12 materials |
| Design Evaluator | 3000 | Four narrative assessments plus two lists |

- These are **application limits**, not verified provider maxima. No provider
  ceiling or context window has been measured (see §9).
- `finish_reason=length` → `AITruncatedResponseError`, surfaced unchanged.
- **No automatic token increase.** **No unbounded retry.** Each operation makes
  at most two requests: the original and one correction.

---

## 8. Error Handling

| Situation | Behaviour | Correction attempted? |
|---|---|---|
| Valid answer | Model returned | — |
| Not JSON / empty / fenced-and-unrepairable | `AIStructuredOutputError` (internal), one correction | Yes, exactly once |
| Pydantic failure | Same path | Yes, exactly once |
| Correction also invalid | `AICorrectionFailedError` carrying both reasons | No further attempt |
| Timeout | `AITimeoutError` | **No** |
| Authentication rejected | `AIAuthenticationError` | **No** |
| Rate limited | `AIRateLimitError` | **No** |
| `finish_reason=length` | `AITruncatedResponseError` | **No** |
| Transport failure *during* the correction | The transport error itself, unwrapped | No further attempt |
| Catalog reference invalid | `CatalogCheck` findings + `is_usable == False` | **No** (by design) |

**Fixed in this step:** previously a timeout during the correction was wrapped
in `AICorrectionFailedError`, which would have reported a network fault as a bad
answer. `ai/parsing.py` now re-raises `AIError` unchanged, and two tests cover
timeout and truncation during repair.

**No fabricated success anywhere:** no default brief, no placeholder concepts, no
empty recommendation, no zero total. A failed call raises; the caller decides
what to show.

---

## 9. Known Limitations

1. **No live API call in this step.** All four services are verified only
   against injected fake completers. Real prompt behaviour, real JSON
   compliance, and the true `max_tokens` headroom for the Concept Generator are
   unverified. Step 2 proved the endpoint, model name, `response_format`, and
   basic completion work; it did not exercise these four prompts.
2. **Concept generation is the most truncation-prone operation.** 6000 tokens
   for three seven-field concepts is plausible but unmeasured. If it truncates
   live, the correct fix is a deliberate prompt/limit revision with approval —
   not an automatic increase. The error is already explicit.
3. **Provider limits remain unverified:** exact `temperature`/`max_tokens`
   ranges, context window, output ceiling, rate-limit behaviour, and the live
   shape of 401/429/5xx responses.
4. **Correction success is untested against the real model.** That a real model
   repairs a malformed answer when told the reason is an assumption; only the
   plumbing is proven.
5. **Materials have no price list in V1.** `MaterialRecommendation` therefore
   carries no cost field, and the budget's `material_subtotal` stays at the
   value `compute_budget` produces from its own inputs. Materials are described,
   never priced.
6. **No spatial reasoning from AI, and none attempted.** `AdvisorResult` has no
   spatial field at all; the caller must run `core.spatial_engine` separately.
   A test asserts the attribute does not exist.
7. **Furniture placement is not assigned by AI.** `position_x_cm` /
   `position_y_cm` exist on `FurnitureRecommendation` as optional data from
   Phase 1. The advisor prompt forbids assigning positions, and the advisor
   never runs geometry; a test confirms a model-supplied position does not
   affect pricing.
8. **`DesignEvaluation` severity is not modelled.** The evaluator returns
   narrative fields and two lists; it does not emit structured severity codes.
   Displaying and gating on findings remains the workflow layer's job.
9. **Prompt size grows with catalog size.** The advisor sends every
   room-type-compatible entry. At 20 items this is small; a much larger catalog
   would need a shortlist step, which is out of V1 scope.
10. **`models/schemas.py:228` has a pre-existing line over 88 characters.** It
    predates this step and was not touched.
11. **No UI wiring yet.** Nothing in `app.py` calls these functions; the landing
    page still renders as in Phase 1. Phase 5 owns the workflow.

---

## 10. Scope Compliance

| Constraint | Status |
|---|---|
| No new dependency | No change to `requirements.txt` or `.venv` |
| `requirements.txt` unchanged | Yes |
| `opencode.json` unchanged | Yes |
| Existing Pydantic models unchanged | Yes — only two new classes added |
| No Streamlit in `ai/*` | Asserted by tests for all five AI modules |
| HTTP only in `ai/client.py` | Asserted by tests for `ai/prompt.py` and the services |
| No Streamlit UI work | Yes |
| No 2D plan, no PDF | Yes |
| No database, no accounts | Yes |
| No Git, commit, push, deploy | Yes — the directory is not a Git repository |
| No Phase 5 work started | Yes |
| No live API call | Yes |
| Credentials in no project file | Verified — 0 matches for the real key |

---

## 11. Deviations and Decisions Requiring Note

1. **Two models were added to `models/schemas.py`.** `TECHNICAL_ARCHITECTURE.md`
   §3.3-C requires material recommendations, but no existing model could hold
   them, and adding a field to `DesignConcept` or `DesignEvaluation` would have
   changed the workflow contract. Two additive classes were the smallest
   change. No existing model was modified.
2. **`MaterialRecommendation` has no cost field.** V1 has no material price
   list; a cost field would invite the model to invent a number that would then
   look like catalog data.
3. **`AdvisorResult` holds the whole `BudgetResult`, not just
   `BudgetAnalysis`.** Storing only the analysis discarded `is_trustworthy`, so
   a partial total could have been shown as the final one.
4. **Catalog validation is excluded from the correction loop** — see §6. This
   interprets "no substitution" and "Python owns catalog facts" strictly.
5. **`ai/parsing.py` was modified** (one `except AIError: raise` branch). This
   is a bug fix required by the step's own error-classification rules, not a
   feature change.

---

## 12. Recommended Next Action

Review this step. If approved, Phase 5 (Application Workflow) can begin by
composing the four services into the Streamlit workflow, which is the first
place these modules are called with real inputs.
