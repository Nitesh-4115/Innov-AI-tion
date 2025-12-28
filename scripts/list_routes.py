"""
List FastAPI routes to inspect ordering and conflicting patterns.
Run: python scripts/list_routes.py
"""
import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import app

for r in app.routes:
    try:
        methods = ','.join(sorted(r.methods or []))
    except Exception:
        methods = ''
    print(f"{r.path}    {methods}    -> name={r.name}")
