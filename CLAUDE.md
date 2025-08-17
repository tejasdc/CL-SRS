# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Concept-Level Spaced Repetition System (CL-SRS) MVP that implements voice-first learning with AI-powered grading. The system ingests content, generates concept-based questions, and schedules reviews using a sophisticated spaced repetition algorithm.

## Architecture

### Monorepo Structure
```
/app
  /api       # FastAPI endpoints for ingestion, authoring, grading
  /ui        # Three-screen React client (Due Cards, Input, Graph)
  /lib/clsrs # Pure scheduling and math functions (reusable library)
/llm
  authoring/  # Unified JSON-only item authoring prompts
  grading/    # JSON-locked grader prompts and validators
/test
  unit/       # R/S math, scheduling, deterministic checks
  integration/ # ASR→grade→update end-to-end tests
```

## Core Components

### 1. CL-SRS Library (`/lib/clsrs`)
Pure functions implementing the scheduling algorithm:
- Predictive forgetting: R(t) = exp(−Δt / S)
- Stability updates based on outcomes (success/partial/fail)
- Latency normalization with log-z against rolling successful recalls
- Concept-level aggregation and KC coverage tracking
- Scheduling priorities based on retention predictions

### 2. Voice-First Grading Pipeline
1. Audio capture with tap-to-start/stop mic control
2. ASR (Whisper) → transcript with confidence and word timestamps
3. Deterministic checks (regex, numeric tolerance) take precedence
4. LLM grading only when needed for semantic equivalence
5. Post-processing with latency penalties and score adjustments
6. Update SRS state and log attempts

### 3. Authoring System
- Unified JSON-only prompts for concept and item generation
- Strict validation with no partial writes
- Enforces ≥1 anchor item per concept
- Required KC coverage (discrimination + application)
- Voice-robustness in answer specifications

## Key Data Models

### Concept
- ID, title, description, prerequisites, relations
- Knowledge Components (KCs): definition, procedure, discrimination, application, boundary_case, contrast
- Policy settings for DDB (0.6-0.8) and coverage thresholds
- Scheduler state with stability and next review time

### Item
- Single KC per item (enforced)
- Type: anchor (hand-authored) or variant (generated)
- Answer spec with regex/numeric acceptance rules
- Cue uniqueness within concept
- Learner state tracking

### Attempt Log
- ASR metadata (transcript, confidence, timestamps)
- Grader verdict and scoring details
- Outcome mapping to success/partial/fail

## Development Commands

### Build and Test
```bash
# Python components (scheduling library, API)
pytest test/unit/          # Unit tests for CL-SRS math
pytest test/integration/   # End-to-end grading pipeline tests
pytest --cov=/lib/clsrs    # Coverage report for scheduler

# Node/React UI
cd app/ui
npm install               # Install dependencies
npm run dev              # Development server
npm run build            # Production build
npm test                 # Run UI tests
```

### Running the System
```bash
# Start API server
cd app/api
uvicorn main:app --reload --port 8000

# Start UI development server
cd app/ui
npm run dev
```

### Linting and Type Checking
```bash
# Python
ruff check app/          # Linting
mypy app/               # Type checking

# JavaScript/TypeScript
cd app/ui
npm run lint            # ESLint
npm run typecheck       # TypeScript checking
```

## API Endpoints

- `POST /ingest_url` - Extract text from URL
- `POST /author_questions` - Generate concepts and items from text
- `POST /grade_attempt` - Process voice/text answer with grading pipeline
- `GET /due_cards` - Retrieve cards scheduled for review

## Critical Implementation Rules

### Grading Precedence
Deterministic acceptance (regex/numeric) ALWAYS takes precedence over LLM grading. The LLM cannot downgrade a deterministic success.

### JSON Validation
- All LLM outputs must be strict JSON
- Retry once on invalid JSON, then fail with `invalid_input`
- No partial writes - validate completely before persisting

### Voice Normalization
Apply consistently in authoring and grading:
- Lowercase, trim whitespace, collapse spaces
- Strip filler words
- Normalize numbers and units

### Variant Safety
- Never change deep_operation
- Maintain cue uniqueness within concept
- Target difficulty DDB ≈ 0.70
- Abort generation on any safety check failure

## Testing Strategy

### Unit Test Coverage
- Target >95% branch coverage on `/lib/clsrs`
- Test all R/S update formulas against spec
- Verify scheduling priorities and interval calculations

### Integration Test Cases
- Golden test cases for success/partial/fail outcomes
- Verify deterministic acceptance cannot be downgraded
- Test full ASR→normalize→grade→update pipeline

### Fixture Data
- 3 concepts with prereqs and contrasts
- 2 anchors + 4 variants per concept
- Simulated learner profiles (fast/accurate, slow/accurate, careless)

## Environment Variables

```bash
# LLM Configuration
OPENAI_API_KEY=...           # For authoring and grading
WHISPER_API_KEY=...          # For ASR

# Model Versions (pinned)
AUTHORING_MODEL=gpt-4
GRADING_MODEL=gpt-4
AUTHORING_PROMPT_VERSION=authoring_v1
GRADING_PROMPT_VERSION=grade_v1
```

## Work Order Sequence

When implementing features, follow this strict order:
1. WO-01: Scaffolding & Config
2. WO-02: Schemas & Validators
3. WO-03: `/lib/clsrs` Math
4. WO-04: Authoring Prompt & Service
5. WO-05: Ingestion
6. WO-06: Grader Prompt & Service
7. WO-07: UI — Review Screen
8. WO-08: UI — Input Screen
9. WO-09: UI — Graph P1
10. WO-10: Telemetry & Weekly Calibration
11. WO-11: Fixtures & E2E

## Acceptance Criteria

- URL ingestion → concepts with items in ≤30s
- Voice answers with fillers → success
- Near-miss answers → partial with specific feedback
- Low-confidence audio → retry without stability change
- All endpoints return strict JSON (no free-form prose)
- Invalid LLM JSON handled safely with one retry