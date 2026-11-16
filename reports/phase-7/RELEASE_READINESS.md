# Phase 7 — Release Readiness

**Project:** Hometsy — Room Intelligence Studio
**Assessed:** 16 November 2026
**Scope assessed:** the approved V1, as defined in `PROJECT_BRIEF.md` and
constrained by `AGENTS.md` §3.

---

## 1. Decision

> **Ready for the next development phase; not yet ready for portfolio
> publication.**

The product works, the full suite passes, and every functional area of V1 has
been exercised both by tests and by real use. The remaining gaps are **evidence**
gaps rather than known defects: responsive behaviour is verified at one live
viewport and by a CSS fixture elsewhere, and accessibility is verified
structurally rather than with assistive technology. A portfolio release claims
more than that, so it should wait until Phase 8/9 addresses those two areas and
adds the required `README.md` / `README.tr.md` and screenshots.

This is a deliberate, evidence-led verdict. Nothing here is marked PASS on the
strength of "it looks right".

---

## 2. Category verdicts

| Category | Verdict | Evidence |
|---|---|---|
| Core workflow (room → preferences → brief → concepts → plan → evaluation → budget → PDF) | **PASS** | four complete live end-to-end runs, including COMPLETE, PARTIAL, over-budget and FAILED paths |
| Deterministic engines (room, spatial, placement, budget) | **PASS** | 39/39 state, 39/39 placement, 41/41 budget; all arithmetic in Python `Decimal` |
| AI integration (4 operations, structured + validated) | **PASS** | 12 live calls, all schema-valid on the first attempt; a failed call never becomes a stored result |
| PDF report | **PASS** | 35/35 structural, 58/58 edge cases, 3 placement states verified from real text, 78,181 B / 14-page live artefact |
| Honesty of claims (no overclaiming) | **PASS** | validated / partial / not-drawn headings; unpriced ≠ zero; materials "unknown, not priced"; partial plan announced as partly placed |
| Interface presentation | **PASS** | UI/PDF comparison 32/32; no overflow at 404 px; long values wrap |
| Responsive layout | **PARTIAL** | 404 px live; other widths from a CSS fixture only — see §3.1 |
| Accessibility | **PARTIAL** | 38/38 structural probe; no real screen-reader or browser audit — see §3.2 |
| Test suite health | **PASS** | 1098 passed, 0 failed, 0 skipped; no test deleted or weakened; 4 mutation checks each killed the intended test |
| Documentation for release | **NOT STARTED** | `README.md`, `README.tr.md` and `docs/screenshots/` are Phase 9 deliverables and remain empty/absent by plan |
| Security / secrets | **PASS** | no credential in source, tests, logs or reports; `DEPLOY_API_KEY` read from the environment only |
| Version control | **N/A** | no Git repository exists; nothing was committed, pushed or deployed |

---

## 3. What is not verified, and why it matters

### 3.1 Responsive behaviour — PARTIAL

- **Live:** 404 px only. `clientWidth` 404, `pageOverflow` 0, media query
  present, tables within bounds.
- **Fixture:** wider and intermediate widths were measured against an
  HTTP-served CSS fixture on port 8513.
- **Why:** the desktop browser exposes no resize control and the Playwright relay
  at `127.0.0.1:19988` was unreachable.

The fixture proves the *stylesheet* behaves; it does not prove the composed
application does, because it does not exercise Streamlit's own layout containers.
**A real 320 / 768 / 1024 / 1440 px pass is still required** before claiming
responsive support.

### 3.2 Accessibility — PARTIAL

Section G (38/38) verified structure: `role="img"`, unique ids, `<title>` and
`<desc>` on both drawings, alt text on every reference image, labelled controls,
and heading order. It did **not** run a screen reader, `axe`, or keyboard-only
navigation.

Specific honest gap: the accessible names are now accurate about layout
completeness (§6.3 of the test report), but *whether* a screen reader announces
them usefully in context is unverified.

---

## 4. Non-blocking known issues

| Issue | Impact | Status |
|---|---|---|
| Hot-reload `TypeError` (`not a WorkflowState under 'hm_workflow_state'`) | development only; reproduced twice after source edits, never in a fresh process | **not a product defect**; restart clears it |
| `\x7f` bytes in PDF text extraction | cosmetic artefact of the extractor, not the document; identical count (62) before and after | pre-existing, out of scope |
| `material_subtotal` field exists but is always zero in V1 | invites the misreading now fixed in the prompt and PDF | structural, deferred; removing it is a model change |
| A partial layout with `GEOMETRIC VALIDITY: Valid` | correct by design (geometry checks only what was placed) and now explained in both UI and evaluation | resolved by explanation, not by changing the engine |

---

## 5. Blocking items before publication

1. **Real multi-viewport verification** at 320 / 768 / 1024 / 1440 px on the
   running application. Until then, no responsive claim may be made.
2. **A real accessibility pass** with assistive technology and/or `axe`, at least
   on the plan and report screens where the SVG and tables live.
3. **Documentation**: `README.md` and `README.tr.md` with equivalent content, plus
   real screenshots in `docs/screenshots/` (currently empty; the rule is that they
   must come from the running application).
4. **A licence check** for every reference image, recorded per `AGENTS.md` §11.

None of these requires a product change. All four are Phase 8/9 work.

---

## 6. What would change this decision

The decision moves to "ready for publication" when:

- the four items in §5 are closed with evidence, and
- the full suite still passes at or above 1098, and
- one further live end-to-end run reproduces COMPLETE and PARTIAL with the final
  code.

The decision would move to "not ready" if any of the honesty guarantees regressed
— specifically if a partial layout, an unpriced item or a failed placement could
again be presented as validated, priced or buildable. Those guarantees are the
core of the product's credibility and are now pinned by tests.
