#!/usr/bin/env python3
"""
Process AgentActivity rows (simple worker for add_medication activities).
Run: python scripts/process_agent_activities.py
"""
import sys
import os
from datetime import date

# ensure project root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from database import get_db_context, init_db
import models
from services import medication_service
import re
from datetime import datetime


def _extract_times_from_text(text: str):
    if not text:
        return []
    times = []
    for m in re.finditer(r"(\d{1,2}:\d{2})\s*(am|pm)?", text, re.IGNORECASE):
        raw = m.group(1)
        suffix = (m.group(2) or '').lower()
        try:
            if suffix:
                dt = datetime.strptime(raw + suffix, "%I:%M%p")
                times.append(dt.strftime("%H:%M"))
            else:
                # assume 24h
                dt = datetime.strptime(raw, "%H:%M")
                times.append(dt.strftime("%H:%M"))
        except Exception:
            continue
    # dedupe while preserving order
    seen = set()
    out = []
    for t in times:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def process_add_med(activity, db):
    input_data = activity.input_data or {}
    name = input_data.get('name') or input_data.get('medication') or input_data.get('med')
    dosage = input_data.get('dosage') or input_data.get('dose')
    frequency = input_data.get('frequency') or input_data.get('freq') or 'once daily'
    times = input_data.get('times') or input_data.get('recurring_times') or []

    # If times are missing, try to extract from the source message or frequency text
    if not times:
        src = input_data.get('source_message') or ''
        times = _extract_times_from_text(src)
        if not times:
            # try frequency string (e.g., 'twice daily at 13:45 and 22:00')
            times = _extract_times_from_text(frequency)

    if not name or not dosage:
        activity.is_successful = False
        activity.error_message = 'Missing name or dosage in activity input'
        db.add(activity)
        db.commit()
        return False, 'missing fields'

    try:
        # Check for existing medication to avoid duplicates
        med = db.query(models.Medication).filter(
            models.Medication.patient_id == activity.patient_id,
            models.Medication.name.ilike(f"%{name}%")
        ).order_by(models.Medication.id.desc()).first()

        if med:
            # update dosage/frequency if missing
            updated = False
            if not med.dosage and dosage:
                med.dosage = dosage
                updated = True
            if not med.frequency and frequency:
                med.frequency = frequency
                updated = True
            if updated:
                db.add(med)
                db.commit()
                db.refresh(med)
        else:
            # Add medication via service
            med = medication_service.add_medication(
                patient_id=activity.patient_id,
                name=name,
                dosage=dosage,
                frequency=frequency,
                frequency_per_day=len(times) if times else 1,
                db=db
            )
        # medication_service.add_medication is async in service signature but implemented
        # to work synchronously if db provided; call and get result
        if hasattr(med, '__await__'):
            # If coroutine, run it
            import asyncio
            med = asyncio.get_event_loop().run_until_complete(med)

        # Update recurring_times
        med.recurring_times = times
        db.add(med)
        db.commit()
        db.refresh(med)

        # Create schedule entries for today (and optionally more days)
        created_schedules = []
        today = date.today()
        for t in times:
            # avoid duplicates
            exists = db.query(models.Schedule).filter(
                models.Schedule.patient_id == activity.patient_id,
                models.Schedule.medication_id == med.id,
                models.Schedule.scheduled_date == today,
                models.Schedule.scheduled_time == t
            ).first()
            if exists:
                created_schedules.append(exists.id)
                continue
            sched = models.Schedule(
                patient_id=activity.patient_id,
                medication_id=med.id,
                scheduled_date=today,
                scheduled_time=t,
                medications_list=[med.name],
                status='pending',
                notes='Created by liaison agent activity'
            )
            db.add(sched)
            db.commit()
            db.refresh(sched)
            created_schedules.append(sched.id)

        # Mark activity successful
        activity.output_data = {'medication_id': med.id, 'schedule_ids': created_schedules}
        activity.is_successful = True
        activity.error_message = None
        db.add(activity)
        db.commit()
        return True, {'medication_id': med.id, 'schedules': created_schedules}
    except Exception as e:
        activity.is_successful = False
        activity.error_message = str(e)
        db.add(activity)
        db.commit()
        return False, str(e)


def main():
    init_db()
    with get_db_context() as db:
        pending = db.query(models.AgentActivity).filter(
            models.AgentActivity.action == 'add_medication',
            (models.AgentActivity.is_successful == False) | (models.AgentActivity.is_successful.is_(None))
        ).order_by(models.AgentActivity.timestamp.asc()).all()

        if not pending:
            print('No pending add_medication activities found — checking for incomplete successful activities')
            # Also process previously-successful activities that lack schedules in output_data
            completed = db.query(models.AgentActivity).filter(
                models.AgentActivity.action == 'add_medication',
                models.AgentActivity.is_successful == True
            ).order_by(models.AgentActivity.timestamp.asc()).all()

            to_fix = []
            for act in completed:
                od = act.output_data or {}
                # consider missing or empty schedule_ids as incomplete
                if not od or not od.get('schedule_ids'):
                    to_fix.append(act)

            if not to_fix:
                print('No incomplete successful activities to process')
                return
            pending = to_fix

        for act in pending:
            print(f'Processing AgentActivity id={act.id} patient_id={act.patient_id}')
            ok, res = process_add_med(act, db)
            if ok:
                print(f'  Success: medication_id={res["medication_id"]} schedules={res["schedules"]}')
            else:
                print(f'  Failed: {res}')

if __name__ == '__main__':
    main()
