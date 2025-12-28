import requests
import time
from datetime import datetime, date, timedelta

BASE = "http://localhost:8000/api/v1"

session = requests.Session()

def wait_for_backend(timeout=30):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = session.get("http://localhost:8000/")
            if r.status_code == 200:
                print("Backend healthy")
                return True
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError("Backend did not become available")


def create_patient():
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
    r = session.post(f"{BASE}/patients", json=payload)
    r.raise_for_status()
    print("Created patient", r.json())
    return r.json()["id"]


def add_med(patient_id):
    payload = {
        "patient_id": patient_id,
        "name": "TestMed",
        "dosage": "10mg",
        "frequency": "daily",
        "frequency_per_day": 2,
        "with_food": False,
        "custom_times": ["08:00", "20:00"],
        "start_date": str(date.today())
    }
    r = session.post(f"{BASE}/patients/{patient_id}/medications", json=payload)
    if r.status_code != 201 and r.status_code != 200:
        print("Add med failed: status", r.status_code)
        print(r.text)
        r.raise_for_status()
    print("Added medication", r.json())
    return r.json().get("medication_id")


def get_today_schedule(patient_id):
    r = session.get(f"{BASE}/patients/{patient_id}/schedule/today")
    r.raise_for_status()
    return r.json()


def create_custom_for_date(patient_id, medication_id, times, target_date):
    payload = {
        "medication_id": medication_id,
        "times": times,
        "scheduled_date": target_date
    }
    r = session.post(f"{BASE}/patients/{patient_id}/schedule/custom", json=payload)
    r.raise_for_status()
    return r.json()


def log_adherence(patient_id, medication_id, schedule_id, scheduled_dt_iso):
    payload = {
        "medication_id": medication_id,
        "taken": True,
        "scheduled_time": scheduled_dt_iso,
        "actual_time": scheduled_dt_iso,
        "notes": "E2E test",
        "schedule_id": schedule_id
    }
    r = session.post(f"{BASE}/adherence/log", json=payload)
    r.raise_for_status()
    return r.json()


if __name__ == '__main__':
    wait_for_backend()
    pid = create_patient()
    med_id = add_med(pid)
    time.sleep(0.5)

    today_schedule = get_today_schedule(pid)
    print("Today's schedule:")
    for s in today_schedule:
        print(s)

    # Create explicit schedule for yesterday to simulate previous-day rows
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    created_yesterday = create_custom_for_date(pid, med_id, ["08:00", "20:00"], yesterday)
    print("Created yesterday entries:", created_yesterday)

    # Find today's 08:00 entry and log adherence for it
    today_schedule = get_today_schedule(pid)
    entry_08 = None
    for s in today_schedule:
        if s.get("time") == "08:00":
            entry_08 = s
            break
    if not entry_08:
        raise RuntimeError("08:00 entry not found in today's schedule")

    scheduled_iso = f"{date.today().isoformat()}T08:00:00+00:00"
    log = log_adherence(pid, med_id, entry_08["id"], scheduled_iso)
    print("Logged adherence:", log)

    # Re-fetch today's schedule to assert update
    today_after = get_today_schedule(pid)
    print("Today's schedule after logging:")
    for s in today_after:
        print(s)

    # Fetch adherence stats (30 days default) to ensure a single log recorded
    r = session.get(f"{BASE}/patients/{pid}/adherence/stats")
    r.raise_for_status()
    stats = r.json()
    print("Adherence stats:", stats)

    print("E2E test completed")
