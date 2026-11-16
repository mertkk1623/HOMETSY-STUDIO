# HOMETSY — ROOM INTELLIGENCE STUDIO

**Project Brief — V1.0**

## 1. Project Overview

**Project Name:** Hometsy — Room Intelligence Studio

**Product Type:** AI-Powered Interior Design & Spatial Planning Application

**Project Purpose:** Portfolio Project

Room Intelligence Studio is a Python-based application that transforms a user's room information, spatial dimensions, design preferences, and budget into a structured interior design proposal.

The application combines AI-assisted design reasoning with deterministic spatial calculations and automated report generation.

The goal is not simply to generate decorative text. It is to demonstrate how AI, engineering logic, structured data, and software development can work together to solve a practical interior design problem.

The application will be developed as a portfolio project. It is not intended to operate as a commercial SaaS product.

## 2. Problem Definition

Planning an interior space requires users to make several connected decisions:

- How should the available space be used?
- Which interior design style is appropriate?
- Which furniture and materials should be considered?
- How can the available budget be distributed?
- Are the proposed furniture dimensions compatible with the room?
- Does the proposed design satisfy the user's requirements?

These decisions are often made independently, making it difficult to evaluate the overall suitability of a design proposal.

Room Intelligence Studio aims to bring these decisions together in a single, structured workflow.

## 3. Product Objective

The application must transform basic room information into an understandable and visually organized interior design proposal.

The final output must include:

1. Room information and dimensions.
2. User preferences and design requirements.
3. AI-generated design concepts.
4. Selected design concept and its rationale.
5. Furniture and material recommendations.
6. A simple dimensioned 2D room plan.
7. Budget allocation and breakdown.
8. Design evaluation and practical recommendations.
9. A professionally formatted PDF report.

## 4. Target User

The primary target user is someone who wants to explore an interior design direction for a residential room without needing professional design software.

V1 will support a controlled set of residential room types:

- Living Room
- Bedroom
- Home Office
- Dining Room

The application is a demonstration of a design-planning workflow, not a substitute for a professional architect or interior designer.

## 5. Core User Workflow

The application must provide one coherent end-to-end workflow.

### Step 1 — Room Configuration

The user defines:

- Room type
- Room name
- Room width
- Room length
- Ceiling height (optional)
- Door location and approximate width
- Window location and approximate width

V1 supports rectangular rooms only.

### Step 2 — Design Preferences

The user selects:

- Preferred interior design style
- Preferred color palette
- Material preferences
- Functional requirements
- Additional notes

The available styles are:

- Warm Minimalism
- Scandinavian
- Japandi
- Contemporary
- Industrial
- Bohemian

The available palette and material directions are:

- Warm Neutral
- Earthy
- Cool Modern
- Natural Materials

Local visual reference images will help users understand and select these preferences.

The selected images are used as visual references in the interface. V1 does not perform image recognition or visual analysis.

### Step 3 — Budget Definition

The user enters an estimated total design budget.

The application must clearly distinguish between:

- Estimated furniture costs
- Estimated material costs
- Other estimated expenses
- Remaining budget

All budget values are indicative estimates, not verified market prices or supplier quotations.

### Step 4 — AI Brief Analysis

The AI analyzes the user's room information, preferences, budget, and notes.

It must:

- Summarize the user's requirements.
- Identify important functional priorities.
- Detect obvious contradictions.
- Identify missing or ambiguous information where relevant.
- Produce a structured design brief.

### Step 5 — Design Concept Generation

The AI generates three distinct design concepts.

Each concept must include:

- Concept name
- Design description
- Main design direction
- Color and material direction
- Furniture approach
- Functional rationale
- Budget suitability

The concepts must be meaningfully different from one another while respecting the user's selected preferences.

### Step 6 — Concept Selection

The user reviews the three concepts and selects one.

Only the selected concept proceeds to the detailed recommendation and reporting stages.

### Step 7 — Furniture and Material Recommendations

The AI prepares recommendations based on:

- Selected design concept
- Room type
- Room dimensions
- User requirements
- Available furniture catalog
- Estimated budget

Recommendations must include appropriate furniture categories, suggested dimensions, material directions, and explanations.

V1 uses a predefined furniture catalog with illustrative default dimensions.

The application must not present catalog dimensions as verified specifications of real commercial products.

### Step 8 — Spatial Planning

Python processes the room dimensions and selected furniture data.

It generates a simple 2D rectangular room plan showing:

- Room boundaries
- Room dimensions
- Door and window positions
- Basic furniture blocks
- Furniture labels
- Approximate furniture dimensions

The spatial engine must apply basic geometric checks to identify furniture that exceeds room boundaries or creates obvious overlaps.

The plan is an illustrative layout, not a construction drawing or professional architectural plan.

### Step 9 — Budget Analysis

Python performs deterministic budget calculations.

It must:

- Calculate estimated furniture costs.
- Calculate estimated material costs.
- Calculate total estimated expenditure.
- Compare estimated expenditure with the user's budget.
- Identify budget overruns or remaining budget.

AI must not perform financial arithmetic that Python can calculate reliably.

### Step 10 — Design Evaluation

The AI evaluates the selected concept and recommendations against the available structured information.

The evaluation should consider:

- Requirement compatibility
- Style consistency
- Functional suitability
- Budget suitability
- Spatial planning warnings
- Missing or uncertain information

The evaluation must not claim to verify physical conditions or measurements that the application cannot observe.

### Step 11 — PDF Report Generation

The application generates a professionally formatted PDF report containing:

1. Project overview
2. Room specifications
3. User requirements
4. Selected design concept
5. Design rationale
6. Color and material direction
7. Furniture recommendations
8. 2D room plan
9. Estimated budget breakdown
10. Design evaluation
11. Practical notes and limitations

## 6. AI Integration Strategy

The existing DeepSeek API integration will be reused.

**Model:** `deepseek-ai/deepseek-v4.1-flash-1017`

The current text-based API is responsible for structured design reasoning and content generation.

AI responsibilities:

- Brief analysis
- Design concept generation
- Furniture and material recommendations
- Design evaluation

AI output must follow predefined structured schemas.

Pydantic validation must be used to validate structured responses before they enter the application workflow.

The application must handle malformed AI responses, API failures, and incomplete outputs gracefully.

### Separation of Responsibilities

**AI handles:**
- Understanding natural-language requirements
- Generating design concepts
- Explaining design decisions
- Suggesting furniture and materials
- Evaluating design suitability

**Python handles:**
- Room geometry
- Furniture dimensions
- Boundary and overlap checks
- Area calculations
- Budget calculations
- Data validation
- 2D plan generation
- PDF generation

AI must not be presented as a source of verified engineering calculations.

## 7. Visual Asset Library

The application will include a small local visual reference library.

Its purpose is to make design preference selection more intuitive and improve the overall interface.

### Style Reference Categories

- Warm Minimalism
- Scandinavian
- Japandi
- Contemporary
- Industrial
- Bohemian

### Palette Reference Categories

- Warm Neutral
- Earthy
- Cool Modern
- Natural Materials

### Asset Requirements

- Images must be stored locally.
- Image sources and licenses must be documented.
- An asset manifest must record filenames, source references, and license information.
- The application must not depend on remote image URLs to display its reference library.
- Assets must be appropriately licensed for use in a public portfolio project.

Furniture information will be stored as structured catalog data rather than a large collection of product photographs.

## 8. V1 Functional Scope

V1 includes:

- Single-room workflow
- Rectangular room geometry
- Four supported residential room types
- Six interior design styles
- Four palette/material directions
- User requirements and budget input
- AI-assisted brief analysis
- Three AI-generated design concepts
- User concept selection
- AI furniture and material recommendations
- Basic furniture catalog
- Simple 2D room layout
- Basic spatial validation
- Deterministic budget calculations
- AI-assisted design evaluation
- PDF report generation
- Error handling and input validation
- Basic automated tests

The complete workflow must function from user input to final PDF output.

## 9. Explicitly Out of Scope

The following features must not be implemented in V1:

- 3D room visualization
- AI-generated interior design images
- Computer vision or image-based room analysis
- Automatic room measurement from photographs
- Irregular L-shaped or U-shaped room geometry
- Advanced furniture placement optimization
- Real-time product price searches
- Live retailer or supplier integrations
- Product purchasing functionality
- User accounts and authentication
- Payment systems
- Database-backed multi-user operation
- Multi-room project management
- Mobile application development
- Professional construction or architectural drawings

These exclusions are intentional and must not be added without a separate scope approval.

## 10. Technical Direction

The application will use the existing Python and Streamlit environment.

The preferred technology stack is:

- Python
- Streamlit
- Existing DeepSeek API integration
- Pydantic
- Matplotlib
- ReportLab
- Pytest

Additional dependencies should only be introduced if an actual V1 requirement justifies them.

Existing API configuration, environment variables, and project conventions must be inspected before implementation.

No API endpoint, credential, or configuration value should be invented.

## 11. V1 Acceptance Criteria

V1 will be considered complete when:

1. A user can enter valid rectangular room dimensions.
2. A user can select a room type, style, palette, and budget.
3. The application can produce a structured AI brief.
4. The application can generate three distinct design concepts.
5. A user can select one concept.
6. The application can generate furniture and material recommendations.
7. The spatial engine can create a dimensioned 2D room plan.
8. Basic room boundary and furniture overlap checks work.
9. Budget calculations are deterministic and tested.
10. The AI evaluation is based on the actual structured project data.
11. A complete PDF report can be generated.
12. Invalid inputs and API errors are handled gracefully.
13. Automated tests cover the critical deterministic functionality.
14. The application can be deployed and demonstrated without requiring undocumented manual steps.

## 12. Product Roadmap

### V1 — Core Room Intelligence Workflow

**Current development scope**

A complete workflow from room configuration to AI-assisted design proposal, 2D layout, budget analysis, and PDF reporting.

### V2 — Planned

- Vision model integration
- Room photograph analysis
- Image-based style extraction
- AI-generated design concept images
- Additional layout alternatives

### V3 — Planned

- 3D visualization
- Multi-room planning
- Product catalog integration
- Advanced spatial optimization

V2 and V3 are roadmap items only. They must not expand the V1 implementation scope.

## 13. Project Principles

The following principles guide all development decisions:

1. Practical problem-solving over feature quantity.
2. Real AI functionality over superficial AI labels.
3. Deterministic calculations over AI-generated arithmetic.
4. Clear separation between AI and application logic.
5. Small, maintainable, testable components.
6. Minimal dependencies.
7. No unnecessary SaaS infrastructure.
8. No unsupported claims about design accuracy.
9. A complete V1 is more valuable than an unfinished complex product.
10. Every feature must contribute directly to the core user workflow.

## 14. Project Definition of Done

The project is complete when the V1 application works end to end, passes its critical tests, produces a consistent PDF report, and can be demonstrated through a polished Streamlit interface.

The final portfolio presentation will include:

- English README
- Turkish README
- Actual application screenshots
- Technical overview
- Feature descriptions
- V1/V2/V3 roadmap
- Clear project limitations

Screenshots will be captured from the actual running application and stored in `docs/screenshots/`.

The project must not present planned features as completed functionality.
