"""
One-off script to add five fake patients to the database for testing.
Run: python scripts/add_fake_patients.py
"""
from datetime import date
import sys
import os

# Ensure project root is on sys.path so imports resolve when run as a script
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from database import get_db_context, init_db
import models

FAKE_PATIENTS = [
    {
        "full_name": "Aisha Khan",
        "timezone": "Asia/Kolkata",
        "conditions": ["Hypertension"],
        "breakfast_time": "08:00",
        "lunch_time": "13:00",
        "dinner_time": "20:00",
        "sleep_time": "23:00",
        "active": True
    },
    {
        "full_name": "Carlos Mendez",
        "timezone": "America/Los_Angeles",
        "conditions": ["Diabetes"],
        "breakfast_time": "07:30",
        "lunch_time": "12:30",
        "dinner_time": "18:30",
        "sleep_time": "22:30",
        "active": True
    },
    {
        "full_name": "Emma Johansson",
        "timezone": "Europe/Stockholm",
        "conditions": ["Asthma"],
        "breakfast_time": "08:00",
        "lunch_time": "12:00",
        "dinner_time": "18:00",
        "sleep_time": "22:00",
        "active": True
    },
    {
        "full_name": "Liam O'Connor",
        "timezone": "Europe/Dublin",
        "conditions": ["Depression"],
        "breakfast_time": "09:00",
        "lunch_time": "13:00",
        "dinner_time": "19:00",
        "sleep_time": "23:00",
        "active": True
    },
    {
        "full_name": "Sofia Rossi",
        "timezone": "Europe/Rome",
        "conditions": ["Hyperlipidemia"],
        "breakfast_time": "07:45",
        "lunch_time": "12:45",
        "dinner_time": "19:30",
        "sleep_time": "22:30",
        "active": True
    }
]


def _ensure_time_obj(t):
    from datetime import time
    if t is None:
        return None
    if isinstance(t, time):
        return t
    if isinstance(t, str):
        parts = t.split(":")
        return time(int(parts[0]), int(parts[1]))
    return None


def main():
    # Ensure DB initialized
    init_db()
    with get_db_context() as db:
        created = []
        for p in FAKE_PATIENTS:
            existing = db.query(models.Patient).filter(models.Patient.full_name == p["full_name"]).first()
            if existing:
                created.append(existing)
                continue
            # Split full name into first/last
            parts = p["full_name"].split()
            first = parts[0]
            last = " ".join(parts[1:]) if len(parts) > 1 else ""
            # Generate a test email
            safe_first = ''.join(ch for ch in first.lower() if ch.isalnum())
            safe_last = ''.join(ch for ch in last.lower() if ch.isalnum()) or 'user'
            email = f"{safe_first}.{safe_last}@example.test"

            patient = models.Patient(
                first_name=first,
                last_name=last,
                email=email,
                timezone=p["timezone"],
                conditions=p.get("conditions", []),
                breakfast_time=_ensure_time_obj(p.get("breakfast_time")),
                lunch_time=_ensure_time_obj(p.get("lunch_time")),
                dinner_time=_ensure_time_obj(p.get("dinner_time")),
                sleep_time=_ensure_time_obj(p.get("sleep_time")),
                is_active=p.get("active", True)
            )
            db.add(patient)
            db.commit()
            db.refresh(patient)
            created.append(patient)
            print(f"Created patient: {patient.id} - {patient.full_name}")

        print(f"Total patients present/created: {len(created)}")


if __name__ == '__main__':
    main()
