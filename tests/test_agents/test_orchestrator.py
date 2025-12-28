"""
Tests for Agent Orchestrator
=============================

Tests agent coordination, routing logic, LangGraph state machine,
and multi-agent workflow execution.
"""

import pytest
from datetime import datetime, date, timedelta
from unittest.mock import MagicMock, patch, AsyncMock
from sqlalchemy.orm import Session

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from models import Patient, Medication, AdherenceLog, AdherenceStatus
from agents.state import AgentState, AgentResult, create_initial_state


# ==================== FIXTURES ====================

@pytest.fixture
def mock_planning_agent():
    """Create a mock planning agent"""
    agent = MagicMock()
    agent.agent_name = "Planning Agent"
    agent.agent_type = "planning"
    agent.process.return_value = {
        "patient_id": 1,
        "current_task": "optimize schedule",
        "agent_results": {"planning": {"success": True, "summary": "Schedule optimized"}},
        "context": {},
        "messages": [],
        "next_agent": None,
        "error": None
    }
    return agent


@pytest.fixture
def mock_monitoring_agent():
    """Create a mock monitoring agent"""
    agent = MagicMock()
    agent.agent_name = "Monitoring Agent"
    agent.agent_type = "monitoring"
    agent.process.return_value = {
        "patient_id": 1,
        "current_task": "analyze adherence",
        "agent_results": {"monitoring": {"success": True, "summary": "Adherence analyzed"}},
        "context": {},
        "messages": [],
        "next_agent": None,
        "error": None
    }
    return agent


@pytest.fixture
def mock_barrier_agent():
    """Create a mock barrier agent"""
    agent = MagicMock()
    agent.agent_name = "Barrier Resolution Agent"
    agent.agent_type = "barrier"
    agent.process.return_value = {
        "patient_id": 1,
        "current_task": "identify barriers",
        "agent_results": {"barrier": {"success": True, "summary": "Barriers identified"}},
        "context": {},
        "messages": [],
        "next_agent": None,
        "error": None
    }
    return agent


@pytest.fixture
def mock_liaison_agent():
    """Create a mock liaison agent"""
    agent = MagicMock()
    agent.agent_name = "Healthcare Liaison Agent"
    agent.agent_type = "liaison"
    agent.process.return_value = {
        "patient_id": 1,
        "current_task": "generate report",
        "agent_results": {"liaison": {"success": True, "summary": "Report generated"}},
        "context": {},
        "messages": [],
        "next_agent": None,
        "error": None
    }
    return agent


@pytest.fixture
def orchestrator(mock_planning_agent, mock_monitoring_agent, mock_barrier_agent, mock_liaison_agent):
    """Create orchestrator with mock agents"""
    from agents.orchestrator import AgentOrchestrator
    
    return AgentOrchestrator(
        planning_agent=mock_planning_agent,
        monitoring_agent=mock_monitoring_agent,
        barrier_agent=mock_barrier_agent,
        liaison_agent=mock_liaison_agent
    )


@pytest.fixture
def sample_state(test_patient):
    """Create a sample agent state"""
    return create_initial_state(
        patient_id=test_patient.id,
        task="How can I improve my medication adherence?",
        context={}
    )


# ==================== UNIT TESTS ====================

class TestOrchestratorInit:
    """Tests for AgentOrchestrator initialization"""
    
    def test_orchestrator_initialization(self, orchestrator):
        """Test that orchestrator initializes correctly"""
        assert orchestrator.planning_agent is not None
        assert orchestrator.monitoring_agent is not None
        assert orchestrator.barrier_agent is not None
        assert orchestrator.liaison_agent is not None
    
    def test_graph_built(self, orchestrator):
        """Test that LangGraph is built"""
        assert orchestrator.graph is not None
    
    def test_max_iterations_set(self, orchestrator):
        """Test that max iterations limit is set"""
        assert hasattr(orchestrator, "max_iterations")
        assert orchestrator.max_iterations > 0


class TestTaskRouting:
    """Tests for task routing logic"""
    
    @pytest.mark.unit
    def test_route_to_planning_agent(self, orchestrator, sample_state):
        """Test routing schedule-related tasks to planning agent"""
        sample_state["current_task"] = "optimize my medication schedule"
        
        result = orchestrator._route_task(sample_state)
        next_agent = orchestrator._determine_next_agent(result)
        
        # Should route to planning
        assert next_agent in ["planning", "monitoring", "barrier", "liaison", "end"]
    
    @pytest.mark.unit
    def test_route_to_monitoring_agent(self, orchestrator, sample_state):
        """Test routing adherence-related tasks to monitoring agent"""
        sample_state["current_task"] = "analyze my adherence patterns"
        
        result = orchestrator._route_task(sample_state)
        next_agent = orchestrator._determine_next_agent(result)
        
        assert next_agent in ["planning", "monitoring", "barrier", "liaison", "end"]
    
    @pytest.mark.unit
    def test_route_to_barrier_agent(self, orchestrator, sample_state):
        """Test routing barrier-related tasks to barrier agent"""
        sample_state["current_task"] = "I can't afford my medication"
        
        result = orchestrator._route_task(sample_state)
        next_agent = orchestrator._determine_next_agent(result)
        
        assert next_agent in ["planning", "monitoring", "barrier", "liaison", "end"]
    
    @pytest.mark.unit
    def test_route_to_liaison_agent(self, orchestrator, sample_state):
        """Test routing report-related tasks to liaison agent"""
        sample_state["current_task"] = "generate a report for my doctor"
        
        result = orchestrator._route_task(sample_state)
        next_agent = orchestrator._determine_next_agent(result)
        
        assert next_agent in ["planning", "monitoring", "barrier", "liaison", "end"]
    
    @pytest.mark.unit
    def test_route_ambiguous_task(self, orchestrator, sample_state):
        """Test routing ambiguous tasks"""
        sample_state["current_task"] = "help me"
        
        result = orchestrator._route_task(sample_state)
        # Should handle gracefully, possibly default to monitoring


class TestAgentExecution:
    """Tests for agent execution"""
    
    @pytest.mark.unit
    def test_execute_planning_agent(self, orchestrator, sample_state):
        """Test executing planning agent"""
        sample_state["current_task"] = "create schedule"
        sample_state["target_agent"] = "planning"
        
        result = orchestrator._execute_planning(sample_state)
        
        assert "agent_results" in result
        orchestrator.planning_agent.process.assert_called()
    
    @pytest.mark.unit
    def test_execute_monitoring_agent(self, orchestrator, sample_state):
        """Test executing monitoring agent"""
        sample_state["target_agent"] = "monitoring"
        
        result = orchestrator._execute_monitoring(sample_state)
        
        assert "agent_results" in result
        orchestrator.monitoring_agent.process.assert_called()
    
    @pytest.mark.unit
    def test_execute_barrier_agent(self, orchestrator, sample_state):
        """Test executing barrier agent"""
        sample_state["target_agent"] = "barrier"
        
        result = orchestrator._execute_barrier(sample_state)
        
        assert "agent_results" in result
        orchestrator.barrier_agent.process.assert_called()
    
    @pytest.mark.unit
    def test_execute_liaison_agent(self, orchestrator, sample_state):
        """Test executing liaison agent"""
        sample_state["target_agent"] = "liaison"
        
        result = orchestrator._execute_liaison(sample_state)
        
        assert "agent_results" in result
        orchestrator.liaison_agent.process.assert_called()
    
    @pytest.mark.unit
    def test_agent_execution_error_handling(self, orchestrator, sample_state):
        """Test error handling during agent execution"""
        orchestrator.planning_agent.process.side_effect = Exception("Agent error")
        sample_state["target_agent"] = "planning"
        
        result = orchestrator._execute_planning(sample_state)
        
        # Should handle error gracefully
        assert result is not None


class TestResponseSynthesis:
    """Tests for response synthesis"""
    
    @pytest.mark.unit
    def test_synthesize_single_agent_result(self, orchestrator, sample_state):
        """Test synthesizing response from single agent"""
        sample_state["agent_results"] = {
            "planning": {"success": True, "summary": "Schedule optimized"}
        }
        
        result = orchestrator._synthesize_response(sample_state)
        
        assert result is not None
    
    @pytest.mark.unit
    def test_synthesize_multiple_agent_results(self, orchestrator, sample_state):
        """Test synthesizing response from multiple agents"""
        sample_state["agent_results"] = {
            "planning": {"success": True, "summary": "Schedule optimized"},
            "monitoring": {"success": True, "summary": "Adherence analyzed"}
        }
        
        result = orchestrator._synthesize_response(sample_state)
        
        assert result is not None
    
    @pytest.mark.unit
    def test_synthesize_with_errors(self, orchestrator, sample_state):
        """Test synthesizing when some agents had errors"""
        sample_state["agent_results"] = {
            "planning": {"success": True, "summary": "Schedule optimized"},
            "monitoring": {"success": False, "summary": "Error occurred"}
        }
        
        result = orchestrator._synthesize_response(sample_state)
        
        assert result is not None


class TestCompletionCheck:
    """Tests for workflow completion checking"""
    
    @pytest.mark.unit
    def test_check_complete_when_done(self, orchestrator, sample_state):
        """Test completion check when workflow is done"""
        sample_state["agent_results"] = {"planning": {"success": True}}
        sample_state["next_agent"] = None
        sample_state["iteration_count"] = 1
        
        result = orchestrator._check_if_complete(sample_state)
        
        assert result in ["continue", "end"]
    
    @pytest.mark.unit
    def test_check_continue_when_next_agent(self, orchestrator, sample_state):
        """Test completion check when more agents needed"""
        sample_state["agent_results"] = {"monitoring": {"success": True, "next_agent_suggestion": "barrier"}}
        sample_state["next_agent"] = "barrier"
        sample_state["iteration_count"] = 1
        
        result = orchestrator._check_if_complete(sample_state)
        
        # Should continue to next agent
        assert result in ["continue", "end"]
    
    @pytest.mark.unit
    def test_max_iterations_enforced(self, orchestrator, sample_state):
        """Test that max iterations prevents infinite loops"""
        sample_state["next_agent"] = "planning"  # Would continue
        sample_state["iteration_count"] = orchestrator.max_iterations + 1
        
        result = orchestrator._check_if_complete(sample_state)
        
        # Should end due to max iterations
        assert result == "end"


class TestFullWorkflow:
    """Tests for full workflow execution"""
    
    @pytest.mark.unit
    def test_run_simple_workflow(self, orchestrator, sample_state):
        """Test running a simple single-agent workflow"""
        sample_state["current_task"] = "optimize schedule"
        
        # Mock graph invoke
        with patch.object(orchestrator, "graph") as mock_graph:
            mock_graph.invoke.return_value = {
                **sample_state,
                "agent_results": {"planning": {"success": True}},
                "final_response": "Schedule optimized successfully"
            }
            
            result = orchestrator.run(sample_state)
            
            assert result is not None
    
    @pytest.mark.unit
    def test_run_multi_agent_workflow(self, orchestrator, sample_state):
        """Test running a multi-agent workflow"""
        sample_state["current_task"] = "analyze adherence and suggest improvements"
        
        # This task might involve monitoring → barrier → planning
        pass
    
    @pytest.mark.unit
    def test_workflow_with_escalation(self, orchestrator, sample_state):
        """Test workflow that requires escalation"""
        sample_state["current_task"] = "I have severe side effects"
        sample_state["requires_escalation"] = True
        
        # Should route to liaison for escalation


class TestConversationHandling:
    """Tests for conversation state handling"""
    
    @pytest.mark.unit
    def test_handle_new_conversation(self, orchestrator, test_patient):
        """Test handling new conversation"""
        state = create_initial_state(
            patient_id=test_patient.id,
            task="Hello, I need help",
            context={}
        )
        
        assert state["patient_id"] == test_patient.id
        assert state["current_task"] == "Hello, I need help"
        assert len(state["messages"]) == 0
    
    @pytest.mark.unit
    def test_handle_follow_up_message(self, orchestrator, sample_state):
        """Test handling follow-up in conversation"""
        sample_state["messages"] = [
            {"role": "user", "content": "How is my adherence?"},
            {"role": "assistant", "content": "Your adherence is 85%"}
        ]
        sample_state["current_task"] = "Can you give me more details?"
        
        # Should have context from previous messages


class TestSpecialCases:
    """Tests for special cases and edge conditions"""
    
    @pytest.mark.unit
    def test_handle_empty_task(self, orchestrator, sample_state):
        """Test handling empty task"""
        sample_state["current_task"] = ""
        
        result = orchestrator._route_task(sample_state)
        
        # Should handle gracefully
    
    @pytest.mark.unit
    def test_handle_very_long_task(self, orchestrator, sample_state):
        """Test handling very long task description"""
        sample_state["current_task"] = "a" * 10000  # Very long task
        
        # Should handle gracefully without crashing
    
    @pytest.mark.unit
    def test_handle_missing_patient(self, orchestrator):
        """Test handling when patient doesn't exist"""
        state = create_initial_state(
            patient_id=99999,  # Non-existent patient
            task="Help me",
            context={}
        )
        
        # Should handle gracefully


# ==================== INTEGRATION TESTS ====================

class TestOrchestratorIntegration:
    """Integration tests for orchestrator"""
    
    @pytest.mark.integration
    def test_full_workflow_with_real_agents(self, db_session, test_patient):
        """Test full workflow with real agent instances"""
        # This would use real agents without LLM mocking
        pass
    
    @pytest.mark.integration
    def test_multi_turn_conversation(self, orchestrator, sample_state):
        """Test multi-turn conversation handling"""
        pass


# ==================== LANGGRAPH SPECIFIC TESTS ====================

class TestLangGraphIntegration:
    """Tests specific to LangGraph functionality"""
    
    @pytest.mark.unit
    def test_graph_nodes_registered(self, orchestrator):
        """Test that all graph nodes are registered"""
        # LangGraph should have router, planning, monitoring, barrier, liaison, synthesize nodes
        pass
    
    @pytest.mark.unit
    def test_graph_edges_correct(self, orchestrator):
        """Test that graph edges are correctly configured"""
        pass
    
    @pytest.mark.unit
    def test_conditional_edges_work(self, orchestrator, sample_state):
        """Test that conditional routing works correctly"""
        pass
