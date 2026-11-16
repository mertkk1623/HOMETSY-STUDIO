# Phase 5 / Step 3 — Completion Report

**Project:** Hometsy — Room Intelligence Studio
**Phase:** 5 — Complete Application Workflow
**Step:** 3 — AI Readiness & Live Provider Validation
**Date:** 2026-11-15
**Status:** Live validation complete for all four services; one defect found and
fixed; awaiting approval.

---

## 1. Objective

Prove that the four AI operations work against the real provider — not merely
that they return HTTP 200, but that each real answer is valid JSON, satisfies its
Pydantic model, is usable content, and respects the business rules that Python
owns.

The four operations:

1. `ai.brief_analyzer.analyze_brief`
2. `ai.concept_generator.generate_concepts`
3. `ai.design_advisor.recommend_furniture`
4. `ai.design_evaluator.evaluate_design`

---

## 2. Approach

### 2.1 Code review before any live call

The following were read before the provider was contacted, so no field name,
enum value, token limit or error category in this report is guessed:

| Area | Files |
|---|---|
| Approved documentation | `AGENTS.md`, `PROJECT_BRIEF.md`, `TECHNICAL_ARCHITECTURE.md`, `DEVELOPMENT_PLAN.md`, `reports/phase-4-step-5/*`, `reports/phase-5-step-2/*` |
| AI layer | `ai/config.py`, `ai/client.py`, `ai/parsing.py`, `ai/prompt.py`, `ai/brief_analyzer.py`, `ai/concept_generator.py`, `ai/design_advisor.py`, `ai/design_evaluator.py`, `ai/__init__.py` |
| Models | `models/schemas.py`, `models/__init__.py` |
| Core engines | `core/room_engine.py`, `core/spatial_engine.py`, `core/budget_engine.py`, `core/validation.py` |
| Data | `data/furniture_catalog.json` (20 items, 11 usable for a Living Room) |
| Tests | `tests/conftest.py` fixtures |

Confirmed from the code, not assumed:

- `complete()` returns a `ChatCompletion` carrying `finish_reason` and
  `prompt_tokens` / `completion_tokens` / `total_tokens`.
- Correction is exactly one extra request, issued only for an unparseable or
  schema-invalid answer. Transport failures (timeout, auth, rate limit,
  truncation) never trigger a correction.
- `AdvisorResult.is_usable` requires **both** a valid catalog check and
  `budget.is_trustworthy`.
- `verify_catalog_references` delegates to `core.validation.validate_catalog_references`,
  so the AI layer cannot invent a second catalog rule.

### 2.2 One identical scenario through all four services

Derived from the real models — `RoomType`, `Wall`, `DesignStyle`,
`PaletteDirection`, `OpeningInput`, `Money` — never typed from memory.

| Field | Value |
|---|---|
| Room type | `RoomType.LIVING_ROOM` |
| Name | `Living Room` |
| Dimensions | 400 × 500 cm (20.0 m²) |
| Ceiling | 270 cm |
| Door | `Wall.SOUTH`, offset 60 cm, width 90 cm |
| Window | `Wall.NORTH`, offset 120 cm, width 160 cm |
| Style | `DesignStyle.JAPANDI` |
| Palette | `PaletteDirection.NATURAL_MATERIALS` |
| Material preferences | oak, linen, wool, matte clay |
| Requirements | Seating for four; reading corner near the window; storage for books and media |
| Notes | Two adults, two children; keep the window side open; avoid a heavy, dark look |
| Budget | `85000.00` TRY |
| Catalog | 11 items support a Living Room |

The budget is deliberately consistent with the catalog: the eleven Living Room
items total 76,700.00 TRY, so 85,000.00 is a realistic ceiling that still leaves
the advisor a genuine choice, and an over-budget result would be a design
decision rather than an impossible constraint.

### 2.3 Test order

Brief → Concepts (using Test 1's real brief) → Recommendations (using Test 2's
first real concept) → Evaluation (using the real recommendations, the real
spatial result and the real budget result). Each stage consumed the previous
stage's actual output, and a failure in one stage stopped everything downstream.

---

## 3. Results per function

### 3.1 Test 1 — `analyze_brief`

**Success.**

| Measure | Value |
|---|---|
| Latency | 12.57 s |
| Prompt tokens | 789 |
| Completion tokens | 1707 |
| Total tokens | 2496 |
| Token cap | 2000 |
| `finish_reason` | `stop` |
| Correction calls | 0 (parsed on the first attempt) |
| HTTP | 200 |

Content checks:

- Valid JSON, validated into `DesignBrief` on the first attempt.
- Summary is coherent and restates the supplied facts correctly: 20.0 m²,
  Japandi, natural materials, seating for four, reading corner at the north
  window, book/media storage, 85,000.00 TRY.
- Six functional priorities, ten constraints, ten ambiguities, eight warnings —
  all within the contract's limits (`LongText` 2000, `ShortText` 200 per item,
  10 items per list).
- It reinterpreted nothing it was forbidden to change: the room, budget and
  stated preferences are repeated as given.
- Warnings are genuine risks rather than invented rules, and the tight-budget
  warning is defensible against a 76,700.00 TRY catalog floor.
- No arithmetic was performed by the model; the floor area it quotes is the
  value Python supplied in `room_facts`.

### 3.2 Test 2 — `generate_concepts`

**Success.**

| Measure | Value |
|---|---|
| Latency | 9.26 s |
| Prompt tokens | 1513 |
| Completion tokens | 1286 |
| Total tokens | 2799 |
| Token cap | 6000 |
| `finish_reason` | `stop` (not truncated) |
| Correction calls | 0 |
| HTTP | 200 |

Content checks:

- Exactly **3** concepts, conforming to `ConceptCollection`'s
  `min_length = max_length = REQUIRED_CONCEPT_COUNT` and its distinct-name
  validator.
- 3 distinct names: *Low Horizon*, *Window Bench Reading Nook*, *Slim Shelf
  Spine*.
- Meaningfully different, not three renamings of one idea. Pairwise Jaccard
  overlap of the narrative fields is 0.304 / 0.271 / 0.312 — low similarity. The
  organising ideas genuinely differ: (1) low seating pulled to the edges, (2) the
  window wall itself becomes a built-in reading bench, (3) storage concentrated
  on one spine wall with symmetrical seating.
- All three are consistent with the room, the 20.0 m² area, the north window and
  the south door, and all three use the natural-materials vocabulary.
- All field lengths within contract. Descriptions 364 / 390 / 414 characters
  (`LongText` limit 2000); names 11 / 25 / 16 characters (limit 80).
- No price, total or currency claim in any concept — verified by regex scan,
  zero matches. The model described budget fit qualitatively instead of
  inventing arithmetic, which is the required behaviour.
- 1286 of 6000 tokens used, so the 6000 cap had ample headroom. The truncation
  risk flagged in the Phase 5 Step 2 handover did **not** materialise.

Observation (not a failure): none of the three concepts uses the literal string
"Japandi"; the style is expressed through oak, linen, wool, matte clay and low
proportions instead. That matches the contract ("keep the chosen style and
palette recognisable"), which asks for recognisability rather than a keyword.

### 3.3 Test 3 — `recommend_furniture`

**Failed on the first attempt, then succeeded after a fix.** This is the one real
defect found in this step.

First attempt (concept *Low Horizon*, cap 4000):

| Measure | Value |
|---|---|
| Latency | 23.47 s |
| Token cap | 4000 |
| Failure | `AITruncatedResponseError` (`category = "truncated_response"`) |
| `finish_reason` | `length` |
| Correction calls | 0 — correctly, because truncation is a transport-shaped failure, not a schema failure |

Second attempt (same concept, same prompt, cap 8000):

| Measure | Value |
|---|---|
| Latency | 25.33 s |
| Prompt tokens | 2806 |
| Completion tokens | **4414** |
| Total tokens | 7220 |
| Token cap | 8000 |
| `finish_reason` | `stop` |
| Correction calls | 0 |
| HTTP | 200 |

The 4414 completion tokens explain the failure exactly: the old 4000 cap was
below what this answer actually needs, so it could never have succeeded.

Content checks on the successful answer:

- Valid JSON, validated into `DesignRecommendation` on the first attempt.
- **7 furniture references, every one a real catalog ID**: `sofa_two_seat`,
  `armchair` (×2), `sideboard`, `rug_large`, `floor_lamp`, `side_table`,
  `plant_large`.
- **Zero unknown identifiers**, zero duplicates, and every ID supports
  `Living Room`. `verify_catalog_references` returned `is_valid = True` with an
  empty message list.
- Quantities 1–2, all rotations 0 and all positions `null` — the advisor
  correctly refused to place furniture, leaving geometry to Python.
- 6 materials, each conforming to `MaterialRecommendation` with `name`,
  `category`, `color_direction`, `rationale`, `quantity_note` and **no cost
  field**, so no invented price can reach the budget engine.
- **No price, cost, total or currency claim anywhere** in the rationale fields —
  regex scan returned zero matches. The model did not do the financial
  arithmetic.
- Budget remained Python-owned and preserved:
  `compute_budget` produced furniture_subtotal 48,600.00, total 48,600.00,
  remaining 36,400.00, `is_over_budget = False`, usage 57.2%, and
  `is_trustworthy = True` with no line errors.
- Recommendations are appropriate to the room and concept: seating for four
  (2-seat sofa + 2 armchairs), one quiet storage volume for books and media, a
  reading-corner chair pairing (armchair + floor lamp + side table), and the
  textile/plant layer the natural-materials palette asks for.

### 3.4 Test 4 — `evaluate_design`

**Success.**

| Measure | Value |
|---|---|
| Latency | 9.36 s |
| Prompt tokens | 2358 |
| Completion tokens | 1229 |
| Total tokens | 3587 |
| Token cap | 8000 |
| `finish_reason` | `stop` (not truncated) |
| Correction calls | 0 |
| HTTP | 200 |

Content checks:

- Valid JSON, validated into `DesignEvaluation` on the first attempt, and
  re-validated independently after the run.
- All four narrative fields present and non-empty (573 / 436 / 607 / 370
  characters, within `LongText`); 10 limitations and 8 recommendations, at the
  allowed maximum of 10 and within `ShortText`.
- **Consistent with the brief**: it tracks the four functional requirements
  (seating for four, reading corner, storage, window side open) one by one, and
  it uses the Japandi / natural-materials vocabulary from the brief rather than
  inventing a different direction.
- **Spatial result used correctly, including its honest limitations.** The
  spatial engine reported `is_valid = True` with seven `unplaced_item` warnings,
  because the advisor returned no coordinates. The evaluation did not read
  `is_valid = True` as "the layout works". It stated plainly that the layout
  "cannot be confirmed as workable", that no overlaps or boundary conflicts were
  checked, and listed "No item has placement coordinates, so the layout was not
  spatially validated" as its first limitation. That is the correct
  interpretation of a warning-only result, and it is the behaviour the
  deterministic-first design depends on.
- **Budget result used correctly.** It quoted 48,600.00 TRY total against the
  85,000.00 TRY limit with 36,400.00 TRY remaining, marked complete and within
  budget — all three figures match the Python output exactly, unaltered. It did
  not recompute, re-round or contradict them.
- It noticed that `material_subtotal` is 0.00 and drew the right conclusion: no
  spend is allocated to curtains, textiles or extra lighting. That is a genuine
  limitation of V1 (materials carry no catalog price), correctly surfaced rather
  than papered over.
- It did not invent measurements, prices or catalog items.

---

## 4. The defect, its root cause, and the fix

### 4.1 Symptom

`recommend_furniture` returned `finish_reason = length` on the real provider at
`MAX_TOKENS = 4000`.

### 4.2 Root cause (measured, not inferred)

Two measurements were taken before any code was changed:

**Probe A — what does `max_tokens` mean here?** The real advisor prompt was sent
with `max_tokens = 64`:

```
finish_reason   : length
usage           : prompt_tokens 2140, completion_tokens 64, total_tokens 2204,
                  reasoning_tokens 66
content chars   : 0
```

`prompt_tokens` was untouched at 2140 while `completion_tokens` landed exactly on
the cap, so **`max_tokens` is an output-only budget**; the prompt is not charged
against it. The same payload also revealed `reasoning_tokens`.

**Probe B — how much output does a real answer need?** The real advisor prompt
was sent with a generous cap:

```
finish_reason   : stop
usage           : completion_tokens 3007, reasoning_tokens 2100
content chars   : 3620          (schema valid, catalog valid, budget trustworthy)
```

So of the ~3000 output tokens, **2100 were hidden reasoning** and only ~900 were
the JSON itself. The reasoning tokens share the output budget with the answer.

**Conclusion:** `MAX_TOKENS = 4000` left roughly 1,900 tokens for JSON after
reasoning overhead. The live answer (4414 completion tokens) exceeded that. The
prompt, the contract, the Pydantic schema, the catalog filter and the budget
logic were all sound — only the cap was wrong. This is the smallest possible
fault with the smallest possible fix.

`evaluate_design` at `MAX_TOKENS = 3000` carried the same exposure against the
same reasoning overhead and would very likely have truncated next.

### 4.3 Fix applied

Two constants, and the two test assertions that pin them. Nothing else.

| File | Change |
|---|---|
| `ai/design_advisor.py` | `MAX_TOKENS` 4000 → 8000, with a comment recording the measurement |
| `ai/design_evaluator.py` | `MAX_TOKENS` 3000 → 8000, cross-referencing the advisor note |
| `tests/test_ai_services.py` | `test_application_token_limits_match_the_approved_values` and the `test_each_service_uses_its_own_limit` parametrisation updated to 8000 / 8000 |

Deliberately **not** changed:

- No prompt text, no contract, no field rule.
- No AI task boundary — the advisor still does not price or place.
- No core engine (`core/*` untouched).
- No Pydantic model.
- No new dependency.
- No retry logic — the client still makes exactly one request per call.
- `analyze_brief` (2000) and `generate_concepts` (6000) untouched: both passed
  live with headroom (1707 / 1286 completion tokens).

8000 was chosen because the two measured answers peaked at 4414 completion
tokens; 8000 gives ~1.8× headroom for a longer answer on a larger room without
being an unbounded ceiling. It remains an application budget, not a provider
maximum.

This change was reported to the project owner and approved before it was made.

---

## 5. Failure modes — each reported separately

| Failure mode | Occurred? | Detail |
|---|---|---|
| Authentication error | No | No 401/403 on any call |
| Rate limit | No | No 429 |
| Timeout | No | Slowest call 25.33 s against the 60 s default timeout |
| Network error | No | No connection failure |
| Invalid JSON | No | All four answers parsed with `json.loads` on the first attempt |
| Schema validation error | No | All four validated into their Pydantic models first time |
| **Truncated response** | **Yes — once** | `recommend_furniture`, `finish_reason = length` at cap 4000. Fixed (§4). Clean on retry at 8000 |
| Invalid catalog reference | No | 7/7 IDs real, 0 unknown, 0 duplicates, all room-type compatible |
| Concept count mismatch | No | Exactly 3, distinct names |
| Budget trustworthiness failure | No | `is_trustworthy = True`, no line errors, `is_usable` not triggered |

Note on correction behaviour: **zero correction calls were made across all four
services.** Every answer parsed and validated on the first request. The single
correction path was never exercised by live traffic, and it was deliberately not
provoked with a bad answer.

---

## 6. Provider behaviour worth recording

Discovered from real responses, not documented anywhere in the project:

1. **`max_tokens` is output-only.** A 2140-token prompt with `max_tokens = 64`
   reported `prompt_tokens = 2140` unchanged.
2. **The model emits `reasoning_tokens`**, reported inside `usage`, and those
   tokens are charged against the `max_tokens` output budget. Budgeting an output
   cap for JSON alone is therefore unsafe on this model. This is the direct cause
   of the only failure in this step.
3. `usage` also carries `prompt_tokens_details`, which is `null` in every
   response observed; `_parse_usage` ignores it, which is correct.
4. Latency ranged 9.26–25.33 s. The advisor is the slowest and the largest
   consumer, consistent with the largest prompt and the most reasoning.

---

## 7. API usage actually consumed

Seven HTTP requests in total. No request was made speculatively, and no failed
call was retried in a loop.

| # | Request | Purpose | Tokens |
|---|---|---|---|
| 1 | Brief analysis | Test 1 | 2496 |
| 2 | Concept generation | Test 2 | 2799 |
| 3 | Advisor, cap 4000 | Test 3 (failed, truncated) | not returned by the provider on a truncated answer |
| 4 | Diagnostic probe, cap 64 | Establish `max_tokens` semantics | 2204 |
| 5 | Diagnostic probe, cap 8000 | Measure the advisor's real output requirement | 5813 |
| 6 | Advisor, cap 8000 | Test 3 (success) | 7220 |
| 7 | Evaluation, cap 8000 | Test 4 | 3587 |

Recorded total across requests that reported usage: **24,119 tokens**. Requests
4 and 5 were diagnostics, not re-runs of a service: they were necessary to
distinguish "the prompt is wrong" from "the cap is too small" before changing
approved code.

Token waste avoided: Tests 1 and 2 were not re-sent after the fix. Their real
outputs were reloaded from the recorded result and reused verbatim.

---

## 8. Files created or modified

### Modified (3)

| File | Change |
|---|---|
| `ai/design_advisor.py` | `MAX_TOKENS` 4000 → 8000 + explanatory comment |
| `ai/design_evaluator.py` | `MAX_TOKENS` 3000 → 8000 + explanatory comment |
| `tests/test_ai_services.py` | Two assertions updated to the new limits |

### Created (3)

| File | Purpose |
|---|---|
| `reports/phase-5-step-3/COMPLETION_REPORT.md` | This document |
| `reports/phase-5-step-3/TEST_REPORT.md` | Test execution record |
| `reports/phase-5-step-3/NEXT_SESSION.md` | Handover |

### Not modified

No change to `core/*`, `models/*`, `workflow/*`, `ui/*`, `app.py`, `data/*`,
`ai/client.py`, `ai/parsing.py`, `ai/prompt.py`, `ai/config.py`,
`ai/brief_analyzer.py` or `ai/concept_generator.py`.

The throwaway live-validation harness and the two diagnostic probes live in the
system temp directory (`C:\Users\[LOCAL_USER]\AppData\Local\Temp\opencode\`), outside
the repository, and are not part of the project.

---

## 9. Known limitations

1. **No geometry was validated live.** The advisor legitimately returns
   `position_x_cm = null`, so the spatial result was warning-only
   (`is_valid = True`, seven `unplaced_item` warnings) and no overlap, boundary
   or clearance rule was actually exercised by real advisor output. Automatic
   placement belongs to Phase 6. The evaluation handled this honestly, but this
   step did not and could not prove the geometric path against live data.
2. **Materials have no price in V1.** `material_subtotal` is 0.00, so the
   budget total covers furniture only. The evaluator correctly flagged this.
3. **One scenario, one run.** This is a single 20.0 m² Japandi living room. Other
   room types, styles and palettes, and unusually long answers, could still
   truncate at 8000.
4. **Concept 1 and the advisor disagree on one detail.** *Low Horizon* describes
   "a single lounge chair" in addition to "two lightweight chairs"; the advisor's
   basket contains a two-seat sofa and two armchairs, with no separate lounge
   chair. The evaluator caught this itself and listed it as a limitation. It is
   an inter-stage consistency issue for the workflow layer to surface, not an AI
   failure.
5. **No correction path was exercised live.** It remains covered only by mocked
   tests.
6. **Latency is not tuned.** 25.33 s for the advisor is within the 60 s timeout
   but noticeable in a Streamlit request.
7. **`reasoning_tokens` is not modelled.** `_parse_usage` reads
   `prompt_tokens` / `completion_tokens` / `total_tokens` and ignores
   `reasoning_tokens`. Correct for the current contract, but it means the
   application cannot show the reasoning share without a schema change.

---

## 10. Scope compliance

- No Streamlit AI screens were built.
- No UI design was changed.
- No Turkish localisation.
- No PDF work.
- No database, no new provider, no model change.
- No Git, no commit, no push, no deploy.
- No system shutdown, restart or sleep command was run.

---

## 11. Recommended next action

Review this report, then authorise **Phase 5 Step 4** as defined in
`DEVELOPMENT_PLAN.md`. The four AI operations are now proven against the real
provider with real, validated, business-consistent output, so the remaining
Phase 5 work is connecting them to the existing `ui/` screens through
`WorkflowState.attempt` — a layer that already exists and is tested.

Implementation is stopped here and awaiting approval.
