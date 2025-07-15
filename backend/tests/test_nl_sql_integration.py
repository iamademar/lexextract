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
from app.routers.chat import create_enhanced_prompt, handle_special_queries


class TestNLSQLIntegration:
    """Integration tests for the complete NL-to-SQL system"""
    
    def setup_method(self):
        """Set up test client for each test"""
        self.client = TestClient(app)

    @patch('app.llms.mistral_llm.requests.post')
    @patch('app.routers.chat.run_in_threadpool')
    def test_full_mistral_llm_integration(self, mock_run_in_threadpool, mock_requests_post):
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
        mock_run_in_threadpool.return_value = mock_engine # Changed from mock_create_engine to mock_run_in_threadpool
        
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

    @patch('app.routers.chat.database')
    def test_special_query_handler_integration(self, mock_database):
        """Test integration of special query handler with the chat system"""
        mock_database.run.return_value = "[('clients',), ('statements',), ('transactions',)]"
        
        # Test that special queries bypass the normal SQL chain
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
        
        # Verify database.run was called with the special query
        mock_database.run.assert_called_once()

    @patch('app.routers.chat.database')
    def test_client_specific_queries_integration(self, mock_database):
        """Test integration of client-specific queries"""
        mock_database.run.return_value = "[('1', 'statement.pdf', '2025-01-01', 'Test Client')]"
        
        response = self.client.post(
            "/chat",
            json={"message": "find statements from Test Client"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert "Test Client" in response_data["response"]
        assert "WHERE c.name ILIKE '%Test Client%'" in response_data["sql"]

    def test_enhanced_prompt_creation(self):
        """Test the enhanced prompt creation system"""
        query = "show me all clients"
        enhanced_prompt = create_enhanced_prompt(query)
        
        # Should contain PostgreSQL-specific guidance
        assert "PostgreSQL SQL expert" in enhanced_prompt
        assert "tablename" in enhanced_prompt
        assert "schemaname = 'public'" in enhanced_prompt
        assert "ILIKE" in enhanced_prompt
        
        # Should contain database schema information
        assert "clients" in enhanced_prompt
        assert "statements" in enhanced_prompt
        assert "transactions" in enhanced_prompt
        
        # Should contain the actual query
        assert query in enhanced_prompt

    def test_keyword_based_pattern_matching_integration(self):
        """Test integration of keyword-based pattern matching"""
        # Test that the new keyword system works with the API
        test_cases = [
            ("recent statements", True),
            ("latest transactions", True),
            ("all client data", True),
            ("database information", True),
            ("hello world", False),
            ("how are you", False)
        ]
        
        for query, should_be_db in test_cases:
            # Mock the appropriate response based on expected behavior
            with patch('app.routers.chat.run_in_threadpool') as mock_run, \
                 patch('app.routers.chat.query_mistral') as mock_mistral:
                
                mock_run.return_value = "Database result"
                mock_mistral.return_value = "General chat response"
                
                response = self.client.post(
                    "/chat",
                    json={"message": query}
                )
                
                assert response.status_code == status.HTTP_200_OK
                response_data = response.json()
                
                if should_be_db:
                    # Should be processed as database query
                    assert response_data["sql"] is not None
                    mock_run.assert_called()
                else:
                    # Should fall back to general chat
                    assert response_data["sql"] is None
                    mock_mistral.assert_called()

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
            "response": "I had trouble with that database query. Can you try rephrasing it?"
        }
        mock_response.raise_for_status.return_value = None
        mock_requests_post.return_value = mock_response
        
        response = self.client.post(
            "/chat",
            json={"message": "list all clients"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert "trouble with that database query" in response_data["response"]
        assert response_data["sql"] is None

    @patch('app.routers.chat.database')
    @patch('app.llms.mistral_llm.requests.post')
    def test_special_query_error_fallback(self, mock_requests_post, mock_database):
        """Test special query error falling back to Mistral"""
        # Mock database error for special query
        mock_database.run.side_effect = Exception("Database connection failed")
        
        # Mock Mistral fallback response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "I couldn't access the database to list tables."
        }
        mock_response.raise_for_status.return_value = None
        mock_requests_post.return_value = mock_response
        
        response = self.client.post(
            "/chat",
            json={"message": "list all tables"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert "couldn't access the database" in response_data["response"]
        assert response_data["sql"] is None

    @patch('app.routers.chat.run_in_threadpool')
    @patch('app.llms.mistral_llm.requests.post')
    def test_enhanced_prompt_with_mistral_llm(self, mock_requests_post, mock_run_in_threadpool):
        """Test that enhanced prompts work with MistralLLM"""
        # Mock Ollama API response with SQL
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "SELECT COUNT(*) FROM clients;"
        }
        mock_response.raise_for_status.return_value = None
        mock_requests_post.return_value = mock_response
        
        # Mock SQL execution result
        mock_run_in_threadpool.return_value = "Total clients: 5"
        
        response = self.client.post(
            "/chat",
            json={"message": "how many clients are there"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert "Total clients: 5" in response_data["response"]
        assert response_data["sql"] == "Database query executed successfully"

    def test_multiple_query_types_in_sequence(self):
        """Test that different query types work correctly in sequence"""
        queries = [
            ("list all tables", "special"),
            ("how many clients", "normal_db"),
            ("hello world", "general"),
            ("show database schema", "special"),
            ("find statements from Test Client", "special")
        ]
        
        for query, query_type in queries:
            if query_type == "special":
                with patch('app.routers.chat.database') as mock_db:
                    mock_db.run.return_value = "Special query result"
                    
                    response = self.client.post("/chat", json={"message": query})
                    assert response.status_code == status.HTTP_200_OK
                    response_data = response.json()
                    assert response_data["sql"] is not None
                    
            elif query_type == "normal_db":
                with patch('app.routers.chat.run_in_threadpool') as mock_run:
                    mock_run.return_value = "Normal DB result"
                    
                    response = self.client.post("/chat", json={"message": query})
                    assert response.status_code == status.HTTP_200_OK
                    response_data = response.json()
                    assert response_data["sql"] == "Database query executed successfully"
                    
            elif query_type == "general":
                with patch('app.routers.chat.query_mistral') as mock_mistral:
                    mock_mistral.return_value = "General chat response"
                    
                    response = self.client.post("/chat", json={"message": query})
                    assert response.status_code == status.HTTP_200_OK
                    response_data = response.json()
                    assert response_data["sql"] is None

    def test_sql_injection_protection_integration(self):
        """Test SQL injection protection in the integrated system"""
        malicious_queries = [
            "list all tables; DROP TABLE clients;",
            "show database schema' OR '1'='1",
            "find statements from Test Client'; DELETE FROM statements; --"
        ]
        
        for query in malicious_queries:
            with patch('app.routers.chat.database') as mock_db:
                mock_db.run.return_value = "Safe query result"
                
                response = self.client.post("/chat", json={"message": query})
                assert response.status_code == status.HTTP_200_OK
                
                # Should still process the query but safely
                if mock_db.run.called:
                    called_query = mock_db.run.call_args[0][0]
                    # Should not contain dangerous SQL
                    assert "DROP" not in called_query.upper()
                    assert "DELETE" not in called_query.upper()

    def test_performance_with_large_queries(self):
        """Test system performance with large query messages"""
        # Create a very large query message
        large_query = "list all clients " + "with lots of additional text " * 100
        
        with patch('app.routers.chat.run_in_threadpool') as mock_run:
            mock_run.return_value = "Query result"
            
            response = self.client.post("/chat", json={"message": large_query})
            assert response.status_code == status.HTTP_200_OK
            response_data = response.json()
            assert response_data["sql"] is not None
            
            # Should still be processed as a database query
            mock_run.assert_called_once()

    def test_concurrent_requests_handling(self):
        """Test that the system can handle concurrent requests"""
        import threading
        import time
        
        results = []
        
        def make_request(query):
            with patch('app.routers.chat.database') as mock_db:
                mock_db.run.return_value = f"Result for {query}"
                
                response = self.client.post("/chat", json={"message": query})
                results.append(response.status_code)
        
        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=make_request, args=(f"list all tables {i}",))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All requests should have succeeded
        assert all(status == 200 for status in results)
        assert len(results) == 5 