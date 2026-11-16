# Phase 5 / Step 3 — Test Report

**Project:** Hometsy — Room Intelligence Studio
**Phase:** 5 — Complete Application Workflow
**Step:** 3 — AI Readiness & Live Provider Validation
**Date:** 2026-11-15
**Environment:** Windows, `.venv` Python 3.13.18
**Provider:** `deepseek-ai/deepseek-v4.1-flash-1017` via `https://api-cdn.deploy.com/api/v1`

---

## 1. Summary

| Suite | Result |
|---|---|
| Full `pytest` suite | **801 passed, 0 failed, 0 skipped, 0 errors** in 10.07 s |
| Live provider validation | **4 of 4 services succeeded** (Test 3 after one fix) |
| AI-free Streamlit flow | 32 passed |
| Secret leakage scan | No key found in any project file or report |

One real defect was found and fixed: the advisor's output token cap was too small
for this model's reasoning-token overhead. Details in §4.

---

## 2. Commands executed and real results

### 2.1 Full suite (after the fix)

```
cd "[PROJECT_ROOT]"
& ".venv\Scripts\python.exe" -m pytest -q
```

```
........................................................................ [  8%]
........................................................................ [ 17%]
........................................................................ [ 26%]
........................................................................ [ 35%]
........................................................................ [ 44%]
........................................................................ [ 53%]
........................................................................ [ 62%]
........................................................................ [ 71%]
........................................................................ [ 80%]
........................................................................ [ 89%]
........................................................................ [ 98%]
.........                                                                [100%]
801 passed in 10.07s
```

- Tests collected: 801
- Passed: 801
- Failed: 0
- Skipped: 0
- Errors: 0

Baseline before this step was also 801, so the change added no tests and removed
none. Two existing assertions were updated to the corrected constants; no test
was weakened, skipped, deleted or made conditional.

### 2.2 AI-free Streamlit flow

```
& ".venv\Scripts\python.exe" -m pytest tests/test_ui_app.py -q
```

```
32 passed in 6.88s
```

This confirms the Step 3 change did not disturb the interface layer. It is
expected to be unaffected: `ui/` imports no AI module.

### 2.3 Per-file suite composition (unchanged)

| File | Tests |
|---|---|
| `test_ai_client.py` | 58 |
| `test_ai_config.py` | 30 |
| `test_ai_parsing.py` | 112 |
| `test_ai_prompt.py` | 38 |
| `test_ai_services.py` | 70 |
| `test_budget_engine.py` | 34 |
| `test_data_library.py` | 34 |
| `test_models.py` | 54 |
| `test_room_engine.py` | 48 |
| `test_spatial_engine.py` | 45 |
| `test_ui_app.py` | 32 |
| `test_ui_commits.py` | 40 |
| `test_ui_presentation.py` | 22 |
| `test_ui_session.py` | 22 |
| `test_validation.py` | 35 |
| `test_workflow_dependencies.py` | 35 |
| `test_workflow_integration.py` | 9 |
| `test_workflow_state.py` | 83 |
| **Total** | **801** |

No test in the suite requires a live API key. The live validation of this step
was performed by a temporary harness outside the repository, deliberately kept
out of `tests/` so the suite stays offline and deterministic.

---

## 3. Automated test changes

Two assertions in `tests/test_ai_services.py` were updated because the constants
they pin changed:

| Test | Before | After |
|---|---|---|
| `test_application_token_limits_match_the_approved_values` | advisor 4000, evaluator 3000 | advisor 8000, evaluator 8000 |
| `test_each_service_uses_its_own_limit` (parametrised) | `("advisor", 4000)`, `("evaluator", 3000)` | `("advisor", 8000)`, `("evaluator", 8000)` |

Both tests still assert the same property as before — that each service uses its
own documented limit and that those limits equal the module constants. The brief
(2000) and concept (6000) assertions are untouched.

A comment was added above the first test recording why the two limits were
raised, so a future reader does not treat 8000 as arbitrary.

---

## 4. Live validation — per-service results

Every call below went to the real provider. No `completer` fake was used. No
test injected a canned response.

### 4.1 Test 1 — `analyze_brief`

| Field | Value |
|---|---|
| Status | **PASS** |
| HTTP | 200 |
| Latency | 12.57 s |
| Prompt tokens | 789 |
| Completion tokens | 1707 |
| Total tokens | 2496 |
| Cap | 2000 |
| `finish_reason` | `stop` |
| Correction calls | 0 |
| Parsed shape | `DesignBrief` |
| Pydantic validation | Passed, first attempt |
| JSON validity | Passed, first attempt |

Content verdict: coherent and faithful to the inputs. Six functional priorities,
ten constraints, ten ambiguities, eight warnings. No fabricated measurement, no
arithmetic, no change to the room, budget or stated preferences.

### 4.2 Test 2 — `generate_concepts`

| Field | Value |
|---|---|
| Status | **PASS** |
| HTTP | 200 |
| Latency | 9.26 s |
| Prompt tokens | 1513 |
| Completion tokens | 1286 |
| Total tokens | 2799 |
| Cap | 6000 |
| `finish_reason` | `stop` — not truncated |
| Correction calls | 0 |
| Parsed shape | `ConceptCollection` |
| Pydantic validation | Passed, first attempt (count + distinct-name validators) |
| JSON validity | Passed, first attempt |

Content verdict: exactly 3 concepts with 3 distinct names, substantively
different, all consistent with the room, style, palette and budget.

Distinctness evidence — pairwise Jaccard similarity of the narrative fields:

| Pair | Similarity |
|---|---|
| Low Horizon ↔ Window Bench Reading Nook | 0.304 |
| Low Horizon ↔ Slim Shelf Spine | 0.271 |
| Window Bench Reading Nook ↔ Slim Shelf Spine | 0.312 |

Low overlap for natural-language interiors prose. The three organising ideas are
structurally different, not adjective swaps.

Token headroom: 1286 of 6000 used (21%). The truncation risk flagged in the
Phase 5 Step 2 handover did not occur.

### 4.3 Test 3 — `recommend_furniture`

**First attempt: FAIL. Second attempt after the fix: PASS.**

#### Attempt 1 — cap 4000

| Field | Value |
|---|---|
| Status | **FAIL** |
| Failure class | `AITruncatedResponseError` |
| Category | `truncated_response` |
| `finish_reason` | `length` |
| Latency | 23.47 s |
| Correction calls | 0 — correct, truncation must not be corrected |
| Downstream stages | Not run (dependency rule respected) |

#### Attempt 2 — cap 8000, after the approved fix

| Field | Value |
|---|---|
| Status | **PASS** |
| HTTP | 200 |
| Latency | 25.33 s |
| Prompt tokens | 2806 |
| Completion tokens | 4414 |
| Total tokens | 7220 |
| Cap | 8000 |
| `finish_reason` | `stop` — not truncated |
| Correction calls | 0 |
| Parsed shape | `DesignRecommendation` |
| Pydantic validation | Passed, first attempt |
| JSON validity | Passed, first attempt |

Content verdict:

| Check | Result |
|---|---|
| Catalog IDs used | `sofa_two_seat`, `armchair` ×2, `sideboard`, `rug_large`, `floor_lamp`, `side_table`, `plant_large` |
| Unknown IDs | **none** |
| Duplicate IDs | none |
| Room-type compatible | 7 of 7 |
| `catalog_check.is_valid` | **True**, no messages |
| `budget.is_trustworthy` | **True**, no line errors |
| Furniture subtotal | 48,600.00 TRY |
| Total estimated | 48,600.00 TRY |
| Remaining | 36,400.00 TRY |
| `is_over_budget` | False |
| Budget usage | 57.2% |
| Price/cost claims in text | **none** (regex scan, 0 matches) |
| Geometry claims | none — all `position_x_cm` / `position_y_cm` are `null`, all rotations 0 |
| Materials | 6, all schema-conforming, no cost field exists to populate |

The advisor respected every boundary: it selected from the catalog, explained
why, refused to price, refused to place, and invented no identifier. Python
remained the sole owner of pricing and geometry.

#### Root cause of the failure (measured)

Two diagnostic probes were run before any code changed.

**Probe A** — real advisor prompt, `max_tokens = 64`:

```
finish_reason          : length
prompt_tokens          : 2140   (unchanged by the cap)
completion_tokens      : 64     (pinned exactly at the cap)
total_tokens           : 2204
reasoning_tokens       : 66
content chars          : 0
```

Conclusion: `max_tokens` is an **output-only** budget.

**Probe B** — real advisor prompt, generous cap:

```
finish_reason          : stop
completion_tokens      : 3007
reasoning_tokens       : 2100     (~70% of output)
content chars          : 3620
schema valid           : True
catalog valid          : True
budget trustworthy     : True
```

Conclusion: reasoning tokens are charged against the output budget and consumed
~2100 of it, leaving only ~900 for JSON. A 4000 cap therefore reserves roughly
1900 tokens for JSON — insufficient, since the live answer needed 4414 total
output tokens.

The prompt, contract, schema, catalog filter and budget engine were all proven
correct by Probe B and by the successful second attempt. Only the cap was wrong.

#### Fix applied

| File | Before | After |
|---|---|---|
| `ai/design_advisor.py` | `MAX_TOKENS = 4000` | `MAX_TOKENS = 8000` |
| `ai/design_evaluator.py` | `MAX_TOKENS = 3000` | `MAX_TOKENS = 8000` |

The evaluator was raised in the same change because it faced the identical
exposure (a 3000 cap against the same reasoning overhead) and would very likely
have truncated next. This was reported and approved before the edit.

### 4.4 Test 4 — `evaluate_design`

| Field | Value |
|---|---|
| Status | **PASS** |
| HTTP | 200 |
| Latency | 9.36 s |
| Prompt tokens | 2358 |
| Completion tokens | 1229 |
| Total tokens | 3587 |
| Cap | 8000 |
| `finish_reason` | `stop` — not truncated |
| Correction calls | 0 |
| Parsed shape | `DesignEvaluation` |
| Pydantic validation | Passed first attempt, and re-validated independently after the run |
| JSON validity | Passed, first attempt |

Content verdict:

| Check | Result |
|---|---|
| Consistent with the brief | Yes — addresses all four functional requirements individually |
| Spatial result interpreted correctly | **Yes** — see below |
| Budget result interpreted correctly | **Yes** — see below |
| Narrative lengths | 573 / 436 / 607 / 370 chars, all within 2000 |
| Limitations | 10 (contract max 10) |
| Recommendations | 8 |
| Invented measurements / catalog items | none |

**Spatial interpretation.** The deterministic result was `is_valid = True` with
seven `unplaced_item` warnings, because the advisor returned no coordinates. The
evaluator did **not** treat `is_valid = True` as "the layout is verified". It
wrote that the layout "cannot be confirmed as workable", that "no overlaps or
boundary conflicts were checked", and listed missing placement coordinates as its
first limitation. Treating a warning-only result as unverified is the correct
reading.

**Budget interpretation.** Quoted exactly, unchanged:

| Figure | Python value | Quoted by evaluator |
|---|---|---|
| Total | 48,600.00 TRY | 48600.00 TRY ✓ |
| Limit | 85,000.00 TRY | 85000.00 TRY ✓ |
| Remaining | 36,400.00 TRY | 36400.00 TRY ✓ |

It also correctly observed that `material_subtotal` is 0.00 and concluded that no
spend is allocated to textiles or lighting — a real V1 limitation, surfaced
rather than hidden. No recalculation, no re-rounding, no contradiction.

---

## 5. Failure-mode checklist

Every category the step brief asked to report separately:

| Failure mode | Occurred | Evidence |
|---|---|---|
| Authentication error | No | No 401/403 |
| Rate limit | No | No 429 |
| Timeout | No | Max latency 25.33 s vs 60 s timeout |
| Network error | No | No connection failure |
| Invalid JSON | No | 4/4 parsed on first attempt |
| Schema validation error | No | 4/4 validated on first attempt |
| **Truncated response** | **Yes, once** | Test 3 attempt 1, `finish_reason=length` at 4000. Fixed; clean at 8000 |
| Invalid catalog reference | No | 7/7 real, 0 unknown, 0 duplicates |
| Concept count mismatch | No | Exactly 3, distinct names |
| Budget trustworthiness failure | No | `is_trustworthy=True`, `is_usable` not triggered |

---

## 6. API consumption

Seven requests total; no speculative calls, no retry loops, no deliberate
malformed responses.

| # | Request | Attempts | Tokens | Note |
|---|---|---|---|---|
| 1 | Brief analysis | 1 | 2496 | Test 1 |
| 2 | Concept generation | 1 | 2799 | Test 2 |
| 3 | Advisor @ 4000 | 1 | n/a | Truncated; provider returned no usage |
| 4 | Probe @ 64 | 1 | 2204 | Diagnosis: output-only cap |
| 5 | Probe @ 8000 | 1 | 5813 | Diagnosis: real output requirement |
| 6 | Advisor @ 8000 | 1 | 7220 | Test 3 |
| 7 | Evaluation @ 8000 | 1 | 3587 | Test 4 |

Total recorded: **24,119 tokens** across the five requests that reported usage.

Requests 4 and 5 were diagnostics rather than re-runs: they were required to
prove the fault was the cap and not the prompt before changing approved code.
Tests 1 and 2 were **not** re-sent after the fix; their recorded output was
reloaded and reused.

Correction calls across the whole step: **0**.

---

## 7. Secret hygiene verification

### 7.1 Key absent from all project files

A scan of 68 project files across `ai/`, `core/`, `models/`, `ui/`, `workflow/`,
`tests/`, `data/`, `reports/`, `assets/`, plus `app.py`, `pytest.ini`,
`requirements.txt`, `.env.example` and `.gitignore`:

```
files scanned: 68
exact-key hits: []
key length: 24   (length only; value never printed)
```

Result: the `DEPLOY_API_KEY` value appears in **no** project file.

### 7.2 No token-shaped strings in reports

A regex scan of every `reports/**/*.md` for `sk-`-prefixed key strings and for
authorization-header style token strings:

```
suspicious token-like strings in reports: []
```

### 7.3 Handling discipline

- The key was read only via `load_config()` from the process environment.
- It was never printed, logged, written to a file, or included in a report.
- The live harness lives outside the repository, in the system temp directory.
- Diagnostic probe scripts printed only token counts and character lengths —
  never the credential, never a request header.
- No real user data was used; the scenario is synthetic.

---

## 8. Verification that the AI-free Streamlit flow still works

`tests/test_ui_app.py` — 32 passed. This suite drives `app.py` through Streamlit
`AppTest` and covers the room form, the preferences form, navigation, validation
messaging and session state. It does not touch the network.

The change in this step is two integer constants inside `ai/`. `ui/` and
`app.py` import no AI module by design (`app.py` is a router that never imports
`ai`), so the interface path is structurally unaffected — and the passing suite
confirms it in practice.

---

## 9. Known limitations of this test run

1. **The geometric path was not exercised with live data.** The advisor returns
   no coordinates, so the spatial engine produced seven `unplaced_item` warnings
   and no boundary, overlap or clearance rule was actually triggered. Phase 6
   owns placement.
2. **Single scenario, single run.** One 20.0 m² Japandi living room. Other room
   types, styles, palettes and unusually long answers remain unmeasured at 8000.
3. **The correction path was not exercised live.** It remains covered only by
   mocked tests; deliberately provoking it was out of scope.
4. **Materials are unpriced in V1**, so the budget total covers furniture only.
5. **Reasoning tokens are not modelled** in `ChatCompletion`; the application
   cannot display the reasoning share without a schema change.
6. **Live calls are not part of the automated suite**, by design, so CI cannot
   detect a future provider-side truncation regression.

---

## 10. Conclusion

All four AI services produce real, valid, schema-conforming, business-consistent
output on the live provider. One genuine defect existed — an output token cap too
small for the model's reasoning overhead — and it was diagnosed by measurement,
fixed with a two-constant change, and re-verified live. The suite remains green
at 801 passing tests, and no credential reached any file.
