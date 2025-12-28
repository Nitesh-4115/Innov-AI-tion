"""
Small test script to call the internal search_drugs implementation.
Run: python scripts/test_search_drugs.py
"""
import asyncio
import json
import os
import sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from app import search_drugs

async def run():
    print('Searching for "met"...')
    res = await search_drugs('met', limit=10)
    print(json.dumps(res, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    asyncio.run(run())
