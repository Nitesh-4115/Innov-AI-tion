"""
AdherenceGuardian Test Suite
============================

This package contains all tests for the AdherenceGuardian medication adherence system.

Test Structure:
- test_api/: API endpoint tests for FastAPI routes
- test_agents/: Agent unit and integration tests
- conftest.py: Shared pytest fixtures

Running Tests:
    # Run all tests
    pytest

    # Run with coverage
    pytest --cov=. --cov-report=html

    # Run specific test module
    pytest tests/test_api/

    # Run with verbose output
    pytest -v

    # Run only marked tests
    pytest -m "unit"
    pytest -m "integration"
"""

# Test configuration
TEST_DATABASE_URL = "sqlite:///:memory:"
TEST_PATIENT_EMAIL = "test.patient@example.com"

# Common test data
SAMPLE_MEDICATIONS = [
    {"name": "Metformin", "dosage": "500mg", "frequency": "2x daily"},
    {"name": "Lisinopril", "dosage": "10mg", "frequency": "once daily"},
    {"name": "Atorvastatin", "dosage": "20mg", "frequency": "once daily"},
]

SAMPLE_CONDITIONS = ["Type 2 Diabetes", "Hypertension", "High Cholesterol"]

__all__ = [
    "TEST_DATABASE_URL",
    "TEST_PATIENT_EMAIL", 
    "SAMPLE_MEDICATIONS",
    "SAMPLE_CONDITIONS",
]
