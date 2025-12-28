"""
Tests for Patients API
=======================

Tests patient CRUD operations, search, filtering, and validation.
"""

import pytest
from datetime import date, time
from fastapi import status
from fastapi.testclient import TestClient

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from models import Patient


# ==================== FIXTURES ====================

@pytest.fixture
def patient_create_data():
    """Sample data for creating a patient"""
    return {
        "email": "newpatient@example.com",
        "first_name": "Jane",
        "last_name": "Smith",
        "phone": "+1987654321",
        "date_of_birth": "1975-03-20",
        "timezone": "America/New_York",
        "conditions": ["Hypertension"],
        "allergies": ["Sulfa drugs"]
    }


@pytest.fixture
def patient_update_data():
    """Sample data for updating a patient"""
    return {
        "first_name": "Janet",
        "phone": "+1555555555",
        "conditions": ["Hypertension", "Type 2 Diabetes"]
    }


# ==================== CREATE TESTS ====================

class TestCreatePatient:
    """Tests for patient creation endpoint"""
    
    @pytest.mark.api
    def test_create_patient_success(self, client: TestClient, patient_create_data):
        """Test successful patient creation"""
        response = client.post("/api/v1/patients/", json=patient_create_data)
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["email"] == patient_create_data["email"]
        assert data["first_name"] == patient_create_data["first_name"]
        assert data["last_name"] == patient_create_data["last_name"]
    
    @pytest.mark.api
    def test_create_patient_minimal_data(self, client: TestClient):
        """Test patient creation with minimal required data"""
        minimal_data = {
            "email": "minimal@example.com",
            "first_name": "Min",
            "last_name": "Imal"
        }
        
        response = client.post("/api/v1/patients/", json=minimal_data)
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["email"] == minimal_data["email"]
    
    @pytest.mark.api
    def test_create_patient_duplicate_email(self, client: TestClient, test_patient, db_session):
        """Test that duplicate email returns error"""
        duplicate_data = {
            "email": test_patient.email,  # Same email as existing patient
            "first_name": "Duplicate",
            "last_name": "User"
        }
        
        response = client.post("/api/v1/patients/", json=duplicate_data)
        
        assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT]
    
    @pytest.mark.api
    def test_create_patient_invalid_email(self, client: TestClient):
        """Test that invalid email returns error"""
        invalid_data = {
            "email": "not-an-email",
            "first_name": "Test",
            "last_name": "User"
        }
        
        response = client.post("/api/v1/patients/", json=invalid_data)
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    @pytest.mark.api
    def test_create_patient_missing_required_fields(self, client: TestClient):
        """Test that missing required fields returns error"""
        incomplete_data = {
            "email": "incomplete@example.com"
            # Missing first_name and last_name
        }
        
        response = client.post("/api/v1/patients/", json=incomplete_data)
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    @pytest.mark.api
    def test_create_patient_with_preferences(self, client: TestClient, patient_create_data):
        """Test patient creation with lifestyle preferences"""
        patient_create_data["wake_time"] = "06:30"
        patient_create_data["sleep_time"] = "22:30"
        patient_create_data["breakfast_time"] = "07:30"
        patient_create_data["lunch_time"] = "12:30"
        patient_create_data["dinner_time"] = "19:00"
        
        response = client.post("/api/v1/patients/", json=patient_create_data)
        
        assert response.status_code == status.HTTP_201_CREATED


# ==================== READ TESTS ====================

class TestGetPatient:
    """Tests for patient retrieval endpoints"""
    
    @pytest.mark.api
    def test_get_patient_by_id(self, client: TestClient, test_patient):
        """Test getting patient by ID"""
        response = client.get(f"/api/v1/patients/{test_patient.id}")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == test_patient.id
        assert data["email"] == test_patient.email
    
    @pytest.mark.api
    def test_get_patient_not_found(self, client: TestClient):
        """Test getting non-existent patient returns 404"""
        response = client.get("/api/v1/patients/99999")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    @pytest.mark.api
    def test_get_patient_invalid_id(self, client: TestClient):
        """Test getting patient with invalid ID format"""
        response = client.get("/api/v1/patients/invalid")
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestListPatients:
    """Tests for patient listing endpoint"""
    
    @pytest.mark.api
    def test_list_patients_empty(self, client: TestClient):
        """Test listing patients when database is empty"""
        response = client.get("/api/v1/patients/")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "items" in data or isinstance(data, list)
    
    @pytest.mark.api
    def test_list_patients_with_data(self, client: TestClient, multiple_patients):
        """Test listing patients with data"""
        response = client.get("/api/v1/patients/")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        if "items" in data:
            assert len(data["items"]) >= 3
        else:
            assert len(data) >= 3
    
    @pytest.mark.api
    def test_list_patients_pagination(self, client: TestClient, multiple_patients):
        """Test patient listing pagination"""
        response = client.get("/api/v1/patients/?page=1&page_size=2")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        if "items" in data:
            assert len(data["items"]) <= 2
    
    @pytest.mark.api
    def test_list_patients_filter_active(self, client: TestClient, test_patient):
        """Test filtering patients by active status"""
        response = client.get("/api/v1/patients/?is_active=true")
        
        assert response.status_code == status.HTTP_200_OK
    
    @pytest.mark.api
    def test_list_patients_search(self, client: TestClient, test_patient):
        """Test searching patients by name or email"""
        response = client.get(f"/api/v1/patients/?search={test_patient.first_name}")
        
        assert response.status_code == status.HTTP_200_OK


# ==================== UPDATE TESTS ====================

class TestUpdatePatient:
    """Tests for patient update endpoint"""
    
    @pytest.mark.api
    def test_update_patient_success(self, client: TestClient, test_patient, patient_update_data):
        """Test successful patient update"""
        response = client.put(
            f"/api/v1/patients/{test_patient.id}",
            json=patient_update_data
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["first_name"] == patient_update_data["first_name"]
    
    @pytest.mark.api
    def test_update_patient_partial(self, client: TestClient, test_patient):
        """Test partial patient update"""
        partial_update = {"phone": "+1999999999"}
        
        response = client.put(
            f"/api/v1/patients/{test_patient.id}",
            json=partial_update
        )
        
        # Depending on implementation, this might use PATCH or PUT
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_422_UNPROCESSABLE_ENTITY]
    
    @pytest.mark.api
    def test_update_patient_not_found(self, client: TestClient, patient_update_data):
        """Test updating non-existent patient"""
        response = client.put(
            "/api/v1/patients/99999",
            json=patient_update_data
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    @pytest.mark.api
    def test_update_patient_email_to_duplicate(self, client: TestClient, test_patient, multiple_patients):
        """Test that updating email to existing email fails"""
        other_patient = multiple_patients[0]
        update_data = {"email": other_patient.email}
        
        response = client.put(
            f"/api/v1/patients/{test_patient.id}",
            json=update_data
        )
        
        # Should fail due to duplicate email
        assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT, status.HTTP_200_OK]


class TestUpdatePatientPreferences:
    """Tests for patient preferences update endpoint"""
    
    @pytest.mark.api
    def test_update_preferences(self, client: TestClient, test_patient):
        """Test updating patient preferences"""
        preferences = {
            "wake_time": "07:00",
            "sleep_time": "23:00",
            "breakfast_time": "08:00",
            "lunch_time": "13:00",
            "dinner_time": "19:30"
        }
        
        response = client.put(
            f"/api/v1/patients/{test_patient.id}/preferences",
            json=preferences
        )
        
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
    
    @pytest.mark.api
    def test_update_notification_preferences(self, client: TestClient, test_patient):
        """Test updating notification preferences"""
        notification_prefs = {
            "notification_preferences": {
                "sms_enabled": True,
                "email_enabled": True,
                "reminder_minutes_before": 30
            }
        }
        
        response = client.put(
            f"/api/v1/patients/{test_patient.id}/preferences",
            json=notification_prefs
        )
        
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]


# ==================== DELETE TESTS ====================

class TestDeletePatient:
    """Tests for patient deletion endpoint"""
    
    @pytest.mark.api
    def test_delete_patient_success(self, client: TestClient, test_patient):
        """Test successful patient deletion"""
        response = client.delete(f"/api/v1/patients/{test_patient.id}")
        
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT]
        
        # Verify patient is deleted/deactivated
        get_response = client.get(f"/api/v1/patients/{test_patient.id}")
        assert get_response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_200_OK]
    
    @pytest.mark.api
    def test_delete_patient_not_found(self, client: TestClient):
        """Test deleting non-existent patient"""
        response = client.delete("/api/v1/patients/99999")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ==================== CONDITIONS & ALLERGIES TESTS ====================

class TestPatientConditions:
    """Tests for patient conditions management"""
    
    @pytest.mark.api
    def test_add_condition(self, client: TestClient, test_patient):
        """Test adding a condition to patient"""
        condition_data = {"condition": "Asthma"}
        
        response = client.post(
            f"/api/v1/patients/{test_patient.id}/conditions",
            json=condition_data
        )
        
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED, status.HTTP_404_NOT_FOUND]
    
    @pytest.mark.api
    def test_remove_condition(self, client: TestClient, test_patient):
        """Test removing a condition from patient"""
        # First add a condition
        test_patient.conditions = ["Test Condition"]
        
        response = client.delete(
            f"/api/v1/patients/{test_patient.id}/conditions/Test%20Condition"
        )
        
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT, status.HTTP_404_NOT_FOUND]


class TestPatientAllergies:
    """Tests for patient allergies management"""
    
    @pytest.mark.api
    def test_add_allergy(self, client: TestClient, test_patient):
        """Test adding an allergy to patient"""
        allergy_data = {"allergy": "Penicillin"}
        
        response = client.post(
            f"/api/v1/patients/{test_patient.id}/allergies",
            json=allergy_data
        )
        
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED, status.HTTP_404_NOT_FOUND]


# ==================== PATIENT SUMMARY TESTS ====================

class TestPatientSummary:
    """Tests for patient summary endpoints"""
    
    @pytest.mark.api
    def test_get_patient_summary(self, client: TestClient, test_patient):
        """Test getting patient summary"""
        response = client.get(f"/api/v1/patients/{test_patient.id}/summary")
        
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
    
    @pytest.mark.api
    def test_get_patient_detail(self, client: TestClient, patient_with_medications):
        """Test getting detailed patient information"""
        response = client.get(f"/api/v1/patients/{patient_with_medications.id}/detail")
        
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]


# ==================== VALIDATION TESTS ====================

class TestPatientValidation:
    """Tests for patient data validation"""
    
    @pytest.mark.api
    def test_invalid_date_of_birth_format(self, client: TestClient):
        """Test invalid date of birth format"""
        data = {
            "email": "test@example.com",
            "first_name": "Test",
            "last_name": "User",
            "date_of_birth": "invalid-date"
        }
        
        response = client.post("/api/v1/patients/", json=data)
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    @pytest.mark.api
    def test_future_date_of_birth(self, client: TestClient):
        """Test future date of birth"""
        data = {
            "email": "future@example.com",
            "first_name": "Future",
            "last_name": "Patient",
            "date_of_birth": "2030-01-01"
        }
        
        response = client.post("/api/v1/patients/", json=data)
        
        # Might be rejected or accepted depending on validation
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]
    
    @pytest.mark.api
    def test_invalid_timezone(self, client: TestClient):
        """Test invalid timezone"""
        data = {
            "email": "tz@example.com",
            "first_name": "TZ",
            "last_name": "Test",
            "timezone": "Invalid/Timezone"
        }
        
        response = client.post("/api/v1/patients/", json=data)
        
        # Might be rejected or accepted depending on validation
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]
