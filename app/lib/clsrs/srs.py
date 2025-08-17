"""
Core SRS math functions for CL-SRS system
Pure functions with no side effects
"""
import math
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum


class Outcome(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAIL = "fail"


@dataclass
class ConceptState:
    """State of a concept for scheduling"""
    concept_id: str
    next_review_at: datetime
    stability_s: float
    last_outcome: Optional[str]
    coverage: Dict[str, float]  # KC -> coverage value
    is_due: bool
    r_pred: float


def r_pred(days_since_last: float, S: float) -> float:
    """
    Calculate predicted retention R(t) = exp(-Δt/S)
    
    Args:
        days_since_last: Days since last review
        S: Stability in days
    
    Returns:
        Predicted retention [0, 1]
    """
    if S <= 0:
        return 0.0
    return math.exp(-days_since_last / S)


def update_S(S: float, outcome: str, r_pred_at_show: float, z_success_max: float = 1.0) -> float:
    """
    Update stability based on outcome and predicted retention
    
    Args:
        S: Current stability in days
        outcome: Review outcome (success/partial/fail)
        r_pred_at_show: Predicted retention at time of review
        z_success_max: Maximum latency z-score for full success credit
    
    Returns:
        Updated stability, clamped to [1, 3650] days
    """
    # Base multipliers from spec
    if outcome == Outcome.SUCCESS:
        # Success: stretch by factor based on R_pred
        if r_pred_at_show >= 0.6:
            multiplier = 3.0
        else:
            # Linear interpolation for R < 0.6
            multiplier = 1.0 + (r_pred_at_show / 0.6) * 2.0
        
        # Apply latency adjustment (simplified for now)
        # In full implementation, would use actual z-score
        latency_factor = 1.0  # Placeholder
        multiplier *= latency_factor
        
    elif outcome == Outcome.PARTIAL:
        # Partial: smaller stretch
        multiplier = 1.5 if r_pred_at_show >= 0.6 else 1.2
        
    else:  # FAIL
        # Failure: significant reduction
        multiplier = 0.5
    
    # Update and clamp
    new_S = S * multiplier
    return max(1.0, min(3650.0, new_S))


def latency_z(ms: int, baseline: List[int], priors: Tuple[float, float] = (math.log(2500), 0.6)) -> float:
    """
    Calculate z-score for response latency using log-normal distribution
    
    Args:
        ms: Response latency in milliseconds
        baseline: List of recent successful response times
        priors: (log_mean, log_std) priors for when baseline is insufficient
    
    Returns:
        Z-score of latency
    """
    if len(baseline) < 5:
        # Use priors
        log_mean, log_std = priors
    else:
        # Calculate from baseline
        log_latencies = [math.log(max(1, lat)) for lat in baseline]
        log_mean = sum(log_latencies) / len(log_latencies)
        
        # Calculate standard deviation
        variance = sum((ll - log_mean) ** 2 for ll in log_latencies) / len(log_latencies)
        log_std = math.sqrt(variance) if variance > 0 else 0.6
    
    # Calculate z-score
    if log_std == 0:
        return 0.0
    
    log_ms = math.log(max(1, ms))
    z = (log_ms - log_mean) / log_std
    
    return z


def kc_coverage(events: List[Dict], tau_days_by_kc: Dict[str, int]) -> Dict[str, float]:
    """
    Calculate decayed KC coverage based on recent events
    
    Args:
        events: List of attempt events with 'kc', 'outcome', 'days_ago' keys
        tau_days_by_kc: Decay time constant for each KC
    
    Returns:
        Dictionary of KC -> coverage value [0, 1]
    """
    coverage = {}
    
    # Group events by KC
    kc_events = {}
    for event in events:
        kc = event['kc']
        if kc not in kc_events:
            kc_events[kc] = []
        kc_events[kc].append(event)
    
    # Calculate coverage for each KC
    for kc, kc_event_list in kc_events.items():
        tau = tau_days_by_kc.get(kc, 14)  # Default tau = 14 days
        
        # Weight by outcome and decay
        weighted_sum = 0.0
        for event in kc_event_list:
            days_ago = event.get('days_ago', 0)
            decay = math.exp(-days_ago / tau)
            
            # Outcome weights
            outcome = event.get('outcome', 'fail')
            if outcome == 'success':
                weight = 1.0
            elif outcome == 'partial':
                weight = 0.5
            else:
                weight = 0.0
            
            weighted_sum += weight * decay
        
        # Normalize to [0, 1]
        coverage[kc] = min(1.0, weighted_sum)
    
    return coverage


def schedule_concepts(concepts_state: List[ConceptState], now: datetime) -> List[str]:
    """
    Select concepts for review based on scheduling rules
    
    Args:
        concepts_state: List of concept states with scheduling info
        now: Current datetime
    
    Returns:
        Ordered list of concept IDs to review
    """
    scheduled = []
    
    # First priority: Due concepts (past their next_review_at)
    due_concepts = [c for c in concepts_state if c.is_due]
    
    # Sort due concepts by how overdue they are
    due_concepts.sort(key=lambda c: c.next_review_at)
    
    for concept in due_concepts:
        # Check coverage gating
        required_coverage = {
            'discrimination': 1.0,
            'application': 1.0
        }
        
        coverage_met = all(
            concept.coverage.get(kc, 0) >= threshold
            for kc, threshold in required_coverage.items()
        )
        
        if coverage_met or len(scheduled) == 0:  # Always schedule at least one
            scheduled.append(concept.concept_id)
    
    # Second priority: Concepts near target retention (R ≈ 0.7)
    if not scheduled:
        # Find concepts closest to R = 0.7
        targetable = [c for c in concepts_state if not c.is_due]
        targetable.sort(key=lambda c: abs(c.r_pred - 0.7))
        
        if targetable and abs(targetable[0].r_pred - 0.7) < 0.1:
            scheduled.append(targetable[0].concept_id)
    
    return scheduled


def next_item_interval(S: float, outcome: str) -> float:
    """
    Calculate next review interval for an item based on outcome
    
    Args:
        S: Item stability in days
        outcome: Review outcome (success/partial/fail)
    
    Returns:
        Next interval in days
    """
    # Target retention values by outcome
    if outcome == Outcome.SUCCESS:
        R_target = 0.9  # High retention target for success
    elif outcome == Outcome.PARTIAL:
        R_target = 0.8  # Medium retention target
    else:  # FAIL
        R_target = 0.95  # Very high retention (short interval)
    
    # interval = -S * ln(R_target)
    if R_target <= 0 or R_target >= 1:
        return 1.0  # Minimum 1 day
    
    interval = -S * math.log(R_target)
    
    # Clamp to reasonable bounds
    return max(1.0, min(365.0, interval))


def calculate_concept_stability(item_stabilities: List[float]) -> float:
    """
    Calculate concept-level stability from item stabilities
    
    Args:
        item_stabilities: List of item stability values
    
    Returns:
        Median stability for the concept
    """
    if not item_stabilities:
        return 2.5  # Default initial stability
    
    # Use median as aggregate
    sorted_stabilities = sorted(item_stabilities)
    n = len(sorted_stabilities)
    
    if n % 2 == 0:
        return (sorted_stabilities[n//2 - 1] + sorted_stabilities[n//2]) / 2
    else:
        return sorted_stabilities[n//2]


def initial_stability_by_kc(kc: str) -> float:
    """
    Get initial stability (S0) for a KC
    
    Args:
        kc: Knowledge component type
    
    Returns:
        Initial stability in days
    """
    s0_map = {
        'definition': 2.5,
        'procedure': 2.5,
        'discrimination': 2.0,
        'application': 2.0,
        'boundary_case': 1.8,
        'contrast': 1.8
    }
    return s0_map.get(kc, 2.0)