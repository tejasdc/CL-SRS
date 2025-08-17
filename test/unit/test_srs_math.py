"""
Unit tests for CL-SRS math functions
Tests against spec formulas and examples
"""
import pytest
import math
from datetime import datetime, timedelta
from app.lib.clsrs.srs import (
    r_pred, update_S, latency_z, kc_coverage,
    schedule_concepts, next_item_interval,
    calculate_concept_stability, initial_stability_by_kc,
    ConceptState, Outcome
)


class TestRetentionPrediction:
    """Test R(t) = exp(-Δt/S) formula"""
    
    def test_r_pred_basic(self):
        """Test basic retention prediction"""
        # R(0) = 1 (just reviewed)
        assert r_pred(0, 10) == 1.0
        
        # R(∞) → 0
        assert r_pred(1000, 10) < 0.001
        
        # R(S) = exp(-1) ≈ 0.368
        S = 10
        expected = math.exp(-1)
        assert abs(r_pred(S, S) - expected) < 0.001
    
    def test_r_pred_spec_examples(self):
        """Test against spec examples"""
        # Example: S=5 days, t=3 days
        S = 5
        t = 3
        expected = math.exp(-t/S)
        assert abs(r_pred(t, S) - expected) < 0.001
        
        # Example: S=20 days, t=14 days (one tau period)
        S = 20
        t = 14
        expected = math.exp(-0.7)
        assert abs(r_pred(t, S) - expected) < 0.001
    
    def test_r_pred_edge_cases(self):
        """Test edge cases"""
        # Zero stability
        assert r_pred(1, 0) == 0.0
        
        # Negative time (shouldn't happen but handle gracefully)
        assert r_pred(-1, 10) > 1.0


class TestStabilityUpdate:
    """Test stability update rules"""
    
    def test_update_S_success_high_retention(self):
        """Test S update for success with R >= 0.6"""
        S = 10
        outcome = Outcome.SUCCESS
        r_at_show = 0.7
        
        new_S = update_S(S, outcome, r_at_show)
        
        # Should multiply by ~3.0
        assert new_S > S * 2.5
        assert new_S < S * 3.5
    
    def test_update_S_success_low_retention(self):
        """Test S update for success with R < 0.6"""
        S = 10
        outcome = Outcome.SUCCESS
        r_at_show = 0.3
        
        new_S = update_S(S, outcome, r_at_show)
        
        # Should multiply by 1 + (0.3/0.6)*2 = 2.0
        expected_multiplier = 2.0
        assert abs(new_S - S * expected_multiplier) < 0.5
    
    def test_update_S_partial(self):
        """Test S update for partial success"""
        S = 10
        outcome = Outcome.PARTIAL
        
        # High retention
        new_S = update_S(S, outcome, 0.7)
        assert abs(new_S - S * 1.5) < 0.1
        
        # Low retention
        new_S = update_S(S, outcome, 0.3)
        assert abs(new_S - S * 1.2) < 0.1
    
    def test_update_S_fail(self):
        """Test S update for failure"""
        S = 10
        outcome = Outcome.FAIL
        
        new_S = update_S(S, outcome, 0.7)
        assert abs(new_S - S * 0.5) < 0.1
    
    def test_update_S_clamping(self):
        """Test S is clamped to [1, 3650]"""
        # Test upper bound
        S = 3000
        new_S = update_S(S, Outcome.SUCCESS, 0.8)
        assert new_S == 3650
        
        # Test lower bound
        S = 1.5
        new_S = update_S(S, Outcome.FAIL, 0.2)
        assert new_S == 1.0


class TestLatencyZ:
    """Test latency z-score calculation"""
    
    def test_latency_z_with_baseline(self):
        """Test z-score with sufficient baseline"""
        baseline = [2000, 2500, 3000, 2200, 2800]  # ms
        
        # Average response
        z = latency_z(2500, baseline)
        assert abs(z) < 0.5  # Should be near 0
        
        # Fast response
        z = latency_z(1000, baseline)
        assert z < -1  # Should be negative
        
        # Slow response
        z = latency_z(5000, baseline)
        assert z > 1  # Should be positive
    
    def test_latency_z_with_priors(self):
        """Test z-score with insufficient baseline"""
        baseline = [2000, 2500]  # Only 2 samples
        
        # Should use priors (ln(2500), 0.6)
        z = latency_z(2500, baseline)
        assert abs(z) < 0.5
        
        z = latency_z(5000, baseline)
        assert z > 0
    
    def test_latency_z_edge_cases(self):
        """Test edge cases"""
        # Empty baseline
        z = latency_z(2500, [])
        assert isinstance(z, float)
        
        # Zero latency (shouldn't happen but handle)
        z = latency_z(0, [1000, 2000])
        assert isinstance(z, float)


class TestKCCoverage:
    """Test KC coverage calculation"""
    
    def test_kc_coverage_basic(self):
        """Test basic coverage calculation"""
        events = [
            {'kc': 'definition', 'outcome': 'success', 'days_ago': 0},
            {'kc': 'procedure', 'outcome': 'success', 'days_ago': 7},
            {'kc': 'discrimination', 'outcome': 'partial', 'days_ago': 14},
        ]
        
        tau_days = {
            'definition': 14,
            'procedure': 14,
            'discrimination': 14
        }
        
        coverage = kc_coverage(events, tau_days)
        
        # Recent success should have high coverage
        assert coverage['definition'] == 1.0
        
        # Week-old success should be decayed
        assert 0.5 < coverage['procedure'] < 0.7
        
        # Two-week-old partial should be low
        assert 0.1 < coverage['discrimination'] < 0.3
    
    def test_kc_coverage_outcome_weights(self):
        """Test outcome weighting"""
        events = [
            {'kc': 'test', 'outcome': 'success', 'days_ago': 0},
            {'kc': 'test2', 'outcome': 'partial', 'days_ago': 0},
            {'kc': 'test3', 'outcome': 'fail', 'days_ago': 0},
        ]
        
        tau_days = {'test': 14, 'test2': 14, 'test3': 14}
        coverage = kc_coverage(events, tau_days)
        
        assert coverage['test'] == 1.0  # Success weight = 1.0
        assert coverage['test2'] == 0.5  # Partial weight = 0.5
        assert coverage['test3'] == 0.0  # Fail weight = 0.0


class TestScheduling:
    """Test concept scheduling logic"""
    
    def test_schedule_due_concepts(self):
        """Test scheduling prioritizes due concepts"""
        now = datetime.now()
        
        concepts = [
            ConceptState(
                concept_id="c1",
                next_review_at=now - timedelta(days=1),  # Overdue
                stability_s=10,
                last_outcome="success",
                coverage={'discrimination': 1.0, 'application': 1.0},
                is_due=True,
                r_pred=0.5
            ),
            ConceptState(
                concept_id="c2",
                next_review_at=now + timedelta(days=1),  # Not due
                stability_s=10,
                last_outcome="success",
                coverage={'discrimination': 1.0, 'application': 1.0},
                is_due=False,
                r_pred=0.8
            ),
        ]
        
        scheduled = schedule_concepts(concepts, now)
        assert scheduled == ["c1"]  # Due concept scheduled
    
    def test_schedule_coverage_gating(self):
        """Test coverage requirements gate scheduling"""
        now = datetime.now()
        
        concepts = [
            ConceptState(
                concept_id="c1",
                next_review_at=now - timedelta(days=1),
                stability_s=10,
                last_outcome="success",
                coverage={'discrimination': 0.5, 'application': 0.5},  # Below threshold
                is_due=True,
                r_pred=0.5
            ),
            ConceptState(
                concept_id="c2",
                next_review_at=now - timedelta(hours=1),
                stability_s=10,
                last_outcome="success",
                coverage={'discrimination': 1.0, 'application': 1.0},  # Meets threshold
                is_due=True,
                r_pred=0.6
            ),
        ]
        
        scheduled = schedule_concepts(concepts, now)
        # c2 should be scheduled first (meets coverage)
        assert "c2" in scheduled
    
    def test_schedule_target_retention(self):
        """Test scheduling targets R ≈ 0.7 when nothing due"""
        now = datetime.now()
        
        concepts = [
            ConceptState(
                concept_id="c1",
                next_review_at=now + timedelta(days=1),
                stability_s=10,
                last_outcome="success",
                coverage={'discrimination': 1.0, 'application': 1.0},
                is_due=False,
                r_pred=0.72  # Close to 0.7
            ),
            ConceptState(
                concept_id="c2",
                next_review_at=now + timedelta(days=2),
                stability_s=10,
                last_outcome="success",
                coverage={'discrimination': 1.0, 'application': 1.0},
                is_due=False,
                r_pred=0.9  # Far from 0.7
            ),
        ]
        
        scheduled = schedule_concepts(concepts, now)
        assert scheduled == ["c1"]  # Closest to 0.7


class TestIntervals:
    """Test interval calculation"""
    
    def test_next_item_interval_success(self):
        """Test interval after success"""
        S = 10
        interval = next_item_interval(S, Outcome.SUCCESS)
        
        # interval = -S * ln(0.9)
        expected = -S * math.log(0.9)
        assert abs(interval - expected) < 0.1
    
    def test_next_item_interval_partial(self):
        """Test interval after partial"""
        S = 10
        interval = next_item_interval(S, Outcome.PARTIAL)
        
        # interval = -S * ln(0.8)
        expected = -S * math.log(0.8)
        assert abs(interval - expected) < 0.1
    
    def test_next_item_interval_fail(self):
        """Test interval after failure"""
        S = 10
        interval = next_item_interval(S, Outcome.FAIL)
        
        # interval = -S * ln(0.95) - should be short
        expected = -S * math.log(0.95)
        assert abs(interval - expected) < 0.1
        assert interval < 1  # Should be less than a day for reasonable S
    
    def test_interval_clamping(self):
        """Test intervals are clamped to reasonable bounds"""
        # Very high stability
        interval = next_item_interval(1000, Outcome.SUCCESS)
        assert interval <= 365
        
        # Very low stability
        interval = next_item_interval(0.1, Outcome.FAIL)
        assert interval >= 1.0


class TestConceptStability:
    """Test concept-level stability calculation"""
    
    def test_calculate_concept_stability_median(self):
        """Test median calculation"""
        # Odd number of items
        stabilities = [5, 10, 15]
        assert calculate_concept_stability(stabilities) == 10
        
        # Even number of items
        stabilities = [5, 10, 15, 20]
        assert calculate_concept_stability(stabilities) == 12.5
    
    def test_calculate_concept_stability_empty(self):
        """Test with no items"""
        assert calculate_concept_stability([]) == 2.5  # Default


class TestInitialStability:
    """Test initial stability values"""
    
    def test_initial_stability_values(self):
        """Test S0 values match spec"""
        assert initial_stability_by_kc('definition') == 2.5
        assert initial_stability_by_kc('procedure') == 2.5
        assert initial_stability_by_kc('discrimination') == 2.0
        assert initial_stability_by_kc('application') == 2.0
        assert initial_stability_by_kc('boundary_case') == 1.8
        assert initial_stability_by_kc('contrast') == 1.8
        
        # Unknown KC
        assert initial_stability_by_kc('unknown') == 2.0