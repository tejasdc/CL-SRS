"""
Validators for ensuring data integrity and schema compliance
"""
import hashlib
import json
from typing import Any, Dict, List, Optional
from app.api.models_v1 import (
    Concept, Item, VariantTemplate, AttemptLog,
    KnowledgeComponent, ItemType
)


class SchemaValidator:
    """Strict schema validation with no unknown fields allowed"""
    
    @staticmethod
    def validate_concept(data: Dict[str, Any]) -> Concept:
        """Validate and create Concept, rejecting unknown fields"""
        allowed_fields = set(Concept.__fields__.keys())
        provided_fields = set(data.keys())
        unknown_fields = provided_fields - allowed_fields
        
        if unknown_fields:
            raise ValueError(f"Unknown fields in Concept: {unknown_fields}")
        
        concept = Concept(**data)
        
        # Validate required KCs are present
        required_kcs = concept.policy.coverage_model.required_kcs
        if not all(kc in concept.kcs for kc in required_kcs):
            raise ValueError(f"Concept missing required KCs: {required_kcs}")
        
        # Validate at least one anchor exists
        if len(concept.anchors) < 1:
            raise ValueError("Concept must have at least 1 anchor item")
        
        return concept
    
    @staticmethod
    def validate_item(data: Dict[str, Any]) -> Item:
        """Validate and create Item, enforcing all constraints"""
        allowed_fields = set(Item.__fields__.keys())
        provided_fields = set(data.keys())
        unknown_fields = provided_fields - allowed_fields
        
        if unknown_fields:
            raise ValueError(f"Unknown fields in Item: {unknown_fields}")
        
        item = Item(**data)
        
        # Validate variant items have template and params
        if item.type == ItemType.VARIANT:
            if not item.variant_template_id:
                raise ValueError("Variant items must have variant_template_id")
            if not item.generator_params:
                raise ValueError("Variant items must have generator_params")
        
        # Validate answer_spec is present and complete
        if not item.answer_spec:
            raise ValueError("Item must have answer_spec")
        
        return item
    
    @staticmethod
    def validate_variant_template(data: Dict[str, Any]) -> VariantTemplate:
        """Validate variant template with safety checks"""
        allowed_fields = set(VariantTemplate.__fields__.keys())
        provided_fields = set(data.keys())
        unknown_fields = provided_fields - allowed_fields
        
        if unknown_fields:
            raise ValueError(f"Unknown fields in VariantTemplate: {unknown_fields}")
        
        template = VariantTemplate(**data)
        
        # Validate deep_operation is not empty
        if not template.deep_operation:
            raise ValueError("VariantTemplate must have deep_operation defined")
        
        return template
    
    @staticmethod
    def validate_attempt_log(data: Dict[str, Any]) -> AttemptLog:
        """Validate attempt log with required grader data"""
        allowed_fields = set(AttemptLog.__fields__.keys())
        provided_fields = set(data.keys())
        unknown_fields = provided_fields - allowed_fields
        
        if unknown_fields:
            raise ValueError(f"Unknown fields in AttemptLog: {unknown_fields}")
        
        attempt = AttemptLog(**data)
        
        # Validate ASR confidence if present
        if attempt.asr and attempt.asr.confidence < 0.5:
            attempt.grader.flags.asr_low_confidence = True
        
        return attempt


class CueUniquenessValidator:
    """Ensure cue uniqueness within concepts"""
    
    def __init__(self):
        self.cue_registry: Dict[str, List[str]] = {}  # concept_id -> list of cue texts
    
    def register_cue(self, concept_id: str, cue_text: str) -> bool:
        """Register a cue and check for uniqueness"""
        if concept_id not in self.cue_registry:
            self.cue_registry[concept_id] = []
        
        # Check for exact duplicates
        if cue_text in self.cue_registry[concept_id]:
            return False
        
        # Check for near-duplicates (simplified check)
        for existing_cue in self.cue_registry[concept_id]:
            if self._are_cues_too_similar(cue_text, existing_cue):
                return False
        
        self.cue_registry[concept_id].append(cue_text)
        return True
    
    def _are_cues_too_similar(self, cue1: str, cue2: str) -> bool:
        """Check if two cues are too similar (simplified Levenshtein-like check)"""
        # Normalize for comparison
        cue1_norm = cue1.lower().strip()
        cue2_norm = cue2.lower().strip()
        
        # Exact match after normalization
        if cue1_norm == cue2_norm:
            return True
        
        # Very simple similarity check (can be enhanced)
        words1 = set(cue1_norm.split())
        words2 = set(cue2_norm.split())
        
        if len(words1) == 0 or len(words2) == 0:
            return False
        
        # Jaccard similarity
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        jaccard = len(intersection) / len(union) if union else 0
        
        # If more than 60% similar, consider too similar
        return jaccard > 0.6


class VariantSafetyValidator:
    """Validate variant generation safety"""
    
    @staticmethod
    def validate_param_hash(params: Dict[str, Any]) -> str:
        """Generate canonical parameter hash"""
        # Sort params for consistent hashing
        canonical = json.dumps(params, sort_keys=True)
        return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"
    
    @staticmethod
    def check_deep_operation_preserved(
        template: VariantTemplate,
        generated_item: Item
    ) -> bool:
        """Ensure variant preserves deep operation"""
        # This would involve semantic checking in production
        # For now, basic validation
        return generated_item.kc == template.kc
    
    @staticmethod
    def check_difficulty_window(
        predicted_difficulty: float,
        target: float = 0.70,
        window: tuple = (0.5, 0.9)
    ) -> bool:
        """Check if difficulty is within acceptable window"""
        return window[0] <= predicted_difficulty <= window[1]


class AuthoringValidator:
    """Validate authoring output"""
    
    @staticmethod
    def validate_authoring_output(data: Dict[str, Any]) -> bool:
        """Validate complete authoring JSON output"""
        required_keys = {"concepts", "items"}
        
        if not all(key in data for key in required_keys):
            raise ValueError(f"Authoring output missing required keys: {required_keys}")
        
        # Validate each concept
        concepts = []
        for concept_data in data["concepts"]:
            concept = SchemaValidator.validate_concept(concept_data)
            concepts.append(concept)
        
        # Validate each item
        items = []
        cue_validator = CueUniquenessValidator()
        
        for item_data in data["items"]:
            item = SchemaValidator.validate_item(item_data)
            
            # Check cue uniqueness
            if not cue_validator.register_cue(item.concept_id, item.cue.text):
                raise ValueError(f"Duplicate or similar cue detected: {item.cue.text}")
            
            items.append(item)
        
        # Validate concept-item relationships
        for concept in concepts:
            concept_items = [i for i in items if i.concept_id == concept.id]
            
            # Check anchors exist
            anchor_items = [i for i in concept_items if i.type == ItemType.ANCHOR]
            if len(anchor_items) < 1:
                raise ValueError(f"Concept {concept.id} has no anchor items")
            
            # Check required KCs covered
            item_kcs = set(i.kc for i in concept_items)
            required_kcs = set(concept.policy.coverage_model.required_kcs)
            
            if not required_kcs.issubset(item_kcs):
                missing = required_kcs - item_kcs
                raise ValueError(f"Concept {concept.id} missing required KCs: {missing}")
        
        return True