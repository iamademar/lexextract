import pytest
import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.routers.chat import handle_special_queries


class TestSpecialQueryHandler:
    """Test cases for the handle_special_queries function"""

    def test_list_tables_queries(self):
        """Test various forms of list tables queries"""
        test_cases = [
            "list all tables",
            "list tables",
            "show all tables",
            "show tables",
            "what tables are there",
            "what tables exist"
        ]
        
        for query in test_cases:
            result = handle_special_queries(query)
            assert result is not None, f"Query '{query}' should return a special query"
            assert "SELECT tablename FROM pg_tables" in result
            assert "schemaname = 'public'" in result
            assert "ORDER BY tablename" in result

    def test_database_schema_queries(self):
        """Test various forms of database schema queries"""
        test_cases = [
            "show database schema",
            "database schema",
            "show table schema",
            "table schema",
            "describe tables"
        ]
        
        for query in test_cases:
            result = handle_special_queries(query)
            assert result is not None, f"Query '{query}' should return a special query"
            assert "information_schema.columns" in result
            assert "pg_tables" in result
            assert "tablename" in result
            assert "column_name" in result
            assert "data_type" in result

    def test_client_statement_queries(self):
        """Test client-specific statement queries"""
        test_cases = [
            "find statements from Test Client",
            "statements from Test Client",
            "show statements from Test Client",
            "get statements from Test Client"
        ]
        
        for query in test_cases:
            result = handle_special_queries(query)
            assert result is not None, f"Query '{query}' should return a special query"
            assert "SELECT s.id, s.file_path, s.uploaded_at, c.name" in result
            assert "FROM statements s" in result
            assert "JOIN clients c ON s.client_id = c.id" in result
            assert "WHERE c.name ILIKE '%Test Client%'" in result
            assert "ORDER BY s.uploaded_at DESC" in result

    def test_client_transaction_queries(self):
        """Test client-specific transaction queries"""
        test_cases = [
            "find transactions from Test Client",
            "transactions from Test Client",
            "show transactions from Test Client",
            "get transactions from Test Client"
        ]
        
        for query in test_cases:
            result = handle_special_queries(query)
            assert result is not None, f"Query '{query}' should return a special query"
            assert "SELECT t.id, t.date, t.payee, t.amount, t.balance, c.name" in result
            assert "FROM transactions t" in result
            assert "JOIN statements s ON t.statement_id = s.id" in result
            assert "JOIN clients c ON s.client_id = c.id" in result
            assert "WHERE c.name ILIKE '%Test Client%'" in result
            assert "ORDER BY t.date DESC" in result

    def test_general_client_statement_queries(self):
        """Test general client statement queries without specific client name"""
        test_cases = [
            "show client statements",
            "list client statements",
            "find client statements",
            "get client statements"
        ]
        
        for query in test_cases:
            result = handle_special_queries(query)
            assert result is not None, f"Query '{query}' should return a special query"
            assert "SELECT s.id, s.file_path, s.uploaded_at, c.name" in result
            assert "FROM statements s" in result
            assert "JOIN clients c ON s.client_id = c.id" in result
            assert "ORDER BY s.uploaded_at DESC" in result
            # Should not have WHERE clause for general queries
            assert "WHERE" not in result

    def test_case_insensitive_matching(self):
        """Test that queries are case-insensitive"""
        test_cases = [
            ("LIST ALL TABLES", "pg_tables"),
            ("List All Tables", "pg_tables"),
            ("list all tables", "pg_tables"),
            ("SHOW DATABASE SCHEMA", "information_schema"),
            ("Show Database Schema", "information_schema"),
            ("show database schema", "information_schema"),
            ("FIND STATEMENTS FROM TEST CLIENT", "Test Client"),
            ("Find Statements From Test Client", "Test Client"),
            ("find statements from test client", "Test Client")
        ]
        
        for query, expected_content in test_cases:
            result = handle_special_queries(query)
            assert result is not None, f"Query '{query}' should return a special query"
            assert expected_content in result or expected_content.lower() in result.lower()

    def test_non_special_queries_return_none(self):
        """Test that non-special queries return None"""
        test_cases = [
            "hello world",
            "how are you",
            "what is the weather",
            "calculate something",
            "explain machine learning",
            "random text",
            "show me something else",
            "find my keys",
            "list my groceries",
            "get help",
            "client information",  # Too vague
            "statement data",      # Too vague
            "show results"         # Too vague
        ]
        
        for query in test_cases:
            result = handle_special_queries(query)
            assert result is None, f"Query '{query}' should return None"

    def test_partial_matches_dont_trigger(self):
        """Test that partial matches don't trigger special queries"""
        test_cases = [
            "tablet computers",  # Contains 'table' but not 'tables'
            "client side code",  # Contains 'client' but not the right context
            "statement of purpose",  # Contains 'statement' but not the right context
            "show and tell",     # Contains 'show' but not database related
            "find my way",       # Contains 'find' but not database related
        ]
        
        for query in test_cases:
            result = handle_special_queries(query)
            # These might still return results due to keyword matching
            # but they shouldn't trigger the specific special query patterns
            if result is not None:
                # If it returns a result, it should be a general client query
                # not a specific pattern like list tables or schema
                assert "pg_tables" not in result
                assert "information_schema" not in result or "from test client" not in query.lower()

    def test_whitespace_handling(self):
        """Test that queries with extra whitespace are handled correctly"""
        test_cases = [
            "  list all tables  ",
            "\tshow database schema\t",
            "  find statements from Test Client  ",
            "list    all    tables",
            "show  database  schema"
        ]
        
        for query in test_cases:
            result = handle_special_queries(query)
            assert result is not None, f"Query '{query}' should return a special query"
            # Should work the same as trimmed version
            trimmed_result = handle_special_queries(query.strip())
            assert result == trimmed_result

    def test_sql_injection_protection(self):
        """Test that special queries are protected against SQL injection"""
        test_cases = [
            "list all tables; DROP TABLE clients;",
            "show database schema' OR '1'='1",
            "find statements from Test Client'; DELETE FROM statements; --"
        ]
        
        for query in test_cases:
            result = handle_special_queries(query)
            if result is not None:
                # The result should be a predetermined safe query
                # and not contain the injection attempt
                assert "DROP" not in result.upper()
                assert "DELETE" not in result.upper()
                assert "INSERT" not in result.upper()
                assert "UPDATE" not in result.upper()
                
                # Should still match expected patterns
                if "list all tables" in query.lower():
                    assert "SELECT tablename FROM pg_tables" in result
                elif "show database schema" in query.lower():
                    assert "information_schema.columns" in result
                elif "find statements from" in query.lower():
                    assert "WHERE c.name ILIKE '%Test Client%'" in result

    def test_special_query_priorities(self):
        """Test that more specific queries take precedence over general ones"""
        # A query that could match multiple patterns should match the most specific one
        query = "find statements from Test Client"
        result = handle_special_queries(query)
        
        assert result is not None
        # Should match the client-specific pattern, not the general client pattern
        assert "WHERE c.name ILIKE '%Test Client%'" in result
        
        # Test that client-specific transaction queries work
        query = "find transactions from Test Client"
        result = handle_special_queries(query)
        
        assert result is not None
        assert "transactions t" in result
        assert "WHERE c.name ILIKE '%Test Client%'" in result

    def test_query_structure_validation(self):
        """Test that returned queries have proper SQL structure"""
        queries = [
            "list all tables",
            "show database schema",
            "find statements from Test Client",
            "find transactions from Test Client",
            "show client statements"
        ]
        
        for query in queries:
            result = handle_special_queries(query)
            assert result is not None
            
            # All queries should start with SELECT
            assert result.strip().upper().startswith("SELECT")
            
            # All queries should end with semicolon
            assert result.strip().endswith(";")
            
            # Should not contain common SQL injection patterns
            dangerous_patterns = ["--", "/*", "*/", "xp_", "sp_", "exec", "execute"]
            for pattern in dangerous_patterns:
                assert pattern not in result.lower()

    def test_empty_and_none_inputs(self):
        """Test handling of empty and None inputs"""
        test_cases = [
            "",
            "   ",
            "\t\t",
            "\n\n",
            None
        ]
        
        for query in test_cases:
            if query is None:
                # Should handle None gracefully
                try:
                    result = handle_special_queries(query)
                    assert result is None
                except (AttributeError, TypeError):
                    # Acceptable to raise an exception for None input
                    pass
            else:
                result = handle_special_queries(query)
                assert result is None, f"Empty query '{repr(query)}' should return None" 