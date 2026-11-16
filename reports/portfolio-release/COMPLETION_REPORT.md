# Completion report — portfolio release preparation

**Project:** Hometsy — Room Intelligence Studio
**Work package:** portfolio presentation and release verification
**Completed:** 16 November 2026
**Scope:** verify accessibility with real evidence, select portfolio screenshots,
write the case study, tighten both READMEs, run release-readiness checks, and
report honestly. No new V1 feature was added and no completed phase was reopened.

---

## 1. Verdict

> **PASS for portfolio publication**, with one evidence item **NOT VERIFIED** and
> stated as such.

The deliverable set is complete: a 10-image portfolio screenshot selection beside
the untouched 20-image collection, a 375-line case study, both READMEs corrected
where they overstated accessibility, and three reports in
`reports/portfolio-release/`.

One real application defect was found and fixed during the review — page titles
were `h2` and section headings were paragraphs, so screen-reader heading
navigation reached almost nothing. It is fixed, regression-tested and
mutation-verified.

What remains genuinely unverified is a **screen-reader listening session**. NVDA
is absent and was deliberately not installed; the assistant cannot hear Narrator.
That gap is recorded in every document that discusses accessibility, and no
screen-reader compatibility or WCAG conformance is claimed anywhere.

---

## 2. Objectives and outcome

| # | Objective | Outcome |
|---|---|---|
| 1 | Focused screen-reader check, or record NOT VERIFIED | **NOT VERIFIED** for listening; accessibility-tree inspection performed instead, and it found a real defect |
| 2 | Select 8–10 strongest screenshots, keep full collection | **10 selected** into `docs/screenshots/portfolio/`; all 20 originals untouched |
| 3 | Necessary README improvements only, both languages | Accessibility sections corrected; test count 1,123 → 1,149; case-study link added; 15 sections in each language |
| 4 | Write `docs/PORTFOLIO_CASE_STUDY.md` | **375 lines**, 11 sections, real screenshot paths, honest QA |
| 5 | Release-readiness checks | **19/19 automated checks PASS**; one NOT VERIFIED category |
| 6 | Three reports with accurate PASS/PARTIAL/FAIL/NOT VERIFIED | This file, `RELEASE_READINESS.md`, `SCREENSHOT_SELECTION.md` |

---

## 3. The defect found and fixed

### 3.1 What was wrong

Inspecting the accessibility tree on the room screen returned **one `h2` and no
`h1`**. The source showed why:

```python
# before
<h2 class="hm-page-title">       # page title, second level
<p class="hm-group">             # five section headings, plain paragraphs
```

All five section-label classes were paragraphs: `hm-group`, `hm-section-label`,
`hm-card-title`, `hm-card-name`, `hm-block-title`. A screen-reader user pressing
`H` to move between headings would find a single item per screen, and the document
had no top-level heading at all.

The automated axe scan had reported **zero violations** on the same screens,
including a `page-has-heading-one` pass. It was a false green: axe 4.10.2 reported
`passes: 1` for a page with provably zero `h1` elements. This is recorded in the
READMEs and the case study rather than quietly corrected.

### 3.2 What was changed

`ui/theme.py` — the heading helpers are the only place heading markup is produced:

| Helper | Emits | Note |
|---|---|---|
| `page_intro()` | `h1` | was `h2` |
| `page_title()` | `h1` | **new** |
| `group_heading()` | `h2` | was `p` |
| `section_heading()` | `h2` | **new** |
| `card_heading()` | `h3` | **new**, supports inline style |
| `card_name()` | `h3` | **new** |
| `block_title()` | `h2` / `h3` | was `p`; rejects levels below the page title |

Call sites updated:

| File | Change |
|---|---|
| `ui/pages_landing.py` | landing title → `h1`; 3 section labels → `h2`; 3 card titles → `h3` (inline-style support preserved) |
| `ui/pages_concepts.py` | concept name → `h3`; section block → `h2` |
| `ui/pages_preferences.py` | reference card name → `h3` |
| `ui/pages_plan.py` | material card title → `h3` |

### 3.3 Preserving the appearance

Streamlit's markdown stylesheet gives heading tags their own typeface, line height
and padding. Two consequences were handled deliberately:

- `hm-title` / `hm-page-title` were **already** heading tags, so they keep
  Streamlit's heading presentation — which is what they always rendered with.
- The five label classes were paragraphs and are pinned back to inherited
  paragraph presentation (Inter, `line-height: inherit`, `padding: 0`) using
  **two-class selectors**, because Streamlit's `.st-emotion-cache-* h2` rules
  outrank a single class.

A global `.hm-page h1` reset was tried first. It restyled the page titles — which
had never looked wrong — so it was removed and replaced with class-scoped rules.
`tests/test_ui_headings.py` now asserts that no global heading reset returns.

### 3.4 Verified pixel-identical

Because the fix touched CSS, the visual result was measured rather than assumed:

| Screen | Result |
|---|---|
| Landing | **identical, byte-for-byte** |
| Room setup | max channel delta 1/255 in blue only; **0 pixels** above a delta of 2 |
| Design preferences | content identical, excluding a 6-px scrollbar strip |
| Project review | content identical |

**Consequence:** the 20 screenshots were **not** recaptured. A recapture would have
produced the same pixels, and substituting new files would have implied a visual
change that did not happen.

### 3.5 Verified in the live tree

After the fix, all nine screens were re-inspected in the browser:

| Screen | Outline |
|---|---|
| Landing | `h1` × 1, section `h2`s, card `h3`s |
| Room setup | `h1` × 1 (was `h2`), **5 real `h2` sections** (were 5 `<p>`) |
| Design preferences | `h1` × 1, grouped `h2`/`h3` |
| Project review | `h1` × 1, `h2` sections |
| Brief | `h1` × 1, `h2` × 3, `h3` × 4 |
| Concepts | `h1` × 1; concept names are `h3` |
| Plan | `h1` × 1, `h2` × 9, `h3` × 7 |
| Evaluation | `h1` × 1, sections present |
| Budget / report | `h1` × 1; report status message is `role=status`; download is a named button |

An outline script over all nine screens reported **OK** with no level skips.

---

## 4. Tests

### 4.1 New regression suite

`tests/test_ui_headings.py` — **26 tests**:

- every helper emits the expected tag and escapes text
- no heading class is applied to a `<p>`
- no page module hand-writes a heading tag
- exactly one `h1` per screen, across all nine screens
- no skipped heading levels
- no empty heading text
- CSS invariants: the label classes keep paragraph presentation, and no global
  heading reset exists
- `rule_body` helper with a clean assertion message rather than an `IndexError`

### 4.2 Mutation verification

| Mutation | Result |
|---|---|
| Revert the tag fix (titles `h2`, labels `<p>`) | **8 failed, 16 passed** |
| Remove the CSS label pin | **1 failed, 25 passed** |

Both failures are attributable to the intended behaviour, not to incidental
breakage.

### 4.3 Full suite

```
1,149 passed, 0 failed, 0 skipped   (72.90 s)
```

- `--collect-only`: **1,149 collected** — the passed count is the whole suite.
- `compileall` over `ui core ai models workflow tests app.py`: exit **0**.
- 1,123 existed at the end of Phase 8; +26 = 1,149. No test was deleted,
  skipped or weakened.

---

## 5. Screenshot selection

**10 of 20** selected into `docs/screenshots/portfolio/`, renamed into narrative
order:

| # | File | Theme |
|---|---|---|
| 1 | `01-product-identity.png` | landing, product identity, roadmap |
| 2 | `02-room-definition.png` | room definition |
| 3 | `03-design-preferences.png` | design preferences |
| 4 | `04-ai-design-concepts.png` | AI design concepts |
| 5 | `05-furniture-recommendations.png` | furniture recommendations |
| 6 | `06-2d-floor-plan.png` | 2D plan |
| 7 | `07-spatial-validation.png` | spatial validation |
| 8 | `08-design-evaluation.png` | AI evaluation beside deterministic results |
| 9 | `09-budget-analysis.png` | budget analysis |
| 10 | `10-pdf-report.png` | PDF report |

All ten required themes are covered. The full 20-image collection remains in
`docs/screenshots/` and is still referenced (12 embedded images plus 2 mobile
links per README). Copies, not moves — nothing was deleted or overwritten.
`SCREENSHOT_SELECTION.md` maps each selection to its original and explains every
exclusion.

No screenshot was fabricated, mocked, generated or recaptured. The figures are
consistent across the set because they come from one continuous session
(Şişli Living Room, 400 × 500 cm, Japandi, Warm Neutral): 20.00 m², 7 of 7 items
placed, 42.200,00 TRY against a 45.000,00 TRY limit.

---

## 6. Documentation

### 6.1 `docs/PORTFOLIO_CASE_STUDY.md` — new, 375 lines

Eleven sections: overview, problem and objective, user workflow, architecture,
engineering decisions, AI integration, deterministic geometry and budget engines,
QA evidence, screenshots with real paths, limitations and roadmap, and what the
project demonstrates.

It contains no invented users, customers, revenue or production usage. It states
plainly that this is a portfolio project and that the AI-written text in the
screenshots is genuine model output that varies between runs.

### 6.2 `README.md` and `README.tr.md`

Only necessary changes:

| Change | Reason |
|---|---|
| Accessibility section rewritten in both languages | the old text claimed "semantic headings" and cited axe as the evidence; both are now inaccurate |
| Test count 1,123 → 1,149 | the suite grew by 26 |
| `test_ui_headings.py` added to the test table | it is a real module |
| Case-study link added to the documentation table | the file now exists |
| Link to the 10-image portfolio selection and its rationale | the selection is otherwise not discoverable from the entry point |
| Link to `reports/portfolio-release/RELEASE_READINESS.md` | so the accessibility caveat is traceable |

The new Accessibility sections state the axe false positive, the heading tests,
the absence of a listening session and the absence of a WCAG claim.

Both files keep 15 top-level sections with equivalent content. The Turkish file
uses native placeholders (`anahtar-buraya`) and native technical vocabulary.

### 6.3 Reports

| File | Contents |
|---|---|
| `reports/portfolio-release/RELEASE_READINESS.md` | 13 sections: decision, 15 category verdicts, honest accessibility state, install, configuration, secrets, commands, screenshots, documentation accuracy, tests, live evidence, limitations |
| `reports/portfolio-release/SCREENSHOT_SELECTION.md` | selection table, source mapping, excluded images with reasons, verification performed, caveats |
| `reports/portfolio-release/COMPLETION_REPORT.md` | this file |

---

## 7. Release-readiness verification performed

An automated script ran **19 checks**, all PASS:

| Area | Checks |
|---|---|
| Secrets | `secrets.toml` absent; 0 credential-shaped literals; `.gitignore` excludes `.streamlit/secrets.toml`, `.env*` and `output/reports/` |
| Images | 34 embedded references, 34 resolve |
| Links | all `.md` / `.png` / `.json` / `.toml` / `.txt` references resolve |
| Configuration | `ai/config.py` reads `DEPLOY_API_KEY`; model ID present; `requirements.txt` has no editable installs; theme pinned in `.streamlit/config.toml` |
| Stale wording | no "in development" / "coming soon" / TODO / FIXME in `ui/`; roadmap badges say `Complete`; no leftover `current` state |
| Commands | install, run, test and the env var all documented; placeholder is not a real key |

**Independent secret scan:** the real `DEPLOY_API_KEY` value (length 24) was
searched as a literal across **126 text files** and every binary asset under
8 MB — including all 20 screenshots and the generated PDFs. **Zero hits.** The
only key-shaped string in the repository is `sk-abcdef1234567890`, a deliberate
fixture in a redaction test.

**Encoding:** all deliverables are UTF-8, no BOM, no mojibake, and **no mixed
line endings**. Pre-existing CRLF in `theme.py`, `pages_preferences.py`,
`shell.py`, `commits.py`, `diagram.py`, `pages_review.py`, `test_ui_app.py` and
`test_ui_presentation.py` is uniform within each file and was not introduced by
these edits.

---

## 8. Live end-to-end evidence

The application was driven through the complete workflow with the real model on
`127.0.0.1:8512`: room → preferences → review → brief → three concepts →
selection → furniture and plan → evaluation → budget → PDF.

- PDF: **74,769 B, 13 pages, 20,425 characters**.
- All ten sections present, located by lettered heading: B overview, C brief,
  D concept, E furniture and materials, F validated plan, G spatial validation,
  H budget analysis, I AI design evaluation, J limitations and disclaimer.
- The downloaded copy
  (`[LOCAL_DOWNLOADS]\hometsy-sisli-living-room-report.pdf`) is the same 74,769 B
  file; verified independently for page count and section markers.
- The old "In development" caption is absent from the generated PDF.
- The accessibility tree was inspected on all nine screens during this run.

**Operational note:** the Streamlit process exited by itself during the long AI
session and was restarted. The workflow completed. This is recorded so it is not
mistaken for an application defect; no project process remains running.

---

## 9. Files created and modified

### Created

| File | Lines / size | Purpose |
|---|---|---|
| `docs/PORTFOLIO_CASE_STUDY.md` | 375 lines | portfolio case study |
| `tests/test_ui_headings.py` | 541 lines, 26 tests | heading structure and CSS invariants |
| `docs/screenshots/portfolio/` (10 files) | — | presentation selection |
| `reports/portfolio-release/SCREENSHOT_SELECTION.md` | — | selection rationale |
| `reports/portfolio-release/RELEASE_READINESS.md` | — | release verdicts and evidence |
| `reports/portfolio-release/COMPLETION_REPORT.md` | — | this report |

### Modified

| File | Change |
|---|---|
| `ui/theme.py` | heading helpers `h1`/`h2`/`h3`; 4 new helpers; class-scoped presentation-preservation CSS |
| `ui/pages_landing.py` | title and section/card headings |
| `ui/pages_concepts.py` | concept name and section heading |
| `ui/pages_preferences.py` | reference card name |
| `ui/pages_plan.py` | material card title |
| `README.md` | accessibility section, test count, test table, case-study link |
| `README.tr.md` | same, in Turkish |

### Not touched

No data file, schema, calculation engine, AI module, workflow rule or PDF layout
was changed. No dependency was added. `requirements.txt` is unchanged. Nothing was
deleted.

---

## 10. Known limitations

1. **No screen-reader listening session.** NOT VERIFIED. Accessibility-tree
   inspection is structural evidence only; reading order, announcement timing and
   pronunciation were never evaluated.
2. **No WCAG conformance claim,** and none is implied by the tests, the axe scan
   or the heading outline.
3. **Axe's heading rule was wrong here.** Documented so the project's automated
   evidence is not over-read in future.
4. **AI prose varies between runs.** Figures the model wrote differ per run;
   deterministic figures reproduce exactly. Screenshots show one run.
5. **Screenshots cover one project.** They show the application's behaviour, not a
   survey of rooms or styles.
6. **Pre-existing CRLF** in eight source files. Uniform within each file, left
   unchanged to avoid a noisy diff for no functional gain.
7. **No Git repository exists.** Nothing committed, pushed or deployed.

---

## 11. Scope compliance

- No V1 feature added; no excluded feature attempted.
- No completed phase reopened. Phase 7/8 findings were used as baseline evidence,
  not re-audited.
- The axe scan was **not** re-run, because no change affected contrast, labels,
  alternative text or focusability — the only UI change was heading tags with
  pixel-identical rendering.
- No dependency introduced, including for accessibility; axe remains an external
  QA instrument outside `requirements.txt`.
- No API configuration, model, endpoint or schema changed.
- No secret written, logged, printed or committed.
- No shutdown, restart, sleep or hibernate was performed; the machine was left
  running.

---

## 12. Recommended next action

Publish the repository when the owner is ready. The artefacts are ready as they
stand.

The single highest-value follow-up is a **real screen-reader session** — roughly
30 minutes with NVDA on the room, plan and report screens. It needs no code change
and no new dependency, and it would convert the one NOT VERIFIED item into either
confirmation or the next concrete defect.

Git initialisation, commits, remote creation and deployment remain **not
performed**, and require explicit owner approval.
