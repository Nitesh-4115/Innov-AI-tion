"""
Base Agent Class
Abstract base class for all agents in the AdherenceGuardian system
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
import json

from sqlalchemy.orm import Session

from config import settings, agent_config
from database import get_db_context
import models
from agents.state import AgentState, AgentResult, PatientContext


logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for all AdherenceGuardian agents
    
    Provides common functionality:
    - LLM client management
    - Database access
    - Activity logging
    - Health checks
    - Safety boundaries
    """
    
    # Agent identification
    agent_name: str = "BaseAgent"
    agent_type: str = "base"
    description: str = "Base agent class"
    
    def __init__(self):
        """Initialize the agent with LLM client"""
        self.llm_client = self._init_llm_client()
        self.model = settings.LLM_MODEL
        self.temperature = settings.LLM_TEMPERATURE
        self.max_tokens = settings.LLM_MAX_TOKENS
        
        # Safety settings
        self.safety_never_diagnose = agent_config.SAFETY_NEVER_DIAGNOSE
        self.safety_never_change_dosage = agent_config.SAFETY_NEVER_CHANGE_DOSAGE
        self.safety_always_escalate_severe = agent_config.SAFETY_ALWAYS_ESCALATE_SEVERE
        
        logger.info(f"Initialized {self.agent_name}")
    
    def _init_llm_client(self):
        """Initialize the LLM client based on configuration"""
        if settings.LLM_PROVIDER == "anthropic":
            try:
                import anthropic
                return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
            except ImportError:
                logger.error("Anthropic package not installed")
                return None
        elif settings.LLM_PROVIDER == "openai":
            try:
                from openai import OpenAI
                return OpenAI(api_key=settings.OPENAI_API_KEY)
            except ImportError:
                logger.error("OpenAI package not installed")
                return None
        else:
            logger.warning(f"Unknown LLM provider: {settings.LLM_PROVIDER}")
            return None
    
    @abstractmethod
    def process(self, state: AgentState) -> AgentState:
        """
        Main processing method - must be implemented by subclasses
        
        Args:
            state: Current agent state
            
        Returns:
            Updated agent state
        """
        pass
    
    def call_llm(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        json_mode: bool = False
    ) -> str:
        """
        Call the LLM with the given prompt
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            max_tokens: Override default max tokens
            temperature: Override default temperature
            json_mode: Whether to request JSON output
            
        Returns:
            LLM response text
        """
        if not self.llm_client:
            logger.error("LLM client not initialized")
            return "I apologize, but I'm unable to process your request at the moment."
        
        try:
            # Inject time context into the system prompt so the LLM is aware
            # of current timestamps (both UTC and local) when reasoning.
            def _time_context() -> str:
                now_local = datetime.now().astimezone()
                now_utc = datetime.utcnow().replace(tzinfo=None)
                return (
                    f"Time Context:\n"
                    f"- UTC: {now_utc.isoformat()}Z\n"
                    f"- Local: {now_local.isoformat()} ({now_local.tzname() or 'local'})\n"
                )

            if system_prompt:
                system_prompt = f"{system_prompt}\n\n{_time_context()}"
            else:
                system_prompt = _time_context()

            if settings.LLM_PROVIDER == "anthropic":
                messages = [{"role": "user", "content": prompt}]
                
                kwargs = {
                    "model": self.model,
                    "max_tokens": max_tokens or self.max_tokens,
                    "messages": messages
                }
                
                if system_prompt:
                    kwargs["system"] = system_prompt
                
                response = self.llm_client.messages.create(**kwargs)
                return response.content[0].text
                
            elif settings.LLM_PROVIDER == "openai":
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})
                
                kwargs = {
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": max_tokens or self.max_tokens,
                    "temperature": temperature or self.temperature
                }
                
                if json_mode:
                    kwargs["response_format"] = {"type": "json_object"}
                
                response = self.llm_client.chat.completions.create(**kwargs)
                return response.choices[0].message.content
                
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return f"I encountered an error processing your request: {str(e)}"
    
    def parse_json_response(self, response: str, default: Optional[Dict] = None) -> Dict:
        """
        Parse JSON from LLM response
        
        Args:
            response: Raw LLM response
            default: Default value if parsing fails
            
        Returns:
            Parsed JSON dict
        """
        try:
            # Try to extract JSON from response
            # Handle cases where JSON is wrapped in markdown code blocks
            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                response = response[start:end].strip()
            elif "```" in response:
                start = response.find("```") + 3
                end = response.find("```", start)
                response = response[start:end].strip()
            
            return json.loads(response)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON: {e}")
            return default or {}
    
    def get_patient_context(self, patient_id: int, db: Optional[Session] = None) -> PatientContext:
        """
        Load patient context for agent processing
        
        Args:
            patient_id: Patient identifier
            db: Optional database session
            
        Returns:
            PatientContext with patient data
        """
        close_db = False
        if db is None:
            db = next(get_db_context())
            close_db = True
        
        try:
            patient = db.query(models.Patient).filter(
                models.Patient.id == patient_id
            ).first()
            
            if not patient:
                return PatientContext(patient_id=patient_id, name="Unknown")
            
            # Get medications
            medications = db.query(models.Medication).filter(
                models.Medication.patient_id == patient_id,
                models.Medication.active == True
            ).all()
            
            # Get recent adherence
            from datetime import timedelta
            week_ago = datetime.utcnow() - timedelta(days=7)
            month_ago = datetime.utcnow() - timedelta(days=30)
            
            recent_logs = db.query(models.AdherenceLog).filter(
                models.AdherenceLog.patient_id == patient_id,
                models.AdherenceLog.scheduled_time >= month_ago
            ).all()
            
            week_logs = [l for l in recent_logs if l.scheduled_time >= week_ago]
            
            adherence_7d = (
                sum(1 for l in week_logs if l.taken) / len(week_logs) * 100
            ) if week_logs else None
            
            adherence_30d = (
                sum(1 for l in recent_logs if l.taken) / len(recent_logs) * 100
            ) if recent_logs else None
            
            # Get active barriers
            barriers = db.query(models.BarrierResolution).filter(
                models.BarrierResolution.patient_id == patient_id,
                models.BarrierResolution.resolved == False
            ).all()
            
            # Get recent symptoms
            symptoms = db.query(models.SymptomReport).filter(
                models.SymptomReport.patient_id == patient_id,
                models.SymptomReport.reported_at >= week_ago
            ).all()
            
            return PatientContext(
                patient_id=patient.id,
                name=patient.full_name,
                age=patient.age,
                conditions=patient.conditions if isinstance(patient.conditions, list) else [],
                allergies=patient.allergies if isinstance(patient.allergies, list) else [],
                wake_time=str(patient.wake_time) if patient.wake_time else "08:00",
                sleep_time=str(patient.sleep_time) if patient.sleep_time else "22:00",
                breakfast_time=str(patient.breakfast_time) if patient.breakfast_time else "08:00",
                lunch_time=str(patient.lunch_time) if patient.lunch_time else "12:00",
                dinner_time=str(patient.dinner_time) if patient.dinner_time else "19:00",
                medications=[
                    {
                        "id": m.id,
                        "name": m.name,
                        "dosage": m.dosage,
                        "frequency": m.frequency,
                        "with_food": m.with_food
                    }
                    for m in medications
                ],
                adherence_rate_7d=adherence_7d,
                adherence_rate_30d=adherence_30d,
                active_barriers=[
                    {
                        "id": b.id,
                        "type": b.barrier_type_text or str(b.barrier_type),
                        "description": b.description
                    }
                    for b in barriers
                ],
                recent_symptoms=[
                    {
                        "id": s.id,
                        "symptom": s.symptom,
                        "severity": s.severity,
                        "medication": s.medication_name
                    }
                    for s in symptoms
                ]
            )
            
        finally:
            if close_db:
                db.close()
    
    def log_activity(
        self,
        patient_id: int,
        action: str,
        activity_type: str,
        input_data: Optional[Dict] = None,
        output_data: Optional[Dict] = None,
        reasoning: Optional[str] = None,
        tools_used: Optional[List[str]] = None,
        is_successful: bool = True,
        error_message: Optional[str] = None,
        db: Optional[Session] = None
    ) -> None:
        """
        Log agent activity to database
        
        Args:
            patient_id: Patient identifier
            action: Action performed
            activity_type: Type of activity
            input_data: Input data for the action
            output_data: Output/result data
            reasoning: Agent's reasoning
            tools_used: List of tools used
            is_successful: Whether action succeeded
            error_message: Error message if failed
            db: Optional database session
        """
        close_db = False
        if db is None:
            with get_db_context() as db:
                self._save_activity(
                    db, patient_id, action, activity_type,
                    input_data, output_data, reasoning, tools_used,
                    is_successful, error_message
                )
            return
        
        self._save_activity(
            db, patient_id, action, activity_type,
            input_data, output_data, reasoning, tools_used,
            is_successful, error_message
        )
    
    def _save_activity(
        self,
        db: Session,
        patient_id: int,
        action: str,
        activity_type: str,
        input_data: Optional[Dict],
        output_data: Optional[Dict],
        reasoning: Optional[str],
        tools_used: Optional[List[str]],
        is_successful: bool,
        error_message: Optional[str]
    ) -> None:
        """Internal method to save activity to database"""
        activity = models.AgentActivity(
            patient_id=patient_id,
            agent_name=self.agent_name,
            agent_type=models.AgentType(self.agent_type) if self.agent_type in [e.value for e in models.AgentType] else None,
            action=action,
            activity_type=activity_type,
            input_data=input_data,
            output_data=output_data,
            reasoning=reasoning,
            tools_used=tools_used,
            is_successful=is_successful,
            error_message=error_message,
            timestamp=datetime.utcnow()
        )
        db.add(activity)
        db.commit()
    
    def create_result(
        self,
        success: bool,
        summary: str,
        data: Optional[Dict] = None,
        recommendations: Optional[List[str]] = None,
        confidence: float = 0.0,
        reasoning: Optional[str] = None,
        tools_used: Optional[List[str]] = None,
        requires_followup: bool = False,
        requires_escalation: bool = False,
        next_agent_suggestion: Optional[str] = None
    ) -> AgentResult:
        """
        Create a standardized agent result
        
        Args:
            success: Whether the operation succeeded
            summary: Summary of the result
            data: Detailed result data
            recommendations: List of recommendations
            confidence: Confidence score (0-1)
            reasoning: Agent's reasoning
            tools_used: Tools used in processing
            requires_followup: Whether followup is needed
            requires_escalation: Whether to escalate to provider
            next_agent_suggestion: Suggested next agent
            
        Returns:
            AgentResult instance
        """
        return AgentResult(
            agent_type=self.agent_type,
            success=success,
            summary=summary,
            data=data or {},
            recommendations=recommendations or [],
            confidence=confidence,
            reasoning=reasoning,
            tools_used=tools_used or [self.agent_name],
            requires_followup=requires_followup,
            requires_escalation=requires_escalation,
            next_agent_suggestion=next_agent_suggestion
        )
    
    def check_safety_boundaries(self, content: str) -> Dict[str, bool]:
        """
        Check if response violates safety boundaries
        
        Args:
            content: Content to check
            
        Returns:
            Dict with safety check results
        """
        content_lower = content.lower()
        
        return {
            "contains_diagnosis": any(
                term in content_lower
                for term in ["you have", "diagnosis", "you are suffering from", "condition is"]
            ) and self.safety_never_diagnose,
            "contains_dosage_change": any(
                term in content_lower
                for term in ["increase dose", "decrease dose", "change dosage", "take more", "take less"]
            ) and self.safety_never_change_dosage,
            "requires_escalation": any(
                term in content_lower
                for term in ["emergency", "severe", "critical", "immediate medical attention", "call 911"]
            ) and self.safety_always_escalate_severe
        }
    
    def sanitize_response(self, response: str) -> str:
        """
        Sanitize LLM response to enforce safety boundaries
        
        Args:
            response: Raw LLM response
            
        Returns:
            Sanitized response
        """
        safety_check = self.check_safety_boundaries(response)
        
        if safety_check["contains_diagnosis"]:
            response += "\n\n⚠️ **Note**: I cannot provide medical diagnoses. Please consult your healthcare provider for proper diagnosis."
        
        if safety_check["contains_dosage_change"]:
            response += "\n\n⚠️ **Note**: Any changes to medication dosage should only be made by your prescribing physician."
        
        if safety_check["requires_escalation"]:
            response += "\n\n🚨 **Important**: Based on the information provided, please contact your healthcare provider or emergency services immediately."
        
        return response
    
    def is_healthy(self) -> bool:
        """
        Check if the agent is healthy and operational
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            # Test LLM connectivity with minimal call
            if self.llm_client:
                if settings.LLM_PROVIDER == "anthropic":
                    self.llm_client.messages.create(
                        model=self.model,
                        max_tokens=10,
                        messages=[{"role": "user", "content": "test"}]
                    )
                elif settings.LLM_PROVIDER == "openai":
                    self.llm_client.chat.completions.create(
                        model=self.model,
                        max_tokens=10,
                        messages=[{"role": "user", "content": "test"}]
                    )
                return True
            return False
        except Exception as e:
            logger.error(f"{self.agent_name} health check failed: {e}")
            return False
    
    def get_system_prompt(self) -> str:
        """
        Get the system prompt for this agent
        Override in subclasses for agent-specific prompts
        
        Returns:
            System prompt string
        """
        return f"""You are {self.agent_name}, an AI assistant that is part of the AdherenceGuardian 
medication adherence system. {self.description}

IMPORTANT SAFETY RULES:
1. NEVER provide medical diagnoses
2. NEVER recommend changing medication dosages without physician approval
3. ALWAYS recommend contacting healthcare providers for serious symptoms
4. Be supportive, empathetic, and helpful while maintaining appropriate boundaries

Always be clear, concise, and patient-focused in your responses."""
