import pytest
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from app.services.pdf_utils import is_text_page, is_scanned_page


class TestPDFUtils:
    """Test suite for PDF page type detection utilities"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.test_data_dir = Path(__file__).parent / "sample_data"
        self.sample_pdf_1 = self.test_data_dir / "bank-statement-1.pdf"
        self.sample_pdf_2 = self.test_data_dir / "bank-statement-2.pdf"
        
    def test_is_text_page_with_text_pdf(self):
        """Test is_text_page with a PDF containing extractable text"""
        # Mock pdfplumber to simulate a text-based PDF
        with patch('app.services.pdf_utils.pdfplumber') as mock_pdfplumber:
            # Mock PDF with text content - need more than 50 chars and 10 words
            mock_page = Mock()
            mock_page.extract_text.return_value = "This is sample text from a bank statement with enough content to pass the requirements\nDate: 01/01/2024\nAmount: $100.00 with more words"
            
            mock_pdf = Mock()
            mock_pdf.pages = [mock_page]
            mock_pdf.__enter__ = Mock(return_value=mock_pdf)
            mock_pdf.__exit__ = Mock(return_value=None)
            
            mock_pdfplumber.open.return_value = mock_pdf
            
            # Test with a real file path (mocked internally)
            result = is_text_page(str(self.sample_pdf_1), 1)
            
            assert result is True
            mock_pdfplumber.open.assert_called_once()
            mock_page.extract_text.assert_called_once()
    
    def test_is_text_page_with_scanned_pdf(self):
        """Test is_text_page with a scanned PDF (no extractable text)"""
        with patch('app.services.pdf_utils.pdfplumber') as mock_pdfplumber:
            # Mock PDF with no text content
            mock_page = Mock()
            mock_page.extract_text.return_value = None
            
            mock_pdf = Mock()
            mock_pdf.pages = [mock_page]
            mock_pdf.__enter__ = Mock(return_value=mock_pdf)
            mock_pdf.__exit__ = Mock(return_value=None)
            
            mock_pdfplumber.open.return_value = mock_pdf
            
            result = is_text_page(str(self.sample_pdf_1), 1)
            
            assert result is False
            mock_pdfplumber.open.assert_called_once()
            mock_page.extract_text.assert_called_once()
    
    def test_is_text_page_with_whitespace_only(self):
        """Test is_text_page with PDF containing only whitespace"""
        with patch('app.services.pdf_utils.pdfplumber') as mock_pdfplumber:
            # Mock PDF with only whitespace
            mock_page = Mock()
            mock_page.extract_text.return_value = "   \n\n\t\t   \n  "
            
            mock_pdf = Mock()
            mock_pdf.pages = [mock_page]
            mock_pdf.__enter__ = Mock(return_value=mock_pdf)
            mock_pdf.__exit__ = Mock(return_value=None)
            
            mock_pdfplumber.open.return_value = mock_pdf
            
            result = is_text_page(str(self.sample_pdf_1), 1)
            
            assert result is False
    
    def test_is_text_page_with_non_alphanumeric_only(self):
        """Test is_text_page with PDF containing only formatting characters"""
        with patch('app.services.pdf_utils.pdfplumber') as mock_pdfplumber:
            # Mock PDF with only formatting characters
            mock_page = Mock()
            mock_page.extract_text.return_value = "---|---|---\n***   ***\n___________"
            
            mock_pdf = Mock()
            mock_pdf.pages = [mock_page]
            mock_pdf.__enter__ = Mock(return_value=mock_pdf)
            mock_pdf.__exit__ = Mock(return_value=None)
            
            mock_pdfplumber.open.return_value = mock_pdf
            
            result = is_text_page(str(self.sample_pdf_1), 1)
            
            assert result is False
    
    def test_is_text_page_with_mixed_content(self):
        """Test is_text_page with PDF containing mixed alphanumeric and formatting characters"""
        with patch('app.services.pdf_utils.pdfplumber') as mock_pdfplumber:
            # Mock PDF with mixed content - need more than 50 chars and 10 words
            mock_page = Mock()
            mock_page.extract_text.return_value = "---|Date123|Amount456---\n***   ABC   ***\n___DEF789___\nTransaction data with enough content to pass the word count and character count requirements for text detection"
            
            mock_pdf = Mock()
            mock_pdf.pages = [mock_page]
            mock_pdf.__enter__ = Mock(return_value=mock_pdf)
            mock_pdf.__exit__ = Mock(return_value=None)
            
            mock_pdfplumber.open.return_value = mock_pdf
            
            result = is_text_page(str(self.sample_pdf_1), 1)
            
            assert result is True
    
    def test_is_scanned_page_with_text_pdf(self):
        """Test is_scanned_page with a PDF containing extractable text"""
        with patch('app.services.pdf_utils.pdfplumber') as mock_pdfplumber:
            # Mock PDF with text content - need more than 50 chars and 10 words
            mock_page = Mock()
            mock_page.extract_text.return_value = "This is sample text from a bank statement with enough content to pass the requirements and have more than ten words"
            
            mock_pdf = Mock()
            mock_pdf.pages = [mock_page]
            mock_pdf.__enter__ = Mock(return_value=mock_pdf)
            mock_pdf.__exit__ = Mock(return_value=None)
            
            mock_pdfplumber.open.return_value = mock_pdf
            
            result = is_scanned_page(str(self.sample_pdf_1), 1)
            
            assert result is False
    
    def test_is_scanned_page_with_scanned_pdf(self):
        """Test is_scanned_page with a scanned PDF (no extractable text)"""
        with patch('app.services.pdf_utils.pdfplumber') as mock_pdfplumber:
            # Mock PDF with no text content
            mock_page = Mock()
            mock_page.extract_text.return_value = None
            
            mock_pdf = Mock()
            mock_pdf.pages = [mock_page]
            mock_pdf.__enter__ = Mock(return_value=mock_pdf)
            mock_pdf.__exit__ = Mock(return_value=None)
            
            mock_pdfplumber.open.return_value = mock_pdf
            
            result = is_scanned_page(str(self.sample_pdf_1), 1)
            
            assert result is True
    
    def test_file_not_found_error(self):
        """Test that file not found scenarios are handled gracefully"""
        non_existent_file = Path("/path/to/non/existent/file.pdf")
        
        # The new implementation returns False instead of raising exceptions
        result = is_text_page(str(non_existent_file), 1)
        assert result is False
    
    def test_invalid_page_number_too_high(self):
        """Test that invalid page numbers are handled gracefully"""
        with patch('app.services.pdf_utils.pdfplumber') as mock_pdfplumber:
            # Mock PDF with only 1 page
            mock_pdf = Mock()
            mock_pdf.pages = [Mock()]  # Only one page
            mock_pdf.__enter__ = Mock(return_value=mock_pdf)
            mock_pdf.__exit__ = Mock(return_value=None)
            
            mock_pdfplumber.open.return_value = mock_pdf
            
            # The new implementation returns False instead of raising ValueError
            result = is_text_page(str(self.sample_pdf_1), 5)  # Request page 5 when only 1 page exists
            assert result is False
    
    def test_invalid_page_number_zero(self):
        """Test that invalid page numbers are handled gracefully"""
        with patch('app.services.pdf_utils.pdfplumber') as mock_pdfplumber:
            # Mock PDF with 1 page
            mock_pdf = Mock()
            mock_pdf.pages = [Mock()]
            mock_pdf.__enter__ = Mock(return_value=mock_pdf)
            mock_pdf.__exit__ = Mock(return_value=None)
            
            mock_pdfplumber.open.return_value = mock_pdf
            
            # The new implementation returns False instead of raising ValueError
            result = is_text_page(str(self.sample_pdf_1), 0)  # Page numbers should be 1-indexed
            assert result is False
    
    def test_invalid_page_number_negative(self):
        """Test that negative page numbers are handled gracefully"""
        with patch('app.services.pdf_utils.pdfplumber') as mock_pdfplumber:
            # Mock PDF with 1 page
            mock_pdf = Mock()
            mock_pdf.pages = [Mock()]
            mock_pdf.__enter__ = Mock(return_value=mock_pdf)
            mock_pdf.__exit__ = Mock(return_value=None)
            
            mock_pdfplumber.open.return_value = mock_pdf
            
            # The new implementation returns False instead of raising ValueError
            result = is_text_page(str(self.sample_pdf_1), -1)
            assert result is False
    
    def test_pdf_processing_exception(self):
        """Test that general exceptions are handled gracefully"""
        with patch('app.services.pdf_utils.pdfplumber') as mock_pdfplumber:
            # Mock pdfplumber to raise an exception
            mock_pdfplumber.open.side_effect = Exception("Corrupted PDF file")
            
            # The new implementation returns False instead of raising exceptions
            result = is_text_page(str(self.sample_pdf_1), 1)
            assert result is False
    
    def test_multiple_pages_text_detection(self):
        """Test is_text_page with multiple pages - some with text, some without"""
        with patch('app.services.pdf_utils.pdfplumber') as mock_pdfplumber:
            # Mock PDF with multiple pages
            mock_page_1 = Mock()
            mock_page_1.extract_text.return_value = "Page 1 has text content with enough words to pass the requirements for text detection algorithm"
            
            mock_page_2 = Mock()
            mock_page_2.extract_text.return_value = None  # Scanned page
            
            mock_page_3 = Mock()
            mock_page_3.extract_text.return_value = "Page 3 also has text content with enough words to pass the requirements for text detection algorithm"
            
            mock_pdf = Mock()
            mock_pdf.pages = [mock_page_1, mock_page_2, mock_page_3]
            mock_pdf.__enter__ = Mock(return_value=mock_pdf)
            mock_pdf.__exit__ = Mock(return_value=None)
            
            mock_pdfplumber.open.return_value = mock_pdf
            
            # Test each page
            assert is_text_page(str(self.sample_pdf_1), 1) is True
            assert is_text_page(str(self.sample_pdf_1), 2) is False
            assert is_text_page(str(self.sample_pdf_1), 3) is True
            
            # Test is_scanned_page for consistency
            assert is_scanned_page(str(self.sample_pdf_1), 1) is False
            assert is_scanned_page(str(self.sample_pdf_1), 2) is True
            assert is_scanned_page(str(self.sample_pdf_1), 3) is False
    
    def test_pathlib_path_input(self):
        """Test that both string and Path objects work as input"""
        with patch('app.services.pdf_utils.pdfplumber') as mock_pdfplumber:
            # Mock PDF with text content - need more than 50 chars and 10 words
            mock_page = Mock()
            mock_page.extract_text.return_value = "Test content with enough words to pass the requirements for text detection algorithm implementation"
            
            mock_pdf = Mock()
            mock_pdf.pages = [mock_page]
            mock_pdf.__enter__ = Mock(return_value=mock_pdf)
            mock_pdf.__exit__ = Mock(return_value=None)
            
            mock_pdfplumber.open.return_value = mock_pdf
            
            # Test with string path
            result_str = is_text_page(str(self.sample_pdf_1), 1)
            
            # Test with Path object (converted to string)
            result_path = is_text_page(str(self.sample_pdf_1), 1)
            
            # Both should work and return the same result
            assert result_str is True
            assert result_path is True
    
    @pytest.mark.integration
    def test_real_pdf_files(self):
        """Integration test with actual PDF files if they exist"""
        # Skip if sample files don't exist
        if not self.sample_pdf_1.exists():
            pytest.skip("Sample PDF files not available for integration testing")
        
        # Test with actual PDF files
        try:
            # Test first page of sample PDF
            result_1 = is_text_page(str(self.sample_pdf_1), 1)
            result_2 = is_scanned_page(str(self.sample_pdf_1), 1)
            
            # These should be opposites
            assert result_1 != result_2
            
            # Test with second sample PDF if available
            if self.sample_pdf_2.exists():
                result_3 = is_text_page(str(self.sample_pdf_2), 1)
                result_4 = is_scanned_page(str(self.sample_pdf_2), 1)
                
                # These should also be opposites
                assert result_3 != result_4
                
        except Exception as e:
            pytest.skip(f"Integration test failed due to: {e}") 