<h1 align="center">Concept-Level Spaced Repetition (CL-SRS)</h1>

<p align="center">
  <strong>A new spaced repetition algorithm that schedules at the concept level, not the card level.</strong>
</p>

<p align="center">
  <a href="#the-invention">The Invention</a> &middot;
  <a href="#why-card-level-srs-is-broken">Why Card-Level Is Broken</a> &middot;
  <a href="#the-algorithm">The Algorithm</a> &middot;
  <a href="#quick-start">Quick Start</a> &middot;
  <a href="#architecture">Architecture</a>
</p>

---

## The Invention

Every spaced repetition system ever built — Anki, SuperMemo, FSRS, Leitner — operates at the same level: the **card**. One fact, one interval, one self-reported grade. The algorithm sees a stream of pass/fail signals and adjusts timing. That's it.

This is a fundamental limitation. Cards are atoms. But knowledge isn't atomic — it's structured. You don't "know" photosynthesis because you can recall its definition. You know it when you can distinguish C3 from C4 pathways, apply it to explain why shade plants adapt differently, and identify where the process becomes rate-limited. That's understanding. Cards can't measure it.

**CL-SRS is a new scheduling algorithm that operates at the concept level.** It tracks six dimensions of understanding per concept, gates interval stretching on demonstrated mastery across those dimensions, and uses AI to evaluate comprehension — not just recall. No existing SRS does this.

### What's New

1. **Concept-level scheduling** — Items are grouped into concepts. The scheduler operates on concepts, not individual cards. A concept's stability is the median of its items, and its next review is determined by aggregate coverage, not any single card.

2. **Six-dimension knowledge tracking** — Each concept is tested across definition, procedure, discrimination, application, boundary cases, and contrast. Coverage per dimension decays exponentially over time. You can't coast on easy dimensions.

3. **Coverage gating** — This is the key mechanism. A concept's review interval only stretches when discrimination AND application coverage exceed their thresholds. Knowing the definition isn't enough. The algorithm forces depth before it grants spacing.

4. **AI-graded understanding** — Instead of self-grading ("Did I get it? Eh, I'll hit Good"), the system listens to your spoken answer and evaluates what you actually understand — what's present, what's missing, where the confusion is. Grading is evidence-based, not self-reported.

## Why Card-Level SRS Is Broken

Card-level SRS has a structural blind spot: it conflates **recall** with **understanding**.

You can have a card "What is mitosis?" at a 30-day interval — the algorithm thinks you know it well — while you have no idea how mitosis differs from meiosis. The card-level algorithm has no way to detect this. It doesn't know that other dimensions of understanding exist, let alone that they're weak.

This leads to real problems:

- **Surface learning** — Learners optimize for recall without building transferable understanding
- **Gaming the interval** — Self-grading lets you hit "Easy" on cards you barely comprehend, inflating intervals without real mastery
- **No gap detection** — The algorithm can't tell the difference between "knows the definition" and "understands the concept deeply"
- **Isolation** — Cards exist in a vacuum. No prerequisite relationships, no contrast pairs, no coverage requirements

CL-SRS addresses all of these by moving the scheduling unit from the card to the concept, and by requiring demonstrated coverage across multiple knowledge dimensions before stretching intervals.

## The Algorithm

### Knowledge Dimensions

Every concept is decomposed into items across six dimensions:

| Dimension | What It Measures | Why It Matters |
|-----------|-----------------|----------------|
| **Definition** | Can you state what it is? | Baseline recall |
| **Procedure** | Can you describe how it works? | Procedural knowledge |
| **Discrimination** | Can you distinguish it from similar concepts? | Prevents interference |
| **Application** | Can you use it in a new context? | Transfer learning |
| **Boundary Case** | Do you know where it breaks down? | Depth of understanding |
| **Contrast** | Can you compare it to related concepts? | Relational knowledge |

### The Forgetting Curve

Retention follows a standard exponential decay:

```
R(t) = exp(-Δt / S)
```

Where `S` is stability (in days) and `Δt` is time since last review. Stability updates are outcome-dependent:

| Outcome | High R (≥ 0.6) | Low R (< 0.6) |
|---------|----------------|---------------|
| **Success** | S × 3.0 | S × (1 + R/0.6 × 2) |
| **Partial** | S × 1.5 | S × 1.2 |
| **Fail** | S × 0.5 | S × 0.5 |

Stability is clamped to [1, 3650] days.

### Coverage Gating (The Core Innovation)

Each knowledge dimension has a coverage score that decays over time:

```
coverage[kc] = Σ (weight × exp(-days_ago / τ))
```

Where `weight` = 1.0 (success), 0.5 (partial), 0.0 (fail), and `τ` is a per-dimension decay constant (14 days for core dimensions, 21 days for boundary/contrast).

**The gating rule:** A concept's review interval only stretches when:
- `discrimination_coverage ≥ 1.0`
- `application_coverage ≥ 1.0`

This means you can ace every definition card in a concept, but if you haven't demonstrated discrimination and application, your intervals stay short. The algorithm *forces* depth.

### Concept-Level Aggregation

- **Concept stability** = median of item stabilities
- **Scheduling priority** = due concepts first (sorted by overdue-ness), then concepts nearest R ≈ 0.7 (optimal challenge point)
- **Item intervals** = `-S × ln(R_target)` where R_target varies by outcome (0.9 for success, 0.8 for partial, 0.95 for fail)

### Latency Normalization

Response time is normalized against a personal baseline using log-z scores:

```
z = (log(ms) - log_mean) / log_std
```

With priors `(ln(2500), 0.6)` until 5+ successful attempts establish a baseline. Slow responses get penalized — fluency matters, not just correctness.

## Voice-First Grading

Instead of self-grading, CL-SRS uses a multi-stage grading pipeline:

```
Speech ──▶ ASR (Whisper) ──▶ Normalize ──▶ Deterministic ──▶ LLM Semantic
                                              Check            (if needed)
                                               │
                                               ▼
                                        Regex/numeric match?
                                        YES → SUCCESS (immutable)
                                        NO  → LLM evaluates meaning
```

Key design decision: **deterministic checks always take precedence over AI.** If your answer matches the regex or falls within numeric tolerance, no LLM hallucination can downgrade it. The AI adds semantic understanding on top — it doesn't replace reliable checks.

The normalizer handles voice artifacts: filler words ("um", "like"), number words ("twenty five" → "25"), whitespace collapse, and case normalization. This is enforced consistently in both content authoring and answer grading.

## How It Compares

| | CL-SRS | Anki (SM-2) | SuperMemo | FSRS |
|---|---|---|---|---|
| Scheduling unit | **Concept** | Card | Card | Card |
| Knowledge dimensions | **6 (tracked)** | 1 (pass/fail) | 1 (grade 0-5) | 1 (grade) |
| Coverage gating | **Yes** | No | No | No |
| Grading | **AI + deterministic** | Self-graded | Self-graded | Self-graded |
| Voice input | **Native** | No | No | No |
| Content generation | **AI from any URL** | Manual | Manual | Manual |
| Gap detection | **Per-dimension** | None | None | None |
| Open source | Yes | Yes | No | Yes |

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- OpenAI API key

### Run

```bash
cp .env.example .env    # Add your OpenAI API key
./start.sh              # Starts API + UI
```

<details>
<summary>Manual setup</summary>

```bash
# Backend
cd app/api
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Frontend
cd ../ui
npm install

# Start
python run_api.py          # API at http://localhost:8000
cd app/ui && npm run dev   # UI at http://localhost:5173
```
</details>

### Try the API

```bash
# Feed it content
curl -X POST http://localhost:8000/ingest_url \
  -H "Content-Type: application/json" \
  -d '{"url": "https://en.wikipedia.org/wiki/Spaced_repetition"}'

# Generate concept-level questions
curl -X POST http://localhost:8000/author_questions \
  -H "Content-Type: application/json" \
  -d '{"text": "The Earth orbits the Sun in 365.25 days."}'

# See what's due
curl http://localhost:8000/due_cards
```

## Architecture

```
/app
  /api              # FastAPI backend
    /services       # Authoring, grading, ingestion pipelines
    models.py       # Pydantic schemas (strict validation)
    storage.py      # Persistence layer
  /ui               # React + TypeScript frontend (Review, Input, Graph screens)
  /lib/clsrs        # Pure scheduling library (zero side effects)
    srs.py          # R/S math, coverage gating, scheduling
/llm
  /authoring        # Versioned authoring prompts (JSON-only output)
  /grading          # Versioned grading prompts (schema-locked)
/test
  /unit             # Deterministic algorithm tests
  /integration      # End-to-end pipeline tests
```

### Tech Stack

| Layer | Technology |
|-------|-----------|
| **API** | FastAPI, Pydantic, OpenAI GPT-4 |
| **Scheduling** | CL-SRS library (pure Python, zero dependencies, portable) |
| **Frontend** | React 18, Tailwind CSS, shadcn/ui, Framer Motion |
| **Knowledge Graph** | vis-network |
| **Speech-to-Text** | Whisper API |

### Design Principles

1. **Deterministic > LLM** — Regex/numeric acceptance always takes precedence. AI enriches, never overrides.
2. **Pure scheduling library** — `/lib/clsrs` has zero side effects. Deterministic, testable, portable to any language.
3. **Frozen prompts** — LLM prompts are versioned files, not strings in code. Auditable and A/B testable.
4. **No partial writes** — Validate completely before persisting. Invalid LLM output gets one retry, then fails safely.
5. **Voice-native** — Normalization rules enforced consistently in content authoring and answer grading.

## Roadmap

**Shipped:**
- CL-SRS scheduling algorithm with 6-dimension coverage gating
- AI content generation from any URL or text
- Voice-first grading pipeline (ASR + deterministic + LLM)
- Interactive knowledge graph visualization
- Three-screen UI (Review, Input, Graph)

**Building:**
- Calibration telemetry and learning analytics
- Conversational follow-up (multi-turn probing of weak dimensions)
- Database persistence and multi-user support
- Mobile-optimized voice experience

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ingest_url` | POST | Extract text from any URL |
| `/author_questions` | POST | Decompose text into concepts + items |
| `/grade_attempt` | POST | Grade a voice/text answer |
| `/due_cards` | GET | Get concepts scheduled for review |

Interactive docs at `http://localhost:8000/docs` when running.

## Contributing

The codebase is modular:

- **The algorithm** — `app/lib/clsrs/srs.py` (pure functions, easy to test and extend)
- **Grading pipeline** — `app/api/services/grading.py` (multi-stage, well-documented)
- **UI** — `app/ui/src/components/` (React + Tailwind)
- **LLM prompts** — `llm/` (version-controlled text files)

## License

MIT
