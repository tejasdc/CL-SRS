"""
Storage layer for CL-SRS data
Using persistent file-based storage that survives server restarts
"""
from typing import Dict, List, Optional
from datetime import datetime
import json
import os
from pathlib import Path
from app.api.models_simple import Concept, Item, VariantTemplate, AttemptLog
from app.lib.clsrs.srs import initial_stability_by_kc


class Storage:
    """Persistent file-based storage"""
    
    def __init__(self, data_dir: str = None):
        if data_dir is None:
            # Use absolute path relative to this file
            import os
            current_dir = os.path.dirname(os.path.abspath(__file__))
            data_dir = os.path.join(current_dir, "data")
        
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # File paths
        self.concepts_file = self.data_dir / "concepts.json"
        self.items_file = self.data_dir / "items.json"
        self.templates_file = self.data_dir / "templates.json"
        self.attempts_file = self.data_dir / "attempts.json"
        self.latency_file = self.data_dir / "latency.json"
        
        print(f"[STORAGE] Initializing storage with data directory: {self.data_dir.absolute()}")
        
        # Load existing data
        self.concepts: Dict[str, Concept] = self._load_concepts()
        self.items: Dict[str, Item] = self._load_items()
        self.templates: Dict[str, VariantTemplate] = {}  # TODO: implement later
        self.attempts: List[AttemptLog] = self._load_attempts()
        self.latency_baseline: Dict[str, List[int]] = self._load_latency()
        
        print(f"[STORAGE] Loaded {len(self.concepts)} concepts, {len(self.items)} items from disk")
    
    def _load_concepts(self) -> Dict[str, Concept]:
        """Load concepts from file"""
        if not self.concepts_file.exists():
            return {}
        try:
            with open(self.concepts_file, 'r') as f:
                data = json.load(f)
                return {cid: Concept(**cdata) for cid, cdata in data.items()}
        except Exception as e:
            print(f"Error loading concepts: {e}")
            return {}
    
    def _save_concepts(self):
        """Save concepts to file"""
        try:
            # Convert dataclass to dict using the dict() method we defined
            data = {}
            for cid, concept in self.concepts.items():
                data[cid] = concept.dict() if hasattr(concept, 'dict') else concept.__dict__
            with open(self.concepts_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            print(f"Successfully saved {len(data)} concepts to {self.concepts_file}")
        except Exception as e:
            print(f"Error saving concepts: {e}")
            import traceback
            traceback.print_exc()
    
    def _load_items(self) -> Dict[str, Item]:
        """Load items from file"""
        if not self.items_file.exists():
            return {}
        try:
            with open(self.items_file, 'r') as f:
                data = json.load(f)
                return {iid: Item(**idata) for iid, idata in data.items()}
        except Exception as e:
            print(f"Error loading items: {e}")
            return {}
    
    def _save_items(self):
        """Save items to file"""
        try:
            # Convert dataclass to dict using the dict() method we defined
            data = {}
            for iid, item in self.items.items():
                data[iid] = item.dict() if hasattr(item, 'dict') else item.__dict__
            with open(self.items_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            print(f"Successfully saved {len(data)} items to {self.items_file}")
        except Exception as e:
            print(f"Error saving items: {e}")
            import traceback
            traceback.print_exc()
    
    def _load_latency(self) -> Dict[str, List[int]]:
        """Load latency data from file"""
        if not self.latency_file.exists():
            return {}
        try:
            with open(self.latency_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading latency: {e}")
            return {}
    
    def _save_latency(self):
        """Save latency data to file"""
        try:
            with open(self.latency_file, 'w') as f:
                json.dump(self.latency_baseline, f, indent=2)
        except Exception as e:
            print(f"Error saving latency: {e}")
    
    def _load_attempts(self) -> List[AttemptLog]:
        """Load attempts from file"""
        if not self.attempts_file.exists():
            return []
        try:
            with open(self.attempts_file, 'r') as f:
                data = json.load(f)
                return [AttemptLog(**attempt_data) for attempt_data in data]
        except Exception as e:
            print(f"Error loading attempts: {e}")
            return []
    
    def _save_attempts(self):
        """Save attempts to file"""
        try:
            # Convert AttemptLog objects to dictionaries
            data = []
            for attempt in self.attempts:
                attempt_dict = {
                    'attempt_id': attempt.attempt_id,
                    'ts': attempt.ts.isoformat() if isinstance(attempt.ts, datetime) else attempt.ts,
                    'item_id': attempt.item_id,
                    'concept_id': attempt.concept_id,
                    'asr': attempt.asr.__dict__ if attempt.asr and hasattr(attempt.asr, '__dict__') else attempt.asr,
                    'latency_ms': attempt.latency_ms,
                    'grader': attempt.grader.__dict__ if attempt.grader and hasattr(attempt.grader, '__dict__') else attempt.grader,
                    'outcome': attempt.outcome
                }
                data.append(attempt_dict)
            
            with open(self.attempts_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            print(f"Error saving attempts: {e}")
    
    async def save_concept(self, concept: Concept) -> Concept:
        """Save a concept with initial scheduling state"""
        if not concept.scheduler_state:
            # Initialize scheduler state for new concept
            concept.scheduler_state = {
                "next_review_at": datetime.utcnow(),  # Schedule immediately
                "last_outcome": None,
                "stability_s": 2.5,  # Default initial stability
                "last_session_at": None,
                "interval_days": 1.0
            }
        
        self.concepts[concept.id] = concept
        self._save_concepts()  # Persist to file
        return concept
    
    async def get_concept(self, concept_id: str) -> Optional[Concept]:
        """Get concept by ID"""
        return self.concepts.get(concept_id)
    
    async def get_all_concepts(self) -> List[Concept]:
        """Get all concepts"""
        return list(self.concepts.values())
    
    async def save_item(self, item: Item) -> Item:
        """Save an item with initial learner state"""
        print(f"DEBUG: Saving item {item.id} to storage")
        if not item.learner_state:
            # Initialize learner state based on KC
            initial_s = initial_stability_by_kc(item.kc.value if hasattr(item.kc, 'value') else item.kc)
            item.learner_state = {
                "next_review_at": datetime.utcnow().isoformat(),
                "last_review_at": None,
                "stability_s": initial_s,
                "attempts": 0,
                "streak": 0
            }
        
        self.items[item.id] = item
        self._save_items()  # Persist to file
        print(f"DEBUG: Item {item.id} saved. Total items: {len(self.items)}")
        
        # Update concept's item list
        if item.concept_id in self.concepts:
            concept = self.concepts[item.concept_id]
            if item.id not in concept.item_ids:
                concept.item_ids.append(item.id)
            if item.type == "anchor" and item.id not in concept.anchors:
                concept.anchors.append(item.id)
            self._save_concepts()  # Persist concept changes too
        
        return item
    
    async def get_item(self, item_id: str) -> Optional[Item]:
        """Get item by ID"""
        item = self.items.get(item_id)
        # print(f"DEBUG: get_item({item_id}) -> {'Found' if item else 'Not found'} (total items: {len(self.items)})")
        return item
    
    async def get_items_by_concept(self, concept_id: str) -> List[Item]:
        """Get all items for a concept"""
        return [item for item in self.items.values() if item.concept_id == concept_id]
    
    async def save_template(self, template: VariantTemplate) -> VariantTemplate:
        """Save a variant template"""
        self.templates[template.id] = template
        return template
    
    async def get_template(self, template_id: str) -> Optional[VariantTemplate]:
        """Get template by ID"""
        return self.templates.get(template_id)
    
    async def save_attempt(self, attempt: AttemptLog) -> AttemptLog:
        """Save an attempt log and update latency baseline"""
        self.attempts.append(attempt)
        self._save_attempts()  # Persist attempts
        
        # Update latency baseline for successful attempts
        if attempt.outcome == "success" and attempt.latency_ms > 0:
            if attempt.item_id not in self.latency_baseline:
                self.latency_baseline[attempt.item_id] = []
            
            baseline = self.latency_baseline[attempt.item_id]
            baseline.append(attempt.latency_ms)
            
            # Keep only last 20 successful latencies
            if len(baseline) > 20:
                self.latency_baseline[attempt.item_id] = baseline[-20:]
            
            self._save_latency()  # Persist latency changes
        
        return attempt
    
    async def get_attempts_by_item(self, item_id: str) -> List[AttemptLog]:
        """Get all attempts for an item"""
        return [a for a in self.attempts if a.item_id == item_id]
    
    async def get_attempts_by_concept(self, concept_id: str) -> List[AttemptLog]:
        """Get all attempts for a concept"""
        return [a for a in self.attempts if a.concept_id == concept_id]
    
    async def get_latency_baseline(self, item_id: str) -> List[int]:
        """Get latency baseline for an item"""
        return self.latency_baseline.get(item_id, [])
    
    async def get_due_items(self, now: Optional[datetime] = None) -> List[Item]:
        """Get items due for review"""
        if now is None:
            now = datetime.utcnow()
        
        due_items = []
        for item in self.items.values():
            if item.learner_state and isinstance(item.learner_state, dict):
                next_review = item.learner_state.get('next_review_at')
                if next_review and isinstance(next_review, str):
                    try:
                        next_review_dt = datetime.fromisoformat(next_review.replace('Z', '+00:00'))
                        if next_review_dt <= now:
                            due_items.append(item)
                    except ValueError:
                        # Skip items with invalid datetime format
                        continue
            elif item.learner_state and hasattr(item.learner_state, 'next_review_at'):
                # Handle object format for backward compatibility
                if item.learner_state.next_review_at <= now:
                    due_items.append(item)
        return due_items
    
    async def update_item_after_attempt(self, item_id: str, outcome: str, next_review_at: datetime, new_stability: float):
        """Update item state after an attempt"""
        item = self.items.get(item_id)
        if item:
            if item.learner_state is None:
                item.learner_state = {}
            
            if isinstance(item.learner_state, dict):
                item.learner_state.update({
                    'last_review_at': datetime.utcnow().isoformat(),
                    'next_review_at': next_review_at.isoformat(),
                    'stability_s': new_stability,
                    'attempts': item.learner_state.get('attempts', 0) + 1,
                    'last_outcome': outcome
                })
                
                if outcome == "success":
                    item.learner_state['streak'] = item.learner_state.get('streak', 0) + 1
                else:
                    item.learner_state['streak'] = 0
            else:
                # Handle object format for backward compatibility
                item.learner_state.last_review_at = datetime.utcnow()
                item.learner_state.next_review_at = next_review_at
                item.learner_state.stability_s = new_stability
                item.learner_state.attempts += 1
                
                if outcome == "success":
                    item.learner_state.streak += 1
                else:
                    item.learner_state.streak = 0
            
            self._save_items()  # Persist item changes
    
    async def update_concept_after_session(self, concept_id: str, outcome: str, next_review_at: datetime, new_stability: float):
        """Update concept state after a session"""
        concept = self.concepts.get(concept_id)
        if concept and concept.scheduler_state:
            concept.scheduler_state["last_session_at"] = datetime.utcnow()
            concept.scheduler_state["next_review_at"] = next_review_at
            concept.scheduler_state["last_outcome"] = outcome
            concept.scheduler_state["stability_s"] = new_stability
            
            # Calculate interval
            delta = next_review_at - datetime.utcnow()
            concept.scheduler_state["interval_days"] = delta.total_seconds() / 86400
            
            self._save_concepts()  # Persist concept changes


# Global storage instance
storage = Storage()