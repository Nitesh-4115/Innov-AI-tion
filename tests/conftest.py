"""
Pytest Configuration and Shared Fixtures
========================================

This module provides shared fixtures for all AdherenceGuardian tests.
Fixtures include database sessions, test clients, sample data, and mocks.
"""

import os
import sys
from datetime import datetime, date, time, timedelta
from typing import Generator, Dict, Any, List
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Base, get_db
from models import (
    Patient, Medication, Schedule, AdherenceLog, SymptomReport,
    AgentActivity, DrugInteraction, BarrierResolution, ProviderReport,
    Intervention, AdherenceStatus, BarrierCategory, SeverityLevel, AgentType,
    InterventionType
)
from app import app


# ==================== DATABASE FIXTURES ====================

@pytest.fixture(scope="function")
def test_engine():
    """Create a test database engine with in-memory SQLite"""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False
    )
    
    # Enable foreign keys for SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    yield engine
    
    # Cleanup
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(test_engine) -> Generator[Session, None, None]:
    """Create a test database session"""
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_engine
    )
    
    session = TestingSessionLocal()
    
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Create a FastAPI test client with database override"""
    
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


# ==================== SAMPLE DATA FIXTURES ====================

@pytest.fixture
def sample_patient_data() -> Dict[str, Any]:
    """Sample patient data for creating test patients"""
    return {
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@example.com",
        "phone": "+1234567890",
        "date_of_birth": date(1965, 5, 15),
        "age": 59,
        "conditions": ["Type 2 Diabetes", "Hypertension"],
        "allergies": ["Penicillin"],
        "timezone": "America/New_York",
        "wake_time": time(7, 0),
        "sleep_time": time(22, 0),
        "breakfast_time": time(8, 0),
        "lunch_time": time(12, 0),
        "dinner_time": time(19, 0),
        "is_active": True
    }


@pytest.fixture
def sample_medication_data() -> Dict[str, Any]:
    """Sample medication data for creating test medications"""
    return {
        "name": "Metformin",
        "generic_name": "metformin hydrochloride",
        "rxnorm_id": "6809",
        "dosage": "500mg",
        "dosage_form": "tablet",
        "strength": "500",
        "strength_unit": "mg",
        "frequency": "2x daily",
        "frequency_per_day": 2,
        "instructions": "Take with meals",
        "with_food": True,
        "purpose": "Blood sugar control",
        "active": True,
        "start_date": date.today()
    }


@pytest.fixture
def test_patient(db_session: Session, sample_patient_data: Dict) -> Patient:
    """Create and return a test patient"""
    patient = Patient(**sample_patient_data)
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return patient


@pytest.fixture
def test_medication(db_session: Session, test_patient: Patient, sample_medication_data: Dict) -> Medication:
    """Create and return a test medication linked to test patient"""
    medication = Medication(
        patient_id=test_patient.id,
        **sample_medication_data
    )
    db_session.add(medication)
    db_session.commit()
    db_session.refresh(medication)
    return medication


@pytest.fixture
def test_schedule(db_session: Session, test_patient: Patient, test_medication: Medication) -> Schedule:
    """Create and return a test schedule"""
    schedule = Schedule(
        patient_id=test_patient.id,
        medication_id=test_medication.id,
        scheduled_date=date.today(),
        scheduled_time="08:00",
        meal_relation="with",
        status="pending"
    )
    db_session.add(schedule)
    db_session.commit()
    db_session.refresh(schedule)
    return schedule


@pytest.fixture
def test_adherence_log(db_session: Session, test_patient: Patient, test_medication: Medication) -> AdherenceLog:
    """Create and return a test adherence log"""
    log = AdherenceLog(
        patient_id=test_patient.id,
        medication_id=test_medication.id,
        scheduled_time=datetime.now(),
        actual_time=datetime.now(),
        status=AdherenceStatus.TAKEN,
        taken=True,
        logged_by="user"
    )
    db_session.add(log)
    db_session.commit()
    db_session.refresh(log)
    return log


@pytest.fixture
def test_symptom_report(db_session: Session, test_patient: Patient, test_medication: Medication) -> SymptomReport:
    """Create and return a test symptom report"""
    report = SymptomReport(
        patient_id=test_patient.id,
        symptom="Nausea",
        description="Mild nausea after taking medication",
        severity=3,
        medication_name=test_medication.name,
        suspected_medication_id=test_medication.id,
        timing="30 minutes after dose"
    )
    db_session.add(report)
    db_session.commit()
    db_session.refresh(report)
    return report


@pytest.fixture
def multiple_patients(db_session: Session) -> List[Patient]:
    """Create multiple test patients with different profiles"""
    patients_data = [
        {
            "first_name": "Alice",
            "last_name": "Smith",
            "email": "alice.smith@example.com",
            "age": 45,
            "conditions": ["Hypertension"],
            "timezone": "America/New_York"
        },
        {
            "first_name": "Bob",
            "last_name": "Johnson",
            "email": "bob.johnson@example.com",
            "age": 62,
            "conditions": ["Type 2 Diabetes", "High Cholesterol"],
            "timezone": "America/Chicago"
        },
        {
            "first_name": "Carol",
            "last_name": "Williams",
            "email": "carol.williams@example.com",
            "age": 55,
            "conditions": ["Asthma", "GERD"],
            "timezone": "America/Los_Angeles"
        }
    ]
    
    patients = []
    for data in patients_data:
        patient = Patient(**data)
        db_session.add(patient)
        patients.append(patient)
    
    db_session.commit()
    for patient in patients:
        db_session.refresh(patient)
    
    return patients


@pytest.fixture
def patient_with_medications(db_session: Session, test_patient: Patient) -> Patient:
    """Create a patient with multiple medications"""
    medications_data = [
        {"name": "Metformin", "dosage": "500mg", "frequency": "2x daily", "with_food": True, "frequency_per_day": 2},
        {"name": "Lisinopril", "dosage": "10mg", "frequency": "once daily", "with_food": False, "frequency_per_day": 1},
        {"name": "Atorvastatin", "dosage": "20mg", "frequency": "once daily at bedtime", "with_food": False, "frequency_per_day": 1},
    ]
    
    for med_data in medications_data:
        medication = Medication(
            patient_id=test_patient.id,
            start_date=date.today(),
            active=True,
            **med_data
        )
        db_session.add(medication)
    
    db_session.commit()
    db_session.refresh(test_patient)
    return test_patient


@pytest.fixture
def adherence_history(db_session: Session, test_patient: Patient, test_medication: Medication) -> List[AdherenceLog]:
    """Create adherence history for the past 7 days"""
    logs = []
    base_time = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
    
    # Pattern: mostly adherent with a few misses
    adherence_pattern = [True, True, False, True, True, True, False]
    
    for i, taken in enumerate(adherence_pattern):
        scheduled = base_time - timedelta(days=6-i)
        log = AdherenceLog(
            patient_id=test_patient.id,
            medication_id=test_medication.id,
            scheduled_time=scheduled,
            actual_time=scheduled + timedelta(minutes=5) if taken else None,
            status=AdherenceStatus.TAKEN if taken else AdherenceStatus.MISSED,
            taken=taken,
            logged_by="user"
        )
        db_session.add(log)
        logs.append(log)
    
    db_session.commit()
    for log in logs:
        db_session.refresh(log)
    
    return logs


# ==================== DRUG INTERACTION FIXTURES ====================

@pytest.fixture
def test_drug_interaction(db_session: Session) -> DrugInteraction:
    """Create a test drug interaction"""
    interaction = DrugInteraction(
        drug1="Metformin",
        drug1_rxnorm_id="6809",
        drug2="Alcohol",
        drug2_rxnorm_id=None,
        severity=SeverityLevel.MEDIUM,
        severity_text="moderate",
        description="Alcohol can increase the risk of lactic acidosis with metformin",
        mechanism="Alcohol inhibits gluconeogenesis and may enhance metformin effects",
        management="Limit alcohol consumption while taking metformin"
    )
    db_session.add(interaction)
    db_session.commit()
    db_session.refresh(interaction)
    return interaction


# ==================== AGENT FIXTURES ====================

@pytest.fixture
def mock_llm_service():
    """Mock LLM service for agent tests"""
    with patch("services.llm_service.LLMService") as mock:
        mock_instance = MagicMock()
        mock_instance.generate.return_value = {
            "response": "Test LLM response",
            "tokens_used": 100
        }
        mock_instance.generate_async = AsyncMock(return_value={
            "response": "Test async LLM response",
            "tokens_used": 100
        })
        mock.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_vector_store():
    """Mock vector store for RAG tests"""
    with patch("knowledge_base.vector_store.VectorStore") as mock:
        mock_instance = MagicMock()
        mock_instance.search.return_value = [
            {"content": "Test document content", "metadata": {"source": "test"}, "score": 0.95}
        ]
        mock.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def test_agent_activity(db_session: Session, test_patient: Patient) -> AgentActivity:
    """Create a test agent activity log"""
    activity = AgentActivity(
        patient_id=test_patient.id,
        agent_name="MonitoringAgent",
        agent_type=AgentType.MONITORING,
        action="Analyzed adherence pattern",
        activity_type="monitoring",
        input_data={"patient_id": test_patient.id, "days": 7},
        output_data={"adherence_rate": 85.7, "trend": "stable"},
        reasoning="Patient shows consistent adherence with minor gaps",
        execution_time_ms=150,
        is_successful=True
    )
    db_session.add(activity)
    db_session.commit()
    db_session.refresh(activity)
    return activity


# ==================== BARRIER AND INTERVENTION FIXTURES ====================

@pytest.fixture
def test_barrier(db_session: Session, test_patient: Patient) -> BarrierResolution:
    """Create a test barrier resolution record"""
    barrier = BarrierResolution(
        patient_id=test_patient.id,
        barrier_type=BarrierCategory.COST,
        barrier_type_text="cost",
        description="High medication costs causing non-adherence",
        severity=SeverityLevel.HIGH,
        identified_by_agent=AgentType.BARRIER,
        resolved=False
    )
    db_session.add(barrier)
    db_session.commit()
    db_session.refresh(barrier)
    return barrier


@pytest.fixture  
def test_intervention(db_session: Session, test_patient: Patient) -> Intervention:
    """Create a test intervention record"""
    intervention = Intervention(
        patient_id=test_patient.id,
        type=InterventionType.REMINDER,
        type_text="reminder",
        description="Adjusted reminder timing based on activity patterns",
        initiated_by_agent=AgentType.MONITORING,
        is_successful=None  # Not yet evaluated
    )
    db_session.add(intervention)
    db_session.commit()
    db_session.refresh(intervention)
    return intervention


# ==================== PROVIDER REPORT FIXTURES ====================

@pytest.fixture
def test_provider_report(db_session: Session, test_patient: Patient) -> ProviderReport:
    """Create a test provider report"""
    report = ProviderReport(
        patient_id=test_patient.id,
        report_period_start=date.today() - timedelta(days=7),
        report_period_end=date.today(),
        overall_adherence=85.7,
        doses_taken=12,
        doses_missed=2,
        doses_delayed=0,
        summary="Patient shows good overall adherence with occasional evening misses",
        recommendations=["Consider once-daily formulation"],
        concerns="Occasional evening dose misses",
        generated_by_agent=AgentType.LIAISON
    )
    db_session.add(report)
    db_session.commit()
    db_session.refresh(report)
    return report


# ==================== UTILITY FIXTURES ====================

@pytest.fixture
def current_datetime() -> datetime:
    """Return current datetime for consistent testing"""
    return datetime.now()


@pytest.fixture
def mock_notification_service():
    """Mock notification service for testing alerts"""
    with patch("tools.notification_sevice.NotificationService") as mock:
        mock_instance = MagicMock()
        mock_instance.send_sms.return_value = {"status": "sent", "sid": "test_sid"}
        mock_instance.send_email.return_value = {"status": "sent", "id": "test_id"}
        mock.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_rxnorm_client():
    """Mock RxNorm API client"""
    with patch("knowledge_base.rxnorm_client.RxNormClient") as mock:
        mock_instance = MagicMock()
        mock_instance.get_drug_info.return_value = {
            "rxcui": "6809",
            "name": "Metformin",
            "tty": "IN"
        }
        mock_instance.get_interactions.return_value = []
        mock.return_value = mock_instance
        yield mock_instance


# ==================== MARKERS ====================

def pytest_configure(config):
    """Register custom markers"""
    config.addinivalue_line("markers", "unit: mark test as a unit test")
    config.addinivalue_line("markers", "integration: mark test as an integration test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "api: mark test as an API test")
    config.addinivalue_line("markers", "agent: mark test as an agent test")
    config.addinivalue_line("markers", "database: mark test as requiring database")


# ==================== ASYNC FIXTURES ====================

@pytest.fixture
def event_loop():
    """Create event loop for async tests"""
    import asyncio
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ==================== CLEANUP ====================

@pytest.fixture(autouse=True)
def cleanup_after_test(db_session: Session):
    """Automatic cleanup after each test"""
    yield
    # Session is automatically rolled back by db_session fixture
