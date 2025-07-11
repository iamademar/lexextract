import pytest
import pytest_asyncio
import os
import sys
import io
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.main import app
from app.db import get_db, Base
from app.models import Statement, Client, Transaction

# Test database configuration
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Create test engine and session
test_engine = create_async_engine(TEST_DATABASE_URL, echo=True)
TestAsyncSessionLocal = sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)

async def override_get_db():
    """Override database dependency for tests"""
    async with TestAsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

# Override the dependency
app.dependency_overrides[get_db] = override_get_db

# Create test client
client = TestClient(app)

@pytest_asyncio.fixture(scope="function")
async def setup_database():
    """Setup test database with a test client"""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create a test client
    async with TestAsyncSessionLocal() as session:
        test_client = Client(
            name="Test Client",
            contact_name="Test Contact", 
            contact_email="test@example.com"
        )
        session.add(test_client)
        await session.commit()
        yield test_client.id
    
    # Cleanup
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

def create_sample_pdf():
    """Create a sample PDF with bank statement-like content"""
    # Simple PDF structure for testing
    pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj

2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj

3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj

4 0 obj
<<
/Length 144
>>
stream
BT
/F1 12 Tf
72 720 Td
(Account Transactions) Tj
0 -24 Td
(10/02 POS PURCHASE 4.23 697.73) Tj
0 -12 Td
(10/03 PREAUTHORIZED CREDIT 65.73 763.01) Tj
ET
endstream
endobj

xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000207 00000 n 
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
401
%%EOF"""
    return pdf_content

@pytest.mark.asyncio
async def test_upload_statement_with_parser_integration(setup_database):
    """Test that the upload endpoint correctly integrates OCR and parser"""
    client_id = setup_database
    
    # Create sample PDF
    pdf_content = create_sample_pdf()
    
    # Upload the file
    files = {
        "file": ("test_statement.pdf", io.BytesIO(pdf_content), "application/pdf")
    }
    
    response = client.post(f"/upload/statement?client_id={client_id}", files=files)
    
    # Check response
    assert response.status_code == 201
    response_data = response.json()
    
    # Verify response structure includes new fields
    assert "statement_id" in response_data
    assert "pages_processed" in response_data
    assert "transactions_found" in response_data
    assert "transactions_saved" in response_data
    assert "ocr_preview" in response_data
    
    statement_id = response_data["statement_id"]
    
    # Verify statement was created in database
    async with TestAsyncSessionLocal() as session:
        # Check Statement record
        statement_result = await session.execute(select(Statement).where(Statement.id == statement_id))
        statement = statement_result.scalar_one_or_none()
        
        assert statement is not None
        assert statement.client_id == client_id
        assert statement.ocr_text is not None
        
        # Check Transaction records
        transactions_result = await session.execute(
            select(Transaction).where(Transaction.statement_id == statement_id)
        )
        transactions = transactions_result.scalars().all()
        
        # Should have created some transactions
        print(f"Found {len(transactions)} transactions in database")
        print(f"Response says found: {response_data['transactions_found']}, saved: {response_data['transactions_saved']}")
        
        # Verify transaction data structure
        for transaction in transactions:
            assert transaction.statement_id == statement_id
            assert transaction.date is not None
            assert transaction.payee is not None
            assert transaction.amount is not None
            assert transaction.type in ["Credit", "Debit"]
            assert transaction.currency is not None

@pytest.mark.asyncio
async def test_upload_with_parsing_failure_fallback(setup_database):
    """Test that upload still works even if parsing fails"""
    client_id = setup_database
    
    # Create a minimal PDF that should pass OCR but might not parse well
    minimal_pdf = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj  
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj
xref
0 4
0000000000 65535 f
0000000015 00000 n
0000000060 00000 n
0000000111 00000 n
trailer<</Size 4/Root 1 0 R>>
startxref
180
%%EOF"""
    
    files = {
        "file": ("minimal.pdf", io.BytesIO(minimal_pdf), "application/pdf")
    }
    
    response = client.post(f"/upload/statement?client_id={client_id}", files=files)
    
    # Should still succeed even if parsing fails
    assert response.status_code == 201
    response_data = response.json()
    
    # Should have statement_id and other fields
    assert "statement_id" in response_data
    assert "pages_processed" in response_data
    assert "transactions_found" in response_data
    assert "transactions_saved" in response_data
    
    # Verify statement was still created
    statement_id = response_data["statement_id"]
    async with TestAsyncSessionLocal() as session:
        statement_result = await session.execute(select(Statement).where(Statement.id == statement_id))
        statement = statement_result.scalar_one_or_none()
        assert statement is not None

if __name__ == "__main__":
    pytest.main([__file__]) 