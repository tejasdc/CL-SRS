"""
Grading service for evaluating learner responses
Implements ASR → normalize → deterministic → LLM → post-process pipeline
"""
import re
import json
import math
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime, timedelta
from pathlib import Path
import openai
import os
from dotenv import load_dotenv

from app.api.models_simple import Item, AttemptLog, ASRData, GraderData, Outcome, GraderVerdict
from app.api.storage import storage
from app.lib.clsrs.srs import update_S, latency_z, next_item_interval, r_pred

load_dotenv()


class GradingService:
    """Service for grading learner attempts"""
    
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment")
        
        openai.api_key = self.api_key
        model_name = os.getenv("GRADING_MODEL", "gpt-3.5-turbo")
        # Map invalid model names to valid ones
        if model_name == "gpt-5":
            model_name = "gpt-4o"  # Latest GPT-4 model
        self.model = model_name
        self.prompt_version = os.getenv("GRADING_PROMPT_VERSION", "grade_v1")
        
        # Load prompt template
        prompt_path = Path(__file__).parent.parent.parent.parent / "llm" / "grading" / f"{self.prompt_version}.prompt"
        with open(prompt_path, "r") as f:
            self.system_prompt = f.read()
    
    async def grade_attempt(
        self,
        item: Item,
        audio_or_text: Optional[str] = None,
        asr_data: Optional[ASRData] = None,
        latency_ms: int = 0
    ) -> Dict[str, Any]:
        """
        Grade an attempt through the full pipeline
        
        Args:
            item: The item being attempted
            audio_or_text: Text response (if audio, should be transcribed already)
            asr_data: ASR metadata if available
            latency_ms: Response latency in milliseconds
        
        Returns:
            Grading result with outcome, score, and feedback
        """
        # Step 1: Ensure we have text (ASR would happen before this)
        if not audio_or_text:
            return {
                "outcome": Outcome.FAIL,
                "score_adj": 0,
                "explanation_for_user": "No response received",
                "next_review_eta": datetime.utcnow() + timedelta(hours=1)
            }
        
        # Step 2: Normalize the transcript
        normalized = self._normalize_transcript(audio_or_text)
        
        # Step 3: Deterministic checks (take precedence)
        verdict, score_raw = await self._deterministic_accept(item, normalized, asr_data)
        
        # Step 4: LLM grading if needed
        grader_output = None
        need_feedback = verdict is None or self._should_provide_feedback(item, verdict)
        
        if need_feedback:
            grader_output = await self._call_llm_grader(item, normalized, asr_data)
            
            # If deterministic didn't match, use LLM verdict
            if verdict is None and grader_output:
                verdict = grader_output.get("verdict", GraderVerdict.INVALID_INPUT)
                score_raw = grader_output.get("score_0_100", 0)
        
        # Step 5: Post-processing
        score_adj, outcome = await self._postprocess(
            verdict, score_raw, latency_ms, item, asr_data, grader_output
        )
        
        # Step 6: Update SRS state
        next_review_eta = await self._update_srs(item, outcome, latency_ms)
        
        # Step 7: Log attempt
        attempt_log = await self._log_attempt(
            item, asr_data, grader_output, score_adj, outcome, latency_ms
        )
        
        # Return result
        explanation = ""
        if grader_output and "explanation_for_user" in grader_output:
            explanation = grader_output["explanation_for_user"]
        elif outcome == Outcome.SUCCESS:
            explanation = "Correct!"
        elif outcome == Outcome.PARTIAL:
            explanation = "Partially correct. Review the full answer."
        else:
            explanation = f"The answer is: {item.answer}"
        
        result = {
            "outcome": outcome.value if hasattr(outcome, 'value') else outcome,
            "score_adj": score_adj,
            "explanation_for_user": explanation,
            "next_review_eta": next_review_eta.isoformat() if isinstance(next_review_eta, datetime) else next_review_eta
        }
        print(f"[GRADING] Returning result: {result}")
        return result
    
    def _normalize_transcript(self, text: str) -> str:
        """
        Normalize transcript for comparison
        - Lowercase
        - Trim whitespace
        - Collapse multiple spaces
        - Remove common fillers
        - Normalize numbers and units
        """
        # Lowercase and trim
        text = text.lower().strip()
        
        # Remove common fillers
        fillers = ["um", "uh", "er", "ah", "like", "you know", "i mean", "well", "so"]
        for filler in fillers:
            text = re.sub(r'\b' + filler + r'\b', '', text)
        
        # Collapse whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Normalize numbers (basic)
        # "twenty five" -> "25", "one hundred" -> "100"
        number_map = {
            "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
            "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
            "ten": "10", "eleven": "11", "twelve": "12", "thirteen": "13",
            "fourteen": "14", "fifteen": "15", "sixteen": "16", "seventeen": "17",
            "eighteen": "18", "nineteen": "19", "twenty": "20", "thirty": "30",
            "forty": "40", "fifty": "50", "sixty": "60", "seventy": "70",
            "eighty": "80", "ninety": "90", "hundred": "100", "thousand": "1000"
        }
        
        for word, num in number_map.items():
            text = re.sub(r'\b' + word + r'\b', num, text)
        
        return text.strip()
    
    async def _deterministic_accept(
        self, 
        item: Item, 
        normalized: str,
        asr_data: Optional[ASRData]
    ) -> Tuple[Optional[str], Optional[float]]:
        """
        Apply deterministic acceptance rules
        
        Returns:
            Tuple of (verdict, score) or (None, None) if no deterministic match
        """
        if not item.answer_spec or not item.answer_spec.accept:
            return None, None
        
        accept = item.answer_spec.accept
        
        # Check regex acceptance
        if accept.regex:
            for pattern in accept.regex:
                try:
                    if re.match(pattern, normalized):
                        return GraderVerdict.SUCCESS, 100
                except re.error:
                    continue
        
        # Check alias acceptance
        if accept.aliases:
            for alias in accept.aliases:
                if normalized == alias.lower():
                    return GraderVerdict.SUCCESS, 100
        
        # Check numeric acceptance
        if accept.numeric:
            numeric_result = self._check_numeric(normalized, accept.numeric)
            if numeric_result:
                return numeric_result
        
        # Check forbidden terms
        if item.answer_spec.policy and item.answer_spec.policy.forbidden_terms:
            for term in item.answer_spec.policy.forbidden_terms:
                if term.lower() in normalized:
                    # Forbidden term hit - reduce score but don't fail immediately
                    return None, None  # Let LLM grade with penalty
        
        return None, None
    
    def _check_numeric(self, text: str, numeric_spec: Dict[str, Any]) -> Optional[Tuple[str, float]]:
        """Check numeric answer against tolerance"""
        # Extract number from text
        number_pattern = r'[-+]?\d*\.?\d+'
        matches = re.findall(number_pattern, text)
        
        if not matches:
            return None
        
        try:
            value = float(matches[0])
            target = numeric_spec.get("target", 0)
            
            # Check absolute tolerance
            if "tol_abs" in numeric_spec:
                tol = numeric_spec["tol_abs"]
                if abs(value - target) <= tol:
                    return GraderVerdict.SUCCESS, 100
                elif abs(value - target) <= 2 * tol:
                    return GraderVerdict.PARTIAL, 70
            
            # Check relative tolerance
            if "tol_rel" in numeric_spec:
                tol = numeric_spec["tol_rel"]
                if target != 0:
                    rel_error = abs((value - target) / target)
                    if rel_error <= tol:
                        return GraderVerdict.SUCCESS, 100
                    elif rel_error <= 2 * tol:
                        return GraderVerdict.PARTIAL, 70
            
            # Check units if required
            if numeric_spec.get("units_required") and numeric_spec.get("units"):
                if numeric_spec["units"].lower() not in text.lower():
                    return GraderVerdict.PARTIAL, 50  # Missing units
            
        except (ValueError, TypeError):
            pass
        
        return None
    
    async def _call_llm_grader(
        self,
        item: Item,
        normalized: str,
        asr_data: Optional[ASRData]
    ) -> Optional[Dict[str, Any]]:
        """Call LLM for semantic grading"""
        try:
            # Prepare item card for grader
            item_card = {
                "prompt": item.prompt,
                "canonical_answer": item.answer,
                "answer_spec": item.answer_spec.dict() if item.answer_spec else {},
                "forbidden_terms": item.forbidden_terms
            }
            
            # Prepare ASR metadata
            asr_meta = {}
            if asr_data:
                asr_meta = {
                    "confidence": asr_data.confidence,
                    "alternatives": asr_data.alts[:3] if asr_data.alts else []
                }
            
            user_prompt = f"""
            Grade the following response:
            
            ITEM: {json.dumps(item_card)}
            NORMALIZED_TRANSCRIPT: {normalized}
            ASR_META: {json.dumps(asr_meta)}
            
            Return ONLY valid JSON matching the output schema.
            """
            
            client = openai.OpenAI(
                api_key=self.api_key,
                timeout=30.0  # 30 second timeout
            )
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=1,
                max_completion_tokens=500
            )
            
            result = response.choices[0].message.content
            
            # Parse JSON
            try:
                grader_output = json.loads(result)
                return grader_output
            except json.JSONDecodeError:
                # One retry
                retry_prompt = "The output was not valid JSON. Please return ONLY valid JSON:\n" + user_prompt
                response = client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": retry_prompt}
                    ],
                    temperature=1,
                    max_completion_tokens=500
                )
                
                result = response.choices[0].message.content
                grader_output = json.loads(result)
                return grader_output
                
        except Exception as e:
            # Return invalid_input on failure
            return {
                "verdict": GraderVerdict.INVALID_INPUT,
                "score_0_100": 0,
                "confidence_0_1": 0,
                "matched_criteria": [],
                "missing_concepts": [],
                "flags": {"asr_low_confidence": asr_data and asr_data.confidence < 0.5},
                "explanation_for_user": "Could not process response"
            }
    
    async def _postprocess(
        self,
        verdict: str,
        score_raw: float,
        latency_ms: int,
        item: Item,
        asr_data: Optional[ASRData],
        grader_output: Optional[Dict[str, Any]]
    ) -> Tuple[int, str]:
        """
        Apply post-processing: latency penalties, forbidden terms, score mapping
        
        Returns:
            Tuple of (adjusted_score, outcome)
        """
        score_adj = score_raw
        
        # Apply latency penalty
        baseline = await storage.get_latency_baseline(item.id)
        if baseline and latency_ms > 0:
            z = latency_z(latency_ms, baseline)
            
            # Apply penalty for slow responses
            z_success_max = 2.0
            z_partial_max = 3.5
            
            if item.answer_spec and item.answer_spec.policy:
                z_success_max = item.answer_spec.policy.z_success_max
                z_partial_max = item.answer_spec.policy.z_partial_max
            
            if z > z_partial_max:
                score_adj *= 0.5  # Heavy penalty
            elif z > z_success_max:
                score_adj *= 0.75  # Moderate penalty
        
        # Apply forbidden term penalty
        if grader_output and grader_output.get("flags", {}).get("forbidden_term_hit"):
            score_adj *= 0.5
        
        # Apply ASR confidence penalty
        if asr_data and asr_data.confidence < 0.5:
            score_adj *= 0.8
        
        # Clamp score
        score_adj = max(0, min(100, int(score_adj)))
        
        # Map to outcome bands
        if score_adj >= 80:
            outcome = Outcome.SUCCESS
        elif score_adj >= 50:
            outcome = Outcome.PARTIAL
        else:
            outcome = Outcome.FAIL
        
        # Override with verdict if deterministic
        if verdict == GraderVerdict.SUCCESS:
            outcome = Outcome.SUCCESS
        elif verdict == GraderVerdict.INVALID_INPUT:
            outcome = Outcome.FAIL
        
        return score_adj, outcome
    
    async def _update_srs(self, item: Item, outcome: str, latency_ms: int) -> datetime:
        """Update SRS state and return next review time"""
        if not item.learner_state:
            return datetime.utcnow() + timedelta(days=1)
        
        # Handle dict format for learner_state
        if isinstance(item.learner_state, dict):
            last_review = item.learner_state.get('last_review_at')
            if last_review:
                if isinstance(last_review, str):
                    last_review = datetime.fromisoformat(last_review.replace('Z', '+00:00'))
                delta = datetime.utcnow() - last_review
                days_since = delta.total_seconds() / 86400
            else:
                days_since = 0
            
            current_S = item.learner_state.get('stability_s', 2.5)
        else:
            # Handle object format for backward compatibility
            if item.learner_state.last_review_at:
                delta = datetime.utcnow() - item.learner_state.last_review_at
                days_since = delta.total_seconds() / 86400
            else:
                days_since = 0
            
            current_S = item.learner_state.stability_s
        
        # Calculate R_pred at time of show
        r_at_show = r_pred(days_since, current_S)
        
        # Get latency z-score for adjustment
        baseline = await storage.get_latency_baseline(item.id)
        z = latency_z(latency_ms, baseline) if baseline else 0
        z_max = 2.0  # Default
        
        # Update stability
        new_S = update_S(current_S, outcome, r_at_show, z_max)
        
        # Calculate next interval
        interval_days = next_item_interval(new_S, outcome)
        next_review = datetime.utcnow() + timedelta(days=interval_days)
        
        # Update storage
        await storage.update_item_after_attempt(item.id, outcome, next_review, new_S)
        
        return next_review
    
    async def _log_attempt(
        self,
        item: Item,
        asr_data: Optional[ASRData],
        grader_output: Optional[Dict[str, Any]],
        score_adj: int,
        outcome: str,
        latency_ms: int
    ) -> AttemptLog:
        """Log the attempt with all metadata"""
        grader_data = GraderData(
            model=self.model,
            prompt_version=self.prompt_version,
            verdict=grader_output.get("verdict", GraderVerdict.SUCCESS) if grader_output else GraderVerdict.SUCCESS,
            score_raw=grader_output.get("score_0_100", 100) if grader_output else 100,
            score_adj=score_adj,
            matched_criteria=grader_output.get("matched_criteria", []) if grader_output else [],
            missing_concepts=grader_output.get("missing_concepts", []) if grader_output else [],
            flags={
                "forbidden_term_hit": grader_output.get("flags", {}).get("forbidden_term_hit", []) if grader_output else [],
                "asr_low_confidence": asr_data and asr_data.confidence < 0.5
            },
            explanation_for_user=grader_output.get("explanation_for_user", "") if grader_output else ""
        )
        
        attempt = AttemptLog(
            item_id=item.id,
            concept_id=item.concept_id,
            asr=asr_data,
            latency_ms=latency_ms,
            grader=grader_data,
            outcome=outcome
        )
        
        await storage.save_attempt(attempt)
        return attempt
    
    def _should_provide_feedback(self, item: Item, verdict: str) -> bool:
        """Determine if we should provide LLM feedback even with deterministic match"""
        # Always provide feedback for failures
        if verdict != GraderVerdict.SUCCESS:
            return True
        
        # Optionally provide feedback for success (can be configured)
        return False