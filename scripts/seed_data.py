#!/usr/bin/env python
"""
Seed Data
Script to seed the database with initial data for development and testing
"""

import sys
import os
import argparse
import logging
import random
from datetime import datetime, timedelta, time, date
from typing import List, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, engine, Base
from models import (
    Patient, Medication, Schedule, 
    AdherenceLog, SymptomReport, AdherenceStatus
)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_tables():
    """Create all database tables"""
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Tables created successfully")


def seed_demo_patient(db) -> Patient:
    """Create a demo patient with full data"""
    logger.info("Creating demo patient...")
    
    # Check if demo patient exists
    existing = db.query(Patient).filter(Patient.email == "demo@adherenceguardian.com").first()
    if existing:
        logger.info("Demo patient already exists")
        return existing
    
    # Create patient
    patient = Patient(
        first_name="John",
        last_name="Doe",
        date_of_birth=date(1965, 5, 15),
        email="demo@adherenceguardian.com",
        phone="+15551234567",
        timezone="America/New_York",
        conditions=["Type 2 Diabetes", "Hypertension", "Hyperlipidemia"],
        allergies=["Penicillin"],
        wake_time=time(7, 0),
        sleep_time=time(22, 0),
        breakfast_time=time(8, 0),
        lunch_time=time(12, 0),
        dinner_time=time(19, 0),
        is_active=True
    )
    db.add(patient)
    db.flush()
    
    logger.info(f"Created patient: {patient.first_name} {patient.last_name} (ID: {patient.id})")
    
    return patient


def seed_medications(db, patient_id: int) -> List[Medication]:
    """Add medications for a patient"""
    logger.info("Adding medications...")
    
    medications_data = [
        {
            "name": "Metformin",
            "generic_name": "metformin hydrochloride",
            "dosage": "1000mg",
            "dosage_form": "tablet",
            "frequency": "twice daily",
            "frequency_per_day": 2,
            "instructions": "Take with meals to reduce stomach upset",
            "with_food": True,
            "purpose": "Blood sugar control for Type 2 Diabetes",
            "rxnorm_id": "860975"
        },
        {
            "name": "Lisinopril",
            "generic_name": "lisinopril",
            "dosage": "20mg",
            "dosage_form": "tablet",
            "frequency": "once daily",
            "frequency_per_day": 1,
            "instructions": "Take in the morning",
            "with_food": False,
            "purpose": "Blood pressure control",
            "rxnorm_id": "314076"
        },
        {
            "name": "Atorvastatin",
            "generic_name": "atorvastatin calcium",
            "dosage": "40mg",
            "dosage_form": "tablet",
            "frequency": "once daily",
            "frequency_per_day": 1,
            "instructions": "Take at bedtime for best effectiveness",
            "with_food": False,
            "purpose": "Cholesterol management",
            "rxnorm_id": "617312"
        },
        {
            "name": "Aspirin",
            "generic_name": "aspirin",
            "dosage": "81mg",
            "dosage_form": "tablet",
            "frequency": "once daily",
            "frequency_per_day": 1,
            "instructions": "Take with food",
            "with_food": True,
            "purpose": "Cardiovascular protection",
            "rxnorm_id": "1191"
        }
    ]
    
    medications = []
    for med_data in medications_data:
        medication = Medication(
            patient_id=patient_id,
            name=med_data["name"],
            generic_name=med_data["generic_name"],
            dosage=med_data["dosage"],
            dosage_form=med_data["dosage_form"],
            frequency=med_data["frequency"],
            frequency_per_day=med_data["frequency_per_day"],
            instructions=med_data["instructions"],
            with_food=med_data["with_food"],
            purpose=med_data["purpose"],
            rxnorm_id=med_data["rxnorm_id"],
            start_date=date.today() - timedelta(days=180),
            active=True
        )
        db.add(medication)
        db.flush()
        medications.append(medication)
        logger.info(f"  Added: {medication.name} ({medication.dosage})")
    
    return medications


def seed_schedules(db, patient_id: int, medications: List[Medication], days: int = 30):
    """Create medication schedules"""
    logger.info(f"Creating schedules for {days} days...")
    
    # Define schedule times for each medication
    schedule_times = {
        "Metformin": ["08:00", "18:00"],  # With breakfast and dinner
        "Lisinopril": ["08:00"],  # Morning
        "Atorvastatin": ["21:00"],  # Bedtime
        "Aspirin": ["08:00"],  # With breakfast
    }
    
    today = date.today()
    schedules_created = 0
    
    for medication in medications:
        times = schedule_times.get(medication.name, ["08:00"])
        
        for day_offset in range(days):
            schedule_date = today - timedelta(days=day_offset)
            
            for sched_time in times:
                schedule = Schedule(
                    patient_id=patient_id,
                    medication_id=medication.id,
                    scheduled_date=schedule_date,
                    scheduled_time=sched_time,
                    meal_relation="with" if medication.with_food else None,
                    status="pending" if day_offset == 0 else "taken",  # Today pending, past taken
                )
                db.add(schedule)
                schedules_created += 1
    
    db.flush()
    logger.info(f"Created {schedules_created} schedule entries")


def seed_adherence_history(db, patient_id: int, medications: List[Medication], days: int = 30):
    """Seed adherence history for a patient"""
    logger.info(f"Seeding {days} days of adherence history...")
    
    random.seed(42)  # For reproducibility
    
    today = datetime.now()
    records_created = 0
    
    # Adherence rates by medication
    adherence_rates = {
        "Metformin": 0.88,  # Some GI issues cause misses
        "Lisinopril": 0.92,
        "Atorvastatin": 0.85,  # Evening doses often missed
        "Aspirin": 0.90,
    }
    
    schedule_times = {
        "Metformin": [time(8, 0), time(18, 0)],
        "Lisinopril": [time(8, 0)],
        "Atorvastatin": [time(21, 0)],
        "Aspirin": [time(8, 0)],
    }
    
    for medication in medications:
        base_rate = adherence_rates.get(medication.name, 0.85)
        times = schedule_times.get(medication.name, [time(8, 0)])
        
        for day_offset in range(1, days + 1):  # Skip today
            record_date = today - timedelta(days=day_offset)
            
            for sched_time in times:
                scheduled_dt = datetime.combine(record_date.date(), sched_time)
                
                # Weekend adherence slightly lower
                rate = base_rate - 0.05 if record_date.weekday() >= 5 else base_rate
                taken = random.random() < rate
                
                actual_time = None
                delay = None
                status = AdherenceStatus.MISSED
                
                if taken:
                    # Add variance to actual time
                    variance = random.randint(-10, 45)
                    actual_time = scheduled_dt + timedelta(minutes=variance)
                    delay = max(0, variance)
                    status = AdherenceStatus.TAKEN if delay < 30 else AdherenceStatus.DELAYED
                
                record = AdherenceLog(
                    patient_id=patient_id,
                    medication_id=medication.id,
                    scheduled_time=scheduled_dt,
                    actual_time=actual_time,
                    deviation_minutes=delay,
                    status=status,
                    taken=taken,
                    logged_by="system",
                    confirmation_method="seeded"
                )
                db.add(record)
                records_created += 1
    
    db.flush()
    logger.info(f"Created {records_created} adherence records")


def seed_symptom_reports(db, patient_id: int):
    """Seed some symptom reports for a patient"""
    logger.info("Seeding symptom reports...")
    
    symptoms_data = [
        {
            "symptom": "Nausea",
            "description": "Mild nausea after taking metformin",
            "severity": 3,
            "days_ago": 5,
        },
        {
            "symptom": "Headache",
            "description": "Tension headache, lasted about 2 hours",
            "severity": 4,
            "days_ago": 12,
        },
        {
            "symptom": "Dizziness",
            "description": "Lightheaded when standing up quickly",
            "severity": 2,
            "days_ago": 8,
        },
        {
            "symptom": "Fatigue",
            "description": "Feeling tired in the afternoon",
            "severity": 5,
            "days_ago": 3,
        },
        {
            "symptom": "Muscle aches",
            "description": "Legs feel achy, especially after walking",
            "severity": 3,
            "days_ago": 15,
        },
    ]
    
    for data in symptoms_data:
        reported_at = datetime.now() - timedelta(days=data["days_ago"])
        
        symptom = SymptomReport(
            patient_id=patient_id,
            symptom=data["symptom"],
            description=data["description"],
            severity=data["severity"],
            reported_at=reported_at
        )
        db.add(symptom)
    
    db.flush()
    logger.info(f"Created {len(symptoms_data)} symptom reports")


def seed_all(clear_existing: bool = False):
    """Run all seed operations"""
    
    print("\n" + "="*60)
    print("Database Seeding")
    print("="*60)
    
    # Create tables
    create_tables()
    
    db = SessionLocal()
    
    try:
        if clear_existing:
            logger.info("Clearing existing data...")
            db.query(AdherenceLog).delete()
            db.query(SymptomReport).delete()
            db.query(Schedule).delete()
            db.query(Medication).delete()
            db.query(Patient).delete()
            db.commit()
            logger.info("Existing data cleared")
        
        # Create demo patient
        patient = seed_demo_patient(db)
        db.commit()
        
        # Add medications
        medications = seed_medications(db, patient.id)
        db.commit()
        
        # Create schedules
        seed_schedules(db, patient.id, medications, days=30)
        db.commit()
        
        # Seed adherence history
        seed_adherence_history(db, patient.id, medications, days=30)
        db.commit()
        
        # Seed symptom reports
        seed_symptom_reports(db, patient.id)
        db.commit()
        
        # Print summary
        print("\n" + "="*60)
        print("Seeding Complete!")
        print("="*60)
        print(f"\nDatabase Statistics:")
        print(f"  Patients: {db.query(Patient).count()}")
        print(f"  Medications: {db.query(Medication).count()}")
        print(f"  Schedules: {db.query(Schedule).count()}")
        print(f"  Adherence Records: {db.query(AdherenceLog).count()}")
        print(f"  Symptom Reports: {db.query(SymptomReport).count()}")
        
        # Calculate adherence rate
        total = db.query(AdherenceLog).filter(
            AdherenceLog.patient_id == patient.id
        ).count()
        taken = db.query(AdherenceLog).filter(
            AdherenceLog.patient_id == patient.id,
            AdherenceLog.taken == True
        ).count()
        
        if total > 0:
            print(f"\nDemo Patient Adherence Rate: {(taken/total)*100:.1f}%")
        
        print(f"\nDemo Patient ID: {patient.id}")
        print(f"Demo Patient Email: {patient.email}")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error during seeding: {e}")
        raise
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Seed the database with initial data"
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing data before seeding"
    )
    
    args = parser.parse_args()
    
    seed_all(clear_existing=args.clear)


if __name__ == "__main__":
    main()
