# HOMETSY — ROOM INTELLIGENCE STUDIO

**Design System — V1.0**

## 1. Design Direction

Room Intelligence Studio should feel like a modern digital interior design studio.

The interface must communicate:

- Professionalism
- Creativity
- Spatial awareness
- Simplicity
- Trust
- Attention to detail

The visual direction should combine editorial interior design aesthetics with a clean, modern software interface.

The application must not look like a generic AI chatbot or a default Streamlit dashboard.

### Design Principles

1. Visual quality over decorative complexity.
2. Clear information hierarchy.
3. Large, meaningful visual references.
4. Consistent spacing and typography.
5. Minimal unnecessary interface elements.
6. Clear distinction between user input, AI output, and calculated results.
7. Desktop-first responsive layout.
8. Consistent visual language between the application and generated PDF.

## 2. Brand Identity

**Product:** Hometsy — Room Intelligence Studio

**Positioning:** AI-assisted interior design and spatial planning.

**Brand personality:**

- Modern
- Refined
- Warm
- Intelligent
- Practical
- Minimal

The product should feel closer to a premium interior design studio than a technical engineering application.

### Brand Usage

The product name should appear consistently in:

- Application header
- Navigation
- Report cover
- PDF footer
- README screenshots

The interface should use the full product name on the landing page and a compact brand treatment within the application workflow.

## 3. Color System

The primary color palette should be warm, neutral, and restrained.

| Token | Color | Usage |
|---|---|---|
| Primary | `#4B5147` | Primary actions and selected states |
| Primary Dark | `#343A32` | Strong emphasis |
| Background | `#F6F4EF` | Main application background |
| Surface | `#FFFFFF` | Cards and content surfaces |
| Surface Muted | `#EEECE5` | Secondary backgrounds |
| Text Primary | `#292B27` | Main text |
| Text Secondary | `#5A5C56` | Supporting text |
| Border | `#E4E1D9` | Dividers and card borders |
| Success | `#4F6A53` | Successful validation |
| Warning | `#8A602C` | Warnings and budget attention |
| Error | `#A44A40` | Errors and critical issues |

> **Contrast note (Phase 8).** Text Secondary, Success, Warning and Error were
> darkened from their original values after a real axe-core scan measured them
> below the WCAG 2.1 AA minimum of 4.5:1 on the Surface Muted background —
> 3.61:1 for the success badge and 4.24:1 for secondary text. Each value above is
> the nearest hue match that clears 4.5:1 on all three surfaces the product uses
> (Surface Muted, Background, Surface). The 11px uppercase badge text has no
> large-text exemption, so these values are what make the badges legible.


### Color Usage Rules

- Use the primary green sparingly.
- Avoid excessive saturated colors.
- Do not use gradients as a default design treatment.
- Avoid large decorative color blocks.
- Maintain sufficient text contrast.
- Use status colors consistently.

The design should remain visually calm even when displaying detailed information.

## 4. Typography

The interface should use a clean sans-serif typography system.

Preferred font:

**Inter**

Fallback:

- Arial
- Sans-serif

### Typography Hierarchy

| Element | Recommended Size | Weight |
|---|---:|---|
| Main page heading | 32–36 px | 600 |
| Section heading | 22–26 px | 600 |
| Card heading | 16–18 px | 600 |
| Body text | 14–16 px | 400 |
| Supporting text | 12–13 px | 400 |
| Small labels | 11–12 px | 500 |

Typography should be consistent across the application.

Avoid oversized headings, unnecessary uppercase labels, and excessive font-weight variations.

## 5. Layout and Spacing

The interface should use a consistent spacing scale.

| Token | Value |
|---|---:|
| XS | 4 px |
| SM | 8 px |
| MD | 16 px |
| LG | 24 px |
| XL | 32 px |
| 2XL | 48 px |
| 3XL | 64 px |

### Layout Rules

- Use a centered content area.
- Avoid excessively wide text sections.
- Maintain consistent horizontal alignment.
- Use generous spacing between major sections.
- Keep form controls visually grouped.
- Use cards only when they improve content organization.
- Avoid unnecessary nested cards.

The main content should remain readable on typical laptop and desktop screens.

## 6. Interface Structure

The application should use a guided, multi-stage workflow.

### 6.1 Landing Page

The landing page introduces the product and guides the user into the room planning process.

Required elements:

- Product branding
- Main headline
- Short product explanation
- Primary start action
- Brief feature overview
- V1 / V2 / V3 roadmap

The landing page should communicate the main workflow visually:

**Define Your Room → Explore Concepts → Plan Your Space → Generate Your Report**

The roadmap must distinguish implemented V1 features from planned V2 and V3 features.

### 6.2 Workflow Navigation

The main workflow should use a clear progress indicator.

Recommended stages:

1. Room Setup
2. Design Preferences
3. Design Concepts
4. Design Plan
5. Final Report

The user should always understand:

- Which stage they are in.
- What information is required.
- What the next action will do.
- Whether a previous stage has been completed.

Do not display all stages as equally prominent content at once.

### 6.3 Room Setup

The room configuration interface should be organized into logical sections.

**Room Information**
- Room type
- Room name
- Width
- Length
- Ceiling height

**Openings**
- Door position
- Door width
- Window position
- Window width

Use clear dimension labels and centimeter units.

Where possible, provide a small visual explanation of room orientation and opening positions.

### 6.4 Design Preferences

The style selection interface should use image cards.

Each style card must contain:

- Local reference image
- Style name
- Short description
- Clear selected state

The six available styles:

- Warm Minimalism
- Scandinavian
- Japandi
- Contemporary
- Industrial
- Bohemian

Palette selection should follow the same visual language.

Each palette card should include:

- Reference image or visual swatch
- Palette name
- Short description

Selected cards should use a subtle border and clear selection indicator.

Avoid excessive animations or complicated hover effects.

### 6.5 Budget and Requirements

The budget section should be simple and understandable.

It must include:

- Total estimated budget
- Functional requirements
- Additional notes

Use short helper text to explain that catalog prices are illustrative estimates.

Avoid making the interface resemble accounting software.

### 6.6 Design Concepts

The three AI-generated concepts should be displayed as comparable cards.

Each concept card should show:

- Concept name
- Short description
- Main design direction
- Color and material direction
- Furniture approach
- Budget suitability
- Selection action

The selected concept must be visually distinguishable.

The interface should make comparing three alternatives easy.

### 6.7 Design Plan

The selected concept page should present:

- Design summary
- Furniture recommendations
- Material recommendations
- 2D room layout
- Spatial warnings
- Estimated budget allocation

The 2D plan should receive sufficient visual space.

Do not shrink the room layout into a small decorative thumbnail.

Spatial warnings should be easy to distinguish from informational notes.

### 6.8 Final Report

The final report page should provide:

- Project summary
- Selected concept summary
- Spatial validation status
- Budget summary
- Design evaluation
- PDF download action

The download action should be prominent and easy to find.

## 7. Cards and Components

### Design Reference Cards

- Consistent aspect ratio
- Large image area
- Short supporting description
- Clear selection state
- Subtle border
- Consistent internal spacing

### Concept Cards

- Clear concept title
- Readable description
- Compact supporting details
- Visible budget suitability
- Distinct selection action

### Metric Components

Use simple metric displays for:

- Room area
- Total estimated budget
- Estimated expenditure
- Remaining budget

Avoid excessive dashboard-style KPI components.

### Status Components

Use consistent statuses:

- Valid
- Warning
- Error
- Planned

Do not use color alone to communicate status. Include text labels.

## 8. Iconography

Use a consistent, minimal icon family.

Icons should support navigation and information recognition.

Preferred approach:

- Lucide-style line icons
- Consistent stroke weight
- Consistent size
- No decorative icon overload

Avoid mixing multiple unrelated icon styles.

## 9. Image and Asset Guidelines

Visual reference images are a core part of the product experience.

### Style Images

The interface must include one primary reference image for each of the six supported styles.

### Palette Images

The interface must include one reference image or designed swatch for each of the four palette categories.

### Image Requirements

- Use locally stored assets.
- Prefer landscape or square compositions appropriate for cards.
- Maintain consistent image presentation.
- Avoid watermarked images.
- Avoid visibly low-quality or heavily compressed images.
- Document source and license information.
- Do not depend on external image URLs at runtime.

### Asset Presentation

Images should demonstrate the visual character of each category.

The application must not imply that the AI has analyzed these images.

The selected style and palette identifiers are passed to the AI as structured textual preferences.

## 10. 2D Room Plan Visual Style

The 2D room layout should be functional and visually clean.

It must prioritize spatial readability over decorative detail.

### Visual Requirements

- Clear room boundaries
- Readable dimension annotations
- Distinguishable doors and windows
- Clearly labeled furniture blocks
- Consistent furniture colors
- Appropriate scale
- Legible labels
- Simple legend where necessary

The room plan should use a restrained neutral palette.

Avoid unnecessary textures, shadows, gradients, and 3D effects.

The same visual language should be preserved when embedding the plan into the PDF.

## 11. PDF Report Design

The PDF should look like a professional interior design proposal.

### Visual Direction

- Editorial layout
- Clean typography
- Warm neutral backgrounds where appropriate
- Restrained use of the primary brand color
- Clear section hierarchy
- Consistent page margins
- Carefully aligned tables and figures

### Recommended Report Structure

**Cover**
- Hometsy branding
- Project name
- Room name and type
- Selected design concept

**Project Overview**
- Room dimensions
- Room area
- User requirements

**Design Concept**
- Concept description
- Design rationale
- Color and material direction

**Furniture and Materials**
- Recommendation list
- Dimensions
- Indicative costs

**Spatial Plan**
- Large 2D room layout
- Dimension annotations
- Spatial warnings

**Budget**
- Estimated cost breakdown
- Total estimated expenditure
- Budget comparison

**Design Evaluation**
- Compatibility assessment
- Practical recommendations
- Known limitations

### PDF Rules

- Use embedded fonts where appropriate.
- Ensure Turkish characters render correctly.
- Avoid tables splitting awkwardly across pages.
- Avoid text clipping and overlapping.
- Keep images sharp and correctly proportioned.
- Clearly label all illustrative cost estimates.
- Include a concise limitations note.

## 12. Responsive Behavior

The application is desktop-first.

It should remain usable on tablet-sized screens.

For narrower screens:

- Stack columns vertically.
- Keep form controls full-width where appropriate.
- Allow image cards to wrap.
- Preserve readable typography.
- Avoid horizontal overflow.
- Keep the 2D room plan accessible.

A dedicated mobile application is outside V1 scope.

## 13. Streamlit Implementation Guidelines

The design should be implemented using Streamlit components and scoped CSS.

Guidelines:

- Keep custom CSS centralized.
- Avoid repeated inline styling.
- Use reusable UI helper functions where justified.
- Maintain consistent component spacing.
- Avoid fragile CSS selectors tied to Streamlit's internal DOM structure.
- Do not modify Streamlit internals.
- Prefer stable Streamlit layout primitives.
- Test the interface after major visual changes.

The application must remain functional if a decorative style rule fails.

Visual customization must not compromise input behavior, navigation, accessibility, or application stability.

## 14. Accessibility and Usability

The interface should provide:

- Readable contrast
- Clear form labels
- Understandable validation messages
- Visible selection states
- Consistent interaction patterns
- Meaningful button labels
- Keyboard-accessible controls wherever supported

Important information must not be communicated through color alone.

## 15. Design System Definition of Done

The design system is successfully implemented when:

1. The landing page communicates the product clearly.
2. The application has a consistent visual identity.
3. All workflow stages follow the same layout rules.
4. Style and palette selection cards use local images.
5. Selected states are clearly visible.
6. Concept cards are easy to compare.
7. The 2D plan is readable and dimensioned.
8. Budget and validation information are easy to understand.
9. The PDF follows the same visual identity.
10. Turkish characters render correctly.
11. The interface remains usable on desktop and tablet screens.
12. No major visual or functional defects remain.
