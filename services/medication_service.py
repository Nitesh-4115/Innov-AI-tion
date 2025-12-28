"""
Medication Service
Business logic for medication management
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, date
from sqlalchemy.orm import Session
from sqlalchemy import and_

from database import get_db_context
import models
from tools.drug_database import drug_database, DrugInfo
from tools.interaction_checker import interaction_checker


logger = logging.getLogger(__name__)


class MedicationService:
    """
    Service for medication-related operations
    """
    
    async def add_medication(
        self,
        patient_id: int,
        name: str,
        dosage: str,
        frequency: str,
        frequency_per_day: int = 1,
        generic_name: Optional[str] = None,
        rxnorm_id: Optional[str] = None,
        instructions: Optional[str] = None,
        with_food: bool = False,
        purpose: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        db: Optional[Session] = None
    ) -> models.Medication:
        """
        Add a new medication for a patient
        
        Args:
            patient_id: Patient ID
            name: Medication name
            dosage: Dosage (e.g., "500mg")
            frequency: Frequency description (e.g., "twice daily")
            frequency_per_day: Number of doses per day
            generic_name: Generic drug name
            rxnorm_id: RxNorm concept ID
            instructions: Special instructions
            with_food: Whether to take with food
            purpose: Why medication is prescribed
            start_date: Start date
            end_date: End date (if temporary)
            db: Database session
            
        Returns:
            Created Medication object
        """
        def _add(session: Session) -> models.Medication:
            # Verify patient exists
            patient = session.query(models.Patient).filter(
                models.Patient.id == patient_id
            ).first()
            
            if not patient:
                raise ValueError(f"Patient {patient_id} not found")
            
            # Check for allergies
            if patient.allergies:
                name_lower = name.lower()
                for allergy in patient.allergies:
                    if allergy.lower() in name_lower or name_lower in allergy.lower():
                        raise ValueError(f"Patient has allergy to {allergy}")
            
            medication = models.Medication(
                patient_id=patient_id,
                name=name,
                generic_name=generic_name,
                rxnorm_id=rxnorm_id,
                dosage=dosage,
                frequency=frequency,
                frequency_per_day=frequency_per_day,
                instructions=instructions,
                with_food=with_food,
                purpose=purpose,
                start_date=start_date or date.today(),
                end_date=end_date,
                active=True
            )
            
            session.add(medication)
            session.commit()
            session.refresh(medication)
            
            logger.info(f"Added medication {name} for patient {patient_id}")
            return medication
        
        if db:
            return _add(db)
        
        with get_db_context() as session:
            return _add(session)
    
    async def get_medication(
        self,
        medication_id: int,
        db: Optional[Session] = None
    ) -> Optional[models.Medication]:
        """Get medication by ID"""
        def _get(session: Session) -> Optional[models.Medication]:
            return session.query(models.Medication).filter(
                models.Medication.id == medication_id
            ).first()
        
        if db:
            return _get(db)
        
        with get_db_context() as session:
            return _get(session)
    
    async def get_patient_medications(
        self,
        patient_id: int,
        active_only: bool = True,
        db: Optional[Session] = None
    ) -> List[models.Medication]:
        """Get all medications for a patient"""
        def _get(session: Session) -> List[models.Medication]:
            query = session.query(models.Medication).filter(
                models.Medication.patient_id == patient_id
            )
            
            if active_only:
                query = query.filter(models.Medication.active == True)
            
            return query.all()
        
        if db:
            return _get(db)
        
        with get_db_context() as session:
            return _get(session)
    
    async def update_medication(
        self,
        medication_id: int,
        updates: Dict[str, Any],
        db: Optional[Session] = None
    ) -> Optional[models.Medication]:
        """Update medication information"""
        def _update(session: Session) -> Optional[models.Medication]:
            medication = session.query(models.Medication).filter(
                models.Medication.id == medication_id
            ).first()
            
            if not medication:
                return None
            
            allowed_fields = {
                'name', 'generic_name', 'dosage', 'frequency',
                'frequency_per_day', 'instructions', 'with_food',
                'purpose', 'active', 'end_date', 'notes'
            }
            
            for field, value in updates.items():
                if field in allowed_fields and hasattr(medication, field):
                    setattr(medication, field, value)
            
            medication.updated_at = datetime.utcnow()
            session.commit()
            session.refresh(medication)
            
            return medication
        
        if db:
            return _update(db)
        
        with get_db_context() as session:
            return _update(session)
    
    async def discontinue_medication(
        self,
        medication_id: int,
        reason: Optional[str] = None,
        db: Optional[Session] = None
    ) -> Optional[models.Medication]:
        """Discontinue a medication"""
        updates = {
            'active': False,
            'end_date': date.today()
        }
        if reason:
            updates['notes'] = f"Discontinued: {reason}"
        
        return await self.update_medication(medication_id, updates, db)
    
    async def check_interactions(
        self,
        patient_id: int,
        new_medication: Optional[str] = None,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Check for drug interactions among patient's medications
        
        Args:
            patient_id: Patient ID
            new_medication: Optional new medication to check against existing
            db: Database session
            
        Returns:
            Interaction summary
        """
        medications = await self.get_patient_medications(patient_id, active_only=True, db=db)
        med_names = [m.name for m in medications]
        
        if new_medication:
            med_names.append(new_medication)
        
        # Use interaction checker tool
        summary = interaction_checker.get_interaction_summary(med_names)
        
        return summary
    
    async def get_medication_info(
        self,
        medication_name: str
    ) -> Optional[DrugInfo]:
        """Get detailed drug information"""
        return await drug_database.get_drug_info(medication_name)
    
    async def get_medication_details(
        self,
        medication_id: int,
        db: Optional[Session] = None
    ) -> Optional[Dict[str, Any]]:
        """Get comprehensive medication details including drug info"""
        medication = await self.get_medication(medication_id, db)
        
        if not medication:
            return None
        
        # Get additional drug database info
        drug_info = await drug_database.get_drug_info(medication.name)
        
        details = {
            "id": medication.id,
            "name": medication.name,
            "generic_name": medication.generic_name,
            "dosage": medication.dosage,
            "frequency": medication.frequency,
            "frequency_per_day": medication.frequency_per_day,
            "with_food": medication.with_food,
            "instructions": medication.instructions,
            "purpose": medication.purpose,
            "active": medication.active,
            "start_date": medication.start_date.isoformat() if medication.start_date else None,
            "end_date": medication.end_date.isoformat() if medication.end_date else None
        }
        
        if drug_info:
            details["drug_info"] = {
                "drug_class": drug_info.drug_class,
                "common_side_effects": drug_info.common_side_effects,
                "serious_side_effects": drug_info.serious_side_effects,
                "warnings": drug_info.warnings,
                "food_recommendation": drug_database._get_food_recommendation(drug_info)
            }
        
        return details
    
    async def get_medications_needing_refill(
        self,
        patient_id: int,
        days_threshold: int = 7,
        db: Optional[Session] = None
    ) -> List[Dict[str, Any]]:
        """Get medications that will need refill soon"""
        def _get(session: Session) -> List[Dict[str, Any]]:
            # Get prescriptions with low quantity
            prescriptions = session.query(models.Prescription).filter(
                and_(
                    models.Prescription.patient_id == patient_id,
                    models.Prescription.is_active == True
                )
            ).all()
            
            refill_needed = []
            for rx in prescriptions:
                if rx.quantity_remaining and rx.quantity_remaining <= days_threshold:
                    medication = session.query(models.Medication).filter(
                        models.Medication.id == rx.medication_id
                    ).first()
                    
                    if medication:
                        refill_needed.append({
                            "medication_id": medication.id,
                            "medication_name": medication.name,
                            "quantity_remaining": rx.quantity_remaining,
                            "pharmacy": rx.pharmacy_name,
                            "pharmacy_phone": rx.pharmacy_phone,
                            "refills_remaining": rx.refills_remaining
                        })
            
            return refill_needed
        
        if db:
            return _get(db)
        
        with get_db_context() as session:
            return _get(session)
    
    async def get_medication_schedule_info(
        self,
        patient_id: int,
        db: Optional[Session] = None
    ) -> List[Dict[str, Any]]:
        """Get medication info formatted for scheduling"""
        medications = await self.get_patient_medications(patient_id, active_only=True, db=db)
        
        schedule_info = []
        for med in medications:
            drug_info = await drug_database.get_drug_info(med.name)
            
            info = {
                "medication_id": med.id,
                "name": med.name,
                "dosage": med.dosage,
                "frequency_per_day": med.frequency_per_day,
                "with_food": med.with_food or (drug_info.with_food if drug_info else False),
                "instructions": med.instructions
            }
            
            # Add min hours between doses if available
            if med.min_hours_between_doses:
                info["min_hours_between"] = med.min_hours_between_doses
            elif med.frequency_per_day > 0:
                # Calculate based on frequency
                info["min_hours_between"] = 24 / med.frequency_per_day - 1
            
            schedule_info.append(info)
        
        return schedule_info
    
    async def search_medications(
        self,
        query: str,
        limit: int = 10
    ) -> List[Dict[str, str]]:
        """Search for medications in drug database"""
        return await drug_database.search_drugs(query, limit)
    
    async def get_side_effects(
        self,
        medication_name: str
    ) -> Dict[str, List[str]]:
        """Get side effects for a medication"""
        return await drug_database.get_side_effects(medication_name)
    
    async def get_food_requirements(
        self,
        medication_name: str
    ) -> Dict[str, Any]:
        """Get food requirements for a medication"""
        return await drug_database.get_food_requirements(medication_name)


# Singleton instance
medication_service = MedicationService()
