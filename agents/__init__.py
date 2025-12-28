"""
AdherenceGuardian Agents Package
Multi-agent system for medication adherence support
"""

from agents.state import (
    AgentState,
    AgentResult,
    PatientContext,
    MedicationInfo,
    ScheduleSlot,
    AdherenceData,
    BarrierInfo,
    SymptomInfo,
    ProviderReportData,
    create_initial_state,
    add_agent_message,
    update_agent_result
)

from agents.base_agent import BaseAgent
from agents.planning_agent import PlanningAgent
from agents.monitoring_agent import MonitoringAgent
from agents.barrier_agent import BarrierAgent
from agents.liaison_agent import LiaisonAgent
from agents.orchestrator import AgentOrchestrator


def create_orchestrator() -> AgentOrchestrator:
    """
    Factory function to create a fully configured AgentOrchestrator
    with all agents initialized
    
    Returns:
        AgentOrchestrator: Configured orchestrator with all agents
    """
    planning_agent = PlanningAgent()
    monitoring_agent = MonitoringAgent()
    barrier_agent = BarrierAgent()
    liaison_agent = LiaisonAgent()
    
    orchestrator = AgentOrchestrator(
        planning_agent=planning_agent,
        monitoring_agent=monitoring_agent,
        barrier_agent=barrier_agent,
        liaison_agent=liaison_agent
    )
    
    return orchestrator


__all__ = [
    # State types
    "AgentState",
    "AgentResult",
    "PatientContext",
    "MedicationInfo",
    "ScheduleSlot",
    "AdherenceData",
    "BarrierInfo",
    "SymptomInfo",
    "ProviderReportData",
    
    # State helpers
    "create_initial_state",
    "add_agent_message",
    "update_agent_result",
    
    # Agents
    "BaseAgent",
    "PlanningAgent",
    "MonitoringAgent",
    "BarrierAgent",
    "LiaisonAgent",
    "AgentOrchestrator",
    
    # Factory
    "create_orchestrator"
]
