# HOMETSY — Phase 8: UI/UX Improvement Plan

**Based on:** live inspection of every screen at 1440 / 1024 / 768 / 430 / 404 / 390 / 360 px,
plus a real axe-core 4.10.2 scan of all nine screens.

The five problems below are the ones that actually affect a user's ability to
use the product. Each is stated with the evidence that proves it exists. Nothing
here is speculative or "nice to have".

---

## Problem 1 — The user cannot tell where they are in the journey

**Evidence**

| Symptom | Measurement |
|---|---|
| Three different, contradictory progress vocabularies | Room says `Step 1 of 2`; preferences says `Step 2 of 2`; brief says `Design Concepts · Step 1`; plan says `Design Plan · Step 3`; budget says `Design Plan · Step 5`; the bar simultaneously says `0 of 10 steps complete` |
| "Step 2 of 2" reads as "there are two steps" | Immediately contradicted by the same screen's own bar: `2 of 10 steps complete` |
| The stage strip consumes the first screen on mobile | 5 stages stacked in 2 columns = **221 px of an 844 px viewport (26 %)**; the page title starts at y=486 |
| Nothing on the shell says what to do next | The only guidance is a call-note several hundred pixels down the page |

**Why it matters:** This is the first thing a new user meets, and it is wrong on
every screen. A portfolio reviewer will read it as carelessness.

**Plan**

1. Replace the mixed numbering with the five stages the shell already models:
   `Stage 2 of 5 · Design Preferences`. One vocabulary, consistent everywhere.
2. Make the bar report stage completion, not internal step counts:
   `2 of 5 stages complete`.
3. Let the strip name the current stage in the bar so the strip can become
   compact on narrow screens: a 2-column grid at `max-width: 640px` instead of
   five rows.
4. Emit a single "next" line from the shell, derived from the workflow's own
   `outstanding_steps` — never invented by the page.

**Files:** `ui/shell.py`, `ui/theme.py`, and the one `page_intro` call per page.

---

## Problem 2 — The landing page understates and misdescribes the product

**Evidence**

> "Room information and design preferences are available now and work without
> any AI call. The concept, plan and report stages follow in later development
> steps."

Every one of those stages works and was exercised live this session. The
sentence is a Phase-3 leftover.

`AGENTS.md` §10 forbids presenting implemented features as planned. This
sentence does exactly that, on the page a reviewer reads first.

**Plan**

- Replace it with an accurate description of the start action.
- Make the hero's flow line match the five real stages, so the landing page and
  the workflow use the same words.

**Files:** `ui/pages_landing.py`.

---

## Problem 3 — Real contrast failures (axe-core, `serious`)

**Evidence** — `color-contrast`, impact `serious`, on 4 of 9 screens:

| Element | Foreground | Background | Ratio | Required | Screens |
|---|---|---|---|---|---|
| `.hm-badge` (success) | `#66816A` | `#EEECE5` | **3.61** | 4.5 | room, report, evaluation, budget |
| `.hm-badge` (planned) | `#6E7069` | `#EEECE5` | **4.24** | 4.5 | landing |
| `.hm-call-note` | `#6E7069` | `#EEECE5` | **4.24** | 4.5 | report |

The 11 px uppercase badge text is small, so it gets no large-text exemption.

**Plan**

- Darken the three affected tokens to the nearest value that clears 4.5:1 on
  every approved surface, keeping the hue:

| Token | Before | After | On muted | On background | On white |
|---|---|---|---|---|---|
| `text_secondary` | `#6E7069` | `#5A5C56` | 5.73 | 6.16 | 6.77 |
| `success` | `#66816A` | `#4F6A53` | 5.05 | 5.43 | 5.97 |
| `warning` | `#B88748` | `#8A602C` | 4.69 | 5.04 | 5.54 |
| `error` | `#B65F55` | `#A44A40` | 4.89 | 5.26 | 5.78 |

- Mirror the change in `core.report_generator.PALETTE` (a test asserts the two
  are equal) and update the `DESIGN_SYSTEM.md` palette table so the document
  and the implementation agree.

**Files:** `ui/theme.py`, `core/report_generator.py`, `DESIGN_SYSTEM.md`.

---

## Problem 4 — The cost chart has no accessible alternative

**Evidence** — axe-core `image-alt`, impact `serious`, on the budget screen:

```html
<img src="/media/….png" style="max-width: 100%; width: 998.75px;">
```

A Matplotlib figure rendered by `st.pyplot` with no `alt`. A screen reader
announces an unlabelled graphic; the figures inside it are reachable only by
looking at it.

**Plan**

- Pass a real `alt` to `st.pyplot` that states the chart's content and its
  figures, in the same words the caption uses.

**Files:** `ui/pages_budget.py`.

---

## Problem 5 — The plan drawing is unreadable on a phone and its labels overflow

**Evidence**

- At 390 px the plan SVG renders **324 px wide** from a 640-unit viewBox
  (scale 0.506). Its labels are declared at 9 and 8 user units, so they reach
  the screen at **4.56 px and 4.05 px** — below any legible size.
- At the same width the labels spill outside their blocks: "Sideboard" and
  "Bookshelf" are drawn wider than the rectangles they name.
- The plan is the product's central artefact; a reviewer on a phone sees a grey
  diagram with text too small to read.

**Plan**

- Give the plan frame the same treatment the wide tables already use: a minimum
  drawing width with the frame scrolling horizontally inside itself, so the page
  never overflows but the drawing stays legible.
- Make each block's label honest about the space it has: measure the estimated
  text width against the block, and fall back from the full name to the first
  word, and then to nothing, rather than drawing text that overruns. The full
  name is always in the "Placed pieces" table directly below.

**Implemented outcome — the first-word fallback was rejected.** The plan above
proposed falling back to the first word. On seeing it rendered, that is worse
than no label: "Floor" alone, "Side" alone and "Coffee" alone each name a
*different piece of furniture* than the block drawn, so the fallback silently
misinforms. The implementation wraps the name onto a second line instead, and
drops the label only when the name needs more lines than the block can hold.
`_label_for()` therefore takes `available=` and `max_lines=`, and
`_wrap_label()` returns the whole name across spans. The rest of the plan (the
minimum drawing width, the frame scrolling inside itself) was implemented as
written. See `COMPLETION_REPORT.md` §5 problem 5 for the reasoning and the tests.

**Files:** `ui/diagram.py`, `ui/theme.py`, `ui/pages_plan.py`.

---

## What is deliberately *not* being changed

| Observed | Why it is left alone |
|---|---|
| Streamlit's own chrome (toolbar, "Link to heading", fullscreen) | Vendor UI, not ours; replacing it would fight the framework |
| The single-column 1440 px layout with generous margins | Deliberate: 62–68 ch measure for readability |
| Five summary cards that look alike | They carry words (`COMPLETE`, `IN PROGRESS`), so state is not colour-only — verified |
| `st.multiselect` with `options=[]` for free-text entry | Works, is labelled, and is a Streamlit pattern; replacing it is an architecture change |
| The 10-step internal model | Correct for the workflow; only its *presentation* was wrong |

---

## Verification plan

- Targeted pytest per group, then one full suite run against the 1098 baseline.
- Re-run axe-core on all nine screens and record the before/after violation
  count.
- Re-measure all seven viewports for page overflow after the CSS change.
- Regenerate the PDF and confirm it still builds and that the palette change
  did not break its text.
