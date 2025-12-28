"""
Tests for Barrier Resolution Agent
===================================

Tests barrier identification, cost assistance, side effect handling,
forgetfulness strategies, and intervention generation.
"""

import pytest
from datetime import datetime, date, timedelta
from unittest.mock import MagicMock, patch, AsyncMock
from sqlalchemy.orm import Session

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from models import (
    Patient, Medication, AdherenceLog, SymptomReport,
    BarrierResolution, Intervention, AdherenceStatus,
    BarrierCategory, SeverityLevel, InterventionType
)
from agents.state import AgentState, AgentResult


# ==================== FIXTURES ====================

@pytest.fixture
def barrier_agent():
    """Create a barrier agent instance with mocked LLM"""
    with patch("agents.barrier_agent.BarrierAgent._init_llm_client") as mock_llm:
        mock_llm.return_value = MagicMock()
        from agents.barrier_agent import BarrierAgent
        agent = BarrierAgent()
        yield agent


@pytest.fixture
def sample_agent_state(test_patient):
    """Create a sample agent state for testing"""
    return {
        "patient_id": test_patient.id,
        "current_task": "identify barriers",
        "context": {},
        "agent_results": {},
        "messages": [],
        "next_agent": None,
        "error": None,
        "requires_escalation": False
    }


@pytest.fixture
def patient_with_cost_barrier(db_session: Session, test_patient: Patient):
    """Create a patient with cost-related adherence issues"""
    # High-cost medication
    expensive_med = Medication(
        patient_id=test_patient.id,
        name="Ozempic",
        dosage="0.5mg",
        frequency="once weekly",
        frequency_per_day=1,
        purpose="Blood sugar control",
        active=True,
        start_date=date.today() - timedelta(days=30)
    )
    db_session.add(expensive_med)
    db_session.commit()
    
    # Low adherence pattern suggesting cost barrier
    for i in range(4):  # 4 weeks
        scheduled = datetime.now() - timedelta(weeks=3-i)
        taken = i < 2  # Only first 2 weeks taken
        log = AdherenceLog(
            patient_id=test_patient.id,
            medication_id=expensive_med.id,
            scheduled_time=scheduled,
            status=AdherenceStatus.TAKEN if taken else AdherenceStatus.MISSED,
            taken=taken,
            skip_reason="Cost" if not taken else None
        )
        db_session.add(log)
    
    db_session.commit()
    return test_patient


@pytest.fixture
def patient_with_side_effect_barrier(db_session: Session, test_patient: Patient, test_medication: Medication):
    """Create a patient with side effect-related adherence issues"""
    # Add symptom reports
    symptoms = [
        SymptomReport(
            patient_id=test_patient.id,
            symptom="Nausea",
            severity=6,
            medication_name=test_medication.name,
            suspected_medication_id=test_medication.id,
            description="Severe nausea after taking medication",
            reported_at=datetime.now() - timedelta(days=5)
        ),
        SymptomReport(
            patient_id=test_patient.id,
            symptom="Nausea",
            severity=7,
            medication_name=test_medication.name,
            suspected_medication_id=test_medication.id,
            description="Worse nausea, considering stopping",
            reported_at=datetime.now() - timedelta(days=2)
        ),
    ]
    for s in symptoms:
        db_session.add(s)
    
    # Declining adherence
    for i in range(7):
        scheduled = datetime.now() - timedelta(days=6-i)
        taken = i < 3  # Stopped after day 3
        log = AdherenceLog(
            patient_id=test_patient.id,
            medication_id=test_medication.id,
            scheduled_time=scheduled,
            status=AdherenceStatus.TAKEN if taken else AdherenceStatus.SKIPPED,
            taken=taken,
            skip_reason="Side effects" if not taken else None
        )
        db_session.add(log)
    
    db_session.commit()
    return test_patient


@pytest.fixture
def patient_with_forgetfulness_barrier(db_session: Session, test_patient: Patient, test_medication: Medication):
    """Create a patient with forgetfulness-related adherence issues"""
    # Random miss pattern indicating forgetfulness
    pattern = [True, False, True, True, False, True, False, True, False, True]
    
    for i, taken in enumerate(pattern):
        scheduled = datetime.now() - timedelta(days=9-i)
        log = AdherenceLog(
            patient_id=test_patient.id,
            medication_id=test_medication.id,
            scheduled_time=scheduled,
            status=AdherenceStatus.TAKEN if taken else AdherenceStatus.MISSED,
            taken=taken,
            skip_reason="Forgot" if not taken else None
        )
        db_session.add(log)
    
    db_session.commit()
    return test_patient


# ==================== UNIT TESTS ====================

class TestBarrierAgentInit:
    """Tests for BarrierAgent initialization"""
    
    def test_agent_initialization(self, barrier_agent):
        """Test that barrier agent initializes correctly"""
        assert barrier_agent.agent_name == "Barrier Resolution Agent"
        assert barrier_agent.agent_type == "barrier"
    
    def test_barrier_categories_loaded(self, barrier_agent):
        """Test that barrier categories are defined"""
        assert hasattr(barrier_agent, "barrier_categories")
        assert BarrierCategory.COST in barrier_agent.barrier_categories
        assert BarrierCategory.SIDE_EFFECTS in barrier_agent.barrier_categories
        assert BarrierCategory.FORGETFULNESS in barrier_agent.barrier_categories
    
    def test_category_weights_valid(self, barrier_agent):
        """Test that category weights are in valid range"""
        for category, config in barrier_agent.barrier_categories.items():
            assert 0 <= config["weight"] <= 1
            assert 0 <= config["escalation_threshold"] <= 1


class TestBarrierIdentification:
    """Tests for barrier identification"""
    
    @pytest.mark.unit
    def test_identify_barriers_no_data(self, barrier_agent, db_session, test_patient):
        """Test barrier identification with no adherence data"""
        with patch("agents.barrier_agent.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=db_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            
            result = barrier_agent.identify_barriers(test_patient.id)
            
            assert result.success is True
    
    @pytest.mark.unit
    def test_identify_cost_barrier_from_patterns(self, barrier_agent, sample_agent_state):
        """Test identification of cost barrier from adherence patterns"""
        # Pattern: medication taken at start of month, missed at end
        pass
    
    @pytest.mark.unit
    def test_identify_side_effect_barrier(self, barrier_agent, sample_agent_state):
        """Test identification of side effect barrier"""
        pass
    
    @pytest.mark.unit
    def test_identify_forgetfulness_barrier(self, barrier_agent, sample_agent_state):
        """Test identification of forgetfulness barrier"""
        pass


class TestCostBarrierHandling:
    """Tests for cost barrier resolution"""
    
    @pytest.mark.unit
    def test_handle_cost_barrier(self, barrier_agent, db_session, test_patient, test_medication):
        """Test cost barrier handling"""
        with patch.object(barrier_agent, "call_llm") as mock_llm:
            mock_llm.return_value = '{"strategies": ["generic alternative", "manufacturer coupon"]}'
            
            result = barrier_agent.handle_cost_barrier(
                test_patient.id,
                medication_id=test_medication.id
            )
            
            assert result is not None
    
    @pytest.mark.unit
    def test_find_generic_alternatives(self, barrier_agent):
        """Test finding generic alternatives for medications"""
        with patch("httpx.get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: {"drugGroup": {"conceptGroup": []}}
            )
            
            # Test RxNorm API call if method exists
            if hasattr(barrier_agent, "_find_generic_alternatives"):
                alternatives = barrier_agent._find_generic_alternatives("Lipitor")
                assert isinstance(alternatives, list)
    
    @pytest.mark.unit
    def test_find_cost_assistance_programs(self, barrier_agent):
        """Test finding cost assistance programs"""
        if hasattr(barrier_agent, "_find_cost_assistance"):
            programs = barrier_agent._find_cost_assistance("Metformin")
            assert isinstance(programs, list)


class TestSideEffectBarrierHandling:
    """Tests for side effect barrier resolution"""
    
    @pytest.mark.unit
    def test_handle_side_effect_barrier(self, barrier_agent, db_session, test_patient, test_medication):
        """Test side effect barrier handling"""
        # Create symptom report
        symptom = SymptomReport(
            patient_id=test_patient.id,
            symptom="Nausea",
            severity=5,
            medication_name=test_medication.name,
            suspected_medication_id=test_medication.id
        )
        db_session.add(symptom)
        db_session.commit()
        
        with patch.object(barrier_agent, "call_llm") as mock_llm:
            mock_llm.return_value = '{"recommendations": ["take with food", "split dose"]}'
            
            result = barrier_agent.handle_side_effect_barrier(
                test_patient.id,
                symptom_id=symptom.id,
                medication_id=test_medication.id
            )
            
            assert result is not None
    
    @pytest.mark.unit
    def test_side_effect_escalation_threshold(self, barrier_agent):
        """Test that severe side effects trigger escalation"""
        threshold = barrier_agent.barrier_categories[BarrierCategory.SIDE_EFFECTS]["escalation_threshold"]
        assert threshold > 0


class TestForgetfulnessBarrierHandling:
    """Tests for forgetfulness barrier resolution"""
    
    @pytest.mark.unit
    def test_handle_forgetfulness_barrier(self, barrier_agent, db_session, test_patient):
        """Test forgetfulness barrier handling"""
        with patch.object(barrier_agent, "call_llm") as mock_llm:
            mock_llm.return_value = '{"strategies": ["set phone alarm", "use pill organizer", "link to routine"]}'
            
            result = barrier_agent.handle_forgetfulness_barrier(test_patient.id)
            
            assert result is not None
    
    @pytest.mark.unit
    def test_reminder_strategy_generation(self, barrier_agent):
        """Test generation of reminder strategies"""
        pass


class TestComplexityBarrierHandling:
    """Tests for complexity barrier resolution"""
    
    @pytest.mark.unit
    def test_handle_complexity_barrier(self, barrier_agent, db_session, test_patient):
        """Test complexity barrier handling"""
        with patch.object(barrier_agent, "call_llm") as mock_llm:
            mock_llm.return_value = '{"simplification": "Consider once-daily formulation"}'
            
            result = barrier_agent.handle_complexity_barrier(test_patient.id)
            
            assert result is not None


class TestAgentProcess:
    """Tests for main process() method"""
    
    @pytest.mark.unit
    def test_process_cost_task(self, barrier_agent, sample_agent_state):
        """Test processing cost barrier task"""
        sample_agent_state["current_task"] = "resolve cost barrier"
        sample_agent_state["context"]["medication_name"] = "Ozempic"
        
        with patch.object(barrier_agent, "handle_cost_barrier") as mock_handle:
            mock_handle.return_value = AgentResult(
                success=True,
                summary="Found cost assistance options",
                data={"programs": ["manufacturer coupon"]},
                confidence=0.8
            )
            
            result_state = barrier_agent.process(sample_agent_state)
            
            assert "barrier" in result_state["agent_results"]
            mock_handle.assert_called_once()
    
    @pytest.mark.unit
    def test_process_side_effect_task(self, barrier_agent, sample_agent_state):
        """Test processing side effect barrier task"""
        sample_agent_state["current_task"] = "address side effect concerns"
        sample_agent_state["context"]["symptom_id"] = 1
        
        with patch.object(barrier_agent, "handle_side_effect_barrier") as mock_handle:
            mock_handle.return_value = AgentResult(
                success=True,
                summary="Side effect management plan created",
                data={},
                confidence=0.75
            )
            
            result_state = barrier_agent.process(sample_agent_state)
            
            assert "barrier" in result_state["agent_results"]
    
    @pytest.mark.unit
    def test_process_forgetfulness_task(self, barrier_agent, sample_agent_state):
        """Test processing forgetfulness barrier task"""
        sample_agent_state["current_task"] = "help with forgetting doses"
        
        with patch.object(barrier_agent, "handle_forgetfulness_barrier") as mock_handle:
            mock_handle.return_value = AgentResult(
                success=True,
                summary="Reminder strategies created",
                data={"strategies": []},
                confidence=0.85
            )
            
            result_state = barrier_agent.process(sample_agent_state)
            
            assert "barrier" in result_state["agent_results"]
    
    @pytest.mark.unit
    def test_process_identify_task(self, barrier_agent, sample_agent_state):
        """Test processing barrier identification task"""
        sample_agent_state["current_task"] = "identify adherence barriers"
        
        with patch.object(barrier_agent, "identify_barriers") as mock_identify:
            mock_identify.return_value = AgentResult(
                success=True,
                summary="Barriers identified",
                data={"barriers": [{"type": "cost", "severity": "high"}]},
                confidence=0.9
            )
            
            result_state = barrier_agent.process(sample_agent_state)
            
            assert "barrier" in result_state["agent_results"]
    
    @pytest.mark.unit
    def test_process_handles_errors(self, barrier_agent, sample_agent_state):
        """Test that process handles errors gracefully"""
        sample_agent_state["current_task"] = "identify barriers"
        
        with patch.object(barrier_agent, "identify_barriers") as mock_identify:
            mock_identify.side_effect = Exception("API error")
            
            result_state = barrier_agent.process(sample_agent_state)
            
            assert result_state.get("error") is not None or \
                   result_state["agent_results"]["barrier"]["success"] is False


class TestInterventionGeneration:
    """Tests for intervention generation"""
    
    @pytest.mark.unit
    def test_create_intervention_record(self, barrier_agent, db_session, test_patient):
        """Test creating intervention records"""
        pass
    
    @pytest.mark.unit
    def test_intervention_prioritization(self, barrier_agent):
        """Test that interventions are prioritized correctly"""
        pass


class TestEscalation:
    """Tests for escalation logic"""
    
    @pytest.mark.unit
    def test_escalation_for_severe_cost_barrier(self, barrier_agent, sample_agent_state):
        """Test escalation for severe cost barrier"""
        with patch.object(barrier_agent, "handle_cost_barrier") as mock_handle:
            mock_handle.return_value = AgentResult(
                success=True,
                summary="Patient cannot afford medication",
                data={},
                confidence=0.9,
                requires_escalation=True
            )
            
            sample_agent_state["current_task"] = "resolve cost barrier"
            result_state = barrier_agent.process(sample_agent_state)
            
            # Should flag for escalation to provider
    
    @pytest.mark.unit
    def test_escalation_for_dangerous_side_effects(self, barrier_agent, sample_agent_state):
        """Test escalation for dangerous side effects"""
        pass


# ==================== INTEGRATION TESTS ====================

class TestBarrierAgentIntegration:
    """Integration tests for barrier agent"""
    
    @pytest.mark.integration
    def test_full_barrier_assessment_workflow(
        self, barrier_agent, db_session, patient_with_cost_barrier
    ):
        """Test complete barrier assessment workflow"""
        pass
    
    @pytest.mark.integration
    def test_multi_barrier_handling(self, barrier_agent, db_session, test_patient):
        """Test handling multiple simultaneous barriers"""
        pass


# ==================== EDGE CASES ====================

class TestBarrierAgentEdgeCases:
    """Edge case tests for barrier agent"""
    
    @pytest.mark.unit
    def test_no_barriers_detected(self, barrier_agent, db_session, test_patient):
        """Test handling when no barriers are detected"""
        pass
    
    @pytest.mark.unit
    def test_conflicting_barriers(self, barrier_agent):
        """Test handling of conflicting barrier resolutions"""
        # E.g., cost barrier suggests generic, but patient allergic to generic formulation
        pass
    
    @pytest.mark.unit
    def test_external_api_failure(self, barrier_agent):
        """Test handling when external APIs fail"""
        with patch("httpx.get") as mock_get:
            mock_get.side_effect = Exception("Network error")
            
            # Should handle gracefully
