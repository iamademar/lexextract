import pytest
import pytest_asyncio
import os
import sys
import json
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from fastapi.testclient import TestClient
from fastapi import status

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.main import app
from app.routers.chat import ChatRequest, ChatResponse


class TestChatEndpoint:
    """Test cases for the /chat endpoint"""
    
    def setup_method(self):
        """Set up test client for each test"""
        self.client = TestClient(app)

    @patch('app.routers.chat.query_mistral')
    def test_chat_endpoint_success(self, mock_query_mistral):
        """Test successful chat request"""
        # Mock the mistral service
        mock_query_mistral.return_value = "Hello! How can I help you today?"
        
        # Make request to the endpoint
        response = self.client.post(
            "/chat",
            json={
                "client_id": 123,
                "message": "Hello"
            }
        )
        
        # Assertions
        assert response.status_code == status.HTTP_200_OK
        
        response_data = response.json()
        assert response_data["client_id"] == 123
        assert response_data["response"] == "Hello! How can I help you today?"
        
        # Check that the service was called with correct parameters
        mock_query_mistral.assert_called_once_with("Hello", 123)

    @patch('app.routers.chat.query_mistral')
    def test_chat_endpoint_different_client_ids(self, mock_query_mistral):
        """Test chat endpoint with different client IDs"""
        mock_query_mistral.return_value = "Response"
        
        # Test with different client IDs
        test_cases = [1, 42, 999, 12345]
        
        for client_id in test_cases:
            response = self.client.post(
                "/chat",
                json={
                    "client_id": client_id,
                    "message": "Test message"
                }
            )
            
            assert response.status_code == status.HTTP_200_OK
            
            response_data = response.json()
            assert response_data["client_id"] == client_id
            assert response_data["response"] == "Response"

    @patch('app.routers.chat.query_mistral')
    def test_chat_endpoint_long_message(self, mock_query_mistral):
        """Test chat endpoint with long message"""
        mock_query_mistral.return_value = "I understand your long message"
        
        # Create a long message
        long_message = "This is a very long message. " * 100
        
        response = self.client.post(
            "/chat",
            json={
                "client_id": 456,
                "message": long_message
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        
        response_data = response.json()
        assert response_data["client_id"] == 456
        assert response_data["response"] == "I understand your long message"
        
        # Check that the long message was passed to the service
        mock_query_mistral.assert_called_once_with(long_message, 456)

    @patch('app.routers.chat.query_mistral')
    def test_chat_endpoint_special_characters(self, mock_query_mistral):
        """Test chat endpoint with special characters"""
        mock_query_mistral.return_value = "Handled special characters"
        
        # Test with special characters
        special_message = "Hello! @#$%^&*()_+-=[]{}|;':\",./<>?"
        
        response = self.client.post(
            "/chat",
            json={
                "client_id": 789,
                "message": special_message
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        
        response_data = response.json()
        assert response_data["client_id"] == 789
        assert response_data["response"] == "Handled special characters"
        
        # Check that special characters were preserved
        mock_query_mistral.assert_called_once_with(special_message, 789)

    @patch('app.routers.chat.query_mistral')
    def test_chat_endpoint_empty_message(self, mock_query_mistral):
        """Test chat endpoint with empty message"""
        mock_query_mistral.return_value = "Please provide a message"
        
        response = self.client.post(
            "/chat",
            json={
                "client_id": 101,
                "message": ""
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        
        response_data = response.json()
        assert response_data["client_id"] == 101
        assert response_data["response"] == "Please provide a message"
        
        # Check that empty message was passed to the service
        mock_query_mistral.assert_called_once_with("", 101)

    @patch('app.routers.chat.query_mistral')
    def test_chat_endpoint_service_error_response(self, mock_query_mistral):
        """Test chat endpoint when service returns error message"""
        mock_query_mistral.return_value = "Error: Unable to connect to AI service. Please try again later."
        
        response = self.client.post(
            "/chat",
            json={
                "client_id": 202,
                "message": "Hello"
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        
        response_data = response.json()
        assert response_data["client_id"] == 202
        assert response_data["response"] == "Error: Unable to connect to AI service. Please try again later."

    @patch('app.routers.chat.query_mistral')
    def test_chat_endpoint_service_exception(self, mock_query_mistral):
        """Test chat endpoint when service raises exception"""
        # Mock the service to raise an exception
        mock_query_mistral.side_effect = Exception("Service failed")
        
        response = self.client.post(
            "/chat",
            json={
                "client_id": 303,
                "message": "Hello"
            }
        )
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        
        response_data = response.json()
        assert response_data["detail"] == "Failed to process chat request"

    def test_chat_endpoint_missing_client_id(self):
        """Test chat endpoint with missing client_id"""
        response = self.client.post(
            "/chat",
            json={
                "message": "Hello"
            }
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
        response_data = response.json()
        assert "detail" in response_data
        
        # Check that the error mentions client_id
        error_details = response_data["detail"]
        assert any("client_id" in str(error) for error in error_details)

    def test_chat_endpoint_missing_message(self):
        """Test chat endpoint with missing message"""
        response = self.client.post(
            "/chat",
            json={
                "client_id": 123
            }
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
        response_data = response.json()
        assert "detail" in response_data
        
        # Check that the error mentions message
        error_details = response_data["detail"]
        assert any("message" in str(error) for error in error_details)

    def test_chat_endpoint_invalid_client_id_type(self):
        """Test chat endpoint with invalid client_id type"""
        response = self.client.post(
            "/chat",
            json={
                "client_id": "invalid",
                "message": "Hello"
            }
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
        response_data = response.json()
        assert "detail" in response_data
        
        # Check that the error mentions client_id type validation
        error_details = response_data["detail"]
        assert any("client_id" in str(error) and "integer" in str(error) for error in error_details)

    def test_chat_endpoint_invalid_message_type(self):
        """Test chat endpoint with invalid message type"""
        response = self.client.post(
            "/chat",
            json={
                "client_id": 123,
                "message": 456  # Should be string
            }
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
        response_data = response.json()
        assert "detail" in response_data
        
        # Check that the error mentions message type validation
        error_details = response_data["detail"]
        assert any("message" in str(error) for error in error_details)

    def test_chat_endpoint_empty_body(self):
        """Test chat endpoint with empty request body"""
        response = self.client.post(
            "/chat",
            json={}
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
        response_data = response.json()
        assert "detail" in response_data

    def test_chat_endpoint_invalid_json(self):
        """Test chat endpoint with invalid JSON"""
        response = self.client.post(
            "/chat",
            content="invalid json",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_chat_endpoint_no_content_type(self):
        """Test chat endpoint without Content-Type header"""
        response = self.client.post(
            "/chat",
            content=json.dumps({
                "client_id": 123,
                "message": "Hello"
            })
        )
        
        # This should still work as FastAPI is flexible with content types
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_422_UNPROCESSABLE_ENTITY]

    @patch('app.routers.chat.query_mistral')
    def test_chat_endpoint_negative_client_id(self, mock_query_mistral):
        """Test chat endpoint with negative client_id"""
        mock_query_mistral.return_value = "Response for negative client ID"
        
        response = self.client.post(
            "/chat",
            json={
                "client_id": -123,
                "message": "Hello"
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        
        response_data = response.json()
        assert response_data["client_id"] == -123
        assert response_data["response"] == "Response for negative client ID"

    @patch('app.routers.chat.query_mistral')
    def test_chat_endpoint_zero_client_id(self, mock_query_mistral):
        """Test chat endpoint with zero client_id"""
        mock_query_mistral.return_value = "Response for zero client ID"
        
        response = self.client.post(
            "/chat",
            json={
                "client_id": 0,
                "message": "Hello"
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        
        response_data = response.json()
        assert response_data["client_id"] == 0
        assert response_data["response"] == "Response for zero client ID"

    @patch('app.routers.chat.query_mistral')
    def test_chat_endpoint_large_client_id(self, mock_query_mistral):
        """Test chat endpoint with very large client_id"""
        mock_query_mistral.return_value = "Response for large client ID"
        
        large_client_id = 2**31 - 1  # Max 32-bit signed integer
        
        response = self.client.post(
            "/chat",
            json={
                "client_id": large_client_id,
                "message": "Hello"
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        
        response_data = response.json()
        assert response_data["client_id"] == large_client_id
        assert response_data["response"] == "Response for large client ID"

    @patch('app.routers.chat.query_mistral')
    def test_chat_endpoint_unicode_message(self, mock_query_mistral):
        """Test chat endpoint with unicode characters"""
        mock_query_mistral.return_value = "Handled unicode message"
        
        unicode_message = "Hello! 🌟 こんにちは 🎉 مرحبا"
        
        response = self.client.post(
            "/chat",
            json={
                "client_id": 555,
                "message": unicode_message
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        
        response_data = response.json()
        assert response_data["client_id"] == 555
        assert response_data["response"] == "Handled unicode message"
        
        # Check that unicode message was passed to the service
        mock_query_mistral.assert_called_once_with(unicode_message, 555)

    @patch('app.routers.chat.query_mistral')
    def test_chat_endpoint_response_schema(self, mock_query_mistral):
        """Test that response follows the correct schema"""
        mock_query_mistral.return_value = "Test response"
        
        response = self.client.post(
            "/chat",
            json={
                "client_id": 999,
                "message": "Test message"
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        
        response_data = response.json()
        
        # Check that response has exactly the expected keys
        assert set(response_data.keys()) == {"client_id", "response"}
        
        # Check that types are correct
        assert isinstance(response_data["client_id"], int)
        assert isinstance(response_data["response"], str)
        
        # Check that values are correct
        assert response_data["client_id"] == 999
        assert response_data["response"] == "Test response" 