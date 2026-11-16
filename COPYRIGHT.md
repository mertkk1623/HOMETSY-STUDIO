# Copyright Notice

**HOMETSY — Room Intelligence Studio**
Copyright © 2026 the project owner. All rights reserved.

## 1. Proprietary status

The HOMETSY source code, application design, user interface, written
documentation, calculation models, test suite, generated reports and the
project's own visual assets are **proprietary and confidential**.

This repository is published for **portfolio and evaluation purposes only**.
Publication does **not** grant a licence to use, copy, modify, merge, publish,
distribute, sublicense, sell, host, deploy or create derivative works from any
part of it.

**No open-source licence is granted.** The absence of a `LICENSE` file is
deliberate. All rights are reserved by the copyright holder. Any use beyond
viewing this repository requires prior written permission.

## 2. No warranty

The software and all project materials are provided **"as is"**, without
warranty of any kind, express or implied, including but not limited to
merchantability, fitness for a particular purpose, accuracy and
non-infringement. In no event shall the copyright holder be liable for any
claim, damage or other liability arising from the software or its use.

The 2D plans, budget figures and furniture costs produced by the application are
**illustrative**, not professional construction drawings, quotations or verified
market prices.

## 3. Third-party components

Third-party material included in this repository remains the property of its
respective owners and is **not** claimed by the project owner. It is included
under the terms of its own licence.

| Component | Location | Terms |
|---|---|---|
| **DejaVu Sans** (fonts) | `assets/fonts/DejaVuSans.ttf`, `assets/fonts/DejaVuSans-Bold.ttf` | Bitstream Vera Fonts Copyright © 2003 Bitstream, Inc.; DejaVu changes are in the public domain; Arev-derived glyphs © 2006 Tavmjong Bah. Full text in `assets/fonts/DejaVu-LICENSE.txt` and reproduced in part in §4 below. |
| **HOMETSY brand assets** (logo, symbol, favicon) | `assets/brand/` | Original assets created for this project. Covered by §1 above — no separate licence is granted. |
| **HOMETSY icon set** (17 line icons) | `assets/icons/` | Original assets created for this project. Covered by §1 above. |
| **HOMETSY hero image** (source) | `assets/images/hero-living-room.png` | Original AI-generated image, produced with ChatGPT ImageGen. Governed by §5 below, the same terms as the reference imagery. |
| **HOMETSY hero image** (runtime) | `assets/images/hero-living-room.jpg` | Downscaled JPEG derivative of the source above, re-encoded to 1280 × 720 for the landing page. Same origin and same terms as the source image; not a separately generated asset. |
| **Inter** (typeface) | **not included** | Inter is the approved typeface in `DESIGN_SYSTEM.md` §4 but is **not bundled** with this project. No Inter font file is present and none is downloaded at runtime; the interface falls back to Arial and then to the system sans-serif. See §6. |
| **Python packages** (Streamlit, Pydantic, Matplotlib, ReportLab, Pytest, and others) | installed at runtime via `requirements.txt`; not vendored here | Each package's own licence |

The DejaVu font licence requires its copyright and permission notices to
accompany every copy of the fonts. `assets/fonts/DejaVu-LICENSE.txt` must be kept
in place and must not be removed or altered.

## 4. DejaVu font licence notice (required attribution)

> Fonts are © Bitstream (see below). DejaVu changes are in public domain.
> Glyphs imported from Arev fonts are © Tavmjong Bah (see below).
>
> **Bitstream Vera Fonts Copyright** — Copyright © 2003 by Bitstream, Inc. All
> Rights Reserved. Bitstream Vera is a trademark of Bitstream, Inc. Permission is
> hereby granted, free of charge, to any person obtaining a copy of the fonts
> accompanying this license ("Fonts") and associated documentation files (the
> "Font Software"), to reproduce and distribute the Font Software, including
> without limitation the rights to use, copy, merge, publish, distribute, and/or
> sell copies of the Font Software, and to permit persons to whom the Font
> Software is furnished to do so, subject to the following conditions: the above
> copyright and trademark notices and this permission notice shall be included in
> all copies of one or more of the Font Software typefaces.
>
> **Arev Fonts Copyright** — Copyright © 2006 by Tavmjong Bah. All Rights
> Reserved. Permission is hereby granted, free of charge, to any person obtaining
> a copy of the fonts accompanying this license ("Fonts") and associated
> documentation files (the "Font Software"), to reproduce and distribute the
> modifications to the Bitstream Vera Font Software, subject to the same
> condition that the copyright and permission notices accompany all copies.

The complete, unmodified licence text is `assets/fonts/DejaVu-LICENSE.txt`. Where
this summary and that file differ, that file governs.

## 5. Reference imagery

The style and palette reference images in `assets/images/` and
`assets/source_pack/` are **original AI-generated illustrative reference sheets
created for this project** — 13 source images and 10 runtime copies, 23 in total.
They were produced with **ChatGPT ImageGen**. No third-party stock photography is
used, and no image contains third-party photographic material.

The project owner asserts rights in these images to the extent such rights subsist
in AI-generated output. Under OpenAI's Terms of Use, output generated through the
service is owned by the user, and OpenAI assigns its right, title and interest in
that output to the user; the same terms note that output may not be unique and
that other users may receive similar output. These images are therefore published
as the project owner's material, without any claim of exclusivity.
`assets/source_pack/asset_manifest.json` records their origin.

The images are illustrative design inspiration — they are **not** photographs of
real projects, products or clients, and no product specifications, prices or
evaluations may be inferred from them. No third-party photographer, agency,
retailer or brand is a source of, or a party to, these images.

**No affiliation or endorsement is claimed.** OpenAI does not sponsor, endorse,
certify or otherwise approve this project, and nothing in this repository should be
read as implying that it does. No OpenAI name, logo or brand asset is included.

No ownership is claimed over any third-party trademark, brand name or product
design that may be referenced descriptively in the furniture catalog or
documentation.

## 6. Typeface status (Inter)

`DESIGN_SYSTEM.md` §4 names **Inter** as the interface typeface. It is **not
included in this repository**:

- no `.woff2`/`.woff`/`.ttf` file for Inter exists under `assets/fonts/`,
- no `@font-face` rule loads one,
- no remote font service is contacted (`AGENTS.md` §11 forbids it),
- `theme.FONT_FAMILY` is `"Inter, Arial, sans-serif"`, which resolves to Arial
  on a machine without Inter and to Inter on one that has it installed.

Adding Inter would require the following files, all under the **SIL Open Font
License, Version 1.1**, together with the verbatim `OFL.txt` that the licence
requires to accompany them:

| File | Weight | Style |
|---|---|---|
| `Inter-Regular.woff2` | 400 | normal |
| `Inter-Medium.woff2` | 500 | normal |
| `Inter-SemiBold.woff2` | 600 | normal |
| `Inter-Bold.woff2` | 700 | normal |
| `OFL.txt` | — | the licence text, unmodified |

They must be obtained from the official Inter release (the `rsms/inter`
project's own distribution) and placed in `assets/fonts/`, and registered through
Streamlit's documented `[[theme.fontFaces]]` table. **No unverified mirror is an
acceptable source.** Until that happens, the interface is set in Arial and this
notice is the accurate statement of that.

Inter is **not** referenced in any PDF: `core.report_generator` embeds **DejaVu
Sans**, whose licence is recorded in §4.

## 7. Reporting infringement

If you believe material in this repository infringes your rights, please contact
the repository owner through the hosting platform so the matter can be resolved.
