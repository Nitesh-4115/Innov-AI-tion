#!/usr/bin/env python
"""
Generate Synthetic Patients
Script to generate synthetic patient data for testing and development
"""

import sys
import os
import random
import argparse
from datetime import datetime, timedelta, time
from typing import List, Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, engine, Base
from models import (
    Patient, Medication, Schedule, 
    AdherenceLog, SymptomReport,
    AdherenceStatus
)


# Synthetic data pools
FIRST_NAMES = [
    "James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda",
    "William", "Elizabeth", "David", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
    "Thomas", "Sarah", "Charles", "Karen", "Christopher", "Nancy", "Daniel", "Lisa",
    "Matthew", "Betty", "Anthony", "Margaret", "Mark", "Sandra", "Donald", "Ashley",
    "Steven", "Kimberly", "Paul", "Emily", "Andrew", "Donna", "Joshua", "Michelle"
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson"
]

CONDITIONS = [
    {"name": "Type 2 Diabetes", "icd_code": "E11.9", "severity": "moderate"},
    {"name": "Hypertension", "icd_code": "I10", "severity": "moderate"},
    {"name": "Hyperlipidemia", "icd_code": "E78.5", "severity": "mild"},
    {"name": "Major Depressive Disorder", "icd_code": "F32.9", "severity": "moderate"},
    {"name": "Generalized Anxiety Disorder", "icd_code": "F41.1", "severity": "mild"},
    {"name": "Hypothyroidism", "icd_code": "E03.9", "severity": "mild"},
    {"name": "GERD", "icd_code": "K21.0", "severity": "mild"},
    {"name": "Chronic Pain", "icd_code": "G89.29", "severity": "moderate"},
    {"name": "Atrial Fibrillation", "icd_code": "I48.91", "severity": "moderate"},
    {"name": "COPD", "icd_code": "J44.9", "severity": "moderate"},
    {"name": "Asthma", "icd_code": "J45.909", "severity": "mild"},
    {"name": "Osteoarthritis", "icd_code": "M19.90", "severity": "moderate"}
]

MEDICATIONS_BY_CONDITION = {
    "Type 2 Diabetes": [
        {"name": "Metformin", "dosage": "500mg", "frequency": "twice daily", "times": ["08:00", "18:00"]},
        {"name": "Metformin", "dosage": "1000mg", "frequency": "twice daily", "times": ["08:00", "18:00"]},
        {"name": "Glipizide", "dosage": "5mg", "frequency": "once daily", "times": ["08:00"]},
    ],
    "Hypertension": [
        {"name": "Lisinopril", "dosage": "10mg", "frequency": "once daily", "times": ["08:00"]},
        {"name": "Lisinopril", "dosage": "20mg", "frequency": "once daily", "times": ["08:00"]},
        {"name": "Amlodipine", "dosage": "5mg", "frequency": "once daily", "times": ["08:00"]},
        {"name": "Metoprolol", "dosage": "25mg", "frequency": "twice daily", "times": ["08:00", "20:00"]},
    ],
    "Hyperlipidemia": [
        {"name": "Atorvastatin", "dosage": "20mg", "frequency": "once daily", "times": ["21:00"]},
        {"name": "Atorvastatin", "dosage": "40mg", "frequency": "once daily", "times": ["21:00"]},
        {"name": "Simvastatin", "dosage": "20mg", "frequency": "once daily", "times": ["21:00"]},
    ],
    "Major Depressive Disorder": [
        {"name": "Sertraline", "dosage": "50mg", "frequency": "once daily", "times": ["08:00"]},
        {"name": "Sertraline", "dosage": "100mg", "frequency": "once daily", "times": ["08:00"]},
        {"name": "Escitalopram", "dosage": "10mg", "frequency": "once daily", "times": ["08:00"]},
    ],
    "Generalized Anxiety Disorder": [
        {"name": "Sertraline", "dosage": "50mg", "frequency": "once daily", "times": ["08:00"]},
        {"name": "Buspirone", "dosage": "10mg", "frequency": "twice daily", "times": ["08:00", "20:00"]},
    ],
    "Hypothyroidism": [
        {"name": "Levothyroxine", "dosage": "50mcg", "frequency": "once daily", "times": ["06:00"]},
        {"name": "Levothyroxine", "dosage": "75mcg", "frequency": "once daily", "times": ["06:00"]},
        {"name": "Levothyroxine", "dosage": "100mcg", "frequency": "once daily", "times": ["06:00"]},
    ],
    "GERD": [
        {"name": "Omeprazole", "dosage": "20mg", "frequency": "once daily", "times": ["08:00"]},
        {"name": "Omeprazole", "dosage": "40mg", "frequency": "once daily", "times": ["08:00"]},
        {"name": "Pantoprazole", "dosage": "40mg", "frequency": "once daily", "times": ["08:00"]},
    ],
    "Chronic Pain": [
        {"name": "Gabapentin", "dosage": "300mg", "frequency": "three times daily", "times": ["08:00", "14:00", "20:00"]},
        {"name": "Acetaminophen", "dosage": "500mg", "frequency": "as needed", "times": ["08:00", "14:00", "20:00"]},
    ],
    "Atrial Fibrillation": [
        {"name": "Warfarin", "dosage": "5mg", "frequency": "once daily", "times": ["18:00"]},
        {"name": "Metoprolol", "dosage": "50mg", "frequency": "twice daily", "times": ["08:00", "20:00"]},
    ],
    "COPD": [
        {"name": "Tiotropium", "dosage": "18mcg", "frequency": "once daily", "times": ["08:00"]},
        {"name": "Albuterol", "dosage": "90mcg", "frequency": "as needed", "times": []},
    ],
    "Asthma": [
        {"name": "Fluticasone", "dosage": "110mcg", "frequency": "twice daily", "times": ["08:00", "20:00"]},
        {"name": "Albuterol", "dosage": "90mcg", "frequency": "as needed", "times": []},
    ],
    "Osteoarthritis": [
        {"name": "Celecoxib", "dosage": "200mg", "frequency": "once daily", "times": ["08:00"]},
        {"name": "Acetaminophen", "dosage": "500mg", "frequency": "as needed", "times": []},
    ]
}

SYMPTOMS = [
    "Headache", "Nausea", "Dizziness", "Fatigue", "Muscle pain",
    "Joint pain", "Stomach upset", "Dry mouth", "Drowsiness",
    "Insomnia", "Anxiety", "Constipation", "Diarrhea", "Rash",
    "Cough", "Shortness of breath", "Swelling", "Weight gain"
]

ADHERENCE_PROFILES = {
    "excellent": {"base_rate": 0.95, "variance": 0.03},
    "good": {"base_rate": 0.85, "variance": 0.08},
    "moderate": {"base_rate": 0.70, "variance": 0.12},
    "poor": {"base_rate": 0.50, "variance": 0.15},
    "very_poor": {"base_rate": 0.30, "variance": 0.15}
}


def generate_phone() -> str:
    """Generate random US phone number"""
    return f"+1{random.randint(200, 999)}{random.randint(100, 999)}{random.randint(1000, 9999)}"


def generate_email(first_name: str, last_name: str) -> str:
    """Generate email from name"""
    domains = ["gmail.com", "yahoo.com", "outlook.com", "email.com"]
    suffix = random.randint(1, 999)
    return f"{first_name.lower()}.{last_name.lower()}{suffix}@{random.choice(domains)}"


def generate_dob(min_age: int = 25, max_age: int = 85) -> datetime:
    """Generate random date of birth"""
    today = datetime.now()
    age = random.randint(min_age, max_age)
    days_offset = random.randint(0, 365)
    return today - timedelta(days=age * 365 + days_offset)


def select_conditions(count: int = None) -> List[Dict]:
    """Select random conditions for a patient"""
    if count is None:
        count = random.choices([1, 2, 3, 4], weights=[30, 40, 20, 10])[0]
    return random.sample(CONDITIONS, min(count, len(CONDITIONS)))


def select_adherence_profile() -> str:
    """Select adherence profile with weighted distribution"""
    profiles = ["excellent", "good", "moderate", "poor", "very_poor"]
    weights = [15, 35, 30, 15, 5]
    return random.choices(profiles, weights=weights)[0]


def should_take_dose(profile: str, day_of_week: int, hour: int) -> bool:
    """Determine if dose should be taken based on profile and patterns"""
    config = ADHERENCE_PROFILES[profile]
    base_prob = config["base_rate"]
    variance = config["variance"]
    
    prob = base_prob + random.uniform(-variance, variance)
    
    # Weekend effect (slightly lower adherence)
    if day_of_week >= 5:
        prob -= 0.05
    
    # Time of day effect
    if hour < 7 or hour > 21:
        prob -= 0.08
    
    # Morning rush effect
    if 7 <= hour <= 9:
        prob -= 0.03
    
    return random.random() < max(0, min(1, prob))


def generate_patient(db, patient_num: int, days_of_history: int = 30) -> Patient:
    """Generate a single synthetic patient with full data"""
    
    first_name = random.choice(FIRST_NAMES)
    last_name = random.choice(LAST_NAMES)
    
    # Create patient
    patient = Patient(
        first_name=first_name,
        last_name=last_name,
        date_of_birth=generate_dob(),
        email=generate_email(first_name, last_name),
        phone=generate_phone(),
        timezone="America/New_York",
        is_active=True
    )
    db.add(patient)
    db.flush()  # Get patient ID
    
    # Select conditions and adherence profile
    conditions = select_conditions()
    adherence_profile = select_adherence_profile()
    
    print(f"  Patient {patient_num}: {first_name} {last_name}")
    print(f"    Conditions: {[c['name'] for c in conditions]}")
    print(f"    Adherence Profile: {adherence_profile}")
    
    # Note: Store conditions in patient notes (no separate HealthCondition model)
    patient.notes = f"Conditions: {', '.join([c['name'] for c in conditions])}"
    
    # Add medications based on conditions
    medications = []
    for cond in conditions:
        cond_name = cond["name"]
        if cond_name in MEDICATIONS_BY_CONDITION:
            med_options = MEDICATIONS_BY_CONDITION[cond_name]
            med_data = random.choice(med_options)
            
            # Check if medication already added
            if not any(m.name == med_data["name"] for m in medications):
                medication = Medication(
                    patient_id=patient.id,
                    name=med_data["name"],
                    dosage=med_data["dosage"],
                    frequency=med_data["frequency"],
                    instructions=f"Take {med_data['dosage']} {med_data['frequency']}",
                    purpose=cond_name,
                    start_date=datetime.now().date() - timedelta(days=random.randint(30, 365)),
                    active=True,
                    with_food=med_data["name"].lower() in ["metformin", "ibuprofen", "naproxen"]
                )
                db.add(medication)
                db.flush()
                medications.append(medication)
                
                # Add schedules for next 60 days
                for day_offset in range(days_of_history):
                    schedule_date = datetime.now().date() - timedelta(days=day_offset)
                    for time_str in med_data["times"]:
                        schedule = Schedule(
                            patient_id=patient.id,
                            medication_id=medication.id,
                            scheduled_date=schedule_date,
                            scheduled_time=time_str,
                            medications_list=[med_data["name"]],
                            meal_relation="with" if med_data["name"] in ["metformin", "ibuprofen"] else None,
                            status="pending"
                        )
                        db.add(schedule)
    
    db.flush()
    
    # Generate adherence history
    today = datetime.now().date()
    adherence_records = []
    
    for med in medications:
        schedules = db.query(Schedule).filter(
            Schedule.medication_id == med.id
        ).all()
        
        for schedule in schedules:
            hour = int(schedule.scheduled_time.split(":")[0])
            record_date = schedule.scheduled_date
            scheduled_dt = datetime.combine(record_date, time(hour=hour))
            
            taken = should_take_dose(
                adherence_profile,
                record_date.weekday(),
                hour
            )
            
            taken_at = None
            delay_minutes = None
            if taken:
                # Add some variance to taken time
                variance_minutes = random.randint(-30, 60)
                taken_at = scheduled_dt + timedelta(minutes=variance_minutes)
                delay_minutes = max(0, variance_minutes)
            
            # Update schedule status
            if taken:
                schedule.status = "taken"
            else:
                schedule.status = "missed"
            
            status = AdherenceStatus.TAKEN if taken else AdherenceStatus.MISSED
            if taken and delay_minutes and delay_minutes > 30:
                status = AdherenceStatus.DELAYED
            
            record = AdherenceLog(
                patient_id=patient.id,
                medication_id=med.id,
                scheduled_time=scheduled_dt,
                actual_time=taken_at,
                deviation_minutes=delay_minutes,
                status=status,
                taken=taken,
                logged_by="synthetic"
            )
            adherence_records.append(record)
    
    db.bulk_save_objects(adherence_records)
    
    # Generate some symptom reports
    num_symptoms = random.randint(0, 5)
    for _ in range(num_symptoms):
        symptom = SymptomReport(
            patient_id=patient.id,
            symptom=random.choice(SYMPTOMS),
            severity=random.randint(1, 10),
            reported_at=datetime.now() - timedelta(
                days=random.randint(0, days_of_history),
                hours=random.randint(0, 23)
            ),
            description="Synthetic data for testing"
        )
        db.add(symptom)
    
    return patient


def generate_synthetic_patients(
    num_patients: int = 10,
    days_of_history: int = 30,
    clear_existing: bool = False
):
    """Generate synthetic patients"""
    
    print(f"\n{'='*60}")
    print("Synthetic Patient Generator")
    print(f"{'='*60}")
    print(f"Generating {num_patients} patients with {days_of_history} days of history")
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        if clear_existing:
            print("\nClearing existing data...")
            db.query(AdherenceLog).delete()
            db.query(SymptomReport).delete()
            db.query(Schedule).delete()
            db.query(Medication).delete()
            db.query(Patient).delete()
            db.commit()
            print("Existing data cleared.")
        
        print(f"\nGenerating {num_patients} patients...\n")
        
        patients = []
        for i in range(1, num_patients + 1):
            patient = generate_patient(db, i, days_of_history)
            patients.append(patient)
        
        db.commit()
        
        # Print summary
        print(f"\n{'='*60}")
        print("Generation Complete!")
        print(f"{'='*60}")
        print(f"Patients created: {len(patients)}")
        print(f"Total medications: {db.query(Medication).count()}")
        print(f"Total schedules: {db.query(Schedule).count()}")
        print(f"Total adherence logs: {db.query(AdherenceLog).count()}")
        print(f"Total symptom reports: {db.query(SymptomReport).count()}")
        
        # Adherence summary
        total_records = db.query(AdherenceLog).count()
        taken_records = db.query(AdherenceLog).filter(AdherenceLog.taken == True).count()
        if total_records > 0:
            overall_adherence = (taken_records / total_records) * 100
            print(f"\nOverall adherence rate: {overall_adherence:.1f}%")
        
    except Exception as e:
        db.rollback()
        print(f"\nError: {e}")
        raise
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Generate synthetic patient data for AdherenceGuardian"
    )
    parser.add_argument(
        "-n", "--num-patients",
        type=int,
        default=10,
        help="Number of patients to generate (default: 10)"
    )
    parser.add_argument(
        "-d", "--days",
        type=int,
        default=30,
        help="Days of adherence history to generate (default: 30)"
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing data before generating"
    )
    
    args = parser.parse_args()
    
    generate_synthetic_patients(
        num_patients=args.num_patients,
        days_of_history=args.days,
        clear_existing=args.clear
    )


if __name__ == "__main__":
    main()
