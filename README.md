# CL-SRS: Concept-Level Spaced Repetition System

A voice-first learning system that implements concept-level spaced repetition with AI-powered grading.

## Project Status

### Completed Work Orders
- ✅ WO-01: Scaffolding & Config - Repository structure and configuration
- ✅ WO-02: Schemas & Validators - Data models with strict validation  
- ✅ WO-03: CL-SRS Math Library - Core scheduling algorithms
- ✅ WO-04: Authoring Prompt & Service - LLM-based content generation
- ✅ WO-05: Ingestion Service - URL and text extraction
- ✅ WO-06: Grading Pipeline - Complete ASR→normalize→deterministic→LLM pipeline

### ✅ All Core Features Complete!
- ✅ WO-07: Review Screen - Modern card-based review with voice recording
- ✅ WO-08: Input Screen - URL/text ingestion with AI question generation  
- ✅ WO-09: Graph Visualization - Interactive knowledge graph with vis-network

### Next Steps (Optional Enhancements)
- WO-10: Telemetry & Weekly Calibration
- WO-11: Integration Tests & Fixtures

## Getting Started

### Prerequisites
- Python 3.11+ (see note below for Python 3.13)
- Node.js 18+
- OpenAI API key
- Whisper API key (for voice recognition)

**Note for Python 3.13 users:** If you encounter issues installing `lxml`, use the alternative requirements:
```bash
pip install -r app/api/requirements-py313.txt
```

### Quick Start

1. **Clone and setup:**
```bash
# Copy environment file
cp .env.example .env
# Edit .env with your OpenAI API key

# Run everything with one command:
./start.sh
```

Or manually:

```bash
# Install Python dependencies
cd app/api
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Install Node dependencies
cd ../ui
npm install
```

2. **Run tests:**
```bash
# Python tests
pytest test/unit -v

# Check test coverage
pytest test/unit --cov=app/lib/clsrs --cov-report=html
```

3. **Start the API server:**
```bash
# Using the run script
python run_api.py

# Or directly with uvicorn
uvicorn app.api.main:app --reload --port 8000

# API will be available at:
# - http://localhost:8000
# - API docs: http://localhost:8000/docs
# - ReDoc: http://localhost:8000/redoc
```

4. **Test the API:**
```bash
# Health check
curl http://localhost:8000/health

# Ingest a URL
curl -X POST http://localhost:8000/ingest_url \
  -H "Content-Type: application/json" \
  -d '{"url": "https://en.wikipedia.org/wiki/Spaced_repetition"}'

# Author questions from text
curl -X POST http://localhost:8000/author_questions \
  -H "Content-Type: application/json" \
  -d '{"text": "The Earth orbits around the Sun. It takes 365.25 days to complete one orbit."}'

# Get due cards
curl http://localhost:8000/due_cards
```

## Project Structure

```
/app
  /api           # FastAPI backend
  /ui            # React frontend
  /lib/clsrs     # Pure SRS math functions
/llm
  /authoring     # Item generation prompts
  /grading       # Grading prompts
/test
  /unit          # Unit tests
  /integration   # Integration tests
```

## UI Features

### Modern, Minimalist Design
- **Tailwind CSS** for utility-first styling
- **shadcn/ui** components for consistent, modern UI
- **Framer Motion** for smooth animations
- **Dark mode ready** with CSS variables
- **Fully responsive** mobile-first design

### Three Main Screens

#### 1. Review Screen
- Card-based review interface
- Voice recording with tap-to-start/stop
- Real-time grading feedback
- Progress tracking
- Smooth card transitions

#### 2. Input Screen  
- URL or text input modes
- AI-powered question generation
- Loading states and success feedback
- Input validation and tips

#### 3. Knowledge Graph
- Interactive network visualization
- Color-coded performance indicators
- Concept relationships (prerequisites & contrasts)
- Click to view concept details
- Zoom, pan, and drag support

## Core Components

### 1. Data Models (`app/api/models.py`)
- **Concept**: Learning concepts with KCs, prerequisites, and scheduling state
- **Item**: Individual questions with answer specifications
- **VariantTemplate**: Templates for generating item variations
- **AttemptLog**: Complete record of each learning attempt

### 2. Validators (`app/api/validators.py`)
- Strict schema validation (no unknown fields)
- Cue uniqueness checking within concepts
- Variant safety validation
- Authoring output validation

### 3. SRS Library (`app/lib/clsrs/srs.py`)
- **r_pred()**: Predictive forgetting curve R(t) = exp(-Δt/S)
- **update_S()**: Stability updates based on outcomes
- **latency_z()**: Response time normalization
- **kc_coverage()**: Knowledge component coverage tracking
- **schedule_concepts()**: Intelligent concept selection
- **next_item_interval()**: Calculate review intervals

## Key Features

- **Voice-First**: Optimized for voice input with ASR integration
- **Concept-Level Scheduling**: Reviews scheduled at concept level, not individual items
- **Strict Validation**: All data strictly validated against schemas
- **Deterministic Grading**: Regex/numeric checks take precedence over LLM
- **Coverage Gating**: Concepts only stretch when KC coverage thresholds met

## Development Guidelines

1. **No Partial Writes**: Validate completely before persisting
2. **Deterministic > LLM**: Deterministic acceptance cannot be downgraded
3. **Strict JSON**: All LLM outputs must be valid JSON (one retry allowed)
4. **Voice Normalization**: Consistent normalization in authoring and grading

## Next Development Steps

To continue building:

1. **WO-04**: Create authoring prompts and `/author_questions` endpoint
2. **WO-05**: Implement URL ingestion with readability
3. **WO-06**: Build the complete grading pipeline
4. **WO-07-09**: Implement the three-screen UI
5. **WO-10-11**: Add telemetry and integration tests

Run `pytest test/unit -v` to verify all math functions work correctly before proceeding.