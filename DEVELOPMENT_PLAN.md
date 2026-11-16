# HOMETSY — ROOM INTELLIGENCE STUDIO

**Development Plan — V1.0**

## 1. Development Objective

The objective is to build a complete, working V1 of Room Intelligence Studio through small, controlled development phases.

The project must prioritize:

- A functional end-to-end workflow
- Reliable deterministic calculations
- Meaningful AI integration
- A polished Streamlit interface
- Professional PDF output
- Testable and maintainable code

Development must follow the approved PROJECT_BRIEF.md, TECHNICAL_ARCHITECTURE.md, and DESIGN_SYSTEM.md.

No feature outside the approved V1 scope may be implemented without explicit approval.

## 2. Development Rules

1. Complete one development package at a time.
2. Review each package before moving to the next.
3. Do not skip required tests.
4. Do not implement future roadmap features.
5. Do not introduce unnecessary dependencies.
6. Preserve existing working code and configuration.
7. Do not invent API credentials or endpoints.
8. Do not silently change approved product decisions.
9. Report blockers instead of implementing speculative workarounds.
10. Keep the application runnable throughout development whenever practical.

OpenCode must not begin the next package until the current package has been reviewed and approved.

## 3. Development Phases

### Phase 0 — Workspace and Environment Inspection

**Objective:** Understand the existing development environment before implementation.

Tasks:

- Inspect the current workspace.
- Identify existing Python version and environment configuration.
- Inspect existing DeepSeek API integration, if present.
- Identify available dependencies.
- Review the approved project documentation.
- Identify potential technical conflicts.
- Confirm the proposed project structure.

Deliverables:

- Workspace inspection summary
- Environment and dependency summary
- Existing API integration summary
- Any identified blockers

Restrictions:

- Do not install packages.
- Do not modify existing configurations.
- Do not create application code.
- Do not initialize Git.
- Do not deploy.

**Acceptance Criteria:**

The development environment and existing API configuration are understood, and no unresolved critical blocker remains.

### Phase 1 — Application Foundation and Data Models

**Objective:** Establish the minimum application structure and validated data models.

Tasks:

- Create the approved project structure.
- Create the Streamlit application entry point.
- Implement Pydantic models.
- Define room input schemas.
- Define design preference schemas.
- Define budget input schemas.
- Define AI output schemas.
- Define the consolidated project result model.
- Add basic application configuration.
- Implement initial input validation.

Deliverables:

- Working Streamlit application shell
- Validated data models
- Basic configuration
- Initial model tests

**Acceptance Criteria:**

- The application starts successfully.
- Valid model data is accepted.
- Invalid model data is rejected with understandable errors.
- Core models can be tested independently.

### Phase 2 — Local Data and Visual Asset Library

**Objective:** Prepare the reference assets and furniture catalog.

Tasks:

- Prepare the six style reference categories.
- Prepare the four palette/material reference categories.
- Source appropriately licensed images.
- Store all selected images locally.
- Create the asset manifest.
- Record image source and license information.
- Create the furniture catalog JSON.
- Validate catalog dimensions and illustrative costs.
- Create design reference metadata.

Deliverables:

- Local style reference library
- Local palette reference library
- Asset manifest
- Furniture catalog
- Design reference metadata

**Acceptance Criteria:**

- All reference images load locally.
- No runtime dependency on external image URLs exists.
- Asset sources and licenses are documented.
- Furniture catalog records contain valid identifiers and required fields.
- Catalog costs are clearly identified as illustrative.

If a suitable image cannot be sourced with acceptable licensing, report the missing asset instead of using an unverified image.

### Phase 3 — Core Calculation Engines

**Objective:** Implement the deterministic logic independently of AI.

Tasks:

- Implement room dimension validation.
- Implement room area calculations.
- Implement rectangular room geometry.
- Implement door and window boundary validation.
- Implement furniture rectangle representation.
- Implement furniture rotation handling.
- Implement room boundary checks.
- Implement basic furniture overlap detection.
- Implement deterministic furniture placement rules.
- Implement budget calculations.
- Implement consolidated validation results.

Deliverables:

- Room engine
- Spatial engine
- Budget engine
- Validation engine
- Automated unit tests

**Acceptance Criteria:**

- Geometry calculations use centimeters internally.
- Room area calculations are correct.
- Furniture outside room boundaries is detected.
- Basic furniture overlaps are detected.
- Rotated furniture dimensions are handled correctly.
- Budget totals are calculated by Python.
- Critical deterministic tests pass.
- Core calculation modules do not require live AI requests.

### Phase 4 — DeepSeek AI Integration

**Objective:** Connect the approved AI responsibilities to the application.

Tasks:

- Inspect and reuse the existing DeepSeek API configuration.
- Implement the AI client.
- Implement timeout and error handling.
- Implement structured response handling.
- Implement Pydantic validation for AI outputs.
- Implement brief analysis.
- Implement three-concept generation.
- Implement furniture and material recommendations.
- Implement design evaluation.
- Add controlled retry handling for invalid structured responses.
- Add tests using mocked API responses.

Deliverables:

- AI client
- Brief analyzer
- Concept generator
- Design advisor
- Design evaluator
- AI validation tests

**Acceptance Criteria:**

- The existing approved model is used.
- API configuration is not invented or hardcoded.
- All AI outputs are validated before use.
- Three distinct concepts can be generated.
- Invalid AI responses are handled gracefully.
- API failures produce understandable messages.
- Automated tests do not require a live API key.

### Phase 5 — Complete Application Workflow

**Objective:** Connect the interface, AI services, and calculation engines.

Tasks:

- Implement room setup interface.
- Implement style and palette selection.
- Implement budget and requirement input.
- Implement AI brief analysis interaction.
- Display the three generated concepts.
- Implement concept selection.
- Generate furniture and material recommendations.
- Run spatial validation.
- Run budget calculations.
- Run design evaluation.
- Implement session state management.
- Implement invalidation of dependent results when upstream inputs change.

Deliverables:

- Complete interactive Streamlit workflow
- Connected application services
- Session state management
- Workflow validation

**Acceptance Criteria:**

A user can complete the entire workflow without manually editing application data or restarting the application.

Changing important room or preference inputs must not leave outdated concepts, recommendations, or calculations presented as current results.

### Phase 6 — 2D Layout and PDF Reporting

**Objective:** Produce the final spatial visualization and professional report.

Tasks:

- Generate the dimensioned 2D room plan.
- Display furniture labels and dimensions.
- Display room openings.
- Display spatial warnings.
- Prepare consolidated report data.
- Implement the PDF report template.
- Add room specifications and design concept.
- Add furniture and material recommendations.
- Add the 2D plan.
- Add budget breakdown.
- Add design evaluation.
- Add limitations and practical notes.
- Verify Turkish character support.

Deliverables:

- Matplotlib room plan
- PDF report generator
- Downloadable PDF output

**Acceptance Criteria:**

- The room plan is dimensioned and readable.
- Furniture blocks correspond to validated project data.
- The PDF includes all required sections.
- Turkish characters display correctly.
- No major text clipping or layout overlap occurs.
- PDF generation failures are handled gracefully.

### Phase 7 — Interface Polish and Final Validation

**Objective:** Bring the complete application to portfolio-quality presentation.

Tasks:

- Implement the approved design system.
- Polish the landing page.
- Polish navigation and progress indicators.
- Refine style and palette cards.
- Refine concept comparison cards.
- Improve the 2D plan presentation.
- Refine budget and validation displays.
- Add the V1/V2/V3 roadmap to the landing page.
- Review responsive behavior.
- Review error messages and empty states.
- Test the complete workflow.
- Fix identified defects.

Deliverables:

- Polished Streamlit interface
- Final application validation
- Complete V1 demonstration workflow

**Acceptance Criteria:**

- The interface follows DESIGN_SYSTEM.md.
- All V1 features work together.
- No critical workflow defects remain.
- The roadmap clearly distinguishes implemented and planned features.
- The application can be demonstrated from start to finish.

### Phase 8 — Documentation and Portfolio Preparation

**Objective:** Prepare the completed project for public portfolio presentation.

Tasks:

- Write the English README.
- Write the Turkish README.
- Ensure both documents contain equivalent information.
- Document architecture and functionality.
- Document installation and configuration.
- Document AI integration and limitations.
- Document the furniture catalog and illustrative pricing.
- Document V1/V2/V3 roadmap.
- Capture actual application screenshots.
- Store screenshots in `docs/screenshots/`.
- Verify relative image paths and Markdown links.
- Review repository contents before publication.

Deliverables:

- README.md
- README.tr.md
- Actual application screenshots
- Final documentation review

**Acceptance Criteria:**

- Both README documents are complete.
- English and Turkish versions have equivalent content.
- Screenshots come from the actual application.
- All screenshot paths work.
- No secrets or private configuration files are included.
- Planned features are not represented as implemented.

## 4. Dependency Order

The development sequence must respect the following dependencies:

| Phase | Depends On |
|---|---|
| Phase 0 | Approved project documentation |
| Phase 1 | Phase 0 |
| Phase 2 | Phase 1 |
| Phase 3 | Phase 1 |
| Phase 4 | Phase 1 |
| Phase 5 | Phases 2, 3 and 4 |
| Phase 6 | Phase 5 |
| Phase 7 | Phases 2–6 |
| Phase 8 | Phase 7 |

Phases 2, 3, and 4 may be developed independently after Phase 1, but each must be completed and reviewed before integration.

## 5. Testing Strategy

Testing must be performed throughout development rather than postponed until the end.

### Unit Tests

Prioritize:

- Room dimension validation
- Room area calculations
- Furniture geometry
- Furniture boundary checks
- Furniture overlap checks
- Budget calculations
- Pydantic model validation

### AI Tests

Use mocked responses to verify:

- Valid structured output
- Invalid structured output
- Missing fields
- Invalid catalog references
- API errors
- Timeout handling

### Integration Tests

Verify:

- Complete project data flow
- Concept selection
- Recommendation generation
- Spatial validation integration
- Budget integration
- Report generation

### Final End-to-End Test

Complete one representative residential room scenario from initial input to PDF download.

All critical tests must pass before declaring V1 complete.

## 6. Review and Approval Gates

The project must use explicit approval gates.

| Gate | Review Point |
|---|---|
| Gate 0 | Workspace inspection |
| Gate 1 | Application foundation |
| Gate 2 | Asset library and catalog |
| Gate 3 | Core calculation engines |
| Gate 4 | AI integration |
| Gate 5 | Complete workflow |
| Gate 6 | PDF reporting |
| Gate 7 | Interface and final validation |
| Gate 8 | Documentation and portfolio preparation |

At every gate, OpenCode must provide:

1. Work completed
2. Files created or modified
3. Tests executed and their results
4. Known limitations
5. Outstanding issues
6. Proposed next step

No subsequent phase should begin until the current gate is approved.

## 7. Change Management

Any proposed change that affects:

- V1 functionality
- Approved architecture
- Dependencies
- AI responsibilities
- Data models
- Visual direction
- Project scope

Must be reported before implementation.

OpenCode must explain:

- Why the change is necessary
- What problem it solves
- Whether an existing approved solution is sufficient
- Its effect on complexity and testing

Approval is required before making material scope changes.

## 8. Deployment and Publication Restrictions

Deployment, GitHub publication, and portfolio integration are separate approval stages.

OpenCode must not:

- Push code to GitHub without explicit approval.
- Deploy the application without explicit approval.
- Publish screenshots without review.
- Commit changes before the final review.
- Overwrite existing remote repository content.
- Perform force pushes.

The project must first pass local validation and documentation review.

## 9. Definition of Project Completion

V1 is complete when:

- All approved V1 features are implemented.
- The complete workflow works.
- Deterministic calculation tests pass.
- AI response validation works.
- PDF generation works.
- The interface follows the approved design system.
- Critical errors are resolved.
- Documentation is complete.
- Actual screenshots are captured.
- The project is ready for a controlled portfolio publication process.

## 10. Final Development Principle

The purpose of this development plan is not to maximize the amount of code produced.

The objective is to deliver a small, coherent, technically credible application that demonstrates practical problem-solving through AI, Python, spatial reasoning, data validation, and product design.

A complete and reliable V1 is more valuable than a complex application with unfinished features.
