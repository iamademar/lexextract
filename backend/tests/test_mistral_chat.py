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

from app.services.mistral_chat import query_mistral


class TestMistralChat:
    """Test cases for the Mistral chat service"""

    @patch('app.services.mistral_chat.requests.post')
    def test_query_mistral_success(self, mock_post):
        """Test successful query to Mistral API"""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "Hello! How can I help you today?"
        }
        mock_post.return_value = mock_response
        
        # Test the function
        result = query_mistral("Hello")
        
        # Assertions
        assert result == "Hello! How can I help you today?"
        mock_post.assert_called_once_with(
            "http://host.docker.internal:11434/api/generate",
            json={
                "model": "mistral",
                "prompt": "Hello",
                "stream": False
            },
            timeout=30
        )

    @patch('app.services.mistral_chat.requests.post')
    def test_query_mistral_with_whitespace_response(self, mock_post):
        """Test that response whitespace is properly stripped"""
        # Mock response with whitespace
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "   Hello! How can I help you today?   \n\n"
        }
        mock_post.return_value = mock_response
        
        result = query_mistral("Hello")
        
        assert result == "Hello! How can I help you today?"

    @patch('app.services.mistral_chat.requests.post')
    def test_query_mistral_empty_response(self, mock_post):
        """Test handling of empty response"""
        # Mock empty response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": ""
        }
        mock_post.return_value = mock_response
        
        result = query_mistral("Hello")
        
        assert result == ""

    @patch('app.services.mistral_chat.requests.post')
    def test_query_mistral_missing_response_key(self, mock_post):
        """Test handling when response key is missing"""
        # Mock response without "response" key
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": "Hello! How can I help you today?"
        }
        mock_post.return_value = mock_response
        
        result = query_mistral("Hello")
        
        assert result == ""

    @patch('app.services.mistral_chat.requests.post')
    def test_query_mistral_connection_error(self, mock_post):
        """Test handling of connection errors"""
        # Mock connection error
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection failed")
        
        result = query_mistral("Hello")
        
        assert result == "Error: Unable to connect to AI service. Please try again later."

    @patch('app.services.mistral_chat.requests.post')
    def test_query_mistral_timeout_error(self, mock_post):
        """Test handling of timeout errors"""
        # Mock timeout error
        mock_post.side_effect = requests.exceptions.Timeout("Request timed out")
        
        result = query_mistral("Hello")
        
        assert result == "Error: Request timed out. Please try again."

    @patch('app.services.mistral_chat.requests.post')
    def test_query_mistral_http_error(self, mock_post):
        """Test handling of HTTP errors"""
        # Mock HTTP error
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error")
        mock_post.return_value = mock_response
        
        result = query_mistral("Hello")
        
        assert result == "Error: Failed to process your request. Please try again."

    @patch('app.services.mistral_chat.requests.post')
    def test_query_mistral_json_decode_error(self, mock_post):
        """Test handling of JSON decode errors"""
        # Mock response with invalid JSON
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "doc", 0)
        mock_post.return_value = mock_response
        
        result = query_mistral("Hello")
        
        assert result == "Error: An unexpected error occurred. Please try again."

    @patch('app.services.mistral_chat.requests.post')
    def test_query_mistral_unexpected_error(self, mock_post):
        """Test handling of unexpected errors"""
        # Mock unexpected error
        mock_post.side_effect = Exception("Unexpected error occurred")
        
        result = query_mistral("Hello")
        
        assert result == "Error: An unexpected error occurred. Please try again."

    @patch('app.services.mistral_chat.requests.post')
    def test_query_mistral_prompt_handling(self, mock_post):
        """Test that prompts are passed through correctly"""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "Response for query"
        }
        mock_post.return_value = mock_response
        
        query_mistral("Show me my transactions")
        
        # Check that the prompt was passed through correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[1]['json']['prompt'] == "Show me my transactions"

    @patch('app.services.mistral_chat.requests.post')
    def test_query_mistral_request_parameters(self, mock_post):
        """Test that all request parameters are set correctly"""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "Test response"
        }
        mock_post.return_value = mock_response
        
        query_mistral("Hello")
        
        # Check all request parameters
        mock_post.assert_called_once_with(
            "http://host.docker.internal:11434/api/generate",
            json={
                "model": "mistral",
                "prompt": "Hello",
                "stream": False
            },
            timeout=30
        )

    @patch('app.services.mistral_chat.requests.post')
    def test_query_mistral_long_message(self, mock_post):
        """Test handling of long messages"""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "I understand your long message"
        }
        mock_post.return_value = mock_response
        
        # Create a long message
        long_message = "This is a very long message. " * 100
        
        result = query_mistral(long_message)
        
        assert result == "I understand your long message"
        
        # Check that the long message was included in the prompt
        call_args = mock_post.call_args
        assert call_args[1]['json']['prompt'] == long_message

    @patch('app.services.mistral_chat.requests.post')
    def test_query_mistral_special_characters(self, mock_post):
        """Test handling of special characters in messages"""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "Handled special characters"
        }
        mock_post.return_value = mock_response
        
        # Test with special characters
        special_message = "Hello! @#$%^&*()_+-=[]{}|;':\",./<>?"
        
        result = query_mistral(special_message)
        
        assert result == "Handled special characters"
        
        # Check that special characters were preserved
        call_args = mock_post.call_args
        assert call_args[1]['json']['prompt'] == special_message 