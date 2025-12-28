"""
Quick script to print adherence stats for patient id 1 (Aisha Khan).
Run: python scripts/quick_stats_aisha.py
"""
import asyncio
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from database import init_db, get_db_context
# Import the FastAPI handler function directly
from app import get_adherence_stats, get_adherence_daily


def main():
    init_db()
    with get_db_context() as db:
        # Run the async handlers with the provided DB session
        stats = asyncio.run(get_adherence_stats(1, 30, db))
        daily = asyncio.run(get_adherence_daily(1, 30, db))

        print("=== Adherence Stats (30 days) for patient id=1 ===")
        print(json.dumps(stats, indent=2, default=str))
        print("\n=== Daily Adherence (30 days) ===")
        print(json.dumps(daily, indent=2, default=str))


if __name__ == '__main__':
    main()
