"""
Use FastAPI TestClient to call the running app handlers (no server needed) and show validation errors.
Run: python scripts/http_test_search.py
"""
import json
import sys
import os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

def run_test(q, limit):
    r = client.get(f"/api/v1/medications/search?query={q}&limit={limit}")
    print(f"REQUEST: query={q!r}, limit={limit!r} -> status={r.status_code}")
    try:
        print(json.dumps(r.json(), indent=2, ensure_ascii=False))
    except Exception:
        print(r.text)

if __name__ == '__main__':
    # Test a few combinations
    run_test('', 1000)
    run_test('', 100000)
    run_test('met', 1000)
    run_test('met', 10)
