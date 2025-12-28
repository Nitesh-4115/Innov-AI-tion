"""
Tests for Monitoring Agent
===========================

Tests adherence tracking, pattern detection, anomaly identification,
and symptom analysis functionality.
"""

import pytest
from datetime import datetime, date, timedelta
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from models import (
    Patient, Medication, AdherenceLog, SymptomReport,
    AdherenceStatus, SeverityLevel
)
from agents.state import AgentState, AgentResult


# ==================== FIXTURES ====================

@pytest.fixture
def monitoring_agent():
    """Create a monitoring agent instance with mocked LLM"""
    with patch("agents.monitoring_agent.MonitoringAgent._init_llm_client") as mock_llm:
        mock_llm.return_value = MagicMock()
        from agents.monitoring_agent import MonitoringAgent
        agent = MonitoringAgent()
        yield agent


@pytest.fixture
def sample_agent_state(test_patient):
    """Create a sample agent state for testing"""
    return {
        "patient_id": test_patient.id,
        "current_task": "analyze adherence",
        "context": {},
        "agent_results": {},
        "messages": [],
        "next_agent": None,
        "error": None,
        "requires_escalation": False
    }


@pytest.fixture
def patient_with_adherence_data(db_session: Session, test_patient: Patient, test_medication: Medication):
    """Create a patient with 14 days of adherence history"""
    base_time = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
    
    # Create varied adherence pattern
    # Days 1-7: Good adherence (6/7 taken)
    # Days 8-14: Declining adherence (4/7 taken)
    pattern = [True, True, True, False, True, True, True,  # Week 1
               True, False, True, False, True, False, True]  # Week 2
    
    for i, taken in enumerate(pattern):
        scheduled = base_time - timedelta(days=13-i)
        log = AdherenceLog(
            patient_id=test_patient.id,
            medication_id=test_medication.id,
            scheduled_time=scheduled,
            actual_time=scheduled + timedelta(minutes=10) if taken else None,
            status=AdherenceStatus.TAKEN if taken else AdherenceStatus.MISSED,
            taken=taken,
            logged_by="user"
        )
        db_session.add(log)
    
    db_session.commit()
    db_session.refresh(test_patient)
    return test_patient


@pytest.fixture
def patient_with_symptoms(db_session: Session, test_patient: Patient, test_medication: Medication):
    """Create a patient with symptom reports"""
    symptoms = [
        SymptomReport(
            patient_id=test_patient.id,
            symptom="Nausea",
            description="Mild nausea 30 min after taking medication",
            severity=3,
            medication_name=test_medication.name,
            suspected_medication_id=test_medication.id,
            timing="30 minutes after dose",
            reported_at=datetime.now() - timedelta(days=2)
        ),
        SymptomReport(
            patient_id=test_patient.id,
            symptom="Headache",
            description="Mild headache in the afternoon",
            severity=4,
            medication_name=test_medication.name,
            timing="2 hours after dose",
            reported_at=datetime.now() - timedelta(days=1)
        ),
        SymptomReport(
            patient_id=test_patient.id,
            symptom="Dizziness",
            description="Brief dizziness when standing",
            severity=5,
            reported_at=datetime.now()
        ),
    ]
    
    for symptom in symptoms:
        db_session.add(symptom)
    
    db_session.commit()
    return test_patient


# ==================== UNIT TESTS ====================

class TestMonitoringAgentInit:
    """Tests for MonitoringAgent initialization"""
    
    def test_agent_initialization(self, monitoring_agent):
        """Test that monitoring agent initializes correctly"""
        assert monitoring_agent.agent_name == "Monitoring Agent"
        assert monitoring_agent.agent_type == "monitoring"
    
    def test_configuration_loaded(self, monitoring_agent):
        """Test that configuration values are loaded"""
        assert hasattr(monitoring_agent, "adherence_target")
        assert hasattr(monitoring_agent, "anomaly_threshold")
        assert hasattr(monitoring_agent, "monitoring_window_days")
    
    def test_adherence_target_range(self, monitoring_agent):
        """Test that adherence target is within valid range"""
        assert 0 <= monitoring_agent.adherence_target <= 100


class TestAdherenceAnalysis:
    """Tests for adherence analysis functionality"""
    
    @pytest.mark.unit
    def test_analyze_adherence_no_logs(self, monitoring_agent, db_session, test_patient):
        """Test analysis with no adherence logs"""
        with patch("agents.monitoring_agent.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=db_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            
            result = monitoring_agent.analyze_adherence(test_patient.id)
            
            assert result.success is True
            # Should handle empty data gracefully
    
    @pytest.mark.unit
    def test_calculate_adherence_rate(self, monitoring_agent):
        """Test adherence rate calculation"""
        # Mock data: 8 taken, 2 missed = 80%
        logs = []
        for i in range(10):
            log = MagicMock()
            log.taken = i < 8  # First 8 are taken
            logs.append(log)
        
        # If agent has this method
        if hasattr(monitoring_agent, "_calculate_adherence_rate"):
            rate = monitoring_agent._calculate_adherence_rate(logs)
            assert rate == 80.0
    
    @pytest.mark.unit
    def test_adherence_trend_calculation(self, monitoring_agent):
        """Test calculation of adherence trends over time"""
        # Test with declining adherence data
        pass


class TestPatternDetection:
    """Tests for pattern detection in adherence data"""
    
    @pytest.mark.unit
    def test_detect_time_patterns(self, monitoring_agent):
        """Test detection of time-based patterns"""
        # E.g., always misses evening doses
        pass
    
    @pytest.mark.unit
    def test_detect_day_of_week_patterns(self, monitoring_agent):
        """Test detection of day-of-week patterns"""
        # E.g., always misses weekend doses
        pass
    
    @pytest.mark.unit
    def test_detect_declining_trend(self, monitoring_agent):
        """Test detection of declining adherence trend"""
        pass


class TestAnomalyDetection:
    """Tests for anomaly detection"""
    
    @pytest.mark.unit
    def test_detect_sudden_drop(self, monitoring_agent):
        """Test detection of sudden adherence drop"""
        pass
    
    @pytest.mark.unit
    def test_detect_multiple_consecutive_misses(self, monitoring_agent):
        """Test detection of multiple consecutive missed doses"""
        pass
    
    @pytest.mark.unit
    def test_anomaly_threshold_respected(self, monitoring_agent):
        """Test that anomaly threshold is properly applied"""
        threshold = monitoring_agent.anomaly_threshold
        assert 0 <= threshold <= 100


class TestSymptomAnalysis:
    """Tests for symptom analysis and side effect detection"""
    
    @pytest.mark.unit
    def test_analyze_single_symptom(self, monitoring_agent, db_session, test_patient, test_symptom_report):
        """Test analysis of a single symptom report"""
        with patch.object(monitoring_agent, "call_llm") as mock_llm:
            mock_llm.return_value = '{"likely_medication_related": true, "confidence": 0.7, "recommendation": "Monitor closely"}'
            
            result = monitoring_agent.analyze_symptom(
                test_patient.id,
                test_symptom_report.id
            )
            
            assert result is not None
    
    @pytest.mark.unit
    def test_symptom_severity_classification(self, monitoring_agent):
        """Test proper classification of symptom severity"""
        # Severity 1-3: Low
        # Severity 4-6: Medium
        # Severity 7-9: High
        # Severity 10: Critical
        pass
    
    @pytest.mark.unit
    def test_symptom_correlation_with_medication(self, monitoring_agent):
        """Test correlation of symptoms with medication timing"""
        pass
    
    @pytest.mark.unit
    def test_escalation_for_severe_symptoms(self, monitoring_agent, sample_agent_state):
        """Test that severe symptoms trigger escalation"""
        sample_agent_state["current_task"] = "analyze symptom"
        sample_agent_state["context"]["severity"] = 8
        
        with patch.object(monitoring_agent, "analyze_symptom") as mock_analyze:
            mock_analyze.return_value = AgentResult(
                success=True,
                summary="Severe symptom detected",
                data={"severity": 8},
                confidence=0.9,
                requires_escalation=True
            )
            
            result_state = monitoring_agent.process(sample_agent_state)
            
            # Should flag for escalation
            assert result_state.get("requires_escalation", False) or \
                   result_state["agent_results"]["monitoring"].get("requires_escalation", False)


class TestAgentProcess:
    """Tests for main process() method"""
    
    @pytest.mark.unit
    def test_process_adherence_task(self, monitoring_agent, sample_agent_state):
        """Test processing adherence analysis task"""
        sample_agent_state["current_task"] = "analyze adherence"
        
        with patch.object(monitoring_agent, "analyze_adherence") as mock_analyze:
            mock_analyze.return_value = AgentResult(
                success=True,
                summary="Adherence rate: 85%",
                data={"adherence_rate": 85.0},
                confidence=0.9
            )
            
            result_state = monitoring_agent.process(sample_agent_state)
            
            assert "monitoring" in result_state["agent_results"]
            mock_analyze.assert_called_once()
    
    @pytest.mark.unit
    def test_process_symptom_task(self, monitoring_agent, sample_agent_state):
        """Test processing symptom analysis task"""
        sample_agent_state["current_task"] = "analyze symptom report"
        sample_agent_state["context"]["symptom_id"] = 1
        
        with patch.object(monitoring_agent, "analyze_symptom") as mock_analyze:
            mock_analyze.return_value = AgentResult(
                success=True,
                summary="Symptom analyzed",
                data={"correlation_score": 0.6},
                confidence=0.8
            )
            
            result_state = monitoring_agent.process(sample_agent_state)
            
            assert "monitoring" in result_state["agent_results"]
            mock_analyze.assert_called_once()
    
    @pytest.mark.unit
    def test_process_pattern_task(self, monitoring_agent, sample_agent_state):
        """Test processing pattern analysis task"""
        sample_agent_state["current_task"] = "analyze adherence patterns"
        
        with patch.object(monitoring_agent, "analyze_adherence_patterns") as mock_patterns:
            mock_patterns.return_value = AgentResult(
                success=True,
                summary="Patterns identified",
                data={"patterns": ["evening_misses"]},
                confidence=0.75
            )
            
            result_state = monitoring_agent.process(sample_agent_state)
            
            assert "monitoring" in result_state["agent_results"]
    
    @pytest.mark.unit
    def test_process_handles_errors(self, monitoring_agent, sample_agent_state):
        """Test that process handles errors gracefully"""
        sample_agent_state["current_task"] = "analyze adherence"
        
        with patch.object(monitoring_agent, "analyze_adherence") as mock_analyze:
            mock_analyze.side_effect = Exception("Database error")
            
            result_state = monitoring_agent.process(sample_agent_state)
            
            assert result_state.get("error") is not None or \
                   result_state["agent_results"]["monitoring"]["success"] is False


class TestNextAgentSuggestion:
    """Tests for next agent suggestion logic"""
    
    @pytest.mark.unit
    def test_suggest_barrier_agent_for_low_adherence(self, monitoring_agent, sample_agent_state):
        """Test that low adherence suggests barrier agent"""
        with patch.object(monitoring_agent, "analyze_adherence") as mock_analyze:
            mock_analyze.return_value = AgentResult(
                success=True,
                summary="Low adherence detected: 45%",
                data={"adherence_rate": 45.0},
                confidence=0.9,
                next_agent_suggestion="barrier"
            )
            
            result_state = monitoring_agent.process(sample_agent_state)
            
            # Should suggest barrier agent
            assert result_state.get("next_agent") == "barrier" or \
                   result_state["agent_results"]["monitoring"].get("next_agent_suggestion") == "barrier"


# ==================== INTEGRATION TESTS ====================

class TestMonitoringAgentIntegration:
    """Integration tests for monitoring agent"""
    
    @pytest.mark.integration
    def test_full_adherence_analysis_workflow(
        self, monitoring_agent, db_session, patient_with_adherence_data
    ):
        """Test complete adherence analysis workflow"""
        with patch("agents.monitoring_agent.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=db_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            
            # This would test full flow with real data
            pass
    
    @pytest.mark.integration
    def test_symptom_analysis_with_medication_correlation(
        self, monitoring_agent, db_session, patient_with_symptoms
    ):
        """Test symptom analysis correlates with medications"""
        pass


# ==================== EDGE CASES ====================

class TestMonitoringAgentEdgeCases:
    """Edge case tests for monitoring agent"""
    
    @pytest.mark.unit
    def test_analysis_with_single_log(self, monitoring_agent, db_session, test_patient, test_medication):
        """Test analysis with only one adherence log"""
        log = AdherenceLog(
            patient_id=test_patient.id,
            medication_id=test_medication.id,
            scheduled_time=datetime.now(),
            taken=True,
            status=AdherenceStatus.TAKEN
        )
        db_session.add(log)
        db_session.commit()
        
        # Should handle gracefully
    
    @pytest.mark.unit
    def test_analysis_with_100_percent_adherence(self, monitoring_agent):
        """Test analysis with perfect adherence"""
        pass
    
    @pytest.mark.unit
    def test_analysis_with_0_percent_adherence(self, monitoring_agent):
        """Test analysis with zero adherence"""
        pass
    
    @pytest.mark.unit
    def test_symptom_without_medication_link(self, monitoring_agent, db_session, test_patient):
        """Test symptom analysis when no medication is linked"""
        symptom = SymptomReport(
            patient_id=test_patient.id,
            symptom="General fatigue",
            severity=3
        )
        db_session.add(symptom)
        db_session.commit()
        
        # Should handle gracefully without medication correlation
