# Screenshot selection — portfolio presentation

**Date:** 16 November 2026
**Scope:** select the strongest 8–10 images from the existing 20 for portfolio use.

## Decision

Ten images were selected into `docs/screenshots/portfolio/`. The originals are
**unchanged and complete** in `docs/screenshots/` (all 20 remain). The selection
folder contains copies, renamed in narrative order so the portfolio sequence
reads correctly without a separate index file.

No screenshot was fabricated, mocked up or synthetically generated. No screenshot
was recaptured for this selection: every candidate was checked against the
running application and the current source, and all 20 were still accurate.

## Selected images

| # | Portfolio file | Source | Demonstrates |
|---|---|---|---|
| 1 | `01-product-identity.png` | `01-landing.png` | Landing page, product identity, five-stage journey, honest V1/V2/V3 roadmap |
| 2 | `02-room-definition.png` | `02-room-setup.png` | Room definition: centimetre input, door/window placement, live preview |
| 3 | `03-design-preferences.png` | `03-design-preferences.png` | Design preferences: six styles, four palettes, requirements, budget |
| 4 | `04-ai-design-concepts.png` | `08-design-concepts.png` | AI design concepts: three directions, style reference captioned as illustrative |
| 5 | `05-furniture-recommendations.png` | `11-design-plan.png` | Furniture recommendations: model-chosen catalog pieces with catalog size and rationale |
| 6 | `06-2d-floor-plan.png` | `12-plan-drawing.png` | 2D plan: drawn to scale from real coordinates, rotation applied, origin marked |
| 7 | `07-spatial-validation.png` | `13-spatial-validation.png` | Spatial validation: placed sizes, rotations, positions, engine verdict |
| 8 | `08-design-evaluation.png` | `15-design-evaluation.png` | AI design evaluation beside the deterministic spatial and budget results |
| 9 | `09-budget-analysis.png` | `16-budget-analysis.png` | Budget analysis: indicative total, limit, remaining budget, per-item arithmetic |
| 10 | `10-pdf-report.png` | `18-final-report.png` | PDF report: the generated A4 report ready to download |

All ten required portfolio themes are covered:

- product identity and landing — #1
- room definition — #2
- design preferences — #3
- AI design concepts — #4
- furniture recommendations — #5
- 2D spatial plan — #6 (with #7 for the validation evidence)
- evaluation and budget — #8 and #9
- final PDF/report experience — #10

## Images deliberately not selected

| File | Why it is not in the selection |
|---|---|
| `04-project-review.png` | Accurate and useful, but the review screen is an intermediate step; #2 and #3 already establish the input story. Available as supporting evidence. |
| `05-brief-before-ai.png` | A "before pressing the button" state. Valuable for workflow proof, weaker as a portfolio image than an actual result. |
| `06-brief-analysed.png` | Strong content, but the brief's structured output is largely visible again in the PDF (#10) and the concepts (#4). Kept as supporting evidence. |
| `07-concepts-before-ai.png` | Superseded by #4, which shows the generated concepts. |
| `09-concept-selected.png` | Shows the selection step; #4 already conveys the concept comparison and the selected state is a small badge. Kept for the workflow narrative. |
| `10-plan-before-advisor.png` | Pre-AI state; superseded by #5. |
| `14-evaluation-before-ai.png` | Pre-AI state; superseded by #8. |
| `17-cost-distribution.png` | A good chart, but #9 already carries the budget story with figures and arithmetic. Kept as supporting evidence. |
| `19-plan-mobile-390.png` | Referenced separately in the README/case study as responsive evidence rather than as a primary portfolio image. |
| `20-budget-mobile-390.png` | Same: responsive evidence, not a primary image. |

The full collection is therefore still reachable from the documentation: the
README embeds 14 images and links both mobile captures, and the case study links
both mobile captures.

## Verification performed

Each selected image was opened and checked against the current implementation:

- **Content is current.** The roadmap in #1 shows V1 badged *Complete* (the stale
  "In development" label was fixed and the screenshot recaptured during Phase 8).
  No screen still shows a removed or renamed control.
- **Visual consistency.** All ten share the same shell, stage strip, palette,
  typography and spacing. They come from one continuous session (Şişli Living
  Room, 400 × 500 cm, Japandi, Warm Neutral) so figures agree across images:
  20.00 m², 7 of 7 placed, 42.200,00 TRY total against a 45.000,00 TRY limit.
- **Readability.** Text is legible at native 1440 px width; the 2D plan (#6) is
  shown in its own capture so labels are not shrunk by page-level framing.
- **No secrets.** No key, token, path or hostname appears in any image.
- **No fabricated evidence.** Every image is a browser capture of the running
  application, not a mockup, and the PDF shown is a real generated file.

## Honest caveats

- The screenshots are from one saved project. They illustrate the application's
  behaviour; they are not a survey of different rooms or styles.
- The AI-written text inside #4, #5 and #8 is genuine model output from that
  session. Model output varies between runs, so a reviewer running the app will
  see different wording for the same inputs. The deterministic figures
  (dimensions, positions, totals) reproduce exactly.
- The landing screenshot shows the roadmap as it exists today: V1 complete, V2
  and V3 marked planned and not implemented.
- Images were not recaptured after the heading-semantics fix, because that fix
  was verified to be **pixel-identical** on the landing, room, preferences and
  review screens (see `RELEASE_READINESS.md` §4). Recapturing would have produced
  byte-identical images apart from the transient scrollbar.
