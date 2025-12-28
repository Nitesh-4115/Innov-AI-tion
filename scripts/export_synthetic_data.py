#!/usr/bin/env python
"""
Export Synthetic Data
Script to export synthetic patient data to JSON files for reference
"""

import sys
import os
import json
import logging
from pathlib import Path
from datetime import datetime, date
from typing import Dict, List, Any

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models import Patient, Medication, Schedule, AdherenceLog, SymptomReport

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def json_serializer(obj):
    """Custom JSON serializer for dates and datetimes"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def export_patients(db, output_dir: Path) -> int:
    """Export all patients to JSON"""
    patients = db.query(Patient).all()
    
    patients_data = []
    for p in patients:
        patients_data.append({
            "id": p.id,
            "first_name": p.first_name,
            "last_name": p.last_name,
            "email": p.email,
            "phone": p.phone,
            "date_of_birth": p.date_of_birth,
            "age": p.age,
            "timezone": p.timezone,
            "conditions": p.conditions,
            "allergies": p.allergies,
            "is_active": p.is_active,
            "created_at": p.created_at
        })
    
    file_path = output_dir / "patients.json"
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(patients_data, f, indent=2, default=json_serializer)
    
    logger.info(f"Exported {len(patients_data)} patients to {file_path}")
    return len(patients_data)


def export_medications(db, output_dir: Path) -> int:
    """Export all medications to JSON"""
    medications = db.query(Medication).all()
    
    meds_data = []
    for m in medications:
        meds_data.append({
            "id": m.id,
            "patient_id": m.patient_id,
            "name": m.name,
            "dosage": m.dosage,
            "frequency": m.frequency,
            "instructions": m.instructions,
            "purpose": m.purpose,
            "start_date": m.start_date,
            "active": m.active,
            "with_food": m.with_food
        })
    
    file_path = output_dir / "medications.json"
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(meds_data, f, indent=2, default=json_serializer)
    
    logger.info(f"Exported {len(meds_data)} medications to {file_path}")
    return len(meds_data)


def export_adherence_summary(db, output_dir: Path) -> Dict:
    """Export adherence summary statistics"""
    patients = db.query(Patient).all()
    
    summary = {
        "total_patients": len(patients),
        "overall_adherence_rate": 0.0,
        "by_profile": {},
        "by_medication": {},
        "patient_summaries": []
    }
    
    total_taken = 0
    total_logs = 0
    
    for patient in patients:
        logs = db.query(AdherenceLog).filter(AdherenceLog.patient_id == patient.id).all()
        meds = db.query(Medication).filter(Medication.patient_id == patient.id).all()
        
        taken = sum(1 for log in logs if log.taken)
        total = len(logs)
        
        total_taken += taken
        total_logs += total
        
        rate = (taken / total * 100) if total > 0 else 0
        
        patient_summary = {
            "patient_id": patient.id,
            "name": f"{patient.first_name} {patient.last_name}",
            "medications": len(meds),
            "total_doses": total,
            "doses_taken": taken,
            "adherence_rate": round(rate, 1)
        }
        summary["patient_summaries"].append(patient_summary)
        
        # By medication
        for med in meds:
            med_logs = [log for log in logs if log.medication_id == med.id]
            med_taken = sum(1 for log in med_logs if log.taken)
            med_total = len(med_logs)
            med_rate = (med_taken / med_total * 100) if med_total > 0 else 0
            
            if med.name not in summary["by_medication"]:
                summary["by_medication"][med.name] = {
                    "patients": 0,
                    "total_doses": 0,
                    "doses_taken": 0
                }
            
            summary["by_medication"][med.name]["patients"] += 1
            summary["by_medication"][med.name]["total_doses"] += med_total
            summary["by_medication"][med.name]["doses_taken"] += med_taken
    
    # Calculate overall and medication rates
    summary["overall_adherence_rate"] = round((total_taken / total_logs * 100) if total_logs > 0 else 0, 1)
    
    for med_name, med_data in summary["by_medication"].items():
        med_data["adherence_rate"] = round(
            (med_data["doses_taken"] / med_data["total_doses"] * 100) 
            if med_data["total_doses"] > 0 else 0, 1
        )
    
    file_path = output_dir / "adherence_summary.json"
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)
    
    logger.info(f"Exported adherence summary to {file_path}")
    return summary


def export_symptom_reports(db, output_dir: Path) -> int:
    """Export symptom reports to JSON"""
    symptoms = db.query(SymptomReport).all()
    
    symptoms_data = []
    for s in symptoms:
        symptoms_data.append({
            "id": s.id,
            "patient_id": s.patient_id,
            "symptom": s.symptom,
            "severity": s.severity,
            "description": s.description,
            "reported_at": s.reported_at
        })
    
    file_path = output_dir / "symptom_reports.json"
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(symptoms_data, f, indent=2, default=json_serializer)
    
    logger.info(f"Exported {len(symptoms_data)} symptom reports to {file_path}")
    return len(symptoms_data)


def main():
    print("\n" + "="*60)
    print("Synthetic Data Export")
    print("="*60)
    
    output_dir = Path("data/synthetic")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    db = SessionLocal()
    
    try:
        # Export all data
        patients_count = export_patients(db, output_dir)
        meds_count = export_medications(db, output_dir)
        summary = export_adherence_summary(db, output_dir)
        symptoms_count = export_symptom_reports(db, output_dir)
        
        print("\n" + "="*60)
        print("Export Complete!")
        print("="*60)
        print(f"\nOutput directory: {output_dir}")
        print(f"\nPatients: {patients_count}")
        print(f"Medications: {meds_count}")
        print(f"Symptom Reports: {symptoms_count}")
        print(f"Overall Adherence Rate: {summary['overall_adherence_rate']}%")
        
        # Show adherence by medication
        print("\nAdherence by Medication:")
        for med_name, med_data in sorted(
            summary["by_medication"].items(), 
            key=lambda x: x[1]["adherence_rate"]
        ):
            print(f"  {med_name}: {med_data['adherence_rate']}% ({med_data['patients']} patients)")
        
    finally:
        db.close()


if __name__ == "__main__":
    main()
