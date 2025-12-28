"""
Monitoring Agent
Tracks adherence patterns, detects anomalies, and analyzes symptoms
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging

from sqlalchemy.orm import Session

from config import agent_config
from database import get_db_context
import models
from agents.base_agent import BaseAgent
from agents.state import AgentState, AgentResult, AdherenceData, SymptomInfo
from agents.prompts import (
    MONITORING_SYSTEM_PROMPT,
    ADHERENCE_ANALYSIS_PROMPT,
    PATTERN_ANALYSIS_PROMPT,
    SYMPTOM_ANALYSIS_PROMPT,
    SINGLE_SYMPTOM_ANALYSIS_PROMPT,
    COMMON_SIDE_EFFECTS
)


logger = logging.getLogger(__name__)


class MonitoringAgent(BaseAgent):
    """
    Agent responsible for:
    - Tracking daily adherence rates and trends
    - Detecting anomalies (missed doses, irregular patterns)
    - Identifying potential side effects from symptom reports
    - Adapting reminder strategies based on response data
    - Learning optimal intervention timing
    """
    
    agent_name = "Monitoring Agent"
    agent_type = "monitoring"
    description = "Monitors medication adherence patterns, detects anomalies, and analyzes symptoms for potential side effects"
    
    def __init__(self):
        super().__init__()
        
        # Configuration
        self.adherence_target = agent_config.MONITORING_ADHERENCE_TARGET
        self.anomaly_threshold = agent_config.MONITORING_ANOMALY_THRESHOLD
        self.monitoring_window_days = agent_config.MONITORING_WINDOW_DAYS
    
    def process(self, state: AgentState) -> AgentState:
        """Main processing method called by orchestrator"""
        task = state["current_task"].lower()
        patient_id = state["patient_id"]
        context = state.get("context", {})
        
        try:
            if "symptom" in task or "side effect" in task:
                result = self.analyze_symptom(
                    patient_id,
                    context.get("symptom_id")
                )
            elif "pattern" in task or "trend" in task:
                result = self.analyze_adherence_patterns(patient_id)
            elif "anomal" in task or "issue" in task:
                result = self.detect_anomalies(patient_id)
            else:
                # Default: general adherence analysis
                result = self.analyze_adherence(patient_id)
            
            state["agent_results"]["monitoring"] = result.model_dump()
            state["context"]["monitoring_result"] = result.model_dump()
            
            # Check if escalation needed
            if result.requires_escalation:
                state["requires_escalation"] = True
            
            # Suggest next agent if needed
            if result.next_agent_suggestion:
                state["next_agent"] = result.next_agent_suggestion
            
        except Exception as e:
            logger.error(f"Monitoring agent error: {e}")
            state["error"] = str(e)
            state["agent_results"]["monitoring"] = self.create_result(
                success=False,
                summary=f"Error during monitoring: {str(e)}",
                confidence=0.0
            ).model_dump()
        
        return state
    
    def analyze_adherence(self, patient_id: int, days: int = None) -> AgentResult:
        """
        Analyze overall adherence for a patient
        
        Args:
            patient_id: Patient identifier
            days: Number of days to analyze (default from config)
            
        Returns:
            AgentResult with adherence analysis
        """
        days = days or self.monitoring_window_days
        
        with get_db_context() as db:
            # Get adherence logs
            start_date = datetime.utcnow() - timedelta(days=days)
            
            logs = db.query(models.AdherenceLog).filter(
                models.AdherenceLog.patient_id == patient_id,
                models.AdherenceLog.scheduled_time >= start_date
            ).all()
            
            if not logs:
                return self.create_result(
                    success=True,
                    summary="No adherence data found for the specified period",
                    data={"has_data": False},
                    confidence=0.5
                )
            
            # Calculate metrics
            total = len(logs)
            taken = sum(1 for l in logs if l.taken)
            missed = sum(1 for l in logs if l.status == models.AdherenceStatus.MISSED)
            delayed = sum(1 for l in logs if l.status == models.AdherenceStatus.DELAYED)
            
            adherence_rate = taken / total if total > 0 else 0
            target_met = adherence_rate >= self.adherence_target
            
            # Calculate trend
            trend = self._calculate_trend(logs)
            
            # Detect patterns
            patterns = self._detect_patterns(logs)
            
            # Generate insights
            insights = self._generate_adherence_insights(
                adherence_rate, trend, patterns, target_met
            )
            
            # Use LLM for deeper analysis
            llm_analysis = self._llm_analyze_adherence(
                adherence_rate, trend, patterns, insights
            )
            
            # Log activity
            self.log_activity(
                patient_id=patient_id,
                action="adherence_analysis",
                activity_type="monitoring",
                input_data={"days": days},
                output_data={
                    "adherence_rate": adherence_rate,
                    "trend": trend,
                    "target_met": target_met
                },
                reasoning=llm_analysis.get("reasoning"),
                db=db
            )
            
            # Determine if barrier agent needed
            requires_barrier = adherence_rate < 0.7 or "declining" in trend
            
            return self.create_result(
                success=True,
                summary=llm_analysis.get("summary", f"Adherence rate: {adherence_rate*100:.1f}%"),
                data={
                    "adherence_rate": round(adherence_rate * 100, 2),
                    "total_doses": total,
                    "taken": taken,
                    "missed": missed,
                    "delayed": delayed,
                    "trend": trend,
                    "patterns": patterns,
                    "target_met": target_met,
                    "target": self.adherence_target * 100
                },
                recommendations=llm_analysis.get("recommendations", []),
                confidence=0.85,
                reasoning=llm_analysis.get("reasoning"),
                tools_used=["adherence_analyzer", "pattern_detector"],
                requires_followup=not target_met,
                next_agent_suggestion="barrier" if requires_barrier else None
            )
    
    def analyze_adherence_patterns(self, patient_id: int) -> AgentResult:
        """
        Analyze adherence patterns to identify issues
        
        Args:
            patient_id: Patient identifier
            
        Returns:
            AgentResult with pattern analysis
        """
        with get_db_context() as db:
            # Get 30 days of logs for pattern analysis
            start_date = datetime.utcnow() - timedelta(days=30)
            
            logs = db.query(models.AdherenceLog).filter(
                models.AdherenceLog.patient_id == patient_id,
                models.AdherenceLog.scheduled_time >= start_date
            ).order_by(models.AdherenceLog.scheduled_time).all()
            
            if len(logs) < 7:
                return self.create_result(
                    success=True,
                    summary="Insufficient data for pattern analysis (need at least 7 days)",
                    data={"has_sufficient_data": False},
                    confidence=0.3
                )
            
            # Analyze by day of week
            day_patterns = self._analyze_by_day_of_week(logs)
            
            # Analyze by time of day
            time_patterns = self._analyze_by_time_of_day(logs)
            
            # Analyze by medication
            med_patterns = self._analyze_by_medication(logs, db)
            
            # Identify problematic patterns
            issues = []
            
            # Check for weekend drops
            weekday_rate = day_patterns.get("weekday_rate", 0)
            weekend_rate = day_patterns.get("weekend_rate", 0)
            if weekend_rate < weekday_rate - 0.15:
                issues.append({
                    "type": "weekend_drop",
                    "description": f"Adherence drops on weekends ({weekend_rate*100:.0f}% vs {weekday_rate*100:.0f}% on weekdays)",
                    "severity": "medium"
                })
            
            # Check for time-specific issues
            for time_slot, data in time_patterns.items():
                if data["rate"] < 0.7:
                    issues.append({
                        "type": "time_slot_issue",
                        "description": f"Low adherence for {time_slot} doses ({data['rate']*100:.0f}%)",
                        "severity": "medium"
                    })
            
            # Use LLM to generate insights
            analysis = self._llm_analyze_patterns(
                day_patterns, time_patterns, med_patterns, issues
            )
            
            self.log_activity(
                patient_id=patient_id,
                action="pattern_analysis",
                activity_type="monitoring",
                output_data={"issues_found": len(issues)},
                reasoning=analysis.get("reasoning"),
                db=db
            )
            
            return self.create_result(
                success=True,
                summary=analysis.get("summary", f"Found {len(issues)} adherence patterns to address"),
                data={
                    "day_patterns": day_patterns,
                    "time_patterns": time_patterns,
                    "medication_patterns": med_patterns,
                    "issues": issues
                },
                recommendations=analysis.get("recommendations", []),
                confidence=0.8,
                reasoning=analysis.get("reasoning"),
                tools_used=["pattern_analyzer"],
                requires_followup=len(issues) > 0,
                next_agent_suggestion="planning" if any(i["type"] == "time_slot_issue" for i in issues) else None
            )
    
    def detect_anomalies(self, patient_id: int) -> AgentResult:
        """
        Detect anomalies in adherence data
        
        Args:
            patient_id: Patient identifier
            
        Returns:
            AgentResult with detected anomalies
        """
        with get_db_context() as db:
            # Compare recent adherence to historical
            recent_start = datetime.utcnow() - timedelta(days=7)
            historical_start = datetime.utcnow() - timedelta(days=30)
            
            recent_logs = db.query(models.AdherenceLog).filter(
                models.AdherenceLog.patient_id == patient_id,
                models.AdherenceLog.scheduled_time >= recent_start
            ).all()
            
            historical_logs = db.query(models.AdherenceLog).filter(
                models.AdherenceLog.patient_id == patient_id,
                models.AdherenceLog.scheduled_time >= historical_start,
                models.AdherenceLog.scheduled_time < recent_start
            ).all()
            
            anomalies = []
            
            if recent_logs and historical_logs:
                recent_rate = sum(1 for l in recent_logs if l.taken) / len(recent_logs)
                historical_rate = sum(1 for l in historical_logs if l.taken) / len(historical_logs)
                
                # Check for significant drop
                drop = historical_rate - recent_rate
                if drop > self.anomaly_threshold:
                    anomalies.append({
                        "type": "adherence_drop",
                        "severity": "high" if drop > 0.25 else "medium",
                        "description": f"Adherence dropped from {historical_rate*100:.0f}% to {recent_rate*100:.0f}%",
                        "change": round(drop * 100, 1),
                        "detected_at": datetime.utcnow().isoformat()
                    })
            
            # Check for consecutive missed doses
            sorted_logs = sorted(recent_logs, key=lambda x: x.scheduled_time)
            consecutive_missed = 0
            max_consecutive = 0
            
            for log in sorted_logs:
                if not log.taken:
                    consecutive_missed += 1
                    max_consecutive = max(max_consecutive, consecutive_missed)
                else:
                    consecutive_missed = 0
            
            if max_consecutive >= 3:
                anomalies.append({
                    "type": "consecutive_misses",
                    "severity": "high",
                    "description": f"Detected {max_consecutive} consecutive missed doses",
                    "count": max_consecutive
                })
            
            # Check for new symptoms that correlate with timing
            recent_symptoms = db.query(models.SymptomReport).filter(
                models.SymptomReport.patient_id == patient_id,
                models.SymptomReport.reported_at >= recent_start
            ).all()
            
            if recent_symptoms and any(not l.taken for l in recent_logs):
                anomalies.append({
                    "type": "symptom_correlation",
                    "severity": "medium",
                    "description": f"New symptoms reported ({len(recent_symptoms)}) may be affecting adherence",
                    "symptoms_count": len(recent_symptoms)
                })
            
            # Determine if escalation needed
            requires_escalation = any(a["severity"] == "high" for a in anomalies)
            
            self.log_activity(
                patient_id=patient_id,
                action="anomaly_detection",
                activity_type="monitoring",
                output_data={"anomalies_found": len(anomalies)},
                db=db
            )
            
            return self.create_result(
                success=True,
                summary=f"Detected {len(anomalies)} anomalies" if anomalies else "No significant anomalies detected",
                data={
                    "anomalies": anomalies,
                    "recent_adherence": round(sum(1 for l in recent_logs if l.taken) / len(recent_logs) * 100, 1) if recent_logs else None
                },
                recommendations=self._generate_anomaly_recommendations(anomalies),
                confidence=0.85,
                tools_used=["anomaly_detector"],
                requires_followup=len(anomalies) > 0,
                requires_escalation=requires_escalation,
                next_agent_suggestion="barrier" if anomalies else None
            )
    
    def analyze_symptom(self, patient_id: int, symptom_id: Optional[int] = None) -> AgentResult:
        """
        Analyze a symptom report for potential medication correlation
        
        Args:
            patient_id: Patient identifier
            symptom_id: Optional specific symptom to analyze
            
        Returns:
            AgentResult with symptom analysis
        """
        with get_db_context() as db:
            # Get symptom(s) to analyze
            if symptom_id:
                symptoms = [db.query(models.SymptomReport).filter(
                    models.SymptomReport.id == symptom_id
                ).first()]
            else:
                # Get recent unanalyzed symptoms
                symptoms = db.query(models.SymptomReport).filter(
                    models.SymptomReport.patient_id == patient_id,
                    models.SymptomReport.analyzed == False
                ).all()
            
            symptoms = [s for s in symptoms if s is not None]
            
            if not symptoms:
                return self.create_result(
                    success=True,
                    summary="No symptoms to analyze",
                    data={"symptoms_analyzed": 0},
                    confidence=0.9
                )
            
            # Analyze each symptom
            analyses = []
            escalate = False
            
            for symptom in symptoms:
                analysis = self._analyze_single_symptom(symptom, db)
                analyses.append(analysis)
                
                # Update symptom record
                symptom.analyzed = True
                symptom.analysis_result = analysis
                symptom.correlation_score = analysis.get("correlation_score", 0)
                
                # Check if escalation needed
                if symptom.severity >= 8 or analysis.get("requires_medical_attention"):
                    symptom.escalated = True
                    symptom.escalated_to_provider = True
                    escalate = True
                
                db.commit()
            
            # Use LLM for comprehensive analysis
            llm_analysis = self._llm_analyze_symptoms(analyses)
            
            self.log_activity(
                patient_id=patient_id,
                action="symptom_analysis",
                activity_type="monitoring",
                input_data={"symptom_ids": [s.id for s in symptoms]},
                output_data={"escalated": escalate},
                reasoning=llm_analysis.get("reasoning"),
                db=db
            )
            
            return self.create_result(
                success=True,
                summary=llm_analysis.get("summary", f"Analyzed {len(symptoms)} symptom(s)"),
                data={
                    "symptoms_analyzed": len(symptoms),
                    "analyses": analyses,
                    "escalated": escalate
                },
                recommendations=llm_analysis.get("recommendations", []),
                confidence=0.8,
                reasoning=llm_analysis.get("reasoning"),
                tools_used=["symptom_analyzer", "medication_correlator"],
                requires_escalation=escalate,
                next_agent_suggestion="barrier" if any(a.get("is_side_effect") for a in analyses) else (
                    "liaison" if escalate else None
                )
            )
    
    def get_symptom_analysis(self, symptom_id: int) -> Dict:
        """
        Get analysis for a specific symptom (called from API)
        
        Args:
            symptom_id: Symptom identifier
            
        Returns:
            Analysis dict
        """
        with get_db_context() as db:
            symptom = db.query(models.SymptomReport).filter(
                models.SymptomReport.id == symptom_id
            ).first()
            
            if not symptom:
                return {"error": "Symptom not found"}
            
            if not symptom.analyzed:
                # Analyze now
                analysis = self._analyze_single_symptom(symptom, db)
                symptom.analyzed = True
                symptom.analysis_result = analysis
                symptom.correlation_score = analysis.get("correlation_score", 0)
                db.commit()
            
            return {
                "symptom_id": symptom.id,
                "symptom": symptom.symptom,
                "severity": symptom.severity,
                "medication": symptom.medication_name,
                "analysis": symptom.analysis_result,
                "correlation_score": symptom.correlation_score,
                "escalated": symptom.escalated,
                "recommendations": symptom.analysis_result.get("recommendations", []) if symptom.analysis_result else []
            }
    
    def _calculate_trend(self, logs: List) -> str:
        """Calculate adherence trend"""
        if len(logs) < 7:
            return "insufficient_data"
        
        sorted_logs = sorted(logs, key=lambda x: x.scheduled_time)
        mid = len(sorted_logs) // 2
        
        first_half = sorted_logs[:mid]
        second_half = sorted_logs[mid:]
        
        first_rate = sum(1 for l in first_half if l.taken) / len(first_half)
        second_rate = sum(1 for l in second_half if l.taken) / len(second_half)
        
        diff = second_rate - first_rate
        
        if diff > 0.1:
            return "improving"
        elif diff < -0.1:
            return "declining"
        else:
            return "stable"
    
    def _detect_patterns(self, logs: List) -> Dict:
        """Detect adherence patterns"""
        patterns = {
            "morning_adherence": 0,
            "evening_adherence": 0,
            "weekday_adherence": 0,
            "weekend_adherence": 0
        }
        
        morning_logs = [l for l in logs if l.scheduled_time.hour < 12]
        evening_logs = [l for l in logs if l.scheduled_time.hour >= 12]
        weekday_logs = [l for l in logs if l.scheduled_time.weekday() < 5]
        weekend_logs = [l for l in logs if l.scheduled_time.weekday() >= 5]
        
        if morning_logs:
            patterns["morning_adherence"] = sum(1 for l in morning_logs if l.taken) / len(morning_logs)
        if evening_logs:
            patterns["evening_adherence"] = sum(1 for l in evening_logs if l.taken) / len(evening_logs)
        if weekday_logs:
            patterns["weekday_adherence"] = sum(1 for l in weekday_logs if l.taken) / len(weekday_logs)
        if weekend_logs:
            patterns["weekend_adherence"] = sum(1 for l in weekend_logs if l.taken) / len(weekend_logs)
        
        return patterns
    
    def _analyze_by_day_of_week(self, logs: List) -> Dict:
        """Analyze adherence by day of week"""
        days = {i: {"total": 0, "taken": 0} for i in range(7)}
        
        for log in logs:
            day = log.scheduled_time.weekday()
            days[day]["total"] += 1
            if log.taken:
                days[day]["taken"] += 1
        
        day_rates = {
            i: d["taken"] / d["total"] if d["total"] > 0 else 0
            for i, d in days.items()
        }
        
        weekday_total = sum(days[i]["total"] for i in range(5))
        weekday_taken = sum(days[i]["taken"] for i in range(5))
        weekend_total = sum(days[i]["total"] for i in range(5, 7))
        weekend_taken = sum(days[i]["taken"] for i in range(5, 7))
        
        return {
            "by_day": day_rates,
            "weekday_rate": weekday_taken / weekday_total if weekday_total > 0 else 0,
            "weekend_rate": weekend_taken / weekend_total if weekend_total > 0 else 0
        }
    
    def _analyze_by_time_of_day(self, logs: List) -> Dict:
        """Analyze adherence by time of day"""
        time_slots = {
            "morning": {"start": 6, "end": 12, "total": 0, "taken": 0},
            "afternoon": {"start": 12, "end": 18, "total": 0, "taken": 0},
            "evening": {"start": 18, "end": 22, "total": 0, "taken": 0},
            "night": {"start": 22, "end": 6, "total": 0, "taken": 0}
        }
        
        for log in logs:
            hour = log.scheduled_time.hour
            for slot, data in time_slots.items():
                if slot == "night":
                    if hour >= 22 or hour < 6:
                        data["total"] += 1
                        if log.taken:
                            data["taken"] += 1
                        break
                elif data["start"] <= hour < data["end"]:
                    data["total"] += 1
                    if log.taken:
                        data["taken"] += 1
                    break
        
        return {
            slot: {
                "rate": data["taken"] / data["total"] if data["total"] > 0 else 0,
                "total": data["total"]
            }
            for slot, data in time_slots.items()
        }
    
    def _analyze_by_medication(self, logs: List, db: Session) -> Dict:
        """Analyze adherence by medication"""
        med_stats = {}
        
        for log in logs:
            med_id = log.medication_id
            if med_id not in med_stats:
                med = db.query(models.Medication).filter(
                    models.Medication.id == med_id
                ).first()
                med_stats[med_id] = {
                    "name": med.name if med else "Unknown",
                    "total": 0,
                    "taken": 0
                }
            
            med_stats[med_id]["total"] += 1
            if log.taken:
                med_stats[med_id]["taken"] += 1
        
        return {
            mid: {
                "name": data["name"],
                "rate": data["taken"] / data["total"] if data["total"] > 0 else 0,
                "total": data["total"]
            }
            for mid, data in med_stats.items()
        }
    
    def _analyze_single_symptom(self, symptom: models.SymptomReport, db: Session) -> Dict:
        """Analyze a single symptom for medication correlation"""
        analysis = {
            "symptom": symptom.symptom,
            "severity": symptom.severity,
            "medication": symptom.medication_name,
            "correlation_score": 0.0,
            "is_side_effect": False,
            "requires_medical_attention": False,
            "recommendations": []
        }
        
        # Check severity
        if symptom.severity >= 8:
            analysis["requires_medical_attention"] = True
            analysis["recommendations"].append("Contact your healthcare provider due to high severity")
        
        # Common side effects database (simplified)
        common_side_effects = {
            "metformin": ["nausea", "diarrhea", "stomach upset", "loss of appetite"],
            "lisinopril": ["dry cough", "dizziness", "headache", "fatigue"],
            "atorvastatin": ["muscle pain", "joint pain", "nausea", "diarrhea"],
            "amlodipine": ["swelling", "edema", "dizziness", "flushing"],
            "omeprazole": ["headache", "nausea", "diarrhea", "stomach pain"]
        }
        
        # Check if symptom matches known side effects
        if symptom.medication_name:
            med_lower = symptom.medication_name.lower()
            symptom_lower = symptom.symptom.lower()
            
            for drug, effects in common_side_effects.items():
                if drug in med_lower:
                    for effect in effects:
                        if effect in symptom_lower:
                            analysis["is_side_effect"] = True
                            analysis["correlation_score"] = 0.8
                            analysis["recommendations"].append(
                                f"This symptom is a known side effect of {symptom.medication_name}. "
                                "Consider taking with food if GI-related, or consult your doctor if persistent."
                            )
                            break
        
        # Use LLM for deeper analysis
        llm_result = self._llm_analyze_single_symptom(symptom, analysis)
        analysis.update(llm_result)
        
        return analysis
    
    def _generate_adherence_insights(
        self, adherence_rate: float, trend: str, patterns: Dict, target_met: bool
    ) -> List[Dict]:
        """Generate insights from adherence data"""
        insights = []
        
        if not target_met:
            insights.append({
                "type": "warning",
                "title": "Below Target",
                "message": f"Adherence is {adherence_rate*100:.0f}%, below the {self.adherence_target*100:.0f}% target"
            })
        
        if trend == "declining":
            insights.append({
                "type": "alert",
                "title": "Declining Trend",
                "message": "Adherence has been declining recently. Let's identify what's causing this."
            })
        elif trend == "improving":
            insights.append({
                "type": "positive",
                "title": "Improving!",
                "message": "Great progress! Your adherence has been improving."
            })
        
        # Pattern-based insights
        if patterns.get("weekend_adherence", 0) < patterns.get("weekday_adherence", 0) - 0.15:
            insights.append({
                "type": "info",
                "title": "Weekend Challenge",
                "message": "Adherence tends to drop on weekends. Consider setting special weekend reminders."
            })
        
        return insights
    
    def _generate_anomaly_recommendations(self, anomalies: List[Dict]) -> List[str]:
        """Generate recommendations based on detected anomalies"""
        recommendations = []
        
        for anomaly in anomalies:
            if anomaly["type"] == "adherence_drop":
                recommendations.append(
                    "Schedule a review with your healthcare provider to discuss recent adherence challenges"
                )
            elif anomaly["type"] == "consecutive_misses":
                recommendations.append(
                    "Set up multiple reminders at different times to help remember doses"
                )
            elif anomaly["type"] == "symptom_correlation":
                recommendations.append(
                    "Report your symptoms to your healthcare provider - they may be affecting your ability to take medications"
                )
        
        return recommendations
    
    def _llm_analyze_adherence(
        self, adherence_rate: float, trend: str, patterns: Dict, insights: List
    ) -> Dict:
        """Use LLM to analyze adherence data"""
        prompt = f"""Analyze this medication adherence data:

Adherence Rate: {adherence_rate*100:.1f}%
Target: {self.adherence_target*100:.0f}%
Trend: {trend}

Patterns:
- Morning adherence: {patterns.get('morning_adherence', 0)*100:.0f}%
- Evening adherence: {patterns.get('evening_adherence', 0)*100:.0f}%
- Weekday adherence: {patterns.get('weekday_adherence', 0)*100:.0f}%
- Weekend adherence: {patterns.get('weekend_adherence', 0)*100:.0f}%

Current Insights: {insights}

Provide:
1. A brief, encouraging summary (2-3 sentences)
2. 2-3 specific, actionable recommendations
3. Your reasoning

Format as JSON:
{{
    "summary": "...",
    "recommendations": ["...", "..."],
    "reasoning": "..."
}}"""
        
        response = self.call_llm(prompt, system_prompt=self.get_system_prompt())
        return self.parse_json_response(response, {
            "summary": f"Your adherence rate is {adherence_rate*100:.1f}%.",
            "recommendations": [],
            "reasoning": ""
        })
    
    def _llm_analyze_patterns(
        self, day_patterns: Dict, time_patterns: Dict, med_patterns: Dict, issues: List
    ) -> Dict:
        """Use LLM to analyze adherence patterns"""
        prompt = f"""Analyze these medication adherence patterns:

Day of Week Patterns:
- Weekday rate: {day_patterns.get('weekday_rate', 0)*100:.0f}%
- Weekend rate: {day_patterns.get('weekend_rate', 0)*100:.0f}%

Time of Day Patterns:
{chr(10).join([f"- {slot}: {data['rate']*100:.0f}%" for slot, data in time_patterns.items()])}

Issues Detected:
{chr(10).join([f"- {i['type']}: {i['description']}" for i in issues]) if issues else "None"}

Provide:
1. Summary of key patterns
2. Specific recommendations to address issues
3. Reasoning

Format as JSON:
{{
    "summary": "...",
    "recommendations": ["...", "..."],
    "reasoning": "..."
}}"""
        
        response = self.call_llm(prompt, system_prompt=self.get_system_prompt())
        return self.parse_json_response(response, {
            "summary": "Pattern analysis complete.",
            "recommendations": [],
            "reasoning": ""
        })
    
    def _llm_analyze_symptoms(self, analyses: List[Dict]) -> Dict:
        """Use LLM to provide comprehensive symptom analysis"""
        symptoms_text = "\n".join([
            f"- {a['symptom']} (severity: {a['severity']}/10, medication: {a['medication'] or 'unknown'})"
            for a in analyses
        ])
        
        prompt = f"""Analyze these reported symptoms:

{symptoms_text}

Individual Analyses:
{chr(10).join([f"- {a['symptom']}: correlation score {a['correlation_score']:.1f}, is_side_effect: {a['is_side_effect']}" for a in analyses])}

Provide:
1. Overall summary
2. Combined recommendations
3. Whether immediate medical attention is needed

Format as JSON:
{{
    "summary": "...",
    "recommendations": ["...", "..."],
    "requires_immediate_attention": false,
    "reasoning": "..."
}}"""
        
        response = self.call_llm(prompt, system_prompt=self.get_system_prompt())
        return self.parse_json_response(response, {
            "summary": f"Analyzed {len(analyses)} symptom(s).",
            "recommendations": [],
            "reasoning": ""
        })
    
    def _llm_analyze_single_symptom(self, symptom: models.SymptomReport, current_analysis: Dict) -> Dict:
        """Use LLM to analyze a single symptom"""
        prompt = f"""Analyze this medication-related symptom:

Symptom: {symptom.symptom}
Severity: {symptom.severity}/10
Suspected Medication: {symptom.medication_name or 'Not specified'}
Timing: {symptom.timing or 'Not specified'}
Description: {symptom.description or 'None provided'}

Current Analysis:
- Is known side effect: {current_analysis.get('is_side_effect', False)}
- Correlation score: {current_analysis.get('correlation_score', 0)}

Provide:
1. Likelihood this is medication-related (0-1)
2. Specific recommendations
3. Whether this requires medical attention

Format as JSON:
{{
    "correlation_score": 0.0,
    "is_side_effect": false,
    "requires_medical_attention": false,
    "recommendations": ["..."],
    "explanation": "..."
}}"""
        
        response = self.call_llm(prompt, system_prompt=self.get_system_prompt())
        return self.parse_json_response(response, {})
    
    def get_system_prompt(self) -> str:
        """Get monitoring-specific system prompt from prompts module"""
        return MONITORING_SYSTEM_PROMPT
