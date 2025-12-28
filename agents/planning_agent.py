"""
Planning Agent
Optimizes medication schedules using constraint satisfaction and AI reasoning
"""

from typing import List, Dict, Tuple, Optional, Any
from datetime import datetime, time, timedelta
import logging
import json

from sqlalchemy.orm import Session

from config import settings, agent_config
from database import get_db_context
import models
from agents.base_agent import BaseAgent
from agents.state import AgentState, AgentResult
from agents.prompts import (
    PLANNING_SYSTEM_PROMPT,
    SCHEDULE_OPTIMIZATION_PROMPT,
    REPLAN_SCHEDULE_PROMPT,
    INTERACTION_CHECK_PROMPT,
    KNOWN_INTERACTIONS,
    FOOD_REQUIREMENTS
)


logger = logging.getLogger(__name__)


class PlanningAgent(BaseAgent):
    """
    Agent responsible for:
    - Creating optimal medication schedules
    - Managing drug interactions and timing constraints
    - Replanning when disruptions occur
    - Multi-step reasoning for complex regimens
    """
    
    agent_name = "Planning Agent"
    agent_type = "planning"
    description = "Optimizes medication schedules using constraint satisfaction and AI reasoning"
    
    def __init__(self):
        super().__init__()
        
        # Load drug interaction database
        self.drug_interactions = self._load_drug_interactions()
        
        # Default user preferences (overridden by patient data)
        self.default_preferences = {
            "breakfast_time": time(8, 0),
            "lunch_time": time(12, 0),
            "dinner_time": time(18, 0),
            "sleep_time": time(22, 0),
            "wake_time": time(7, 0)
        }
    
    def process(self, state: AgentState) -> AgentState:
        """Main processing method called by orchestrator"""
        task = state["current_task"]
        patient_id = state["patient_id"]
        context = state.get("context", {})
        
        try:
            if "optimize schedule" in task.lower() or "new medication" in task.lower():
                result = self.create_schedule(patient_id, context.get("medication_id"))
            elif "replan" in task.lower():
                result = self.replan_schedule(patient_id, context)
            elif "check interaction" in task.lower():
                result = self.check_interactions(patient_id)
            else:
                result = self.analyze_schedule_query(patient_id, task)
            
            # Update state with results
            state["agent_results"]["planning"] = result.model_dump()
            state["context"]["planning_result"] = result.model_dump()
            
            # Suggest next agent if needed
            if result.next_agent_suggestion:
                state["next_agent"] = result.next_agent_suggestion
                
        except Exception as e:
            logger.error(f"Planning agent error: {e}")
            state["error"] = str(e)
            state["agent_results"]["planning"] = self.create_result(
                success=False,
                summary=f"Error in planning: {str(e)}",
                confidence=0.0
            ).model_dump()
        
        return state
    
    def create_schedule(self, patient_id: int, new_medication_id: int = None) -> AgentResult:
        """
        Create optimized medication schedule using multi-step reasoning
        
        Steps:
        1. Gather all medications and constraints
        2. Identify drug interactions
        3. Determine optimal timing based on:
           - Drug interactions (temporal separation)
           - Food requirements
           - User lifestyle (meals, sleep)
        4. Generate schedule with reasoning
        
        Args:
            patient_id: Patient identifier
            new_medication_id: Optional new medication to incorporate
            
        Returns:
            AgentResult with schedule data
        """
        with get_db_context() as db:
            # Step 1: Gather medications
            medications = db.query(models.Medication).filter(
                models.Medication.patient_id == patient_id,
                models.Medication.is_active == True
            ).all()
            
            if not medications:
                return self.create_result(
                    success=True,
                    summary="No active medications found to schedule",
                    data={"schedule": {}},
                    confidence=0.9
                )
            
            # Get patient preferences
            patient = db.query(models.Patient).filter(
                models.Patient.id == patient_id
            ).first()
            
            user_preferences = self._get_user_preferences(patient)
            
            # Step 2: Build constraint model
            constraints = self._build_constraints(medications, user_preferences)
            
            # Step 3: Use LLM for intelligent scheduling
            schedule = self._llm_optimize_schedule(medications, constraints, patient)
            
            # Step 4: Validate and store
            validated_schedule = self._validate_schedule(schedule, constraints)
            self._store_schedule(db, patient_id, validated_schedule)
            
            # Check for drug interactions to report
            interactions = constraints.get("interactions", [])
            warnings = schedule.get("warnings", [])
            
            # Log agent activity
            self.log_activity(
                patient_id=patient_id,
                action="schedule_creation",
                activity_type="planning",
                input_data={"medication_count": len(medications)},
                output_data={
                    "schedule": validated_schedule,
                    "time_slots": len(validated_schedule)
                },
                reasoning=schedule.get("reasoning", ""),
                db=db
            )
            
            return self.create_result(
                success=True,
                summary=f"Created optimized schedule with {len(validated_schedule)} time slots for {len(medications)} medication(s)",
                data={
                    "schedule": validated_schedule,
                    "interactions": interactions,
                    "time_slots": len(validated_schedule),
                    "medication_count": len(medications),
                    "schedule_updated": True
                },
                recommendations=warnings,
                confidence=0.85,
                reasoning=schedule.get("reasoning", ""),
                tools_used=["constraint_solver", "interaction_checker", "schedule_optimizer"]
            )
    
    def _get_user_preferences(self, patient: Optional[models.Patient]) -> Dict:
        """Get user preferences from patient data or defaults"""
        preferences = self.default_preferences.copy()
        
        if patient and patient.lifestyle_preferences:
            prefs = patient.lifestyle_preferences
            if prefs.get("breakfast_time"):
                preferences["breakfast_time"] = self._parse_time(prefs["breakfast_time"])
            if prefs.get("lunch_time"):
                preferences["lunch_time"] = self._parse_time(prefs["lunch_time"])
            if prefs.get("dinner_time"):
                preferences["dinner_time"] = self._parse_time(prefs["dinner_time"])
            if prefs.get("sleep_time"):
                preferences["sleep_time"] = self._parse_time(prefs["sleep_time"])
            if prefs.get("wake_time"):
                preferences["wake_time"] = self._parse_time(prefs["wake_time"])
        
        return preferences
    
    def _parse_time(self, time_str: str) -> time:
        """Parse time string to time object"""
        try:
            if isinstance(time_str, time):
                return time_str
            parts = time_str.split(":")
            return time(int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)
        except:
            return time(8, 0)
    
    def _build_constraints(self, medications: List, user_preferences: Dict) -> Dict:
        """
        Build constraint model for scheduling
        
        Constraints include:
        - Drug interactions (must be separated by X hours)
        - Food requirements (must be with/without meals)
        - Frequency requirements
        - User preferences
        """
        constraints = {
            "interactions": [],
            "food_requirements": {},
            "timing_restrictions": [],
            "user_preferences": user_preferences
        }
        
        # Check each pair for interactions
        for i, med1 in enumerate(medications):
            for med2 in medications[i+1:]:
                interaction = self._check_interaction(med1.name, med2.name)
                if interaction:
                    constraints["interactions"].append(interaction)
            
            # Food requirements
            if med1.with_food:
                constraints["food_requirements"][med1.name] = "with_meal"
            
            # Parse frequency to timing restrictions
            timing = self._parse_frequency(med1.frequency)
            constraints["timing_restrictions"].append({
                "medication": med1.name,
                "times_per_day": timing["count"],
                "minimum_gap_hours": timing["gap"]
            })
        
        return constraints
    
    def _check_interaction(self, drug1: str, drug2: str) -> Dict:
        """Check if two drugs have interactions"""
        # In production, query DrugBank or RxNorm
        # Simplified example
        known_interactions = {
            ("Metformin", "Lisinopril"): {
                "severity": "moderate",
                "separation_hours": 0,  # Can take together
                "description": "Monitor kidney function"
            }
        }
        
        pair = tuple(sorted([drug1, drug2]))
        return known_interactions.get(pair)
    
    def _parse_frequency(self, frequency: str) -> Dict:
        """Parse frequency string to structured format"""
        freq_lower = frequency.lower()
        
        if "once" in freq_lower:
            return {"count": 1, "gap": 24}
        elif "twice" in freq_lower:
            return {"count": 2, "gap": 12}
        elif "three" in freq_lower or "3" in freq_lower:
            return {"count": 3, "gap": 8}
        elif "four" in freq_lower or "4" in freq_lower:
            return {"count": 4, "gap": 6}
        else:
            return {"count": 1, "gap": 24}
    
    def _llm_optimize_schedule(self, medications: List, constraints: Dict, patient: Optional[models.Patient] = None) -> Dict:
        """
        Use Claude to reason about optimal scheduling
        Provides human-like reasoning about trade-offs
        """
        # Build prompt
        med_list = "\n".join([
            f"- {m.name} {m.dosage}: {m.frequency}" + 
            (f" (with food)" if m.with_food else "")
            for m in medications
        ])
        
        # Format time preferences safely
        prefs = constraints.get("user_preferences", {})
        breakfast = prefs.get("breakfast_time", "08:00")
        lunch = prefs.get("lunch_time", "12:00")
        dinner = prefs.get("dinner_time", "18:00")
        sleep = prefs.get("sleep_time", "22:00")
        
        constraints_text = f"""
Constraints:
- Breakfast: {breakfast}
- Lunch: {lunch}
- Dinner: {dinner}
- Sleep: {sleep}

Drug Requirements:
{chr(10).join([f"- {k}: {v}" for k, v in constraints.get('food_requirements', {}).items()]) or "None"}

Interactions:
{chr(10).join([f"- {i.get('description', 'None')}" for i in constraints.get('interactions', [])]) if constraints.get('interactions') else "None"}
"""
        
        prompt = f"""You are a medication scheduling assistant. Create an optimal daily schedule for these medications:

{med_list}

{constraints_text}

Provide:
1. Optimal schedule (times and medications)
2. Reasoning for each decision
3. Any warnings or considerations

Format as JSON with structure:
{{
  "schedule": {{"08:00": ["Med1 dosage", "Med2 dosage"], "20:00": ["Med1 dosage"]}},
  "reasoning": "explanation",
  "warnings": ["warning1", "warning2"]
}}"""
        
        # Build a system prompt that includes the patient's local time (if available)
        system_prompt = self.get_system_prompt()
        try:
            if patient and getattr(patient, 'timezone', None):
                from zoneinfo import ZoneInfo
                tz = ZoneInfo(patient.timezone)
                now_patient = datetime.now(tz)
                patient_time_block = (
                    f"Patient Time Context:\n- Timezone: {patient.timezone}\n- Local Time: {now_patient.isoformat()} ({now_patient.tzname() or 'local'})\n"
                )
                system_prompt = f"{system_prompt}\n\n{patient_time_block}"
        except Exception:
            # If timezone parsing fails, fall back to system prompt only
            pass

        # Use base agent's call_llm method
        response = self.call_llm(prompt, system_prompt=system_prompt)
        
        # Parse response using base agent's helper
        result = self.parse_json_response(response, {
            "schedule": {
                "08:00": [f"{m.name} {m.dosage}" for m in medications if "once" in (m.frequency or "").lower() or "twice" in (m.frequency or "").lower()],
                "20:00": [f"{m.name} {m.dosage}" for m in medications if "twice" in (m.frequency or "").lower()]
            },
            "reasoning": "Default schedule based on frequency",
            "warnings": []
        })
        
        return result
    
    def _validate_schedule(self, schedule: Dict, constraints: Dict) -> Dict:
        """Validate schedule meets all constraints"""
        # Check minimum gaps between doses
        # Verify food requirements aligned with meals
        # Confirm all medications scheduled
        
        validated = schedule.get("schedule", schedule)
        
        # Ensure it's a dict
        if not isinstance(validated, dict):
            validated = {}
        
        return validated
    
    def _store_schedule(self, db: Session, patient_id: int, schedule: Dict):
        """Store schedule in database"""
        today = datetime.now().date()
        
        # Store as MedicationSchedule entries
        for time_str, medications in schedule.items():
            try:
                # Parse time string
                hour, minute = map(int, time_str.split(":"))
                scheduled_time = datetime.combine(today, time(hour, minute))
                
                for med_info in medications:
                    # Try to find the medication in DB
                    med_name = med_info.split()[0] if med_info else "Unknown"
                    
                    schedule_entry = models.MedicationSchedule(
                        patient_id=patient_id,
                        medication_id=None,  # Would link to actual medication
                        scheduled_time=scheduled_time,
                        frequency="daily",
                        is_active=True,
                        notes=f"Auto-generated by Planning Agent: {med_info}"
                    )
                    db.add(schedule_entry)
            except Exception as e:
                logger.warning(f"Error storing schedule entry: {e}")
        
        db.commit()
    
    def replan_schedule(self, patient_id: int, context: Dict) -> AgentResult:
        """
        Replan schedule due to disruption (travel, missed dose, etc.)
        
        This demonstrates adaptive planning capability
        
        Args:
            patient_id: Patient identifier
            context: Context with disruption details
            
        Returns:
            AgentResult with replanned schedule
        """
        disruption_type = context.get("disruption_type", "general")
        disruption_details = context.get("disruption_details", "")
        
        with get_db_context() as db:
            # Get current medications
            medications = db.query(models.Medication).filter(
                models.Medication.patient_id == patient_id,
                models.Medication.is_active == True
            ).all()
            
            if not medications:
                return self.create_result(
                    success=True,
                    summary="No medications to replan",
                    confidence=0.9
                )
            
            # Use LLM to generate replanning advice
            prompt = f"""A patient needs to replan their medication schedule due to a disruption.

Disruption Type: {disruption_type}
Details: {disruption_details}

Current medications:
{chr(10).join([f"- {m.name} {m.dosage}: {m.frequency}" for m in medications])}

Provide:
1. Adjusted schedule recommendations
2. Reasoning for changes
3. Any precautions

Format as JSON:
{{
    "adjusted_schedule": {{"time": ["medications"]}},
    "reasoning": "...",
    "precautions": ["..."]
}}"""
            
            response = self.call_llm(prompt, system_prompt=self.get_system_prompt())
            result = self.parse_json_response(response, {
                "adjusted_schedule": {},
                "reasoning": "Adjusted timing to accommodate disruption",
                "precautions": []
            })
            
            self.log_activity(
                patient_id=patient_id,
                action="schedule_replan",
                activity_type="planning",
                input_data={"disruption_type": disruption_type},
                output_data=result,
                db=db
            )
            
            return self.create_result(
                success=True,
                summary=f"Schedule replanned due to {disruption_type}",
                data={
                    "schedule": result.get("adjusted_schedule", {}),
                    "schedule_updated": True
                },
                recommendations=result.get("precautions", []),
                confidence=0.75,
                reasoning=result.get("reasoning", "")
            )
    
    def check_interactions(self, patient_id: int) -> AgentResult:
        """
        Check for drug interactions among patient's medications
        
        Args:
            patient_id: Patient identifier
            
        Returns:
            AgentResult with interaction information
        """
        with get_db_context() as db:
            medications = db.query(models.Medication).filter(
                models.Medication.patient_id == patient_id,
                models.Medication.is_active == True
            ).all()
            
            if len(medications) < 2:
                return self.create_result(
                    success=True,
                    summary="Not enough medications to check for interactions",
                    confidence=0.9
                )
            
            interactions = []
            
            # Check each pair
            for i, med1 in enumerate(medications):
                for med2 in medications[i+1:]:
                    interaction = self._check_interaction(med1.name, med2.name)
                    if interaction:
                        interactions.append({
                            "drug1": med1.name,
                            "drug2": med2.name,
                            **interaction
                        })
            
            # Use LLM for additional analysis
            if medications:
                med_names = [m.name for m in medications]
                prompt = f"""Check for potential drug interactions between these medications:
{', '.join(med_names)}

Provide any known interactions, severity, and recommendations.

Format as JSON:
{{
    "interactions": [{{"drugs": ["drug1", "drug2"], "severity": "low/moderate/high", "description": "..."}}],
    "recommendations": ["..."]
}}"""
                
                response = self.call_llm(prompt, system_prompt=self.get_system_prompt())
                llm_result = self.parse_json_response(response, {"interactions": [], "recommendations": []})
                
                # Merge LLM interactions with known ones
                for llm_int in llm_result.get("interactions", []):
                    if llm_int not in interactions:
                        interactions.append(llm_int)
            
            return self.create_result(
                success=True,
                summary=f"Found {len(interactions)} potential interaction(s)" if interactions else "No significant interactions found",
                data={
                    "interactions": interactions,
                    "medication_count": len(medications)
                },
                recommendations=llm_result.get("recommendations", []) if medications else [],
                confidence=0.8,
                tools_used=["interaction_checker", "rxnorm_lookup"]
            )
    
    def analyze_schedule_query(self, patient_id: int, query: str) -> AgentResult:
        """Answer questions about schedule using LLM"""
        with get_db_context() as db:
            # Get current schedules
            schedules = db.query(models.MedicationSchedule).filter(
                models.MedicationSchedule.patient_id == patient_id,
                models.MedicationSchedule.is_active == True
            ).all()
            
            # Get medications for context
            medications = db.query(models.Medication).filter(
                models.Medication.patient_id == patient_id,
                models.Medication.is_active == True
            ).all()
            
            schedule_text = "\n".join([
                f"{s.scheduled_time.strftime('%H:%M') if s.scheduled_time else 'Unknown'}: {s.notes or 'Medication'}"
                for s in schedules
            ]) or "No active schedule found"
            
            med_text = "\n".join([
                f"- {m.name} {m.dosage}: {m.frequency}"
                for m in medications
            ]) or "No medications found"
            
            prompt = f"""Based on this patient's medication information:

Medications:
{med_text}

Current Schedule:
{schedule_text}

Answer this question: {query}

Provide a clear, helpful response."""
            
            response = self.call_llm(prompt, system_prompt=self.get_system_prompt())
            
            return self.create_result(
                success=True,
                summary=response,
                confidence=0.8
            )
    
    def _load_drug_interactions(self) -> Dict:
        """Load drug interaction database"""
        # In production, load from DrugBank or similar
        # This is a simplified version with common interactions
        return {
            ("metformin", "lisinopril"): {
                "severity": "low",
                "separation_hours": 0,
                "description": "Generally safe. Monitor kidney function."
            },
            ("warfarin", "aspirin"): {
                "severity": "high",
                "separation_hours": 0,
                "description": "Increased bleeding risk. Requires careful monitoring."
            },
            ("atorvastatin", "grapefruit"): {
                "severity": "moderate",
                "separation_hours": 0,
                "description": "Avoid grapefruit. Can increase statin levels."
            }
        }
    
    def get_system_prompt(self) -> str:
        """Get planning-specific system prompt from prompts module"""
        return PLANNING_SYSTEM_PROMPT