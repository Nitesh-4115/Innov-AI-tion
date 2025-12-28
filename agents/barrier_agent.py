"""
Barrier Resolution Agent
Identifies and resolves medication adherence barriers
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging
import httpx

from sqlalchemy.orm import Session

from config import settings, agent_config
from database import get_db_context
import models
from agents.base_agent import BaseAgent
from agents.state import AgentState, AgentResult, BarrierInfo
from agents.prompts import (
    BARRIER_SYSTEM_PROMPT,
    BARRIER_PRIORITIZATION_PROMPT,
    COST_ASSISTANCE_PROMPT,
    SIDE_EFFECT_ANALYSIS_PROMPT,
    FORGETFULNESS_STRATEGY_PROMPT,
    COMPLEXITY_SIMPLIFICATION_PROMPT,
    INTERVENTION_TEMPLATES
)


logger = logging.getLogger(__name__)


class BarrierAgent(BaseAgent):
    """
    Agent responsible for:
    - Identifying root causes of adherence barriers
    - Generating personalized intervention strategies
    - Connecting patients with cost assistance programs
    - Recommending schedule modifications
    - Adapting strategies based on patient responses
    """
    
    agent_name = "Barrier Resolution Agent"
    agent_type = "barrier"
    description = "Identifies and resolves barriers to medication adherence including cost, side effects, complexity, and forgetfulness"
    
    def __init__(self):
        super().__init__()
        
        # Barrier categories with weights
        self.barrier_categories = {
            models.BarrierCategory.COST: {"weight": 0.9, "escalation_threshold": 0.7},
            models.BarrierCategory.SIDE_EFFECTS: {"weight": 0.85, "escalation_threshold": 0.6},
            models.BarrierCategory.FORGETFULNESS: {"weight": 0.6, "escalation_threshold": 0.8},
            models.BarrierCategory.COMPLEXITY: {"weight": 0.7, "escalation_threshold": 0.75},
            models.BarrierCategory.BELIEFS: {"weight": 0.75, "escalation_threshold": 0.65},
            models.BarrierCategory.ACCESS: {"weight": 0.8, "escalation_threshold": 0.7},
            models.BarrierCategory.LIFESTYLE: {"weight": 0.65, "escalation_threshold": 0.8}
        }
        
        # External API configuration
        self.rxnorm_api = "https://rxnav.nlm.nih.gov/REST"
        self.goodrx_api_key = settings.GOODRX_API_KEY
    
    def process(self, state: AgentState) -> AgentState:
        """Main processing method called by orchestrator"""
        task = state["current_task"].lower()
        patient_id = state["patient_id"]
        context = state.get("context", {})
        
        try:
            if "cost" in task:
                result = self.handle_cost_barrier(
                    patient_id,
                    context.get("medication_id"),
                    context.get("medication_name")
                )
            elif "side effect" in task or "symptom" in task:
                result = self.handle_side_effect_barrier(
                    patient_id,
                    context.get("symptom_id"),
                    context.get("medication_id")
                )
            elif "forget" in task or "reminder" in task:
                result = self.handle_forgetfulness_barrier(patient_id)
            elif "complex" in task or "regime" in task:
                result = self.handle_complexity_barrier(patient_id)
            elif "identify" in task or "assess" in task:
                result = self.identify_barriers(patient_id)
            else:
                # Default: comprehensive barrier assessment
                result = self.identify_barriers(patient_id)
            
            state["agent_results"]["barrier"] = result.model_dump()
            state["context"]["barrier_result"] = result.model_dump()
            
            if result.requires_escalation:
                state["requires_escalation"] = True
            
            if result.next_agent_suggestion:
                state["next_agent"] = result.next_agent_suggestion
                
        except Exception as e:
            logger.error(f"Barrier agent error: {e}")
            state["error"] = str(e)
            state["agent_results"]["barrier"] = self.create_result(
                success=False,
                summary=f"Error resolving barriers: {str(e)}",
                confidence=0.0
            ).model_dump()
        
        return state
    
    def identify_barriers(self, patient_id: int) -> AgentResult:
        """
        Identify all barriers affecting a patient's adherence
        
        Args:
            patient_id: Patient identifier
            
        Returns:
            AgentResult with identified barriers and strategies
        """
        with get_db_context() as db:
            # Get patient data
            patient_context = self.get_patient_context(patient_id, db)
            
            if not patient_context:
                return self.create_result(
                    success=False,
                    summary="Patient not found",
                    confidence=0.0
                )
            
            barriers = []
            
            # 1. Check for cost barriers
            cost_barrier = self._assess_cost_barrier(patient_id, db)
            if cost_barrier:
                barriers.append(cost_barrier)
            
            # 2. Check for side effect barriers
            side_effect_barrier = self._assess_side_effect_barrier(patient_id, db)
            if side_effect_barrier:
                barriers.append(side_effect_barrier)
            
            # 3. Check for forgetfulness barriers
            forgetfulness_barrier = self._assess_forgetfulness_barrier(patient_id, db)
            if forgetfulness_barrier:
                barriers.append(forgetfulness_barrier)
            
            # 4. Check for complexity barriers
            complexity_barrier = self._assess_complexity_barrier(patient_id, db)
            if complexity_barrier:
                barriers.append(complexity_barrier)
            
            # 5. Check for lifestyle barriers
            lifestyle_barrier = self._assess_lifestyle_barrier(patient_id, db)
            if lifestyle_barrier:
                barriers.append(lifestyle_barrier)
            
            # Use LLM to prioritize and generate comprehensive strategy
            llm_analysis = self._llm_prioritize_barriers(barriers, patient_context)
            
            # Generate interventions for top barriers
            interventions = self._generate_interventions(barriers[:3], patient_id, db)
            
            # Log activity
            self.log_activity(
                patient_id=patient_id,
                action="barrier_assessment",
                activity_type="barrier_resolution",
                output_data={"barriers_found": len(barriers)},
                reasoning=llm_analysis.get("reasoning"),
                db=db
            )
            
            # Determine if escalation needed
            requires_escalation = any(
                b.get("severity") == "high" or b.get("requires_provider")
                for b in barriers
            )
            
            return self.create_result(
                success=True,
                summary=llm_analysis.get("summary", f"Identified {len(barriers)} barriers"),
                data={
                    "barriers": barriers,
                    "interventions": interventions,
                    "priority_order": llm_analysis.get("priority_order", [])
                },
                recommendations=llm_analysis.get("recommendations", []),
                confidence=0.85,
                reasoning=llm_analysis.get("reasoning"),
                tools_used=["barrier_assessor", "intervention_generator"],
                requires_followup=len(barriers) > 0,
                requires_escalation=requires_escalation,
                next_agent_suggestion="planning" if any(
                    b.get("category") in ["forgetfulness", "complexity"] for b in barriers
                ) else None
            )
    
    def handle_cost_barrier(
        self, patient_id: int, medication_id: Optional[int] = None, medication_name: Optional[str] = None
    ) -> AgentResult:
        """
        Handle cost-related barriers
        
        Args:
            patient_id: Patient identifier
            medication_id: Optional medication ID
            medication_name: Optional medication name
            
        Returns:
            AgentResult with cost assistance options
        """
        with get_db_context() as db:
            # Get medications to check
            if medication_id:
                meds = [db.query(models.Medication).filter(
                    models.Medication.id == medication_id
                ).first()]
            elif medication_name:
                meds = db.query(models.Medication).filter(
                    models.Medication.patient_id == patient_id,
                    models.Medication.name.ilike(f"%{medication_name}%")
                ).all()
            else:
                meds = db.query(models.Medication).filter(
                    models.Medication.patient_id == patient_id,
                    models.Medication.is_active == True
                ).all()
            
            meds = [m for m in meds if m is not None]
            
            if not meds:
                return self.create_result(
                    success=True,
                    summary="No medications found to check for cost assistance",
                    confidence=0.7
                )
            
            cost_options = []
            
            for med in meds:
                options = self._find_cost_assistance(med, db)
                if options:
                    cost_options.append({
                        "medication": med.name,
                        "medication_id": med.id,
                        "options": options
                    })
            
            # Use LLM to summarize and prioritize
            llm_result = self._llm_summarize_cost_options(cost_options)
            
            # Save barrier resolution
            for option_set in cost_options:
                resolution = models.BarrierResolution(
                    patient_id=patient_id,
                    barrier_category=models.BarrierCategory.COST,
                    barrier_description=f"Cost barrier for {option_set['medication']}",
                    resolution_strategy=llm_result.get("primary_recommendation", ""),
                    resources_provided=option_set["options"],
                    status="active"
                )
                db.add(resolution)
            
            db.commit()
            
            self.log_activity(
                patient_id=patient_id,
                action="cost_assistance_lookup",
                activity_type="barrier_resolution",
                output_data={"options_found": len(cost_options)},
                db=db
            )
            
            return self.create_result(
                success=True,
                summary=llm_result.get("summary", f"Found cost assistance for {len(cost_options)} medication(s)"),
                data={
                    "cost_options": cost_options,
                    "estimated_savings": llm_result.get("estimated_savings"),
                    "primary_recommendation": llm_result.get("primary_recommendation")
                },
                recommendations=llm_result.get("recommendations", []),
                confidence=0.8,
                tools_used=["cost_assistance_finder", "rxnorm_lookup"],
                requires_followup=True
            )
    
    def handle_side_effect_barrier(
        self, patient_id: int, symptom_id: Optional[int] = None, medication_id: Optional[int] = None
    ) -> AgentResult:
        """
        Handle side effect barriers
        
        Args:
            patient_id: Patient identifier
            symptom_id: Optional symptom ID to address
            medication_id: Optional medication causing issues
            
        Returns:
            AgentResult with side effect management strategies
        """
        with get_db_context() as db:
            # Get relevant symptoms
            if symptom_id:
                symptoms = [db.query(models.SymptomReport).filter(
                    models.SymptomReport.id == symptom_id
                ).first()]
            else:
                symptoms = db.query(models.SymptomReport).filter(
                    models.SymptomReport.patient_id == patient_id,
                    models.SymptomReport.resolved == False
                ).order_by(models.SymptomReport.reported_at.desc()).limit(5).all()
            
            symptoms = [s for s in symptoms if s is not None]
            
            strategies = []
            
            for symptom in symptoms:
                strategy = self._generate_side_effect_strategy(symptom, db)
                strategies.append(strategy)
            
            # Get related medications
            medications = []
            for symptom in symptoms:
                if symptom.medication_name:
                    med = db.query(models.Medication).filter(
                        models.Medication.patient_id == patient_id,
                        models.Medication.name.ilike(f"%{symptom.medication_name}%")
                    ).first()
                    if med and med not in medications:
                        medications.append(med)
            
            # Use LLM for comprehensive analysis
            llm_result = self._llm_analyze_side_effects(symptoms, strategies, medications)
            
            # Save resolution
            if strategies:
                resolution = models.BarrierResolution(
                    patient_id=patient_id,
                    barrier_category=models.BarrierCategory.SIDE_EFFECTS,
                    barrier_description=f"Side effects from: {', '.join([s.medication_name or 'unknown' for s in symptoms])}",
                    resolution_strategy=llm_result.get("primary_strategy", ""),
                    status="active"
                )
                db.add(resolution)
                db.commit()
            
            # Check if escalation needed
            requires_escalation = any(
                s.get("requires_provider") or s.get("severity") == "high"
                for s in strategies
            )
            
            self.log_activity(
                patient_id=patient_id,
                action="side_effect_resolution",
                activity_type="barrier_resolution",
                output_data={"strategies_generated": len(strategies)},
                reasoning=llm_result.get("reasoning"),
                db=db
            )
            
            return self.create_result(
                success=True,
                summary=llm_result.get("summary", f"Generated {len(strategies)} strategies for side effect management"),
                data={
                    "symptoms": [{"symptom": s.symptom, "severity": s.severity} for s in symptoms],
                    "strategies": strategies,
                    "medications_affected": [m.name for m in medications]
                },
                recommendations=llm_result.get("recommendations", []),
                confidence=0.75,
                reasoning=llm_result.get("reasoning"),
                tools_used=["side_effect_analyzer", "medication_database"],
                requires_escalation=requires_escalation,
                next_agent_suggestion="liaison" if requires_escalation else None
            )
    
    def handle_forgetfulness_barrier(self, patient_id: int) -> AgentResult:
        """
        Handle forgetfulness barriers
        
        Args:
            patient_id: Patient identifier
            
        Returns:
            AgentResult with reminder and memory aid strategies
        """
        with get_db_context() as db:
            # Get patient context
            patient_context = self.get_patient_context(patient_id, db)
            
            if not patient_context:
                return self.create_result(
                    success=False,
                    summary="Patient not found",
                    confidence=0.0
                )
            
            # Analyze adherence patterns for forgetfulness indicators
            adherence_logs = db.query(models.AdherenceLog).filter(
                models.AdherenceLog.patient_id == patient_id,
                models.AdherenceLog.scheduled_time >= datetime.utcnow() - timedelta(days=14)
            ).all()
            
            # Identify forgetfulness patterns
            patterns = self._analyze_forgetfulness_patterns(adherence_logs)
            
            # Generate personalized strategies
            strategies = self._generate_forgetfulness_strategies(patient_context, patterns)
            
            # Use LLM to personalize recommendations
            llm_result = self._llm_personalize_reminder_strategy(
                patient_context, patterns, strategies
            )
            
            # Create intervention
            intervention = models.Intervention(
                patient_id=patient_id,
                intervention_type=models.InterventionType.REMINDER,
                description=llm_result.get("primary_strategy", "Enhanced reminder strategy"),
                strategy_details=llm_result.get("strategies", strategies),
                status="active"
            )
            db.add(intervention)
            
            # Save barrier resolution
            resolution = models.BarrierResolution(
                patient_id=patient_id,
                barrier_category=models.BarrierCategory.FORGETFULNESS,
                barrier_description="Forgetfulness-related adherence issues",
                resolution_strategy=llm_result.get("primary_strategy", ""),
                status="active"
            )
            db.add(resolution)
            db.commit()
            
            self.log_activity(
                patient_id=patient_id,
                action="forgetfulness_intervention",
                activity_type="barrier_resolution",
                output_data={"strategies": len(strategies)},
                db=db
            )
            
            return self.create_result(
                success=True,
                summary=llm_result.get("summary", "Generated personalized reminder strategies"),
                data={
                    "patterns": patterns,
                    "strategies": llm_result.get("strategies", strategies),
                    "intervention_id": intervention.id
                },
                recommendations=llm_result.get("recommendations", []),
                confidence=0.85,
                reasoning=llm_result.get("reasoning"),
                tools_used=["pattern_analyzer", "strategy_generator"],
                next_agent_suggestion="planning"
            )
    
    def handle_complexity_barrier(self, patient_id: int) -> AgentResult:
        """
        Handle regimen complexity barriers
        
        Args:
            patient_id: Patient identifier
            
        Returns:
            AgentResult with simplification strategies
        """
        with get_db_context() as db:
            # Get all active medications
            medications = db.query(models.Medication).filter(
                models.Medication.patient_id == patient_id,
                models.Medication.is_active == True
            ).all()
            
            # Get schedules
            schedules = db.query(models.MedicationSchedule).filter(
                models.MedicationSchedule.patient_id == patient_id,
                models.MedicationSchedule.is_active == True
            ).all()
            
            # Calculate complexity score
            complexity = self._calculate_complexity_score(medications, schedules)
            
            # Generate simplification strategies
            strategies = self._generate_simplification_strategies(
                medications, schedules, complexity
            )
            
            # Use LLM for recommendations
            llm_result = self._llm_simplify_regimen(
                medications, schedules, complexity, strategies
            )
            
            # Save resolution if needed
            if complexity["score"] > 5:  # High complexity
                resolution = models.BarrierResolution(
                    patient_id=patient_id,
                    barrier_category=models.BarrierCategory.COMPLEXITY,
                    barrier_description=f"Complex regimen: {complexity['score']}/10 complexity score",
                    resolution_strategy=llm_result.get("primary_strategy", ""),
                    status="active"
                )
                db.add(resolution)
                db.commit()
            
            self.log_activity(
                patient_id=patient_id,
                action="complexity_assessment",
                activity_type="barrier_resolution",
                output_data={"complexity_score": complexity["score"]},
                db=db
            )
            
            return self.create_result(
                success=True,
                summary=llm_result.get("summary", f"Regimen complexity: {complexity['level']}"),
                data={
                    "complexity": complexity,
                    "medication_count": len(medications),
                    "daily_doses": complexity.get("daily_doses", 0),
                    "simplification_strategies": llm_result.get("strategies", strategies)
                },
                recommendations=llm_result.get("recommendations", []),
                confidence=0.8,
                reasoning=llm_result.get("reasoning"),
                tools_used=["complexity_calculator", "simplification_engine"],
                next_agent_suggestion="planning" if complexity["score"] > 5 else None,
                requires_escalation=complexity.get("requires_provider_review", False)
            )
    
    def _assess_cost_barrier(self, patient_id: int, db: Session) -> Optional[Dict]:
        """Assess if cost is a barrier"""
        # Check for medications marked as cost concerns
        medications = db.query(models.Medication).filter(
            models.Medication.patient_id == patient_id,
            models.Medication.is_active == True
        ).all()
        
        # Check adherence logs for cost-related notes
        recent_logs = db.query(models.AdherenceLog).filter(
            models.AdherenceLog.patient_id == patient_id,
            models.AdherenceLog.scheduled_time >= datetime.utcnow() - timedelta(days=30)
        ).all()
        
        # Look for patterns suggesting cost issues (e.g., end of month drops)
        cost_indicators = 0
        
        # Check if adherence drops at end of month
        end_of_month_logs = [l for l in recent_logs if l.scheduled_time.day > 25]
        if end_of_month_logs:
            eom_rate = sum(1 for l in end_of_month_logs if l.taken) / len(end_of_month_logs)
            overall_rate = sum(1 for l in recent_logs if l.taken) / len(recent_logs) if recent_logs else 0
            if eom_rate < overall_rate - 0.15:
                cost_indicators += 1
        
        # Check for expensive medications
        expensive_meds = [m for m in medications if m.estimated_cost and m.estimated_cost > 50]
        if expensive_meds:
            cost_indicators += 1
        
        if cost_indicators > 0:
            return {
                "category": "cost",
                "severity": "high" if cost_indicators > 1 else "medium",
                "indicators": cost_indicators,
                "description": "Cost may be affecting medication adherence",
                "medications_affected": [m.name for m in expensive_meds]
            }
        
        return None
    
    def _assess_side_effect_barrier(self, patient_id: int, db: Session) -> Optional[Dict]:
        """Assess if side effects are a barrier"""
        symptoms = db.query(models.SymptomReport).filter(
            models.SymptomReport.patient_id == patient_id,
            models.SymptomReport.resolved == False,
            models.SymptomReport.reported_at >= datetime.utcnow() - timedelta(days=30)
        ).all()
        
        if symptoms:
            avg_severity = sum(s.severity for s in symptoms) / len(symptoms)
            return {
                "category": "side_effects",
                "severity": "high" if avg_severity >= 7 else "medium" if avg_severity >= 4 else "low",
                "symptom_count": len(symptoms),
                "avg_severity": round(avg_severity, 1),
                "description": f"{len(symptoms)} unresolved symptoms reported",
                "symptoms": [s.symptom for s in symptoms[:5]],
                "requires_provider": avg_severity >= 7
            }
        
        return None
    
    def _assess_forgetfulness_barrier(self, patient_id: int, db: Session) -> Optional[Dict]:
        """Assess if forgetfulness is a barrier"""
        logs = db.query(models.AdherenceLog).filter(
            models.AdherenceLog.patient_id == patient_id,
            models.AdherenceLog.scheduled_time >= datetime.utcnow() - timedelta(days=14)
        ).all()
        
        if not logs:
            return None
        
        # Count delayed doses
        delayed = sum(1 for l in logs if l.status == models.AdherenceStatus.DELAYED)
        missed = sum(1 for l in logs if l.status == models.AdherenceStatus.MISSED)
        
        forgetfulness_rate = (delayed + missed) / len(logs)
        
        if forgetfulness_rate > 0.2:
            return {
                "category": "forgetfulness",
                "severity": "high" if forgetfulness_rate > 0.4 else "medium",
                "forgetfulness_rate": round(forgetfulness_rate * 100, 1),
                "delayed_doses": delayed,
                "missed_doses": missed,
                "description": f"{forgetfulness_rate*100:.0f}% of doses delayed or missed"
            }
        
        return None
    
    def _assess_complexity_barrier(self, patient_id: int, db: Session) -> Optional[Dict]:
        """Assess if regimen complexity is a barrier"""
        medications = db.query(models.Medication).filter(
            models.Medication.patient_id == patient_id,
            models.Medication.is_active == True
        ).all()
        
        schedules = db.query(models.MedicationSchedule).filter(
            models.MedicationSchedule.patient_id == patient_id,
            models.MedicationSchedule.is_active == True
        ).all()
        
        complexity = self._calculate_complexity_score(medications, schedules)
        
        if complexity["score"] > 5:
            return {
                "category": "complexity",
                "severity": "high" if complexity["score"] > 7 else "medium",
                "complexity_score": complexity["score"],
                "medication_count": len(medications),
                "daily_doses": complexity.get("daily_doses", 0),
                "description": complexity["description"],
                "requires_provider": complexity["score"] > 8
            }
        
        return None
    
    def _assess_lifestyle_barrier(self, patient_id: int, db: Session) -> Optional[Dict]:
        """Assess if lifestyle factors are barriers"""
        patient = db.query(models.Patient).filter(
            models.Patient.id == patient_id
        ).first()
        
        if not patient:
            return None
        
        # Check adherence patterns against work hours
        logs = db.query(models.AdherenceLog).filter(
            models.AdherenceLog.patient_id == patient_id,
            models.AdherenceLog.scheduled_time >= datetime.utcnow() - timedelta(days=14)
        ).all()
        
        lifestyle_indicators = []
        
        # Check for work-hour issues
        if patient.work_schedule:
            if patient.work_schedule == "night_shift":
                lifestyle_indicators.append("Night shift may conflict with medication timing")
            elif patient.work_schedule == "variable":
                lifestyle_indicators.append("Variable schedule makes consistent timing difficult")
        
        # Check for travel-related issues
        if hasattr(patient, 'travel_frequency') and patient.travel_frequency == "frequent":
            lifestyle_indicators.append("Frequent travel may disrupt medication routine")
        
        if lifestyle_indicators:
            return {
                "category": "lifestyle",
                "severity": "medium",
                "indicators": lifestyle_indicators,
                "description": "Lifestyle factors may be affecting adherence"
            }
        
        return None
    
    def _find_cost_assistance(self, medication: models.Medication, db: Session) -> List[Dict]:
        """Find cost assistance options for a medication"""
        options = []
        
        # Check database for existing programs
        programs = db.query(models.CostAssistanceProgram).filter(
            models.CostAssistanceProgram.medication_name.ilike(f"%{medication.name}%")
        ).all()
        
        for program in programs:
            options.append({
                "type": "assistance_program",
                "name": program.program_name,
                "provider": program.provider,
                "eligibility": program.eligibility_criteria,
                "savings": program.estimated_savings,
                "url": program.application_url
            })
        
        # Generic alternatives
        options.append({
            "type": "generic",
            "name": f"Generic {medication.name}",
            "description": "Ask your pharmacist about generic alternatives",
            "potential_savings": "Up to 80% off brand price"
        })
        
        # Manufacturer coupons
        options.append({
            "type": "manufacturer_coupon",
            "name": f"{medication.name} manufacturer savings",
            "description": "Check manufacturer website for savings programs",
            "url": f"https://www.{medication.name.lower().replace(' ', '')}.com/savings"
        })
        
        # Pharmacy discount programs
        options.append({
            "type": "pharmacy_discount",
            "name": "GoodRx / RxSaver",
            "description": "Compare prices at local pharmacies",
            "url": f"https://www.goodrx.com/{medication.name.lower().replace(' ', '-')}"
        })
        
        return options
    
    def _generate_side_effect_strategy(self, symptom: models.SymptomReport, db: Session) -> Dict:
        """Generate strategy for managing a side effect"""
        strategy = {
            "symptom": symptom.symptom,
            "medication": symptom.medication_name,
            "severity": symptom.severity,
            "strategies": [],
            "requires_provider": symptom.severity >= 8
        }
        
        # Common side effect management strategies
        symptom_lower = symptom.symptom.lower()
        
        if "nausea" in symptom_lower or "stomach" in symptom_lower:
            strategy["strategies"].extend([
                "Take medication with food",
                "Take medication at bedtime",
                "Stay hydrated",
                "Avoid lying down immediately after taking"
            ])
        elif "dizz" in symptom_lower:
            strategy["strategies"].extend([
                "Rise slowly from sitting/lying positions",
                "Stay hydrated",
                "Take medication at bedtime if possible",
                "Avoid driving if symptoms persist"
            ])
        elif "headache" in symptom_lower:
            strategy["strategies"].extend([
                "Stay hydrated",
                "Take at consistent times",
                "Monitor blood pressure if applicable",
                "Use over-the-counter pain relief (consult pharmacist)"
            ])
        elif "fatigue" in symptom_lower or "tired" in symptom_lower:
            strategy["strategies"].extend([
                "Take medication at bedtime",
                "Maintain regular sleep schedule",
                "Light exercise may help",
                "Review timing with healthcare provider"
            ])
        else:
            strategy["strategies"].extend([
                "Monitor symptoms and keep a log",
                "Discuss with pharmacist for management tips",
                "Contact healthcare provider if symptoms persist"
            ])
        
        return strategy
    
    def _analyze_forgetfulness_patterns(self, logs: List) -> Dict:
        """Analyze patterns in forgetfulness"""
        patterns = {
            "worst_time": None,
            "worst_day": None,
            "consecutive_misses": 0,
            "pattern_type": "random"
        }
        
        if not logs:
            return patterns
        
        # Analyze by time of day
        time_misses = {"morning": 0, "afternoon": 0, "evening": 0, "night": 0}
        time_totals = {"morning": 0, "afternoon": 0, "evening": 0, "night": 0}
        
        for log in logs:
            hour = log.scheduled_time.hour
            if 6 <= hour < 12:
                slot = "morning"
            elif 12 <= hour < 18:
                slot = "afternoon"
            elif 18 <= hour < 22:
                slot = "evening"
            else:
                slot = "night"
            
            time_totals[slot] += 1
            if not log.taken:
                time_misses[slot] += 1
        
        # Find worst time slot
        worst_rate = 0
        for slot, total in time_totals.items():
            if total > 0:
                rate = time_misses[slot] / total
                if rate > worst_rate:
                    worst_rate = rate
                    patterns["worst_time"] = slot
        
        # Analyze by day of week
        day_misses = {i: 0 for i in range(7)}
        day_totals = {i: 0 for i in range(7)}
        
        for log in logs:
            day = log.scheduled_time.weekday()
            day_totals[day] += 1
            if not log.taken:
                day_misses[day] += 1
        
        worst_day_rate = 0
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        for day, total in day_totals.items():
            if total > 0:
                rate = day_misses[day] / total
                if rate > worst_day_rate:
                    worst_day_rate = rate
                    patterns["worst_day"] = day_names[day]
        
        # Count consecutive misses
        sorted_logs = sorted(logs, key=lambda x: x.scheduled_time)
        current_streak = 0
        for log in sorted_logs:
            if not log.taken:
                current_streak += 1
                patterns["consecutive_misses"] = max(patterns["consecutive_misses"], current_streak)
            else:
                current_streak = 0
        
        # Determine pattern type
        if patterns["worst_time"] and worst_rate > 0.4:
            patterns["pattern_type"] = f"time_specific_{patterns['worst_time']}"
        elif patterns["worst_day"] and worst_day_rate > 0.5:
            patterns["pattern_type"] = f"day_specific_{patterns['worst_day']}"
        
        return patterns
    
    def _generate_forgetfulness_strategies(self, patient_context: Dict, patterns: Dict) -> List[Dict]:
        """Generate strategies to address forgetfulness"""
        strategies = []
        
        # Basic reminder strategies
        strategies.append({
            "type": "reminder",
            "name": "Smart Phone Alerts",
            "description": "Set multiple phone alarms 5 minutes before each dose",
            "implementation": "Configure in AdherenceGuardian app settings"
        })
        
        strategies.append({
            "type": "visual_cue",
            "name": "Visual Placement",
            "description": "Keep medications visible near daily routine items (coffee maker, toothbrush)",
            "implementation": "Place pill organizer in high-traffic area"
        })
        
        strategies.append({
            "type": "habit_stacking",
            "name": "Habit Stacking",
            "description": "Link medication taking to existing habits (meals, brushing teeth)",
            "implementation": "Take morning meds with breakfast, evening meds with dinner"
        })
        
        # Pattern-specific strategies
        if patterns.get("worst_time") == "morning":
            strategies.append({
                "type": "timing_adjustment",
                "name": "Morning Routine Integration",
                "description": "Place medications next to coffee maker or breakfast items",
                "implementation": "Set nightstand alarm as backup"
            })
        elif patterns.get("worst_time") == "evening":
            strategies.append({
                "type": "timing_adjustment",
                "name": "Evening Routine Integration",
                "description": "Set dinner table reminder or link to TV watching",
                "implementation": "Consider moving doses to earlier if possible"
            })
        
        if patterns.get("worst_day") in ["Saturday", "Sunday"]:
            strategies.append({
                "type": "weekend_specific",
                "name": "Weekend Reminder System",
                "description": "Extra reminders on weekends when routine changes",
                "implementation": "Enable enhanced weekend notifications"
            })
        
        strategies.append({
            "type": "pill_organizer",
            "name": "Weekly Pill Organizer",
            "description": "Use a weekly pill organizer to track doses",
            "implementation": "Fill weekly on same day each week"
        })
        
        return strategies
    
    def _calculate_complexity_score(self, medications: List, schedules: List) -> Dict:
        """Calculate regimen complexity score"""
        score = 0
        
        # Number of medications (0-3 points)
        med_count = len(medications)
        if med_count <= 2:
            score += 1
        elif med_count <= 5:
            score += 2
        else:
            score += 3
        
        # Daily dose frequency (0-3 points)
        daily_doses = len(set(s.scheduled_time.strftime("%H:%M") for s in schedules if s.frequency == "daily"))
        if daily_doses <= 1:
            score += 1
        elif daily_doses <= 3:
            score += 2
        else:
            score += 3
        
        # Food/timing restrictions (0-2 points)
        restrictions = sum(1 for m in medications if m.food_requirements or m.special_instructions)
        if restrictions > 2:
            score += 2
        elif restrictions > 0:
            score += 1
        
        # Drug interactions (0-2 points)
        # Would check interactions database here
        
        return {
            "score": min(score, 10),
            "level": "high" if score > 7 else "medium" if score > 4 else "low",
            "medication_count": med_count,
            "daily_doses": daily_doses,
            "restrictions": restrictions,
            "description": f"{med_count} medications, {daily_doses} dose times daily",
            "requires_provider_review": score > 8
        }
    
    def _generate_simplification_strategies(self, medications: List, schedules: List, complexity: Dict) -> List[Dict]:
        """Generate strategies to simplify regimen"""
        strategies = []
        
        if complexity["daily_doses"] > 2:
            strategies.append({
                "type": "consolidation",
                "name": "Dose Consolidation",
                "description": "Ask provider about combining dose times where medically appropriate",
                "requires_provider": True
            })
        
        if complexity["medication_count"] > 5:
            strategies.append({
                "type": "combination",
                "name": "Combination Medications",
                "description": "Ask about combination pills that contain multiple medications",
                "requires_provider": True
            })
        
        strategies.append({
            "type": "organization",
            "name": "Pill Organization System",
            "description": "Use AM/PM pill organizers sorted weekly",
            "requires_provider": False
        })
        
        strategies.append({
            "type": "synchronization",
            "name": "Refill Synchronization",
            "description": "Ask pharmacy to sync all medication refills to same date",
            "requires_provider": False
        })
        
        return strategies
    
    def _generate_interventions(self, barriers: List[Dict], patient_id: int, db: Session) -> List[Dict]:
        """Generate interventions for identified barriers"""
        interventions = []
        
        for barrier in barriers:
            category = barrier.get("category")
            
            if category == "cost":
                interventions.append({
                    "barrier": "cost",
                    "intervention_type": "financial_assistance",
                    "action": "Search for cost assistance programs",
                    "priority": "high"
                })
            elif category == "side_effects":
                interventions.append({
                    "barrier": "side_effects",
                    "intervention_type": "symptom_management",
                    "action": "Review symptom management strategies",
                    "priority": "high" if barrier.get("severity") == "high" else "medium"
                })
            elif category == "forgetfulness":
                interventions.append({
                    "barrier": "forgetfulness",
                    "intervention_type": "reminder_enhancement",
                    "action": "Implement enhanced reminder system",
                    "priority": "medium"
                })
            elif category == "complexity":
                interventions.append({
                    "barrier": "complexity",
                    "intervention_type": "regimen_review",
                    "action": "Schedule medication review with provider",
                    "priority": "medium"
                })
        
        return interventions
    
    def _llm_prioritize_barriers(self, barriers: List[Dict], patient_context: Dict) -> Dict:
        """Use LLM to prioritize barriers and generate strategy"""
        if not barriers:
            return {
                "summary": "No significant barriers identified",
                "recommendations": ["Continue current adherence strategies"],
                "priority_order": []
            }
        
        barriers_text = "\n".join([
            f"- {b['category']}: {b['description']} (severity: {b.get('severity', 'unknown')})"
            for b in barriers
        ])
        
        prompt = f"""Prioritize these medication adherence barriers and recommend strategies:

Patient Context:
- Age: {patient_context.get('patient', {}).get('age', 'Unknown')}
- Medications: {len(patient_context.get('medications', []))}
- Work Schedule: {patient_context.get('patient', {}).get('work_schedule', 'Unknown')}

Identified Barriers:
{barriers_text}

Provide:
1. Brief summary (2-3 sentences)
2. Priority order for addressing barriers
3. Top 3 actionable recommendations

Format as JSON:
{{
    "summary": "...",
    "priority_order": ["barrier1", "barrier2", ...],
    "recommendations": ["...", "...", "..."],
    "reasoning": "..."
}}"""
        
        response = self.call_llm(prompt, system_prompt=self.get_system_prompt())
        return self.parse_json_response(response, {
            "summary": f"Identified {len(barriers)} barriers to address",
            "recommendations": [],
            "priority_order": [b["category"] for b in barriers],
            "reasoning": ""
        })
    
    def _llm_summarize_cost_options(self, cost_options: List[Dict]) -> Dict:
        """Use LLM to summarize cost assistance options"""
        if not cost_options:
            return {"summary": "No cost assistance options found"}
        
        options_text = "\n".join([
            f"Medication: {opt['medication']}\nOptions: {', '.join([o['name'] for o in opt['options']])}"
            for opt in cost_options
        ])
        
        prompt = f"""Summarize these medication cost assistance options:

{options_text}

Provide:
1. Brief summary
2. Primary recommendation
3. Estimated potential savings
4. Next steps

Format as JSON:
{{
    "summary": "...",
    "primary_recommendation": "...",
    "estimated_savings": "...",
    "recommendations": ["...", "..."]
}}"""
        
        response = self.call_llm(prompt, system_prompt=self.get_system_prompt())
        return self.parse_json_response(response, {
            "summary": f"Found cost options for {len(cost_options)} medication(s)",
            "recommendations": []
        })
    
    def _llm_analyze_side_effects(self, symptoms: List, strategies: List, medications: List) -> Dict:
        """Use LLM to analyze side effects"""
        symptoms_text = "\n".join([
            f"- {s.symptom} (severity: {s.severity}/10, medication: {s.medication_name or 'unknown'})"
            for s in symptoms
        ])
        
        prompt = f"""Analyze these medication side effects and strategies:

Symptoms:
{symptoms_text}

Medications involved: {', '.join([m.name for m in medications]) if medications else 'Unknown'}

Provide:
1. Summary of the situation
2. Primary management strategy
3. Recommendations
4. Whether provider consultation is needed

Format as JSON:
{{
    "summary": "...",
    "primary_strategy": "...",
    "recommendations": ["...", "..."],
    "requires_provider_consultation": false,
    "reasoning": "..."
}}"""
        
        response = self.call_llm(prompt, system_prompt=self.get_system_prompt())
        return self.parse_json_response(response, {
            "summary": f"Analyzed {len(symptoms)} symptom(s)",
            "recommendations": []
        })
    
    def _llm_personalize_reminder_strategy(self, patient_context: Dict, patterns: Dict, strategies: List) -> Dict:
        """Use LLM to personalize reminder strategies"""
        prompt = f"""Personalize reminder strategies for this patient:

Patient Info:
- Work schedule: {patient_context.get('patient', {}).get('work_schedule', 'Unknown')}
- Lifestyle preferences: {patient_context.get('patient', {}).get('lifestyle_preferences', {})}

Forgetfulness Patterns:
- Worst time: {patterns.get('worst_time', 'Unknown')}
- Worst day: {patterns.get('worst_day', 'Unknown')}
- Pattern type: {patterns.get('pattern_type', 'random')}

Available Strategies:
{chr(10).join([f"- {s['name']}: {s['description']}" for s in strategies])}

Provide:
1. Summary of approach
2. Primary strategy
3. Personalized recommendations
4. Implementation steps

Format as JSON:
{{
    "summary": "...",
    "primary_strategy": "...",
    "strategies": [...],
    "recommendations": ["...", "..."],
    "reasoning": "..."
}}"""
        
        response = self.call_llm(prompt, system_prompt=self.get_system_prompt())
        return self.parse_json_response(response, {
            "summary": "Generated personalized reminder strategy",
            "strategies": strategies,
            "recommendations": []
        })
    
    def _llm_simplify_regimen(self, medications: List, schedules: List, complexity: Dict, strategies: List) -> Dict:
        """Use LLM to provide regimen simplification advice"""
        prompt = f"""Provide regimen simplification advice:

Current Regimen:
- Medications: {len(medications)}
- Daily dose times: {complexity.get('daily_doses', 0)}
- Complexity score: {complexity.get('score', 0)}/10

Available Strategies:
{chr(10).join([f"- {s['name']}: {s['description']}" for s in strategies])}

Provide:
1. Summary assessment
2. Primary simplification strategy
3. Actionable recommendations

Format as JSON:
{{
    "summary": "...",
    "primary_strategy": "...",
    "strategies": [...],
    "recommendations": ["...", "..."],
    "reasoning": "..."
}}"""
        
        response = self.call_llm(prompt, system_prompt=self.get_system_prompt())
        return self.parse_json_response(response, {
            "summary": f"Regimen complexity: {complexity.get('level', 'unknown')}",
            "strategies": strategies,
            "recommendations": []
        })
    
    def get_system_prompt(self) -> str:
        """Get barrier resolution-specific system prompt from prompts module"""
        return BARRIER_SYSTEM_PROMPT
