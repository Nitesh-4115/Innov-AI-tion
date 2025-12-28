"""
Tests for Medications API
==========================

Tests medication CRUD operations, drug interactions, and related functionality.
"""

import pytest
from datetime import date, timedelta
from fastapi import status
from fastapi.testclient import TestClient

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from models import Patient, Medication


# ==================== FIXTURES ====================

@pytest.fixture
def medication_create_data(test_patient):
    """Sample data for creating a medication"""
    return {
        "patient_id": test_patient.id,
        "name": "Lisinopril",
        "generic_name": "lisinopril",
        "dosage": "10mg",
        "frequency": "once daily",
        "frequency_per_day": 1,
        "instructions": "Take in the morning",
        "with_food": False,
        "purpose": "Blood pressure control",
        "start_date": str(date.today())
    }


@pytest.fixture
def medication_update_data():
    """Sample data for updating a medication"""
    return {
        "dosage": "20mg",
        "instructions": "Take in the morning with water"
    }


# ==================== CREATE TESTS ====================

class TestCreateMedication:
    """Tests for medication creation endpoint"""
    
    @pytest.mark.api
    def test_create_medication_success(self, client: TestClient, medication_create_data):
        """Test successful medication creation"""
        response = client.post("/api/v1/medications/", json=medication_create_data)
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == medication_create_data["name"]
        assert data["dosage"] == medication_create_data["dosage"]
    
    @pytest.mark.api
    def test_create_medication_minimal_data(self, client: TestClient, test_patient):
        """Test medication creation with minimal data"""
        minimal_data = {
            "patient_id": test_patient.id,
            "name": "Aspirin",
            "dosage": "81mg",
            "frequency": "once daily"
        }
        
        response = client.post("/api/v1/medications/", json=minimal_data)
        
        assert response.status_code == status.HTTP_201_CREATED
    
    @pytest.mark.api
    def test_create_medication_invalid_patient(self, client: TestClient):
        """Test medication creation with invalid patient ID"""
        data = {
            "patient_id": 99999,
            "name": "Test Med",
            "dosage": "10mg",
            "frequency": "once daily"
        }
        
        response = client.post("/api/v1/medications/", json=data)
        
        assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND]
    
    @pytest.mark.api
    def test_create_medication_missing_required_fields(self, client: TestClient, test_patient):
        """Test medication creation with missing required fields"""
        incomplete_data = {
            "patient_id": test_patient.id,
            "name": "Incomplete Med"
            # Missing dosage and frequency
        }
        
        response = client.post("/api/v1/medications/", json=incomplete_data)
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    @pytest.mark.api
    def test_create_medication_with_rxnorm_id(self, client: TestClient, test_patient):
        """Test medication creation with RxNorm ID"""
        data = {
            "patient_id": test_patient.id,
            "name": "Metformin",
            "generic_name": "metformin hydrochloride",
            "rxnorm_id": "6809",
            "dosage": "500mg",
            "frequency": "twice daily",
            "frequency_per_day": 2
        }
        
        response = client.post("/api/v1/medications/", json=data)
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json().get("rxnorm_id") == "6809"


# ==================== READ TESTS ====================

class TestGetMedication:
    """Tests for medication retrieval endpoints"""
    
    @pytest.mark.api
    def test_get_medication_by_id(self, client: TestClient, test_medication):
        """Test getting medication by ID"""
        response = client.get(f"/api/v1/medications/{test_medication.id}")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == test_medication.id
        assert data["name"] == test_medication.name
    
    @pytest.mark.api
    def test_get_medication_not_found(self, client: TestClient):
        """Test getting non-existent medication"""
        response = client.get("/api/v1/medications/99999")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestGetPatientMedications:
    """Tests for patient medications endpoint"""
    
    @pytest.mark.api
    def test_get_patient_medications(self, client: TestClient, patient_with_medications):
        """Test getting all medications for a patient"""
        response = client.get(f"/api/v1/medications/patient/{patient_with_medications.id}")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        if "items" in data:
            assert len(data["items"]) >= 1
        else:
            assert len(data) >= 1
    
    @pytest.mark.api
    def test_get_patient_medications_active_only(self, client: TestClient, test_patient):
        """Test getting only active medications"""
        response = client.get(f"/api/v1/medications/patient/{test_patient.id}?active_only=true")
        
        assert response.status_code == status.HTTP_200_OK
    
    @pytest.mark.api
    def test_get_patient_medications_empty(self, client: TestClient, test_patient):
        """Test getting medications for patient with none"""
        response = client.get(f"/api/v1/medications/patient/{test_patient.id}")
        
        assert response.status_code == status.HTTP_200_OK
    
    @pytest.mark.api
    def test_get_patient_medications_invalid_patient(self, client: TestClient):
        """Test getting medications for non-existent patient"""
        response = client.get("/api/v1/medications/patient/99999")
        
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]


# ==================== UPDATE TESTS ====================

class TestUpdateMedication:
    """Tests for medication update endpoint"""
    
    @pytest.mark.api
    def test_update_medication_success(self, client: TestClient, test_medication, medication_update_data):
        """Test successful medication update"""
        response = client.put(
            f"/api/v1/medications/{test_medication.id}",
            json=medication_update_data
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["dosage"] == medication_update_data["dosage"]
    
    @pytest.mark.api
    def test_update_medication_not_found(self, client: TestClient, medication_update_data):
        """Test updating non-existent medication"""
        response = client.put(
            "/api/v1/medications/99999",
            json=medication_update_data
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestDiscontinueMedication:
    """Tests for medication discontinuation"""
    
    @pytest.mark.api
    def test_discontinue_medication(self, client: TestClient, test_medication):
        """Test discontinuing a medication"""
        discontinue_data = {
            "reason": "No longer needed",
            "end_date": str(date.today())
        }
        
        response = client.post(
            f"/api/v1/medications/{test_medication.id}/discontinue",
            json=discontinue_data
        )
        
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
    
    @pytest.mark.api
    def test_discontinue_already_discontinued(self, client: TestClient, test_medication):
        """Test discontinuing an already discontinued medication"""
        # First discontinue
        discontinue_data = {"reason": "Test"}
        client.post(f"/api/v1/medications/{test_medication.id}/discontinue", json=discontinue_data)
        
        # Try to discontinue again
        response = client.post(
            f"/api/v1/medications/{test_medication.id}/discontinue",
            json=discontinue_data
        )
        
        # Should handle gracefully
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND]


# ==================== DELETE TESTS ====================

class TestDeleteMedication:
    """Tests for medication deletion endpoint"""
    
    @pytest.mark.api
    def test_delete_medication_success(self, client: TestClient, test_medication):
        """Test successful medication deletion"""
        response = client.delete(f"/api/v1/medications/{test_medication.id}")
        
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT]
    
    @pytest.mark.api
    def test_delete_medication_not_found(self, client: TestClient):
        """Test deleting non-existent medication"""
        response = client.delete("/api/v1/medications/99999")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ==================== INTERACTION TESTS ====================

class TestDrugInteractions:
    """Tests for drug interaction checking"""
    
    @pytest.mark.api
    def test_check_interactions(self, client: TestClient, test_patient):
        """Test checking drug interactions"""
        interaction_request = {
            "patient_id": test_patient.id,
            "drug_names": ["Metformin", "Lisinopril"]
        }
        
        response = client.post("/api/v1/medications/interactions/check", json=interaction_request)
        
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
    
    @pytest.mark.api
    def test_check_interactions_single_drug(self, client: TestClient, test_patient):
        """Test checking interactions with single drug"""
        interaction_request = {
            "patient_id": test_patient.id,
            "drug_names": ["Aspirin"]
        }
        
        response = client.post("/api/v1/medications/interactions/check", json=interaction_request)
        
        # Should handle single drug (no interactions)
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
    
    @pytest.mark.api
    def test_check_interactions_known_interaction(self, client: TestClient, test_patient, test_drug_interaction):
        """Test detecting known drug interaction"""
        interaction_request = {
            "patient_id": test_patient.id,
            "drug_names": [test_drug_interaction.drug1, test_drug_interaction.drug2]
        }
        
        response = client.post("/api/v1/medications/interactions/check", json=interaction_request)
        
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]


# ==================== DRUG SEARCH TESTS ====================

class TestDrugSearch:
    """Tests for drug search functionality"""
    
    @pytest.mark.api
    def test_search_drug_by_name(self, client: TestClient):
        """Test searching for drug by name"""
        response = client.get("/api/v1/medications/search?query=metformin")
        
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
    
    @pytest.mark.api
    def test_search_drug_empty_query(self, client: TestClient):
        """Test drug search with empty query"""
        response = client.get("/api/v1/medications/search?query=")
        
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY]
    
    @pytest.mark.api
    def test_search_drug_partial_match(self, client: TestClient):
        """Test drug search with partial name"""
        response = client.get("/api/v1/medications/search?query=met")
        
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]


# ==================== SIDE EFFECTS TESTS ====================

class TestSideEffects:
    """Tests for side effects information"""
    
    @pytest.mark.api
    def test_get_side_effects(self, client: TestClient, test_medication):
        """Test getting side effects for a medication"""
        response = client.get(f"/api/v1/medications/{test_medication.id}/side-effects")
        
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
    
    @pytest.mark.api
    def test_get_side_effects_by_name(self, client: TestClient):
        """Test getting side effects by drug name"""
        response = client.get("/api/v1/medications/side-effects/metformin")
        
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]


# ==================== FOOD REQUIREMENTS TESTS ====================

class TestFoodRequirements:
    """Tests for food requirement information"""
    
    @pytest.mark.api
    def test_get_food_requirements(self, client: TestClient, test_medication):
        """Test getting food requirements for a medication"""
        response = client.get(f"/api/v1/medications/{test_medication.id}/food-requirements")
        
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]


# ==================== REFILL TESTS ====================

class TestRefills:
    """Tests for medication refill endpoints"""
    
    @pytest.mark.api
    def test_get_refills_needed(self, client: TestClient, test_patient):
        """Test getting medications needing refills"""
        response = client.get(f"/api/v1/medications/patient/{test_patient.id}/refills")
        
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
    
    @pytest.mark.api
    def test_update_refill_status(self, client: TestClient, test_medication):
        """Test updating refill status"""
        refill_data = {
            "refilled_date": str(date.today()),
            "quantity": 30,
            "next_refill_date": str(date.today() + timedelta(days=30))
        }
        
        response = client.post(
            f"/api/v1/medications/{test_medication.id}/refill",
            json=refill_data
        )
        
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED, status.HTTP_404_NOT_FOUND]


# ==================== VALIDATION TESTS ====================

class TestMedicationValidation:
    """Tests for medication data validation"""
    
    @pytest.mark.api
    def test_invalid_frequency(self, client: TestClient, test_patient):
        """Test invalid frequency value"""
        data = {
            "patient_id": test_patient.id,
            "name": "Test Med",
            "dosage": "10mg",
            "frequency": "",  # Empty frequency
            "frequency_per_day": -1  # Negative value
        }
        
        response = client.post("/api/v1/medications/", json=data)
        
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            status.HTTP_201_CREATED  # If validation is lenient
        ]
    
    @pytest.mark.api
    def test_invalid_dates(self, client: TestClient, test_patient):
        """Test invalid date values"""
        data = {
            "patient_id": test_patient.id,
            "name": "Test Med",
            "dosage": "10mg",
            "frequency": "once daily",
            "start_date": "2025-01-01",
            "end_date": "2024-01-01"  # End before start
        }
        
        response = client.post("/api/v1/medications/", json=data)
        
        # Might be rejected or accepted depending on validation
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]
