"""
Healthcare Liaison Agent
Handles provider communication and FHIR-compatible report generation
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging
import json

from sqlalchemy.orm import Session

from config import settings, agent_config
from database import get_db_context
import models
from agents.base_agent import BaseAgent
from agents.state import AgentState, AgentResult, ProviderReportData
from agents.prompts import (
    LIAISON_SYSTEM_PROMPT,
    CLINICAL_NARRATIVE_PROMPT,
    ESCALATION_MESSAGE_PROMPT,
    CARE_COORDINATION_PROMPT,
    FHIR_CODING_SYSTEMS,
    ADHERENCE_LOINC_CODES,
    SEVERITY_SNOMED_CODES,
    REPORT_SECTIONS,
    ESCALATION_TIMEFRAMES
)


logger = logging.getLogger(__name__)


class LiaisonAgent(BaseAgent):
    """
    Agent responsible for:
    - Generating FHIR-compatible provider reports
    - Formatting clinical summaries for healthcare team
    - Handling urgent escalations
    - Facilitating patient-provider communication
    - Managing care coordination
    """
    
    agent_name = "Healthcare Liaison Agent"
    agent_type = "liaison"
    description = "Manages healthcare provider communication, generates FHIR reports, and handles escalations"
    
    def __init__(self):
        super().__init__()
        
        # Severity thresholds for escalation
        self.escalation_thresholds = {
            "critical": 9,      # Immediate provider contact
            "high": 7,          # Same-day communication
            "moderate": 5,      # Within 48 hours
            "low": 3            # Routine report inclusion
        }
        
        # FHIR resource types we generate
        self.supported_fhir_resources = [
            "Observation",      # Adherence observations
            "Condition",        # Symptom conditions
            "MedicationStatement",  # Medication adherence
            "CarePlan",         # Adherence care plan
            "DiagnosticReport"  # Summary reports
        ]
    
    def process(self, state: AgentState) -> AgentState:
        """Main processing method called by orchestrator"""
        task = state["current_task"].lower()
        patient_id = state["patient_id"]
        context = state.get("context", {})
        
        try:
            if "report" in task or "summary" in task:
                result = self.generate_provider_report(
                    patient_id,
                    context.get("report_type", "comprehensive"),
                    context.get("period_days", 30)
                )
            elif "escalat" in task or "urgent" in task:
                result = self.handle_escalation(
                    patient_id,
                    context.get("reason"),
                    context.get("severity", "moderate"),
                    context.get("details", {})
                )
            elif "fhir" in task:
                result = self.generate_fhir_bundle(
                    patient_id,
                    context.get("resource_types", ["DiagnosticReport"])
                )
            else:
                # Default: generate comprehensive report
                result = self.generate_provider_report(patient_id)
            
            state["agent_results"]["liaison"] = result.model_dump()
            state["context"]["liaison_result"] = result.model_dump()
            
            if result.requires_escalation:
                state["requires_escalation"] = True
                
        except Exception as e:
            logger.error(f"Liaison agent error: {e}")
            state["error"] = str(e)
            state["agent_results"]["liaison"] = self.create_result(
                success=False,
                summary=f"Error in provider communication: {str(e)}",
                confidence=0.0
            ).model_dump()
        
        return state
    
    def generate_provider_report(
        self,
        patient_id: int,
        report_type: str = "comprehensive",
        period_days: int = 30
    ) -> AgentResult:
        """
        Generate a provider report summarizing patient adherence
        
        Args:
            patient_id: Patient identifier
            report_type: Type of report (comprehensive, adherence, symptoms, summary)
            period_days: Number of days to include in report
            
        Returns:
            AgentResult with generated report
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
            
            # Collect report data
            report_data = self._collect_report_data(patient_id, period_days, db)
            
            # Generate report sections
            sections = self._generate_report_sections(report_data, report_type)
            
            # Use LLM to generate clinical narrative
            narrative = self._llm_generate_narrative(report_data, report_type)
            
            # Generate recommendations for provider
            recommendations = self._generate_provider_recommendations(report_data)
            
            # Create report record
            report = models.ProviderReport(
                patient_id=patient_id,
                report_type=report_type,
                period_start=datetime.utcnow() - timedelta(days=period_days),
                period_end=datetime.utcnow(),
                adherence_summary=report_data.get("adherence_summary", {}),
                symptoms_summary=report_data.get("symptoms_summary", []),
                barriers_identified=report_data.get("barriers", []),
                recommendations=recommendations,
                clinical_narrative=narrative.get("narrative", ""),
                fhir_bundle=self._generate_fhir_bundle_data(patient_id, report_data, db),
                generated_by="liaison_agent"
            )
            db.add(report)
            db.commit()
            
            self.log_activity(
                patient_id=patient_id,
                action="generate_provider_report",
                activity_type="provider_communication",
                input_data={"report_type": report_type, "period_days": period_days},
                output_data={"report_id": report.id},
                db=db
            )
            
            return self.create_result(
                success=True,
                summary=narrative.get("summary", f"Generated {report_type} report for provider"),
                data={
                    "report_id": report.id,
                    "report_type": report_type,
                    "period": f"{period_days} days",
                    "sections": sections,
                    "clinical_narrative": narrative.get("narrative"),
                    "key_findings": narrative.get("key_findings", [])
                },
                recommendations=recommendations,
                confidence=0.9,
                tools_used=["report_generator", "fhir_converter", "clinical_summarizer"]
            )
    
    def handle_escalation(
        self,
        patient_id: int,
        reason: str,
        severity: str = "moderate",
        details: Dict = None
    ) -> AgentResult:
        """
        Handle an urgent escalation to healthcare provider
        
        Args:
            patient_id: Patient identifier
            reason: Reason for escalation
            severity: Severity level (critical, high, moderate, low)
            details: Additional details about the escalation
            
        Returns:
            AgentResult with escalation status
        """
        with get_db_context() as db:
            # Get patient info
            patient = db.query(models.Patient).filter(
                models.Patient.id == patient_id
            ).first()
            
            if not patient:
                return self.create_result(
                    success=False,
                    summary="Patient not found",
                    confidence=0.0
                )
            
            # Validate and normalize severity
            severity = severity.lower()
            if severity not in self.escalation_thresholds:
                severity = "moderate"
            
            # Generate escalation summary
            escalation_data = self._prepare_escalation_data(
                patient_id, reason, severity, details or {}, db
            )
            
            # Use LLM to generate provider-appropriate message
            llm_result = self._llm_generate_escalation_message(
                patient, escalation_data, severity
            )
            
            # Create escalation record
            escalation = models.ProviderReport(
                patient_id=patient_id,
                report_type="escalation",
                period_start=datetime.utcnow() - timedelta(days=1),
                period_end=datetime.utcnow(),
                adherence_summary={"escalation_reason": reason},
                recommendations=[llm_result.get("recommended_action", "Review patient status")],
                clinical_narrative=llm_result.get("message", ""),
                severity=severity,
                requires_immediate_action=severity in ["critical", "high"],
                generated_by="liaison_agent"
            )
            db.add(escalation)
            
            # Update any related symptom reports
            if details and details.get("symptom_id"):
                symptom = db.query(models.SymptomReport).filter(
                    models.SymptomReport.id == details["symptom_id"]
                ).first()
                if symptom:
                    symptom.escalated = True
                    symptom.escalated_to_provider = True
                    symptom.provider_notified_at = datetime.utcnow()
            
            db.commit()
            
            # Trigger notification based on severity
            notification_sent = self._send_provider_notification(
                patient, escalation_data, severity, llm_result.get("message")
            )
            
            self.log_activity(
                patient_id=patient_id,
                action="escalation",
                activity_type="provider_communication",
                input_data={"severity": severity, "reason": reason},
                output_data={
                    "escalation_id": escalation.id,
                    "notification_sent": notification_sent
                },
                db=db
            )
            
            return self.create_result(
                success=True,
                summary=f"Escalation created with {severity} severity",
                data={
                    "escalation_id": escalation.id,
                    "severity": severity,
                    "provider_message": llm_result.get("message"),
                    "recommended_action": llm_result.get("recommended_action"),
                    "notification_sent": notification_sent,
                    "response_timeframe": self._get_response_timeframe(severity)
                },
                recommendations=[
                    llm_result.get("patient_guidance", "Your healthcare provider has been notified")
                ],
                confidence=0.9,
                requires_escalation=severity in ["critical", "high"],
                tools_used=["escalation_handler", "provider_notifier"]
            )
    
    def generate_fhir_bundle(
        self,
        patient_id: int,
        resource_types: List[str] = None
    ) -> AgentResult:
        """
        Generate FHIR-compatible bundle of patient data
        
        Args:
            patient_id: Patient identifier
            resource_types: Types of FHIR resources to include
            
        Returns:
            AgentResult with FHIR bundle
        """
        resource_types = resource_types or ["DiagnosticReport"]
        
        with get_db_context() as db:
            # Get patient data
            patient_context = self.get_patient_context(patient_id, db)
            
            if not patient_context:
                return self.create_result(
                    success=False,
                    summary="Patient not found",
                    confidence=0.0
                )
            
            # Collect data for FHIR bundle
            report_data = self._collect_report_data(patient_id, 30, db)
            
            # Generate FHIR bundle
            fhir_bundle = self._generate_fhir_bundle_data(
                patient_id, report_data, db, resource_types
            )
            
            self.log_activity(
                patient_id=patient_id,
                action="generate_fhir_bundle",
                activity_type="provider_communication",
                input_data={"resource_types": resource_types},
                output_data={"bundle_type": fhir_bundle.get("type")},
                db=db
            )
            
            return self.create_result(
                success=True,
                summary=f"Generated FHIR bundle with {len(fhir_bundle.get('entry', []))} resources",
                data={
                    "bundle": fhir_bundle,
                    "resource_types_included": resource_types,
                    "entry_count": len(fhir_bundle.get("entry", []))
                },
                confidence=0.95,
                tools_used=["fhir_generator"]
            )
    
    def generate_care_coordination_summary(self, patient_id: int) -> AgentResult:
        """
        Generate a care coordination summary for the healthcare team
        
        Args:
            patient_id: Patient identifier
            
        Returns:
            AgentResult with care coordination summary
        """
        with get_db_context() as db:
            patient_context = self.get_patient_context(patient_id, db)
            
            if not patient_context:
                return self.create_result(
                    success=False,
                    summary="Patient not found",
                    confidence=0.0
                )
            
            # Get all agent activities
            activities = db.query(models.AgentActivity).filter(
                models.AgentActivity.patient_id == patient_id,
                models.AgentActivity.timestamp >= datetime.utcnow() - timedelta(days=30)
            ).order_by(models.AgentActivity.timestamp.desc()).all()
            
            # Get barrier resolutions
            resolutions = db.query(models.BarrierResolution).filter(
                models.BarrierResolution.patient_id == patient_id,
                models.BarrierResolution.status == "active"
            ).all()
            
            # Get active interventions
            interventions = db.query(models.Intervention).filter(
                models.Intervention.patient_id == patient_id,
                models.Intervention.status == "active"
            ).all()
            
            # Generate summary
            summary_data = {
                "patient_overview": {
                    "name": patient_context["patient"]["name"],
                    "medication_count": len(patient_context["medications"]),
                    "active_barriers": len(resolutions),
                    "active_interventions": len(interventions)
                },
                "recent_activities": [
                    {
                        "agent": a.agent_type,
                        "action": a.action,
                        "date": a.timestamp.isoformat(),
                        "outcome": a.output_data
                    }
                    for a in activities[:10]
                ],
                "barrier_resolutions": [
                    {
                        "category": r.barrier_category.value if r.barrier_category else "unknown",
                        "description": r.barrier_description,
                        "strategy": r.resolution_strategy,
                        "status": r.status
                    }
                    for r in resolutions
                ],
                "active_interventions": [
                    {
                        "type": i.intervention_type.value if i.intervention_type else "unknown",
                        "description": i.description,
                        "status": i.status
                    }
                    for i in interventions
                ]
            }
            
            # Use LLM to generate care coordination narrative
            llm_result = self._llm_generate_care_coordination_summary(summary_data)
            
            return self.create_result(
                success=True,
                summary=llm_result.get("summary", "Care coordination summary generated"),
                data={
                    "summary": summary_data,
                    "narrative": llm_result.get("narrative"),
                    "coordination_recommendations": llm_result.get("recommendations", [])
                },
                recommendations=llm_result.get("recommendations", []),
                confidence=0.85,
                tools_used=["care_coordinator", "activity_analyzer"]
            )
    
    def _collect_report_data(self, patient_id: int, period_days: int, db: Session) -> Dict:
        """Collect all data needed for a report"""
        start_date = datetime.utcnow() - timedelta(days=period_days)
        
        # Get adherence data
        adherence_logs = db.query(models.AdherenceLog).filter(
            models.AdherenceLog.patient_id == patient_id,
            models.AdherenceLog.scheduled_time >= start_date
        ).all()
        
        total_doses = len(adherence_logs)
        taken_doses = sum(1 for l in adherence_logs if l.taken)
        adherence_rate = taken_doses / total_doses if total_doses > 0 else 0
        
        # Get medications
        medications = db.query(models.Medication).filter(
            models.Medication.patient_id == patient_id,
            models.Medication.is_active == True
        ).all()
        
        # Get symptoms
        symptoms = db.query(models.SymptomReport).filter(
            models.SymptomReport.patient_id == patient_id,
            models.SymptomReport.reported_at >= start_date
        ).all()
        
        # Get barriers
        barriers = db.query(models.BarrierResolution).filter(
            models.BarrierResolution.patient_id == patient_id,
            models.BarrierResolution.created_at >= start_date
        ).all()
        
        # Get interventions
        interventions = db.query(models.Intervention).filter(
            models.Intervention.patient_id == patient_id,
            models.Intervention.created_at >= start_date
        ).all()
        
        return {
            "period_start": start_date.isoformat(),
            "period_end": datetime.utcnow().isoformat(),
            "adherence_summary": {
                "total_doses": total_doses,
                "taken_doses": taken_doses,
                "adherence_rate": round(adherence_rate * 100, 1),
                "target_rate": agent_config.MONITORING_ADHERENCE_TARGET * 100,
                "target_met": adherence_rate >= agent_config.MONITORING_ADHERENCE_TARGET
            },
            "medications": [
                {"name": m.name, "dosage": m.dosage, "frequency": m.frequency}
                for m in medications
            ],
            "symptoms_summary": [
                {
                    "symptom": s.symptom,
                    "severity": s.severity,
                    "medication": s.medication_name,
                    "date": s.reported_at.isoformat(),
                    "resolved": s.resolved
                }
                for s in symptoms
            ],
            "barriers": [
                {
                    "category": b.barrier_category.value if b.barrier_category else "unknown",
                    "description": b.barrier_description,
                    "strategy": b.resolution_strategy,
                    "status": b.status
                }
                for b in barriers
            ],
            "interventions": [
                {
                    "type": i.intervention_type.value if i.intervention_type else "unknown",
                    "description": i.description,
                    "status": i.status,
                    "effectiveness": i.effectiveness_score
                }
                for i in interventions
            ]
        }
    
    def _generate_report_sections(self, report_data: Dict, report_type: str) -> List[Dict]:
        """Generate report sections based on data"""
        sections = []
        
        # Executive Summary
        sections.append({
            "title": "Executive Summary",
            "content": self._generate_executive_summary(report_data)
        })
        
        # Adherence Section
        adherence = report_data.get("adherence_summary", {})
        sections.append({
            "title": "Medication Adherence",
            "content": {
                "current_rate": f"{adherence.get('adherence_rate', 0)}%",
                "target_rate": f"{adherence.get('target_rate', 90)}%",
                "status": "Target Met" if adherence.get("target_met") else "Below Target",
                "doses_tracked": adherence.get("total_doses", 0)
            }
        })
        
        # Medications Section
        if report_data.get("medications"):
            sections.append({
                "title": "Current Medications",
                "content": report_data["medications"]
            })
        
        # Symptoms Section
        if report_data.get("symptoms_summary"):
            sections.append({
                "title": "Reported Symptoms",
                "content": {
                    "count": len(report_data["symptoms_summary"]),
                    "unresolved": sum(1 for s in report_data["symptoms_summary"] if not s["resolved"]),
                    "high_severity": sum(1 for s in report_data["symptoms_summary"] if s["severity"] >= 7),
                    "details": report_data["symptoms_summary"]
                }
            })
        
        # Barriers Section
        if report_data.get("barriers"):
            sections.append({
                "title": "Identified Barriers",
                "content": report_data["barriers"]
            })
        
        # Interventions Section
        if report_data.get("interventions"):
            sections.append({
                "title": "Active Interventions",
                "content": report_data["interventions"]
            })
        
        return sections
    
    def _generate_executive_summary(self, report_data: Dict) -> Dict:
        """Generate executive summary of report"""
        adherence = report_data.get("adherence_summary", {})
        symptoms = report_data.get("symptoms_summary", [])
        barriers = report_data.get("barriers", [])
        
        return {
            "period": f"{report_data.get('period_start', '')} to {report_data.get('period_end', '')}",
            "adherence_status": "Good" if adherence.get("target_met") else "Needs Attention",
            "adherence_rate": f"{adherence.get('adherence_rate', 0)}%",
            "medication_count": len(report_data.get("medications", [])),
            "symptoms_reported": len(symptoms),
            "unresolved_symptoms": sum(1 for s in symptoms if not s["resolved"]),
            "barriers_identified": len(barriers),
            "active_interventions": sum(1 for i in report_data.get("interventions", []) if i["status"] == "active")
        }
    
    def _generate_provider_recommendations(self, report_data: Dict) -> List[str]:
        """Generate recommendations for provider based on data"""
        recommendations = []
        
        adherence = report_data.get("adherence_summary", {})
        symptoms = report_data.get("symptoms_summary", [])
        barriers = report_data.get("barriers", [])
        
        # Adherence-based recommendations
        if not adherence.get("target_met"):
            rate = adherence.get("adherence_rate", 0)
            if rate < 50:
                recommendations.append(
                    "URGENT: Significant adherence concerns. Consider medication review and patient education session."
                )
            elif rate < 70:
                recommendations.append(
                    "Consider scheduling medication therapy management session to address adherence barriers."
                )
            else:
                recommendations.append(
                    "Adherence slightly below target. Reinforce medication importance at next visit."
                )
        
        # Symptom-based recommendations
        high_severity_symptoms = [s for s in symptoms if s["severity"] >= 7 and not s["resolved"]]
        if high_severity_symptoms:
            recommendations.append(
                f"Review {len(high_severity_symptoms)} high-severity symptom(s) for possible medication adjustment."
            )
        
        # Barrier-based recommendations
        cost_barriers = [b for b in barriers if b["category"] == "cost"]
        if cost_barriers:
            recommendations.append(
                "Cost barriers identified. Consider therapeutic alternatives or patient assistance programs."
            )
        
        side_effect_barriers = [b for b in barriers if b["category"] == "side_effects"]
        if side_effect_barriers:
            recommendations.append(
                "Side effect concerns reported. May benefit from medication timing adjustment or alternative formulation."
            )
        
        return recommendations
    
    def _generate_fhir_bundle_data(
        self,
        patient_id: int,
        report_data: Dict,
        db: Session,
        resource_types: List[str] = None
    ) -> Dict:
        """Generate FHIR bundle from patient data"""
        resource_types = resource_types or ["DiagnosticReport"]
        
        patient = db.query(models.Patient).filter(
            models.Patient.id == patient_id
        ).first()
        
        bundle = {
            "resourceType": "Bundle",
            "type": "collection",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "entry": []
        }
        
        # Add Patient resource reference
        bundle["entry"].append({
            "resource": {
                "resourceType": "Patient",
                "id": str(patient_id),
                "identifier": [
                    {
                        "system": "http://adherenceguardian.example.org/patient",
                        "value": str(patient_id)
                    }
                ],
                "name": [{"text": patient.name if patient else "Unknown"}]
            }
        })
        
        if "DiagnosticReport" in resource_types:
            # Add Diagnostic Report
            bundle["entry"].append({
                "resource": self._create_fhir_diagnostic_report(patient_id, report_data)
            })
        
        if "Observation" in resource_types:
            # Add Adherence Observation
            bundle["entry"].append({
                "resource": self._create_fhir_adherence_observation(patient_id, report_data)
            })
        
        if "MedicationStatement" in resource_types:
            # Add Medication Statements
            for med in report_data.get("medications", []):
                bundle["entry"].append({
                    "resource": self._create_fhir_medication_statement(patient_id, med)
                })
        
        if "Condition" in resource_types:
            # Add Conditions for symptoms
            for symptom in report_data.get("symptoms_summary", []):
                bundle["entry"].append({
                    "resource": self._create_fhir_condition(patient_id, symptom)
                })
        
        return bundle
    
    def _create_fhir_diagnostic_report(self, patient_id: int, report_data: Dict) -> Dict:
        """Create FHIR DiagnosticReport resource"""
        adherence = report_data.get("adherence_summary", {})
        
        return {
            "resourceType": "DiagnosticReport",
            "id": f"adherence-report-{patient_id}-{datetime.utcnow().strftime('%Y%m%d')}",
            "status": "final",
            "category": [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v2-0074",
                            "code": "OTH",
                            "display": "Other"
                        }
                    ],
                    "text": "Medication Adherence Report"
                }
            ],
            "code": {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": "LA14080-8",
                        "display": "Medication adherence"
                    }
                ],
                "text": "Medication Adherence Assessment"
            },
            "subject": {
                "reference": f"Patient/{patient_id}"
            },
            "effectivePeriod": {
                "start": report_data.get("period_start"),
                "end": report_data.get("period_end")
            },
            "issued": datetime.utcnow().isoformat() + "Z",
            "conclusion": f"Overall adherence rate: {adherence.get('adherence_rate', 0)}%. "
                         f"Target {'met' if adherence.get('target_met') else 'not met'}."
        }
    
    def _create_fhir_adherence_observation(self, patient_id: int, report_data: Dict) -> Dict:
        """Create FHIR Observation for adherence"""
        adherence = report_data.get("adherence_summary", {})
        
        return {
            "resourceType": "Observation",
            "id": f"adherence-obs-{patient_id}-{datetime.utcnow().strftime('%Y%m%d')}",
            "status": "final",
            "category": [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                            "code": "survey",
                            "display": "Survey"
                        }
                    ]
                }
            ],
            "code": {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": "LA14080-8",
                        "display": "Medication adherence"
                    }
                ]
            },
            "subject": {
                "reference": f"Patient/{patient_id}"
            },
            "effectiveDateTime": datetime.utcnow().isoformat() + "Z",
            "valueQuantity": {
                "value": adherence.get("adherence_rate", 0),
                "unit": "%",
                "system": "http://unitsofmeasure.org",
                "code": "%"
            },
            "interpretation": [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
                            "code": "N" if adherence.get("target_met") else "L",
                            "display": "Normal" if adherence.get("target_met") else "Low"
                        }
                    ]
                }
            ]
        }
    
    def _create_fhir_medication_statement(self, patient_id: int, medication: Dict) -> Dict:
        """Create FHIR MedicationStatement resource"""
        return {
            "resourceType": "MedicationStatement",
            "id": f"med-stmt-{patient_id}-{medication['name'].lower().replace(' ', '-')}",
            "status": "active",
            "medicationCodeableConcept": {
                "text": medication["name"]
            },
            "subject": {
                "reference": f"Patient/{patient_id}"
            },
            "dosage": [
                {
                    "text": f"{medication.get('dosage', '')} {medication.get('frequency', '')}"
                }
            ]
        }
    
    def _create_fhir_condition(self, patient_id: int, symptom: Dict) -> Dict:
        """Create FHIR Condition resource for symptom"""
        return {
            "resourceType": "Condition",
            "id": f"symptom-{patient_id}-{datetime.fromisoformat(symptom['date']).strftime('%Y%m%d%H%M')}",
            "clinicalStatus": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                        "code": "resolved" if symptom.get("resolved") else "active"
                    }
                ]
            },
            "severity": {
                "coding": [
                    {
                        "system": "http://snomed.info/sct",
                        "code": "24484000" if symptom["severity"] >= 7 else "6736007" if symptom["severity"] >= 4 else "255604002",
                        "display": "Severe" if symptom["severity"] >= 7 else "Moderate" if symptom["severity"] >= 4 else "Mild"
                    }
                ]
            },
            "code": {
                "text": symptom["symptom"]
            },
            "subject": {
                "reference": f"Patient/{patient_id}"
            },
            "onsetDateTime": symptom["date"],
            "note": [
                {
                    "text": f"Suspected relation to: {symptom.get('medication', 'Unknown medication')}"
                }
            ]
        }
    
    def _prepare_escalation_data(
        self,
        patient_id: int,
        reason: str,
        severity: str,
        details: Dict,
        db: Session
    ) -> Dict:
        """Prepare data for escalation"""
        # Get recent adherence
        recent_logs = db.query(models.AdherenceLog).filter(
            models.AdherenceLog.patient_id == patient_id,
            models.AdherenceLog.scheduled_time >= datetime.utcnow() - timedelta(days=7)
        ).all()
        
        adherence_rate = sum(1 for l in recent_logs if l.taken) / len(recent_logs) if recent_logs else 0
        
        # Get recent symptoms
        recent_symptoms = db.query(models.SymptomReport).filter(
            models.SymptomReport.patient_id == patient_id,
            models.SymptomReport.reported_at >= datetime.utcnow() - timedelta(days=7)
        ).all()
        
        return {
            "reason": reason,
            "severity": severity,
            "details": details,
            "context": {
                "recent_adherence_rate": round(adherence_rate * 100, 1),
                "recent_symptoms": [
                    {"symptom": s.symptom, "severity": s.severity}
                    for s in recent_symptoms
                ],
                "timestamp": datetime.utcnow().isoformat()
            }
        }
    
    def _send_provider_notification(
        self,
        patient: models.Patient,
        escalation_data: Dict,
        severity: str,
        message: str
    ) -> bool:
        """Send notification to provider (placeholder for actual notification system)"""
        # In production, this would integrate with:
        # - EHR messaging system
        # - Secure email
        # - Pager system for critical
        # - FHIR messaging
        
        logger.info(f"Provider notification for patient {patient.id}: {severity} - {message[:100]}...")
        
        # Placeholder: would return True if notification sent successfully
        return True
    
    def _get_response_timeframe(self, severity: str) -> str:
        """Get expected response timeframe based on severity"""
        timeframes = {
            "critical": "Immediate attention required",
            "high": "Same-day response recommended",
            "moderate": "Within 48 hours",
            "low": "At next scheduled visit"
        }
        return timeframes.get(severity, "Within 48 hours")
    
    def _llm_generate_narrative(self, report_data: Dict, report_type: str) -> Dict:
        """Use LLM to generate clinical narrative"""
        adherence = report_data.get("adherence_summary", {})
        symptoms = report_data.get("symptoms_summary", [])
        barriers = report_data.get("barriers", [])
        
        prompt = f"""Generate a clinical narrative for a medication adherence report.

Report Type: {report_type}
Period: {report_data.get('period_start', '')} to {report_data.get('period_end', '')}

Adherence Data:
- Rate: {adherence.get('adherence_rate', 0)}%
- Target: {adherence.get('target_rate', 90)}%
- Total doses: {adherence.get('total_doses', 0)}
- Doses taken: {adherence.get('taken_doses', 0)}

Medications: {len(report_data.get('medications', []))}

Symptoms Reported: {len(symptoms)}
{chr(10).join([f"- {s['symptom']} (severity: {s['severity']}/10)" for s in symptoms[:5]]) if symptoms else "None"}

Barriers Identified: {len(barriers)}
{chr(10).join([f"- {b['category']}: {b['description']}" for b in barriers[:3]]) if barriers else "None"}

Generate:
1. A concise summary (1-2 sentences)
2. A clinical narrative (2-3 paragraphs) suitable for a healthcare provider
3. Key findings list

Format as JSON:
{{
    "summary": "...",
    "narrative": "...",
    "key_findings": ["...", "..."]
}}"""
        
        response = self.call_llm(prompt, system_prompt=self.get_system_prompt())
        return self.parse_json_response(response, {
            "summary": f"Patient adherence at {adherence.get('adherence_rate', 0)}% over reporting period.",
            "narrative": "",
            "key_findings": []
        })
    
    def _llm_generate_escalation_message(
        self,
        patient: models.Patient,
        escalation_data: Dict,
        severity: str
    ) -> Dict:
        """Use LLM to generate provider-appropriate escalation message"""
        prompt = f"""Generate an escalation message for a healthcare provider.

Severity: {severity.upper()}
Reason: {escalation_data.get('reason', 'Unspecified')}

Context:
- Recent adherence: {escalation_data['context'].get('recent_adherence_rate', 'N/A')}%
- Recent symptoms: {escalation_data['context'].get('recent_symptoms', [])}

Additional Details: {escalation_data.get('details', {})}

Generate:
1. A clear, professional message for the provider
2. Recommended action
3. Patient guidance to provide

Format as JSON:
{{
    "message": "...",
    "recommended_action": "...",
    "patient_guidance": "..."
}}"""
        
        response = self.call_llm(prompt, system_prompt=self.get_system_prompt())
        return self.parse_json_response(response, {
            "message": f"{severity.upper()} escalation: {escalation_data.get('reason', 'Unspecified reason')}",
            "recommended_action": "Review patient status",
            "patient_guidance": "Your healthcare provider has been notified."
        })
    
    def _llm_generate_care_coordination_summary(self, summary_data: Dict) -> Dict:
        """Use LLM to generate care coordination summary"""
        prompt = f"""Generate a care coordination summary for a healthcare team.

Patient Overview:
- Medications: {summary_data['patient_overview'].get('medication_count', 0)}
- Active Barriers: {summary_data['patient_overview'].get('active_barriers', 0)}
- Active Interventions: {summary_data['patient_overview'].get('active_interventions', 0)}

Recent Agent Activities: {len(summary_data.get('recent_activities', []))}

Barrier Resolutions: {len(summary_data.get('barrier_resolutions', []))}

Active Interventions: {len(summary_data.get('active_interventions', []))}

Generate:
1. Brief summary
2. Care coordination narrative
3. Recommendations for the care team

Format as JSON:
{{
    "summary": "...",
    "narrative": "...",
    "recommendations": ["...", "..."]
}}"""
        
        response = self.call_llm(prompt, system_prompt=self.get_system_prompt())
        return self.parse_json_response(response, {
            "summary": "Care coordination summary generated.",
            "narrative": "",
            "recommendations": []
        })
    
    def get_system_prompt(self) -> str:
        """Get liaison-specific system prompt from prompts module"""
        return LIAISON_SYSTEM_PROMPT
