# HOMETSY — ROOM INTELLIGENCE STUDIO

**AGENTS.md — AI Development Instructions**

## 1. Project Context

You are working on **Hometsy — Room Intelligence Studio**, an AI-assisted interior design and spatial planning application.

This is a portfolio project, not a commercial SaaS product.

The objective is to build a complete, reliable, visually polished V1 that demonstrates:

- Practical problem-solving
- AI integration
- Python development
- Deterministic engineering calculations
- Spatial reasoning
- Data validation
- Product and interface design
- Automated reporting

The project must follow these approved documents:

1. `PROJECT_BRIEF.md`
2. `TECHNICAL_ARCHITECTURE.md`
3. `DESIGN_SYSTEM.md`
4. `DEVELOPMENT_PLAN.md`
5. `AGENTS.md`

These documents collectively define the project's scope, architecture, design direction, and development rules.

## 2. Source of Truth

The approved project documentation is the primary source of truth.

When making implementation decisions:

1. Follow the approved project brief.
2. Follow the approved technical architecture.
3. Follow the approved design system.
4. Follow the approved development plan.
5. Follow these development instructions.

Do not silently reinterpret or expand approved requirements.

If two documents appear inconsistent, stop and report the conflict before making a material implementation decision.

Do not invent additional product requirements.

## 3. Scope Protection

V1 must remain intentionally small and achievable.

The approved V1 includes:

- Rectangular residential room configuration
- Four supported room types
- Six interior design styles
- Four palette/material directions
- User requirements and budget input
- AI-assisted brief analysis
- Three AI-generated design concepts
- Concept selection
- Furniture and material recommendations
- Local furniture catalog
- Basic 2D room planning
- Basic spatial validation
- Deterministic budget calculations
- AI-assisted design evaluation
- Professional PDF report generation
- Automated tests

The following features are explicitly excluded from V1:

- 3D visualization
- Image recognition or vision models
- AI-generated interior images
- Photograph-based room measurement
- Irregular room geometry
- Advanced furniture optimization
- Live product pricing
- Retailer integrations
- Authentication
- Payment systems
- Database-backed multi-user functionality
- Multi-room management
- Microservices
- Multi-agent orchestration frameworks

Do not implement excluded features.

Do not add functionality simply because it appears technically interesting.

## 4. Development Workflow

Development must follow the phases in `DEVELOPMENT_PLAN.md`.

The required sequence is:

1. Workspace and environment inspection
2. Application foundation and data models
3. Local data and visual asset library
4. Core calculation engines
5. DeepSeek AI integration
6. Complete application workflow
7. 2D layout and PDF reporting
8. Interface polish and final validation
9. Documentation and portfolio preparation

Each phase requires an explicit review and approval before proceeding.

### Approval Rule

After completing a phase:

- Stop implementation.
- Summarize completed work.
- List created and modified files.
- Report tests and their results.
- Identify known issues.
- Explain any deviations from approved documentation.
- Propose the next phase.

Do not automatically continue into the next phase.

Wait for explicit approval.

## 5. Initial Workspace Rules

Before implementation begins:

- Inspect the existing workspace.
- Identify existing project files.
- Identify Python and environment configuration.
- Inspect the existing DeepSeek API integration, if available.
- Identify existing dependencies and conventions.
- Report any conflicts with the approved architecture.

Do not assume the workspace is empty.

Do not overwrite or delete existing files without explicit approval.

Do not install dependencies during the inspection phase.

Do not modify existing configuration during the inspection phase.

Do not initialize Git during the inspection phase.

## 6. Technology Constraints

Use the approved technology stack:

- Python
- Streamlit
- Existing DeepSeek API integration
- Pydantic
- Matplotlib
- ReportLab
- Pytest

Additional libraries must not be introduced without a clear technical requirement.

Before proposing a new dependency, explain:

- What problem it solves
- Why existing tools are insufficient
- Its effect on application complexity
- Whether it introduces deployment or maintenance overhead

Prefer the Python standard library for simple operations.

Avoid unnecessary abstractions and frameworks.

## 7. AI Integration Rules

The approved model is:

`deepseek-ai/deepseek-v4.1-flash-1017`

Reuse the existing API integration and configuration.

Do not invent:

- API endpoints
- API credentials
- Environment variable names without inspection
- Provider-specific capabilities
- Image analysis capabilities
- Image generation capabilities

AI responsibilities are limited to:

1. Brief analysis
2. Design concept generation
3. Furniture and material recommendations
4. Design evaluation

AI responses must be structured and validated using Pydantic.

Never trust raw AI output without validation.

Handle malformed output, missing fields, invalid catalog references, timeouts, and API errors.

A failed AI request must not be represented as a successful result.

### Strict Separation of Responsibilities

AI handles design reasoning and natural-language interpretation.

Python handles:

- Geometry
- Dimensions
- Area calculations
- Furniture boundaries
- Overlap detection
- Budget calculations
- Data validation
- 2D plan generation
- PDF generation

Do not delegate deterministic calculations to the language model.

## 8. Engineering and Calculation Rules

All spatial calculations must use centimeters internally.

Area outputs must be presented in square meters.

Use a consistent coordinate system.

The room origin must be the bottom-left corner.

Furniture must be represented using its actual catalog dimensions within the application.

Furniture rotation must be accounted for in geometric validation.

Basic overlap and boundary checks must be deterministic.

Do not claim comprehensive ergonomic, accessibility, structural, or building-code compliance.

The 2D plan is illustrative, not a professional construction drawing.

### Budget Rules

All budget arithmetic must be performed in Python.

Use the local furniture catalog and explicitly defined indicative costs.

Never present illustrative prices as verified current market prices.

AI-generated cost allocations must be checked against the available catalog data before calculation.

## 9. Code Quality Rules

Write code that is:

- Readable
- Modular
- Maintainable
- Testable
- Consistent with the approved architecture

Prefer simple functions and focused modules.

Avoid:

- Unnecessary classes
- Excessive abstraction
- Duplicate logic
- Circular dependencies
- Large monolithic files
- Hardcoded business rules scattered throughout the application
- Silent exception handling
- Unnecessary global state

Keep UI logic separate from business and calculation logic.

Use meaningful names for functions, variables, models, and files.

Add comments where they explain non-obvious decisions, not where they merely repeat the code.

## 10. Streamlit Rules

Streamlit is the primary application interface.

The interface must follow `DESIGN_SYSTEM.md`.

Use session state to maintain workflow progress.

Changing important upstream inputs must invalidate dependent results.

Avoid fragile CSS selectors and modifications to Streamlit internals.

Keep custom CSS centralized.

Do not compromise application functionality for visual effects.

Do not present planned features as implemented features.

## 11. Visual Asset and Licensing Rules

All reference images must be stored locally.

Use appropriately licensed images suitable for a public portfolio project.

Document:

- Original source
- License
- Attribution requirements
- Local filename

Do not use:

- Unverified images
- Watermarked images
- Images with unclear usage rights
- Remote image URLs as runtime dependencies

If licensing cannot be verified, do not include the image.

Do not generate artificial reference assets unless explicitly approved.

The application must not claim to analyze selected images with the text-only DeepSeek model.

## 12. Testing Rules

Tests are mandatory.

Prioritize deterministic unit tests for:

- Room calculations
- Dimension validation
- Furniture geometry
- Boundary checks
- Overlap detection
- Budget calculations
- Pydantic schemas

AI tests must use mocked responses where possible.

The core test suite must not require a live API key.

Do not claim tests passed unless they were actually executed.

Report:

- Test command
- Number of tests
- Passed tests
- Failed tests
- Skipped tests
- Relevant failure details

Never hide failing tests or modify tests merely to make an implementation appear successful.

## 13. Error Handling and Security

Never hardcode API keys.

Never expose credentials in:

- Source code
- Error messages
- Logs
- Screenshots
- README files

Use the existing configuration mechanism after inspecting it.

Exclude secret files from version control.

Use clear error messages for expected application failures.

Do not silently return fabricated data when an operation fails.

## 14. Documentation Rules

Keep the project documentation consistent with the actual implementation.

Required final documentation:

- `README.md`
- `README.tr.md`

Both documents must contain equivalent information.

Document:

- Project purpose
- Main features
- Technology stack
- Architecture
- Installation
- Configuration
- Application workflow
- AI responsibilities
- Known limitations
- V1/V2/V3 roadmap

Do not document unimplemented features as completed functionality.

Screenshots must come from the actual running application.

Store approved screenshots in:

`docs/screenshots/`

Never fabricate screenshots or represent AI-generated mockups as application screenshots.

## 15. Change Approval Rules

Stop and request approval before:

- Adding features outside V1
- Changing approved architecture
- Introducing significant dependencies
- Changing the AI provider or model
- Changing the API configuration
- Changing core data models in a way that affects the workflow
- Replacing existing files
- Deleting project files
- Changing the visual direction
- Expanding the room geometry scope
- Introducing new external services

For each proposed change, explain its necessity and impact.

Do not make material decisions on behalf of the project owner.

## 16. Git and Deployment Restrictions

Do not perform the following without explicit approval:

- Git initialization
- Git commits
- Git pushes
- GitHub repository publication
- Remote repository changes
- Deployment
- Production configuration changes
- Force pushes

Before any approved commit, review the changed files and repository state.

Before any approved push or deployment, provide a separate summary of the intended operation.

Never overwrite remote content without authorization.

## 17. Communication and Reporting

Communicate in concise, clear language.

After each development package, report:

1. Objective
2. Implementation summary
3. Files created or modified
4. Tests performed
5. Test results
6. Known limitations
7. Scope deviations, if any
8. Recommended next action

If a requirement is unclear, ask before making a material assumption.

If a technical problem cannot be solved within the approved scope, explain the problem and propose the smallest viable solution.

Do not bury important blockers in long technical summaries.

## 18. Final Principle

Build the approved product, not a larger product.

Prioritize working functionality, technical credibility, clarity, and reliability.

A complete, tested, deployable V1 is the objective.

Do not sacrifice completion for unnecessary complexity.
