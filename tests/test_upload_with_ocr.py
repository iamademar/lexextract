import pytest
import pytest_asyncio
import os
import tempfile
import sys
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
import io

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.main import app
from app.db import get_db, Base
from app.models import Statement, Client

# Test database configuration
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Create test engine and session
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)  # Disable echo for cleaner test output
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
    
    yield
    
    # Cleanup
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

def create_minimal_pdf():
    """Create a minimal valid PDF for basic testing"""
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


class TestUploadWithOCR:
    """Comprehensive tests for the upload endpoint with OCR processing"""

    @pytest.mark.asyncio
    async def test_upload_bank_statement_1_success(self, setup_database):
        """Test upload with bank-statement-1.pdf (the problematic one we fixed)"""
        pdf_path = "tests/sample_data/bank-statement-1.pdf"
        
        if not os.path.exists(pdf_path):
            pytest.skip(f"Sample PDF not found: {pdf_path}")
        
        with open(pdf_path, "rb") as f:
            files = {
                "file": ("bank-statement-1.pdf", f, "application/pdf")
            }
            
            response = client.post("/upload/statement?client_id=1", files=files)
        
        assert response.status_code == 201
        data = response.json()
        
        # Verify response structure
        assert "statement_id" in data
        assert "pages_processed" in data
        assert "ocr_preview" in data
        assert isinstance(data["statement_id"], int)
        assert data["statement_id"] > 0
        
        # Verify OCR worked (bank-statement-1.pdf has 2 pages)
        assert data["pages_processed"] == 2
        assert len(data["ocr_preview"]) > 0
        assert "SAMPLE" in data["ocr_preview"] or "JAMES" in data["ocr_preview"]
        
        # Verify database record
        async with TestAsyncSessionLocal() as session:
            stmt = await session.execute(select(Statement).where(Statement.id == data["statement_id"]))
            statement = stmt.scalar_one_or_none()
            assert statement is not None
            assert statement.client_id == 1
            assert statement.ocr_text is not None
            assert len(statement.ocr_text) > 100  # Should have substantial text
            
            # Cleanup test file
            if os.path.exists(statement.file_path):
                os.remove(statement.file_path)

    @pytest.mark.asyncio
    async def test_upload_bank_statement_2_success(self, setup_database):
        """Test upload with bank-statement-2.pdf (the working one)"""
        pdf_path = "tests/sample_data/bank-statement-2.pdf"
        
        if not os.path.exists(pdf_path):
            pytest.skip(f"Sample PDF not found: {pdf_path}")
        
        with open(pdf_path, "rb") as f:
            files = {
                "file": ("bank-statement-2.pdf", f, "application/pdf")
            }
            
            response = client.post("/upload/statement?client_id=1", files=files)
        
        assert response.status_code == 201
        data = response.json()
        
        # Verify response structure
        assert "statement_id" in data
        assert "pages_processed" in data
        assert "ocr_preview" in data
        
        # Verify OCR worked (bank-statement-2.pdf has 1 page)
        assert data["pages_processed"] == 1
        assert len(data["ocr_preview"]) > 0
        assert "Bank" in data["ocr_preview"] or "Account" in data["ocr_preview"]
        
        # Verify database record
        async with TestAsyncSessionLocal() as session:
            stmt = await session.execute(select(Statement).where(Statement.id == data["statement_id"]))
            statement = stmt.scalar_one_or_none()
            assert statement is not None
            assert statement.ocr_text is not None
            
            # Cleanup test file
            if os.path.exists(statement.file_path):
                os.remove(statement.file_path)

    @pytest.mark.asyncio
    async def test_upload_all_sample_pdfs(self, setup_database):
        """Test upload with all available sample PDFs to ensure robustness"""
        sample_files = [
            "tests/sample_data/bank-statement-1.pdf",
            "tests/sample_data/bank-statement-2.pdf", 
            "tests/sample_data/bank-statement-3.pdf",
            "tests/sample_data/bank-statement-4.pdf",
            "tests/sample_data/bank-statement-5.pdf"
        ]
        
        successful_uploads = 0
        
        for pdf_path in sample_files:
            if os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f:
                    files = {
                        "file": (os.path.basename(pdf_path), f, "application/pdf")
                    }
                    
                    response = client.post("/upload/statement?client_id=1", files=files)
                
                assert response.status_code == 201, f"Failed to process {pdf_path}"
                data = response.json()
                
                # Verify OCR extracted some text
                assert data["pages_processed"] > 0
                assert len(data["ocr_preview"]) > 0
                
                successful_uploads += 1
                
                # Cleanup test file
                async with TestAsyncSessionLocal() as session:
                    stmt = await session.execute(select(Statement).where(Statement.id == data["statement_id"]))
                    statement = stmt.scalar_one_or_none()
                    if statement and os.path.exists(statement.file_path):
                        os.remove(statement.file_path)
        
        # Ensure we tested at least one file
        assert successful_uploads > 0, "No sample PDF files found for testing"

    @pytest.mark.asyncio
    async def test_upload_minimal_pdf(self, setup_database):
        """Test upload with minimal PDF (tests OCR with simple content)"""
        pdf_content = create_minimal_pdf()
        
        files = {
            "file": ("minimal.pdf", io.BytesIO(pdf_content), "application/pdf")
        }
        
        response = client.post("/upload/statement?client_id=1", files=files)
        
        assert response.status_code == 201
        data = response.json()
        
        # Even minimal PDF should be processed (though may have no text)
        assert "statement_id" in data
        assert "pages_processed" in data
        assert data["pages_processed"] >= 0
        
        # Cleanup test file
        async with TestAsyncSessionLocal() as session:
            stmt = await session.execute(select(Statement).where(Statement.id == data["statement_id"]))
            statement = stmt.scalar_one_or_none()
            if statement and os.path.exists(statement.file_path):
                os.remove(statement.file_path)

    def test_upload_invalid_mime_type(self):
        """Test upload with invalid MIME type"""
        text_content = b"This is not a PDF file"
        
        files = {
            "file": ("test.txt", io.BytesIO(text_content), "text/plain")
        }
        
        response = client.post("/upload/statement?client_id=1", files=files)
        
        assert response.status_code == 400
        assert "Only PDF files are allowed" in response.json()["detail"]

    def test_upload_large_file(self):
        """Test upload with file larger than 10MB"""
        # Create a large file (11MB)
        large_content = b"a" * (11 * 1024 * 1024)
        
        files = {
            "file": ("large_file.pdf", io.BytesIO(large_content), "application/pdf")
        }
        
        response = client.post("/upload/statement?client_id=1", files=files)
        
        assert response.status_code == 400
        assert "File size must be ≤10 MB" in response.json()["detail"]

    def test_upload_no_file(self):
        """Test upload without providing a file"""
        response = client.post("/upload/statement?client_id=1")
        
        assert response.status_code == 422  # Validation error

    def test_upload_missing_client_id(self):
        """Test upload without providing client_id"""
        pdf_content = create_minimal_pdf()
        files = {
            "file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")
        }
        
        response = client.post("/upload/statement", files=files)
        
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_upload_invalid_client_id(self, setup_database):
        """Test upload with non-existent client_id"""
        pdf_content = create_minimal_pdf()
        files = {
            "file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")
        }
        
        response = client.post("/upload/statement?client_id=999", files=files)
        
        assert response.status_code == 404
        assert "Client with ID 999 not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_upload_corrupted_pdf(self, setup_database):
        """Test upload with corrupted PDF file"""
        corrupted_content = b"This is corrupted PDF content"
        
        files = {
            "file": ("corrupted.pdf", io.BytesIO(corrupted_content), "application/pdf")
        }
        
        response = client.post("/upload/statement?client_id=1", files=files)
        
        # Should return 500 due to OCR processing failure
        assert response.status_code == 500
        assert "All extraction methods failed" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_upload_creates_directory(self, setup_database):
        """Test that upload creates the uploads directory if it doesn't exist"""
        # Remove directory if it exists
        if os.path.exists("data/uploads"):
            import shutil
            shutil.rmtree("data/uploads")
        
        pdf_content = create_minimal_pdf()
        files = {
            "file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")
        }
        
        response = client.post("/upload/statement?client_id=1", files=files)
        
        assert response.status_code == 201
        assert os.path.exists("data/uploads")
        
        # Cleanup
        data = response.json()
        async with TestAsyncSessionLocal() as session:
            stmt = await session.execute(select(Statement).where(Statement.id == data["statement_id"]))
            statement = stmt.scalar_one_or_none()
            if statement and os.path.exists(statement.file_path):
                os.remove(statement.file_path)

    @pytest.mark.asyncio 
    async def test_memory_efficiency_large_pdf(self, setup_database):
        """Test that our memory fixes handle large PDFs without crashing"""
        # Test with the previously problematic bank-statement-1.pdf
        pdf_path = "tests/sample_data/bank-statement-1.pdf"
        
        if not os.path.exists(pdf_path):
            pytest.skip(f"Sample PDF not found: {pdf_path}")
        
        # This should not crash or timeout
        with open(pdf_path, "rb") as f:
            files = {
                "file": ("bank-statement-1.pdf", f, "application/pdf")
            }
            
            response = client.post("/upload/statement?client_id=1", files=files, timeout=120)
        
        # Should succeed without memory issues
        assert response.status_code == 201
        data = response.json()
        assert data["pages_processed"] > 0
        
        # Cleanup
        async with TestAsyncSessionLocal() as session:
            stmt = await session.execute(select(Statement).where(Statement.id == data["statement_id"]))
            statement = stmt.scalar_one_or_none()
            if statement and os.path.exists(statement.file_path):
                os.remove(statement.file_path)


class TestUploadEndpointBasics:
    """Basic endpoint tests without database setup"""
    
    def test_health_endpoint(self):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}
    
    def test_root_endpoint(self):
        """Test root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        assert "LexExtract API is running" in response.json()["message"] 