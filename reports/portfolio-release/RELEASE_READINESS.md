# Release readiness — portfolio review

**Project:** Hometsy — Room Intelligence Studio
**Assessed:** 16 November 2026
**Scope assessed:** the approved V1, as defined in `PROJECT_BRIEF.md` and
constrained by `AGENTS.md` §3.
**Supersedes:** `reports/phase-8/RELEASE_READINESS.md` for the accessibility and
release-artefact categories. The Phase 8 report remains the baseline evidence for
responsive layout, the end-to-end workflow and the axe scan.

---

## 1. Decision

> **Ready for portfolio publication, with two evidence gaps stated openly.**

Everything a reviewer needs to clone, install, configure, run and test the
project is present and verified: dependency pins, a required environment
variable with no secret in the repository, documented run and test commands,
34 resolving image references, and no unfinished-V1 wording anywhere in the
interface.

Two things are **not** verified and are not claimed:

1. **No screen-reader listening session was performed.** NVDA is confirmed absent
   on this machine — checked in eight locations including portable-copy paths on
   16 November 2026 — and was deliberately not installed for this review. A
   substitute was performed — direct inspection of the accessibility tree — and
   that inspection found and fixed a real defect. That is structural evidence,
   not listening, and the project does not claim screen-reader compatibility or
   WCAG conformance. See `SCREEN_READER_TEST.md`.
2. **Axe's heading rule is unreliable in the version used.** It reported a pass
   on a page with zero `h1` elements. The zero-violation axe result is therefore
   not evidence about heading structure; the heading outline is now asserted by
   tests instead. Recorded in §3 rather than hidden.

---

## 2. Category verdicts

| Category | Verdict | Evidence |
|---|---|---|
| Clean install instructions | **PASS** | §4 — venv, pinned requirements, Python 3.13 stated |
| Required configuration | **PASS** | §5 — one env var, documented in both READMEs and `.env.example` |
| No exposed secrets | **PASS** | §6 — real key absent from 126 text files and every binary asset |
| Run and test commands | **PASS** | §7 — documented, executed, 1,149 passing |
| Screenshot references | **PASS** | §8 — 34 embedded images, 34 resolve; 10-image portfolio selection |
| Documentation accuracy | **PASS** | §9 — no finished feature described as unimplemented, no planned feature described as finished |
| Test suite health | **PASS** | §10 — 1,149 passed, 0 failed, 0 skipped, collection count matches |
| Accessibility (automated, axe) | **PASS (narrow)** | §3 — 0 violations on 9 screens; see the heading caveat |
| Accessibility (heading structure) | **PASS** | §3.3 — asserted directly by 26 tests and inspected in the live tree |
| **Accessibility (screen reader)** | **NOT VERIFIED** | §3.4 — NVDA confirmed absent 16 Nov 2026; no session attempted; no conformance claim made |
| Accessibility (WCAG conformance) | **NOT CLAIMED** | §3.4 — deliberately absent from all documentation |
| Responsive layout | **PASS** | Phase 8 §3 — 7 viewport widths in a real browser, no page overflow |
| Core workflow | **PASS** | Phase 8 §2 plus a complete live AI run during this review (§11) |
| PDF report | **PASS** | §11 — 13-page live artefact, 74,769 B, all 10 sections present |
| Version control | **N/A** | no Git repository exists; nothing committed, pushed or deployed |

---

## 3. Accessibility — the honest state

### 3.1 What was already true

Phase 8 ran axe-core 4.10.2 on nine screens across their meaningful states and
recorded **zero violations**. That result stands unchanged: no code change since
then alters contrast, labels, alternative text or focusability, and the axe scan
was not re-run because there was nothing that would make its result differ.

### 3.2 Why the review did not stop there

`AGENTS.md` §12 forbids claiming tests passed when they were not run, and the
Phase 8 report itself already carried "screen reader — NOT VERIFIED". A
manual check needed a screen reader. The decision was:

- **NVDA:** verified absent (see §3.7 — eight locations, including portable-copy
  paths, checked 16 November 2026). Installing and configuring a Windows screen
  reader plus a browser bridge is a large toolchain, and the task brief
  explicitly said not to install one. **Decision: do not install.**
- **Windows 11 Narrator:** present, but this assistant cannot hear audio. Running
  it would produce sound nobody in this session can evaluate, which is not
  evidence.

So the substitute was **direct inspection of the accessibility tree** — the same
tree a screen reader consumes — rather than a listening session. This is
labelled as tree inspection everywhere it appears.

### 3.3 The defect that inspection found — and the fix

Tree inspection on the room screen showed **one `h2` and no `h1`**. Reading the
source explained it:

- the page title was `<h2 class="hm-page-title">`;
- the section headings (`hm-group`, `hm-section-label`, `hm-card-title`,
  `hm-card-name`, `hm-block-title`) were plain `<p>` elements.

A screen-reader user pressing `H` would reach almost nothing, and the document
had no first-level heading at all.

**Fixed** in `ui/theme.py` and the pages that call it:

- `page_intro()` now emits `h1`; a new `page_title()` emits a standalone `h1`.
- `group_heading()` emits `h2`.
- New `section_heading()` emits `h2`; new `card_heading()` / `card_name()` emit
  `h3`; `block_title()` emits `h2` or `h3` by level and rejects lower levels.
- Call sites updated in `pages_landing.py`, `pages_concepts.py`,
  `pages_preferences.py`, `pages_plan.py`.

**Verified after the fix**, live, on all nine screens: every screen has exactly
one `h1`, section headings are real `h2`/`h3`, and no level is skipped.

**Regression-tested** by `tests/test_ui_headings.py` — 26 tests covering helper
output, escaping, one-`h1`-per-screen across all nine screens, level-skip
detection, empty-heading detection, and the absence of hand-written heading tags
in page modules.

**Mutation-verified twice:**

| Mutation | Result |
|---|---|
| Revert the tag fix (titles `h2`, labels `<p>`) | **8 failed, 16 passed** |
| Remove the CSS rule that preserves presentation | **1 failed, 25 passed** |

### 3.4 What is still not verified

- **No listening session.** Nobody has heard this application through a screen
  reader. Reading order, announcement timing, verbosity and pronunciation are
  unverified. The headings, labels, button names, status roles and download
  control were inspected in the tree; speech was never evaluated.
- **No WCAG conformance claim.** The READMEs say this explicitly. A zero-violation
  axe run plus a correct heading outline is not conformance.

### 3.5 A preserved-presentation detail worth recording

Streamlit's own markdown stylesheet styles heading tags with a different
typeface, line height and padding. Converting five label classes from `<p>` to
headings would have changed the visual design if left alone, so those classes are
pinned back to their inherited paragraph presentation with two-class selectors —
required because Streamlit's `.st-emotion-cache-* h2` rules outrank a single
class.

An early attempt applied a global `.hm-page h1` reset. That restyled the page
titles, which were **already** headings and had always looked correct. It was
reverted; the rule is now class-scoped and page titles keep Streamlit's heading
presentation, which is what they always rendered with.

Because this touched CSS, the visual result was verified to be unchanged rather
than assumed:

| Screen | Result |
|---|---|
| Landing | **byte-for-byte identical** |
| Room setup | max channel delta 1/255 in blue; **0 pixels** differ by more than 2 |
| Design preferences | identical content excluding a 6-px scrollbar strip |
| Project review | identical content |

This is why the 20 screenshots were **not** recaptured: a recapture would have
produced the same pixels. See `SCREENSHOT_SELECTION.md`.

### 3.6 Note on the axe false green

axe 4.10.2 reported `page-has-heading-one` with `passes: 1` on a page that
provably contained no `h1`. This is recorded in the READMEs and the case study as
a caution against treating an automated pass as structural proof. It is not an
axe bug report — it is a statement about what this project's evidence does and
does not show.

### 3.7 NVDA check, 16 November 2026 — still NOT VERIFIED

A dedicated attempt was made to close the remaining gap by listening to the
application. **It could not proceed: NVDA is not installed.**

The check was not a single lookup. NVDA also runs as a portable copy with no
installer, so a registry-only check would not have been conclusive. Eight
locations were examined:

| Check | Result |
|---|---|
| `C:\Program Files\NVDA`, `C:\Program Files (x86)\NVDA` | absent |
| `%LOCALAPPDATA%\NVDA`, `%APPDATA%\NVDA` | absent |
| `HKLM\SOFTWARE\NVDA` | absent |
| Uninstall registry entries for NVDA / NonVisual / JAWS | none |
| Start Menu shortcuts | none — only Narrator and On-Screen Keyboard |
| `nvda.exe` on `PATH` | not found |
| `nvda*.exe` recursive search across program, user, temp and `D:\` paths | none |
| Running `nvda` / `jaws` / `narrator` processes | none |

Per instruction, no installer was downloaded, executed or offered for silent
installation, and no alternative screen reader was installed.

Windows 11 Narrator exists on the machine and was **not** used as a substitute:
it speaks through the system audio device, and this session cannot hear audio, so
a run would produce sound nobody could evaluate. Recording a pass from a silent
run would be fabricated evidence.

**Consequence:** no announcement, focus-order, reachability or status-change
finding can be reported. The absence of defects in this report is an absence of
testing, not a clean result. All three critical areas — room definition, 2D plan,
final report — remain **NOT VERIFIED**. Full detail and a resumable checklist are
in `SCREEN_READER_TEST.md`.

---

## 4. Clean install — PASS

`README.md` §Installation and `README.tr.md` §Kurulum state, in order:

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS / Linux
pip install -r requirements.txt
```

`pip install -r requirements.txt` is present verbatim in both files (verified
programmatically). Python 3.13 or newer is stated; the development environment
runs **Python 3.13.18**.

`requirements.txt` pins the approved stack only, with no editable installs:

| Package | Constraint | Resolved here |
|---|---|---|
| streamlit | `==1.67.0` | 1.67.0 |
| pydantic | `>=2.11,<3.0` | 2.14.3 |
| matplotlib | `>=3.11,<4.0` | 3.11.2 |
| reportlab | `>=4.4,<5.0` | 4.5.1 |
| pytest | `>=9.0,<10.0` | 9.2.0 |

No package outside the approved stack is required to run or test the
application. axe-core was used as an external QA instrument from the temp
directory and is correctly **not** a dependency.

`.streamlit/config.toml` pins the light theme, palette and base font size, so a
fresh clone renders as the screenshots show.

---

## 5. Required configuration — PASS

One variable: **`DEPLOY_API_KEY`**.

- `ai/config.py` reads it — verified by an automated check on the source.
- The model ID `deepseek-ai/deepseek-v4.1-flash-1017` is present in
  `ai/config.py` — verified.
- Both READMEs document the variable, for Windows PowerShell and for
  macOS/Linux, plus the `secrets.toml` alternative.
- `.env.example` ships with the placeholder `your-deploy-api-key-here` and no
  real value.
- The README placeholder is `your-key-here`; the Turkish README uses
  `anahtar-buraya`. Both are obviously placeholders, and neither is a credential.

Both READMEs state that **the application runs without a key**: room setup,
preferences, review, budget and the PDF's deterministic sections work, and AI
buttons report that the service is not configured instead of failing silently.
The test suite never needs a key.

---

## 6. No exposed secrets — PASS

Three independent checks:

**6.1 No secret file.** `.streamlit/secrets.toml` does not exist in the
repository. `.gitignore` excludes both `.streamlit/secrets.toml` and `.env`/
`.env.*` (while keeping `!.env.example`), plus `output/reports/`.

**6.2 No credential-shaped literal in source or docs.** An automated scan across
`ui/`, `core/`, `ai/`, `models/`, `workflow/`, `tests/`, `docs/`, `reports/`,
`data/`, `app.py`, both READMEs and `requirements.txt` found **0 hits** for
`sk-`/`sk_` tokens or a literal `DEPLOY_API_KEY` assignment.

One candidate string exists in the suite — `sk-abcdef1234567890` in
`tests/test_ai_config.py`, inside a test asserting that `redact_secrets()` removes
it. It is a deliberate fixture for the redaction test, not a credential; the scan
excludes exactly that one value and nothing else.

**6.3 The real key value is absent everywhere.** The actual `DEPLOY_API_KEY`
(length 24) from the environment was searched as a literal across:

- **126 text files** (`.py`, `.md`, `.json`, `.txt`, `.toml`, `.cfg`, `.ini`,
  `.html`, `.js`, `.yml`, `.yaml`), excluding `.venv`, caches and Git;
- every **binary asset** under 8 MB, including all 20 screenshots and the
  generated PDFs.

**Zero hits in both.** Verdict: **CLEAN**.

The report PDFs in `output/reports/` contain no credential and are excluded from
version control anyway, since they are reproducible from saved project data.

**6.4 Runtime containment.** The credential is read from the environment, excluded
from `repr`, and scrubbed from error messages by `redact_secrets()`, which has its
own tests. A logged exception cannot leak it.

---

## 7. Run and test commands — PASS

Both READMEs contain, verbatim:

```bash
streamlit run app.py
```

with the default URL (`http://localhost:8501`) and a non-default-port example
(`--server.port 8512`), plus the note that the PDF is written to
`output/reports/`.

Tests:

```bash
.venv\Scripts\python.exe -X utf8 -m pytest -q
```

The `-X utf8` flag matters on Windows because test data and the interface contain
Turkish and typographic characters.

A reviewer can therefore install, configure, run and test using only the README.

---

## 8. Screenshot references — PASS

**34 embedded image references** across `README.md`, `README.tr.md` and
`docs/PORTFOLIO_CASE_STUDY.md`; **all 34 resolve to existing files**. All
link-style references to `.png`, `.md`, `.json`, `.toml` and `.txt` files resolve
as well (0 missing).

Collection state:

| Location | Count | Purpose |
|---|---|---|
| `docs/screenshots/` | **20** | the complete, untouched capture set |
| `docs/screenshots/portfolio/` | **10** | the presentation selection, in narrative order |

The selection is **additive**: the originals are unchanged, and the folder names
make the sequence self-explanatory. Both READMEs link the selection folder and
this report, so the artefact is discoverable from the entry point.
`SCREENSHOT_SELECTION.md` maps every selected file back to its original and
explains each exclusion.

No screenshot is fabricated, mocked up or synthetically generated. Every one is a
browser capture of the running application; the PDF in `10-pdf-report.png` is a
real generated file. No key, token, path or hostname appears in any image.

Screenshots were **not recaptured** for this review because the heading fix was
verified pixel-identical (§3.5). Recapturing would have changed bytes only where
a transient scrollbar happened to be present.

---

## 9. Documentation accuracy — PASS

**9.1 No unfinished V1 in the interface.** An automated scan of every module in
`ui/` found no "In development", "coming soon", "TODO" or "FIXME". A stale
"In development" caption had already been removed and the landing screenshot
recaptured during Phase 8; the live PDF generated during this review was checked
for the same string and does not contain it.

**9.2 Roadmap states match reality.** The landing page badges finished versions
as `Complete` (`"complete": "Complete"` present, no leftover `"current"` state).
V1 is marked complete; V2 and V3 are marked planned and are described as not
implemented in both READMEs and in the case study.

**9.3 No finished feature described as unimplemented, and no planned feature
described as finished.** Spot-checked across both READMEs: the AI-vs-Python
split, the invalidation table, the budget rules, the spatial-validation
boundaries and the PDF sections all describe behaviour that exists and is tested.
The limitations sections list real boundaries (one rectangular room, indicative
prices, illustrative plan, no vision, no accounts) and do not claim compliance
with anything.

**9.4 The accessibility claims were corrected.** Both READMEs previously said
"semantic headings" and cited axe zero violations as the supporting evidence.
Both now state what is actually true: one `h1` per screen with real `h2`/`h3`
sections; the axe heading false positive; 26 heading tests; no screen-reader
session; no WCAG claim.

**9.5 Language parity.** `README.md` and `README.tr.md` have the same 15
top-level sections and the same contents in each: purpose, features, screenshots,
architecture, the AI/Python split, stack, install, configuration, running,
workflow, tests, data and assets, limitations, roadmap, documentation. The
Turkish file uses native placeholders and native terminology.

**9.6 Test counts were updated, not inflated.** Both READMEs said 1,123; both now
say **1,149**, which is the measured count after adding `tests/test_ui_headings.py`
(26 tests, verified twice by mutation). The Phase 8 report's 1,123 remains
correct for its date and was not edited.

---

## 10. Test suite health — PASS

```
1,149 passed, 0 failed, 0 skipped   (72.90 s)
```

- `--collect-only` reports **1,149 tests collected**, so the passed count is the
  whole suite rather than a filtered subset.
- `compileall` over `ui core ai models workflow tests app.py` exits **0**.
- No test was deleted, skipped or weakened to reach this result. The only test
  change was the addition of 26 new tests.
- The suite requires **no API key and makes no network call**; every AI operation
  is mocked.

1,123 tests existed at the end of Phase 8. The 26 added tests are the heading
regression suite, which is precisely the kind of test whose absence allowed the
defect in §3.3 to survive an axe pass.

---

## 11. Live end-to-end evidence gathered during this review

The application was run on `127.0.0.1:8512` and driven through the complete
workflow with the real model: room → preferences → review → brief analysis →
three concepts → concept selection → furniture recommendation and plan →
design evaluation → budget → PDF.

- The generated PDF is **74,769 B, 13 pages, 20,425 characters** extracted.
- All ten sections are present, located by their lettered headings: **B** project
  overview, **C** design brief, **D** selected design concept, **E** furniture and
  materials, **F** validated plan, **G** spatial validation, **H** budget
  analysis, **I** AI design evaluation, **J** limitations and disclaimer.
- Downloading the file produced a byte-identical 74,769 B copy at
  `[LOCAL_DOWNLOADS]\hometsy-sisli-living-room-report.pdf`, which was verified
  independently: 13 pages, all section markers present, the old
  "In development" caption absent.
- The accessibility tree was inspected on all nine screens during the same run.

**Operational note, not a defect:** the Streamlit process exited on its own during
the long AI session. It was restarted and the run completed. No project process
remains running. This does not affect the application's behaviour under normal
use, and the workflow was completed before the exit.

---

## 12. Known limitations at release

These are deliberate V1 boundaries or evidence gaps, listed so a reviewer is not
surprised:

1. **No screen-reader listening session.** Structural inspection only.
2. **No WCAG conformance claim,** and none should be inferred.
3. **AI output varies between runs.** The model wrote 42.200,00 TRY in one run and
   41.800,00 TRY in another, with different concept names. Deterministic figures
   (dimensions, positions, geometry verdicts, catalog unit costs, arithmetic)
   reproduce exactly. Screenshots show one such run.
4. **Indicative catalog prices.** Illustrative figures, not market prices, not
   retailer data; the interface says so.
5. **Illustrative plan.** Not a construction or building-code drawing; the
   interface and the PDF both say so.
6. **Basic geometry only.** Boundary, pairwise overlap, door access, window
   clearance and a heuristic circulation score — not ergonomic, accessibility,
   structural or code compliance.
7. **Materials are not priced** and are excluded from the furniture total; shown
   as "not priced" rather than zero.
8. **One rectangular room, one project per session,** no accounts, no database,
   no saved projects.
9. **Text-only model.** No image input, no image generation, and the application
   never implies otherwise.
10. **No Git repository, no deployment.** Nothing was committed, pushed or
    published during this review.

---

## 13. Recommended next action

Publish the repository as a portfolio artefact when the owner is ready, with the
release artefacts as they stand:

- `README.md` / `README.tr.md` — entry point, honest about accessibility
- `docs/PORTFOLIO_CASE_STUDY.md` — the narrative
- `docs/screenshots/portfolio/` — the 10-image presentation set
- `reports/portfolio-release/` — this report, the completion report and the
  screenshot rationale

The single highest-value follow-up, if the work continues, is a **real
screen-reader session** — 30 minutes with NVDA on the room, plan and report
screens would convert the one NOT VERIFIED item into evidence, and would either
confirm the heading fix or find the next defect. It requires no code change and
no new dependency.

Git initialisation, commits, remote creation and deployment remain **not
performed** and need explicit owner approval.
