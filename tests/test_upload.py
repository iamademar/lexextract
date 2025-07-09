import pytest
import pytest_asyncio
import os
import tempfile
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
import asyncio
import io

from app.main import app
from app.db import get_db, Base
from app.models import Statement, Client

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
    """Setup test database"""
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
    
    yield
    
    # Cleanup
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

def create_dummy_pdf():
    """Create a dummy PDF file for testing"""
    # Create a minimal PDF structure
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
>>
endobj

xref
0 4
0000000000 65535 f 
0000000009 00000 n 
0000000074 00000 n 
0000000120 00000 n 
trailer
<<
/Size 4
/Root 1 0 R
>>
startxref
179
%%EOF"""
    return pdf_content

@pytest.mark.asyncio
async def test_upload_statement_success(setup_database):
    """Test successful PDF upload"""
    # Create dummy PDF content
    pdf_content = create_dummy_pdf()
    
    # Create file-like object
    files = {
        "file": ("test_statement.pdf", io.BytesIO(pdf_content), "application/pdf")
    }
    
    response = client.post("/upload/statement?client_id=1", files=files)
    
    assert response.status_code == 201
    data = response.json()
    assert "statement_id" in data
    assert isinstance(data["statement_id"], int)
    assert data["statement_id"] > 0

@pytest.mark.asyncio
async def test_upload_statement_file_saved(setup_database):
    """Test that uploaded file is saved to disk"""
    # Create dummy PDF content
    pdf_content = create_dummy_pdf()
    
    # Create file-like object
    files = {
        "file": ("test_statement.pdf", io.BytesIO(pdf_content), "application/pdf")
    }
    
    response = client.post("/upload/statement?client_id=1", files=files)
    
    assert response.status_code == 201
    data = response.json()
    statement_id = data["statement_id"]
    
    # Verify database record was created
    async with TestAsyncSessionLocal() as session:
        stmt = await session.execute(select(Statement).where(Statement.id == statement_id))
        statement = stmt.scalar_one_or_none()
        assert statement is not None
        assert statement.file_path is not None
        assert statement.client_id == 1  # Verify client_id is set correctly
        
        # Verify file exists on disk
        assert os.path.exists(statement.file_path)
        
        # Verify file content matches
        with open(statement.file_path, "rb") as f:
            saved_content = f.read()
        assert saved_content == pdf_content
        
        # Cleanup - remove test file
        os.remove(statement.file_path)

def test_upload_statement_invalid_mime_type():
    """Test upload with invalid MIME type"""
    text_content = b"This is not a PDF file"
    
    files = {
        "file": ("test.txt", io.BytesIO(text_content), "text/plain")
    }
    
    response = client.post("/upload/statement?client_id=1", files=files)
    
    assert response.status_code == 400
    assert "Only PDF files are allowed" in response.json()["detail"]

def test_upload_statement_large_file():
    """Test upload with file larger than 10MB"""
    # Create a large file (11MB)
    large_content = b"a" * (11 * 1024 * 1024)
    
    files = {
        "file": ("large_file.pdf", io.BytesIO(large_content), "application/pdf")
    }
    
    response = client.post("/upload/statement?client_id=1", files=files)
    
    assert response.status_code == 400
    assert "File size must be ≤10 MB" in response.json()["detail"]

def test_upload_statement_no_file():
    """Test upload without providing a file"""
    response = client.post("/upload/statement?client_id=1")
    
    assert response.status_code == 422  # Validation error

@pytest.mark.asyncio
async def test_upload_creates_directory(setup_database):
    """Test that upload creates the uploads directory if it doesn't exist"""
    # Remove directory if it exists
    if os.path.exists("data/uploads"):
        import shutil
        shutil.rmtree("data/uploads")
    
    # Create dummy PDF content
    pdf_content = create_dummy_pdf()
    
    # Create file-like object
    files = {
        "file": ("test_statement.pdf", io.BytesIO(pdf_content), "application/pdf")
    }
    
    response = client.post("/upload/statement?client_id=1", files=files)
    
    assert response.status_code == 201
    assert os.path.exists("data/uploads")
    
    # Cleanup
    if os.path.exists("data/uploads"):
        import shutil
        shutil.rmtree("data/uploads")
def test_upload_statement_missing_client_id():
    """Test upload without providing client_id"""
    pdf_content = create_dummy_pdf()
    files = {
        "file": ("test_statement.pdf", io.BytesIO(pdf_content), "application/pdf")
    }
    
    response = client.post("/upload/statement", files=files)
    
    assert response.status_code == 422  # Validation error

@pytest.mark.asyncio
async def test_upload_statement_invalid_client_id(setup_database):
    """Test upload with non-existent client_id"""
    pdf_content = create_dummy_pdf()
    files = {
        "file": ("test_statement.pdf", io.BytesIO(pdf_content), "application/pdf")
    }
    
    response = client.post("/upload/statement?client_id=999", files=files)
    
    assert response.status_code == 404
    assert "Client with ID 999 not found" in response.json()["detail"]
