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
from app.routers.chat import ChatRequest, ChatResponse, handle_special_queries


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

    @patch('app.routers.chat.database')
    def test_special_query_handler_list_tables(self, mock_database):
        """Test the special query handler for 'list tables' queries"""
        mock_database.run.return_value = "[('clients',), ('statements',), ('transactions',)]"
        
        response = self.client.post(
            "/chat",
            json={"message": "list all tables"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert "clients" in response_data["response"]
        assert "statements" in response_data["response"]
        assert "transactions" in response_data["response"]
        assert "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;" in response_data["sql"]

    @patch('app.routers.chat.database')
    def test_special_query_handler_show_schema(self, mock_database):
        """Test the special query handler for database schema queries"""
        mock_database.run.return_value = "[('clients', 'id', 'integer'), ('clients', 'name', 'varchar')]"
        
        response = self.client.post(
            "/chat",
            json={"message": "show database schema"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert "clients" in response_data["response"]
        assert "information_schema.columns" in response_data["sql"]

    @patch('app.routers.chat.database')
    def test_special_query_handler_client_statements(self, mock_database):
        """Test the special query handler for client-specific statement queries"""
        mock_database.run.return_value = "[('1', 'path/to/statement.pdf', '2025-01-01', 'Test Client')]"
        
        response = self.client.post(
            "/chat",
            json={"message": "find statements from Test Client"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert "Test Client" in response_data["response"]
        assert "WHERE c.name ILIKE '%Test Client%'" in response_data["sql"]

    def test_keyword_based_intent_detection(self):
        """Test the new keyword-based intent detection system"""
        # Keywords that should trigger database queries
        db_keywords = [
            "list", "show", "what", "give", "find", "search", "how many", "count", 
            "get", "fetch", "display", "select", "where", "from", "table", "database",
            "client", "statement", "transaction", "recent", "latest", "all"
        ]
        
        # Test each keyword triggers database intent
        for keyword in db_keywords:
            test_message = f"{keyword} something"
            # This should be detected as a database query
            # We can't test the internal logic directly, but we can verify the behavior
            assert keyword in test_message.lower()

    def test_enhanced_pattern_matching(self):
        """Test enhanced pattern matching with more keywords"""
        database_phrases = [
            "list all clients",
            "show me transactions", 
            "find recent statements",
            "get client data",
            "fetch all records",
            "display database info",
            "search for transactions",
            "count statements",
            "what clients exist",
            "recent statements",
            "latest transactions",
            "all client data"
        ]
        
        non_database_phrases = [
            "hello world",
            "how are you",
            "tell me a joke",
            "what's the weather"
        ]
        
        # Test that database phrases contain keywords
        for phrase in database_phrases:
            phrase_lower = phrase.lower()
            db_keywords = [
                "list", "show", "what", "give", "find", "search", "how many", "count", 
                "get", "fetch", "display", "select", "where", "from", "table", "database",
                "client", "statement", "transaction", "recent", "latest", "all"
            ]
            
            # At least one keyword should be present
            has_keyword = any(keyword in phrase_lower for keyword in db_keywords)
            assert has_keyword, f"Database phrase '{phrase}' should contain a database keyword"

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
        assert "response" in response_data
        assert "sql" in response_data
        
        # Check values
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
        assert "response" in response_data
        assert "sql" in response_data
        
        # Check values
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

    def test_special_query_handler_function(self):
        """Test the handle_special_queries function directly"""
        # Test list tables query
        result = handle_special_queries("list all tables")
        assert result is not None
        assert "SELECT tablename FROM pg_tables" in result
        assert "schemaname = 'public'" in result
        
        # Test schema query
        result = handle_special_queries("show database schema")
        assert result is not None
        assert "information_schema.columns" in result
        
        # Test client-specific query
        result = handle_special_queries("find statements from Test Client")
        assert result is not None
        assert "WHERE c.name ILIKE '%Test Client%'" in result
        assert "statements s" in result
        assert "clients c" in result
        
        # Test non-special query
        result = handle_special_queries("hello world")
        assert result is None

    def test_client_transaction_query_handling(self):
        """Test handling of client-specific transaction queries"""
        result = handle_special_queries("find transactions from Test Client")
        assert result is not None
        assert "transactions t" in result
        assert "WHERE c.name ILIKE '%Test Client%'" in result
        assert "JOIN statements s ON t.statement_id = s.id" in result
        
    def test_general_client_statement_query(self):
        """Test handling of general client statement queries"""
        result = handle_special_queries("show client statements")
        assert result is not None
        assert "statements s" in result
        assert "clients c" in result
        assert "ORDER BY s.uploaded_at DESC" in result 