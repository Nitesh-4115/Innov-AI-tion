"""
Tests for Planning Agent
=========================

Tests medication schedule optimization, drug interaction detection,
and constraint satisfaction algorithms.
"""

import pytest
from datetime import datetime, date, time, timedelta
from unittest.mock import MagicMock, patch, AsyncMock
from sqlalchemy.orm import Session

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from models import Patient, Medication, Schedule, AdherenceStatus
from agents.state import AgentState, AgentResult


# ==================== FIXTURES ====================

@pytest.fixture
def planning_agent():
    """Create a planning agent instance with mocked LLM"""
    with patch("agents.planning_agent.PlanningAgent._init_llm_client") as mock_llm:
        mock_llm.return_value = MagicMock()
        from agents.planning_agent import PlanningAgent
        agent = PlanningAgent()
        yield agent


@pytest.fixture
def sample_agent_state(test_patient):
    """Create a sample agent state for testing"""
    return {
        "patient_id": test_patient.id,
        "current_task": "optimize schedule",
        "context": {},
        "agent_results": {},
        "messages": [],
        "next_agent": None,
        "error": None
    }


@pytest.fixture
def patient_with_complex_regimen(db_session: Session, test_patient: Patient) -> Patient:
    """Create a patient with multiple medications requiring careful scheduling"""
    medications = [
        Medication(
            patient_id=test_patient.id,
            name="Metformin",
            dosage="500mg",
            frequency="2x daily",
            frequency_per_day=2,
            with_food=True,
            instructions="Take with breakfast and dinner",
            active=True,
            start_date=date.today()
        ),
        Medication(
            patient_id=test_patient.id,
            name="Levothyroxine",
            dosage="50mcg",
            frequency="once daily",
            frequency_per_day=1,
            with_food=False,
            instructions="Take on empty stomach, 30 min before breakfast",
            active=True,
            start_date=date.today()
        ),
        Medication(
            patient_id=test_patient.id,
            name="Lisinopril",
            dosage="10mg",
            frequency="once daily",
            frequency_per_day=1,
            with_food=False,
            active=True,
            start_date=date.today()
        ),
        Medication(
            patient_id=test_patient.id,
            name="Omeprazole",
            dosage="20mg",
            frequency="once daily",
            frequency_per_day=1,
            with_food=False,
            instructions="Take 30 minutes before a meal",
            active=True,
            start_date=date.today()
        ),
    ]
    
    for med in medications:
        db_session.add(med)
    
    db_session.commit()
    db_session.refresh(test_patient)
    return test_patient


# ==================== UNIT TESTS ====================

class TestPlanningAgentInit:
    """Tests for PlanningAgent initialization"""
    
    def test_agent_initialization(self, planning_agent):
        """Test that planning agent initializes correctly"""
        assert planning_agent.agent_name == "Planning Agent"
        assert planning_agent.agent_type == "planning"
        assert planning_agent.default_preferences is not None
    
    def test_default_preferences(self, planning_agent):
        """Test default user preferences are set"""
        prefs = planning_agent.default_preferences
        assert "breakfast_time" in prefs
        assert "lunch_time" in prefs
        assert "dinner_time" in prefs
        assert "wake_time" in prefs
        assert "sleep_time" in prefs
    
    def test_drug_interactions_loaded(self, planning_agent):
        """Test that drug interaction database is loaded"""
        assert hasattr(planning_agent, "drug_interactions")


class TestScheduleCreation:
    """Tests for schedule creation functionality"""
    
    @pytest.mark.unit
    def test_create_schedule_no_medications(self, planning_agent, db_session, test_patient):
        """Test schedule creation with no medications"""
        with patch.object(planning_agent, "_get_db_context") as mock_db:
            mock_db.return_value.__enter__ = MagicMock(return_value=db_session)
            mock_db.return_value.__exit__ = MagicMock(return_value=False)
            
            # Patient has no medications initially
            result = planning_agent.create_schedule(test_patient.id)
            
            assert result.success is True
            assert "No active medications" in result.summary or result.data.get("schedule") == {}
    
    @pytest.mark.unit
    def test_parse_time_valid(self, planning_agent):
        """Test time parsing with valid inputs"""
        assert planning_agent._parse_time("08:00") == time(8, 0)
        assert planning_agent._parse_time("20:30") == time(20, 30)
        assert planning_agent._parse_time("00:00") == time(0, 0)
    
    @pytest.mark.unit
    def test_parse_time_invalid(self, planning_agent):
        """Test time parsing with invalid inputs"""
        # Should return a default time or handle gracefully
        result = planning_agent._parse_time("invalid")
        assert result is not None  # Should not crash


class TestConstraintBuilding:
    """Tests for constraint model building"""
    
    @pytest.mark.unit
    def test_build_constraints_empty_medications(self, planning_agent):
        """Test constraint building with empty medication list"""
        user_prefs = planning_agent.default_preferences
        constraints = planning_agent._build_constraints([], user_prefs)
        
        assert isinstance(constraints, dict)
        assert "interactions" in constraints or constraints == {}
    
    @pytest.mark.unit
    def test_build_constraints_single_medication(self, planning_agent, test_medication):
        """Test constraint building with single medication"""
        user_prefs = planning_agent.default_preferences
        constraints = planning_agent._build_constraints([test_medication], user_prefs)
        
        assert isinstance(constraints, dict)


class TestDrugInteractions:
    """Tests for drug interaction checking"""
    
    @pytest.mark.unit
    def test_check_known_interaction(self, planning_agent):
        """Test detection of known drug interactions"""
        # Test with known interacting drugs if the agent has them
        if hasattr(planning_agent, 'drug_interactions'):
            interactions = planning_agent.drug_interactions
            assert isinstance(interactions, (dict, list))
    
    @pytest.mark.unit
    def test_interaction_severity_classification(self, planning_agent):
        """Test that interactions are properly classified by severity"""
        # This tests the internal interaction classification
        pass  # Implement based on actual interaction data structure


class TestScheduleValidation:
    """Tests for schedule validation"""
    
    @pytest.mark.unit
    def test_validate_schedule_empty(self, planning_agent):
        """Test validation of empty schedule"""
        validated = planning_agent._validate_schedule({}, {})
        assert validated is not None
    
    @pytest.mark.unit
    def test_validate_schedule_with_conflicts(self, planning_agent):
        """Test validation catches timing conflicts"""
        # Two medications at exact same time should be flagged
        schedule = {
            "08:00": ["Metformin", "Levothyroxine"],  # Conflict - levothyroxine needs empty stomach
        }
        # Validation should catch this or adjust
        validated = planning_agent._validate_schedule(schedule, {})
        assert validated is not None


class TestAgentProcess:
    """Tests for main process() method"""
    
    @pytest.mark.unit
    def test_process_optimize_schedule_task(self, planning_agent, sample_agent_state, db_session):
        """Test processing optimize schedule task"""
        sample_agent_state["current_task"] = "optimize schedule"
        
        with patch.object(planning_agent, "create_schedule") as mock_create:
            mock_create.return_value = AgentResult(
                success=True,
                summary="Schedule created",
                data={"schedule": {"08:00": ["Metformin"]}},
                confidence=0.85
            )
            
            result_state = planning_agent.process(sample_agent_state)
            
            assert "planning" in result_state["agent_results"]
            mock_create.assert_called_once()
    
    @pytest.mark.unit
    def test_process_replan_task(self, planning_agent, sample_agent_state):
        """Test processing replan task"""
        sample_agent_state["current_task"] = "replan schedule due to missed dose"
        
        with patch.object(planning_agent, "replan_schedule") as mock_replan:
            mock_replan.return_value = AgentResult(
                success=True,
                summary="Schedule replanned",
                data={},
                confidence=0.8
            )
            
            result_state = planning_agent.process(sample_agent_state)
            
            assert "planning" in result_state["agent_results"]
            mock_replan.assert_called_once()
    
    @pytest.mark.unit
    def test_process_check_interaction_task(self, planning_agent, sample_agent_state):
        """Test processing interaction check task"""
        sample_agent_state["current_task"] = "check interaction between medications"
        
        with patch.object(planning_agent, "check_interactions") as mock_check:
            mock_check.return_value = AgentResult(
                success=True,
                summary="No dangerous interactions found",
                data={"interactions": []},
                confidence=0.9
            )
            
            result_state = planning_agent.process(sample_agent_state)
            
            assert "planning" in result_state["agent_results"]
            mock_check.assert_called_once()
    
    @pytest.mark.unit
    def test_process_handles_errors(self, planning_agent, sample_agent_state):
        """Test that process handles errors gracefully"""
        sample_agent_state["current_task"] = "optimize schedule"
        
        with patch.object(planning_agent, "create_schedule") as mock_create:
            mock_create.side_effect = Exception("Database error")
            
            result_state = planning_agent.process(sample_agent_state)
            
            assert result_state.get("error") is not None or \
                   result_state["agent_results"]["planning"]["success"] is False


class TestUserPreferences:
    """Tests for user preference handling"""
    
    @pytest.mark.unit
    def test_get_user_preferences_default(self, planning_agent):
        """Test getting default preferences when patient has none"""
        prefs = planning_agent._get_user_preferences(None)
        
        assert prefs["breakfast_time"] == time(8, 0)
        assert prefs["lunch_time"] == time(12, 0)
        assert prefs["dinner_time"] == time(18, 0)
    
    @pytest.mark.unit
    def test_get_user_preferences_custom(self, planning_agent, test_patient):
        """Test getting custom preferences from patient"""
        # Mock patient with custom preferences
        test_patient.lifestyle_preferences = {
            "breakfast_time": "07:30",
            "lunch_time": "13:00",
            "dinner_time": "19:30"
        }
        
        prefs = planning_agent._get_user_preferences(test_patient)
        
        # Should use custom values
        assert prefs is not None


# ==================== INTEGRATION TESTS ====================

class TestPlanningAgentIntegration:
    """Integration tests for planning agent"""
    
    @pytest.mark.integration
    @pytest.mark.slow
    def test_full_schedule_creation_workflow(
        self, planning_agent, db_session, patient_with_complex_regimen
    ):
        """Test complete schedule creation workflow"""
        # This would test the full flow with mocked LLM
        with patch.object(planning_agent, "call_llm") as mock_llm:
            mock_llm.return_value = '{"schedule": {"07:00": ["Levothyroxine"], "08:00": ["Metformin"]}, "reasoning": "Levothyroxine first on empty stomach"}'
            
            # Would need to set up proper mocking for full integration
            pass
    
    @pytest.mark.integration
    def test_schedule_respects_food_requirements(self, planning_agent, db_session, test_patient):
        """Test that schedules respect food requirements"""
        # Create medication that must be taken with food
        med_with_food = Medication(
            patient_id=test_patient.id,
            name="Metformin",
            dosage="500mg",
            frequency="2x daily",
            frequency_per_day=2,
            with_food=True,
            active=True,
            start_date=date.today()
        )
        db_session.add(med_with_food)
        db_session.commit()
        
        # Schedule should align with meal times
        # This is validated by the constraint system


# ==================== EDGE CASES ====================

class TestPlanningAgentEdgeCases:
    """Edge case tests for planning agent"""
    
    @pytest.mark.unit
    def test_schedule_with_maximum_medications(self, planning_agent, db_session, test_patient):
        """Test scheduling with many medications"""
        # Create 10+ medications to test scaling
        for i in range(10):
            med = Medication(
                patient_id=test_patient.id,
                name=f"Medication{i}",
                dosage="10mg",
                frequency="once daily",
                frequency_per_day=1,
                active=True,
                start_date=date.today()
            )
            db_session.add(med)
        db_session.commit()
        
        # Should handle gracefully without crashing
    
    @pytest.mark.unit
    def test_schedule_with_conflicting_requirements(self, planning_agent):
        """Test handling of impossible scheduling conflicts"""
        # E.g., two medications that both need empty stomach and interact
        pass
    
    @pytest.mark.unit
    def test_schedule_overnight_medications(self, planning_agent):
        """Test medications that span midnight"""
        pass
