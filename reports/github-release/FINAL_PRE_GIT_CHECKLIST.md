# Final pre-Git checklist — HOMETSY first publication

**Project:** Hometsy — Room Intelligence Studio
**Prepared:** 16 November 2026
**Scope:** everything that must be true *before* the first Git command is run.
**Status:** preparation only — **no Git repository exists, nothing was staged,
committed, pushed or deployed.**

Companion document: `reports/github-release/GITHUB_PREPARATION.md` (full audit).

---

## 1. Publication inventory

Measured against the filesystem. The working directory and the tracked inventory
are different numbers, and the gap is almost entirely `.venv`.

| Measure | Files | Size |
|---|---|---|
| **Files present in the working directory** (excluding `.git`, which does not exist) | **13,902** | **~443 MB** |
| `.venv/` virtual environment | −13,575 | — |
| Python / pytest caches | −104 | — |
| `output/reports/` runtime PDFs | −6 | — |
| **Proposed tracked-file inventory** | **217** | **9.08 MB** |

13,902 − 13,685 excluded = **217 tracked**. The two columns measure different
things: ~443 MB is what sits on disk, 9.08 MB is what would be committed. The disk
figure moves by a few KB whenever these two documents are edited, so it is rounded;
the tracked total is 9.08 MB at the time of writing and can be re-derived at any
time with the one-line check in §7.

> **Note on the figure.** An earlier revision of this checklist recorded
> **196 files / 7.60 MB**. That count was correct before the final UX polish pass
> and is superseded here. The 21 additional files are the polish deliverables,
> itemised in §1.1.

### 1.1 What changed since the 196-file count

The final UX polish pass added **21 files** under `reports/final-ux-polish/` and
modified **7** existing `ui/` presentation modules. No other tracked path was
added or removed.

| Added by the polish pass | Files | Size |
|---|---|---|
| `reports/final-ux-polish/COMPLETION_REPORT.md` | 1 | 22.2 KB |
| `reports/final-ux-polish/evidence/*.png` — UX evidence | 20 | 1,502 KB |
| **Total added** | **21** | **~1.49 MB** |

The 20 UX evidence screenshots split **13 `after-*.png`** (the changed screens in
their new state) and **7 `before-*.png`** (the same screens before the change, for
comparison). They are **working evidence for the polish report, not portfolio
material**: they are deliberately *not* part of the 10-image portfolio selection in
`docs/screenshots/portfolio/`, which remains unchanged in size and membership.

Two published screenshots were also **replaced in place**, not added:
`docs/screenshots/11-design-plan.png` and `docs/screenshots/13-spatial-validation.png`
were re-captured at the same 1440 × 1000 size so that the public documentation
shows the reordered plan screen. The file count is unaffected; the `docs/` size
drops slightly because the two new captures are smaller than the two they replace.

Because of those two replacements, the portfolio duplicates
`docs/screenshots/portfolio/05-furniture-recommendations.png` and
`…/07-spatial-validation.png` are no longer byte-identical to their originals
`11-design-plan.png` / `13-spatial-validation.png`. This is intentional: the
portfolio set is a frozen narrative selection, and its files were left untouched.

### By area

| Area | Files | Size |
|---|---|---|
| `(root)` | 14 | 122.1 KB |
| `.streamlit/` | 1 | 0.3 KB |
| `ai/` | 10 | 85.1 KB |
| `assets/` | 29 | 2,628.7 KB |
| `core/` | 8 | 165.5 KB |
| `data/` | 4 | 15.2 KB |
| `docs/` | 31 | 3,177.4 KB |
| `models/` | 2 | 20.8 KB |
| `reports/` | 66 | 2,159.6 KB |
| `tests/` | 28 | 635.8 KB |
| `ui/` | 21 | 249.5 KB |
| `workflow/` | 3 | 42.2 KB |
| **Total** | **217** | **9.08 MB** |

`reports/` grew from 45 to 66 files: the 21 polish deliverables in §1.1.
`docs/` stays at 31 files — 30 screenshots plus the case study — with two of the
30 replaced in place rather than added.

### Explicitly included

- Source: `app.py`, `ai/` (9), `core/` (7), `ui/` (21), `models/` (2),
  `workflow/` (3), `tests/` (28) — **71 Python files** (70 in package
  directories plus `app.py`)
- Data: `data/` (4)
- **All 23 approved images** — 13 in `assets/source_pack/`, 10 in `assets/images/`
- **30 screenshots** — 20 in `docs/screenshots/`, 10 in `docs/screenshots/portfolio/`.
  Two of the 20 (`11-design-plan.png`, `13-spatial-validation.png`) were re-captured
  after the plan screen was reordered; the rest are the original captures.
- **20 UX evidence screenshots** — `reports/final-ux-polish/evidence/`, working
  evidence for the polish report. Deliberately **not** part of the portfolio
  selection.
- Fonts: 2 `.ttf` + `DejaVu-LICENSE.txt`
- Documents: `README.md`, `README.tr.md`, `COPYRIGHT.md`, `AGENTS.md`,
  `PROJECT_BRIEF.md`, `TECHNICAL_ARCHITECTURE.md`, `DESIGN_SYSTEM.md`,
  `DEVELOPMENT_PLAN.md`, `docs/PORTFOLIO_CASE_STUDY.md`
- Config: `.streamlit/config.toml`, `pytest.ini`, `requirements.txt`,
  `opencode.json`, `.env.example`, `.gitignore`
- Reports: 66 files including the sample PDF
  `reports/phase-6/sample/hometsy-sisli-salonu-report.pdf`, the polish report and
  its **20 UX evidence screenshots** (§1.1)

### Explicitly excluded

| Excluded | Why |
|---|---|
| `.venv/` (13,575 files) | reproducible from `requirements.txt` |
| `__pycache__/`, `.pytest_cache/` (104 files) | bytecode and test caches |
| `output/reports/` (6 PDFs) | runtime-generated, reproducible from saved project data |
| `.env`, `.env.*` | **secrets** — `.env.example` is explicitly re-included via `!.env.example` |
| `.streamlit/secrets.toml` | **secrets** — absent from disk |
| logs, `*.tmp`, `*.bak`, `*.sqlite`, `*.db` | local runtime artifacts |
| `.playwright/`, browser profiles, `test-results/` | automation residue |
| `.DS_Store`, `Thumbs.db`, `.idea/`, `.vscode/` | OS and editor noise |

`.gitignore` was re-checked against the required content: **no rule excludes any
path under `assets/`, `docs/`, `data/` or the repository root.** All required
assets and documentation are tracked.

---

## 2. Security status

| Check | Result |
|---|---|
| API key in any tracked file | **none** — key read from environment only |
| `.env` present on disk | **no** |
| `.streamlit/secrets.toml` present | **no** — correctly absent |
| Credentials, tokens, passwords in source | **none** |
| Secrets in report/history files | **none** — two redaction *test fixtures* (`C:\secret\path`) are invented strings, not real paths |
| `sk-` tokens in the tree | **none real** — one appears in `tests/test_ai_config.py` and the two release reports as a redaction fixture (`sk-abcdef1234567890`); it is a deliberate test input, not a credential |
| Placeholder credentials in READMEs | **expected** — `API_KEY = "your-key-here"` / `"anahtar-buraya"` are documentation placeholders |
| Personal Windows username in tracked files | **none** — 33 occurrences sanitized, verified 0 remaining |
| Local absolute project path in tracked files | **none** — replaced with `[PROJECT_ROOT]` |
| Local downloads path in tracked files | **none** — replaced with `[LOCAL_DOWNLOADS]` |
| Files over 100 MB | **0** — largest is `DejaVuSans.ttf` at 738 KB |
| Files over 1 MB | **0** |
| Git LFS required | **no** |
| Path length risk | **none** — longest tracked relative path 71 chars, longest tracked absolute 108, limit 260. Both are UX evidence PNGs under `reports/final-ux-polish/evidence/`. The longest path anywhere in the tree (166 / 203) is excluded `.venv` content. |

`.env.example` is included on purpose; it contains variable **names**, not values.

---

## 3. Image decision — Option A, approved

**Decision: all 23 HOMETSY images are IN the publication inventory.**

| Item | Value |
|---|---|
| Origin | **ChatGPT ImageGen**, generated for this HOMETSY project |
| Source-pack images | 13 |
| Runtime copies in `assets/images/` | 10 |
| **Total included** | **23** |
| Deleted / relocated / modified | **none** |
| Third-party stock | **none** |
| Attribution required | **none** — no third-party photographer or agency |

**Rights basis.** OpenAI's Terms of Use (effective 1 January 2026, checked 16
November 2026) state, under *Ownership of content*: *"As between you and OpenAI,
and to the extent permitted by applicable law, you (a) retain your ownership rights
in Input and (b) own the Output. We hereby assign to you all our right, title, and
interest, if any, in and to Output."* Publishing the images is distribution of the
owner's own Output. Note the two qualifiers built into that sentence — *between you
and OpenAI*, and *to the extent permitted by applicable law* — so this is a
permission from OpenAI, not a universal clearance against every possible claim.

**Two honest limits:**

- Output may not be unique — the same terms say *"other users may receive similar
  output"*, and the assignment does not extend to other users' output. The
  repository makes **no exclusivity claim**.
- Provenance rests on the two manifests plus the owner's confirmation. The JPEGs
  carry **no embedded C2PA or provenance metadata** (checked directly), so the
  record is documentary rather than technical.

The terms themselves govern and can change; this records the basis relied on at
publication time, not a standing legal opinion.

**No endorsement claim.** Nothing states or implies that OpenAI sponsors, endorses,
certifies or is affiliated with HOMETSY. No OpenAI name, logo or brand asset is
used anywhere in the repository.

The `modern.jpg` / `minimalist.jpg` pair ships as **source-pack provenance only**.
They remain retired from the product (`retained_excluded` in
`data/asset_replacements.json`) and are never displayed. Product decision, not a
rights one.

---

## 4. Proprietary rights status

| Item | State |
|---|---|
| `COPYRIGHT.md` | **present** — proprietary, all rights reserved |
| Root `LICENSE` file | **absent** — deliberate |
| Open-source licence granted | **none** |
| Publication grants any licence | **no** — portfolio and evaluation viewing only |
| DejaVu font notice | **preserved** at `assets/fonts/DejaVu-LICENSE.txt` |
| DejaVu attribution in `COPYRIGHT.md` | **present**, §3–§4 |
| Third-party ownership claimed | **no** — disclaimed explicitly |
| OpenAI endorsement implied | **no** — explicitly disclaimed |

`COPYRIGHT.md` must remain in the repository and must not be replaced with an
open-source licence without an explicit owner decision. The DejaVu licence file
must not be removed: its terms require the notice to accompany the fonts.

---

## 5. Initial branch

**Use `main`.**

Git's system default here is `master`, so the branch must be named at creation:

```text
git init -b main
```

This also sets the upstream name correctly for `git push -u origin main`. No
branch has been created and no global setting was changed.

Note: `core.autocrlf=true` is set at system scope on this machine. Working-tree CRLF
becomes LF in the repository. That is expected Windows behaviour and nothing in
the tree depends on preserving CRLF.

---

## 6. Remaining requirement — Git identity

**This is the only blocker.**

`user.name` and `user.email` are **unset at global, system and local scope**. A
commit cannot be created until they are supplied. No value was invented and no
scope was modified.

Set them **at repository scope only**, after `git init`:

```text
git config user.name  "<your name>"
git config user.email "<your email>"
```

Choose deliberately: this name and email become **public and permanent** in the
commit history. If a noreply address is preferred, use the one GitHub provides for
the account.

---

## 7. Exact next actions before the first commit

For approval — **none of these has been run.**

```text
# 1. Create the repository on the main branch
git init -b main

# 2. Supply the identity (owner input required)
git config user.name  "<owner name>"
git config user.email "<owner email>"

# 3. Stage everything
git add .

# 4. VERIFY before committing — must show 217 files and no secrets
git status --short | Measure-Object -Line
git status --short | Select-String "\.env$|secrets\.toml|\.venv/"

# 5. Commit
git commit -m "HOMETSY V1 — initial publication"

# 6. Attach the remote and publish
git remote add origin <repository url>
git push -u origin main
```

Step 4 is not optional. `git status --short` should list **217** entries
(`A`/`??`), and the second command should return **nothing**. If it returns a
match, stop: something that should be ignored is being staged.

### Pre-flight confirmation

- [ ] Git identity supplied at repository scope
- [ ] Branch is `main`
- [ ] `git status --short` shows 217 files
- [ ] No `.env`, `secrets.toml` or `.venv/` in the staged set
- [ ] `COPYRIGHT.md` is staged
- [ ] All 23 images and 30 screenshots are staged
- [ ] The 21 polish deliverables (`reports/final-ux-polish/`) are staged
- [ ] Remote URL known and correct

---

## 8. Disclosed limitations — not blockers

| Item | Status |
|---|---|
| Screen-reader listening session | **NOT VERIFIED** — NVDA absent, never installed. No WCAG conformance claim is made or permitted. |
| Accessibility evidence | Structural inspection only; `RELEASE_READINESS.md` and `SCREEN_READER_TEST.md` say so plainly. |
| 2D plans | Illustrative, **not** professional construction drawings. |
| Budget figures | Indicative, **not** verified market prices. |
| Test suite | 1,149 passed / 0 failed / 0 skipped, previously verified. **Not rerun for this task**, because no `.py` file was modified. |
| GitHub CLI | Not installed — remote creation must use the web UI. |
| Reference-image provenance | Documentary, not technical: the 23 JPEGs carry no embedded C2PA or provenance metadata. |

---

## 9. Bottom line

The tree is publication-ready. Inventory verified at **217 files / 9.08 MB**,
security clean, imagery approved with a recorded rights basis, proprietary notice
in place, `.gitignore` confirmed non-destructive.

The 21 polish deliverables in `reports/final-ux-polish/` are included as working
evidence, and the two re-captured screenshots show the current plan order. Neither
changes the product, the portfolio selection or the security posture.

**One action remains: supply the Git identity.** Then follow §7 exactly, verifying
step 4 before committing.

No Git operation has been performed. No repository exists. No remote was created.
No deployment occurred.
