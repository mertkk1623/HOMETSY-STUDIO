# Phase 6 — PDF Sample Notes

**Sample:** `reports/phase-6/sample/hometsy-sisli-salonu-report.pdf`
**Size:** 68 116 bytes
**Pages:** 11 (1 cover + 10 body)
**Generated:** deterministically by `generate_report()`, no AI call, no network

---

## 1. What the sample contains

A fully-populated project, so every section has real content:

| Field | Value |
|---|---|
| Room | `Şişli Salonu`, Living Room |
| Dimensions | 400 × 520 cm, ceiling 270 cm, floor area 20.80 m² |
| Openings | door south (offset 60, width 90), window north (offset 120, width 160) |
| Style / palette | Industrial / Warm Neutral |
| Material preference | `meşe` |
| Requirements | "Dört kişilik oturma", "Okuma köşesi" |
| Budget limit | 85.000,00 TRY |
| Concept | Window-Facing Lounge Spine |
| Basket | 8 catalog items, 10 copies |
| Placement | **10 of 10**, status `complete` |
| Layout score | 0.90 |
| Furniture subtotal | 58.600,00 TRY |
| Evaluation | recorded (Turkish) |

The other two concepts (`Perimeter Shelf Spine`, `Reading Corner First`) are
present in state so the report can name the directions that were *not* chosen.

---

## 2. Page map

| Page | Content |
|---|---|
| 1 | **Cover** — brand, project name, room type, area, "Room design report", date. Unnumbered by design. |
| 2 | **B. Project overview** — room, openings, style, palette, materials, requirements, budget limit |
| 3 | **C. Design brief** — summary, functional priorities, constraints, open questions, risks |
| 4 | **D. Selected design concept** — the chosen direction plus the two rejected names |
| 5 | **E. Furniture and materials** — itemised table with quantities and line totals; then the material list marked "Not priced" |
| 6 | **F. Validated 2D room plan** — the drawing, legend, scale note |
| 7 | Placed pieces table — footprint after rotation, rotation, position `(x, y)` in cm |
| 8 | **G. Spatial validation** — status, validity, blocking problems, warnings, score and its framing |
| 9 | **H. Budget analysis** — line totals, subtotal, materials excluded, total |
| 10 | **I. AI design evaluation** — six narrative fields, framed as opinion — and the start of **J. Limitations** |
| 11 | **J. Limitations and disclaimer** — closing attribution and reproducibility note |

Every body page carries the running header
`HOMETSY · Room Intelligence Studio · Şişli Salonu · V1 AI-assisted design report
· illustrative, not a construction drawing or an engineering approval` and a
`Page n of 11` number. The cover is deliberately unnumbered, so the numbering
runs "Page 2 of 11" … "Page 11 of 11".

---

## 3. Content validation performed

Run with the suite's own PDF reader (`tests/test_report_generator.py`), against
the sample file.

### 3.1 Structure

```
bytes=68116  pages=11  header=b'%PDF-1.4'
```

* `%PDF-1.4` header, `%%EOF` trailer, not encrypted.
* `/FontFile2` present twice (regular + bold) — a genuine embedded face.
* `/Count` in the page tree = 11, matching the extracted page count.

### 3.2 All ten sections found, in order

```
p1   Room design report        (A cover)
p2   Project overview          (B)
p3   Design brief              (C)
p4   Selected design concept   (D)
p5   Furniture and materials   (E)
p6   Validated 2D room plan    (F)
p8   Spatial validation        (G)
p9   Budget analysis           (H)
p10  AI design evaluation      (I)
p10  Limitations               (J)
```

### 3.3 Header and page numbers on every page

```
p1  header=yes  number=(cover, unnumbered)
p2  header=yes  number=Page 2 of 11
...
p11 header=yes  number=Page 11 of 11
```

### 3.4 Data fidelity — every printed value traceable to the project

| Check | Expected | Result |
|---|---|---|
| Project name | `Şişli Salonu` | ok |
| Room type | `Living Room` | ok |
| Floor area | `20.80 m²` | ok |
| Dimensions | `400 × 520` | ok |
| Ceiling | `270 cm` | ok |
| Style | `Industrial` | ok |
| Palette | `Warm Neutral` | ok |
| Concept | `Window-Facing Lounge Spine` | ok |
| Material preference | `meşe` | ok |
| Furniture subtotal | `58.600,00 TRY` | ok |
| Budget limit | `85.000,00 TRY` | ok |
| Placement | `All 10 requested items were placed` | ok |
| Sofa footprint | `220 × 90 cm` | ok |
| Armchair quantity | `Armchair` with `2` | ok |
| Evaluation (Turkish) | `Dört kişilik oturma` | ok |
| Score framing | `not a design-quality rating` | ok |

### 3.5 Turkish characters

Letters present in the extracted text layer: **`ç ö ü ğ ı Ş ş`**

* No mojibake (`U+FFFD` absent).
* No garbling of `Şişli` or `meşe`.
* The letters appear because the *project data* is Turkish; the report's own
  prose is English, which is why letters like `Ö` and `Ü` are not present in
  this particular sample. Their round-trip is proven separately by
  `test_turkish_text_survives_into_the_text_layer`, which passes a fully Turkish
  project through the generator and asserts nine Turkish strings plus
  `{ş, Ş, ı, ç, ö, ü}` survive.

### 3.6 The 2D plan

The plan page carries **real vector geometry**, not an image:

* 15 rectangles drawn on the plan's content stream (room boundary, furniture
  footprints, door and window markers).
* Each footprint label shows catalog dimensions (`220 × 90`, `80 × 80`, …).
* Scale note: "Drawn to scale from the coordinates the placement engine
  produced: each rectangle is a catalog footprint after rotation, positioned
  from the room's south-west corner."
* The origin is labelled `Origin (0, 0) · south-west corner, centimetres`.
* The next page repeats every footprint as text: `Three-seat sofa 220 × 90 cm
  0° 180, 0 cm`.

The coordinates in the PDF match those the UI screens show for the same
project — the report presents stored results rather than re-deriving them.

### 3.7 Framing

| Phrase | Present |
|---|---|
| `not a construction drawing` | ok |
| `not an engineering approval` | ok |
| `illustrative` | ok |
| `indicative` | ok |

The evaluation is presented as a critique; the layout score is explicitly "a
heuristic layout score, not a design-quality rating".

### 3.8 No leaks

| Check | Result |
|---|---|
| `api_key` | clean |
| `DEPLOY_API_KEY` | clean |
| `sk-` | clean |
| `Bearer` | clean |
| `Traceback` | clean |
| Absolute filesystem paths | none |

---

## 4. How to regenerate the sample

The sample is produced by a deterministic script (no AI, no network) that builds
a `WorkflowState` from fixed inputs and calls `generate_report()`. Re-running it
on the same catalog and code reproduces the same figures, so the values in §3
can be re-checked at any time.

Output location used for the committed sample:

```
reports/phase-6/sample/
```

Runtime output is separate and ignored by Git:

```
output/reports/          # .gitignore: output/reports/
```

The default runtime directory is created on demand; the filename is always
`hometsy-{sanitized-project-name}-report.pdf`.

---

## 5. Note on the QA copy

A second PDF (76 312 bytes, 14 pages) was produced during the browser
end-to-end run through the real application, with a live AI brief, concepts,
advisor, evaluation and a real download over HTTP. It was **not** kept in the
repository, because `output/reports/` is a runtime directory. Its verification
is recorded in `COMPLETION_REPORT.md` §4.2 and `TEST_REPORT.md` §7.3.
