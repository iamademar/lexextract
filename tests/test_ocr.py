import pytest
import sys
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.ocr import run_ocr, get_ocr_instance


class TestOCRImplementation:
    
    def setup_method(self):
        """Setup method run before each test"""
        self.sample_pdf_1 = "tests/sample_data/bank-statement-1.pdf"
        self.sample_pdf_2 = "tests/sample_data/bank-statement-2.pdf"
    
    @pytest.mark.asyncio
    async def test_run_ocr_with_real_pdf_1(self):
        """Test OCR processing with the first sample PDF"""
        # Skip if sample file doesn't exist
        if not os.path.exists(self.sample_pdf_1):
            pytest.skip(f"Sample PDF not found: {self.sample_pdf_1}")
        
        result = await run_ocr(self.sample_pdf_1)
        
        # Assert it returns a list
        assert isinstance(result, list)
        
        # Assert it returns at least one page
        assert len(result) > 0
        
        # Assert each page contains text (not empty)
        for page_text in result:
            assert isinstance(page_text, str)
            # Most bank statements should have some text
            assert len(page_text.strip()) > 0
    
    @pytest.mark.asyncio
    async def test_run_ocr_with_real_pdf_2(self):
        """Test OCR processing with the second sample PDF"""
        # Skip if sample file doesn't exist
        if not os.path.exists(self.sample_pdf_2):
            pytest.skip(f"Sample PDF not found: {self.sample_pdf_2}")
        
        result = await run_ocr(self.sample_pdf_2)
        
        # Assert it returns a list
        assert isinstance(result, list)
        
        # Assert it returns at least one page
        assert len(result) > 0
        
        # Assert each page contains text (not empty)
        for page_text in result:
            assert isinstance(page_text, str)
            # Most bank statements should have some text
            assert len(page_text.strip()) > 0
    
    @pytest.mark.asyncio
    async def test_run_ocr_file_not_found(self):
        """Test OCR with non-existent file"""
        non_existent_file = "non_existent_file.pdf"
        
        with pytest.raises(FileNotFoundError):
            await run_ocr(non_existent_file)
    
    @pytest.mark.asyncio
    async def test_run_ocr_with_empty_file(self):
        """Test OCR with empty file"""
        # Create a temporary empty file
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            tmp_file_path = tmp_file.name
        
        try:
            # This should raise an exception as it's not a valid PDF
            with pytest.raises(Exception):
                await run_ocr(tmp_file_path)
        finally:
            # Clean up
            os.unlink(tmp_file_path)
    
    def test_get_ocr_instance(self):
        """Test that OCR instance is created successfully"""
        ocr_instance = get_ocr_instance()
        assert ocr_instance is not None
        
        # Test singleton behavior - should return same instance
        ocr_instance_2 = get_ocr_instance()
        assert ocr_instance is ocr_instance_2
    
    @pytest.mark.asyncio
    async def test_run_ocr_returns_expected_format(self):
        """Test that OCR returns expected format even with mocked data"""
        # Skip if sample file doesn't exist
        if not os.path.exists(self.sample_pdf_1):
            pytest.skip(f"Sample PDF not found: {self.sample_pdf_1}")
        
        result = await run_ocr(self.sample_pdf_1)
        
        # Verify the structure
        assert isinstance(result, list)
        for page_text in result:
            assert isinstance(page_text, str)
    
    @pytest.mark.asyncio
    async def test_run_ocr_with_mocked_paddleocr(self):
        """Test OCR with mocked PaddleOCR for consistent testing"""
        mock_ocr_result = [
            [
                [[[100, 50], [200, 50], [200, 100], [100, 100]], ['Bank Statement', 0.95]],
                [[[100, 120], [300, 120], [300, 150], [100, 150]], ['Account Number: 12345', 0.92]],
                [[[100, 170], [250, 170], [250, 200], [100, 200]], ['Balance: $1,000.00', 0.88]]
            ]
        ]
        
        with patch('app.services.ocr.get_ocr_instance') as mock_get_ocr:
            mock_ocr = MagicMock()
            mock_ocr.ocr.return_value = mock_ocr_result
            mock_get_ocr.return_value = mock_ocr
            
            # Create a mock PDF file
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
                tmp_file_path = tmp_file.name
                # Write minimal PDF content
                tmp_file.write(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
            
            try:
                with patch('fitz.open') as mock_fitz:
                    mock_doc = MagicMock()
                    mock_page = MagicMock()
                    mock_pix = MagicMock()
                    mock_pix.tobytes.return_value = b"fake_image_data"
                    mock_page.get_pixmap.return_value = mock_pix
                    mock_doc.__len__.return_value = 1
                    mock_doc.__getitem__.return_value = mock_page
                    mock_fitz.return_value = mock_doc
                    
                    with patch('PIL.Image.open') as mock_image_open:
                        mock_image = MagicMock()
                        mock_image_open.return_value = mock_image
                        
                        with patch('numpy.array') as mock_array:
                            mock_array.return_value = "fake_array"
                            
                            result = await run_ocr(tmp_file_path)
                            
                            # Should return processed text
                            assert isinstance(result, list)
                            assert len(result) == 1
                            assert "Bank Statement" in result[0]
                            assert "Account Number: 12345" in result[0]
                            assert "Balance: $1,000.00" in result[0]
            finally:
                os.unlink(tmp_file_path)


class TestOCRIntegration:
    """Integration tests for OCR functionality"""
    
    @pytest.mark.asyncio
    async def test_ocr_with_both_sample_files(self):
        """Test OCR with both sample files and compare results"""
        sample_files = [
            "tests/sample_data/bank-statement-1.pdf",
            "tests/sample_data/bank-statement-2.pdf"
        ]
        
        results = []
        for file_path in sample_files:
            if os.path.exists(file_path):
                result = await run_ocr(file_path)
                results.append(result)
        
        # Skip if no sample files exist
        if not results:
            pytest.skip("No sample PDF files found")
        
        # Each result should be a list of strings
        for result in results:
            assert isinstance(result, list)
            assert len(result) > 0
            for page_text in result:
                assert isinstance(page_text, str)
    
    @pytest.mark.asyncio
    async def test_ocr_performance_benchmark(self):
        """Basic performance test for OCR"""
        import time
        
        if not os.path.exists("tests/sample_data/bank-statement-1.pdf"):
            pytest.skip("Sample PDF not found")
        
        start_time = time.time()
        result = await run_ocr("tests/sample_data/bank-statement-1.pdf")
        end_time = time.time()
        
        processing_time = end_time - start_time
        
        # Assert processing completes within reasonable time (adjust as needed)
        assert processing_time < 30  # 30 seconds max
        assert isinstance(result, list)
        assert len(result) > 0 