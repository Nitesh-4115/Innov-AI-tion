#!/usr/bin/env python3
"""
Deduplicate schedule rows for a patient (same patient_id, medication_id, scheduled_date, scheduled_time).
Usage: python scripts/dedupe_schedules.py [patient_id]
"""
import sys
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from database import get_db_context, init_db
import models


def dedupe_patient(patient_id: int):
    init_db()
    with get_db_context() as db:
        # Find groups with duplicates
        from sqlalchemy import func
        groups = db.query(
            models.Schedule.patient_id,
            models.Schedule.medication_id,
            models.Schedule.scheduled_date,
            models.Schedule.scheduled_time,
            func.count(models.Schedule.id).label('cnt')
        ).filter(models.Schedule.patient_id == patient_id).group_by(
            models.Schedule.patient_id,
            models.Schedule.medication_id,
            models.Schedule.scheduled_date,
            models.Schedule.scheduled_time
        ).having(func.count(models.Schedule.id) > 1).all()

        if not groups:
            print('No duplicate schedules found for patient', patient_id)
            return

        for g in groups:
            pid, mid, sdate, stime, cnt = g
            print(f'Deduping for med_id={mid} date={sdate} time={stime} (count={cnt})')
            rows = db.query(models.Schedule).filter(
                models.Schedule.patient_id == pid,
                models.Schedule.medication_id == mid,
                models.Schedule.scheduled_date == sdate,
                models.Schedule.scheduled_time == stime
            ).order_by(models.Schedule.id.asc()).all()

            # Keep the first (lowest id)
            keeper = rows[0]
            to_remove = rows[1:]
            print(f'  Keeper id={keeper.id}; removing {[r.id for r in to_remove]}')

            for r in to_remove:
                # Move adherence logs to keeper
                logs = db.query(models.AdherenceLog).filter(models.AdherenceLog.schedule_id == r.id).all()
                for l in logs:
                    l.schedule_id = keeper.id
                    db.add(l)
                db.commit()

                # Delete the duplicate schedule
                db.delete(r)
                db.commit()
                print(f'   Deleted schedule id={r.id}')

        print('Deduplication complete')


if __name__ == '__main__':
    pid = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    dedupe_patient(pid)
