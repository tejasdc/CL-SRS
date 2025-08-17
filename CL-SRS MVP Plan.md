# CL-SRS MVP — Implementation Plan (LLM-Executable)

## 0) Scope, Guardrails, and Non-Goals

- **In scope (MVP):** three-screen UI (Due Cards, Input, Graph P1), URL/text ingestion, concept-level item authoring, review flow with **voice-first** answers, ASR→deterministic checks→LLM grading pipeline, CL-SRS scheduler as a reusable library, storage for concepts/items/attempts, knowledge graph **display only** (no editing).
    
- **Out of scope (block hallucinations):** curriculum discovery, tutoring, live web search, embeddings-based reasoning for correctness, multi-user features, notifications, spaced repetition beyond CL-SRS rules in spec, advanced graph editing, analytics dashboards, AB testing. The LLM must not introduce new fields, KCs, or endpoints not listed here.
    

---

## 1) Repository Layout (monorepo, minimal)

```
/app
  /api           # Fast endpoints
  /ui            # 3-screen client
  /lib/clsrs     # Scheduling + math (reusable)
/llm
  authoring/     # unified JSON-only item authoring prompt
  grading/       # JSON-locked grader prompt + validator
/test
  unit/          # R/S math, scheduling, checks
  integration/   # ASR→grade→update end-to-end

```


**Definition of Done (DoD):** All folders exist; `lib/clsrs` contains pure functions; `llm/*` holds immutable prompt files; no extra directories.

---

## 2) Data Model (authoritative schemas, no extra fields)

### 2.1 Concept (store exactly these fields)

```
{
  "id": "uuid",
  "title": "string",
  "description": "string",
  "prereqs": ["uuid"],
  "relations": [{"type":"contrasts_with","concept_id":"uuid"}],
  "kcs": ["definition","procedure","discrimination","application","boundary_case","contrast"],
  "anchors": ["item_uuid"],
  "item_ids": ["item_uuid"],
  "policy": {
    "ddb_min": 0.6, "ddb_max": 0.8,
    "coverage_model": {
      "required_kcs": ["discrimination","application"],
      "tau_days": {
        "definition":14,"procedure":14,"discrimination":14,
        "application":14,"boundary_case":21,"contrast":21
      },
      "outcome_weights":{"success":1.0,"partial":0.5,"fail":0.0},
      "thresholds":{"definition":0.0,"procedure":0.0,"discrimination":1.0,"application":1.0,"boundary_case":0.0,"contrast":0.0},
      "fallbacks":{"if_missing_kc":"proportional","proxy_map":{"application":"procedure"}}
    },
    "min_anchors_per_session": 1
  },
  "scheduler_state": {
    "next_review_at": "ISO-8601",
    "last_outcome": "success|partial|fail",
    "stability_s": 0.0,
    "last_session_at": "ISO-8601",
    "interval_days": 0.0
  }
}
```

**DoD:** Field names/nesting match exactly; validate on insert; reject unknown fields.

### 2.2 Item
```
{
  "id":"uuid","concept_id":"uuid",
  "kc":"definition|procedure|discrimination|application|boundary_case|contrast",
  "type":"anchor|variant",
  "prompt":"string",
  "answer":"string",
  "acceptance_regex":"string|nullable",
  "forbidden_terms":["string"],
  "cue":{"text":"string","features":["string"]},
  "foils":["string"],
  "variant_template_id":"uuid|null",
  "generator_params":{"seed":0,"params":{},"param_hash":"sha256:..."},
  "learner_state":{
    "next_review_at":"ISO-8601","last_review_at":"ISO-8601",
    "stability_s":0.0,"attempts":0,"streak":0
  }
}
```
**DoD:** Exactly one `kc` per Item; `cue.text` unique within concept; anchors exist for every concept (≥1).

### 2.3 Variant Template (if present)

- Keep `deep_operation` invariant; difficulty model optional; enforce dedupe via `param_hash`.  
    **DoD:** Candidate variants must pass cue-uniqueness, answer-equivalence, and difficulty window checks before persisting.
    

### 2.4 Attempt Log (voice/text)

```
{
  "attempt_id":"uuid","ts":"ISO-8601",
  "item_id":"uuid","concept_id":"uuid",
  "asr":{"transcript":"string","confidence":0..1,"alts":["string"],"speech_ms":0,"word_timestamps":[{"w":"string","ms_start":0,"ms_end":0}]},
  "latency_ms":0,
  "grader":{
    "model":"string","prompt_version":"string",
    "verdict":"success|partial|fail|invalid_input",
    "score_raw":0,"score_adj":0,
    "matched_criteria":["string"],
    "missing_concepts":["string"],
    "flags":{"forbidden_term_hit":[],"asr_low_confidence":false},
    "explanation_for_user":"string"
  },
  "outcome":"success|partial|fail"
}
```
**DoD:** JSON schema validated; logged for every graded attempt.

---

## 3) CL-SRS Library (`/lib/clsrs`) — Pure Functions Only

### 3.1 Predictive forgetting & item updates

- **R(t) = exp(−Δt / S)**; at presentation use **R_pred**; update `S` by outcome; clamp S to [1, 3650].  
    **DoD:** Deterministic unit tests reproduce spec formulas & thresholds.
    

### 3.2 Latency normalization

- Log-z normalization against rolling successful recalls; priors if insufficient data; threshold `z_success_max`.  
    **DoD:** Given a series of latencies, function returns consistent z; matches defaults.
    

### 3.3 Concept aggregates & coverage

- Same-time rule, median S_c, decayed KC coverage with τ per KC, thresholds gating concept stretch.  
    **DoD:** Aggregation functions return identical values to reference examples.
    

### 3.4 Scheduling

- **Concept selection:** prioritize due; else R_c_pred nearest 0.7 with coverage gating.
    
- **After session:** adjust S_c & interval per success/partial/fail rules; set `next_review_at`.
    
- **Per-item intervals:** `interval_i = -S_i * ln(R_target_item)` with target by outcome.  
    **DoD:** Deterministic selection given fixed inputs; intervals match formulas.
    

---

## 4) Voice-First Review & Grading Pipeline

### 4.1 Client capture

- UI shows card → user taps **Mic** (tap to start/stop).
    
- Collect **start timestamp** for latency; send audio blob.
    

### 4.2 Server pipeline

1. **ASR** (Whisper or equivalent): transcript, word timestamps, confidence, alts.
    
2. **Normalization (deterministic)**: lowercase, trim, collapse whitespace, strip fillers, normalize numbers/units.
    
3. **Deterministic checks** (short-circuit):
    
    - Regex acceptance → provisional **success**.
        
    - Numeric within tolerance (+units if required) → success; within 2×tol or unit missing (if required) → **partial**.
        
4. **LLM Grader** (schema-locked) if needed or for feedback:
    
    - Input card = item metadata (prompt, canonical answer, rubric, examples, acceptance rules) + normalized transcript + ASR meta.
        
    - System prompt directs: prefer deterministic acceptance first; output strict JSON only.
        
5. **Post-processing**:
    
    - Apply latency penalties, forbidden-term penalty, clamp score, map to success/partial/fail bands.
        
    - Deterministic result takes precedence if it exists.
        
6. **Update SRS**; log attempt; return verdict, feedback line, and next review ETA.  
    **DoD:** End-to-end returns JSON with `outcome`, `score_adj`, and `explanation_for_user` for every attempt; invalid JSON triggers one retry else `invalid_input`.
    

### 4.3 Grader I/O Schemas (hard constraints)

- **Item Answer Contract**: `answer_spec.mode`, `accept.regex|aliases|numeric`, `policy.strictness|forbidden_terms|z_*`, voice normalization flags.
    
- **Grader Output**: `verdict|score_0_100|confidence_0_1|matched_criteria|missing_concepts|parsed|flags|explanation_for_user`.  
    **DoD:** Strict JSON schema validation; deterministic > LLM rule enforced.
    

---

## 5) Authoring Pipeline (Concept→Anchors→Items)

### 5.1 Prompting contract (JSON-only)

- Use the **Unified Authoring Prompt (voice-first, JSON-only)** to produce: `concept` (id/title/summary/anchors/policy) + `items[]` with exactly one `kc` each, strict `answer_spec`, rubric, examples, optional choice foils, variant_template, and voice robustness flags.
    
- The authoring LLM **must** emit a single JSON object and self-check constraints before emitting.  
    **DoD:** Emitted JSON validates and persists without edits; any failure aborts authoring (no partial writes).
    

### 5.2 Coverage & safety at authoring time

- Enforce **≥1 anchor**, **≥1 discrimination and ≥1 application** if required by concept policy; forbid cue leaks; variants hold operation constant; numeric tolerances set when relevant.  
    **DoD:** Validator rejects sets that miss required KCs or permit cue leaks; no duplicates in `cue.text`.
    

---

## 6) API Endpoints (stable, minimal)

### 6.1 `POST /ingest_url`

- **Input:** `{ "url": "string" }`
    
- **Process:** fetch + extract main text; return `{ "text": "string", "meta": {...} }`.
    
- **DoD:** Returns 200 with non-empty `text` or 4xx with reason. _(MVP: a simple readability extractor; no crawling)_
    

### 6.2 `POST /author_questions`

- **Input:** `{ "text":"string", "system_prompt_id":"authoring_v1", "concept_id?":"string" }`
    
- **Process:** call authoring LLM with unified prompt; JSON-validate; persist Concept/Items; initialize S0_by_kc; schedule first session immediately if concept had none.
    
- **Output:** `{ "concept_id":"uuid", "item_ids":["uuid"] }`
    
- **DoD:** Fails closed on JSON invalid; **no heuristic fixes**; uses init rules for S0 and concept bootstrapping.
    

### 6.3 `POST /grade_attempt`

- **Input:** `{ "item_id":"uuid", "audio_blob|text":..., "asr_payload?":{...}, "latency_ms":int }`
    
- **Output:** `{ "outcome":"success|partial|fail", "score_adj":int, "explanation_for_user":"string", "next_review_eta":"ISO-8601" }`
    
- **DoD:** Mirrors grading spec exactly; logs attempt with all required fields.
    

### 6.4 `GET /due_cards`

- **Input:** `{ "now":"ISO-8601" }`
    
- **Output:** `{ "items":[{"item_id":"uuid","concept_id":"uuid","prompt":"string","kc":"string"}] }`
    
- **DoD:** Uses library scheduling; respects concept coverage gating.
    

---

## 7) Client (3 Screens + Swipe)

1. **Review (default)**
    
    - List of due cards (or “You’re all caught up”).
        
    - Card view: prompt, small concept details, **Mic** button (tap to start/stop), “Submit”, feedback line, “Next”.
        
    - DoD: Mic state clearly visible; prevents multiple submissions; shows one-line verdict + next ETA.
        
2. **Input**
    
    - Text field for URL or paste. “Generate Questions” button.
        
    - DoD: Calls `/ingest_url` then `/author_questions`; success → snackbar with “X items added”; failure → clear error; no autosave drafts.
        
3. **Graph (P1, read-only)**
    
    - Render nodes = concepts; edges from `prereqs` + `contrasts_with`.
        
    - Node tooltip: title, summary, S_c, next_review_at.
        
    - DoD: No editing; zoom/pan; selecting a node filters next Review session.
        

---

## 8) Initialization Rules (Cold Start)

- **Item S0_by_kc (days):** definition 2.5, procedure 2.5, discrimination 2.0, application 2.0, boundary_case 1.8, contrast 1.8.
    
- **Concept with no history:** schedule immediately; S_c = median of item S0; interval_days = 1.0.  
    **DoD:** First session appears right after authoring; next intervals computed per outcomes.
    

---

## 9) Variant Generation Safety (if templates are present)

- Allowed: numeric/context skins, exemplar swaps, near-miss foils with single violated feature; forbidden: changing deep operation, adding new concepts beyond prereqs.
    
- Difficulty window target 0.7; resample once if R_pred outside [0.5, 0.9]; else abort generation.  
    **DoD:** Abort on any check failure; never persist unsafe variants.
    

---

## 10) LLM Prompts (frozen text files)

- **Authoring system prompt:** use the **Unified JSON-only, voice-first authoring** spec verbatim; do not alter output shape; enforce self-check list before emit.  
    **File:** `/llm/authoring/authoring_v1.prompt` (content from the consolidated MD).
    
- **Grader system prompt:** follow **LLM Grader** spec; prefer deterministic, output strict JSON; one retry on schema failure; mark `invalid_input` if still invalid.  
    **File:** `/llm/grading/grade_v1.prompt`.
    

**DoD:** Prompts checked into repo; SHA pinned in config; orchestrator enforces model + prompt version stamping.

---

## 11) Telemetry & Reliability (minimal, required)

- Counters: `json_invalid_rate`, `asr_low_confidence_rate`, `%deterministic_accept`, calibration curve deciles vs actual accuracy.
    
- Reliability rules: deterministic checks override LLM; if `asr.confidence<0.5` or `invalid_input`, prompt retry and **do not** update item stability.  
    **DoD:** Weekly calibration job outputs JSON report; logs include all verdicts/penalties.
    

---

## 12) Test Harness & Fixtures

### Unit tests (pure)

- R/S update math, scheduling priority, per-KC latency z, coverage gating, interval calculators.  
    **DoD:** >95% branch coverage on `/lib/clsrs`.
    

### Integration tests

- Authoring JSON passes validator; items persisted; initial schedules set.
    
- Voice review: audio→ASR→deterministic→LLM→post-process→SRS update.  
    **DoD:** Golden cases for success/partial/fail; deterministic acceptance cannot be downgraded.
    

### Sanity fixtures

- 3 concepts with prereqs/contrasts, 2 anchors + 4 variants each; simulated learners (fast/accurate, slow/accurate, careless).  
    **DoD:** Scheduler keeps R_pred in DDB; concept stretch only after coverage thresholds.
    

---

## 13) Work Orders (execute strictly in order)

**WO-01: Scaffolding & Config**  
Create repo layout, config files, env for LLM/ASR keys. **DoD:** `npm test`/`pytest` passes empty suite.

**WO-02: Schemas & Validators**  
Implement JSON schemas for Concept/Item/VariantTemplate/AttemptLog; write strict validators; reject unknown fields. **DoD:** Round-trip samples validate.

**WO-03: `/lib/clsrs` Math**  
Implement R/S, latency z, coverage, scheduling, intervals; add unit tests from spec examples. **DoD:** All math tests pass.

**WO-04: Authoring Prompt & Service**  
Check in unified authoring prompt; build `/author_questions` endpoint, JSON validate, S0 init, immediate concept schedule. **DoD:** Given sample text, returns persisted concept+items.

**WO-05: Ingestion**  
Implement `/ingest_url` with readability extractor; returns main text. **DoD:** 200 with non-empty text on representative pages.

**WO-06: Grader Prompt & Service**  
Check in grader prompt; implement `/grade_attempt` with ASR→normalize→deterministic→LLM→post-process; precedence + penalties applied. **DoD:** Golden tests cover all branches.

**WO-07: UI — Review Screen**  
Due list, card view, Mic control, verdict line, “Next”; empty-state (“You’re all caught up”). **DoD:** Smooth single-tap start/stop; latency measured.

**WO-08: UI — Input Screen**  
URL/text input; calls `/ingest_url` then `/author_questions`; success snackbar + counts. **DoD:** Errors displayed verbosely; no silent failures.

**WO-09: UI — Graph P1**  
Read-only graph; node tooltip; tap-to-filter session. **DoD:** Visualizes prereqs/contrasts with basic styling.

**WO-10: Telemetry & Weekly Calibration Job**  
Counters, logs, weekly report. **DoD:** JSON file with deciles and AUC@Δ produced.

**WO-11: Fixtures & E2E**  
Seed 3 concepts; run simulated sessions; verify DDB, coverage, and stretch rules. **DoD:** Report shows expected behavior.

---

## 14) Pseudocode Stubs (freeze these; LLM fills bodies only)

`# /lib/clsrs/srs.py def r_pred(days_since_last: float, S: float) -> float: ... def update_S(S: float, outcome: str, r_pred_at_show: float, z_success_max: float=1.0) -> float: ... def latency_z(ms: int, baseline: list[int], priors=(ln(2500), 0.6)) -> float: ... def kc_coverage(events, tau_days_by_kc) -> dict: ... def schedule_concepts(concepts_state, now) -> list: ... def next_item_interval(S: float, outcome: str) -> float: ...`

`# /api/grade.py def grade_attempt(item, audio_or_text, now):     asr = ensure_asr(audio_or_text)     norm = normalize(asr.transcript)     verdict, score_raw = deterministic_accept(item.answer_spec, norm, asr)     out = None     if verdict is None or need_feedback(item):         out = call_llm_grader(item_card(item), norm, asr)         out = ensure_valid_json(out) or {"verdict":"invalid_input","score_0_100":0,"flags":{"asr_low_confidence":asr.confidence<0.5}}         if verdict is None: verdict = out["verdict"]; score_raw = out["score_0_100"]     score_adj, outcome = postprocess(verdict, score_raw, asr, item)     update_item_concept(item, outcome, now)     log_attempt(item, asr, out, score_adj, outcome)     return {"outcome": outcome, "score_adj": score_adj, "explanation_for_user": out and out["explanation_for_user"], "next_review_eta": eta(item)}`

**DoD:** Pseudocode maps line-by-line to grading flow; function names stable.

---

## 15) Acceptance Criteria (MVP)

- From a blank DB, user pastes a URL → **≤30s** later sees 1+ concepts with anchors + items due now; Review screen shows them.
    
- Speaking correct answers with minor fillers yields **success**; near-miss yields **partial** with a specific one-line fix; nonsense or low-confidence audio yields **retry** without stability change.
    
- After a short session, **next due times** update per formulas; Concept interval stretches only when KC coverage thresholds are met.
    
- No endpoint returns free-form prose where JSON is required; **any** invalid LLM JSON is retried once then safely handled.
    

---

## 16) Hard Constraints to Prevent Overreach

- **Deterministic > LLM**: if regex/numeric accept, grader cannot downgrade.
    
- **No new KCs or relations** beyond the fixed sets.
    
- **Abort on safety check failure** during variant generation; do not silently “fix”.
    
- **Voice-first** normalization rules enforced in both authoring (answer specs) and grading.
    
- **Strict JSON ONLY** for LLM outputs; never accept partial or multi-object dumps.