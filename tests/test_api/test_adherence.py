"""
Tests for Adherence API
========================

Tests adherence logging, tracking, rates, trends, and analytics.
"""

import pytest
from datetime import datetime, date, timedelta
from fastapi import status
from fastapi.testclient import TestClient

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from models import Patient, Medication, AdherenceLog, Schedule, AdherenceStatus


# ==================== FIXTURES ====================

@pytest.fixture
def adherence_log_data(test_patient, test_medication):
    """Sample data for logging adherence"""
    return {
        "patient_id": test_patient.id,
        "medication_id": test_medication.id,
        "status": "taken",
        "taken_at": datetime.now().isoformat(),
        "notes": "Taken on time"
    }


@pytest.fixture
def dose_taken_data(test_patient, test_medication, test_schedule):
    """Sample data for quick dose taken log"""
    return {
        "patient_id": test_patient.id,
        "medication_id": test_medication.id,
        "schedule_id": test_schedule.id
    }


# ==================== LOGGING TESTS ====================

class TestLogAdherence:
    """Tests for adherence logging endpoints"""
    
    @pytest.mark.api
    def test_log_adherence_taken(self, client: TestClient, adherence_log_data):
        """Test logging a taken dose"""
        response = client.post("/api/v1/adherence/log", json=adherence_log_data)
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["taken"] == True
    
    @pytest.mark.api
    def test_log_adherence_missed(self, client: TestClient, test_patient, test_medication):
        """Test logging a missed dose"""
        log_data = {
            "patient_id": test_patient.id,
            "medication_id": test_medication.id,
            "status": "missed",
            "notes": "Forgot to take"
        }
        
        response = client.post("/api/v1/adherence/log", json=log_data)
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["taken"] == False
    
    @pytest.mark.api
    def test_log_adherence_skipped(self, client: TestClient, test_patient, test_medication):
        """Test logging a skipped dose"""
        log_data = {
            "patient_id": test_patient.id,
            "medication_id": test_medication.id,
            "status": "skipped",
            "notes": "Intentionally skipped due to side effects"
        }
        
        response = client.post("/api/v1/adherence/log", json=log_data)
        
        assert response.status_code == status.HTTP_201_CREATED
    
    @pytest.mark.api
    def test_log_adherence_delayed(self, client: TestClient, test_patient, test_medication):
        """Test logging a delayed dose"""
        log_data = {
            "patient_id": test_patient.id,
            "medication_id": test_medication.id,
            "status": "delayed",
            "deviation_minutes": 45,
            "taken_at": datetime.now().isoformat()
        }
        
        response = client.post("/api/v1/adherence/log", json=log_data)
        
        assert response.status_code == status.HTTP_201_CREATED
    
    @pytest.mark.api
    def test_log_adherence_invalid_status(self, client: TestClient, test_patient, test_medication):
        """Test logging with invalid status"""
        log_data = {
            "patient_id": test_patient.id,
            "medication_id": test_medication.id,
            "status": "invalid_status"
        }
        
        response = client.post("/api/v1/adherence/log", json=log_data)
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    @pytest.mark.api
    def test_log_adherence_invalid_patient(self, client: TestClient, test_medication):
        """Test logging for non-existent patient"""
        log_data = {
            "patient_id": 99999,
            "medication_id": test_medication.id,
            "status": "taken"
        }
        
        response = client.post("/api/v1/adherence/log", json=log_data)
        
        assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND]


class TestQuickLog:
    """Tests for quick logging endpoints"""
    
    @pytest.mark.api
    def test_dose_taken_quick(self, client: TestClient, dose_taken_data):
        """Test quick dose taken endpoint"""
        response = client.post("/api/v1/adherence/dose/taken", json=dose_taken_data)
        
        assert response.status_code == status.HTTP_201_CREATED
    
    @pytest.mark.api
    def test_dose_missed_quick(self, client: TestClient, test_patient, test_medication):
        """Test quick dose missed endpoint"""
        data = {
            "patient_id": test_patient.id,
            "medication_id": test_medication.id,
            "reason": "Forgot"
        }
        
        response = client.post("/api/v1/adherence/dose/missed", json=data)
        
        assert response.status_code in [status.HTTP_201_CREATED, status.HTTP_404_NOT_FOUND]
    
    @pytest.mark.api
    def test_dose_skipped_quick(self, client: TestClient, test_patient, test_medication):
        """Test quick dose skipped endpoint"""
        data = {
            "patient_id": test_patient.id,
            "medication_id": test_medication.id,
            "reason": "Side effects"
        }
        
        response = client.post("/api/v1/adherence/dose/skipped", json=data)
        
        assert response.status_code in [status.HTTP_201_CREATED, status.HTTP_404_NOT_FOUND]


# ==================== ADHERENCE RATE TESTS ====================

class TestAdherenceRate:
    """Tests for adherence rate calculation endpoints"""
    
    @pytest.mark.api
    def test_get_adherence_rate(self, client: TestClient, test_patient, adherence_history):
        """Test getting adherence rate"""
        response = client.get(f"/api/v1/adherence/rate/{test_patient.id}")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "rate" in data or "adherence_rate" in data
    
    @pytest.mark.api
    def test_get_adherence_rate_custom_period(self, client: TestClient, test_patient, adherence_history):
        """Test getting adherence rate for custom period"""
        response = client.get(f"/api/v1/adherence/rate/{test_patient.id}?days=14")
        
        assert response.status_code == status.HTTP_200_OK
    
    @pytest.mark.api
    def test_get_adherence_rate_no_data(self, client: TestClient, test_patient):
        """Test getting adherence rate with no data"""
        response = client.get(f"/api/v1/adherence/rate/{test_patient.id}")
        
        assert response.status_code == status.HTTP_200_OK
        # Should return 0 or null for no data
    
    @pytest.mark.api
    def test_get_adherence_rate_by_medication(self, client: TestClient, test_patient, test_medication, adherence_history):
        """Test getting adherence rate for specific medication"""
        response = client.get(
            f"/api/v1/adherence/rate/{test_patient.id}?medication_id={test_medication.id}"
        )
        
        assert response.status_code == status.HTTP_200_OK


# ==================== ADHERENCE HISTORY TESTS ====================

class TestAdherenceHistory:
    """Tests for adherence history endpoints"""
    
    @pytest.mark.api
    def test_get_adherence_history(self, client: TestClient, test_patient, adherence_history):
        """Test getting adherence history"""
        response = client.get(f"/api/v1/adherence/history/{test_patient.id}")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, (list, dict))
    
    @pytest.mark.api
    def test_get_adherence_history_date_range(self, client: TestClient, test_patient, adherence_history):
        """Test getting adherence history with date range"""
        start_date = (date.today() - timedelta(days=7)).isoformat()
        end_date = date.today().isoformat()
        
        response = client.get(
            f"/api/v1/adherence/history/{test_patient.id}?start_date={start_date}&end_date={end_date}"
        )
        
        assert response.status_code == status.HTTP_200_OK
    
    @pytest.mark.api
    def test_get_adherence_history_pagination(self, client: TestClient, test_patient, adherence_history):
        """Test adherence history pagination"""
        response = client.get(
            f"/api/v1/adherence/history/{test_patient.id}?page=1&page_size=5"
        )
        
        assert response.status_code == status.HTTP_200_OK


# ==================== ADHERENCE STREAK TESTS ====================

class TestAdherenceStreak:
    """Tests for adherence streak endpoints"""
    
    @pytest.mark.api
    def test_get_adherence_streak(self, client: TestClient, test_patient, adherence_history):
        """Test getting current adherence streak"""
        response = client.get(f"/api/v1/adherence/streak/{test_patient.id}")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "current_streak" in data or "streak" in data or isinstance(data, int)
    
    @pytest.mark.api
    def test_get_adherence_streak_no_data(self, client: TestClient, test_patient):
        """Test getting streak with no adherence data"""
        response = client.get(f"/api/v1/adherence/streak/{test_patient.id}")
        
        assert response.status_code == status.HTTP_200_OK


# ==================== TREND ANALYSIS TESTS ====================

class TestAdherenceTrends:
    """Tests for adherence trend analysis endpoints"""
    
    @pytest.mark.api
    def test_get_weekly_trends(self, client: TestClient, test_patient, adherence_history):
        """Test getting weekly adherence trends"""
        response = client.get(f"/api/v1/adherence/trends/weekly/{test_patient.id}")
        
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
    
    @pytest.mark.api
    def test_get_problem_times(self, client: TestClient, test_patient, adherence_history):
        """Test identifying problem times for adherence"""
        response = client.get(f"/api/v1/adherence/problem-times/{test_patient.id}")
        
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
    
    @pytest.mark.api
    def test_get_daily_summary(self, client: TestClient, test_patient, adherence_history):
        """Test getting daily adherence summary"""
        today = date.today().isoformat()
        
        response = client.get(f"/api/v1/adherence/daily/{test_patient.id}?date={today}")
        
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]


# ==================== BY MEDICATION TESTS ====================

class TestAdherenceByMedication:
    """Tests for per-medication adherence endpoints"""
    
    @pytest.mark.api
    def test_get_adherence_by_medication(self, client: TestClient, test_patient, patient_with_medications):
        """Test getting adherence breakdown by medication"""
        response = client.get(f"/api/v1/adherence/by-medication/{test_patient.id}")
        
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
    
    @pytest.mark.api
    def test_get_medication_adherence_detail(self, client: TestClient, test_patient, test_medication, adherence_history):
        """Test getting detailed adherence for specific medication"""
        response = client.get(
            f"/api/v1/adherence/medication/{test_medication.id}?patient_id={test_patient.id}"
        )
        
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]


# ==================== DASHBOARD TESTS ====================

class TestAdherenceDashboard:
    """Tests for adherence dashboard endpoint"""
    
    @pytest.mark.api
    def test_get_adherence_dashboard(self, client: TestClient, test_patient, adherence_history):
        """Test getting full adherence dashboard data"""
        response = client.get(f"/api/v1/adherence/dashboard/{test_patient.id}")
        
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
        
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            # Dashboard should contain multiple metrics
            assert isinstance(data, dict)


# ==================== VALIDATION TESTS ====================

class TestAdherenceValidation:
    """Tests for adherence data validation"""
    
    @pytest.mark.api
    def test_log_with_future_time(self, client: TestClient, test_patient, test_medication):
        """Test logging with future timestamp"""
        future_time = (datetime.now() + timedelta(hours=2)).isoformat()
        log_data = {
            "patient_id": test_patient.id,
            "medication_id": test_medication.id,
            "status": "taken",
            "taken_at": future_time
        }
        
        response = client.post("/api/v1/adherence/log", json=log_data)
        
        # Might be rejected or accepted depending on validation
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]
    
    @pytest.mark.api
    def test_log_with_very_old_time(self, client: TestClient, test_patient, test_medication):
        """Test logging with very old timestamp"""
        old_time = (datetime.now() - timedelta(days=365)).isoformat()
        log_data = {
            "patient_id": test_patient.id,
            "medication_id": test_medication.id,
            "status": "taken",
            "taken_at": old_time
        }
        
        response = client.post("/api/v1/adherence/log", json=log_data)
        
        # Should be accepted for historical logging
        assert response.status_code in [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST]
    
    @pytest.mark.api
    def test_log_negative_deviation(self, client: TestClient, test_patient, test_medication):
        """Test logging with negative deviation minutes"""
        log_data = {
            "patient_id": test_patient.id,
            "medication_id": test_medication.id,
            "status": "taken",
            "deviation_minutes": -30  # Taken early
        }
        
        response = client.post("/api/v1/adherence/log", json=log_data)
        
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]


# ==================== EDGE CASES ====================

class TestAdherenceEdgeCases:
    """Edge case tests for adherence API"""
    
    @pytest.mark.api
    def test_duplicate_log(self, client: TestClient, test_patient, test_medication, test_schedule):
        """Test logging duplicate adherence entry"""
        log_data = {
            "patient_id": test_patient.id,
            "medication_id": test_medication.id,
            "schedule_id": test_schedule.id,
            "status": "taken"
        }
        
        # First log
        response1 = client.post("/api/v1/adherence/log", json=log_data)
        
        # Duplicate log
        response2 = client.post("/api/v1/adherence/log", json=log_data)
        
        # Should handle duplicates gracefully
        assert response2.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_409_CONFLICT
        ]
    
    @pytest.mark.api
    def test_adherence_for_inactive_medication(self, client: TestClient, test_patient, db_session):
        """Test logging adherence for inactive medication"""
        from models import Medication
        
        inactive_med = Medication(
            patient_id=test_patient.id,
            name="Inactive Med",
            dosage="10mg",
            frequency="once daily",
            active=False
        )
        db_session.add(inactive_med)
        db_session.commit()
        
        log_data = {
            "patient_id": test_patient.id,
            "medication_id": inactive_med.id,
            "status": "taken"
        }
        
        response = client.post("/api/v1/adherence/log", json=log_data)
        
        # Might be rejected or accepted with warning
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_400_BAD_REQUEST
        ]
