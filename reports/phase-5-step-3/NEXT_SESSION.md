# Phase 5 / Step 3 — Next Session Handover

**Project:** Hometsy — Room Intelligence Studio
**Written at the end of:** Phase 5 Step 3 — AI Readiness & Live Provider Validation
**Date:** 2026-11-15
**Status:** Step 3 complete. Implementation stopped, awaiting approval.

---

## 1. Read these first

In this order:

1. `PROJECT_BRIEF.md`
2. `TECHNICAL_ARCHITECTURE.md`
3. `DESIGN_SYSTEM.md`
4. `DEVELOPMENT_PLAN.md`
5. `AGENTS.md`
6. `reports/phase-5-step-3/COMPLETION_REPORT.md`
7. `reports/phase-5-step-3/TEST_REPORT.md`
8. `reports/phase-5-step-2/NEXT_SESSION.md` — still partly valid; see §6 for what changed

`AGENTS.md` §4 requires explicit approval between phases. Do not proceed on your
own.

---

## 2. What this step established

The four AI operations are **proven against the real provider**, not just in
mocked tests:

| Service | Live result | Latency | Tokens (p / c) | Correction calls |
|---|---|---|---|---|
| `analyze_brief` | PASS | 12.57 s | 789 / 1707 | 0 |
| `generate_concepts` | PASS | 9.26 s | 1513 / 1286 | 0 |
| `recommend_furniture` | PASS (after a fix) | 25.33 s | 2806 / 4414 | 0 |
| `evaluate_design` | PASS | 9.36 s | 2358 / 1229 | 0 |

All four answers were valid JSON, satisfied their Pydantic models on the first
attempt, and respected the business rules. Zero correction calls were needed.

Concretely confirmed with real data:

- The advisor used **7 real catalog IDs and invented none**, and correctly
  refused to price the basket or place the furniture.
- Python's budget engine remained authoritative: 48,600.00 TRY of 85,000.00,
  `is_trustworthy = True`.
- The evaluator quoted the calculated figures exactly and correctly refused to
  read a warning-only spatial result as a verified layout.

---

## 3. The one change made in this step

| File | Change |
|---|---|
| `ai/design_advisor.py` | `MAX_TOKENS` 4000 → 8000 |
| `ai/design_evaluator.py` | `MAX_TOKENS` 3000 → 8000 |
| `tests/test_ai_services.py` | Two assertions updated to match |

Nothing else changed. No prompt, contract, Pydantic model, core engine, workflow
module or UI file was touched.

### Why — and do not undo this

This model emits **`reasoning_tokens`**, and those are charged against the
`max_tokens` output budget alongside the JSON. Measured on the real advisor
prompt:

- `max_tokens = 64` → `prompt_tokens` 2140 untouched, `completion_tokens` pinned
  at 64. So `max_tokens` is **output-only**; the prompt is not charged.
- Generous cap → `completion_tokens` 3007, of which **2100 were reasoning**, for
  a 3620-character payload.
- The live advisor answer actually needed **4414** output tokens.

So 4000 could never have worked; ~70% of the output budget goes to hidden
reasoning. Build output caps accordingly:

**Rule of thumb: budget the output cap at roughly 2× the JSON you expect, because
reasoning consumes the rest.**

Both limits are application budgets, not provider maxima. 8000 gives ~1.8×
headroom over the largest answer observed.

---

## 4. Established project facts worth not rediscovering

1. **Run tests with the venv interpreter only:**
   `cd "[PROJECT_ROOT]"; & ".venv\Scripts\python.exe" -m pytest -q`
   Python 3.13.18 in `.venv`. The global 3.15.2 must not be used.
2. **Baseline is 801 passing tests.**
3. **`max_tokens` is output-only** on this provider. Documented nowhere upstream;
   established empirically in this step.
4. **`reasoning_tokens` appears in `usage`** and is not modelled by
   `ChatCompletion`. `_parse_usage` reads only prompt / completion / total, which
   is correct for the current contract. Adding reasoning visibility would require
   a schema change — not approved, do not do it casually.
5. **Observed latency band is 9–26 s.** The default timeout is 60 s, which is
   adequate; the advisor is the slowest and the largest consumer.
6. **The advisor legitimately returns `position_x_cm = null`.** The spatial engine
   therefore reports `unplaced_item` warnings, not errors, and `is_valid` stays
   `True`. This is expected until Phase 6 adds placement. Do not "fix" it by
   making the AI place furniture.
7. **The concept and the advisor can disagree on detail.** In this run, concept
   *Low Horizon* mentioned a separate lounge chair that the basket did not
   contain. The evaluator caught it itself. This is an inter-stage consistency
   concern for the workflow layer, not an AI bug.
8. **`DEPLOY_API_KEY` is in the process environment and nowhere else.** It is
   absent from all 68 scanned project files. Never print it, never write it, never
   put it in a report.

---

## 5. If a live provider call misbehaves again

Follow the method that worked here rather than guessing:

1. **Do not retry in a loop.** The client makes exactly one request by design.
2. **Classify first** from the exception type:
   `AITruncatedResponseError` → the cap is too small.
   `AISchemaValidationError` → the contract or the model drifted.
   `AITimeoutError` → transport, not output size.
   `AIAuthenticationError` / `AIRateLimitError` → configuration or throttling, not
   code.
3. **Measure the cause before changing approved code.** A tiny-`max_tokens` probe
   reveals whether the failure is the cap or the prompt. A generous-cap probe
   reveals the real requirement. Two requests settled it here.
4. **Keep the fix at the smallest layer.** Token limit → constant. Output shape →
   contract. Neither should reach the core engines or the Pydantic models.
5. **Report the problem and the proposed fix before editing**, per the step-7
   rule in the user's instructions and `AGENTS.md` §15.
6. **Do not spend tokens re-running stages that already passed.** They were not
   re-sent after this fix; their recorded output was reused.

The throwaway harness that ran this step is at
`C:\Users\[LOCAL_USER]\AppData\Local\Temp\opencode\hms_live_step3*.py` with results in
`hms_step3\results.json`, outside the repository. It is not project code. Do not
copy it into `tests/` — the suite must stay offline.

---

## 6. Corrections to the Phase 5 Step 2 handover

That document remains mostly accurate. Two points to update when acting on it:

1. It said the four AI prompts "have still never reached the real provider". They
   now have, and all four passed. Its suggestion to "send one probe per prompt
   first" is done — do not repeat it.
2. It flagged concept generation at 6000 tokens as "the known truncation risk".
   That risk **did not materialise**: 1286 of 6000 tokens were used. The real risk
   was the advisor's cap, which is now fixed.

Everything else in it — the `ui/` package layout, the `hm_workflow_state` session
key, forms with explicit submit, `Outcome[T]` commits, `Decimal(str(amount))`
budget conversion, the five-stage / ten-step mapping, the AppTest quirks — is
unaffected by this step and still current.

---

## 7. Recommended next action

**Await approval, then open Phase 5 Step 4 per `DEVELOPMENT_PLAN.md`.**

The groundwork is now in place. `workflow/state.py` already exposes
`attempt(step, produce, record)` as the single bridge between the UI and the AI
services, and `ui/` already contains the session, commit and presentation layers.
Step 4 is connecting the four newly validated operations to those existing
screens — not building a new layer.

When you do start, the natural first move is to wire `analyze_brief` through
`WorkflowState.attempt` into the brief screen, run it against the real provider
once in the actual Streamlit app, and confirm the resulting brief renders. That
completes one end-to-end user journey on live data.

Respect the approval gate. Do not start Step 4 without it.

---

## 8. Standing constraints (unchanged)

- No Git, commit, push or deploy without explicit approval.
- No system shutdown, restart or sleep commands.
- No new dependencies without justification and approval.
- No AI provider or model change.
- Deterministic calculations stay in Python. The AI never computes geometry or
  financial totals.
- Tests must not require a live API key.
- `docs/screenshots/` is still empty; screenshots are Phase 9 work.
