import pytest
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# Import models to ensure they're registered with Base
from app.models import Client, Statement, Transaction, Base


@pytest.fixture
async def async_engine():
    """Create an async engine for testing with PostgreSQL test database"""
    # Override DATABASE_URL for testing
    test_db_url = os.getenv("TEST_DATABASE_URL", "postgresql+asyncpg://postgres:password@localhost:5433/lexextract_test")
    os.environ["DATABASE_URL"] = test_db_url
    
    engine = create_async_engine(test_db_url, echo=True)
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Clean up - drop all tables and dispose engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_database_tables_created(async_engine):
    """Test that all three tables are created correctly"""
    async with async_engine.connect() as conn:
        # Check that clients table exists
        result = await conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name='clients'"))
        clients_table = result.fetchone()
        assert clients_table is not None, "clients table should exist"
        
        # Check that statements table exists  
        result = await conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name='statements'"))
        statements_table = result.fetchone()
        assert statements_table is not None, "statements table should exist"
        
        # Check that transactions table exists
        result = await conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name='transactions'"))
        transactions_table = result.fetchone()
        assert transactions_table is not None, "transactions table should exist"


@pytest.mark.asyncio
async def test_table_schemas(async_engine):
    """Test that tables have the expected columns"""
    async with async_engine.connect() as conn:
        # Check clients table schema
        result = await conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='clients'"))
        clients_columns = {row[0] for row in result.fetchall()}
        expected_clients_cols = {"id", "name", "contact_name", "contact_email", "created_at"}
        assert expected_clients_cols.issubset(clients_columns), f"Missing columns in clients table: {expected_clients_cols - clients_columns}"
        
        # Check statements table schema
        result = await conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='statements'"))
        statements_columns = {row[0] for row in result.fetchall()}
        expected_statements_cols = {"id", "client_id", "uploaded_at", "file_path"}
        assert expected_statements_cols.issubset(statements_columns), f"Missing columns in statements table: {expected_statements_cols - statements_columns}"
        
        # Check transactions table schema
        result = await conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='transactions'"))
        transactions_columns = {row[0] for row in result.fetchall()}
        expected_transactions_cols = {"id", "statement_id", "date", "payee", "amount", "type", "balance", "currency"}
        assert expected_transactions_cols.issubset(transactions_columns), f"Missing columns in transactions table: {expected_transactions_cols - transactions_columns}" 