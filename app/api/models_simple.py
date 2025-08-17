"""
Simplified data models for CL-SRS system using dataclasses
Compatible with Python 3.13
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from uuid import uuid4
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


@dataclass
class AnswerSpec:
    mode: str = "text"
    accept: Dict[str, Any] = field(default_factory=dict)
    policy: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ItemCue:
    text: str = ""
    features: List[str] = field(default_factory=list)


@dataclass
class Item:
    id: str = field(default_factory=lambda: str(uuid4()))
    concept_id: str = ""
    kc: str = "definition"
    type: str = "anchor"
    prompt: str = ""
    answer: str = ""
    answer_spec: Optional[AnswerSpec] = None
    forbidden_terms: List[str] = field(default_factory=list)
    cue: Optional[ItemCue] = None
    foils: List[str] = field(default_factory=list)
    learner_state: Optional[Dict[str, Any]] = None
    
    def dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "concept_id": self.concept_id,
            "kc": self.kc,
            "type": self.type,
            "prompt": self.prompt,
            "answer": self.answer,
            "answer_spec": self.answer_spec.__dict__ if self.answer_spec else None,
            "forbidden_terms": self.forbidden_terms,
            "cue": self.cue.__dict__ if self.cue else None,
            "foils": self.foils,
            "learner_state": self.learner_state
        }


@dataclass
class Concept:
    id: str = field(default_factory=lambda: str(uuid4()))
    title: str = ""
    description: str = ""
    prereqs: List[str] = field(default_factory=list)
    relations: List[Dict[str, str]] = field(default_factory=list)
    kcs: List[str] = field(default_factory=list)
    anchors: List[str] = field(default_factory=list)
    item_ids: List[str] = field(default_factory=list)
    policy: Dict[str, Any] = field(default_factory=dict)
    scheduler_state: Optional[Dict[str, Any]] = None
    
    def dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "prereqs": self.prereqs,
            "relations": self.relations,
            "kcs": self.kcs,
            "anchors": self.anchors,
            "item_ids": self.item_ids,
            "policy": self.policy,
            "scheduler_state": self.scheduler_state
        }


@dataclass
class ASRData:
    transcript: str = ""
    confidence: float = 0.0
    alts: List[str] = field(default_factory=list)
    speech_ms: int = 0
    word_timestamps: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class GraderData:
    model: str = ""
    prompt_version: str = ""
    verdict: str = "fail"
    score_raw: float = 0.0
    score_adj: float = 0.0
    matched_criteria: List[str] = field(default_factory=list)
    missing_concepts: List[str] = field(default_factory=list)
    flags: Dict[str, Any] = field(default_factory=dict)
    explanation_for_user: str = ""


@dataclass
class AttemptLog:
    attempt_id: str = field(default_factory=lambda: str(uuid4()))
    ts: datetime = field(default_factory=datetime.utcnow)
    item_id: str = ""
    concept_id: str = ""
    asr: Optional[ASRData] = None
    latency_ms: int = 0
    grader: Optional[GraderData] = None
    outcome: str = "fail"


@dataclass
class VariantTemplate:
    id: str = field(default_factory=lambda: str(uuid4()))
    concept_id: str = ""
    kc: str = ""
    deep_operation: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    prompt_template: str = ""
    answer_template: str = ""