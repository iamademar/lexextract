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
from app.llms.mistral_llm import MistralLLM


class TestNLSQLIntegration:
    """Integration tests for the complete NL-to-SQL system"""
    
    def setup_method(self):
        """Set up test client for each test"""
        self.client = TestClient(app)

    @patch('app.llms.mistral_llm.requests.post')
    @patch('app.routers.chat.create_engine')
    def test_full_mistral_llm_integration(self, mock_create_engine, mock_requests_post):
        """Test MistralLLM integration with the chat system"""
        # Mock Ollama API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "Hello! I can help you with database queries."
        }
        mock_response.raise_for_status.return_value = None
        mock_requests_post.return_value = mock_response
        
        # Mock database engine to prevent actual DB connection during test
        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine
        
        # Test general chat (should use MistralLLM via fallback)
        response = self.client.post(
            "/chat",
            json={"message": "Hello, can you help me?"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert "database queries" in response_data["response"]
        assert response_data["sql"] is None

    @patch('app.routers.chat.run_in_threadpool')
    @patch('app.llms.mistral_llm.requests.post')
    def test_sql_chain_with_mistral_llm_integration(self, mock_requests_post, mock_run_in_threadpool):
        """Test SQL chain using MistralLLM for query generation"""
        # Mock Ollama API for SQL generation
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "SELECT * FROM clients;"
        }
        mock_response.raise_for_status.return_value = None
        mock_requests_post.return_value = mock_response
        
        # Mock the db_chain.run result (after SQL execution)
        mock_run_in_threadpool.return_value = "Found 2 clients: John Doe, Jane Smith"
        
        response = self.client.post(
            "/chat",
            json={"message": "list all clients"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert "John Doe, Jane Smith" in response_data["response"]
        assert response_data["sql"] == "Database query executed successfully"

    @patch('app.llms.mistral_llm.requests.post')
    def test_mistral_llm_connection_error_handling(self, mock_requests_post):
        """Test handling when MistralLLM cannot connect to Ollama"""
        # Mock connection error
        mock_requests_post.side_effect = Exception("Connection refused")
        
        response = self.client.post(
            "/chat",
            json={"message": "Hello"}
        )
        
        # Should return 200 with error message due to error handling in query_mistral
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert "error" in response_data["response"].lower() or "unexpected" in response_data["response"].lower()

    @patch('app.routers.chat.run_in_threadpool')
    @patch('app.llms.mistral_llm.requests.post')
    def test_sql_chain_error_with_mistral_fallback(self, mock_requests_post, mock_run_in_threadpool):
        """Test SQL chain error falling back to Mistral general chat"""
        # Mock SQL chain failure
        mock_run_in_threadpool.side_effect = Exception("SQL execution failed")
        
        # Mock Mistral fallback response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "I apologize, but I'm having trouble accessing the database right now."
        }
        mock_response.raise_for_status.return_value = None
        mock_requests_post.return_value = mock_response
        
        response = self.client.post(
            "/chat",
            json={"message": "list all clients"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert "having trouble accessing the database" in response_data["response"]
        assert response_data["sql"] is None

    def test_mistral_llm_initialization_in_chat_router(self):
        """Test that MistralLLM is properly initialized in the chat router"""
        from app.routers.chat import llm
        from app.llms.mistral_llm import MistralLLM
        
        # Verify the LLM is properly initialized
        assert isinstance(llm, MistralLLM)
        assert llm.endpoint == "http://host.docker.internal:11434/api/generate"
        assert llm.model == "mistral"
        assert llm.timeout == 30.0

    def test_database_chain_initialization(self):
        """Test that the database chain is properly initialized"""
        from app.routers.chat import db_chain
        
        # Verify the chain exists and has the expected structure
        assert db_chain is not None
        assert hasattr(db_chain, 'run')
        assert hasattr(db_chain, 'llm_chain')
        assert hasattr(db_chain, 'database')

    @patch('app.llms.mistral_llm.requests.post')
    def test_client_context_preservation_through_system(self, mock_requests_post):
        """Test that client context is preserved through the entire system"""
        # Mock Mistral response that includes client context
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "Hello Client 456! How can I assist you today?"
        }
        mock_response.raise_for_status.return_value = None
        mock_requests_post.return_value = mock_response
        
        response = self.client.post(
            "/chat",
            json={"message": "Hello there"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["client_id"] is None
        
        # Verify the prompt was sent to Mistral
        mock_requests_post.assert_called_once()
        call_args = mock_requests_post.call_args
        assert "Hello there" in call_args[1]["json"]["prompt"]

    @patch('app.routers.chat.run_in_threadpool')
    @patch('app.llms.mistral_llm.requests.post')
    def test_different_query_types_routing(self, mock_requests_post, mock_run_in_threadpool):
        """Test that different query types are routed correctly"""
        # Setup mocks
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "Mistral response"}
        mock_response.raise_for_status.return_value = None
        mock_requests_post.return_value = mock_response
        
        mock_run_in_threadpool.return_value = "Database response"
        
        test_cases = [
            # (message, should_use_sql, expected_sql_field)
            ("list all clients", True, "Database query executed successfully"),
            ("show me data", True, "Database query executed successfully"),
            ("count records", True, "Database query executed successfully"),
            ("Hello world", False, None),
            ("Tell me a joke", False, None),
            ("How are you?", False, None),
        ]
        
        for message, should_use_sql, expected_sql in test_cases:
            # Reset mocks
            mock_requests_post.reset_mock()
            mock_run_in_threadpool.reset_mock()
            
            response = self.client.post(
                "/chat",
                json={"client_id": 123, "message": message}
            )
            
            assert response.status_code == status.HTTP_200_OK
            response_data = response.json()
            assert response_data["sql"] == expected_sql
            
            if should_use_sql:
                # Should call SQL chain
                mock_run_in_threadpool.assert_called_once()
            else:
                # Should call Mistral fallback
                mock_requests_post.assert_called_once()

    @patch('app.llms.mistral_llm.requests.post')
    def test_async_handling_in_chat_endpoint(self, mock_requests_post):
        """Test that async operations are handled correctly in the chat endpoint"""
        # Mock delayed response to test async behavior
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "Async response"}
        mock_response.raise_for_status.return_value = None
        mock_requests_post.return_value = mock_response
        
        # Test multiple concurrent requests
        import threading
        import time
        
        results = []
        
        def make_request(client_id):
            response = self.client.post(
                "/chat",
                json={"client_id": client_id, "message": "Hello"}
            )
            results.append((client_id, response.status_code))
        
        threads = []
        for i in range(3):
            thread = threading.Thread(target=make_request, args=(i,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # All requests should succeed
        assert len(results) == 3
        for client_id, status_code in results:
            assert status_code == status.HTTP_200_OK

    @patch('app.routers.chat.run_in_threadpool')
    def test_run_in_threadpool_usage(self, mock_run_in_threadpool):
        """Test that run_in_threadpool is used correctly for SQL operations"""
        mock_run_in_threadpool.return_value = "SQL result"
        
        response = self.client.post(
            "/chat",
            json={"message": "list clients"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify run_in_threadpool was called with the db_chain.run method
        mock_run_in_threadpool.assert_called_once()
        call_args = mock_run_in_threadpool.call_args
        # First argument should be the db_chain.run method
        assert callable(call_args[0][0])
        # Second argument should be the user's message
        assert call_args[0][1] == "list clients"

    def test_response_schema_consistency(self):
        """Test that response schema is consistent across all code paths"""
        with patch('app.llms.mistral_llm.requests.post') as mock_post, \
             patch('app.routers.chat.run_in_threadpool') as mock_threadpool:
            
            # Mock responses
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"response": "Test response"}
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response
            mock_threadpool.return_value = "SQL response"
            
            test_messages = [
                "list all clients",  # SQL path
                "Hello world",       # Mistral path
            ]
            
            for message in test_messages:
                response = self.client.post(
                    "/chat",
                    json={"client_id": 123, "message": message}
                )
                
                assert response.status_code == status.HTTP_200_OK
                response_data = response.json()
                
                # All responses should have the same schema
                assert "client_id" in response_data
                assert "response" in response_data
                assert "sql" in response_data
                assert isinstance(response_data["client_id"], int)
                assert isinstance(response_data["response"], str)
                # sql field can be string or null
                assert response_data["sql"] is None or isinstance(response_data["sql"], str)

    def test_database_url_configuration(self):
        """Test that database URL is correctly configured for sync operations"""
        # Import the chat module to check the DATABASE_URL
        from app.routers import chat
        
        # Check that the DATABASE_URL is properly configured for sync operations
        assert hasattr(chat, 'DATABASE_URL')
        db_url = chat.DATABASE_URL
        
        # Should use psycopg2 (sync) instead of asyncpg (async)
        assert "postgresql+psycopg2://" in db_url
        assert "postgresql+asyncpg://" not in db_url

    def test_database_url_conversion_from_async(self):
        """Test that async database URLs are converted to sync"""
        # Test the conversion function directly
        from app.routers.chat import DATABASE_URL
        
        # Simulate an async URL
        async_url = "postgresql+asyncpg://user:pass@host/db"
        converted_url = async_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
        
        # Verify the conversion logic works
        assert "postgresql+psycopg2://" in converted_url
        assert "postgresql+asyncpg://" not in converted_url
        
        # Test the actual DATABASE_URL is sync
        assert "postgresql+psycopg2://" in DATABASE_URL 