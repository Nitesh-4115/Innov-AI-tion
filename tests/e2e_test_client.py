from fastapi.testclient import TestClient
from app import app
from datetime import date, timedelta
import time

client = TestClient(app)

print('Starting TestClient (runs app startup events)')

with client:
    # Create patient
    payload = {
        "first_name": "E2E",
        "last_name": "Tester",
        "email": f"e2e+{int(time.time())}@example.com",
        "timezone": "UTC",
        "wake_time": "08:00",
        "sleep_time": "22:00",
        "breakfast_time": "08:00",
        "lunch_time": "12:00",
        "dinner_time": "19:00"
    }
    r = client.post("/", json={})
    # Use direct API prefixes as app defines endpoints at /api/v1
    r = client.post("/api/v1/patients", json=payload)
    r.raise_for_status()
    patient = r.json()
    pid = patient["id"]
    print('Created patient', patient)

    # Add medication with custom times
    med_payload = {
        "patient_id": pid,
        "name": "TestMed",
        "dosage": "10mg",
        "frequency": "daily",
        "frequency_per_day": 2,
        "with_food": False,
        "custom_times": ["08:00", "20:00"],
        "start_date": str(date.today())
    }
    r = client.post(f"/api/v1/patients/{pid}/medications", json=med_payload)
    r.raise_for_status()
    med_resp = r.json()
    med_id = med_resp.get("medication_id")
    print('Added medication', med_resp)

    # Get today's schedule
    r = client.get(f"/api/v1/patients/{pid}/schedule/today")
    r.raise_for_status()
    today_schedule = r.json()
    print("Today's schedule:")
    for s in today_schedule:
        print(s)

    # Create yesterday schedule
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    custom_payload = {"medication_id": med_id, "times": ["08:00","20:00"], "scheduled_date": yesterday}
    r = client.post(f"/api/v1/patients/{pid}/schedule/custom", json=custom_payload)
    r.raise_for_status()
    print('Created yesterday schedule entries:', r.json())

    # Find today's 08:00 entry
    entry_08 = None
    r = client.get(f"/api/v1/patients/{pid}/schedule/today")
    r.raise_for_status()
    for s in r.json():
        if s.get('time') == '08:00':
            entry_08 = s
            break
    assert entry_08, '08:00 not found'

    # Log adherence for today's 08:00
    scheduled_iso = f"{date.today().isoformat()}T08:00:00+00:00"
    log_payload = {
        "medication_id": med_id,
        "taken": True,
        "scheduled_time": scheduled_iso,
        "actual_time": scheduled_iso,
        "notes": "E2E test",
        "schedule_id": entry_08['id']
    }
    r = client.post('/api/v1/adherence/log', json=log_payload)
    r.raise_for_status()
    print('Logged adherence:', r.json())

    # Re-fetch today's schedule and stats
    r = client.get(f"/api/v1/patients/{pid}/schedule/today")
    r.raise_for_status()
    print('Today after logging:')
    for s in r.json():
        print(s)

    r = client.get(f"/api/v1/patients/{pid}/adherence/stats")
    r.raise_for_status()
    print('Adherence stats:', r.json())

print('TestClient E2E finished')
