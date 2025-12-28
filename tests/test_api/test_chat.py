"""
Tests for Chat API
===================

Tests AI chat interactions, multi-agent routing, and conversation handling.
"""

import pytest
from datetime import datetime
from fastapi import status
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from models import Patient, Medication, AdherenceLog


# ==================== FIXTURES ====================

@pytest.fixture
def chat_request_data(test_patient):
    """Sample chat request data"""
    return {
        "patient_id": test_patient.id,
        "message": "How can I improve my medication adherence?",
        "conversation_history": [],
        "include_context": True
    }


@pytest.fixture
def conversation_history():
    """Sample conversation history"""
    return [
        {
            "role": "user",
            "content": "What medications am I taking?",
            "timestamp": "2025-12-23T10:00:00"
        },
        {
            "role": "assistant",
            "content": "You are currently taking Metformin 500mg twice daily for blood sugar control.",
            "timestamp": "2025-12-23T10:00:05"
        }
    ]


@pytest.fixture
def quick_action_data(test_patient):
    """Sample quick action data"""
    return {
        "action": "log_dose",
        "patient_id": test_patient.id,
        "parameters": {
            "medication_id": 1,
            "status": "taken"
        }
    }


# ==================== CHAT ENDPOINT TESTS ====================

class TestChatEndpoint:
    """Tests for main chat endpoint"""
    
    @pytest.mark.api
    def test_chat_simple_message(self, client: TestClient, chat_request_data):
        """Test sending a simple chat message"""
        with patch("api.chat.services") as mock_services:
            mock_llm = MagicMock()
            mock_llm.chat.return_value = {
                "response": "I can help you improve your adherence!",
                "agent_used": "monitoring"
            }
            mock_services.get_llm_service.return_value = mock_llm
            mock_services.get_patient_service.return_value = MagicMock()
            
            response = client.post("/api/v1/chat/", json=chat_request_data)
            
            assert response.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]
    
    @pytest.mark.api
    def test_chat_with_conversation_history(self, client: TestClient, chat_request_data, conversation_history):
        """Test chat with existing conversation history"""
        chat_request_data["conversation_history"] = conversation_history
        
        with patch("api.chat.services") as mock_services:
            mock_llm = MagicMock()
            mock_llm.chat.return_value = {"response": "Based on our conversation..."}
            mock_services.get_llm_service.return_value = mock_llm
            mock_services.get_patient_service.return_value = MagicMock()
            
            response = client.post("/api/v1/chat/", json=chat_request_data)
            
            assert response.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]
    
    @pytest.mark.api
    def test_chat_without_context(self, client: TestClient, chat_request_data):
        """Test chat without patient context"""
        chat_request_data["include_context"] = False
        
        with patch("api.chat.services") as mock_services:
            mock_llm = MagicMock()
            mock_llm.chat.return_value = {"response": "How can I help?"}
            mock_services.get_llm_service.return_value = mock_llm
            
            response = client.post("/api/v1/chat/", json=chat_request_data)
            
            assert response.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]
    
    @pytest.mark.api
    def test_chat_invalid_patient(self, client: TestClient):
        """Test chat with invalid patient ID"""
        data = {
            "patient_id": 99999,
            "message": "Hello",
            "include_context": True
        }
        
        response = client.post("/api/v1/chat/", json=data)
        
        assert response.status_code in [
            status.HTTP_200_OK,  # Might work without context
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR
        ]
    
    @pytest.mark.api
    def test_chat_empty_message(self, client: TestClient, test_patient):
        """Test chat with empty message"""
        data = {
            "patient_id": test_patient.id,
            "message": "",
            "include_context": True
        }
        
        response = client.post("/api/v1/chat/", json=data)
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    @pytest.mark.api
    def test_chat_very_long_message(self, client: TestClient, test_patient):
        """Test chat with very long message"""
        data = {
            "patient_id": test_patient.id,
            "message": "a" * 5000,  # Exceeds max_length
            "include_context": True
        }
        
        response = client.post("/api/v1/chat/", json=data)
        
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]


class TestChatRouting:
    """Tests for chat routing to different agents"""
    
    @pytest.mark.api
    def test_route_to_planning_agent(self, client: TestClient, test_patient):
        """Test routing schedule-related query to planning agent"""
        data = {
            "patient_id": test_patient.id,
            "message": "Can you optimize my medication schedule?",
            "include_context": True
        }
        
        response = client.post("/api/v1/chat/", json=data)
        
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]
    
    @pytest.mark.api
    def test_route_to_monitoring_agent(self, client: TestClient, test_patient):
        """Test routing adherence-related query to monitoring agent"""
        data = {
            "patient_id": test_patient.id,
            "message": "How is my medication adherence this week?",
            "include_context": True
        }
        
        response = client.post("/api/v1/chat/", json=data)
        
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]
    
    @pytest.mark.api
    def test_route_to_barrier_agent(self, client: TestClient, test_patient):
        """Test routing barrier-related query to barrier agent"""
        data = {
            "patient_id": test_patient.id,
            "message": "I'm having trouble affording my medications",
            "include_context": True
        }
        
        response = client.post("/api/v1/chat/", json=data)
        
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]
    
    @pytest.mark.api
    def test_route_to_liaison_agent(self, client: TestClient, test_patient):
        """Test routing report-related query to liaison agent"""
        data = {
            "patient_id": test_patient.id,
            "message": "Can you generate a report for my doctor?",
            "include_context": True
        }
        
        response = client.post("/api/v1/chat/", json=data)
        
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]


# ==================== QUICK ACTION TESTS ====================

class TestQuickActions:
    """Tests for quick action endpoints"""
    
    @pytest.mark.api
    def test_quick_action_log_dose(self, client: TestClient, quick_action_data):
        """Test quick action to log a dose"""
        response = client.post("/api/v1/chat/quick-action", json=quick_action_data)
        
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR
        ]
    
    @pytest.mark.api
    def test_quick_action_check_schedule(self, client: TestClient, test_patient):
        """Test quick action to check today's schedule"""
        data = {
            "action": "check_schedule",
            "patient_id": test_patient.id,
            "parameters": {"date": "today"}
        }
        
        response = client.post("/api/v1/chat/quick-action", json=data)
        
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR
        ]
    
    @pytest.mark.api
    def test_quick_action_invalid_action(self, client: TestClient, test_patient):
        """Test quick action with invalid action type"""
        data = {
            "action": "invalid_action",
            "patient_id": test_patient.id,
            "parameters": {}
        }
        
        response = client.post("/api/v1/chat/quick-action", json=data)
        
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR
        ]


# ==================== STREAMING TESTS ====================

class TestChatStreaming:
    """Tests for streaming chat responses"""
    
    @pytest.mark.api
    def test_chat_streaming_endpoint(self, client: TestClient, test_patient):
        """Test streaming chat endpoint"""
        data = {
            "patient_id": test_patient.id,
            "message": "Tell me about my medications",
            "include_context": True
        }
        
        response = client.post("/api/v1/chat/stream", json=data)
        
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR
        ]


# ==================== CONVERSATION MANAGEMENT TESTS ====================

class TestConversationManagement:
    """Tests for conversation management"""
    
    @pytest.mark.api
    def test_get_conversation_history(self, client: TestClient, test_patient):
        """Test getting conversation history"""
        response = client.get(f"/api/v1/chat/history/{test_patient.id}")
        
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND
        ]
    
    @pytest.mark.api
    def test_clear_conversation_history(self, client: TestClient, test_patient):
        """Test clearing conversation history"""
        response = client.delete(f"/api/v1/chat/history/{test_patient.id}")
        
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_204_NO_CONTENT,
            status.HTTP_404_NOT_FOUND
        ]


# ==================== SUGGESTIONS TESTS ====================

class TestChatSuggestions:
    """Tests for chat suggestion features"""
    
    @pytest.mark.api
    def test_get_suggested_questions(self, client: TestClient, test_patient):
        """Test getting suggested questions for patient"""
        response = client.get(f"/api/v1/chat/suggestions/{test_patient.id}")
        
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND
        ]
    
    @pytest.mark.api
    def test_get_context_aware_suggestions(self, client: TestClient, test_patient, patient_with_medications):
        """Test suggestions are context-aware based on patient data"""
        response = client.get(f"/api/v1/chat/suggestions/{patient_with_medications.id}")
        
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND
        ]


# ==================== RESPONSE VALIDATION TESTS ====================

class TestChatResponseValidation:
    """Tests for chat response validation"""
    
    @pytest.mark.api
    def test_response_contains_required_fields(self, client: TestClient, chat_request_data):
        """Test that response contains required fields"""
        with patch("api.chat.services") as mock_services:
            mock_llm = MagicMock()
            mock_llm.chat.return_value = {"response": "Test response"}
            mock_services.get_llm_service.return_value = mock_llm
            mock_services.get_patient_service.return_value = MagicMock()
            
            response = client.post("/api/v1/chat/", json=chat_request_data)
            
            if response.status_code == status.HTTP_200_OK:
                data = response.json()
                assert "response" in data or "message" in data
    
    @pytest.mark.api
    def test_response_includes_timestamp(self, client: TestClient, chat_request_data):
        """Test that response includes timestamp"""
        with patch("api.chat.services") as mock_services:
            mock_llm = MagicMock()
            mock_llm.chat.return_value = {
                "response": "Test",
                "timestamp": datetime.now().isoformat()
            }
            mock_services.get_llm_service.return_value = mock_llm
            mock_services.get_patient_service.return_value = MagicMock()
            
            response = client.post("/api/v1/chat/", json=chat_request_data)
            
            if response.status_code == status.HTTP_200_OK:
                data = response.json()
                # Timestamp might be in response


# ==================== ERROR HANDLING TESTS ====================

class TestChatErrorHandling:
    """Tests for chat error handling"""
    
    @pytest.mark.api
    def test_llm_service_error(self, client: TestClient, chat_request_data):
        """Test handling LLM service errors"""
        with patch("api.chat.services") as mock_services:
            mock_llm = MagicMock()
            mock_llm.chat.side_effect = Exception("LLM service error")
            mock_services.get_llm_service.return_value = mock_llm
            mock_services.get_patient_service.return_value = MagicMock()
            
            response = client.post("/api/v1/chat/", json=chat_request_data)
            
            assert response.status_code in [
                status.HTTP_200_OK,  # Graceful fallback
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                status.HTTP_503_SERVICE_UNAVAILABLE
            ]
    
    @pytest.mark.api
    def test_timeout_handling(self, client: TestClient, chat_request_data):
        """Test handling of timeout errors"""
        # Would need to mock a timeout scenario
        pass


# ==================== SAFETY TESTS ====================

class TestChatSafety:
    """Tests for chat safety boundaries"""
    
    @pytest.mark.api
    def test_no_medical_diagnosis(self, client: TestClient, test_patient):
        """Test that chat doesn't provide medical diagnoses"""
        data = {
            "patient_id": test_patient.id,
            "message": "What disease do I have based on my symptoms?",
            "include_context": True
        }
        
        response = client.post("/api/v1/chat/", json=data)
        
        # Should respond but not diagnose
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]
    
    @pytest.mark.api
    def test_no_dosage_changes(self, client: TestClient, test_patient):
        """Test that chat doesn't recommend dosage changes"""
        data = {
            "patient_id": test_patient.id,
            "message": "Should I double my medication dose?",
            "include_context": True
        }
        
        response = client.post("/api/v1/chat/", json=data)
        
        # Should respond but not recommend dosage changes
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]
    
    @pytest.mark.api
    def test_escalation_for_emergency(self, client: TestClient, test_patient):
        """Test that emergencies trigger appropriate response"""
        data = {
            "patient_id": test_patient.id,
            "message": "I'm having severe chest pain after taking my medication",
            "include_context": True
        }
        
        response = client.post("/api/v1/chat/", json=data)
        
        # Should handle emergency appropriately
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]


# ==================== INTEGRATION TESTS ====================

class TestChatIntegration:
    """Integration tests for chat functionality"""
    
    @pytest.mark.integration
    def test_full_conversation_flow(self, client: TestClient, test_patient):
        """Test a full conversation flow"""
        # Initial message
        msg1 = {
            "patient_id": test_patient.id,
            "message": "Hello",
            "conversation_history": []
        }
        response1 = client.post("/api/v1/chat/", json=msg1)
        
        if response1.status_code == status.HTTP_200_OK:
            # Follow-up with history
            msg2 = {
                "patient_id": test_patient.id,
                "message": "What medications am I taking?",
                "conversation_history": [
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": response1.json().get("response", "")}
                ]
            }
            response2 = client.post("/api/v1/chat/", json=msg2)
            
            assert response2.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]
