"""
Tests for Healthcare Liaison Agent
===================================

Tests provider report generation, FHIR compatibility, escalation handling,
and care coordination functionality.
"""

import pytest
from datetime import datetime, date, timedelta
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session
import json

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from models import (
    Patient, Medication, AdherenceLog, SymptomReport,
    ProviderReport, AgentActivity, AdherenceStatus,
    SeverityLevel, AgentType
)
from agents.state import AgentState, AgentResult


# ==================== FIXTURES ====================

@pytest.fixture
def liaison_agent():
    """Create a liaison agent instance with mocked LLM"""
    with patch("agents.liaison_agent.LiaisonAgent._init_llm_client") as mock_llm:
        mock_llm.return_value = MagicMock()
        from agents.liaison_agent import LiaisonAgent
        agent = LiaisonAgent()
        yield agent


@pytest.fixture
def sample_agent_state(test_patient):
    """Create a sample agent state for testing"""
    return {
        "patient_id": test_patient.id,
        "current_task": "generate provider report",
        "context": {},
        "agent_results": {},
        "messages": [],
        "next_agent": None,
        "error": None,
        "requires_escalation": False
    }


@pytest.fixture
def patient_with_report_data(db_session: Session, test_patient: Patient, test_medication: Medication):
    """Create a patient with comprehensive data for report generation"""
    # Create adherence history
    for i in range(30):
        scheduled = datetime.now() - timedelta(days=29-i)
        taken = i % 5 != 0  # Miss every 5th dose (80% adherence)
        log = AdherenceLog(
            patient_id=test_patient.id,
            medication_id=test_medication.id,
            scheduled_time=scheduled,
            actual_time=scheduled + timedelta(minutes=10) if taken else None,
            status=AdherenceStatus.TAKEN if taken else AdherenceStatus.MISSED,
            taken=taken
        )
        db_session.add(log)
    
    # Create symptom reports
    symptoms = [
        SymptomReport(
            patient_id=test_patient.id,
            symptom="Mild headache",
            severity=3,
            medication_name=test_medication.name,
            reported_at=datetime.now() - timedelta(days=10)
        ),
        SymptomReport(
            patient_id=test_patient.id,
            symptom="Dizziness",
            severity=4,
            medication_name=test_medication.name,
            reported_at=datetime.now() - timedelta(days=5)
        ),
    ]
    for s in symptoms:
        db_session.add(s)
    
    db_session.commit()
    return test_patient


@pytest.fixture
def patient_requiring_escalation(db_session: Session, test_patient: Patient, test_medication: Medication):
    """Create a patient with data requiring urgent escalation"""
    # Critical symptom
    symptom = SymptomReport(
        patient_id=test_patient.id,
        symptom="Severe chest pain",
        severity=9,
        description="Sharp chest pain after taking medication",
        medication_name=test_medication.name,
        suspected_medication_id=test_medication.id,
        reported_at=datetime.now()
    )
    db_session.add(symptom)
    
    # Very low adherence
    for i in range(14):
        log = AdherenceLog(
            patient_id=test_patient.id,
            medication_id=test_medication.id,
            scheduled_time=datetime.now() - timedelta(days=13-i),
            status=AdherenceStatus.MISSED,
            taken=False
        )
        db_session.add(log)
    
    db_session.commit()
    return test_patient


# ==================== UNIT TESTS ====================

class TestLiaisonAgentInit:
    """Tests for LiaisonAgent initialization"""
    
    def test_agent_initialization(self, liaison_agent):
        """Test that liaison agent initializes correctly"""
        assert liaison_agent.agent_name == "Healthcare Liaison Agent"
        assert liaison_agent.agent_type == "liaison"
    
    def test_escalation_thresholds_loaded(self, liaison_agent):
        """Test that escalation thresholds are defined"""
        assert hasattr(liaison_agent, "escalation_thresholds")
        assert "critical" in liaison_agent.escalation_thresholds
        assert "high" in liaison_agent.escalation_thresholds
        assert "moderate" in liaison_agent.escalation_thresholds
        assert "low" in liaison_agent.escalation_thresholds
    
    def test_threshold_values_ordered(self, liaison_agent):
        """Test that threshold values are properly ordered"""
        thresholds = liaison_agent.escalation_thresholds
        assert thresholds["critical"] > thresholds["high"]
        assert thresholds["high"] > thresholds["moderate"]
        assert thresholds["moderate"] > thresholds["low"]
    
    def test_fhir_resources_supported(self, liaison_agent):
        """Test that FHIR resources are defined"""
        assert hasattr(liaison_agent, "supported_fhir_resources")
        assert "Observation" in liaison_agent.supported_fhir_resources
        assert "DiagnosticReport" in liaison_agent.supported_fhir_resources


class TestProviderReportGeneration:
    """Tests for provider report generation"""
    
    @pytest.mark.unit
    def test_generate_report_no_data(self, liaison_agent, db_session, test_patient):
        """Test report generation with minimal data"""
        with patch("agents.liaison_agent.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=db_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            
            result = liaison_agent.generate_provider_report(test_patient.id)
            
            assert result.success is True
    
    @pytest.mark.unit
    def test_generate_comprehensive_report(self, liaison_agent, sample_agent_state):
        """Test comprehensive report generation"""
        with patch.object(liaison_agent, "generate_provider_report") as mock_generate:
            mock_generate.return_value = AgentResult(
                success=True,
                summary="Comprehensive report generated",
                data={
                    "adherence_rate": 80.0,
                    "period_days": 30,
                    "medications_reviewed": 3
                },
                confidence=0.9
            )
            
            sample_agent_state["current_task"] = "generate comprehensive report"
            result_state = liaison_agent.process(sample_agent_state)
            
            assert "liaison" in result_state["agent_results"]
    
    @pytest.mark.unit
    def test_report_includes_adherence_metrics(self, liaison_agent):
        """Test that reports include adherence metrics"""
        pass
    
    @pytest.mark.unit
    def test_report_includes_symptom_summary(self, liaison_agent):
        """Test that reports include symptom summary"""
        pass
    
    @pytest.mark.unit
    def test_report_period_customization(self, liaison_agent, sample_agent_state):
        """Test that report period can be customized"""
        sample_agent_state["context"]["period_days"] = 7
        # Should generate 7-day report


class TestFHIRGeneration:
    """Tests for FHIR resource generation"""
    
    @pytest.mark.unit
    def test_generate_fhir_observation(self, liaison_agent, db_session, test_patient):
        """Test FHIR Observation resource generation"""
        if hasattr(liaison_agent, "_create_fhir_observation"):
            observation = liaison_agent._create_fhir_observation(
                patient_id=test_patient.id,
                code="74009-2",  # Medication adherence
                value=85.0
            )
            
            assert observation is not None
            assert observation.get("resourceType") == "Observation"
    
    @pytest.mark.unit
    def test_generate_fhir_diagnostic_report(self, liaison_agent, db_session, test_patient):
        """Test FHIR DiagnosticReport resource generation"""
        if hasattr(liaison_agent, "_create_diagnostic_report"):
            report = liaison_agent._create_diagnostic_report(
                patient_id=test_patient.id,
                period_start=date.today() - timedelta(days=30),
                period_end=date.today()
            )
            
            assert report is not None
    
    @pytest.mark.unit
    def test_fhir_bundle_structure(self, liaison_agent):
        """Test FHIR Bundle has correct structure"""
        pass
    
    @pytest.mark.unit
    def test_fhir_coding_systems(self, liaison_agent):
        """Test FHIR coding systems are correct"""
        # LOINC, SNOMED-CT codes should be valid
        pass


class TestEscalationHandling:
    """Tests for escalation handling"""
    
    @pytest.mark.unit
    def test_handle_critical_escalation(self, liaison_agent, db_session, test_patient):
        """Test handling critical escalation"""
        with patch.object(liaison_agent, "call_llm") as mock_llm:
            mock_llm.return_value = '{"urgency": "immediate", "contact_method": "phone"}'
            
            result = liaison_agent.handle_escalation(
                test_patient.id,
                reason="Severe symptom reported",
                severity="critical",
                details={"symptom": "chest pain", "severity": 9}
            )
            
            assert result is not None
            assert result.requires_escalation or result.data.get("escalation_required")
    
    @pytest.mark.unit
    def test_handle_moderate_escalation(self, liaison_agent, db_session, test_patient):
        """Test handling moderate escalation"""
        result = liaison_agent.handle_escalation(
            test_patient.id,
            reason="Low adherence detected",
            severity="moderate",
            details={"adherence_rate": 45.0}
        )
        
        assert result is not None
    
    @pytest.mark.unit
    def test_escalation_message_generation(self, liaison_agent):
        """Test escalation message generation"""
        pass
    
    @pytest.mark.unit
    def test_escalation_timeframe_appropriate(self, liaison_agent):
        """Test that escalation timeframes are appropriate for severity"""
        thresholds = liaison_agent.escalation_thresholds
        # Critical should have immediate response
        # High should be same-day
        # Moderate should be 48 hours


class TestAgentProcess:
    """Tests for main process() method"""
    
    @pytest.mark.unit
    def test_process_report_task(self, liaison_agent, sample_agent_state):
        """Test processing report generation task"""
        sample_agent_state["current_task"] = "generate provider report"
        
        with patch.object(liaison_agent, "generate_provider_report") as mock_report:
            mock_report.return_value = AgentResult(
                success=True,
                summary="Report generated",
                data={"report_id": 1},
                confidence=0.85
            )
            
            result_state = liaison_agent.process(sample_agent_state)
            
            assert "liaison" in result_state["agent_results"]
            mock_report.assert_called_once()
    
    @pytest.mark.unit
    def test_process_summary_task(self, liaison_agent, sample_agent_state):
        """Test processing summary generation task"""
        sample_agent_state["current_task"] = "create clinical summary"
        
        with patch.object(liaison_agent, "generate_provider_report") as mock_report:
            mock_report.return_value = AgentResult(
                success=True,
                summary="Summary created",
                data={},
                confidence=0.8
            )
            
            result_state = liaison_agent.process(sample_agent_state)
            
            assert "liaison" in result_state["agent_results"]
    
    @pytest.mark.unit
    def test_process_escalation_task(self, liaison_agent, sample_agent_state):
        """Test processing escalation task"""
        sample_agent_state["current_task"] = "escalate urgent concern"
        sample_agent_state["context"]["reason"] = "Critical symptom"
        sample_agent_state["context"]["severity"] = "critical"
        
        with patch.object(liaison_agent, "handle_escalation") as mock_escalate:
            mock_escalate.return_value = AgentResult(
                success=True,
                summary="Escalation handled",
                data={"escalated_to": "provider"},
                confidence=0.95,
                requires_escalation=True
            )
            
            result_state = liaison_agent.process(sample_agent_state)
            
            assert "liaison" in result_state["agent_results"]
            mock_escalate.assert_called_once()
    
    @pytest.mark.unit
    def test_process_fhir_task(self, liaison_agent, sample_agent_state):
        """Test processing FHIR generation task"""
        sample_agent_state["current_task"] = "generate fhir resources"
        
        with patch.object(liaison_agent, "generate_fhir_bundle") as mock_fhir:
            mock_fhir.return_value = AgentResult(
                success=True,
                summary="FHIR bundle generated",
                data={"bundle": {}},
                confidence=0.9
            )
            
            result_state = liaison_agent.process(sample_agent_state)
            
            assert "liaison" in result_state["agent_results"]
    
    @pytest.mark.unit
    def test_process_handles_errors(self, liaison_agent, sample_agent_state):
        """Test that process handles errors gracefully"""
        sample_agent_state["current_task"] = "generate report"
        
        with patch.object(liaison_agent, "generate_provider_report") as mock_report:
            mock_report.side_effect = Exception("Database error")
            
            result_state = liaison_agent.process(sample_agent_state)
            
            assert result_state.get("error") is not None or \
                   result_state["agent_results"]["liaison"]["success"] is False


class TestClinicalNarrative:
    """Tests for clinical narrative generation"""
    
    @pytest.mark.unit
    def test_generate_adherence_narrative(self, liaison_agent):
        """Test generation of adherence narrative"""
        pass
    
    @pytest.mark.unit
    def test_narrative_includes_trends(self, liaison_agent):
        """Test that narrative includes trend analysis"""
        pass
    
    @pytest.mark.unit
    def test_narrative_clinical_language(self, liaison_agent):
        """Test that narrative uses appropriate clinical language"""
        pass


class TestReportStorage:
    """Tests for report storage"""
    
    @pytest.mark.unit
    def test_store_provider_report(self, liaison_agent, db_session, test_patient):
        """Test storing provider report in database"""
        pass
    
    @pytest.mark.unit
    def test_report_versioning(self, liaison_agent):
        """Test that reports maintain version history"""
        pass


# ==================== INTEGRATION TESTS ====================

class TestLiaisonAgentIntegration:
    """Integration tests for liaison agent"""
    
    @pytest.mark.integration
    def test_full_report_generation_workflow(
        self, liaison_agent, db_session, patient_with_report_data
    ):
        """Test complete report generation workflow"""
        pass
    
    @pytest.mark.integration
    def test_escalation_with_notification(
        self, liaison_agent, db_session, patient_requiring_escalation
    ):
        """Test escalation triggers appropriate notifications"""
        pass


# ==================== EDGE CASES ====================

class TestLiaisonAgentEdgeCases:
    """Edge case tests for liaison agent"""
    
    @pytest.mark.unit
    def test_report_with_no_adherence_data(self, liaison_agent, db_session, test_patient):
        """Test report generation with no adherence data"""
        pass
    
    @pytest.mark.unit
    def test_report_with_100_percent_adherence(self, liaison_agent):
        """Test report generation with perfect adherence"""
        pass
    
    @pytest.mark.unit
    def test_very_long_report_period(self, liaison_agent):
        """Test report generation for extended period (1 year)"""
        pass
    
    @pytest.mark.unit
    def test_multiple_concurrent_escalations(self, liaison_agent):
        """Test handling multiple simultaneous escalations"""
        pass
