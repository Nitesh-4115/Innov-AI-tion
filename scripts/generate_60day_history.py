"""
Generate 60 days of adherence history for all patients and medications.
Run: python scripts/generate_60day_history.py
"""
import sys
import os
import random
from datetime import datetime, date, time, timedelta

# Ensure project root on sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from database import init_db, get_db_context
import models

# Seed for reproducibility
random.seed(42)

# Per-patient adherence probabilities (on-time, delayed, missed)
# Map patient index (1-based) to probabilities
PATIENT_PROBS = {
    1: (0.9, 0.08, 0.02),   # Aisha - very good
    2: (0.7, 0.2, 0.1),     # Carlos - mixed
    3: (0.5, 0.3, 0.2),     # Emma - lower adherence
    4: (0.85, 0.12, 0.03),  # Liam - good
    5: (0.65, 0.25, 0.1)    # Sofia - moderate
}

DAYS = 60

def parse_time_str(tstr):
    if not tstr:
        return time(8, 0)
    parts = tstr.split(":")
    return time(int(parts[0]), int(parts[1]))


def main():
    init_db()
    created = 0
    skipped = 0
    with get_db_context() as db:
        patients = db.query(models.Patient).order_by(models.Patient.id).all()
        meds_total = 0
        for patient in patients:
            pid = patient.id
            probs = PATIENT_PROBS.get(pid, (0.75, 0.2, 0.05))
            print(f"Simulating {DAYS} days for patient {patient.full_name} (id={pid}), probs={probs}")

            medications = db.query(models.Medication).filter(models.Medication.patient_id == pid).all()
            if not medications:
                print(f" - No medications for patient {pid}; skipping")
                continue

            for med in medications:
                meds_total += 1
                times = med.recurring_times or ["08:00"]
                for day_offset in range(1, DAYS + 1):
                    target_date = date.today() - timedelta(days=day_offset)
                    for t in times:
                        scheduled_time_obj = parse_time_str(t)
                        scheduled_dt = datetime.combine(target_date, scheduled_time_obj)

                        # Avoid duplicating logs if one already exists
                        exists = db.query(models.AdherenceLog).filter(
                            models.AdherenceLog.patient_id == pid,
                            models.AdherenceLog.medication_id == med.id,
                            models.AdherenceLog.scheduled_time == scheduled_dt
                        ).first()
                        if exists:
                            skipped += 1
                            continue

                        r = random.random()
                        if r < probs[0]:
                            # on time
                            deviation = 0
                            actual_dt = scheduled_dt
                            status = models.AdherenceStatus.TAKEN
                            taken_flag = True
                        elif r < probs[0] + probs[1]:
                            # delayed
                            deviation = random.randint(5, 90)  # minutes late
                            actual_dt = scheduled_dt + timedelta(minutes=deviation)
                            status = models.AdherenceStatus.DELAYED
                            taken_flag = True
                        else:
                            # missed
                            deviation = None
                            actual_dt = None
                            status = models.AdherenceStatus.MISSED
                            taken_flag = False

                        log = models.AdherenceLog(
                            patient_id=pid,
                            schedule_id=None,
                            medication_id=med.id,
                            scheduled_time=scheduled_dt,
                            actual_time=actual_dt,
                            deviation_minutes=(deviation if deviation is not None else None),
                            status=status,
                            taken=taken_flag,
                            notes="Auto-generated 60-day history",
                            logged_by="system",
                            logged_at=datetime.utcnow()
                        )
                        db.add(log)
                        created += 1
                # commit per medication to avoid huge transaction
                db.commit()
        print(f"Created {created} logs, skipped {skipped} existing. Medications processed: {meds_total}")

if __name__ == '__main__':
    main()
