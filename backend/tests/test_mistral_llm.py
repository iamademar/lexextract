import pytest
import pytest_asyncio
import os
import sys
import json
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import requests

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.llms.mistral_llm import MistralLLM


class TestMistralLLM:
    """Test cases for the MistralLLM LangChain adapter"""

    def setup_method(self):
        """Set up test fixtures for each test"""
        self.llm = MistralLLM()

    def test_llm_type_property(self):
        """Test that _llm_type returns correct string"""
        assert self.llm._llm_type == "mistral-ollama"

    def test_default_initialization(self):
        """Test MistralLLM initializes with correct defaults"""
        llm = MistralLLM()
        assert llm.endpoint == "http://host.docker.internal:11434/api/generate"
        assert llm.model == "mistral"
        assert llm.timeout == 30.0

    def test_custom_initialization(self):
        """Test MistralLLM can be initialized with custom parameters"""
        llm = MistralLLM(
            endpoint="http://custom-endpoint:8080/api/generate",
            model="custom-model",
            timeout=60.0
        )
        assert llm.endpoint == "http://custom-endpoint:8080/api/generate"
        assert llm.model == "custom-model"
        assert llm.timeout == 60.0

    def test_identifying_params(self):
        """Test _identifying_params returns correct dictionary"""
        expected_params = {
            "endpoint": "http://host.docker.internal:11434/api/generate",
            "model": "mistral"
        }
        assert self.llm._identifying_params == expected_params

    @patch('app.llms.mistral_llm.requests.post')
    def test_call_success(self, mock_post):
        """Test successful _call method"""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "This is a test response from Mistral"
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        # Test the call
        result = self.llm._call("Test prompt")
        
        # Assertions
        assert result == "This is a test response from Mistral"
        mock_post.assert_called_once_with(
            "http://host.docker.internal:11434/api/generate",
            json={
                "model": "mistral",
                "prompt": "Test prompt",
                "stream": False
            },
            timeout=30.0
        )

    @patch('app.llms.mistral_llm.requests.post')
    def test_call_with_stop_sequences(self, mock_post):
        """Test _call method with stop sequences (should be ignored)"""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "Test response"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        # Test with stop sequences (should not affect the request)
        result = self.llm._call("Test prompt", stop=["STOP", "END"])
        
        # Should still make the same request (stop sequences not implemented)
        assert result == "Test response"
        mock_post.assert_called_once_with(
            "http://host.docker.internal:11434/api/generate",
            json={
                "model": "mistral",
                "prompt": "Test prompt",
                "stream": False
            },
            timeout=30.0
        )

    @patch('app.llms.mistral_llm.requests.post')
    def test_call_with_run_manager(self, mock_post):
        """Test _call method with run_manager parameter"""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "Test response"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        # Mock run manager
        mock_run_manager = Mock()
        
        # Test with run manager
        result = self.llm._call("Test prompt", run_manager=mock_run_manager)
        
        assert result == "Test response"

    @patch('app.llms.mistral_llm.requests.post')
    def test_call_strips_whitespace(self, mock_post):
        """Test that response whitespace is properly stripped"""
        # Mock response with whitespace
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "  \n  Test response  \n  "}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        result = self.llm._call("Test prompt")
        assert result == "Test response"

    @patch('app.llms.mistral_llm.requests.post')
    def test_call_empty_response(self, mock_post):
        """Test handling of empty response"""
        # Mock empty response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": ""}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        result = self.llm._call("Test prompt")
        assert result == ""

    @patch('app.llms.mistral_llm.requests.post')
    def test_call_missing_response_key(self, mock_post):
        """Test handling of missing response key"""
        # Mock response without 'response' key
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"other_key": "value"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        result = self.llm._call("Test prompt")
        assert result == ""

    @patch('app.llms.mistral_llm.requests.post')
    def test_call_connection_error(self, mock_post):
        """Test handling of connection error"""
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection failed")
        
        with pytest.raises(Exception) as exc_info:
            self.llm._call("Test prompt")
        
        assert "Unable to connect to AI service" in str(exc_info.value)

    @patch('app.llms.mistral_llm.requests.post')
    def test_call_timeout_error(self, mock_post):
        """Test handling of timeout error"""
        mock_post.side_effect = requests.exceptions.Timeout("Request timed out")
        
        with pytest.raises(Exception) as exc_info:
            self.llm._call("Test prompt")
        
        assert "Request timed out" in str(exc_info.value)

    @patch('app.llms.mistral_llm.requests.post')
    def test_call_http_error(self, mock_post):
        """Test handling of HTTP error"""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error")
        mock_post.return_value = mock_response
        
        with pytest.raises(Exception) as exc_info:
            self.llm._call("Test prompt")
        
        assert "Failed to process request" in str(exc_info.value)

    @patch('app.llms.mistral_llm.requests.post')
    def test_call_request_exception(self, mock_post):
        """Test handling of general request exception"""
        mock_post.side_effect = requests.exceptions.RequestException("General request error")
        
        with pytest.raises(Exception) as exc_info:
            self.llm._call("Test prompt")
        
        assert "Failed to process request" in str(exc_info.value)

    @patch('app.llms.mistral_llm.requests.post')
    def test_call_unexpected_error(self, mock_post):
        """Test handling of unexpected error"""
        mock_post.side_effect = ValueError("Unexpected error")
        
        with pytest.raises(Exception) as exc_info:
            self.llm._call("Test prompt")
        
        assert "An unexpected error occurred" in str(exc_info.value)

    @patch('app.llms.mistral_llm.requests.post')
    def test_call_custom_endpoint_and_model(self, mock_post):
        """Test _call with custom endpoint and model"""
        # Create LLM with custom settings
        llm = MistralLLM(
            endpoint="http://custom:9999/api/generate",
            model="custom-mistral",
            timeout=45.0
        )
        
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "Custom response"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        result = llm._call("Test prompt")
        
        assert result == "Custom response"
        mock_post.assert_called_once_with(
            "http://custom:9999/api/generate",
            json={
                "model": "custom-mistral",
                "prompt": "Test prompt",
                "stream": False
            },
            timeout=45.0
        )

    def test_call_with_kwargs(self):
        """Test _call method accepts additional kwargs without error"""
        with patch('app.llms.mistral_llm.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"response": "Test response"}
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response
            
            # Should not raise error with additional kwargs
            result = self.llm._call(
                "Test prompt", 
                some_param="value", 
                another_param=123
            )
            assert result == "Test response" 