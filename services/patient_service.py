"""
Patient Service
Business logic for patient management
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, date, time, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from database import get_db_context
import models


logger = logging.getLogger(__name__)


class PatientService:
    """
    Service for patient-related operations
    """
    
    async def create_patient(
        self,
        email: str,
        first_name: str,
        last_name: str,
        phone: Optional[str] = None,
        date_of_birth: Optional[date] = None,
        conditions: Optional[List[str]] = None,
        allergies: Optional[List[str]] = None,
        timezone: str = "UTC",
        notification_preferences: Optional[Dict] = None,
        db: Optional[Session] = None
    ) -> models.Patient:
        """
        Create a new patient record
        
        Args:
            email: Patient email (unique)
            first_name: First name
            last_name: Last name
            phone: Phone number
            date_of_birth: Date of birth
            conditions: List of medical conditions
            allergies: List of drug allergies
            timezone: Patient's timezone
            notification_preferences: Notification settings
            db: Database session (optional)
            
        Returns:
            Created Patient object
        """
        def _create(session: Session) -> models.Patient:
            # Check for existing patient
            existing = session.query(models.Patient).filter(
                models.Patient.email == email
            ).first()
            
            if existing:
                raise ValueError(f"Patient with email {email} already exists")
            
            # Calculate age if DOB provided
            age = None
            if date_of_birth:
                today = date.today()
                age = today.year - date_of_birth.year
                if today.month < date_of_birth.month or (
                    today.month == date_of_birth.month and today.day < date_of_birth.day
                ):
                    age -= 1
            
            patient = models.Patient(
                email=email,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                date_of_birth=date_of_birth,
                age=age,
                conditions=conditions or [],
                allergies=allergies or [],
                timezone=timezone,
                notification_preferences=notification_preferences or {
                    "sms": True,
                    "email": True,
                    "push": True
                }
            )
            
            session.add(patient)
            session.commit()
            session.refresh(patient)
            
            logger.info(f"Created patient: {patient.id} - {patient.full_name}")
            return patient
        
        if db:
            return _create(db)
        
        with get_db_context() as session:
            return _create(session)
    
    async def get_patient(
        self,
        patient_id: int,
        db: Optional[Session] = None
    ) -> Optional[models.Patient]:
        """Get patient by ID"""
        def _get(session: Session) -> Optional[models.Patient]:
            return session.query(models.Patient).filter(
                models.Patient.id == patient_id
            ).first()
        
        if db:
            return _get(db)
        
        with get_db_context() as session:
            return _get(session)
    
    async def get_patient_by_email(
        self,
        email: str,
        db: Optional[Session] = None
    ) -> Optional[models.Patient]:
        """Get patient by email"""
        def _get(session: Session) -> Optional[models.Patient]:
            return session.query(models.Patient).filter(
                models.Patient.email == email
            ).first()
        
        if db:
            return _get(db)
        
        with get_db_context() as session:
            return _get(session)
    
    async def update_patient(
        self,
        patient_id: int,
        updates: Dict[str, Any],
        db: Optional[Session] = None
    ) -> Optional[models.Patient]:
        """
        Update patient information
        
        Args:
            patient_id: Patient ID
            updates: Dictionary of fields to update
            db: Database session
            
        Returns:
            Updated Patient object or None
        """
        def _update(session: Session) -> Optional[models.Patient]:
            patient = session.query(models.Patient).filter(
                models.Patient.id == patient_id
            ).first()
            
            if not patient:
                return None
            
            # Update allowed fields
            allowed_fields = {
                'first_name', 'last_name', 'phone', 'date_of_birth',
                'conditions', 'allergies', 'timezone', 'wake_time',
                'sleep_time', 'breakfast_time', 'lunch_time', 'dinner_time',
                'notification_preferences', 'preferred_reminder_minutes', 'is_active'
            }
            
            for field, value in updates.items():
                if field in allowed_fields and hasattr(patient, field):
                    setattr(patient, field, value)
            
            # Recalculate age if DOB updated
            if 'date_of_birth' in updates and updates['date_of_birth']:
                dob = updates['date_of_birth']
                today = date.today()
                patient.age = today.year - dob.year
                if today.month < dob.month or (
                    today.month == dob.month and today.day < dob.day
                ):
                    patient.age -= 1
            
            patient.updated_at = datetime.utcnow()
            session.commit()
            session.refresh(patient)
            
            logger.info(f"Updated patient: {patient_id}")
            return patient
        
        if db:
            return _update(db)
        
        with get_db_context() as session:
            return _update(session)
    
    async def update_preferences(
        self,
        patient_id: int,
        wake_time: Optional[time] = None,
        sleep_time: Optional[time] = None,
        breakfast_time: Optional[time] = None,
        lunch_time: Optional[time] = None,
        dinner_time: Optional[time] = None,
        db: Optional[Session] = None
    ) -> Optional[models.Patient]:
        """Update patient lifestyle preferences"""
        updates = {}
        if wake_time:
            updates['wake_time'] = wake_time
        if sleep_time:
            updates['sleep_time'] = sleep_time
        if breakfast_time:
            updates['breakfast_time'] = breakfast_time
        if lunch_time:
            updates['lunch_time'] = lunch_time
        if dinner_time:
            updates['dinner_time'] = dinner_time
        
        return await self.update_patient(patient_id, updates, db)
    
    async def get_all_patients(
        self,
        active_only: bool = True,
        skip: int = 0,
        limit: int = 100,
        db: Optional[Session] = None
    ) -> List[models.Patient]:
        """Get all patients with pagination"""
        def _get_all(session: Session) -> List[models.Patient]:
            query = session.query(models.Patient)
            
            if active_only:
                query = query.filter(models.Patient.is_active == True)
            
            return query.offset(skip).limit(limit).all()
        
        if db:
            return _get_all(db)
        
        with get_db_context() as session:
            return _get_all(session)
    
    async def search_patients(
        self,
        search_term: str,
        db: Optional[Session] = None
    ) -> List[models.Patient]:
        """Search patients by name or email"""
        def _search(session: Session) -> List[models.Patient]:
            term = f"%{search_term}%"
            return session.query(models.Patient).filter(
                or_(
                    models.Patient.first_name.ilike(term),
                    models.Patient.last_name.ilike(term),
                    models.Patient.email.ilike(term)
                )
            ).all()
        
        if db:
            return _search(db)
        
        with get_db_context() as session:
            return _search(session)
    
    async def get_patient_summary(
        self,
        patient_id: int,
        db: Optional[Session] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive patient summary
        
        Returns summary including medications, adherence, recent symptoms, etc.
        """
        def _get_summary(session: Session) -> Optional[Dict[str, Any]]:
            patient = session.query(models.Patient).filter(
                models.Patient.id == patient_id
            ).first()
            
            if not patient:
                return None
            
            # Count medications
            medication_count = session.query(models.Medication).filter(
                and_(
                    models.Medication.patient_id == patient_id,
                    models.Medication.active == True
                )
            ).count()
            
            # Get recent adherence (last 7 days)
            week_ago = datetime.utcnow() - timedelta(days=7)
            adherence_logs = session.query(models.AdherenceLog).filter(
                and_(
                    models.AdherenceLog.patient_id == patient_id,
                    models.AdherenceLog.scheduled_time >= week_ago
                )
            ).all()
            
            total_doses = len(adherence_logs)
            taken_doses = sum(1 for log in adherence_logs if log.taken)
            adherence_rate = (taken_doses / total_doses * 100) if total_doses > 0 else 0
            
            # Get recent symptoms
            recent_symptoms = session.query(models.SymptomReport).filter(
                and_(
                    models.SymptomReport.patient_id == patient_id,
                    models.SymptomReport.reported_at >= week_ago
                )
            ).count()
            
            # Get active barriers
            active_barriers = session.query(models.BarrierResolution).filter(
                and_(
                    models.BarrierResolution.patient_id == patient_id,
                    models.BarrierResolution.resolved == False
                )
            ).count()
            
            return {
                "patient_id": patient.id,
                "name": patient.full_name,
                "email": patient.email,
                "age": patient.age,
                "conditions": patient.conditions,
                "allergies": patient.allergies,
                "active_medications": medication_count,
                "weekly_adherence_rate": round(adherence_rate, 1),
                "recent_symptoms": recent_symptoms,
                "active_barriers": active_barriers,
                "member_since": patient.created_at.isoformat() if patient.created_at else None
            }
        
        if db:
            return _get_summary(db)

        with get_db_context() as session:
            return _get_summary(session)
    
    async def deactivate_patient(
        self,
        patient_id: int,
        db: Optional[Session] = None
    ) -> bool:
        """Deactivate a patient (soft delete)"""
        result = await self.update_patient(patient_id, {'is_active': False}, db)
        return result is not None
    
    async def get_patient_conditions(
        self,
        patient_id: int,
        db: Optional[Session] = None
    ) -> List[str]:
        """Get patient's medical conditions"""
        patient = await self.get_patient(patient_id, db)
        if patient:
            return patient.conditions if isinstance(patient.conditions, list) else []
        return []
    
    async def add_condition(
        self,
        patient_id: int,
        condition: str,
        db: Optional[Session] = None
    ) -> Optional[models.Patient]:
        """Add a medical condition to patient"""
        def _add(session: Session) -> Optional[models.Patient]:
            patient = session.query(models.Patient).filter(
                models.Patient.id == patient_id
            ).first()
            
            if not patient:
                return None
            
            conditions = patient.conditions if isinstance(patient.conditions, list) else []
            if condition not in conditions:
                conditions.append(condition)
                patient.conditions = conditions
                session.commit()
                session.refresh(patient)
            
            return patient
        
        if db:
            return _add(db)
        
        with get_db_context() as session:
            return _add(session)
    
    async def add_allergy(
        self,
        patient_id: int,
        allergy: str,
        db: Optional[Session] = None
    ) -> Optional[models.Patient]:
        """Add a drug allergy to patient"""
        def _add(session: Session) -> Optional[models.Patient]:
            patient = session.query(models.Patient).filter(
                models.Patient.id == patient_id
            ).first()
            
            if not patient:
                return None
            
            allergies = patient.allergies if isinstance(patient.allergies, list) else []
            if allergy not in allergies:
                allergies.append(allergy)
                patient.allergies = allergies
                session.commit()
                session.refresh(patient)
            
            return patient
        
        if db:
            return _add(db)
        
        with get_db_context() as session:
            return _add(session)


# Singleton instance
patient_service = PatientService()
