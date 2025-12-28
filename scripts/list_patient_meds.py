#!/usr/bin/env python3
"""
List medications and schedules for patient Emma Johansson (or patient id provided)
Run: python scripts/list_patient_meds.py [patient_id]
"""
import sys
import os
from datetime import date

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from database import get_db_context, init_db
import models


def main():
    init_db()
    pid = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    with get_db_context() as db:
        patient = db.query(models.Patient).filter(models.Patient.id == pid).first()
        if not patient:
            print('Patient not found')
            return
        print(f'Patient: {patient.full_name} (id={patient.id}) timezone={patient.timezone}')
        meds = db.query(models.Medication).filter(models.Medication.patient_id == pid).all()
        print('Medications:')
        for m in meds:
            print(f' - id={m.id} name={m.name} dosage={m.dosage} freq={m.frequency} recurring_times={m.recurring_times}')
        scheds = db.query(models.Schedule).filter(models.Schedule.patient_id == pid).order_by(models.Schedule.scheduled_date, models.Schedule.scheduled_time).all()
        print('Schedules:')
        for s in scheds:
            print(f' - id={s.id} med_id={s.medication_id} date={s.scheduled_date} time={s.scheduled_time} status={s.status} meds_list={s.medications_list}')

if __name__ == '__main__':
    main()
