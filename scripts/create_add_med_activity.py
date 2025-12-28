#!/usr/bin/env python3
"""
Create an AgentActivity to request adding a medication for a patient.
Run: python scripts/create_add_med_activity.py
"""
from datetime import datetime
import sys
import os

# Ensure project root is on sys.path so imports resolve when run as a script
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from database import get_db_context, init_db
import models


def main():
    init_db()
    with get_db_context() as db:
        # Find Emma Johansson
        patient = db.query(models.Patient).filter(models.Patient.first_name == 'Emma', models.Patient.last_name == 'Johansson').first()
        if not patient:
            print('Patient "Emma Johansson" not found in DB')
            return

        input_data = {
            "name": "Metformin",
            "dose": "500 mg",
            "frequency": "twice_daily",
            "times": ["13:40", "22:00"],
            "timezone": patient.timezone,
        }

        activity = models.AgentActivity(
            patient_id=patient.id,
            agent_name="LiaisonAgent",
            agent_type=models.AgentType.LIAISON,
            action="add_medication",
            activity_type="planning",
            input_data=input_data,
            timestamp=datetime.utcnow(),
        )

        db.add(activity)
        db.commit()
        db.refresh(activity)

        print(f"Created AgentActivity id={activity.id} for patient_id={patient.id}, timezone={patient.timezone}")


if __name__ == '__main__':
    main()
