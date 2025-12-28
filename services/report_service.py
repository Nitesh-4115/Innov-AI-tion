"""
Report Service
Business logic for generating provider reports and FHIR exports
"""

import logging
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from database import get_db_context
import models
from models import AdherenceStatus, SeverityLevel


logger = logging.getLogger(__name__)


class ReportService:
    """
    Service for generating healthcare provider reports
    """
    
    async def create_provider_report(
        self,
        patient_id: int,
        report_period_start: date,
        report_period_end: date,
        provider_id: Optional[str] = None,
        include_fhir: bool = False,
        db: Optional[Session] = None
    ) -> models.ProviderReport:
        """
        Create a comprehensive provider report
        
        Args:
            patient_id: Patient ID
            report_period_start: Start of reporting period
            report_period_end: End of reporting period
            provider_id: Provider identifier
            include_fhir: Whether to include FHIR format
            db: Database session
            
        Returns:
            Created ProviderReport object
        """
        def _create(session: Session) -> models.ProviderReport:
            # Get patient
            patient = session.query(models.Patient).filter(
                models.Patient.id == patient_id
            ).first()
            
            if not patient:
                raise ValueError(f"Patient {patient_id} not found")
            
            # Gather all report data
            report_data = self._gather_report_data(
                session, patient_id,
                report_period_start, report_period_end
            )
            
            # Create FHIR bundle if requested
            fhir_bundle = None
            if include_fhir:
                fhir_bundle = self._create_fhir_bundle(
                    patient, report_data,
                    report_period_start, report_period_end
                )
            
            # Calculate overall adherence score
            adherence_score = report_data.get("adherence_summary", {}).get(
                "adherence_rate", 0.0
            )
            
            # Generate summary text
            summary = self._generate_summary(patient, report_data)
            
            # Create report record
            report = models.ProviderReport(
                patient_id=patient_id,
                provider_id=provider_id,
                report_period_start=report_period_start,
                report_period_end=report_period_end,
                adherence_summary=report_data.get("adherence_summary"),
                medication_summary=report_data.get("medication_summary"),
                symptom_summary=report_data.get("symptom_summary"),
                barrier_summary=report_data.get("barrier_summary"),
                interventions=report_data.get("interventions"),
                recommendations=report_data.get("recommendations"),
                fhir_bundle=fhir_bundle,
                overall_adherence_score=adherence_score,
                generated_at=datetime.utcnow()
            )
            
            session.add(report)
            session.commit()
            session.refresh(report)
            
            logger.info(
                f"Created provider report for patient {patient_id}, "
                f"period {report_period_start} to {report_period_end}"
            )
            return report
        
        if db:
            return _create(db)
        
        with get_db_context() as session:
            return _create(session)
    
    def _gather_report_data(
        self,
        session: Session,
        patient_id: int,
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """Gather all data needed for provider report"""
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())
        
        # Adherence data
        adherence_logs = session.query(models.AdherenceLog).filter(
            and_(
                models.AdherenceLog.patient_id == patient_id,
                models.AdherenceLog.logged_at >= start_dt,
                models.AdherenceLog.logged_at <= end_dt
            )
        ).all()
        
        adherence_summary = self._calculate_adherence_summary(adherence_logs)
        
        # Medication data
        medications = session.query(models.Medication).filter(
            models.Medication.patient_id == patient_id
        ).all()
        
        medication_summary = self._create_medication_summary(
            session, medications, adherence_logs
        )
        
        # Symptom data
        symptoms = session.query(models.SymptomReport).filter(
            and_(
                models.SymptomReport.patient_id == patient_id,
                models.SymptomReport.reported_at >= start_dt,
                models.SymptomReport.reported_at <= end_dt
            )
        ).all()
        
        symptom_summary = self._create_symptom_summary(symptoms)
        
        # Barrier resolutions
        barriers = session.query(models.BarrierResolution).filter(
            and_(
                models.BarrierResolution.patient_id == patient_id,
                models.BarrierResolution.identified_at >= start_dt,
                models.BarrierResolution.identified_at <= end_dt
            )
        ).all()
        
        barrier_summary = self._create_barrier_summary(barriers)
        
        # Interventions
        interventions = session.query(models.Intervention).filter(
            and_(
                models.Intervention.patient_id == patient_id,
                models.Intervention.created_at >= start_dt,
                models.Intervention.created_at <= end_dt
            )
        ).all()
        
        intervention_list = [
            {
                "type": i.intervention_type.value if i.intervention_type else "other",
                "description": i.description,
                "outcome": i.outcome,
                "date": i.created_at.isoformat()
            }
            for i in interventions
        ]
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            adherence_summary, symptom_summary, barrier_summary
        )
        
        return {
            "adherence_summary": adherence_summary,
            "medication_summary": medication_summary,
            "symptom_summary": symptom_summary,
            "barrier_summary": barrier_summary,
            "interventions": intervention_list,
            "recommendations": recommendations
        }
    
    def _calculate_adherence_summary(
        self,
        logs: List[models.AdherenceLog]
    ) -> Dict[str, Any]:
        """Calculate adherence statistics"""
        if not logs:
            return {
                "adherence_rate": 0.0,
                "total_doses": 0,
                "taken": 0,
                "missed": 0,
                "skipped": 0,
                "delayed": 0
            }
        
        total = len(logs)
        taken = sum(1 for l in logs if l.status == AdherenceStatus.TAKEN)
        missed = sum(1 for l in logs if l.status == AdherenceStatus.MISSED)
        skipped = sum(1 for l in logs if l.status == AdherenceStatus.SKIPPED)
        delayed = sum(1 for l in logs if l.status == AdherenceStatus.DELAYED)
        
        adherent = taken + delayed
        rate = (adherent / total) * 100 if total > 0 else 0.0
        
        # Calculate average deviation
        deviations = [
            l.deviation_minutes for l in logs
            if l.deviation_minutes is not None
        ]
        avg_deviation = sum(deviations) / len(deviations) if deviations else 0
        
        return {
            "adherence_rate": round(rate, 1),
            "total_doses": total,
            "taken": taken,
            "missed": missed,
            "skipped": skipped,
            "delayed": delayed,
            "average_time_deviation_minutes": round(avg_deviation, 1)
        }
    
    def _create_medication_summary(
        self,
        session: Session,
        medications: List[models.Medication],
        adherence_logs: List[models.AdherenceLog]
    ) -> List[Dict[str, Any]]:
        """Create per-medication summary"""
        summaries = []
        
        for med in medications:
            med_logs = [l for l in adherence_logs if l.medication_id == med.id]
            
            if med_logs:
                total = len(med_logs)
                taken = sum(1 for l in med_logs if l.status == AdherenceStatus.TAKEN)
                delayed = sum(1 for l in med_logs if l.status == AdherenceStatus.DELAYED)
                adherent = taken + delayed
                rate = (adherent / total) * 100
            else:
                total = 0
                rate = 0.0
            
            summaries.append({
                "medication_id": med.id,
                "medication_name": med.name,
                "dosage": med.dosage,
                "frequency": med.frequency,
                "adherence_rate": round(rate, 1),
                "total_scheduled": total,
                "active": med.active
            })
        
        # Sort by adherence rate (lowest first)
        summaries.sort(key=lambda x: x["adherence_rate"])
        return summaries
    
    def _create_symptom_summary(
        self,
        symptoms: List[models.SymptomReport]
    ) -> Dict[str, Any]:
        """Create symptom summary"""
        if not symptoms:
            return {
                "total_reports": 0,
                "symptoms": []
            }
        
        from collections import defaultdict
        symptom_counts = defaultdict(lambda: {"count": 0, "severities": []})
        
        for s in symptoms:
            symptom_counts[s.symptom_name]["count"] += 1
            symptom_counts[s.symptom_name]["severities"].append(s.severity.value)
        
        symptom_list = []
        for name, data in symptom_counts.items():
            # Get max severity
            severity_order = ["mild", "moderate", "severe", "critical"]
            max_sev = max(
                data["severities"],
                key=lambda x: severity_order.index(x) if x in severity_order else 0
            )
            
            symptom_list.append({
                "symptom": name,
                "occurrence_count": data["count"],
                "max_severity": max_sev
            })
        
        # Sort by count then severity
        symptom_list.sort(key=lambda x: x["occurrence_count"], reverse=True)
        
        return {
            "total_reports": len(symptoms),
            "unique_symptoms": len(symptom_counts),
            "symptoms": symptom_list[:10]  # Top 10
        }
    
    def _create_barrier_summary(
        self,
        barriers: List[models.BarrierResolution]
    ) -> Dict[str, Any]:
        """Create barrier resolution summary"""
        if not barriers:
            return {
                "total_identified": 0,
                "resolved": 0,
                "barriers": []
            }
        
        resolved = sum(1 for b in barriers if b.resolved)
        
        barrier_list = [
            {
                "category": b.category.value if b.category else "unknown",
                "description": b.barrier_description,
                "resolved": b.resolved,
                "resolution": b.resolution_description
            }
            for b in barriers
        ]
        
        return {
            "total_identified": len(barriers),
            "resolved": resolved,
            "resolution_rate": round((resolved / len(barriers)) * 100, 1),
            "barriers": barrier_list
        }
    
    def _generate_recommendations(
        self,
        adherence: Dict,
        symptoms: Dict,
        barriers: Dict
    ) -> List[Dict[str, str]]:
        """Generate recommendations based on data analysis"""
        recommendations = []
        
        # Adherence-based recommendations
        adherence_rate = adherence.get("adherence_rate", 0)
        if adherence_rate < 70:
            recommendations.append({
                "category": "adherence",
                "priority": "high",
                "recommendation": "Consider medication regimen review - adherence below 70%"
            })
        elif adherence_rate < 85:
            recommendations.append({
                "category": "adherence",
                "priority": "medium",
                "recommendation": "Monitor adherence closely - some improvement needed"
            })
        
        if adherence.get("missed", 0) > 10:
            recommendations.append({
                "category": "adherence",
                "priority": "medium",
                "recommendation": "Review timing of doses - significant missed doses"
            })
        
        # Symptom-based recommendations
        symptom_list = symptoms.get("symptoms", [])
        severe_symptoms = [
            s for s in symptom_list
            if s.get("max_severity") in ["severe", "critical"]
        ]
        
        if severe_symptoms:
            recommendations.append({
                "category": "symptoms",
                "priority": "high",
                "recommendation": f"Review severe symptoms reported: {', '.join(s['symptom'] for s in severe_symptoms[:3])}"
            })
        
        # Barrier-based recommendations
        if barriers.get("total_identified", 0) > 0:
            unresolved = barriers["total_identified"] - barriers.get("resolved", 0)
            if unresolved > 0:
                recommendations.append({
                    "category": "barriers",
                    "priority": "medium",
                    "recommendation": f"{unresolved} unresolved barriers to adherence"
                })
        
        return recommendations
    
    def _generate_summary(
        self,
        patient: models.Patient,
        data: Dict
    ) -> str:
        """Generate text summary for the report"""
        adherence_rate = data.get("adherence_summary", {}).get("adherence_rate", 0)
        total_symptoms = data.get("symptom_summary", {}).get("total_reports", 0)
        
        summary = f"Report for {patient.first_name} {patient.last_name}\n"
        summary += f"Overall Adherence: {adherence_rate}%\n"
        summary += f"Symptom Reports: {total_symptoms}\n"
        
        if data.get("recommendations"):
            summary += f"\nKey Recommendations:\n"
            for rec in data["recommendations"][:3]:
                summary += f"- {rec['recommendation']}\n"
        
        return summary
    
    def _create_fhir_bundle(
        self,
        patient: models.Patient,
        data: Dict,
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """Create FHIR R4 compliant bundle"""
        bundle = {
            "resourceType": "Bundle",
            "type": "collection",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "entry": []
        }
        
        # Patient resource
        patient_resource = {
            "resourceType": "Patient",
            "id": str(patient.id),
            "name": [{
                "given": [patient.first_name],
                "family": patient.last_name
            }],
            "birthDate": patient.date_of_birth.isoformat() if patient.date_of_birth else None,
            "gender": "unknown"  # Would need to add gender to model
        }
        
        bundle["entry"].append({
            "resource": patient_resource
        })
        
        # MedicationStatement resources
        for med in data.get("medication_summary", []):
            med_statement = {
                "resourceType": "MedicationStatement",
                "status": "active" if med["active"] else "stopped",
                "medicationCodeableConcept": {
                    "text": med["medication_name"]
                },
                "subject": {
                    "reference": f"Patient/{patient.id}"
                },
                "dosage": [{
                    "text": f"{med['dosage']} {med['frequency']}"
                }],
                "extension": [{
                    "url": "http://example.org/adherence-rate",
                    "valueDecimal": med["adherence_rate"]
                }]
            }
            
            bundle["entry"].append({
                "resource": med_statement
            })
        
        # Observation resources for adherence
        adherence_obs = {
            "resourceType": "Observation",
            "status": "final",
            "code": {
                "coding": [{
                    "system": "http://loinc.org",
                    "code": "71799-1",
                    "display": "Medication adherence"
                }]
            },
            "subject": {
                "reference": f"Patient/{patient.id}"
            },
            "effectivePeriod": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "valueQuantity": {
                "value": data.get("adherence_summary", {}).get("adherence_rate", 0),
                "unit": "%"
            }
        }
        
        bundle["entry"].append({
            "resource": adherence_obs
        })
        
        # Condition resources for symptoms
        for symptom in data.get("symptom_summary", {}).get("symptoms", []):
            condition = {
                "resourceType": "Condition",
                "clinicalStatus": {
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                        "code": "active"
                    }]
                },
                "severity": {
                    "text": symptom["max_severity"]
                },
                "code": {
                    "text": symptom["symptom"]
                },
                "subject": {
                    "reference": f"Patient/{patient.id}"
                },
                "note": [{
                    "text": f"Reported {symptom['occurrence_count']} times"
                }]
            }
            
            bundle["entry"].append({
                "resource": condition
            })
        
        return bundle
    
    async def get_report(
        self,
        report_id: int,
        db: Optional[Session] = None
    ) -> Optional[models.ProviderReport]:
        """Get a provider report by ID"""
        def _get(session: Session) -> Optional[models.ProviderReport]:
            return session.query(models.ProviderReport).filter(
                models.ProviderReport.id == report_id
            ).first()
        
        if db:
            return _get(db)
        
        with get_db_context() as session:
            return _get(session)
    
    async def get_patient_reports(
        self,
        patient_id: int,
        limit: int = 10,
        db: Optional[Session] = None
    ) -> List[models.ProviderReport]:
        """Get recent provider reports for a patient"""
        def _get(session: Session) -> List[models.ProviderReport]:
            return session.query(models.ProviderReport).filter(
                models.ProviderReport.patient_id == patient_id
            ).order_by(
                desc(models.ProviderReport.generated_at)
            ).limit(limit).all()
        
        if db:
            return _get(db)
        
        with get_db_context() as session:
            return _get(session)
    
    async def get_report_as_fhir(
        self,
        report_id: int,
        db: Optional[Session] = None
    ) -> Optional[Dict[str, Any]]:
        """Get report FHIR bundle"""
        report = await self.get_report(report_id, db)
        
        if report and report.fhir_bundle:
            return report.fhir_bundle
        
        return None
    
    async def generate_quick_summary(
        self,
        patient_id: int,
        days: int = 7,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Generate a quick summary without creating a full report"""
        def _generate(session: Session) -> Dict[str, Any]:
            end_date = date.today()
            start_date = end_date - timedelta(days=days)
            start_dt = datetime.combine(start_date, datetime.min.time())
            end_dt = datetime.combine(end_date, datetime.max.time())
            
            # Get patient
            patient = session.query(models.Patient).filter(
                models.Patient.id == patient_id
            ).first()
            
            if not patient:
                raise ValueError(f"Patient {patient_id} not found")
            
            # Adherence
            adherence_logs = session.query(models.AdherenceLog).filter(
                and_(
                    models.AdherenceLog.patient_id == patient_id,
                    models.AdherenceLog.logged_at >= start_dt,
                    models.AdherenceLog.logged_at <= end_dt
                )
            ).all()
            
            total_doses = len(adherence_logs)
            taken = sum(
                1 for l in adherence_logs
                if l.status in [AdherenceStatus.TAKEN, AdherenceStatus.DELAYED]
            )
            missed = sum(
                1 for l in adherence_logs
                if l.status == AdherenceStatus.MISSED
            )
            
            adherence_rate = (taken / total_doses) * 100 if total_doses > 0 else 0.0
            
            # Symptoms
            symptoms = session.query(models.SymptomReport).filter(
                and_(
                    models.SymptomReport.patient_id == patient_id,
                    models.SymptomReport.reported_at >= start_dt,
                    models.SymptomReport.reported_at <= end_dt
                )
            ).all()
            
            severe_count = sum(
                1 for s in symptoms
                if s.severity in [SeverityLevel.SEVERE, SeverityLevel.CRITICAL]
            )
            
            return {
                "patient_name": f"{patient.first_name} {patient.last_name}",
                "period_days": days,
                "adherence_rate": round(adherence_rate, 1),
                "total_doses_scheduled": total_doses,
                "doses_taken": taken,
                "doses_missed": missed,
                "symptom_reports": len(symptoms),
                "severe_symptoms": severe_count,
                "generated_at": datetime.utcnow().isoformat()
            }
        
        if db:
            return _generate(db)
        
        with get_db_context() as session:
            return _generate(session)
    
    async def export_report_json(
        self,
        report_id: int,
        db: Optional[Session] = None
    ) -> Optional[str]:
        """Export report as JSON string"""
        report = await self.get_report(report_id, db)
        
        if not report:
            return None
        
        export_data = {
            "report_id": report.id,
            "patient_id": report.patient_id,
            "period": {
                "start": report.report_period_start.isoformat(),
                "end": report.report_period_end.isoformat()
            },
            "overall_adherence_score": report.overall_adherence_score,
            "adherence_summary": report.adherence_summary,
            "medication_summary": report.medication_summary,
            "symptom_summary": report.symptom_summary,
            "barrier_summary": report.barrier_summary,
            "interventions": report.interventions,
            "recommendations": report.recommendations,
            "generated_at": report.generated_at.isoformat()
        }
        
        return json.dumps(export_data, indent=2)


# Singleton instance
report_service = ReportService()
