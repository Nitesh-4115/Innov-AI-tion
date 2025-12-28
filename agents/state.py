"""
Agent State Definitions
Shared state schemas for LangGraph agent coordination
"""

from typing import Dict, List, Optional, Any, TypedDict, Annotated
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
import operator


class AgentType(str, Enum):
    """Types of agents in the system"""
    ORCHESTRATOR = "orchestrator"
    PLANNING = "planning"
    MONITORING = "monitoring"
    BARRIER = "barrier"
    LIAISON = "liaison"


class MessageRole(str, Enum):
    """Message roles in conversation"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    AGENT = "agent"


class Message(TypedDict):
    """Single message in conversation"""
    role: str
    content: str
    timestamp: datetime
    agent: Optional[str]
    metadata: Optional[Dict[str, Any]]


class AgentState(TypedDict):
    """
    Shared state between agents in LangGraph workflow
    
    This state is passed through the graph and modified by each agent node.
    """
    # Core identifiers
    patient_id: int
    session_id: Optional[str]
    
    # Task information
    current_task: str
    task_type: Optional[str]  # "chat", "schedule", "monitor", "resolve", "report"
    
    # Conversation history
    messages: Annotated[List[Message], operator.add]
    
    # Shared context between agents
    context: Dict[str, Any]
    
    # Routing
    next_agent: str
    previous_agents: List[str]
    
    # Results
    agent_results: Dict[str, Any]
    final_response: str
    
    # Metadata
    tools_used: List[str]
    confidence: float
    error: Optional[str]
    
    # Flags
    requires_escalation: bool
    is_complete: bool


class PatientContext(BaseModel):
    """Patient-specific context loaded for agents"""
    patient_id: int
    name: str
    age: Optional[int] = None
    conditions: List[str] = Field(default_factory=list)
    allergies: List[str] = Field(default_factory=list)
    
    # Lifestyle for scheduling
    wake_time: Optional[str] = "08:00"
    sleep_time: Optional[str] = "22:00"
    breakfast_time: Optional[str] = "08:00"
    lunch_time: Optional[str] = "12:00"
    dinner_time: Optional[str] = "19:00"
    
    # Current medications
    medications: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Recent adherence
    adherence_rate_7d: Optional[float] = None
    adherence_rate_30d: Optional[float] = None
    current_streak: int = 0
    
    # Active barriers
    active_barriers: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Recent symptoms
    recent_symptoms: List[Dict[str, Any]] = Field(default_factory=list)


class MedicationInfo(BaseModel):
    """Medication information for scheduling"""
    id: int
    name: str
    generic_name: Optional[str] = None
    dosage: str
    frequency: str
    frequency_per_day: int = 1
    with_food: bool = False
    instructions: Optional[str] = None
    
    # Constraints
    min_hours_between_doses: Optional[float] = None
    max_daily_doses: Optional[int] = None
    
    # Interactions
    interactions: List[Dict[str, Any]] = Field(default_factory=list)


class ScheduleSlot(BaseModel):
    """Single time slot in medication schedule"""
    time: str  # "08:00"
    medications: List[str]
    meal_relation: Optional[str] = None  # "before", "with", "after"
    notes: Optional[str] = None


class AdherenceData(BaseModel):
    """Adherence data for monitoring"""
    total_doses: int
    taken_doses: int
    missed_doses: int
    delayed_doses: int
    adherence_rate: float
    trend: str  # "improving", "declining", "stable"
    anomalies: List[Dict[str, Any]] = Field(default_factory=list)


class BarrierInfo(BaseModel):
    """Barrier information for resolution"""
    id: Optional[int] = None
    category: str  # "cost", "side_effects", "complexity", etc.
    description: str
    severity: str  # "low", "medium", "high", "critical"
    medication_related: Optional[str] = None
    identified_at: Optional[datetime] = None
    
    # Resolution
    is_resolved: bool = False
    resolution_strategy: Optional[str] = None
    recommendations: List[str] = Field(default_factory=list)


class SymptomInfo(BaseModel):
    """Symptom information for analysis"""
    id: int
    symptom: str
    severity: int  # 1-10
    medication_name: Optional[str] = None
    timing: Optional[str] = None
    description: Optional[str] = None
    
    # Analysis
    correlation_score: Optional[float] = None
    likely_cause: Optional[str] = None
    recommended_action: Optional[str] = None


class ProviderReportData(BaseModel):
    """Data for provider report generation"""
    patient_id: int
    patient_name: str
    report_period_start: str
    report_period_end: str
    
    # Metrics
    overall_adherence: float
    medications_summary: List[Dict[str, Any]]
    
    # Issues
    symptoms_reported: List[Dict[str, Any]]
    barriers_identified: List[Dict[str, Any]]
    
    # Recommendations
    recommendations: List[str]
    concerns: List[str]
    
    # Flags
    requires_attention: bool = False
    escalation_reasons: List[str] = Field(default_factory=list)


class AgentResult(BaseModel):
    """Standard result structure from agents"""
    agent_type: str
    success: bool
    summary: str
    
    # Detailed results
    data: Dict[str, Any] = Field(default_factory=dict)
    recommendations: List[str] = Field(default_factory=list)
    
    # Metadata
    confidence: float = 0.0
    reasoning: Optional[str] = None
    tools_used: List[str] = Field(default_factory=list)
    
    # Flags
    requires_followup: bool = False
    requires_escalation: bool = False
    next_agent_suggestion: Optional[str] = None


def create_initial_state(
    patient_id: int,
    task: str,
    task_type: str = "chat",
    context: Optional[Dict] = None,
    session_id: Optional[str] = None
) -> AgentState:
    """
    Create initial agent state for workflow execution
    
    Args:
        patient_id: Patient identifier
        task: The task or message to process
        task_type: Type of task (chat, schedule, monitor, etc.)
        context: Optional initial context
        session_id: Optional session identifier
    
    Returns:
        Initialized AgentState
    """
    # If no explicit context is provided, ingest lightweight patient context
    # so agents can resolve pronouns (e.g. "it", "that medication").
    final_context = context or {}
    if not context:
        try:
            from database import get_db_context
            import models
            from datetime import date

            with get_db_context() as db:
                patient = db.query(models.Patient).filter(models.Patient.id == patient_id).first()
                if patient:
                    final_context.setdefault("patient_profile", {})
                    final_context["patient_profile"].update({
                        "id": patient.id,
                        "full_name": patient.full_name,
                        "timezone": patient.timezone
                    })

                    meds = []
                    for m in patient.medications:
                        meds.append({
                            "id": m.id,
                            "name": m.name,
                            "dosage": m.dosage,
                            "recurring_times": m.recurring_times or []
                        })
                    final_context["medications"] = meds

                    # Recent schedules and activities
                    schedules = []
                    rows = db.query(models.Schedule).filter(models.Schedule.patient_id == patient_id).order_by(models.Schedule.scheduled_date.desc()).limit(50).all()
                    for s in rows:
                        schedules.append({
                            "id": s.id,
                            "medication_id": s.medication_id,
                            "scheduled_date": str(s.scheduled_date),
                            "scheduled_time": s.scheduled_time,
                            "status": s.status,
                            "medications_list": s.medications_list or []
                        })
                    final_context["schedules"] = schedules

                    acts = db.query(models.AgentActivity).filter(models.AgentActivity.patient_id == patient_id).order_by(models.AgentActivity.timestamp.desc()).limit(20).all()
                    activities = []
                    for a in acts:
                        activities.append({
                            "id": a.id,
                            "action": a.action,
                            "input": a.input_data,
                            "output": a.output_data,
                            "is_successful": bool(a.is_successful),
                            "timestamp": str(a.timestamp)
                        })
                    final_context["recent_agent_activities"] = activities
        except Exception:
            # If anything goes wrong, fall back to empty context
            final_context = context or {}

    return AgentState(
        patient_id=patient_id,
        session_id=session_id,
        current_task=task,
        task_type=task_type,
        messages=[{
            "role": MessageRole.USER.value,
            "content": task,
            "timestamp": datetime.utcnow(),
            "agent": None,
            "metadata": None
        }],
        context=final_context,
        next_agent="",
        previous_agents=[],
        agent_results={},
        final_response="",
        tools_used=[],
        confidence=0.0,
        error=None,
        requires_escalation=False,
        is_complete=False
    )


def add_agent_message(state: AgentState, agent: str, content: str, metadata: Optional[Dict] = None) -> AgentState:
    """Add an agent message to state"""
    state["messages"].append({
        "role": MessageRole.AGENT.value,
        "content": content,
        "timestamp": datetime.utcnow(),
        "agent": agent,
        "metadata": metadata
    })
    return state


def update_agent_result(state: AgentState, agent: str, result: AgentResult) -> AgentState:
    """Update state with agent result"""
    state["agent_results"][agent] = result.model_dump()
    state["tools_used"].extend(result.tools_used)
    state["previous_agents"].append(agent)
    
    if result.requires_escalation:
        state["requires_escalation"] = True
    
    return state
