# HOMETSY — ROOM INTELLIGENCE STUDIO

**Technical Architecture — V1.0**

## 1. Architecture Overview

Room Intelligence Studio will use a modular Python application architecture built around Streamlit.

The architecture is intentionally lightweight. It must support a complete end-to-end workflow without introducing unnecessary infrastructure, microservices, databases, or complex deployment requirements.

The application will consist of five logical layers:

1. Presentation Layer
2. Application Workflow Layer
3. AI Integration Layer
4. Core Calculation Layer
5. Reporting Layer

All layers will run within a single Python application.

## 2. Technology Stack

| Component | Technology | Responsibility |
|---|---|---|
| User Interface | Streamlit | User interaction and workflow |
| Main Language | Python | Application logic |
| AI Provider | Existing DeepSeek API | Design reasoning and content generation |
| AI Model | deepseek-ai/deepseek-v4.1-flash-1017 | Text-based AI tasks |
| Data Validation | Pydantic | Structured input/output validation |
| Data Processing | Python standard library | Core calculations and transformations |
| 2D Visualization | Matplotlib | Room layout generation |
| PDF Generation | ReportLab | Final design report |
| Automated Testing | Pytest | Core logic and integration testing |

Pandas and OpenPyXL are not required by default. They may only be introduced if an actual V1 requirement justifies them.

## 3. Application Architecture

### 3.1 Presentation Layer

**Technology:** Streamlit

Responsibilities:

- Display the application interface.
- Collect room information.
- Display local style and palette references.
- Collect design preferences and budget.
- Display AI-generated concepts.
- Allow concept selection.
- Display recommendations and validation results.
- Provide PDF report download.

The interface must not contain geometry calculations, AI prompt construction, or PDF generation logic.

Streamlit should primarily coordinate user interaction and display application results.

### 3.2 Application Workflow Layer

This layer coordinates the complete user journey.

Responsibilities:

- Validate submitted information.
- Build the project input object.
- Call the AI services in the correct order.
- Store intermediate workflow results in Streamlit session state.
- Pass structured data between modules.
- Handle workflow errors.
- Prepare the final report data.

The workflow should be sequential and easy to understand.

No background job infrastructure or task queue is required for V1.

### 3.3 AI Integration Layer

**Technology:** Existing DeepSeek API integration.

The AI layer is responsible for interpreting user requirements and generating design-related recommendations.

It must not calculate room geometry, furniture collisions, room areas, or financial totals.

The AI layer will contain the following logical services.

#### A. Brief Analyzer

Input:

- Room specifications
- Selected style
- Palette and material preferences
- Budget
- User notes

Output:

- Structured design brief
- Functional priorities
- Constraints
- Ambiguities
- Relevant warnings

#### B. Concept Generator

Input:

- Structured design brief
- Room information
- Selected preferences
- Budget

Output:

Three distinct design concepts.

Each concept must follow a predefined Pydantic schema.

#### C. Design Advisor

Input:

- Selected concept
- Room specifications
- Structured design brief
- Furniture catalog
- Budget

Output:

- Furniture recommendations
- Suggested dimensions
- Material recommendations
- Color direction
- Design rationale
- Indicative cost allocations

The AI may select and recommend items from the predefined catalog. It must not invent catalog IDs or treat unverified product specifications as real products.

#### D. Design Evaluator

Input:

- Structured design brief
- Selected concept
- AI recommendations
- Spatial validation results
- Python-calculated budget results

Output:

- Requirement compatibility assessment
- Style consistency assessment
- Functional suitability assessment
- Budget suitability assessment
- Identified limitations
- Practical recommendations

The evaluator must receive actual calculated results from Python.

It must not independently recalculate or override deterministic results.

### AI Output Validation

All structured AI responses must be validated using Pydantic models.

Validation must cover:

- Required fields
- Field types
- Allowed values
- Numeric ranges where applicable
- List lengths
- Catalog item identifiers

Malformed or incomplete AI responses must not silently enter the application workflow.

The application may attempt one controlled correction or retry for invalid structured output. If validation still fails, the user must receive a clear error message.

The application must never fabricate a successful result when the AI request fails.

### AI Call Strategy

V1 should use a maximum of four primary AI operations:

1. Brief analysis
2. Concept generation
3. Design recommendations
4. Design evaluation

No autonomous multi-agent framework is required.

The services are separate logical responsibilities, not separate AI agents or deployed services.

## 4. Core Calculation Layer

This layer contains deterministic application logic.

Its outputs must be reproducible from the same input data.

### 4.1 Room Engine

Responsibilities:

- Validate room dimensions.
- Calculate room area.
- Store room boundary information.
- Normalize door and window data.
- Check that openings are positioned within valid room boundaries.

V1 supports rectangular rooms only.

All dimensions should use centimeters internally for spatial calculations.

Area calculations should use square meters in user-facing outputs.

### 4.2 Spatial Engine

Responsibilities:

- Generate a rectangular room boundary.
- Place door and window representations.
- Convert furniture dimensions into 2D rectangles.
- Validate furniture against room boundaries.
- Detect basic furniture-to-furniture overlaps.
- Generate layout data for Matplotlib.

Furniture placement must follow deterministic rules.

The system should use a simple predefined placement strategy rather than attempting advanced automatic interior design optimization.

If the selected furniture cannot fit into the room, the system must report the problem instead of silently generating an invalid layout.

The spatial engine must distinguish between a geometric overlap warning and a real-world circulation or accessibility assessment. V1 does not perform comprehensive ergonomic or building-code verification.

### 4.3 Budget Engine

Responsibilities:

- Read indicative catalog costs.
- Calculate furniture subtotals.
- Calculate material subtotals.
- Calculate total estimated expenditure.
- Compare the result with the user-defined budget.
- Calculate remaining budget or budget overrun.

All financial arithmetic must be handled by Python.

All prices must be clearly identified as illustrative estimates.

No live market pricing is included in V1.

### 4.4 Validation Engine

Responsibilities:

- Validate user inputs.
- Check room dimension limits.
- Validate furniture catalog references.
- Check required fields.
- Verify consistency between workflow stages.
- Collect spatial and budget warnings.

Validation errors and non-blocking warnings must be represented separately.

## 5. Data Models

Pydantic will define the primary application data structures.

The exact field definitions will be finalized during implementation, but the following logical models are required.

| Model | Purpose |
|---|---|
| RoomInput | Room type, name, dimensions and openings |
| DesignPreferences | Style, palette and material preferences |
| UserRequirements | Functional requirements and notes |
| BudgetInput | User-defined budget |
| DesignBrief | AI-analyzed requirements |
| DesignConcept | One generated design concept |
| ConceptCollection | Three generated concepts |
| FurnitureItem | Catalog furniture definition |
| FurnitureRecommendation | Selected furniture and suggested placement |
| SpatialValidation | Boundary and overlap results |
| BudgetAnalysis | Deterministic budget calculations |
| DesignEvaluation | AI-generated evaluation |
| ProjectResult | Consolidated workflow output |

Models should remain small and focused.

Do not create additional abstraction layers unless required by an actual implementation need.

## 6. Furniture Catalog

The furniture catalog will be maintained as a local JSON file.

Each item should include:

- Unique item ID
- Display name
- Furniture category
- Default width in centimeters
- Default depth in centimeters
- Indicative unit cost
- Supported room types
- Simple 2D drawing representation

Example catalog items:

| Furniture | Default Dimensions |
|---|---|
| Three-seat sofa | 220 × 90 cm |
| Two-seat sofa | 180 × 90 cm |
| Armchair | 80 × 80 cm |
| Coffee table | 100 × 60 cm |
| TV unit | 180 × 40 cm |
| Dining table | 140 × 80 cm |
| Desk | 120 × 60 cm |
| Wardrobe | 180 × 60 cm |

These are illustrative defaults, not verified product specifications.

Catalog costs must also be marked as illustrative.

## 7. Spatial Planning Approach

Matplotlib will generate the 2D room layout.

The room will be represented as a rectangle.

Furniture will be represented as dimensioned rectangles.

The layout must show:

- Room boundary
- Dimension annotations
- Door position
- Window position
- Furniture blocks
- Furniture labels
- Basic scale and orientation

The spatial engine must use one consistent coordinate system.

The room origin should be the bottom-left corner.

All internal geometry calculations should use centimeters.

The application must account for furniture rotation when evaluating alternative orientations.

V1 does not need advanced placement optimization. A deterministic placement strategy with basic validation is sufficient.

The generated layout is illustrative and must not be presented as a professional architectural drawing.

## 8. Budget Calculation Approach

The budget engine will calculate costs using the local catalog and recommendation quantities.

Example:

- Furniture item quantity × indicative unit cost
- Material quantity × indicative unit cost
- Other estimated expenses

The system will calculate:

- Furniture subtotal
- Material subtotal
- Other expenses
- Total estimated cost
- Available budget
- Remaining budget or overrun

The application must clearly distinguish estimated costs from verified market prices.

AI-generated cost allocations must be validated against catalog data before calculation.

Python remains the source of truth for all totals.

## 9. Reporting Layer

**Technology:** ReportLab

The reporting layer will receive a consolidated ProjectResult object.

It will generate a PDF containing:

1. Project overview
2. Room specifications
3. Design requirements
4. Selected design concept
5. Design rationale
6. Color and material direction
7. Furniture recommendations
8. 2D room layout
9. Budget breakdown
10. Design evaluation
11. Limitations and practical notes

The PDF generator must not call AI services or perform independent business calculations.

The report should use a consistent typography system, spacing, page hierarchy, and visual identity.

The generated 2D layout image will be embedded into the PDF.

## 10. Visual Asset Architecture

All reference images must be stored locally.

Suggested organization:

- `assets/images/styles/`
- `assets/images/palettes/`
- `assets/images/materials/`

An asset manifest must record:

- Asset filename
- Display name
- Category
- Original source
- License
- Attribution requirements

The Streamlit interface must use local image paths.

The AI receives the selected style and palette identifiers and their textual descriptions, not the actual image files.

The V1 application must not claim to understand or analyze visual references.

## 11. Application State Management

Streamlit session state will maintain the current project workflow.

It should store only the data needed to preserve progress between interface interactions, including:

- Room input
- Design preferences
- User requirements
- Budget
- Analyzed brief
- Generated concepts
- Selected concept
- Recommendations
- Spatial validation
- Budget analysis
- Final evaluation

Each stage must verify that its required previous-stage data exists.

Changing important upstream inputs should invalidate dependent results to avoid using stale AI output or outdated calculations.

No database is required for V1.

Project persistence across browser sessions is not required.

## 12. Error Handling

The application must handle:

- Missing user inputs
- Invalid room dimensions
- Invalid opening positions
- Furniture that exceeds room boundaries
- Furniture overlaps
- Missing catalog references
- AI API failures
- Network timeouts
- Malformed AI responses
- Pydantic validation failures
- PDF generation errors

Errors must be understandable to the user.

Technical details should be available for debugging without exposing API keys or sensitive configuration values.

The application must never expose secrets in the interface or logs.

## 13. Testing Strategy

Pytest will be used for automated testing.

Priority test areas:

### Room Engine

- Valid rectangular room
- Invalid dimensions
- Room area calculation
- Opening boundary validation

### Spatial Engine

- Furniture within room boundaries
- Furniture outside room boundaries
- Furniture overlap detection
- Rotated furniture dimensions

### Budget Engine

- Furniture subtotal
- Material subtotal
- Total cost
- Remaining budget
- Budget overrun

### Data Validation

- Valid model inputs
- Missing required fields
- Invalid catalog identifiers
- Invalid AI output

### Reporting

- PDF generation from valid project data
- Handling missing optional sections
- Ensuring the generated file is non-empty

External AI API tests should be separated from deterministic unit tests.

The core test suite must run without requiring a live AI API request.

## 14. Proposed Project Structure

The implementation should use a compact modular structure.

```text
room-intelligence-studio/
│
├── app.py
│
├── pages/
│   ├── 1_Room_Setup.py
│   ├── 2_Design_Studio.py
│   └── 3_Design_Report.py
│
├── core/
│   ├── room_engine.py
│   ├── spatial_engine.py
│   ├── budget_engine.py
│   └── validation.py
│
├── ai/
│   ├── client.py
│   ├── brief_analyzer.py
│   ├── concept_generator.py
│   ├── design_advisor.py
│   └── design_evaluator.py
│
├── models/
│   └── schemas.py
│
├── data/
│   ├── furniture_catalog.json
│   └── design_references.json
│
├── assets/
│   ├── images/
│   │   ├── styles/
│   │   ├── palettes/
│   │   └── materials/
│   └── fonts/
│
├── reports/
│   └── report_generator.py
│
├── tests/
│   ├── test_room_engine.py
│   ├── test_spatial_engine.py
│   ├── test_budget_engine.py
│   └── test_models.py
│
├── docs/
│   └── screenshots/
│
├── .streamlit/
│   └── config.toml
│
├── PROJECT_BRIEF.md
├── TECHNICAL_ARCHITECTURE.md
├── DESIGN_SYSTEM.md
├── DEVELOPMENT_PLAN.md
├── AGENTS.md
├── README.md
├── README.tr.md
├── requirements.txt
├── .env.example
└── .gitignore
```

The structure is a proposed logical organization, not a requirement to create empty directories in advance.

If inspection reveals a simpler structure that preserves the same separation of responsibilities, prefer the simpler option.

## 15. Security and Configuration

API credentials must be stored outside source code.

The existing DeepSeek API configuration must be inspected and reused.

The application must:

- Read credentials from environment variables or Streamlit secrets.
- Never hardcode API keys.
- Exclude `.env` from version control.
- Provide a sanitized `.env.example`.
- Avoid exposing secrets in error messages.
- Avoid logging complete API credentials or sensitive request headers.

## 16. Deployment Architecture

V1 will be deployed as a single Streamlit application.

The deployment must require:

- Python dependencies
- DeepSeek API credentials
- Local reference assets
- Furniture catalog data

No database, external worker, container orchestration, or separate backend service is required.

The application must be demonstrable using a configured deployment environment.

## 17. Architecture Constraints

The following constraints are mandatory:

1. No microservices.
2. No multi-agent orchestration framework.
3. No database in V1.
4. No authentication system.
5. No image vision model.
6. No image generation service.
7. No live retailer integrations.
8. No advanced spatial optimization.
9. No unnecessary dependencies.
10. No duplicate calculation logic across modules.

## 18. Architectural Definition of Done

The architecture is successfully implemented when:

- Each logical layer has a clear responsibility.
- The AI layer returns validated structured data.
- The core calculation layer produces deterministic results.
- Spatial validation is independent of AI output generation.
- Budget calculations are independent of AI arithmetic.
- The reporting layer consumes consolidated project data.
- The Streamlit workflow maintains valid state.
- Critical modules can be tested without live AI requests.
- The complete application can run as one deployable Streamlit project.
