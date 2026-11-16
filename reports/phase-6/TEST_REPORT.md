# Phase 6 — Test Report

**Project:** Hometsy — Room Intelligence Studio
**Date:** 2026-11-15
**Python:** 3.13.18 (`.venv`)
**Command:** `.venv\Scripts\python.exe -m pytest -q`

---

## 1. Summary

| Run | Result |
|---|---|
| Full suite | **1076 passed, 0 failed, 0 skipped** in 44.72 s |
| Baseline (end of Phase 5) | 996 passed |
| Delta | **+80** |
| Targeted (report + brief) | **150 passed** in 9.40 s |

Per-file:

| File | Tests | Status |
|---|---|---|
| `tests/test_report_generator.py` | 46 | passed |
| `tests/test_ui_report.py` | 25 | passed |
| `tests/test_ai_services.py` | 79 | passed |

No existing test was deleted, weakened or retuned to accommodate the
implementation. Four tests in three other files were updated for one **spec**
change — the stage strip gained a fifth stage — which is recorded in §6.

All automated tests are mock-only. **No test opens a socket or needs an API
key**; the live validation in §7 was run separately and deliberately.

---

## 2. `tests/test_ai_services.py` — Brief Analyzer reliability (+9)

These map directly onto the failure taxonomy in the step brief. The key
distinction is that a truncated answer is a *transport-shaped* failure and must
not be corrected, while malformed or empty content is correctable exactly once.

| Case | Test | Assertion |
|---|---|---|
| Valid JSON | `test_analyze_brief_returns_a_validated_model` | returns a `DesignBrief` |
| Valid JSON, one request | `test_analyze_brief_sends_one_request` | `call_count == 1` |
| **Token limit hit** | `test_brief_that_hits_the_token_limit_is_not_corrected` | raises `AITruncatedResponseError`, **1** call, `max_tokens == BRIEF_TOKENS` |
| **Correction keeps the limit** | `test_brief_correction_uses_the_same_token_limit` | both calls use 8000: `[8000, 8000]` |
| **Truncated JSON content** | `test_truncated_json_content_is_corrected_once_then_reported` | cut-off JSON corrected once; when the repair is also cut off, `AICorrectionFailedError` with `AIInvalidJSONError` as `first_error` |
| Missing fields | `test_brief_missing_summary_triggers_correction` | `{}` then valid → success, 2 calls |
| Missing fields twice | `test_brief_two_bad_answers_raise` | `AICorrectionFailedError` |
| **Pydantic/schema error** | `test_a_schema_error_in_the_first_answer_is_corrected` | wrong type on `summary` corrected |
| **Provider error (rate limit)** | `test_a_provider_error_before_any_content_is_raised_as_itself` | `AIRateLimitError` propagates, **1** call |
| **Provider error (5xx)** | `test_a_server_error_before_any_content_is_raised_as_itself` | `AIServerError` propagates, **1** call |
| **Empty response** | `test_an_empty_brief_answer_is_reported_as_empty` | `""` twice → `AICorrectionFailedError`, message mentions "empty" |
| **Empty then recovered** | `test_an_empty_first_answer_can_be_corrected` | `"   "` then valid → success |
| **No unnecessary calls** | `test_a_valid_first_answer_is_never_sent_twice` | exactly 1 call on the happy path |

The truncation tests are the regression guard for the Phase 6 bug: if anyone
lowers `MAX_TOKENS` again, or makes truncation correctable, these fail.

Also updated in this file:

```python
def test_application_token_limits_match_the_approved_values() -> None:
    assert BRIEF_TOKENS == 8000          # was 2000
```

and the parametrised case now reads `("brief", 8000)`.

---

## 3. `tests/test_report_generator.py` — the PDF (46)

This file carries **its own minimal PDF reader** (no `pypdf`, `pdfplumber` or
`fitz` is installed, and none was added):

* `_objects` — parse the cross-reference objects.
* `_stream` — decode `/ASCII85Decode` + `/FlateDecode` (ReportLab 4.5.1 compresses
  with both).
* `_cmap` / `_unescape` — resolve the `/ToUnicode` cmap, because ReportLab writes
  TTF subsets as `FirstChar 0 / LastChar 127` keyed by subset font name like
  `/F2+0`.
* `pdf_pages` — text **per page**, in document order.
* `pdf_text`, `page_count`.

### 3.1 Document and styling

| Area | Covered by |
|---|---|
| File is a real PDF | header `%PDF-`, trailing `%%EOF`, no `/Encrypt` |
| A4 page size | `/MediaBox` asserted |
| Section presence, all ten | one test walks A–J |
| Page header and footer | asserted on body pages |
| Page numbers | "Page n of N" on every body page, cover unnumbered |
| Heading hierarchy | section letters/titles asserted in order |
| No orphan headings | a heading is never the last flowable on a page |
| Selectable text | text layer is extractable, not an image |
| Long text wraps | a very long rationale does not overflow |
| Palette parity | report colours match `ui.theme.COLORS` |
| Money parity | `format_money` matches `ui.commits.format_money` |

### 3.2 Turkish characters and fonts

| Test | Assertion |
|---|---|
| `test_the_font_contains_every_turkish_letter` | both faces carry `ğ Ğ ş Ş ı İ ö Ö ü Ü ç Ç` |
| `test_the_font_is_embedded_in_the_pdf` | `/FontFile2` and `DejaVuSans` present |
| `test_turkish_text_survives_into_the_text_layer` | nine Turkish strings survive round-trip; `{ş, Ş, ı, ç, ö, ü}` actually occur |

### 3.3 The plan flowable

| Scenario | Assertion |
|---|---|
| `COMPLETE` | drawing present, all footprints, coordinates readable |
| `FAILED` | **no** drawing; explicit statement that no layout was produced |
| `PARTIAL` | only placed items drawn; shortfall stated on the same page |
| Absent | section says there is no placement |
| Exact coordinates | `137.5, 42.25 cm` reaches the table |

### 3.4 Budget and furniture

| Scenario | Assertion |
|---|---|
| Quantities > 1 | carried into both tables and into the arithmetic (`qty 3`) |
| Unpriced item | named, "Not priced", "Excluded", absent from the itemised table |
| Materials | listed as "Not priced", excluded from the total |
| Over budget | stated as a real risk, not softened |
| Long basket (12 items) | every row present, none dropped |
| Long table (60 rows) | header repeated on **every** page carrying rows |

### 3.5 Framing and safety

| Area | Assertion |
|---|---|
| Opinion framing | evaluation presented as opinion, not engineering approval |
| Limitations | disclaimer section present and non-empty |
| Filename safety | Turkish folded, spaces → dashes, invalid chars dropped |
| Path escape | a `..\\` project name still lands inside the output directory |
| Failure messages | user-safe, no paths or provider detail |
| Layer purity | the generator imports neither Streamlit nor the AI layer |
| Legacy result | a `ProjectResult` built without the four new fields still renders |

---

## 4. `tests/test_ui_report.py` — screen and seam (25)

| Group | Tests | What is proven |
|---|---|---|
| When a report may exist | 2 | `can_finalize` needs every earlier step; a report before the evaluation is refused |
| Finalization | 3 | finalize is the **only** creator of a `ProjectResult`; the result carries advisor and layout data |
| One click, one PDF | 5 | one call per click; download offered after; safe filename; **rerun generates nothing**; regenerate replaces on purpose |
| Failure keeps the project | 4 | PDF failure keeps `state.result`; button stays; unexpected error leaks nothing; message never echoes provider detail |
| Stale artifacts | 3 | invalidation withdraws the file even when the screen redirects; identity is the currency rule; a missing file is reported |
| No AI in this step | 2 | all four AI functions are booby-trapped and never called |
| Presentation | 3 | stored results summarised; back link works; new project clears the artifact |

`FakeGenerator` writes into `tmp_path`, so **a test run leaves no file in the
project's `output/reports/`**. This was a real defect found during QA: the first
version of the fixture wrote stub PDFs into the real output directory. Verified
fixed by running the full suite and confirming `output/reports/` does not exist
afterwards.

---

## 5. Coverage of the brief's required Brief cases

| Required case | Test |
|---|---|
| Valid JSON | ✅ `test_analyze_brief_returns_a_validated_model` |
| Token-limit hit | ✅ `test_brief_that_hits_the_token_limit_is_not_corrected` |
| Truncated JSON | ✅ `test_truncated_json_content_is_corrected_once_then_reported` |
| Missing fields | ✅ `test_brief_missing_summary_triggers_correction` |
| Pydantic validation error | ✅ `test_a_schema_error_in_the_first_answer_is_corrected` |
| Provider error | ✅ rate limit + 5xx, both propagated as themselves |
| Empty response | ✅ reported, and recoverable when the retry is good |
| Correction/recovery success | ✅ several |
| Correction/recovery failure | ✅ `AICorrectionFailedError`, `first_error` preserved |
| Previous-result preservation | ✅ covered at the UI layer (`attempt` stores only on success) and in `tests/test_ui_ai_flow.py` |
| No unnecessary API calls | ✅ `call_count` asserted in every case |

---

## 6. Updates to existing tests (spec change, not weakening)

The stage strip gained "Final Report", so `AVAILABLE_STAGES` has 5 entries and no
stage is "Not available yet" any more:

| File | Tests | Change |
|---|---|---|
| `tests/test_ui_app.py` | 2 | stage count / labels |
| `tests/test_ui_ai_flow.py` | 1 | stage strip expectation |
| `tests/test_ui_budget.py` | 1 | next-step label |

Each assertion was changed to the new expected value; none was made weaker or
removed.

---

## 7. Live validation (separate from the suite)

Not part of `pytest`, run deliberately against the real provider. The credential
was read from the process environment and **never printed**.

### 7.1 Brief Analyzer at the old cap (2000)

```
{"attempt": 1, "cap": 2000, "outcome": "API_ERROR",
 "error": "AITruncatedResponseError/truncated_response"}
{"attempt": 2, "cap": 2000, "outcome": "API_ERROR",
 "error": "AITruncatedResponseError/truncated_response"}
{"attempt": 3, "cap": 2000, "prompt_tokens": 766, "completion_tokens": 1675,
 "finish_reason": "stop", "json_valid": true, "outcome": "SUCCESS"}
```

2 of 3 truncated — the diagnosis.

### 7.2 Brief Analyzer at the new cap (8000)

| Run | Prompt | Completion | Finish | JSON | Seconds |
|---|---|---|---|---|---|
| 1 | 766 | 3351 | `stop` | valid | 21.63 |
| 2 | 766 | 2520 | `stop` | valid | 17.12 |
| 3 | 766 | 2517 | `stop` | valid | 14.50 |

3 of 3 succeeded.

### 7.3 Whole workflow through the real UI

Against `streamlit run app.py`, real Chromium, 404 px viewport:

* Brief analysis: success, Turkish text intact.
* Concepts: 3 returned.
* Advisor + layout: 10 of 10 placed, all blocking spatial checks passed.
* Evaluation: success.
* Budget: 58.600,00 TRY.
* PDF: 76 312 bytes, download served as
  `application/pdf; filename="hometsy-sisli-salonu-report.pdf"`, HTTP 200.
* Console errors: **0** across every screen.

---

## 8. Test hygiene

* **No network in the suite.** All AI functions are injected fakes or
  monkeypatched.
* **No writes to the repository.** PDF tests use `tmp_path`; the screen tests
  use a `tmp_path`-backed generator. Confirmed by running the full suite and
  checking `output/reports/` does not exist afterwards.
* **No secrets.** No test reads a key; no error message is asserted to contain
  one.
* **Failures were fixed, not hidden.** Two weak assertions written during this
  phase were found during self-review and tightened:
  * `"0,00 TRY" not in text` — this string is a substring of
    `"45.000,00 TRY"`, so the assertion could never fail for the reason
    intended. Replaced with a check of the itemised table slice plus the engine's
    own error text.
  * a header-repetition test that counted occurrences in the whole document
    could pass with the header printed once. Replaced with a direct
    `SimpleDocTemplate` test over a 60-row table asserting the header on every
    page.
