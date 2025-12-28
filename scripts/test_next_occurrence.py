from fastapi.testclient import TestClient
from app import app
from datetime import date, timedelta
import time

client = TestClient(app)

print('Starting next-occurrence test')

with client:
    # Create patient
    payload = {
        "first_name": "NextOcc",
        "last_name": "Tester",
        "email": f"nextocc+{int(time.time())}@example.com",
        "timezone": "UTC",
        "wake_time": "08:00",
        "sleep_time": "22:00",
    }
    r = client.post("/api/v1/patients", json=payload)
    r.raise_for_status()
    patient = r.json()
    pid = patient["id"]
    print('Created patient', pid)

    # Add medication with two times
    med_payload = {
        "patient_id": pid,
        "name": "TomorrowMed",
        "dosage": "5mg",
        "frequency": "daily",
        "frequency_per_day": 2,
        "custom_times": ["08:00", "20:00"],
        "start_date": str(date.today())
    }
    r = client.post(f"/api/v1/patients/{pid}/medications", json=med_payload)
    r.raise_for_status()
    med_resp = r.json()
    med_id = med_resp.get("medication_id")
    print('Added medication', med_id)

    # Fetch today's schedule
    r = client.get(f"/api/v1/patients/{pid}/schedule/today")
    r.raise_for_status()
    today_schedule = r.json()
    print("Today's schedule initially:")
    for s in today_schedule:
        print(s)

    # Mark all today's entries as taken so no pending remain
    for s in today_schedule:
        sched_iso = f"{date.today().isoformat()}T{s.get('time')}:00+00:00"
        log_payload = {
            "medication_id": med_id,
            "taken": True,
            "scheduled_time": sched_iso,
            "actual_time": sched_iso,
            "notes": "Marking taken for next-occ test",
            "schedule_id": s.get('id')
        }
        r = client.post('/api/v1/adherence/log', json=log_payload)
        r.raise_for_status()
    print('Marked today entries as taken')

    # Call schedule/today again — should trigger creation of next-occurrence entries
    r = client.get(f"/api/v1/patients/{pid}/schedule/today")
    r.raise_for_status()
    new_schedule = r.json()
    print('Schedule after marking taken:')
    for s in new_schedule:
        print(s)

    created_next = [s for s in new_schedule if s.get('notes') and 'generated-next' in s.get('notes')]
    print('Created next-occurrence entries found:', len(created_next))
    for s in created_next:
        print(s)

print('Next-occurrence test finished')
