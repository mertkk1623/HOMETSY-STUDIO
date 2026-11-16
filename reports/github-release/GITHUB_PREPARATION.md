# GitHub preparation — first publication readiness

**Project:** Hometsy — Room Intelligence Studio
**Prepared:** 16 November 2026
**Objective:** prepare the existing project for its first GitHub publication.
**Status:** preparation only — **nothing was published, initialised, staged,
committed, pushed or deployed.**

---

## 1. Decision

> **Ready for first GitHub publication. One blocker remains: the Git identity.**
> The source-pack question is closed — Option A is approved and all 23 images are
> included (§10.2–§10.3).

The repository content is clean: no credential is present, `.env` and
`secrets.toml` are absent, `.venv` and caches are excluded, **217 files totalling
9.08 MB** are proposed, no file approaches a GitHub size limit, and no case
collision or path-length risk exists. Licensing is correct for the stated All
Rights Reserved decision, the bundled third-party font notice is preserved, the
proprietary rights notice exists, and the imagery has a recorded ownership basis.

> **Inventory note.** This audit originally measured **196 files / 7.60 MB**. The
> current figure is **217 files / 9.08 MB**: a later UX polish pass added 21
> deliverables under `reports/final-ux-polish/` and re-captured two screenshots in
> place. The difference is itemised in
> `FINAL_PRE_GIT_CHECKLIST.md` §1.1. Nothing in the security, licensing or
> large-file findings below changes.

The only thing standing between this tree and a first commit:

1. **Git identity is unset** at every scope. A commit cannot be created without
   it. It was deliberately not configured, because the author name and email on a
   public commit are the owner's choice.

Resolved during preparation: the 33 local paths across 22 files are sanitized
(§9.5), `main` is the recommended initial branch (§12.1), `COPYRIGHT.md` exists
(§10.5), and the source-pack redistribution question is closed by owner approval
(§10.2).

---

## 2. Git availability

| Item | Value |
|---|---|
| Git | **installed** — `git version 2.56.1.windows.1` |
| Repository state | **not a Git repository** (`rev-parse --is-inside-work-tree` fails) |
| GitHub CLI (`gh`) | **not installed** — remote creation would need the web UI or a later CLI install |
| `user.name` (global / system / local) | **unset at all three scopes** |
| `user.email` (global / system / local) | **unset at all three scopes** |
| `init.defaultBranch` (global) | unset |
| `init.defaultBranch` (system) | **`master`** |
| `core.autocrlf` | **`true`** (system scope) |
| `core.eol` | unset |
| `core.longpaths` | unset |

**Consequences worth knowing before the first commit:**

- **No identity means `git commit` fails.** This is the single hard blocker, and
  it is a one-time owner setting. No value is recorded here, because identity is
  private information.
- **Default branch will be `master`.** **`main` is recommended** (see §12.1). It
  must be set explicitly with `git init -b main` or `init.defaultBranch`; the
  choice was not made for you.
- **`core.autocrlf=true` will normalise line endings on commit.** Working-tree
  CRLF becomes LF in the repository, and LF becomes CRLF on checkout. This is
  standard on Windows and is the desired behaviour; it is noted so the first
  `git status` / diff does not look alarming.
- **`core.longpaths` is unset.** Not a problem here — the longest tracked relative
  path is 71 characters and the longest tracked absolute path is 108, both far
  inside the 260-character limit. Both are UX evidence PNGs under
  `reports/final-ux-polish/evidence/`. (The longest path anywhere in the working
  tree is excluded `.venv` content at 166 / 203.)

No Git command that writes state was run: no `init`, `add`, `commit`, `push`,
`remote`, `tag`, `config`, or `gh` invocation.

---

## 3. Repository structure

**217 files, 9.08 MB** in total — **214 files, 9.01 MB** of pre-existing project
content plus this report, `COPYRIGHT.md` and
`reports/github-release/FINAL_PRE_GIT_CHECKLIST.md`.

| Area | Files | Notes |
|---|---|---|
| `(root)` | 14 | `app.py`, `requirements.txt`, `pytest.ini`, `.gitignore`, `.env.example`, both READMEs, four governing documents, `opencode.json`, `COPYRIGHT.md` |
| `.streamlit/` | 1 | `config.toml` — pinned theme; `secrets.toml` correctly absent |
| `ai/` | 10 | HTTP client, prompt assembly, parsing, four analyzers/generators, config |
| `assets/` | 29 | 2 fonts + licence, 10 style/palette images, 13 source-pack images + 2 manifests + `.gitkeep` |
| `core/` | 8 | room, placement, spatial and budget engines, report generator, validation |
| `data/` | 4 | furniture catalog, design references, asset replacements, `.gitkeep` |
| `docs/` | 31 | case study + 20 original screenshots + 10 portfolio screenshots |
| `models/` | 2 | Pydantic schemas and package init |
| `reports/` | 66 | 11 phase directories, portfolio-release set, one sample PDF, **the 21-file UX polish deliverable**, **this report**, the checklist |
| `tests/` | 28 | 1,149 tests |
| `ui/` | 21 | shell, theme, session, commits, diagram, one module per screen |
| `workflow/` | 3 | state machine and dependency rules |

Structure is consistent with `TECHNICAL_ARCHITECTURE.md`: only `ui` imports
Streamlit, and `core` / `ai` / `models` / `workflow` stay framework-free.

### File-type profile

| Type | Files | Size |
|---|---|---|
| `.py` | 71 | 1,201.1 KB |
| `.md` | 53 | 717.6 KB |
| `.png` | 50 | 4,661.6 KB |
| `.jpg` | 23 | 1,195.7 KB |
| `.ttf` | 2 | 1,426.0 KB |
| `.pdf` | 1 | 66.5 KB |
| `.json` | 6 | 18.0 KB |
| `.toml` / `.ini` / `.txt` | 4 | 5.3 KB |
| `.example` | 1 | 0.2 KB |
| `.gitignore` (no suffix) | 1 | 0.7 KB |
| `.gitkeep` placeholders | 5 | 0 B |
| **Total** | **217** | **9.08 MB** |

`.png` rose from 30 to 50: the 20 UX evidence screenshots. `.md` rose from 52 to
53: the polish completion report.

---

## 4. `.gitignore` changes

### 4.1 What was already correct

The existing 22 patterns already covered everything essential:

```gitignore
__pycache__/   *.py[cod]   *.pyo   *.pyd
.venv/   venv/   env/
.env   .env.*   !.env.example   .streamlit/secrets.toml
.pytest_cache/   .ruff_cache/   .mypy_cache/   htmlcov/   .coverage   .coverage.*
output/reports/
.DS_Store   Thumbs.db   .idea/   .vscode/
```

This correctly excludes the virtual environment, all Python caches, `.env`,
`secrets.toml`, and the runtime-generated `output/reports/`. Nothing here needed
changing.

### 4.2 What was added

Two gaps existed against the task checklist — "browser profiles and local runtime
artifacts are excluded". Neither category exists in the tree today, but a future
run could create one, and an ignore file is cheaper than a history rewrite.

```gitignore
# Local runtime artifacts: logs, temp files and local databases
*.log
*.tmp
*.bak
*.orig
*.rej
*.sqlite
*.sqlite3
*.db

# Browser automation profiles and test residue
.playwright/
browser-profile/
chromium-profile/
playwright-report/
test-results/
```

### 4.3 Verified non-destructive

The ignore file was simulated against all 13,876 files in the tree before and
after the change. **The proposed inventory is identical: 193 files both times.**
The new patterns excluded zero real files — they only cover artifacts that do not
yet exist.

The file remains pure LF, no BOM, and the pre-existing content is unchanged.

---

## 5. Secret scan

**Result: CLEAN. No credential is present in any file proposed for commit.**

The scan covered 137 text files across every tracked directory, plus a binary
search for the live credential value.

| Check | Result |
|---|---|
| `.env` | **absent** — only `.env.example`, containing the placeholder `your-deploy-api-key-here` |
| `.streamlit/secrets.toml` | **absent** |
| Real `DEPLOY_API_KEY` value, searched in **all text and binary files** | **not found in any file** |
| Credential-shaped literals (`sk-…`, AWS, private-key blocks, bearer tokens) | 0 real secrets |
| API-key-style assignments | 7 matches — **all placeholders** |

### 5.1 The three flagged items, classified

Thirteen candidate matches were reviewed individually. **None is a secret.**

| Location | Match | Classification |
|---|---|---|
| `tests/test_ai_config.py:196` | `Bearer` + 16-char string | **Test fixture** — input to `test_redact_secrets_removes_bearer_tokens`, which asserts the value is scrubbed |
| `tests/test_ai_config.py:201-202` | `sk-` + 16-char string | **Test fixture** — input to `test_redact_secrets_removes_sk_style_tokens`, which asserts the value is scrubbed |
| `reports/phase-6/COMPLETION_REPORT.md:255` | 32-char hex | **Not a credential** — a Streamlit media filename (`GET /media/<32 hex>.pdf`) recorded in an HTTP transcript |

The two redaction fixtures are deliberately fake test data. They are **not**
real secrets and must not be classified as such: they are the *evidence that the
redaction function works*. Their only cost is that a naive future scanner will
flag them again, which is why this table exists.

**Seven placeholder matches**, all documented installation guidance:

- `.env.example:3` → `your-deploy-api-key-here`
- `README.md:251, 254, 261` → `your-key-here`
- `README.tr.md:251, 254, 261` → `anahtar-buraya`

### 5.2 Safe handling

No credential value was printed in any terminal output or report. Where a value
had to be examined, it was masked with a length marker before display. The live
key was compared by byte search in memory only.

---

## 6. Large-file findings

**No large-file problem exists.**

| Metric | Value | GitHub limit |
|---|---|---|
| Largest single file | 738 KB (`assets/fonts/DejaVuSans.ttf`) | 100 MB hard |
| Total proposed commit | 9.08 MB (217 files incl. this report, `COPYRIGHT.md`, the checklist and the 21-file UX polish deliverable) | — |
| Files over 1 MB | **0** (both fonts are 738 KB and 688 KB; the largest PNG is 508 KB) | — |
| Files over 100 KB | 12 | — |
| Files over 50 MB | **0** | 100 MB hard |
| Files needing Git LFS | **0** | — |

Nothing requires Git LFS, Git LFS is not recommended, and adding it would be
unnecessary complexity. The fonts are legitimately needed by
`core/report_generator.py` at build time and must ship.

### Other repository hazards, all clear

| Hazard | Result |
|---|---|
| Case-insensitive filename collisions | **0** |
| Longest tracked relative path | 71 chars |
| Longest tracked absolute path | 108 chars (limit 260) |
| Longest path anywhere in tree | 166 relative / 203 absolute — excluded `.venv` content |
| Stray logs / temp / database files | **0 found** |
| Stray browser profiles or test residue | **0 found** |
| Build output or caches in tree | none outside `.venv` |

### Intentional duplications, documented

1. **Portfolio screenshots duplicate originals** — 8 of the 10 files in
   `docs/screenshots/portfolio/` are byte-identical to their originals in
   `docs/screenshots/`, costing ~1.1 MB. This is **deliberate**: the originals are
   the complete capture archive, the selection is the narrative sequence, and both
   are referenced by documentation. Removing either would break links.
   Two pairs are now **not** identical by design: `05-furniture-recommendations.png`
   and `07-spatial-validation.png` in the portfolio set are the frozen originals,
   while `11-design-plan.png` / `13-spatial-validation.png` were re-captured after
   the plan screen was reordered. The portfolio selection was intentionally left
   untouched rather than silently rewritten.
2. **Source-pack assets duplicate the integrated assets** — `assets/source_pack/`
   holds the original crops that `assets/images/` was derived from, plus their
   provenance manifests. This is an intentional audit trail, not clutter.

Total redundancy is ~1.7 MB out of ~9.08 MB. Acceptable for a portfolio repository.

---

## 7. Proposed files to include — the inventory

Every file below would be committed. This is the complete list; nothing is
abbreviated. Counts are **193 files inventoried by the original audit**; adding
`reports/github-release/GITHUB_PREPARATION.md` (this report), `COPYRIGHT.md` and
`reports/github-release/FINAL_PRE_GIT_CHECKLIST.md` brought that audit to
**196 files**, and the later UX polish pass added **21** more under
`reports/final-ux-polish/` — a first commit of **217 files**.

### Root — 14 files

```
.env.example          .gitignore            AGENTS.md
COPYRIGHT.md          DESIGN_SYSTEM.md      DEVELOPMENT_PLAN.md
PROJECT_BRIEF.md      README.md             README.tr.md
TECHNICAL_ARCHITECTURE.md                   app.py
opencode.json         pytest.ini            requirements.txt
```

### `.streamlit/` — 1 file

```
config.toml
```

### `ai/` — 10 files

```
.gitkeep            __init__.py        brief_analyzer.py   client.py
concept_generator.py config.py         design_advisor.py   design_evaluator.py
parsing.py          prompt.py
```

### `assets/` — 29 files

These 29 files are the *audit-era* inventory. Under **Option B** in §10.2, the 23
`.jpg` files would be withheld, leaving 6: the 2 font files, their licence, the 2
manifests and `.gitkeep`. Nothing has been removed.

```
.gitkeep
fonts/DejaVu-LICENSE.txt      fonts/DejaVuSans.ttf        fonts/DejaVuSans-Bold.ttf
images/palettes/cool_modern.jpg      images/palettes/earthy.jpg
images/palettes/natural_materials.jpg images/palettes/warm_neutral.jpg
images/styles/bohemian.jpg     images/styles/contemporary.jpg
images/styles/industrial.jpg    images/styles/japandi.jpg
images/styles/scandinavian.jpg  images/styles/warm_minimalism.jpg
source_pack/asset_manifest.json
source_pack/Replacements/asset_manifest.json
source_pack/Replacements/japandi.jpg
source_pack/Replacements/natural_materials.jpg
source_pack/Replacements/warm_minimalism.jpg
source_pack/palettes/calm_blue.jpg      source_pack/palettes/modern_contrast.jpg
source_pack/palettes/natural_earth.jpg  source_pack/palettes/neutral_harmony.jpg
source_pack/styles/bohemian.jpg         source_pack/styles/contemporary.jpg
source_pack/styles/industrial.jpg       source_pack/styles/minimalist.jpg
source_pack/styles/modern.jpg           source_pack/styles/scandinavian.jpg
```

### `core/` — 8 files

```
.gitkeep   __init__.py   budget_engine.py   placement_engine.py
report_generator.py   room_engine.py   spatial_engine.py   validation.py
```

### `data/` — 4 files

```
.gitkeep   asset_replacements.json   design_references.json   furniture_catalog.json
```

### `docs/` — 31 files

```
PORTFOLIO_CASE_STUDY.md
screenshots/01-landing.png … 20-budget-mobile-390.png            (20 originals)
screenshots/portfolio/01-product-identity.png … 10-pdf-report.png  (10 selected)
```

### `models/` — 2 files

```
__init__.py   schemas.py
```

### `reports/` — 66 files

```
.gitkeep
phase-4-step-5/    COMPLETION_REPORT.md  NEXT_SESSION.md  TEST_REPORT.md
phase-5-step-1/    COMPLETION_REPORT.md  NEXT_SESSION.md  TEST_REPORT.md
phase-5-step-2/    COMPLETION_REPORT.md  NEXT_SESSION.md  TEST_REPORT.md
phase-5-step-3/    COMPLETION_REPORT.md  NEXT_SESSION.md  TEST_REPORT.md
phase-5-step-4/    COMPLETION_REPORT.md  NEXT_SESSION.md  TEST_REPORT.md
phase-5-step-5a/   COMPLETION_REPORT.md  NEXT_SESSION.md  TEST_REPORT.md
phase-5-step-5b/   COMPLETION_REPORT.md  NEXT_SESSION.md  TEST_REPORT.md
phase-5-step-6/    COMPLETION_REPORT.md  NEXT_SESSION.md  TEST_REPORT.md
phase-6/           COMPLETION_REPORT.md  NEXT_SESSION.md  TEST_REPORT.md
                   PDF_SAMPLE_NOTES.md    sample/hometsy-sisli-salonu-report.pdf
phase-7/           COMPLETION_REPORT.md  NEXT_SESSION.md  TEST_REPORT.md
                   RELEASE_READINESS.md
phase-8/           COMPLETION_REPORT.md  NEXT_SESSION.md  TEST_REPORT.md
                   RELEASE_READINESS.md   UI_PLAN.md
portfolio-release/ COMPLETION_REPORT.md  RELEASE_READINESS.md
                   SCREENSHOT_SELECTION.md  SCREEN_READER_TEST.md
final-ux-polish/   COMPLETION_REPORT.md   (1 file)
                   evidence/  after-01 … after-06   (13 PNGs)
                              before-02 … before-06 (7 PNGs)
github-release/    GITHUB_PREPARATION.md   FINAL_PRE_GIT_CHECKLIST.md
                   (the two documents in this directory)
```

The `final-ux-polish/evidence/` PNGs are working evidence for the polish report —
before/after captures of the changed screens. They are **not** portfolio images and
are not referenced by `README.md`, `README.tr.md` or the case study; the 10-image
portfolio selection in `docs/screenshots/portfolio/` remains separate.

### `tests/` — 28 files

```
conftest.py
test_ai_client.py      test_ai_config.py      test_ai_parsing.py
test_ai_prompt.py      test_ai_services.py    test_budget_engine.py
test_data_library.py   test_models.py         test_placement_engine.py
test_report_generator.py  test_room_engine.py  test_spatial_engine.py
test_ui_advisor_flow.py   test_ui_ai_flow.py   test_ui_app.py
test_ui_budget.py      test_ui_commits.py     test_ui_evaluation.py
test_ui_headings.py    test_ui_layout.py      test_ui_presentation.py
test_ui_report.py      test_ui_session.py     test_validation.py
test_workflow_dependencies.py  test_workflow_integration.py
test_workflow_state.py
```

### `ui/` — 21 files

```
__init__.py   ai_actions.py   budget.py   commits.py   diagram.py
layout.py     references.py   report.py   session.py   shell.py   theme.py
pages_landing.py     pages_room.py        pages_preferences.py
pages_review.py      pages_brief.py       pages_concepts.py
pages_plan.py        pages_evaluation.py  pages_budget.py
pages_report.py
```

### `workflow/` — 3 files

```
__init__.py   dependencies.py   state.py
```

---

## 8. Proposed files to exclude

### 8.1 Excluded by `.gitignore` — 13,685 files

| Path | Files | Reason |
|---|---|---|
| `.venv/` | 13,575 | virtual environment; reproducible from `requirements.txt` |
| `tests/__pycache__` and other `__pycache__` | 71 | bytecode caches |
| `ai/`, `core/`, `ui/`, `models/`, `workflow/` `__pycache__` | 42 | bytecode caches |
| `.pytest_cache/` | 5 | test cache |
| `output/reports/*.pdf` | 6 | runtime-generated, reproducible from saved project data |

### 8.2 Absent from the tree — nothing to exclude

Confirmed absent, so no rule is doing hidden work:

- `.env`, `.env.*` (except the example)
- `.streamlit/secrets.toml`
- `.idea/`, `.vscode/`, `.DS_Store`, `Thumbs.db`
- logs, temp files, `.bak`/`.orig`/`.rej`, SQLite databases
- browser profiles, `.playwright/`, Playwright reports, `test-results/`
- `node_modules/`, `dist/`, `build/`, notebooks, `.ipynb_checkpoints`

### 8.3 Deliberately kept despite being generated

**`reports/phase-6/sample/hometsy-sisli-salonu-report.pdf`** (66.5 KB) is a
generated PDF, but it is an intentional portfolio artefact: `PDF_SAMPLE_NOTES.md`
documents it, explains how to regenerate it deterministically, and references it
directly. It is excluded from the `output/reports/` rule on purpose and stays.

---

## 9. Local paths in tracked files — sanitized (inventory retained as audit evidence)

**33 occurrences across 22 files**, all inside `reports/`. One Windows username
appeared in these files. These are local development records, **not credentials**,
but they would have become public on publication.

> **Status: sanitized.** The original audit found these paths and, per the
> instruction in force at the time, left them intact. They have since been
> replaced with neutral placeholders in a separate, owner-approved cleanup. The
> three tables in §9.1–§9.3 are **retained verbatim as historical audit
> evidence**: they record exactly where the paths were and how many there were.
> The headings name each category generically rather than quoting the original
> form, so no literal local path survives in the tracked set. The files
> themselves no longer contain any of it.

Substitution applied, and nothing else:

| Original form | Replacement | Count |
|---|---|---|
| Windows user directory, e.g. `C:\Users\<name>\...` | `C:\Users\[LOCAL_USER]\...` | 9 |
| Project root (local absolute path) | `[PROJECT_ROOT]` | 22 |
| Downloads directory (local absolute path) | `[LOCAL_DOWNLOADS]` | 2 |
| | **Total** | **33** |

The replacement is confined to the exact line numbers listed below, so no
surrounding text, date, test result or technical claim could be altered. Every
file remained UTF-8 without BOM and LF-only. Full verification is recorded in
§9.5.

### 9.1 Windows username (`C:\Users\<name>`) — original finding

| File | Line | Context |
|---|---|---|
| `reports/phase-4-step-5/TEST_REPORT.md` | 309 | external probe script location |
| `reports/phase-5-step-3/COMPLETION_REPORT.md` | 435 | throwaway harness location |
| `reports/phase-5-step-3/NEXT_SESSION.md` | 138 | probe location |
| `reports/phase-5-step-5b/NEXT_SESSION.md` | 186 | probe location |
| `reports/phase-7/COMPLETION_REPORT.md` | 88 | probe file list |
| `reports/phase-7/NEXT_SESSION.md` | 95 | probe location |
| `reports/phase-8/COMPLETION_REPORT.md` | 125 | `axe.min.js` location |
| `reports/phase-8/NEXT_SESSION.md` | 94 | `axe.min.js` location |
| `reports/phase-8/NEXT_SESSION.md` | 139 | `axe.min.js` location |

### 9.2 Project root (local absolute path) — original finding

| File | Line |
|---|---|
| `reports/phase-4-step-5/NEXT_SESSION.md` | 150 |
| `reports/phase-4-step-5/TEST_REPORT.md` | 15 |
| `reports/phase-5-step-1/NEXT_SESSION.md` | 72, 205 |
| `reports/phase-5-step-1/TEST_REPORT.md` | 15 |
| `reports/phase-5-step-2/NEXT_SESSION.md` | 90, 236 |
| `reports/phase-5-step-2/TEST_REPORT.md` | 15, 282 |
| `reports/phase-5-step-3/NEXT_SESSION.md` | 91 |
| `reports/phase-5-step-3/TEST_REPORT.md` | 31 |
| `reports/phase-5-step-5a/NEXT_SESSION.md` | 124 |
| `reports/phase-5-step-5a/TEST_REPORT.md` | 7, 14 |
| `reports/phase-5-step-5b/NEXT_SESSION.md` | 141 |
| `reports/phase-5-step-5b/TEST_REPORT.md` | 7, 14 |
| `reports/phase-5-step-6/NEXT_SESSION.md` | 50 |
| `reports/phase-5-step-6/TEST_REPORT.md` | 7, 14 |
| `reports/phase-6/NEXT_SESSION.md` | 98 |
| `reports/phase-7/NEXT_SESSION.md` | 22 |

### 9.3 Download directory (local absolute path) — original finding

| File | Line | Context |
|---|---|---|
| `reports/portfolio-release/COMPLETION_REPORT.md` | 294 | downloaded PDF verification |
| `reports/portfolio-release/RELEASE_READINESS.md` | 424 | downloaded PDF verification |

### 9.4 Assessment (original)

- **No credential, token or account identifier** is involved.
- The username is a local Windows account name and the paths are ordinary
  development locations.
- The portfolio-release pair is **deliberate evidence**: it records that the
  downloaded PDF was verified byte-identically against the generated one.
- Replacing them with a neutral placeholder is a cosmetic, reversible change that
  would need owner direction, because it edits historical records.

### 9.5 Sanitization record and verification

Owner approval was given, and the substitution described above was applied.

**Scope discipline.** The rewrite was restricted to the 33 inventoried line
numbers. A helper script indexed each target file by line, replaced matches on
those lines only, and rewrote the file only if a change occurred. Because line
numbers were pinned, no other line in those 22 files could be touched. All 22
files were consumed and written as UTF-8 without BOM with LF endings, matching
their original encoding.

**Result.** All 33 replacements applied; 0 lines skipped for a missing match;
22 of 22 files modified.

**Post-change verification**, run across the repository (133 text files, honouring
`.gitignore`):

| Check | Result |
|---|---|
| Personal Windows username anywhere in the tree | **0** |
| Live `C:\Users\<real name>\...` path | **0** |
| Live `...\Projects\room-intelligence-studio` path | **0** |
| Live `...\indirilenler` path | **0** |
| Leftovers on the 33 inventoried lines | **0** |
| `[PROJECT_ROOT]` in the 22 sanitized files | 22 |
| `[LOCAL_USER]` in the 22 sanitized files | 9 |
| `[LOCAL_DOWNLOADS]` in the 22 sanitized files | 2 |

Counts match the original inventory exactly, which confirms the replacement was
one-for-one and nothing was added or dropped. (The repository-wide totals are
higher because this report itself now documents the placeholders.)

The sanitized lines read naturally, for example:

```text
cd "[PROJECT_ROOT]"
Script location: `C:\Users\[LOCAL_USER]\AppData\Local\Temp\opencode\probe_services.py`
(`[LOCAL_DOWNLOADS]\hometsy-sisli-living-room-report.pdf`) is the same 74,769 B
```

**Deliberately not changed.** These matched the scanner but are not
machine-specific and were left alone:

| Location | Text | Why it stays |
|---|---|---|
| `tests/test_report_generator.py`, `tests/test_ui_report.py` | `C:\secret\path`, `C:\Windows\System32` | Redaction and path-handling **test fixtures**; they are invented strings that the tests assert on. Changing them would modify tests, which is out of scope. |
| `reports/portfolio-release/SCREEN_READER_TEST.md`, `RELEASE_READINESS.md` | `C:\Program Files\NVDA`, `C:\ProgramData`, `C:\tools`, `D:\` | Generic, system-wide Windows locations in the NVDA-absence audit. They contain no username and describe a standard OS layout. |
| `tests/test_ui_presentation.py` | `overflow-x: auto` | Not a path; a regex false positive. |

The §9.1–§9.3 headings and the substitution table now name each category
generically (*local absolute path*) rather than quoting the original form, so no
literal local path survives anywhere in the tracked set while the audit trail —
file, line and count per finding — is preserved unchanged.

---

## 10. Licensing and ownership

| Item | State |
|---|---|
| Root `LICENSE` file | **absent** — correct for **All Rights Reserved** |
| Proprietary rights notice | **`COPYRIGHT.md` added** (§10.3) |
| Open-source licence text anywhere in the project | **none** |
| `assets/fonts/DejaVu-LICENSE.txt` | **present and preserved** — Bitstream Vera / public-domain notice kept beside the fonts |
| `core/report_generator.py` attribution | present — cites the font licence in a docstring |
| Third-party image licences | `assets/source_pack/asset_manifest.json` records original AI-generated provenance and a redistribution caveat |

No open-source licence was added. `COPYRIGHT.md` states that the code and project
materials are proprietary and that all rights are reserved, without creating a
`LICENSE` file or granting any rights.

### 10.1 Source-pack redistribution review

The manifests were read in full, the images were hashed, and the code was
searched for references.

**What the manifests say.**

- `assets/source_pack/asset_manifest.json`
  - `source`: *"Original AI-generated visual reference sheet created in this
    conversation"*
  - `license_note`: *"No third-party stock imagery used. Review applicable
    platform terms before external redistribution."*
  - `asset_note`: *"Cropped reference assets; illustrative design inspiration,
    not verified products or completed client projects."*
- `assets/source_pack/Replacements/asset_manifest.json`
  - `source`: *"Original AI-generated illustrated visual reference sheet created
    for this project"*
  - `notes`: illustrative reference crops, not photographs of real projects or
    products.

**What this establishes.**

- **No external platform dataset, stock library or scraped image set is involved.**
  Every one of the 13 source-pack images is declared as original AI-generated
  content produced within this project. There is no third-party photographer,
  agency or retailer to attribute.
- **Attribution to a third party is therefore not required**, and
  `data/design_references.json` records the same conclusion
  (`third_party_stock: false`, `attribution_required: false`).
- **Redistribution permission was not explicitly stated in the manifests.** They
  carried a self-recorded instruction to *review applicable platform terms* before
  redistributing externally. That was a caveat the project wrote to itself about
  the terms of the platform on which the images were generated — **not** an
  assertion that redistribution is forbidden, and **not** a conflicting licence.

**This is now resolved.** The owner has confirmed that all 23 images were
generated with **ChatGPT ImageGen for this HOMETSY project**, and has reviewed the
applicable OpenAI output-ownership terms (§10.3). The manifest caveat is therefore
satisfied rather than overridden: the review it asked for has taken place, and the
owner has accepted the conclusion. The caveat text is deliberately **left in the
manifest** as a record that the review was required and performed.

Because the instruction is to treat unclear redistribution rights as
**EXCLUDE UNTIL PERMISSION IS CONFIRMED**, that rule applied while the question
was open. It is now closed and the classification below reflects the approval.

### 10.2 Asset classification — Option A approved

The source pack is **15 files** — 13 JPEG images plus 2 JSON manifests. The table
covers the whole publication inventory, not only the pack, so the font and runtime
rows are included for completeness.

**Decision: Option A is approved.** All 23 HOMETSY images are IN the publication
inventory. Nothing was deleted, relocated or modified to reach this decision.

| # | Files | Classification | Basis |
|---|---|---|---|
| 1 | `assets/source_pack/Replacements/` — `japandi.jpg`, `warm_minimalism.jpg`, `natural_materials.jpg` (3 images) | **APPROVED FOR PUBLICATION** | Owner-confirmed ChatGPT ImageGen output for this project; output ownership assigned to the user under the OpenAI terms (§10.3). No third-party stock. |
| 2 | `assets/source_pack/styles/` — `scandinavian`, `contemporary`, `industrial`, `bohemian` (4 images) | **APPROVED FOR PUBLICATION** | Same basis. |
| 3 | `assets/source_pack/palettes/` — `neutral_harmony`, `natural_earth`, `modern_contrast`, `calm_blue` (4 images) | **APPROVED FOR PUBLICATION** | Same basis. |
| 4 | `assets/source_pack/styles/modern.jpg`, `styles/minimalist.jpg` (2 images) | **APPROVED, retained as provenance** | Same rights basis. Separately, these two remain **retired from the product** — `data/asset_replacements.json` records them as `retained_excluded` because they misrepresent their categories. That is a product decision, distinct from rights. They ship as source-pack provenance only and are never displayed. |
| 5 | `assets/images/styles/*.jpg` (6), `assets/images/palettes/*.jpg` (4) | **APPROVED FOR PUBLICATION** | Byte-identical copies of the pack images (verified by SHA-256), same rights basis. They are **load-bearing at runtime**: `ui/references.py` raises `ReferenceError` if a mapped image is absent. |
| 6 | `assets/fonts/DejaVuSans.ttf`, `DejaVuSans-Bold.ttf`, `DejaVu-LICENSE.txt` | **SAFE WITH ATTRIBUTION** | Bitstream Vera / Arev licence explicitly permits redistribution, including in a larger package, provided the copyright and permission notices accompany the fonts. Notice present and preserved; attribution restated in `COPYRIGHT.md` §3–§4. |
| 7 | `assets/source_pack/asset_manifest.json`, `assets/source_pack/Replacements/asset_manifest.json` | **SAFE TO PUBLISH** | Plain JSON metadata recording provenance. They contain no image data and exist precisely to document origin. |
| 8 | Everything else in the tree (code, tests, data, docs, reports, the 30 screenshots, the sample PDF, `.gitkeep` files) | **SAFE TO PUBLISH** | Created for this project; no third-party content beyond the font. |

**Totals: 23 images** — 13 source-pack + 10 runtime. All included.

**Why rows 2–4 and 5 had to be decided together.** They are the same pixels under
different paths. Approving `assets/images/` while withholding the source pack would
not have reduced any redistribution exposure — it would only have removed the
provenance record while publishing the images themselves. Option A covers both by
construction.

### 10.3 Basis for the approval — and what it does not say

The owner's confirmation, recorded verbatim in substance:

- The images were generated with **ChatGPT ImageGen** for this HOMETSY project.
- **13** original generated images exist in the source pack.
- **10** runtime copies exist in `assets/images/`.
- All **23** are to remain included, unmodified and in place.

**The ownership basis.** OpenAI's Terms of Use state, under *Ownership of content*:
*"As between you and OpenAI, and to the extent permitted by applicable law, you (a)
retain your ownership rights in Input and (b) own the Output. We hereby assign to
you all our right, title, and interest, if any, in and to Output."* Publishing the
images in a repository is distribution of the owner's own Output, not of OpenAI's
services. The same terms separately prohibit distributing *the Services*
themselves — which is not what this repository contains.

**Two limits are recorded honestly rather than glossed over:**

1. **Similarity.** The same section continues: *"output may not be unique and other
   users may receive similar output."* The assignment does not extend to other
   users' output. So the images are the owner's to publish, but they are not
   guaranteed exclusive — the repository does not claim they are unique.
2. **Inputs.** The owner warranted having the rights needed to supply Input. No
   third-party stock was supplied as Input according to both manifests, which is
   what makes the chain clean; that rests on the manifests and the owner's
   confirmation, not on any verification this audit performed.

**What this section explicitly does NOT claim:**

- **It does not claim OpenAI endorses, sponsors, certifies or is affiliated with
  HOMETSY.** No such statement is made anywhere in the repository, and none should
  be inferred. There is no OpenAI logo, wordmark or brand asset in the project.
- **It does not claim the images are unique, exclusive or free of similarity to
  other users' outputs.**
- **It does not claim trademark clearance.** The images are illustrative interior
  vignettes; if any depicts a recognisable branded product, that is a residual
  third-party rights question the audit cannot resolve (§10.4).
- **It does not restate OpenAI's terms as advice.** The quotation above is a
  reading of the published terms as they stood when checked; the terms themselves
  govern, and they can change.

Image provenance also rests on the manifests plus the owner's confirmation. The
JPEGs carry **no embedded C2PA or provenance manifest** — checked directly, no
`c2pa`, `DALL·E`, `OpenAI` or software tags are present — so the record is
documentary, not technical. That is normal for cropped reference sheets, but it is
worth stating plainly rather than implying the files self-attest their origin.

### 10.4 Remaining third-party rights caveats

These stay open and are **not** blockers for a portfolio publication:

| Caveat | Status |
|---|---|
| **DejaVu font licence** | **Satisfied.** Notice present at `assets/fonts/DejaVu-LICENSE.txt`, attribution reproduced in `COPYRIGHT.md` §3–§4. Must not be removed. |
| **Python dependencies** | Not vendored. Each installed at runtime via `requirements.txt` under its own licence (Apache-2.0, MIT, BSD, PSF and similar). No source is redistributed, so nothing to attribute in-tree. |
| **Incidental brands in imagery** | Not verifiable from the audit. The images are AI-generated illustrative vignettes, not photographs of real products; the manifests state they are *"illustrative design inspiration, not verified products."* `COPYRIGHT.md` disclaims ownership of third-party trademarks. |
| **No name/logo rights to OpenAI marks** | `COPYRIGHT.md` and this report make no brand claim, and no OpenAI mark is used. |
| **AI-generated-content disclosure** | `README.md` and `data/design_references.json` state plainly that the images are AI-generated. OpenAI's Sharing & Publication Policy is written for social-media and demonstration sharing rather than repository publication, so it is not applied here as a formal rule; the disclosure is made because it is accurate, not to claim compliance with that policy. |

### 10.5 `COPYRIGHT.md` status

**Created.** `COPYRIGHT.md` at the repository root states that:

- The source code, UI, documentation, calculation models, tests, reports and the
  project's own visual assets are **proprietary**; all rights reserved.
- Publication is for portfolio and evaluation only and grants no licence.
- No open-source licence is granted; the absent `LICENSE` file is deliberate.
- Software is provided "as is", with no warranty, and the 2D plans and budget
  figures are illustrative.
- Third-party material stays with its owners: the DejaVu font licence is named,
  its required attribution is reproduced in summary, and
  `assets/fonts/DejaVu-LICENSE.txt` is named as governing.
- No ownership is claimed over third-party trademarks or product designs, and
  rights in AI-generated imagery are asserted only to the extent they subsist.

It adds no `LICENSE` file and no open-source grant.

### 10.6 Option B — not taken, retained as a record

Option B (withhold all 23 images) was **not chosen**. It is kept here only because
it records what the alternative would have cost, and because a future owner may
want the reasoning. Nothing in this section was executed.

Excluding the source pack would not have been a file deletion, but it would have
broken the current test suite, and it is worth being precise about how much.

`tests/test_data_library.py` has 34 test functions. **16 of them** reference the
source pack — via a literal `source_pack` path, a `source_image` field, or the
`_collect_reference_paths` helper, which enumerates every declared `assets/…` path
from the metadata and asserts it exists. Those 16 would have been the realistic
breakage set, not an incidental corner of the file.
`test_reference_path_inventory_is_complete` also pins the count at exactly 28
declared paths, so removing source-pack entries would have failed an arithmetic
assertion as well as an existence one.

The application would have broken harder than the tests. `ui/references.py` validates
every mapped image at load time and raises `ReferenceError("Missing reference
image: ...")` if one is absent, so the preferences screen would **fail to render**,
not degrade with a placeholder. The runtime copies in `assets/images/` are therefore
load-bearing, and they are byte-identical to the pack images.

Had Option B been chosen, the follow-up would have been a deliberate, approved
change covering: removing the source-pack paths from `data/design_references.json`
and `data/asset_replacements.json` (which also means recomputing the 28-path
assertion), adjusting the 16 dependent tests, and adding a documented placeholder
path for clones. **No part of that was done, and none of it is needed now.**

A note on provenance for future readers: the manifests describe the images as
illustrative reference crops, the categories are fully described in
`PROJECT_BRIEF.md` and `DESIGN_SYSTEM.md`, and `data/design_references.json` names
each expected filename — so a fork that ever needed to replace them could do so
one image per category at the declared path. No such generator is included in the
project, and none is claimed.

---

## 11. Documentation consistency

| Check | Result |
|---|---|
| `README.md` references | **30 / 30 resolve** — 12 images, 4 file links, 14 in-page anchors |
| `README.tr.md` references | **30 / 30 resolve** — 12 images, 4 file links, 14 in-page anchors |
| `docs/PORTFOLIO_CASE_STUDY.md` references | **12 / 12 resolve** — 10 images, 2 file links |
| Section parity between READMEs | **15 H2 and 12 H3 each, equivalent content** |
| Test count consistency | **`1,149` in both READMEs** (en `1,149`, tr `1.149` — same number, locale formatting); **0 stale `1,123`** |
| Backticked file references in `reports/portfolio-release/` | **0 broken** — see the breakdown below |
| Stale UI wording (`In development`, `coming soon`, TODO, FIXME) in `ui/` | **0 hits** across all 21 `ui/` modules. The 17 mentions in `reports/` (plus 4 in this row itself) are historical descriptions of the defect and its fix — including the regression test that now guards against it — not live product wording. |
| Roadmap status for V1 | **marked complete** — `README.md` L455 *"V1 — Core Room Intelligence Workflow *(complete)*"*, `README.tr.md` L452 *"*(tamamlandı)*"*. V2/V3 remain described as not implemented. |
| WCAG claims | **none** — every mention is an explicit disclaimer. The only string resembling a claim is `reports/phase-8/RELEASE_READINESS.md`, which lists *"WCAG 2.1 AA conformant"* under **"the project may not say"**. |
| Screen-reader verification claims | **none** — every mention is `NOT VERIFIED` |

The two README reference counts were originally recorded as *"28 / 28"* and the
case study as *"22 / 22"*. Neither figure reproduces from the files under a single
counting basis, so they have been replaced by the exact breakdown above: every
rendered link and image target, plus every in-page anchor, resolved. The
conclusion is unchanged — **nothing is broken** — but the numbers are now ones
that can be re-derived. The Turkish README writes the test count as `1.149`
(decimal-separator locale convention), which is the same 1,149 tests, not a
divergence.

**How the `reports/portfolio-release/` figure was derived.** Across the 4 reports
there are **155** backticked tokens that end in a file extension. Of those:

| Bucket | Count | Examples |
|---|---|---|
| Not a path at all | 21 | bare extensions (`.json`, `.md`, `.py`), the `compileall` command line, `pip install -r requirements.txt`, `!.env.example` |
| Resolve to a real file | 129 | module names, report names, the sample PDF |
| Absent by design | 5 | `.streamlit/secrets.toml` and `secrets.toml`, which the reports themselves document as deliberately absent |
| **Genuinely broken** | **0** | — |

155 = 21 + 129 + 5. An earlier draft of this report stated *"160 tokens, 6
unresolved"*, which did not reproduce under any single counting basis and has been
replaced. The conclusion is unchanged: **no reference in those reports is broken.**

The addition of `COPYRIGHT.md` to the documentation tables in both READMEs was
made during this cleanup and is included in the counts above.

### 11.1 `SCREEN_READER_TEST.md` accuracy — verified, with one correction

The file states plainly that no listening test occurred. Confirmed accurate:

- §1 outcome: *"The manual test could not be performed. NVDA is not installed."*
- §1: *"the application has been **inspected** structurally, and has never been
  **heard**."*
- §6: all three areas — room definition, 2D plan, final report — are
  `NOT VERIFIED`, with the note that no defect was found *because no test ran*.
- §7: screen-reader compatibility claim permitted: **NO**; WCAG claim: **NO**.

**One inconsistency was found and fixed:** §2 said *"Five independent locations
were checked"*, while its own table lists **eight** rows. The sentence was
corrected to "Eight". This is a factual self-correction, not a rewrite, and the
`NOT VERIFIED` verdict is untouched.

### 11.2 `RELEASE_READINESS.md` verdict — verified intact

- §1 states the two evidence gaps, including that a screen-reader listening
  session was not performed.
- §2 category table: `Accessibility (screen reader)` → **`NOT VERIFIED`**.
- §3.7 — *"NVDA check, 16 November 2026 — still NOT VERIFIED"* — documents the
  absence check across eight locations.
- §12 limitations: *"No screen-reader listening session. Structural inspection
  only."* and *"No WCAG conformance claim, and none should be inferred."*

(The section numbers in this subsection refer to `RELEASE_READINESS.md`, not to
this report.)

The four documentation updates from the cancelled NVDA task are **preserved
unchanged**, as instructed.

---

## 12. Open items before publication

| # | Issue | Severity | Needs |
|---|---|---|---|
| 1 | **Git identity unset** (`user.name`, `user.email`) | **Blocker** — `commit` will fail | Owner value, one-time |
| 2 | **GitHub CLI not installed** | Not a blocker | Only needed for CLI-based remote creation |
| 3 | **Real screen-reader session not performed** | Disclosed, not a blocker | Remains `NOT VERIFIED`; no WCAG claim may be made |

**Only one blocker remains: the Git identity.** Everything else is either done or
is a disclosed limitation that does not prevent publication.

Resolved by the cleanup and approval work:

| # | Issue | Resolution |
|---|---|---|
| 1 | 33 local paths across 22 files in `reports/` | **Sanitized** — §9.5 |
| 2 | Default branch would be `master` | **`main` recommended** — §12.1 |
| 3 | No proprietary rights notice | **`COPYRIGHT.md` created** — §10.5 |
| 4 | Source-pack redistribution permission unconfirmed | **Option A approved** — owner confirmed ChatGPT ImageGen origin and accepted the OpenAI output-ownership basis (§10.2–§10.3) |

### 12.1 Branch recommendation

**Use `main` as the initial branch.** Git's system default here is `master`, so
the branch must be named explicitly at the first commit; otherwise the repository
opens on `master`:

```text
git init -b main
```

or, if the repository already exists, `git branch -m main`. No Git command was
run and no system or global setting was changed. `core.autocrlf=true` is set at
system scope; that is a local workstation preference and is not recorded in the
repository.

### 12.2 Git identity

`user.name` and `user.email` are **unset at global, system and local scope**. The
first commit will fail until the owner supplies them. This was deliberately not
resolved here, because the author name and email attached to a public commit are
the owner's choice, not a technical default. Nothing at system or global scope was
modified.

### 12.3 Finalized publication inventory

Measured against the filesystem on completion of this task. The working directory
and the proposed tracked inventory are **different things**, and the difference is
almost entirely `.venv`:

| Measure | Files | Size |
|---|---|---|
| **Total files present in the working directory** (excluding `.git`, which does not exist) | **13,902** | **~443 MB** |
| `.venv/` virtual environment | −13,575 | — |
| Python and pytest caches (`__pycache__/`, `.pytest_cache/`) | −104 | — |
| `output/reports/` runtime-generated PDFs | −6 | — |
| **Proposed tracked-file inventory** | **217** | **9.08 MB** |

13,902 − 13,685 = **217**. The ~443 MB working directory is not the publication
size; the 9.08 MB tracked inventory is.

This section originally recorded 196 files / 7.60 MB. The increase to 217 files is
the 21-file UX polish deliverable (§7, `reports/final-ux-polish/`); no other
tracked path was added, and the two re-captured screenshots were replaced in place.

Proposed inventory by area:

| Area | Files | Size | Notes |
|---|---|---|---|
| `(root)` | 14 | 122.1 KB | includes `README.md`, `README.tr.md`, `COPYRIGHT.md`, `.gitignore`, `.env.example`, the four governing documents, `opencode.json`, `app.py`, `pytest.ini`, `requirements.txt` |
| `.streamlit/` | 1 | 0.3 KB | `config.toml`; `secrets.toml` correctly absent |
| `ai/` | 10 | 85.1 KB | HTTP client, prompts, parsing, evaluators |
| `assets/` | 29 | 2,628.7 KB | **23 approved images**, 2 fonts, DejaVu licence, 2 manifests, `.gitkeep` |
| `core/` | 8 | 165.5 KB | room, placement, spatial, budget engines, report generator |
| `data/` | 4 | 15.2 KB | furniture catalog, design references, asset replacements, `.gitkeep` |
| `docs/` | 31 | 3,177.4 KB | case study + **30 screenshots** (20 original + 10 portfolio) |
| `models/` | 2 | 20.8 KB | Pydantic schemas |
| `reports/` | 66 | 2,159.6 KB | 11 phase directories, portfolio-release set, 1 sample PDF, **21-file UX polish deliverable**, this report, the checklist |
| `tests/` | 28 | 635.8 KB | 1,149 tests |
| `ui/` | 21 | 249.5 KB | shell, theme, session, one module per screen |
| `workflow/` | 3 | 42.2 KB | state machine and dependency rules |
| **Total** | **217** | **9.08 MB** | |

**`.gitignore` coverage was re-verified against the required content.** The rules
exclude `output/reports/` but match **no** path under `assets/`, `docs/`,
`data/` or the repository root. Every required asset and document resolves as
tracked:

| Required item | Tracked |
|---|---|
| `README.md`, `README.tr.md`, `COPYRIGHT.md` | yes |
| `assets/fonts/DejaVu-LICENSE.txt` | yes |
| 13 source-pack images | yes |
| 10 runtime images | yes |
| 30 screenshots (`docs/screenshots/`) | yes |
| 20 UX evidence screenshots (`reports/final-ux-polish/evidence/`) | yes — working evidence, intentionally outside the portfolio selection |
| `reports/phase-6/sample/hometsy-sisli-salonu-report.pdf` | yes |
| `.env.example` (with `!.env.example` negation) | yes |

No rule accidentally excludes a required asset or document.

### 12.4 What `.gitignore` excludes, and why

| Pattern | Rationale |
|---|---|
| `.venv/`, `venv/`, `env/` | reproducible from `requirements.txt` |
| `__pycache__/`, `*.py[cod]`, caches | bytecode and tool caches |
| `.env`, `.env.*` (with `!.env.example`) | **secrets** — the example is deliberately kept |
| `.streamlit/secrets.toml` | **secrets** |
| `output/reports/` | runtime-generated, reproducible from saved project data |
| `*.log`, `*.tmp`, `*.bak`, `*.sqlite`, `*.db` | local runtime artifacts |
| `.playwright/`, browser profiles, `test-results/` | automation residue |
| `.DS_Store`, `Thumbs.db`, `.idea/`, `.vscode/` | OS and editor noise |

One generated file is **deliberately kept** despite the `output/reports/` rule:
`reports/phase-6/sample/hometsy-sisli-salonu-report.pdf`, which is a portfolio
artefact documented in `PDF_SAMPLE_NOTES.md`.

---

## 13. What was and was not done

### Done

- Inspected Git availability, identity state, configuration and repository state.
- Inventoried the full tree and simulated `.gitignore` matching against all
  13,876 files.
- Scanned for secrets across 137 text files plus all binary files.
- Scanned for local path leakage and enumerated it line by line.
- Checked large files, path lengths, case collisions and line endings.
- Verified documentation links, section parity, test counts and accessibility
  honesty.
- Added two `.gitignore` blocks; verified they exclude zero real files.
- Corrected one factual inconsistency in `SCREEN_READER_TEST.md`.
- **Sanitized all 33 local path occurrences across 22 report files** (§9.5),
  replacing them with `[PROJECT_ROOT]`, `[LOCAL_USER]` and `[LOCAL_DOWNLOADS]`,
  and verified 0 remaining occurrences.
- **Reviewed the source pack for redistribution rights** and classified every
  asset (§10.1–§10.2).
- **Recorded the owner's Option A approval**, with the ChatGPT ImageGen origin and
  the OpenAI output-ownership basis, and noted the two limits (output similarity;
  no endorsement claim). All 23 images are approved for inclusion (§10.2–§10.3).
- **Created `COPYRIGHT.md`**, a proprietary all-rights-reserved notice that
  preserves the DejaVu attribution and disclaims ownership of third-party
  material (§10.5).
- **Added one documentation-table row to each README** so the notice is
  discoverable from the front page, keeping H2/H3 parity.
- **Re-verified documentation references** and corrected three §11 counts that
  did not reproduce under a single counting basis (§11).
- **Finalized and measured the publication inventory** against the filesystem:
  13,902 working-directory files → 217 tracked, 9.08 MB tracked of ~443 MB on
  disk (§12.3–§12.4). The audit-era figure was 196 files / 7.60 MB; the 21-file
  UX polish deliverable was added afterwards and is recorded in
  `FINAL_PRE_GIT_CHECKLIST.md` §1.1.
- **Re-captured two screenshots** (`docs/screenshots/11-design-plan.png`,
  `13-spatial-validation.png`) at 1440 × 1000 so the public documentation reflects
  the reordered plan screen. The other 18 originals and the 10-image portfolio
  selection were left untouched.
- **Created `reports/github-release/FINAL_PRE_GIT_CHECKLIST.md`**.

### Not done

- **No `git init`**, `git add`, `git commit`, `git push`, `git remote add`, or
  `git tag`.
- **No remote repository** created; **no `gh` command** run.
- **No deployment.**
- **No Git identity configured** — deliberately untouched.
- **No Git or system configuration changed** — not globally, not locally.
- **No file deleted**, moved or renamed.
- **No image deleted, relocated or modified** — all 23 remain byte-identical in
  place; verified by size and by the absence of any write to `assets/`.
- **No source code or test changed** — not one `.py` file was modified.
- **No test suite rerun**, since no code changed; the previously verified
  1,149 passed / 0 failed / 0 skipped baseline stands.

### Files modified by this task

| File | Change |
|---|---|
| `.gitignore` | +17 lines: runtime artifacts and browser/test residue |
| `reports/portfolio-release/SCREEN_READER_TEST.md` | "Five" → "Eight" location count |
| `reports/phase-4-step-5/NEXT_SESSION.md` | 1 path → `[PROJECT_ROOT]` |
| `reports/phase-4-step-5/TEST_REPORT.md` | 1 path → `[PROJECT_ROOT]`, 1 → `[LOCAL_USER]` |
| `reports/phase-5-step-1/NEXT_SESSION.md` | 2 paths → `[PROJECT_ROOT]` |
| `reports/phase-5-step-1/TEST_REPORT.md` | 1 path → `[PROJECT_ROOT]` |
| `reports/phase-5-step-2/NEXT_SESSION.md` | 2 paths → `[PROJECT_ROOT]` |
| `reports/phase-5-step-2/TEST_REPORT.md` | 2 paths → `[PROJECT_ROOT]` |
| `reports/phase-5-step-3/COMPLETION_REPORT.md` | 1 path → `[LOCAL_USER]` |
| `reports/phase-5-step-3/NEXT_SESSION.md` | 1 → `[PROJECT_ROOT]`, 1 → `[LOCAL_USER]` |
| `reports/phase-5-step-3/TEST_REPORT.md` | 1 path → `[PROJECT_ROOT]` |
| `reports/phase-5-step-5a/NEXT_SESSION.md` | 1 path → `[PROJECT_ROOT]` |
| `reports/phase-5-step-5a/TEST_REPORT.md` | 2 paths → `[PROJECT_ROOT]` |
| `reports/phase-5-step-5b/NEXT_SESSION.md` | 1 → `[PROJECT_ROOT]`, 1 → `[LOCAL_USER]` |
| `reports/phase-5-step-5b/TEST_REPORT.md` | 2 paths → `[PROJECT_ROOT]` |
| `reports/phase-5-step-6/NEXT_SESSION.md` | 1 path → `[PROJECT_ROOT]` |
| `reports/phase-5-step-6/TEST_REPORT.md` | 2 paths → `[PROJECT_ROOT]` |
| `reports/phase-6/NEXT_SESSION.md` | 1 path → `[PROJECT_ROOT]` |
| `reports/phase-7/COMPLETION_REPORT.md` | 1 path → `[LOCAL_USER]` |
| `reports/phase-7/NEXT_SESSION.md` | 1 → `[PROJECT_ROOT]`, 1 → `[LOCAL_USER]` |
| `reports/phase-8/COMPLETION_REPORT.md` | 1 path → `[LOCAL_USER]` |
| `reports/phase-8/NEXT_SESSION.md` | 2 paths → `[LOCAL_USER]` |
| `reports/portfolio-release/COMPLETION_REPORT.md` | 1 path → `[LOCAL_DOWNLOADS]` |
| `reports/portfolio-release/RELEASE_READINESS.md` | 1 path → `[LOCAL_DOWNLOADS]` |
| `README.md` | +1 documentation-table row for `COPYRIGHT.md`; asset-provenance paragraph updated to record the completed platform-terms review and the no-endorsement statement |
| `README.tr.md` | same two changes, in Turkish |
| `reports/github-release/GITHUB_PREPARATION.md` | registration of the sanitization, asset review and copyright notice (§1, §3, §6, §7, §9–§14) |

Path edits total 33 substitutions across 22 files; each is a single token
replacement and no other line was altered. The two README changes are one table
row each, added so the notice is discoverable from the front page, and they keep
the READMEs at 15 H2 / 12 H3 parity.

### Files created by this task

| File | Purpose |
|---|---|
| `COPYRIGHT.md` | proprietary rights notice; §5 records the ChatGPT ImageGen origin, the 23-image total and the no-endorsement statement |
| `reports/github-release/GITHUB_PREPARATION.md` | this report |
| `reports/github-release/FINAL_PRE_GIT_CHECKLIST.md` | concise pre-commit checklist |

---

## 14. Recommendation

**Proceed to the first GitHub publication once the Git identity is supplied.**

The privacy, ownership and redistribution concerns are now all closed: no personal
username or local absolute path remains, a proprietary rights notice is in place
with the DejaVu attribution preserved, and the imagery question is settled by owner
approval on a recorded basis.

One requirement remains:

1. **Git identity** — `user.name` and `user.email`. The first commit fails without
   them. Set it at repository scope only (§12.2), after `git init -b main`.

The full pre-commit checklist lives in
`reports/github-release/FINAL_PRE_GIT_CHECKLIST.md`.

Recommended first publication sequence, for approval — **not executed**:

```text
git init -b main
git config user.name  "<owner name>"
git config user.email "<owner email>"
git add .
git status --short          # must show 217 entries
git status --short | Select-String "\.env$|secrets\.toml|\.venv/"   # must show nothing
git commit -m "HOMETSY V1 — initial publication"
git remote add origin <repository url>
git push -u origin main
```

The verify step is mandatory, not advisory — see §7 of the checklist.

The proposed **217-file, 9.08 MB** inventory is clean and complete: no secrets, no
oversized files, no build artifacts, a correct proprietary licensing posture,
preserved third-party notices, 23 approved images, 30 published screenshots,
20 UX evidence screenshots, and documentation whose accessibility claims match its
evidence.

No Git operation has been or will be performed until explicit approval is given.
