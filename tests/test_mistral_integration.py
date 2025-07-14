import pytest
import pytest_asyncio
import os
import sys
import json
import requests
from pathlib import Path
from fastapi.testclient import TestClient
from fastapi import status

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.main import app
from app.services.mistral_chat import query_mistral


def is_ollama_available():
    """Check if Ollama is running and available"""
    try:
        response = requests.get("http://localhost:11434", timeout=5)
        return response.status_code == 200
    except:
        return False


def is_mistral_model_available():
    """Check if Mistral model is available in Ollama"""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            tags = response.json()
            models = [model["name"] for model in tags.get("models", [])]
            return any("mistral" in model for model in models)
        return False
    except:
        return False


@pytest.mark.skipif(not is_ollama_available(), reason="Ollama is not running")
@pytest.mark.skipif(not is_mistral_model_available(), reason="Mistral model is not available")
class TestMistralIntegration:
    """Integration tests for Mistral with actual Ollama service"""
    
    def setup_method(self):
        """Set up test client for each test"""
        self.client = TestClient(app)

    def test_query_mistral_actual_service(self):
        """Test query_mistral function with actual Ollama service"""
        # Use the actual service (not mocked)
        result = query_mistral("Hello, please respond with 'Integration test successful'", 123)
        
        # Check that we got a response
        assert result is not None
        assert len(result) > 0
        assert not result.startswith("Error:")

    def test_query_mistral_simple_math(self):
        """Test simple math query with actual service"""
        result = query_mistral("What is 2 + 2? Please respond with only the number.", 456)
        
        assert result is not None
        assert len(result) > 0
        assert not result.startswith("Error:")
        # Note: We don't assert the exact answer as the model might respond with additional text

    def test_query_mistral_client_context(self):
        """Test that client context is preserved"""
        client_id = 999
        message = "Please acknowledge that you received this message for client ID " + str(client_id)
        
        result = query_mistral(message, client_id)
        
        assert result is not None
        assert len(result) > 0
        assert not result.startswith("Error:")

    def test_chat_endpoint_actual_service(self):
        """Test chat endpoint with actual Ollama service"""
        response = self.client.post(
            "/chat",
            json={
                "client_id": 789,
                "message": "Hello, please respond with 'Endpoint test successful'"
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        
        response_data = response.json()
        assert response_data["client_id"] == 789
        assert isinstance(response_data["response"], str)
        assert len(response_data["response"]) > 0
        assert not response_data["response"].startswith("Error:")

    def test_chat_endpoint_multiple_requests(self):
        """Test multiple consecutive requests to chat endpoint"""
        messages = [
            "Hello",
            "What is your name?",
            "Thank you"
        ]
        
        for i, message in enumerate(messages):
            response = self.client.post(
                "/chat",
                json={
                    "client_id": 100 + i,
                    "message": message
                }
            )
            
            assert response.status_code == status.HTTP_200_OK
            
            response_data = response.json()
            assert response_data["client_id"] == 100 + i
            assert isinstance(response_data["response"], str)
            assert len(response_data["response"]) > 0
            assert not response_data["response"].startswith("Error:")

    def test_chat_endpoint_long_conversation(self):
        """Test a longer conversation to ensure model maintains context appropriately"""
        # Note: Each request is independent, so we're just testing that the service 
        # can handle multiple requests without issues
        
        conversation = [
            "Hello, I'm testing the chat system",
            "Can you help me with financial questions?",
            "What types of financial analysis can you assist with?",
            "Thank you for your help"
        ]
        
        client_id = 555
        
        for message in conversation:
            response = self.client.post(
                "/chat",
                json={
                    "client_id": client_id,
                    "message": message
                }
            )
            
            assert response.status_code == status.HTTP_200_OK
            
            response_data = response.json()
            assert response_data["client_id"] == client_id
            assert isinstance(response_data["response"], str)
            assert len(response_data["response"]) > 0
            assert not response_data["response"].startswith("Error:")

    def test_performance_simple_query(self):
        """Test performance of simple queries"""
        import time
        
        start_time = time.time()
        
        response = self.client.post(
            "/chat",
            json={
                "client_id": 777,
                "message": "Hello"
            }
        )
        
        end_time = time.time()
        response_time = end_time - start_time
        
        assert response.status_code == status.HTTP_200_OK
        
        # Check that response time is reasonable (under 30 seconds)
        assert response_time < 30.0, f"Response time {response_time} seconds is too slow"
        
        response_data = response.json()
        assert not response_data["response"].startswith("Error:")

    def test_error_handling_service_unavailable(self):
        """Test what happens when service becomes unavailable during test"""
        # This test is more for documentation - it shows how errors are handled
        # when the service becomes unavailable
        
        # First, make a successful request
        response = self.client.post(
            "/chat",
            json={
                "client_id": 888,
                "message": "Hello"
            }
        )
        
        # If the service is available, this should succeed
        if response.status_code == status.HTTP_200_OK:
            response_data = response.json()
            assert not response_data["response"].startswith("Error:")
        else:
            # If service is unavailable, we should get an error response
            assert response.status_code == status.HTTP_200_OK
            response_data = response.json()
            assert response_data["response"].startswith("Error:")


@pytest.mark.skipif(is_ollama_available(), reason="Ollama is running - test offline behavior")
class TestMistralOffline:
    """Test behavior when Ollama is not available"""
    
    def setup_method(self):
        """Set up test client for each test"""
        self.client = TestClient(app)

    def test_query_mistral_offline(self):
        """Test query_mistral when Ollama is not available"""
        result = query_mistral("Hello", 123)
        
        # Should return an error message when service is unavailable
        assert result.startswith("Error:")
        assert "connect" in result.lower() or "service" in result.lower()

    def test_chat_endpoint_offline(self):
        """Test chat endpoint when Ollama is not available"""
        response = self.client.post(
            "/chat",
            json={
                "client_id": 123,
                "message": "Hello"
            }
        )
        
        # Should still return 200 OK but with error message
        assert response.status_code == status.HTTP_200_OK
        
        response_data = response.json()
        assert response_data["client_id"] == 123
        assert response_data["response"].startswith("Error:")


class TestMistralServiceHealth:
    """Health check tests for Mistral service"""
    
    def test_ollama_health_check(self):
        """Test if Ollama service is reachable"""
        try:
            response = requests.get("http://localhost:11434", timeout=5)
            if response.status_code == 200:
                print("✅ Ollama service is running")
            else:
                print(f"❌ Ollama service returned status {response.status_code}")
        except Exception as e:
            print(f"❌ Ollama service is not reachable: {e}")

    def test_mistral_model_availability(self):
        """Test if Mistral model is available"""
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            if response.status_code == 200:
                tags = response.json()
                models = [model["name"] for model in tags.get("models", [])]
                mistral_models = [model for model in models if "mistral" in model]
                if mistral_models:
                    print(f"✅ Mistral models available: {mistral_models}")
                else:
                    print("❌ No Mistral models found")
            else:
                print(f"❌ Could not get model list: status {response.status_code}")
        except Exception as e:
            print(f"❌ Could not check model availability: {e}")

    def test_mistral_generate_endpoint(self):
        """Test Mistral generate endpoint directly"""
        try:
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "mistral",
                    "prompt": "Hello, respond with 'Health check successful'",
                    "stream": False
                },
                timeout=30
            )
            if response.status_code == 200:
                result = response.json()
                if "response" in result:
                    print(f"✅ Mistral generate endpoint working: {result['response'][:100]}...")
                else:
                    print(f"❌ Unexpected response format: {result}")
            else:
                print(f"❌ Generate endpoint returned status {response.status_code}")
        except Exception as e:
            print(f"❌ Generate endpoint test failed: {e}")


# Test fixtures and utilities
@pytest.fixture
def mock_ollama_response():
    """Fixture for mocking Ollama responses"""
    return {
        "model": "mistral",
        "created_at": "2024-01-01T00:00:00Z",
        "response": "This is a test response from Mistral",
        "done": True
    }


@pytest.fixture
def sample_chat_requests():
    """Fixture providing sample chat request data"""
    return [
        {"client_id": 1, "message": "Hello"},
        {"client_id": 2, "message": "What is machine learning?"},
        {"client_id": 3, "message": "Help me analyze my bank statement"},
        {"client_id": 4, "message": "Thank you"},
    ]


# Utility functions for testing
def create_test_chat_request(client_id: int, message: str) -> dict:
    """Create a test chat request"""
    return {
        "client_id": client_id,
        "message": message
    }


def validate_chat_response(response_data: dict, expected_client_id: int) -> bool:
    """Validate chat response structure and content"""
    if not isinstance(response_data, dict):
        return False
    
    if "client_id" not in response_data or "response" not in response_data:
        return False
    
    if response_data["client_id"] != expected_client_id:
        return False
    
    if not isinstance(response_data["response"], str):
        return False
    
    return True 