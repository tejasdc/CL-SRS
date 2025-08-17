"""
Data models for CL-SRS system - Pydantic v1 compatible
"""
from datetime import datetime
from typing import Dict, List, Optional, Literal, Any
from uuid import uuid4
from pydantic import BaseModel, Field, validator
from enum import Enum


class KnowledgeComponent(str, Enum):
    DEFINITION = "definition"
    PROCEDURE = "procedure"
    DISCRIMINATION = "discrimination"
    APPLICATION = "application"
    BOUNDARY_CASE = "boundary_case"
    CONTRAST = "contrast"


class ItemType(str, Enum):
    ANCHOR = "anchor"
    VARIANT = "variant"


class Outcome(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAIL = "fail"


class GraderVerdict(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAIL = "fail"
    INVALID_INPUT = "invalid_input"


class AnswerMode(str, Enum):
    TEXT = "text"
    NUMERIC = "numeric"
    CHOICE_SINGLE = "choice_single"
    CHOICE_MULTI = "choice_multi"
    CLOZE = "cloze"


# Concept Models
class CoverageModel(BaseModel):
    required_kcs: List[KnowledgeComponent] = [
        KnowledgeComponent.DISCRIMINATION,
        KnowledgeComponent.APPLICATION
    ]
    tau_days: Dict[str, int] = {
        "definition": 14,
        "procedure": 14,
        "discrimination": 14,
        "application": 14,
        "boundary_case": 21,
        "contrast": 21
    }
    outcome_weights: Dict[str, float] = {
        "success": 1.0,
        "partial": 0.5,
        "fail": 0.0
    }
    thresholds: Dict[str, float] = {
        "definition": 0.0,
        "procedure": 0.0,
        "discrimination": 1.0,
        "application": 1.0,
        "boundary_case": 0.0,
        "contrast": 0.0
    }
    fallbacks: Dict[str, str] = {
        "if_missing_kc": "proportional",
        "proxy_map": {"application": "procedure"}
    }


class ConceptPolicy(BaseModel):
    ddb_min: float = 0.6
    ddb_max: float = 0.8
    coverage_model: CoverageModel = Field(default_factory=CoverageModel)
    min_anchors_per_session: int = 1


class ConceptRelation(BaseModel):
    type: Literal["contrasts_with"] = "contrasts_with"
    concept_id: str


class SchedulerState(BaseModel):
    next_review_at: datetime
    last_outcome: Optional[Outcome] = None
    stability_s: float = 0.0
    last_session_at: Optional[datetime] = None
    interval_days: float = 0.0


class Concept(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    description: str
    prereqs: List[str] = []
    relations: List[ConceptRelation] = []
    kcs: List[KnowledgeComponent] = []
    anchors: List[str] = []
    item_ids: List[str] = []
    policy: ConceptPolicy = Field(default_factory=ConceptPolicy)
    scheduler_state: Optional[SchedulerState] = None

    @validator('anchors')
    def validate_anchors(cls, v):
        if len(v) < 1:
            raise ValueError("Concept must have at least 1 anchor item")
        return v
    
    class Config:
        use_enum_values = True


# Item Models
class NumericAcceptance(BaseModel):
    target: float
    tol_abs: Optional[float] = None
    tol_rel: Optional[float] = None
    units: Optional[str] = None
    units_required: bool = False


class AcceptanceRules(BaseModel):
    regex: Optional[List[str]] = None
    aliases: Optional[List[str]] = None
    numeric: Optional[NumericAcceptance] = None


class AnswerPolicy(BaseModel):
    strictness: Literal["strict", "lenient"] = "lenient"
    forbidden_terms: List[str] = []
    z_success_max: float = 2.0
    z_partial_max: float = 3.5


class AnswerSpec(BaseModel):
    mode: AnswerMode
    accept: AcceptanceRules
    policy: AnswerPolicy = Field(default_factory=AnswerPolicy)


class ItemCue(BaseModel):
    text: str
    features: List[str] = []


class GeneratorParams(BaseModel):
    seed: int
    params: Dict[str, Any] = {}
    param_hash: str


class LearnerState(BaseModel):
    next_review_at: datetime
    last_review_at: Optional[datetime] = None
    stability_s: float = 0.0
    attempts: int = 0
    streak: int = 0


class Item(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    concept_id: str
    kc: KnowledgeComponent
    type: ItemType
    prompt: str
    answer: str
    acceptance_regex: Optional[str] = None
    answer_spec: AnswerSpec
    forbidden_terms: List[str] = []
    cue: ItemCue
    foils: List[str] = []
    variant_template_id: Optional[str] = None
    generator_params: Optional[GeneratorParams] = None
    learner_state: Optional[LearnerState] = None

    @validator('generator_params', always=True)
    def validate_generator_params(cls, v, values):
        if values.get('type') == ItemType.VARIANT and v is None:
            raise ValueError("Variant items must have generator_params")
        return v
    
    class Config:
        use_enum_values = True


# Variant Template Models
class VariantConstraints(BaseModel):
    cue_features: List[str] = []
    forbidden_terms: List[str] = []
    difficulty: Dict[str, float] = {"target_p": 0.70}


class VariantUniqueness(BaseModel):
    dedupe_scope: str = "template"
    canonical_keys: List[str] = []


class DifficultyFeature(BaseModel):
    name: str
    weight: float


class DifficultyModel(BaseModel):
    kind: Literal["logistic"] = "logistic"
    intercept: float = 0.0
    features: List[DifficultyFeature] = []


class GenerationHistory(BaseModel):
    used_param_hashes: List[str] = []
    counts_by_param: Dict[str, int] = {}
    calibration_stats: Dict[str, Any] = {
        "by_feature": {},
        "global_success_rate_7d": 0.70
    }


class VariantTemplate(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    concept_id: str
    kc: KnowledgeComponent
    deep_operation: str
    parameters: Dict[str, Any] = {}
    prompt_template: str
    answer_template: str
    constraints: VariantConstraints = Field(default_factory=VariantConstraints)
    uniqueness: VariantUniqueness = Field(default_factory=VariantUniqueness)
    difficulty_model: Optional[DifficultyModel] = None
    generation_history: GenerationHistory = Field(default_factory=GenerationHistory)
    
    class Config:
        use_enum_values = True


# Attempt Log Models
class ASRData(BaseModel):
    transcript: str
    confidence: float = Field(ge=0.0, le=1.0)
    alts: List[str] = []
    speech_ms: int = 0
    word_timestamps: List[Dict[str, Any]] = []


class GraderFlags(BaseModel):
    forbidden_term_hit: List[str] = []
    asr_low_confidence: bool = False


class GraderData(BaseModel):
    model: str
    prompt_version: str
    verdict: GraderVerdict
    score_raw: float
    score_adj: float
    matched_criteria: List[str] = []
    missing_concepts: List[str] = []
    flags: GraderFlags = Field(default_factory=GraderFlags)
    explanation_for_user: str


class AttemptLog(BaseModel):
    attempt_id: str = Field(default_factory=lambda: str(uuid4()))
    ts: datetime = Field(default_factory=datetime.utcnow)
    item_id: str
    concept_id: str
    asr: Optional[ASRData] = None
    latency_ms: int
    grader: GraderData
    outcome: Outcome
    
    class Config:
        use_enum_values = True