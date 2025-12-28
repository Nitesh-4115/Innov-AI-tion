"""
Symptom Service
Business logic for symptom tracking and analysis
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, date, timedelta
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func

from database import get_db_context
import models
from models import SeverityLevel
from tools.symptom_correlator import symptom_correlator


logger = logging.getLogger(__name__)


class SymptomService:
    """
    Service for symptom tracking and analysis
    """
    
    async def report_symptom(
        self,
        patient_id: int,
        symptom_name: str,
        severity: SeverityLevel,
        description: Optional[str] = None,
        medication_id: Optional[int] = None,
        onset_time: Optional[datetime] = None,
        duration_minutes: Optional[int] = None,
        body_location: Optional[str] = None,
        triggers: Optional[List[str]] = None,
        relieved_by: Optional[List[str]] = None,
        db: Optional[Session] = None
    ) -> models.SymptomReport:
        """
        Report a symptom
        
        Args:
            patient_id: Patient ID
            symptom_name: Name of the symptom
            severity: Severity level
            description: Detailed description
            medication_id: Associated medication if known
            onset_time: When symptom started
            duration_minutes: How long symptom lasted
            body_location: Where on body (for pain/discomfort)
            triggers: What might have caused it
            relieved_by: What helped relieve it
            db: Database session
            
        Returns:
            Created SymptomReport object
        """
        def _report(session: Session) -> models.SymptomReport:
            # Verify patient exists
            patient = session.query(models.Patient).filter(
                models.Patient.id == patient_id
            ).first()
            
            if not patient:
                raise ValueError(f"Patient {patient_id} not found")
            
            # Create additional data dict for extra fields
            additional_data = {}
            if body_location:
                additional_data["body_location"] = body_location
            if triggers:
                additional_data["triggers"] = triggers
            if relieved_by:
                additional_data["relieved_by"] = relieved_by
            
            report = models.SymptomReport(
                patient_id=patient_id,
                symptom_name=symptom_name,
                severity=severity,
                description=description,
                medication_id=medication_id,
                onset_time=onset_time,
                duration_minutes=duration_minutes,
                additional_data=additional_data if additional_data else None,
                reported_at=datetime.utcnow()
            )
            
            session.add(report)
            session.commit()
            session.refresh(report)
            
            logger.info(
                f"Symptom reported for patient {patient_id}: "
                f"{symptom_name} ({severity.value})"
            )
            return report
        
        if db:
            return _report(db)
        
        with get_db_context() as session:
            return _report(session)
    
    async def get_symptom_report(
        self,
        report_id: int,
        db: Optional[Session] = None
    ) -> Optional[models.SymptomReport]:
        """Get a symptom report by ID"""
        def _get(session: Session) -> Optional[models.SymptomReport]:
            return session.query(models.SymptomReport).filter(
                models.SymptomReport.id == report_id
            ).first()
        
        if db:
            return _get(db)
        
        with get_db_context() as session:
            return _get(session)
    
    async def get_patient_symptoms(
        self,
        patient_id: int,
        days: int = 30,
        severity: Optional[SeverityLevel] = None,
        db: Optional[Session] = None
    ) -> List[models.SymptomReport]:
        """Get symptom reports for a patient"""
        def _get(session: Session) -> List[models.SymptomReport]:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            query = session.query(models.SymptomReport).filter(
                and_(
                    models.SymptomReport.patient_id == patient_id,
                    models.SymptomReport.reported_at >= start_date
                )
            )
            
            if severity:
                query = query.filter(models.SymptomReport.severity == severity)
            
            return query.order_by(desc(models.SymptomReport.reported_at)).all()
        
        if db:
            return _get(db)
        
        with get_db_context() as session:
            return _get(session)
    
    async def update_symptom_report(
        self,
        report_id: int,
        updates: Dict[str, Any],
        db: Optional[Session] = None
    ) -> Optional[models.SymptomReport]:
        """Update a symptom report"""
        def _update(session: Session) -> Optional[models.SymptomReport]:
            report = session.query(models.SymptomReport).filter(
                models.SymptomReport.id == report_id
            ).first()
            
            if not report:
                return None
            
            allowed_fields = {
                'symptom_name', 'severity', 'description',
                'medication_id', 'onset_time', 'duration_minutes',
                'resolved', 'resolved_at'
            }
            
            for field, value in updates.items():
                if field in allowed_fields and hasattr(report, field):
                    setattr(report, field, value)
            
            session.commit()
            session.refresh(report)
            
            return report
        
        if db:
            return _update(db)
        
        with get_db_context() as session:
            return _update(session)
    
    async def resolve_symptom(
        self,
        report_id: int,
        resolution_notes: Optional[str] = None,
        db: Optional[Session] = None
    ) -> Optional[models.SymptomReport]:
        """Mark a symptom as resolved"""
        updates = {
            'resolved': True,
            'resolved_at': datetime.utcnow()
        }
        if resolution_notes:
            updates['description'] = resolution_notes
        
        return await self.update_symptom_report(report_id, updates, db)
    
    async def get_symptom_summary(
        self,
        patient_id: int,
        days: int = 30,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Get summary of patient symptoms"""
        def _get(session: Session) -> Dict[str, Any]:
            symptoms = session.query(models.SymptomReport).filter(
                and_(
                    models.SymptomReport.patient_id == patient_id,
                    models.SymptomReport.reported_at >= datetime.utcnow() - timedelta(days=days)
                )
            ).all()
            
            if not symptoms:
                return {
                    "total_reports": 0,
                    "most_common": [],
                    "severity_distribution": {},
                    "days_analyzed": days
                }
            
            # Count by symptom name
            symptom_counts = defaultdict(int)
            for s in symptoms:
                symptom_counts[s.symptom_name] += 1
            
            # Sort by frequency
            most_common = [
                {"symptom": name, "count": count}
                for name, count in sorted(
                    symptom_counts.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:5]
            ]
            
            # Severity distribution
            severity_dist = defaultdict(int)
            for s in symptoms:
                severity_dist[s.severity.value] += 1
            
            # Count by medication (potential side effects)
            med_related = defaultdict(list)
            for s in symptoms:
                if s.medication_id:
                    med = session.query(models.Medication).filter(
                        models.Medication.id == s.medication_id
                    ).first()
                    if med:
                        med_related[med.name].append(s.symptom_name)
            
            return {
                "total_reports": len(symptoms),
                "most_common": most_common,
                "severity_distribution": dict(severity_dist),
                "medication_related": dict(med_related),
                "days_analyzed": days
            }
        
        if db:
            return _get(db)
        
        with get_db_context() as session:
            return _get(session)
    
    async def analyze_correlations(
        self,
        patient_id: int,
        days: int = 30,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Analyze symptom correlations with medications
        
        Uses symptom correlator tool to identify patterns
        """
        def _analyze(session: Session) -> Dict[str, Any]:
            # Get symptoms
            symptoms = session.query(models.SymptomReport).filter(
                and_(
                    models.SymptomReport.patient_id == patient_id,
                    models.SymptomReport.reported_at >= datetime.utcnow() - timedelta(days=days)
                )
            ).all()
            
            # Get medications
            medications = session.query(models.Medication).filter(
                and_(
                    models.Medication.patient_id == patient_id,
                    models.Medication.active == True
                )
            ).all()
            
            # Prepare data for correlator
            symptom_data = [
                {
                    "symptom_name": s.symptom_name,
                    "severity": s.severity.value,
                    "reported_at": s.reported_at.isoformat(),
                    "medication_id": s.medication_id
                }
                for s in symptoms
            ]
            
            medication_data = [
                {
                    "medication_id": m.id,
                    "name": m.name,
                    "start_date": m.start_date.isoformat() if m.start_date else None
                }
                for m in medications
            ]
            
            # Use symptom correlator
            correlation_analysis = symptom_correlator.analyze_correlations(
                symptom_data,
                medication_data
            )
            
            return correlation_analysis
        
        if db:
            return _analyze(db)
        
        with get_db_context() as session:
            return _analyze(session)
    
    async def get_potential_side_effects(
        self,
        patient_id: int,
        db: Optional[Session] = None
    ) -> List[Dict[str, Any]]:
        """
        Identify symptoms that may be medication side effects
        """
        def _get(session: Session) -> List[Dict[str, Any]]:
            # Get recent symptoms
            symptoms = session.query(models.SymptomReport).filter(
                and_(
                    models.SymptomReport.patient_id == patient_id,
                    models.SymptomReport.reported_at >= datetime.utcnow() - timedelta(days=30)
                )
            ).all()
            
            # Get medications
            medications = session.query(models.Medication).filter(
                and_(
                    models.Medication.patient_id == patient_id,
                    models.Medication.active == True
                )
            ).all()
            
            med_names = [m.name for m in medications]
            symptom_list = [s.symptom_name for s in symptoms]
            
            # Use correlator to identify side effects
            potential_side_effects = symptom_correlator.identify_potential_side_effects(
                med_names,
                symptom_list
            )
            
            return potential_side_effects
        
        if db:
            return _get(db)
        
        with get_db_context() as session:
            return _get(session)
    
    async def get_symptom_trends(
        self,
        patient_id: int,
        symptom_name: Optional[str] = None,
        weeks: int = 4,
        db: Optional[Session] = None
    ) -> List[Dict[str, Any]]:
        """Get symptom trends over time"""
        def _get(session: Session) -> List[Dict[str, Any]]:
            trends = []
            today = date.today()
            
            for week in range(weeks):
                week_end = today - timedelta(days=7 * week)
                week_start = week_end - timedelta(days=6)
                
                start_dt = datetime.combine(week_start, datetime.min.time())
                end_dt = datetime.combine(week_end, datetime.max.time())
                
                query = session.query(models.SymptomReport).filter(
                    and_(
                        models.SymptomReport.patient_id == patient_id,
                        models.SymptomReport.reported_at >= start_dt,
                        models.SymptomReport.reported_at <= end_dt
                    )
                )
                
                if symptom_name:
                    query = query.filter(
                        models.SymptomReport.symptom_name == symptom_name
                    )
                
                symptoms = query.all()
                
                # Calculate average severity
                if symptoms:
                    severity_values = {
                        SeverityLevel.MILD: 1,
                        SeverityLevel.MODERATE: 2,
                        SeverityLevel.SEVERE: 3,
                        SeverityLevel.CRITICAL: 4
                    }
                    avg_severity = sum(
                        severity_values.get(s.severity, 2)
                        for s in symptoms
                    ) / len(symptoms)
                else:
                    avg_severity = 0
                
                trends.append({
                    "week_start": week_start.isoformat(),
                    "week_end": week_end.isoformat(),
                    "total_reports": len(symptoms),
                    "average_severity": round(avg_severity, 2)
                })
            
            return trends
        
        if db:
            return _get(db)
        
        with get_db_context() as session:
            return _get(session)
    
    async def get_severe_symptoms(
        self,
        patient_id: int,
        days: int = 7,
        db: Optional[Session] = None
    ) -> List[Dict[str, Any]]:
        """Get severe or critical symptoms requiring attention"""
        def _get(session: Session) -> List[Dict[str, Any]]:
            symptoms = session.query(models.SymptomReport).filter(
                and_(
                    models.SymptomReport.patient_id == patient_id,
                    models.SymptomReport.reported_at >= datetime.utcnow() - timedelta(days=days),
                    models.SymptomReport.severity.in_([
                        SeverityLevel.SEVERE,
                        SeverityLevel.CRITICAL
                    ])
                )
            ).order_by(desc(models.SymptomReport.reported_at)).all()
            
            severe_list = []
            for s in symptoms:
                med_name = None
                if s.medication_id:
                    med = session.query(models.Medication).filter(
                        models.Medication.id == s.medication_id
                    ).first()
                    med_name = med.name if med else None
                
                severe_list.append({
                    "report_id": s.id,
                    "symptom_name": s.symptom_name,
                    "severity": s.severity.value,
                    "description": s.description,
                    "medication": med_name,
                    "reported_at": s.reported_at.isoformat(),
                    "resolved": s.resolved if hasattr(s, 'resolved') else False
                })
            
            return severe_list
        
        if db:
            return _get(db)
        
        with get_db_context() as session:
            return _get(session)
    
    async def get_symptoms_for_provider_report(
        self,
        patient_id: int,
        start_date: date,
        end_date: date,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Get symptom data formatted for provider reports"""
        def _get(session: Session) -> Dict[str, Any]:
            start_dt = datetime.combine(start_date, datetime.min.time())
            end_dt = datetime.combine(end_date, datetime.max.time())
            
            symptoms = session.query(models.SymptomReport).filter(
                and_(
                    models.SymptomReport.patient_id == patient_id,
                    models.SymptomReport.reported_at >= start_dt,
                    models.SymptomReport.reported_at <= end_dt
                )
            ).all()
            
            # Group by symptom
            symptom_groups = defaultdict(list)
            for s in symptoms:
                symptom_groups[s.symptom_name].append({
                    "severity": s.severity.value,
                    "date": s.reported_at.date().isoformat(),
                    "description": s.description
                })
            
            # Create provider-friendly format
            symptom_report = []
            for name, occurrences in symptom_groups.items():
                # Get max severity
                severity_order = ["mild", "moderate", "severe", "critical"]
                max_severity = max(
                    occurrences,
                    key=lambda x: severity_order.index(x["severity"])
                    if x["severity"] in severity_order else 0
                )["severity"]
                
                symptom_report.append({
                    "symptom": name,
                    "occurrence_count": len(occurrences),
                    "max_severity": max_severity,
                    "first_reported": min(o["date"] for o in occurrences),
                    "last_reported": max(o["date"] for o in occurrences)
                })
            
            # Sort by severity then count
            symptom_report.sort(
                key=lambda x: (
                    severity_order.index(x["max_severity"])
                    if x["max_severity"] in severity_order else 0,
                    x["occurrence_count"]
                ),
                reverse=True
            )
            
            return {
                "total_symptom_reports": len(symptoms),
                "unique_symptoms": len(symptom_groups),
                "symptoms": symptom_report,
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                }
            }
        
        if db:
            return _get(db)
        
        with get_db_context() as session:
            return _get(session)


# Singleton instance
symptom_service = SymptomService()
