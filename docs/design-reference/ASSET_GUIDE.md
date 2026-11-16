# HOMETSY UI V2 — Asset Pack

This pack contains original visual assets prepared as a starting point for the HOMETSY UI V2 redesign.

## Contents

- `brand/hometsy-logo.svg`: primary horizontal wordmark.
- `brand/hometsy-logo-light.svg`: light version for dark surfaces.
- `brand/hometsy-symbol.svg`: standalone architectural mark.
- `brand/favicon.svg` and `favicon-*.png`: favicon variants.
- `images/hero-living-room.png`: original generated interior hero image (1672 × 941).
- `icons/`: individual SVG line icons plus `icons.svg` sprite.
- `reference/hometsy-ui-v2-design-board.png`: visual direction board; reference only, not production UI.

## Suggested destination

Copy the folders into the repository's existing `assets/` directory, preserving this structure:

```text
assets/
  brand/
  images/
  icons/
```

Keep the design board in `docs/design-reference/` if desired; it is not a runtime asset.

## Approved visual direction

- Warm ivory: `#F5F3EE`
- Charcoal: `#252A28`
- Muted olive: `#858A70`
- Terracotta: `#BD8065`
- Supporting surface: `#E9E6DF`
- Supporting line: `#D8D8D2`

**Important:** The existing app/PDF color-token coupling was identified in the Phase 0 audit. Treat the swatches above as visual reference only; do not change existing application or PDF token values without a separate approval.

## Font

Inter is specified as the intended UI typeface, but font binaries are intentionally not bundled. Obtain the official Inter OFL release, include its license text in the project, and verify the font files before configuring Streamlit. Do not fetch fonts from remote URLs at runtime.

## Usage notes

- Use the logo SVG as a brand asset, not as a replacement for accessible text labels.
- SVG icons use `currentColor` in the sprite; individual files use `#252A28` and can be recolored deliberately.
- Use the hero image with `cover` cropping and a responsive focal point.
- The design board is a mood/reference sheet; do not slice UI mockups out of it and present them as working screens.
- All interior imagery is illustrative, not a representation of actual catalog furniture or verified products.
