import pytest
import os
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.ocr import run_ocr, run_structure_analysis, run_unified_ocr_pipeline
from app.services.pdf_utils import is_text_page, is_scanned_page


class TestOCRIntegration:
    """Integration tests for the unified OCR pipeline."""
    
    @pytest.fixture
    def sample_pdf_path(self):
        """Return path to a sample PDF for testing."""
        return os.path.join(os.path.dirname(__file__), 'sample_data', 'bank-statement-1.pdf')
    
    @pytest.fixture
    def mock_text_page(self):
        """Mock is_text_page to return True (vector PDF)."""
        with patch('app.services.ocr.is_text_page', return_value=True):
            yield
    
    @pytest.fixture
    def mock_scanned_page(self):
        """Mock is_text_page to return False (scanned PDF)."""
        with patch('app.services.ocr.is_text_page', return_value=False):
            yield
    
    @pytest.fixture
    def mock_camelot_extraction(self):
        """Mock Camelot extraction to return sample DataFrames."""
        import pandas as pd
        
        # Create mock DataFrames
        mock_df1 = pd.DataFrame([
            ['Date', 'Description', 'Amount'],
            ['2023-01-01', 'Purchase', '-50.00'],
            ['2023-01-02', 'Deposit', '100.00']
        ])
        
        mock_df2 = pd.DataFrame([
            ['Account', 'Balance'],
            ['Checking', '1500.00']
        ])
        
        with patch('app.services.ocr.extract_tables_with_camelot', return_value=[mock_df1, mock_df2]):
            yield
    
    @pytest.fixture
    def mock_tesseract_extraction(self):
        """Mock Tesseract extraction to return sample DataFrames."""
        import pandas as pd
        
        # Create mock DataFrames
        mock_df1 = pd.DataFrame([
            ['Date', 'Payee', 'Amount'],
            ['01/01/2023', 'Store ABC', '25.50'],
            ['01/02/2023', 'Gas Station', '45.00']
        ])
        
        with patch('app.services.ocr.extract_tables_with_tesseract_pipeline', return_value=[mock_df1]):
            yield
    
    @pytest.fixture
    def mock_full_text_extraction(self):
        """Mock full text extraction."""
        def mock_extract_text_side_effect(*args, **kwargs):
            return "Sample extracted text from PDF page"
        
        with patch('pdfplumber.open') as mock_open:
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "Sample extracted text from PDF page"
            mock_page.to_image.return_value.original = MagicMock()
            
            mock_pdf = MagicMock()
            mock_pdf.pages = [mock_page]
            mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
            mock_pdf.__exit__ = MagicMock(return_value=None)
            
            mock_open.return_value = mock_pdf
            yield
    
    def test_run_unified_ocr_pipeline_camelot_path(self, sample_pdf_path, mock_text_page, 
                                                   mock_camelot_extraction, mock_full_text_extraction):
        """Test unified OCR pipeline with Camelot (text PDF) path."""
        results = run_unified_ocr_pipeline(sample_pdf_path)
        
        # Verify structure
        assert isinstance(results, list)
        assert len(results) > 0
        
        # Check first page result
        page_result = results[0]
        assert 'page' in page_result
        assert 'tables' in page_result
        assert 'full_text' in page_result
        assert 'page_type' in page_result
        assert 'extraction_method' in page_result
        
        # Verify page number
        assert page_result['page'] == 1
        
        # Verify tables are list of lists
        assert isinstance(page_result['tables'], list)
        if page_result['tables']:
            for table in page_result['tables']:
                assert isinstance(table, list)
                if table:
                    assert isinstance(table[0], list)
        
        # Verify full text
        assert isinstance(page_result['full_text'], str)
        
        # Verify page type indicates text page
        assert 'text' in page_result['page_type']
        
        # Verify extraction method is camelot
        assert page_result['extraction_method'] == 'camelot'
    
    def test_run_unified_ocr_pipeline_tesseract_path(self, sample_pdf_path, mock_scanned_page, 
                                                     mock_tesseract_extraction, mock_full_text_extraction):
        """Test unified OCR pipeline with Tesseract (scanned PDF) path."""
        with patch('pytesseract.image_to_string', return_value="OCR extracted text"):
            results = run_unified_ocr_pipeline(sample_pdf_path)
        
        # Verify structure
        assert isinstance(results, list)
        assert len(results) > 0
        
        # Check first page result
        page_result = results[0]
        assert 'page' in page_result
        assert 'tables' in page_result
        assert 'full_text' in page_result
        assert 'page_type' in page_result
        assert 'extraction_method' in page_result
        
        # Verify page number
        assert page_result['page'] == 1
        
        # Verify tables are list of lists
        assert isinstance(page_result['tables'], list)
        if page_result['tables']:
            for table in page_result['tables']:
                assert isinstance(table, list)
                if table:
                    assert isinstance(table[0], list)
        
        # Verify full text
        assert isinstance(page_result['full_text'], str)
        
        # Verify page type indicates scanned page
        assert 'scanned' in page_result['page_type']
        
        # Verify extraction method is tesseract
        assert page_result['extraction_method'] == 'tesseract'
    
    def test_run_unified_ocr_pipeline_fallback(self, sample_pdf_path, mock_text_page, 
                                               mock_tesseract_extraction, mock_full_text_extraction):
        """Test unified OCR pipeline fallback from Camelot to Tesseract."""
        # Mock camelot to fail, then tesseract to succeed
        with patch('app.services.ocr.extract_tables_with_camelot', side_effect=Exception("Camelot failed")):
            with patch('pytesseract.image_to_string', return_value="OCR extracted text"):
                results = run_unified_ocr_pipeline(sample_pdf_path)
        
        # Should get results despite camelot failure
        assert isinstance(results, list)
        assert len(results) > 0
        
        page_result = results[0]
        # Should fall back to tesseract_fallback
        assert page_result['extraction_method'] == 'tesseract_fallback'
    
    @pytest.mark.asyncio
    async def test_run_ocr_preserves_api(self, sample_pdf_path, mock_text_page, 
                                         mock_camelot_extraction, mock_full_text_extraction):
        """Test that run_ocr preserves the existing API signature."""
        result = await run_ocr(sample_pdf_path)
        
        # Should return list of strings (one per page)
        assert isinstance(result, list)
        assert len(result) > 0
        
        # Each item should be a string
        for page_text in result:
            assert isinstance(page_text, str)
    
    @pytest.mark.asyncio
    async def test_run_structure_analysis_preserves_api(self, sample_pdf_path, mock_text_page, 
                                                         mock_camelot_extraction, mock_full_text_extraction):
        """Test that run_structure_analysis preserves the existing API signature."""
        result = await run_structure_analysis(sample_pdf_path)
        
        # Should return list of dicts with structure info
        assert isinstance(result, list)
        assert len(result) > 0
        
        # Each item should be a dict with expected keys
        for page_result in result:
            assert isinstance(page_result, dict)
            assert 'page' in page_result
            assert 'structure' in page_result
    
    def test_run_unified_ocr_pipeline_mixed_pages(self, sample_pdf_path, mock_camelot_extraction, 
                                                  mock_tesseract_extraction, mock_full_text_extraction):
        """Test unified OCR pipeline with mixed page types."""
        
        # Mock different page types: first is text, second is scanned
        page_types = [True, False]  # text page, then scanned page
        
        with patch('app.services.ocr.is_text_page', side_effect=page_types):
            with patch('pytesseract.image_to_string', return_value="OCR extracted text"):
                # Mock PDF with 2 pages
                with patch('pdfplumber.open') as mock_open:
                    mock_page1 = MagicMock()
                    mock_page1.extract_text.return_value = "Text page content"
                    mock_page1.to_image.return_value.original = MagicMock()
                    
                    mock_page2 = MagicMock()
                    mock_page2.extract_text.return_value = "Scanned page content"
                    mock_page2.to_image.return_value.original = MagicMock()
                    
                    mock_pdf = MagicMock()
                    mock_pdf.pages = [mock_page1, mock_page2]
                    mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
                    mock_pdf.__exit__ = MagicMock(return_value=None)
                    
                    mock_open.return_value = mock_pdf
                    
                    results = run_unified_ocr_pipeline(sample_pdf_path)
        
        # Should have 2 pages processed
        assert len(results) == 2
        
        # First page should use camelot
        page1 = results[0]
        assert page1['page'] == 1
        assert page1['extraction_method'] == 'camelot'
        assert 'text' in page1['page_type']
        
        # Second page should use tesseract
        page2 = results[1]
        assert page2['page'] == 2
        assert page2['extraction_method'] == 'tesseract'
        assert 'scanned' in page2['page_type']
    
    def test_run_unified_ocr_pipeline_error_handling(self, sample_pdf_path):
        """Test error handling in unified OCR pipeline."""
        # Test with non-existent file
        with pytest.raises(Exception) as exc_info:
            run_unified_ocr_pipeline("nonexistent.pdf")
        assert "failed" in str(exc_info.value).lower()
    
    def test_run_unified_ocr_pipeline_empty_tables(self, sample_pdf_path, mock_text_page, 
                                                   mock_full_text_extraction):
        """Test unified OCR pipeline with empty table extraction."""
        import pandas as pd
        
        # Mock empty dataframe
        empty_df = pd.DataFrame()
        
        with patch('app.services.ocr.extract_tables_with_camelot', return_value=[empty_df]):
            results = run_unified_ocr_pipeline(sample_pdf_path)
        
        # Should still return valid results
        assert len(results) > 0
        page_result = results[0]
        
        # Tables should be empty list (empty dataframes filtered out)
        assert isinstance(page_result['tables'], list)
        assert len(page_result['tables']) == 0
    
    def test_run_unified_ocr_pipeline_table_conversion(self, sample_pdf_path, mock_text_page, 
                                                       mock_full_text_extraction):
        """Test that DataFrames are properly converted to lists of lists."""
        import pandas as pd
        
        # Mock dataframe with specific data
        mock_df = pd.DataFrame([
            ['Col1', 'Col2', 'Col3'],
            ['A1', 'B1', 'C1'],
            ['A2', 'B2', 'C2']
        ])
        
        with patch('app.services.ocr.extract_tables_with_camelot', return_value=[mock_df]):
            results = run_unified_ocr_pipeline(sample_pdf_path)
        
        page_result = results[0]
        tables = page_result['tables']
        
        # Should have one table
        assert len(tables) == 1
        
        # Table should be list of lists
        table = tables[0]
        assert isinstance(table, list)
        assert len(table) == 3  # 3 rows
        
        # Each row should be a list
        for row in table:
            assert isinstance(row, list)
            assert len(row) == 3  # 3 columns
        
        # Verify actual data
        assert table[0] == ['Col1', 'Col2', 'Col3']
        assert table[1] == ['A1', 'B1', 'C1']
        assert table[2] == ['A2', 'B2', 'C2']


if __name__ == "__main__":
    pytest.main([__file__]) 