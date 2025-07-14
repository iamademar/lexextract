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
                "message": "Hello"
            }
        )
        
        # Assertions
        assert response.status_code == status.HTTP_200_OK
        
        response_data = response.json()

        assert response_data["response"] == "Hello! How can I help you today?"
        assert "sql" in response_data
        
        # Check that the service was called with correct parameters
        mock_query_mistral.assert_called_once_with("Hello")

    @patch('app.routers.chat.query_mistral')
    def test_chat_endpoint_with_different_messages(self, mock_query_mistral):
        """Test chat endpoint with different messages"""
        mock_query_mistral.return_value = "Response"
        
        # Test with different messages
        test_cases = ["Hello world", "How are you?", "What's the weather?", "Test message"]
        
        for message in test_cases:
            response = self.client.post(
                "/chat",
                json={
                    "message": message
                }
            )
            
            assert response.status_code == status.HTTP_200_OK

    @patch('app.routers.chat.query_mistral')
    def test_chat_endpoint_with_sql_fallback(self, mock_query_mistral):
        """Test chat endpoint falling back to Mistral for general queries"""
        mock_query_mistral.return_value = "I can help you with general questions!"
        
        # Test with a general query (not DB-related)
        response = self.client.post(
            "/chat",
            json={
                "message": "Tell me a joke"
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        
        response_data = response.json()
        assert response_data["response"] == "I can help you with general questions!"
        assert response_data["sql"] is None

    @patch('app.routers.chat.query_mistral')
    def test_chat_endpoint_with_empty_message(self, mock_query_mistral):
        """Test chat endpoint with empty message"""
        mock_query_mistral.return_value = "Please provide a message"
        
        response = self.client.post(
            "/chat",
            json={
                "message": ""
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        
        response_data = response.json()
        assert response_data["response"] == "Please provide a message"

    @patch('app.routers.chat.query_mistral')
    def test_chat_endpoint_with_unicode_message(self, mock_query_mistral):
        """Test chat endpoint with unicode characters"""
        mock_query_mistral.return_value = "Unicode response: 🎉"
        
        response = self.client.post(
            "/chat",
            json={
                "message": "Hello 世界! 🌍"
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        
        response_data = response.json()
        assert response_data["response"] == "Unicode response: 🎉"

    @patch('app.routers.chat.query_mistral')
    def test_chat_endpoint_with_long_message(self, mock_query_mistral):
        """Test chat endpoint with very long message"""
        mock_query_mistral.return_value = "Response to long message"
        
        # Create a very long message
        long_message = "This is a very long message. " * 100
        
        response = self.client.post(
            "/chat",
            json={
                "message": long_message
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        
        response_data = response.json()
        assert response_data["response"] == "Response to long message"

    @patch('app.routers.chat.query_mistral')
    def test_chat_endpoint_service_error(self, mock_query_mistral):
        """Test chat endpoint when service throws an error"""
        # Mock service to throw an exception
        mock_query_mistral.side_effect = Exception("Service error")
        
        response = self.client.post(
            "/chat",
            json={
                "message": "Hello"
            }
        )
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        
        response_data = response.json()
        assert response_data["detail"] == "Failed to process chat request"

    def test_chat_endpoint_missing_message(self):
        """Test chat endpoint with missing message"""
        response = self.client.post(
            "/chat",
            json={}
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
        response_data = response.json()
        assert "detail" in response_data
        
        # Check that the error mentions message
        error_details = response_data["detail"]
        assert any("message" in str(error) for error in error_details)

    def test_chat_endpoint_invalid_message_type(self):
        """Test chat endpoint with invalid message type"""
        response = self.client.post(
            "/chat",
            json={
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
                "message": "Hello"
            })
        )
        
        # This should still work as FastAPI is flexible with content types
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_422_UNPROCESSABLE_ENTITY] 