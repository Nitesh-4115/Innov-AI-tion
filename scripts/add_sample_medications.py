"""
Add sample medications and schedules for existing test patients.
Run: python scripts/add_sample_medications.py
"""
import sys
import os
from datetime import date, timedelta

# ensure project root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from database import init_db, get_db_context
import models

# Define meds to add per patient (by patient full name)
PATIENT_MED_MAP = {
    "Aisha Khan": [
        {"name": "Amlodipine", "dosage": "5mg", "frequency": "once daily", "recurring_times": ["08:00"]},
        {"name": "Atorvastatin", "dosage": "20mg", "frequency": "once nightly", "recurring_times": ["21:30"]}
    ],
    "Carlos Mendez": [
        {"name": "Metformin", "dosage": "500mg", "frequency": "twice daily", "recurring_times": ["07:30", "19:00"]},
        {"name": "Lisinopril", "dosage": "10mg", "frequency": "once daily", "recurring_times": ["08:00"]}
    ],
    "Emma Johansson": [
        {"name": "Albuterol", "dosage": "2 puffs", "frequency": "as needed", "recurring_times": ["08:00"]},
        {"name": "Montelukast", "dosage": "10mg", "frequency": "once daily", "recurring_times": ["20:00"]}
    ],
    "Liam O'Connor": [
        {"name": "Sertraline", "dosage": "50mg", "frequency": "once daily", "recurring_times": ["09:00"]},
        {"name": "Vitamin D", "dosage": "1000 IU", "frequency": "once daily", "recurring_times": ["08:00"]}
    ],
    "Sofia Rossi": [
        {"name": "Simvastatin", "dosage": "20mg", "frequency": "once nightly", "recurring_times": ["22:00"]},
        {"name": "Aspirin", "dosage": "81mg", "frequency": "once daily", "recurring_times": ["08:00"]}
    ]
}

DAYS_AHEAD = 2  # create schedules for today + next 2 days


def add_med_and_schedules(db, patient, med_def):
    # check existing medication by name
    existing = db.query(models.Medication).filter(
        models.Medication.patient_id == patient.id,
        models.Medication.name.ilike(f"%{med_def['name']}%")
    ).first()
    if existing:
        med = existing
    else:
        med = models.Medication(
            patient_id=patient.id,
            name=med_def["name"],
            dosage=med_def.get("dosage", "unspecified"),
            frequency=med_def.get("frequency", "once daily"),
            recurring_times=med_def.get("recurring_times", []),
            active=True,
            start_date=date.today()
        )
        db.add(med)
        db.commit()
        db.refresh(med)

    # create schedules for today + next DAYS_AHEAD days
    for offset in range(0, DAYS_AHEAD + 1):
        d = date.today() + timedelta(days=offset)
        for t in med.recurring_times or ["08:00"]:
            # avoid duplicate schedule for same date/time
            exists = db.query(models.Schedule).filter(
                models.Schedule.patient_id == patient.id,
                models.Schedule.medication_id == med.id,
                models.Schedule.scheduled_date == d,
                models.Schedule.scheduled_time == t
            ).first()
            if exists:
                continue
            sched = models.Schedule(
                patient_id=patient.id,
                medication_id=med.id,
                scheduled_date=d,
                scheduled_time=t,
                medications_list=[med.name],
                status="pending",
                notes=f"Auto-generated sample schedule for {patient.full_name}"
            )
            db.add(sched)
    db.commit()
    return med


def main():
    init_db()
    with get_db_context() as db:
        for patient_name, meds in PATIENT_MED_MAP.items():
            # find patient by full_name (first + last)
            parts = patient_name.split()
            first = parts[0]
            last = " ".join(parts[1:]) if len(parts) > 1 else ""
            patient = db.query(models.Patient).filter(
                models.Patient.first_name == first,
                models.Patient.last_name == last
            ).first()
            if not patient:
                print(f"Patient not found: {patient_name}")
                continue
            print(f"Adding meds for {patient.full_name} (id={patient.id})")
            for md in meds:
                med = add_med_and_schedules(db, patient, md)
                print(f" - Added/confirmed medication: {med.name} ({med.dosage})")

    print("Done adding medications and schedules.")

if __name__ == '__main__':
    main()
