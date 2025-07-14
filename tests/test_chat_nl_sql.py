import pytest
import pytest_asyncio
import os
import sys
import json
import re
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from pathlib import Path
from fastapi.testclient import TestClient
from fastapi import status

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.main import app
from app.routers.chat import ChatRequest, ChatResponse


class TestChatNLToSQL:
    """Test cases for the enhanced /chat endpoint with NL-to-SQL functionality"""
    
    def setup_method(self):
        """Set up test client for each test"""
        self.client = TestClient(app)

    @patch('app.routers.chat.run_in_threadpool')
    @patch('app.routers.chat.db_chain')
    def test_database_query_intent_detection_list(self, mock_db_chain, mock_run_in_threadpool):
        """Test that 'list' queries are detected as database intents"""
        # Mock SQL chain response
        mock_run_in_threadpool.return_value = "Found 3 clients: Alice, Bob, Charlie"
        
        response = self.client.post(
            "/chat",
            json={"message": "list all clients"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["client_id"] is None
        assert "Alice, Bob, Charlie" in response_data["response"]
        assert response_data["sql"] == "Database query executed successfully"
        
        # Verify SQL chain was called
        mock_run_in_threadpool.assert_called_once()

    @patch('app.routers.chat.run_in_threadpool')
    @patch('app.routers.chat.db_chain')
    def test_database_query_intent_detection_show(self, mock_db_chain, mock_run_in_threadpool):
        """Test that 'show' queries are detected as database intents"""
        mock_run_in_threadpool.return_value = "Showing client details for ID 1"
        
        response = self.client.post(
            "/chat",
            json={"message": "show me client details"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["sql"] == "Database query executed successfully"

    @patch('app.routers.chat.run_in_threadpool')
    @patch('app.routers.chat.db_chain')
    def test_database_query_intent_detection_count(self, mock_db_chain, mock_run_in_threadpool):
        """Test that 'count' queries are detected as database intents"""
        mock_run_in_threadpool.return_value = "Total clients: 42"
        
        response = self.client.post(
            "/chat",
            json={"message": "count all clients"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["sql"] == "Database query executed successfully"

    @patch('app.routers.chat.query_mistral')
    def test_general_chat_fallback(self, mock_query_mistral):
        """Test that general chat queries go to Mistral fallback"""
        mock_query_mistral.return_value = "Hello! How can I help you today?"
        
        response = self.client.post(
            "/chat",
            json={"message": "Hello, how are you?"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["client_id"] is None
        assert response_data["response"] == "Hello! How can I help you today?"
        assert response_data["sql"] is None
        
        # Verify Mistral was called with correct parameters
        mock_query_mistral.assert_called_once_with("Hello, how are you?")

    @patch('app.routers.chat.query_mistral')
    @patch('app.routers.chat.run_in_threadpool')
    @patch('app.routers.chat.db_chain')
    def test_sql_chain_error_fallback(self, mock_db_chain, mock_run_in_threadpool, mock_query_mistral):
        """Test that SQL chain errors fall back to Mistral"""
        # Mock SQL chain to raise an exception
        mock_run_in_threadpool.side_effect = Exception("SQL chain error")
        mock_query_mistral.return_value = "I'm sorry, I had trouble with that query."
        
        response = self.client.post(
            "/chat",
            json={"message": "list all clients"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["client_id"] is None
        assert response_data["response"] == "I'm sorry, I had trouble with that query."
        assert response_data["sql"] is None
        
        # Verify both were called
        mock_run_in_threadpool.assert_called_once()
        mock_query_mistral.assert_called_once_with("list all clients")

    @patch('app.routers.chat.run_in_threadpool')
    @patch('app.routers.chat.db_chain')
    def test_database_query_response_format(self, mock_db_chain, mock_run_in_threadpool):
        """Test the response format for database queries"""
        mock_run_in_threadpool.return_value = "Client data: John Doe, jane@example.com"
        
        response = self.client.post(
            "/chat",
            json={"message": "show all clients"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        
        # Check response structure
        assert "client_id" in response_data
        assert "response" in response_data
        assert "sql" in response_data
        
        # Check values
        assert response_data["client_id"] is None
        assert response_data["response"] == "Client data: John Doe, jane@example.com"
        assert response_data["sql"] == "Database query executed successfully"

    @patch('app.routers.chat.query_mistral')
    def test_general_chat_response_format(self, mock_query_mistral):
        """Test the response format for general chat"""
        mock_query_mistral.return_value = "This is a general AI response"
        
        response = self.client.post(
            "/chat",
            json={"message": "Hello there"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        
        # Check response structure
        assert "client_id" in response_data
        assert "response" in response_data
        assert "sql" in response_data
        
        # Check values
        assert response_data["client_id"] is None
        assert response_data["response"] == "This is a general AI response"
        assert response_data["sql"] is None

    def test_request_validation_still_works(self):
        """Test that request validation still works with new functionality"""
        # Test missing message
        response = self.client.post(
            "/chat",
            json={}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
        # Test invalid data types
        response = self.client.post(
            "/chat",
            json={"message": 123}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_intent_detection_regex_patterns(self):
        """Test the regex patterns used for intent detection"""
        # Test database intent patterns
        db_patterns = [
            "list all clients",
            "show me data", 
            "what clients exist?",
            "give me the results",
            "find all records",
            "search for transactions",
            "how many clients?",
            "count all items",
            "get the data",
            "fetch all records",
            "display the results"
        ]
        
        for pattern in db_patterns:
            # This should match the regex in the chat router
            match = re.match(r"^(list|show|what|give|find|search|how many|count|get|fetch|display)\b.*", pattern, re.I)
            assert match is not None, f"Pattern '{pattern}' should match database intent"
        
        # Test non-database patterns
        non_db_patterns = [
            "hello there",
            "help me code",
            "tell me a joke",
            "calculate something",
            "explain machine learning"
        ]
        
        for pattern in non_db_patterns:
            match = re.match(r"^(list|show|what|give|find|search|how many|count|get|fetch|display)\b.*", pattern, re.I)
            assert match is None, f"Pattern '{pattern}' should NOT match database intent" 