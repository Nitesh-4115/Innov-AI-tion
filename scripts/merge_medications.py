#!/usr/bin/env python3
"""
Merge duplicate medications for a patient by name.
Usage: python scripts/merge_medications.py <patient_id> "Medication Name"
"""
import sys
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from database import get_db_context, init_db
import models


def merge_medications(patient_id: int, name: str):
    init_db()
    with get_db_context() as db:
        meds = db.query(models.Medication).filter(
            models.Medication.patient_id == patient_id,
            models.Medication.name.ilike(f"%{name}%")
        ).order_by(models.Medication.id.asc()).all()

        if not meds or len(meds) == 1:
            print('No duplicates found to merge')
            return

        # Prefer medication with recurring_times populated as primary
        primary = None
        for m in meds:
            if m.recurring_times:
                primary = m
                break
        if not primary:
            primary = meds[0]

        print(f'Primary medication chosen: id={primary.id} name={primary.name} recurring_times={primary.recurring_times}')

        to_merge = [m for m in meds if m.id != primary.id]
        merged_schedule_ids = []
        merged_log_ids = []

        for dup in to_merge:
            print(f'Merging duplicate med id={dup.id} name={dup.name}')
            # Reassign schedules
            schedules = db.query(models.Schedule).filter(models.Schedule.medication_id == dup.id).all()
            for s in schedules:
                # If a schedule with same date/time already exists for primary, merge logs and delete duplicate
                exists = db.query(models.Schedule).filter(
                    models.Schedule.patient_id == s.patient_id,
                    models.Schedule.medication_id == primary.id,
                    models.Schedule.scheduled_date == s.scheduled_date,
                    models.Schedule.scheduled_time == s.scheduled_time
                ).first()
                if exists:
                    # Reassign adherence logs to existing schedule
                    logs = db.query(models.AdherenceLog).filter(models.AdherenceLog.schedule_id == s.id).all()
                    for l in logs:
                        l.schedule_id = exists.id
                        db.add(l)
                        db.commit()
                        merged_log_ids.append(l.id)
                    # Delete duplicate schedule
                    db.delete(s)
                    db.commit()
                    continue

                # Otherwise reassign to primary
                s.medication_id = primary.id
                ml = s.medications_list or []
                if primary.name not in ml:
                    ml = [primary.name] + [x for x in ml if x != primary.name]
                    s.medications_list = ml
                db.add(s)
                db.commit()
                merged_schedule_ids.append(s.id)

            # Reassign adherence logs
            logs = db.query(models.AdherenceLog).filter(models.AdherenceLog.medication_id == dup.id).all()
            for l in logs:
                l.medication_id = primary.id
                db.add(l)
                db.commit()
                merged_log_ids.append(l.id)

            # Optionally merge recurring_times into primary
            if dup.recurring_times:
                rt_primary = primary.recurring_times or []
                for t in dup.recurring_times:
                    if t not in rt_primary:
                        rt_primary.append(t)
                primary.recurring_times = rt_primary
                db.add(primary)
                db.commit()

            # Delete duplicate medication
            db.delete(dup)
            db.commit()
            print(f'  Deleted duplicate med id={dup.id}')

        db.refresh(primary)
        print(f'Merge complete. Primary med id={primary.id} now has recurring_times={primary.recurring_times}')
        print(f'Merged schedules: {merged_schedule_ids}')
        print(f'Merged adherence logs: {merged_log_ids}')


def main():
    if len(sys.argv) < 3:
        print('Usage: python scripts/merge_medications.py <patient_id> "Medication Name"')
        return
    pid = int(sys.argv[1])
    name = sys.argv[2]
    merge_medications(pid, name)


if __name__ == '__main__':
    main()
