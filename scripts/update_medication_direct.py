#!/usr/bin/env python3
"""
Directly update medication dosage for a patient by name (for testing).
Usage: python scripts/update_medication_direct.py <patient_id> "Medication Name" "new dosage"
"""
import sys
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from database import get_db_context, init_db
import models
from services import medication_service


def update_med_by_name(pid: int, name: str, new_dosage: str):
    init_db()
    with get_db_context() as db:
        med = db.query(models.Medication).filter(
            models.Medication.patient_id == pid,
            models.Medication.name.ilike(f"%{name}%")
        ).order_by(models.Medication.id.desc()).first()
        if not med:
            print('Medication not found')
            return
        print(f'Found med id={med.id} name={med.name} old dosage={med.dosage}')
        updated = medication_service.medication_service.update_medication(med.id, {'dosage': new_dosage}, db=db)
        # medication_service.update_medication may be async, handle both
        import asyncio
        if hasattr(updated, '__await__'):
            updated = asyncio.get_event_loop().run_until_complete(updated)
        db.refresh(updated)
        print(f'Updated med id={updated.id} new dosage={updated.dosage}')
        # create AgentActivity for audit
        act = models.AgentActivity(
            patient_id=pid,
            agent_name="script",
            agent_type=models.AgentType.LIAISON,
            action="update_medication",
            activity_type="manual",
            input_data={'medication_id': updated.id, 'updates': {'dosage': new_dosage}},
            output_data={'medication_id': updated.id},
            is_successful=True
        )
        db.add(act)
        db.commit()
        print(f'Logged AgentActivity id={act.id}')


if __name__ == '__main__':
    if len(sys.argv) < 4:
        print('Usage: python scripts/update_medication_direct.py <patient_id> "Medication Name" "new dosage"')
    else:
        pid = int(sys.argv[1])
        name = sys.argv[2]
        nd = sys.argv[3]
        update_med_by_name(pid, name, nd)
