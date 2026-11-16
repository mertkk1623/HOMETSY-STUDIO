# Screen-reader verification — NVDA

**Project:** Hometsy — Room Intelligence Studio
**Attempted:** 16 November 2026, 04:13 (local)
**Objective:** replace the outstanding `NOT VERIFIED` screen-reader item with a
real listening session before portfolio publication.

---

## 1. Outcome

> **The manual test could not be performed. NVDA is not installed.**
> **Screen-reader listening remains NOT VERIFIED.**

No installer was downloaded, executed or offered for silent installation, as
instructed. No alternative screen reader was installed. No source file was
changed. Nothing was committed, pushed or deployed.

The single remaining evidence gap before publication is therefore unchanged from
the previous review: the application has been **inspected** structurally, and has
never been **heard**.

---

## 2. NVDA availability check

This was not a single failed lookup. Eight independent locations were checked,
including the places a *portable* NVDA copy would live — NVDA runs without an
installer, so a registry-only check would have been insufficient.

| Check | Result |
|---|---|
| `C:\Program Files\NVDA`, `C:\Program Files (x86)\NVDA` | absent |
| `%LOCALAPPDATA%\NVDA`, `%APPDATA%\NVDA` (user config) | absent |
| `HKLM\SOFTWARE\NVDA` registry key | absent |
| Uninstall registry entries (`DisplayName` matching NVDA / NonVisual / JAWS) | none |
| Start Menu shortcuts (user and all-users) | none — only `Narrator.lnk` and On-Screen Keyboard |
| `nvda.exe` / `nvda` on `PATH` | not found |
| `nvda*.exe` recursive search in Program Files, Program Files (x86), `%LOCALAPPDATA%`, `C:\ProgramData`, `C:\tools`, Downloads, Desktop, temp, `D:\` | none |
| Running processes matching `nvda` / `jaws` / `narrator` | none |

**NVDA version: not applicable — no installation exists.**

**Screen readers present on the machine:** Windows 11 Narrator only
(`C:\Windows\System32\Narrator.exe`). It is a built-in component, not an
installed third-party reader, and it was **not** used as a substitute — see §5.

---

## 3. Official download source

NVDA is free and open source, published by NV Access:

- **Download page:** https://www.nvaccess.org/download/
- Current release at the time of this check: **NVDA 2026.3.1**
- Supports Windows 10 and later (this machine runs Windows 11 Home, build 26200)

Installation requires owner approval and a real listening environment. It was
deliberately not performed, per §1 of the task instructions.

---

## 4. Test environment (recorded, but unused)

Recorded so a future session can resume without re-discovery.

| Item | Value |
|---|---|
| OS | Windows 11 Home, version 10.0.26200, build 26200 |
| Python | 3.13.18 (project-local `.venv`) |
| Application | Streamlit 1.67.0, `app.py`, port 8512 |
| Browsers available | Chrome 157.0.8103.78, Edge 157.0.4341.60 |
| Application state | not started for this task; no project process running; ports 8512 and 8517 free |
| Baseline | 1,149 tests passed, 0 failed, 0 skipped (previously verified, not re-run) |

No environment **change** was made for this task. No Windows accessibility
setting, audio setting or unrelated system setting was touched.

---

## 5. Why Narrator was not used as a substitute

Narrator is present, but it is not an acceptable substitute here:

1. **The evaluator cannot hear.** Narrator speaks through the system audio
   device. This session has no audio perception, so a Narrator run would produce
   sound that nobody in this process could evaluate. Capturing audio and
   transcribing it is not the same instrument: it re-introduces a text pipeline
   and stops being a listening test at all.
2. **The instruction was explicit.** Alternative screen readers were not to be
   installed or substituted.
3. **A silent run would be worse than no run.** Running Narrator, hearing
   nothing, and recording a pass would be exactly the kind of fabricated evidence
   `AGENTS.md` §12 forbids.

Recommendation for whoever completes this: NVDA is the better instrument anyway
— it is the reference reader for this kind of markup review, it exposes a speech
viewer and a log, and its browse-mode behaviour around `h1`–`h3`, `role=status`
and named buttons is well documented.

---

## 6. Scope that remains untested

The intended scope is preserved so the follow-up session is a checklist, not a
design exercise. All three areas are **NOT VERIFIED**.

### A. Room definition

| Check | Status |
|---|---|
| Page title and main `h1` announced | **NOT VERIFIED** |
| Room name input | **NOT VERIFIED** |
| Room type selection | **NOT VERIFIED** |
| Width and length inputs, label comprehensibility | **NOT VERIFIED** |
| Door and window controls | **NOT VERIFIED** |
| Required fields and validation errors | **NOT VERIFIED** |
| Primary action buttons | **NOT VERIFIED** |
| Keyboard navigation and focus order | **NOT VERIFIED** |

### B. 2D spatial plan

| Check | Status |
|---|---|
| Plan section heading | **NOT VERIFIED** |
| Room dimensions and area | **NOT VERIFIED** |
| Door and window descriptions | **NOT VERIFIED** |
| Placement status COMPLETE / PARTIAL / FAILED | **NOT VERIFIED** |
| Furniture names and placement information | **NOT VERIFIED** |
| Blocking errors and warnings | **NOT VERIFIED** |
| Action buttons | **NOT VERIFIED** |
| SVG accessible description actually usable, not merely present | **NOT VERIFIED** |

The last row is the one this project most needs: a good `aria-label` that is
never announced, announced twice, or announced without the surrounding context is
indistinguishable from a correct one until someone listens.

### C. Final report

| Check | Status |
|---|---|
| Report section heading | **NOT VERIFIED** |
| Readiness / generation status announced | **NOT VERIFIED** |
| Generate report button | **NOT VERIFIED** |
| Success or error feedback announced | **NOT VERIFIED** |
| PDF download control has a meaningful name | **NOT VERIFIED** |
| Keyboard access to the download action | **NOT VERIFIED** |

**Keyboard interactions tested: none.** No `Tab`, `Shift+Tab`, `Enter`, `Space` or
arrow-key sequence was evaluated through a screen reader, so no announcement,
focus-loss, unreachable-control or unannounced-status finding can be reported.

**Defects found: none.** Not because the interface is proven correct, but because
no test was executed. This report must not be read as a clean result.

---

## 7. Per-section verdicts

| Section | Verdict |
|---|---|
| A. Room definition | **NOT VERIFIED** |
| B. 2D spatial plan | **NOT VERIFIED** |
| C. Final report | **NOT VERIFIED** |
| NVDA listening session performed | **NO** |
| Screen-reader compatibility claim permitted | **NO** |
| WCAG conformance claim permitted | **NO** |

---

## 8. What *is* verified about accessibility

Recorded so the gap is not mistaken for total absence of evidence. None of the
following is a substitute for listening.

| Evidence | Result | Source |
|---|---|---|
| Automated axe-core 4.10.2 scan, 9 screens | **0 violations** | `reports/phase-8/RELEASE_READINESS.md` §4 |
| Axe's `page-has-heading-one` reliability | **unreliable** — passed a page with zero `h1` | found during portfolio review |
| Heading outline, all 9 screens, live tree | **1 `h1` per screen, no level skips** | `reports/portfolio-release/RELEASE_READINESS.md` §3.3 |
| Heading structure regression tests | **26 tests**, mutation-verified twice | `tests/test_ui_headings.py` |
| Accessibility tree inspection | headings, labels, button names, `role=status`, download control present | portfolio review |
| Keyboard operability (source/focus styles) | skip link, visible focus, focusable plan frame | Phase 8 |
| Contrast | 4.5:1 minimum, asserted | Phase 8 |
| Heading fix visual impact | pixel-identical | `RELEASE_READINESS.md` §3.5 |

The distinction that matters: **a correct tree is necessary but not sufficient.**
The defect found during the portfolio review — `h2` page titles and `<p>` section
headings — was invisible to axe and obvious to the tree. A listening session is
the next layer, and it is the layer that has never been applied.

---

## 9. Standing limitations

1. **No listening session has ever been performed** on this application.
2. **Reading order, announcement timing, verbosity and pronunciation** are
   entirely unverified.
3. **No screen-reader compatibility or WCAG conformance is claimed** anywhere in
   the documentation, and none should be inferred from this report.
4. The material in §8 is structural and automated evidence only.

---

## 10. How to complete this task

Roughly 30 minutes, no code change, no new dependency:

1. Install NVDA from https://www.nvaccess.org/download/ (owner approval), or run a
   portable copy.
2. Start the application:
   `.venv\Scripts\python.exe -m streamlit run app.py --server.port 8512 --server.headless true --browser.gatherUsageStats false`
3. Use a fresh browser session — editing source while Streamlit runs causes the
   known `WorkflowState` `TypeError`.
4. Open NVDA's speech viewer so announcements are recorded as text as well as
   speech, then walk §6 A → B → C with `H`, `Tab`, `Enter`, `Space` and arrows.
5. Record each announcement verbatim in a report modelled on this one, replacing
   `NOT VERIFIED` with `PASS`, `PARTIAL` or `FAIL`.
6. Fix only genuine defects, with a focused regression test, per §5 of the task
   instructions.

Only after step 5 may the screen-reader item in `RELEASE_READINESS.md` change
status.
