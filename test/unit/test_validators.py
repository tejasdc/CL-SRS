"""
Unit tests for schema validators
"""
import pytest
from datetime import datetime
from app.api.models import (
    KnowledgeComponent, ItemType, Outcome, GraderVerdict, AnswerMode
)
from app.api.validators import (
    SchemaValidator, CueUniquenessValidator, 
    VariantSafetyValidator, AuthoringValidator
)


class TestSchemaValidator:
    """Test schema validation with strict field checking"""
    
    def test_validate_concept_success(self):
        """Test valid concept passes validation"""
        concept_data = {
            "id": "concept-1",
            "title": "Test Concept",
            "description": "A test concept",
            "kcs": ["definition", "discrimination", "application"],
            "anchors": ["item-1"],
            "item_ids": ["item-1", "item-2"]
        }
        
        concept = SchemaValidator.validate_concept(concept_data)
        assert concept.id == "concept-1"
        assert concept.title == "Test Concept"
        assert len(concept.anchors) == 1
    
    def test_validate_concept_unknown_fields(self):
        """Test concept with unknown fields is rejected"""
        concept_data = {
            "id": "concept-1",
            "title": "Test Concept",
            "description": "A test concept",
            "unknown_field": "should fail",
            "anchors": ["item-1"]
        }
        
        with pytest.raises(ValueError, match="Unknown fields"):
            SchemaValidator.validate_concept(concept_data)
    
    def test_validate_concept_no_anchors(self):
        """Test concept without anchors is rejected"""
        concept_data = {
            "id": "concept-1",
            "title": "Test Concept",
            "description": "A test concept",
            "anchors": []
        }
        
        with pytest.raises(ValueError, match="at least 1 anchor"):
            SchemaValidator.validate_concept(concept_data)
    
    def test_validate_item_success(self):
        """Test valid item passes validation"""
        item_data = {
            "id": "item-1",
            "concept_id": "concept-1",
            "kc": "definition",
            "type": "anchor",
            "prompt": "What is X?",
            "answer": "X is Y",
            "answer_spec": {
                "mode": "text",
                "accept": {
                    "regex": ["^X is Y$"]
                },
                "policy": {
                    "strictness": "strict"
                }
            },
            "cue": {
                "text": "What is X",
                "features": ["definition", "direct"]
            }
        }
        
        item = SchemaValidator.validate_item(item_data)
        assert item.id == "item-1"
        assert item.kc == KnowledgeComponent.DEFINITION
        assert item.type == ItemType.ANCHOR
    
    def test_validate_variant_without_params(self):
        """Test variant item without generator_params is rejected"""
        item_data = {
            "id": "item-1",
            "concept_id": "concept-1",
            "kc": "application",
            "type": "variant",
            "prompt": "Calculate X",
            "answer": "42",
            "answer_spec": {
                "mode": "numeric",
                "accept": {
                    "numeric": {
                        "target": 42,
                        "tol_abs": 0.1
                    }
                },
                "policy": {}
            },
            "cue": {
                "text": "Calculate",
                "features": []
            },
            "variant_template_id": "template-1"
        }
        
        with pytest.raises(ValueError, match="must have generator_params"):
            SchemaValidator.validate_item(item_data)


class TestCueUniquenessValidator:
    """Test cue uniqueness validation"""
    
    def test_unique_cues_accepted(self):
        """Test unique cues are accepted"""
        validator = CueUniquenessValidator()
        
        assert validator.register_cue("concept-1", "What is X?")
        assert validator.register_cue("concept-1", "How does Y work?")
        assert validator.register_cue("concept-1", "Calculate Z")
    
    def test_duplicate_cue_rejected(self):
        """Test exact duplicate cues are rejected"""
        validator = CueUniquenessValidator()
        
        assert validator.register_cue("concept-1", "What is X?")
        assert not validator.register_cue("concept-1", "What is X?")
    
    def test_similar_cue_rejected(self):
        """Test similar cues are rejected"""
        validator = CueUniquenessValidator()
        
        assert validator.register_cue("concept-1", "What is the definition of X?")
        assert not validator.register_cue("concept-1", "What is the definition of X")
        assert not validator.register_cue("concept-1", "what is the definition of x?")
    
    def test_different_concepts_independent(self):
        """Test cues in different concepts are independent"""
        validator = CueUniquenessValidator()
        
        assert validator.register_cue("concept-1", "What is X?")
        assert validator.register_cue("concept-2", "What is X?")


class TestVariantSafetyValidator:
    """Test variant generation safety checks"""
    
    def test_param_hash_generation(self):
        """Test consistent parameter hashing"""
        params1 = {"a": 1, "b": 2}
        params2 = {"b": 2, "a": 1}  # Different order, same content
        params3 = {"a": 1, "b": 3}  # Different content
        
        hash1 = VariantSafetyValidator.validate_param_hash(params1)
        hash2 = VariantSafetyValidator.validate_param_hash(params2)
        hash3 = VariantSafetyValidator.validate_param_hash(params3)
        
        assert hash1 == hash2  # Same content, different order
        assert hash1 != hash3  # Different content
        assert hash1.startswith("sha256:")
    
    def test_difficulty_window_check(self):
        """Test difficulty window validation"""
        assert VariantSafetyValidator.check_difficulty_window(0.7)
        assert VariantSafetyValidator.check_difficulty_window(0.5)
        assert VariantSafetyValidator.check_difficulty_window(0.9)
        assert not VariantSafetyValidator.check_difficulty_window(0.4)
        assert not VariantSafetyValidator.check_difficulty_window(0.95)


class TestAuthoringValidator:
    """Test complete authoring output validation"""
    
    def test_valid_authoring_output(self):
        """Test valid authoring output passes all checks"""
        output = {
            "concepts": [{
                "id": "concept-1",
                "title": "Test Concept",
                "description": "Description",
                "kcs": ["definition", "discrimination", "application"],
                "anchors": ["item-1"],
                "item_ids": ["item-1", "item-2"]
            }],
            "items": [
                {
                    "id": "item-1",
                    "concept_id": "concept-1",
                    "kc": "definition",
                    "type": "anchor",
                    "prompt": "What is X?",
                    "answer": "X is Y",
                    "answer_spec": {
                        "mode": "text",
                        "accept": {"regex": ["^X is Y$"]},
                        "policy": {}
                    },
                    "cue": {"text": "What is X", "features": []}
                },
                {
                    "id": "item-2",
                    "concept_id": "concept-1",
                    "kc": "discrimination",
                    "type": "anchor",
                    "prompt": "Is this X or Y?",
                    "answer": "X",
                    "answer_spec": {
                        "mode": "text",
                        "accept": {"aliases": ["X", "It's X"]},
                        "policy": {}
                    },
                    "cue": {"text": "X or Y choice", "features": []}
                }
            ]
        }
        
        assert AuthoringValidator.validate_authoring_output(output)
    
    def test_missing_required_keys(self):
        """Test authoring output missing required keys fails"""
        output = {
            "concepts": []
            # Missing "items" key
        }
        
        with pytest.raises(ValueError, match="missing required keys"):
            AuthoringValidator.validate_authoring_output(output)
    
    def test_no_anchor_items(self):
        """Test concept without anchor items fails"""
        output = {
            "concepts": [{
                "id": "concept-1",
                "title": "Test",
                "description": "Test",
                "kcs": ["definition"],
                "anchors": ["item-1"],
                "item_ids": []
            }],
            "items": []  # No items at all
        }
        
        with pytest.raises(ValueError, match="no anchor items"):
            AuthoringValidator.validate_authoring_output(output)