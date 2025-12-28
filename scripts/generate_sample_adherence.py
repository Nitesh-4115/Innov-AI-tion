"""
Generate sample adherence logs for test patients.
Run: python scripts/generate_sample_adherence.py
"""
import sys
import os
from datetime import datetime, date, time, timedelta

# Ensure project root on sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from database import init_db, get_db_context
import models

# Plan: for each test patient, look back 3 days and create adherence logs for schedules.
# Patient patterns:
# 1: High adherence (mostly on-time)
# 2: Mixed (some missed, some delayed)
# 3: Low (more missed)
# 4: Good (on-time but occasional delay)
# 5: Moderate

PATTERN = {
    1: ["on_time", "on_time", "on_time"],
    2: ["on_time", "delayed", "missed"],
    3: ["missed", "missed", "delayed"],
    4: ["on_time", "delayed", "on_time"],
    5: ["on_time", "missed", "delayed"]
}

DELAY_MAP = {
    "on_time": 0,
    "delayed": 20,
    "missed": None
}


def parse_time_str(tstr):
    if not tstr:
        return time(8, 0)
    parts = tstr.split(":")
    return time(int(parts[0]), int(parts[1]))


def main():
    init_db()
    created = 0
    with get_db_context() as db:
        patients = db.query(models.Patient).order_by(models.Patient.id).all()
        for patient in patients:
            pid = patient.id
            pattern = PATTERN.get(pid, ["on_time", "on_time", "on_time"])
            print(f"Generating logs for patient {patient.full_name} (id={pid})")

            # For each of the past 3 days (0 = today, 1 = yesterday, 2 = two days ago)
            for day_index, status_tag in enumerate(pattern):
                target_date = date.today() - timedelta(days=day_index)
                # Find schedules for that date
                schedules = db.query(models.Schedule).filter(
                    models.Schedule.patient_id == pid,
                    models.Schedule.scheduled_date == target_date
                ).order_by(models.Schedule.scheduled_time).all()

                for sched in schedules:
                    # Skip if already logged
                    exists = db.query(models.AdherenceLog).filter(
                        models.AdherenceLog.schedule_id == sched.id
                    ).first()
                    if exists:
                        continue

                    tag = status_tag
                    deviation = DELAY_MAP.get(tag)

                    if tag == "missed":
                        status = models.AdherenceStatus.MISSED
                        actual_time = None
                        taken_flag = False
                    else:
                        status = models.AdherenceStatus.TAKEN if deviation == 0 else models.AdherenceStatus.DELAYED
                        sched_time = parse_time_str(sched.scheduled_time)
                        scheduled_dt = datetime.combine(sched.scheduled_date, sched_time)
                        actual_dt = scheduled_dt + timedelta(minutes=deviation)
                        actual_time = actual_dt
                        taken_flag = True

                    log = models.AdherenceLog(
                        patient_id=pid,
                        schedule_id=sched.id,
                        medication_id=sched.medication_id or None,
                        scheduled_time=datetime.combine(sched.scheduled_date, parse_time_str(sched.scheduled_time)),
                        actual_time=actual_time,
                        deviation_minutes=(deviation if deviation is not None else None),
                        status=status,
                        taken=taken_flag,
                        notes="Auto-generated sample adherence",
                        logged_by="system",
                        logged_at=datetime.utcnow()
                    )
                    db.add(log)
                    # Update schedule status to match
                    if taken_flag:
                        sched.status = 'taken'
                    else:
                        sched.status = 'missed'
                    created += 1

            db.commit()

    print(f"Created {created} adherence logs.")

if __name__ == '__main__':
    main()
