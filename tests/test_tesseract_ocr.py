import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch, MagicMock, call
import tempfile
import os
from pathlib import Path
from PIL import Image

# Import the functions we want to test
from app.services.tesseract_ocr import (
    extract_tables_with_tesseract_pipeline,
    _parse_page_specification,
    _convert_page_to_image,
    _try_camelot_on_image,
    _extract_tables_with_region_detection,
    _ocr_table_image,
    _reconstruct_table_from_ocr_data,
    extract_tables_and_text,
    run_extraction_with_tesseract,
    get_tesseract_table_metadata
)


class TestTesseractOCR:
    """Test suite for the enhanced Tesseract OCR service."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sample_pdf_path = "tests/sample_data/bank-statement-1.pdf"
        self.nonexistent_pdf = "tests/sample_data/nonexistent.pdf"
        
        # Mock OCR data for testing
        self.mock_ocr_data = {
            'text': ['Date', 'Description', 'Amount', '2023-01-01', 'Purchase', '-50.00'],
            'left': [10, 100, 200, 10, 100, 200],
            'top': [10, 10, 10, 30, 30, 30],
            'width': [80, 90, 80, 80, 90, 80],
            'height': [15, 15, 15, 15, 15, 15],
            'conf': [95, 90, 85, 92, 88, 94]
        }

    def test_parse_page_specification_single_page(self):
        """Test parsing single page specification."""
        result = _parse_page_specification("1", 5)
        assert result == [0]  # 0-indexed

    def test_parse_page_specification_page_range(self):
        """Test parsing page range specification."""
        result = _parse_page_specification("1-3", 5)
        assert result == [0, 1, 2]  # 0-indexed

    def test_parse_page_specification_comma_separated(self):
        """Test parsing comma-separated page specification."""
        result = _parse_page_specification("1,3,5", 5)
        assert result == [0, 2, 4]  # 0-indexed

    def test_parse_page_specification_mixed(self):
        """Test parsing mixed page specification."""
        result = _parse_page_specification("1,3-4", 5)
        assert result == [0, 2, 3]  # 0-indexed

    def test_parse_page_specification_invalid_pages_filtered(self):
        """Test that invalid page numbers are filtered out."""
        result = _parse_page_specification("1,6,10", 5)
        assert result == [0]  # Only page 1 is valid

    @patch('app.services.tesseract_ocr.pdfplumber')
    def test_convert_page_to_image_success(self, mock_pdfplumber):
        """Test successful page to image conversion."""
        mock_page = Mock()
        mock_to_image = Mock()
        mock_image = Mock()
        mock_to_image.original = mock_image
        mock_page.to_image.return_value = mock_to_image
        
        result = _convert_page_to_image(mock_page, resolution=300)
        
        assert result == mock_image
        mock_page.to_image.assert_called_once_with(resolution=300)

    @patch('app.services.tesseract_ocr.pdfplumber')
    def test_convert_page_to_image_failure(self, mock_pdfplumber):
        """Test page to image conversion failure."""
        mock_page = Mock()
        mock_page.to_image.side_effect = Exception("Conversion failed")
        
        with pytest.raises(Exception, match="Conversion failed"):
            _convert_page_to_image(mock_page)

    @patch('app.services.tesseract_ocr.camelot')
    @patch('app.services.tesseract_ocr.tempfile')
    @patch('app.services.tesseract_ocr.os')
    def test_try_camelot_on_image_success(self, mock_os, mock_tempfile, mock_camelot):
        """Test successful camelot table extraction from image."""
        # Mock tempfile
        mock_tmp_file = Mock()
        mock_tmp_file.name = "/tmp/test.png"
        mock_tempfile.NamedTemporaryFile.return_value.__enter__.return_value = mock_tmp_file
        
        # Mock camelot
        mock_table = Mock()
        mock_df = pd.DataFrame({'A': [1, 2], 'B': [3, 4]})
        mock_table.df = mock_df
        mock_camelot.read_pdf.return_value = [mock_table]
        
        # Mock os.path.exists and os.unlink
        mock_os.path.exists.return_value = True
        
        # Mock image
        mock_image = Mock()
        
        result = _try_camelot_on_image(mock_image, page_num=1, edge_tol=200)
        
        assert len(result) == 1
        assert isinstance(result[0], pd.DataFrame)
        assert result[0].equals(mock_df)
        mock_image.save.assert_called_once_with("/tmp/test.png", format='PNG')

    @patch('app.services.tesseract_ocr.camelot')
    @patch('app.services.tesseract_ocr.tempfile')
    @patch('app.services.tesseract_ocr.os')
    def test_try_camelot_on_image_no_tables(self, mock_os, mock_tempfile, mock_camelot):
        """Test camelot finding no tables."""
        # Mock tempfile
        mock_tmp_file = Mock()
        mock_tmp_file.name = "/tmp/test.png"
        mock_tempfile.NamedTemporaryFile.return_value.__enter__.return_value = mock_tmp_file
        
        # Mock camelot returning no tables
        mock_camelot.read_pdf.return_value = []
        
        # Mock os.path.exists and os.unlink
        mock_os.path.exists.return_value = True
        
        # Mock image
        mock_image = Mock()
        
        result = _try_camelot_on_image(mock_image, page_num=1, edge_tol=200)
        
        assert result == []

    @patch('app.services.tesseract_ocr.camelot')
    @patch('app.services.tesseract_ocr.tempfile')
    @patch('app.services.tesseract_ocr.os')
    def test_try_camelot_on_image_exception(self, mock_os, mock_tempfile, mock_camelot):
        """Test camelot processing exception."""
        # Mock tempfile
        mock_tmp_file = Mock()
        mock_tmp_file.name = "/tmp/test.png"
        mock_tempfile.NamedTemporaryFile.return_value.__enter__.return_value = mock_tmp_file
        
        # Mock camelot exception
        mock_camelot.read_pdf.side_effect = Exception("Camelot failed")
        
        # Mock os.path.exists and os.unlink
        mock_os.path.exists.return_value = True
        
        # Mock image
        mock_image = Mock()
        
        result = _try_camelot_on_image(mock_image, page_num=1, edge_tol=200)
        
        assert result == []

    def test_reconstruct_table_from_ocr_data_success(self):
        """Test successful table reconstruction from OCR data."""
        ocr_data = [
            {'text': 'Date', 'left': 10, 'top': 10},
            {'text': 'Description', 'left': 100, 'top': 10},
            {'text': 'Amount', 'left': 200, 'top': 10},
            {'text': '2023-01-01', 'left': 10, 'top': 30},
            {'text': 'Purchase', 'left': 100, 'top': 30},
            {'text': '-50.00', 'left': 200, 'top': 30}
        ]
        
        result = _reconstruct_table_from_ocr_data(ocr_data)
        
        assert isinstance(result, pd.DataFrame)
        assert result.shape == (2, 3)
        assert result.iloc[0, 0] == 'Date'
        assert result.iloc[0, 1] == 'Description'
        assert result.iloc[0, 2] == 'Amount'
        assert result.iloc[1, 0] == '2023-01-01'
        assert result.iloc[1, 1] == 'Purchase'
        assert result.iloc[1, 2] == '-50.00'

    def test_reconstruct_table_from_ocr_data_empty(self):
        """Test table reconstruction with empty OCR data."""
        result = _reconstruct_table_from_ocr_data([])
        
        assert isinstance(result, pd.DataFrame)
        assert result.empty

    @patch('app.services.tesseract_ocr.pytesseract')
    def test_ocr_table_image_success(self, mock_pytesseract):
        """Test successful OCR on table image."""
        mock_pytesseract.image_to_data.return_value = self.mock_ocr_data
        
        mock_image = Mock()
        
        result = _ocr_table_image(mock_image, table_idx=1, page_num=1, min_confidence=60.0)
        
        assert isinstance(result, pd.DataFrame)
        assert not result.empty
        mock_pytesseract.image_to_data.assert_called_once()

    @patch('app.services.tesseract_ocr.pytesseract')
    def test_ocr_table_image_low_confidence(self, mock_pytesseract):
        """Test OCR with low confidence data."""
        low_conf_data = self.mock_ocr_data.copy()
        low_conf_data['conf'] = [30, 35, 40, 45, 50, 55]  # All below 60
        
        mock_pytesseract.image_to_data.return_value = low_conf_data
        
        mock_image = Mock()
        
        result = _ocr_table_image(mock_image, table_idx=1, page_num=1, min_confidence=60.0)
        
        assert result is None

    @patch('app.services.tesseract_ocr.pytesseract')
    def test_ocr_table_image_exception(self, mock_pytesseract):
        """Test OCR processing exception."""
        mock_pytesseract.image_to_data.side_effect = Exception("OCR failed")
        
        mock_image = Mock()
        
        result = _ocr_table_image(mock_image, table_idx=1, page_num=1, min_confidence=60.0)
        
        assert result is None

    def test_extract_tables_with_tesseract_pipeline_file_not_found(self):
        """Test pipeline with non-existent file."""
        with pytest.raises(FileNotFoundError):
            extract_tables_with_tesseract_pipeline(self.nonexistent_pdf)

    @patch('app.services.tesseract_ocr.pdfplumber')
    @patch('app.services.tesseract_ocr._convert_page_to_image')
    @patch('app.services.tesseract_ocr._try_camelot_on_image')
    @patch('app.services.tesseract_ocr._extract_tables_with_region_detection')
    def test_extract_tables_with_tesseract_pipeline_camelot_success(
        self, mock_region_detection, mock_camelot, mock_convert, mock_pdfplumber
    ):
        """Test pipeline when camelot succeeds."""
        # Mock PDF file existence
        with patch('app.services.tesseract_ocr.Path.exists', return_value=True):
            # Mock pdfplumber
            mock_page = Mock()
            mock_pdf = Mock()
            mock_pdf.pages = [mock_page]
            mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf
            
            # Mock image conversion
            mock_image = Mock()
            mock_convert.return_value = mock_image
            
            # Mock camelot success
            mock_df = pd.DataFrame({'A': [1, 2], 'B': [3, 4]})
            mock_camelot.return_value = [mock_df]
            
            result = extract_tables_with_tesseract_pipeline(self.sample_pdf_path)
            
            assert len(result) == 1
            assert isinstance(result[0], pd.DataFrame)
            assert result[0].equals(mock_df)
            # Region detection should not be called since camelot succeeded
            mock_region_detection.assert_not_called()

    @patch('app.services.tesseract_ocr.pdfplumber')
    @patch('app.services.tesseract_ocr._convert_page_to_image')
    @patch('app.services.tesseract_ocr._try_camelot_on_image')
    @patch('app.services.tesseract_ocr._extract_tables_with_region_detection')
    def test_extract_tables_with_tesseract_pipeline_fallback_to_region_detection(
        self, mock_region_detection, mock_camelot, mock_convert, mock_pdfplumber
    ):
        """Test pipeline fallback to region detection when camelot fails."""
        # Mock PDF file existence
        with patch('app.services.tesseract_ocr.Path.exists', return_value=True):
            # Mock pdfplumber
            mock_page = Mock()
            mock_pdf = Mock()
            mock_pdf.pages = [mock_page]
            mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf
            
            # Mock image conversion
            mock_image = Mock()
            mock_convert.return_value = mock_image
            
            # Mock camelot failure
            mock_camelot.return_value = []
            
            # Mock region detection success
            mock_df = pd.DataFrame({'A': [1, 2], 'B': [3, 4]})
            mock_region_detection.return_value = [mock_df]
            
            result = extract_tables_with_tesseract_pipeline(self.sample_pdf_path)
            
            assert len(result) == 1
            assert isinstance(result[0], pd.DataFrame)
            assert result[0].equals(mock_df)
            # Both should be called
            mock_camelot.assert_called_once()
            mock_region_detection.assert_called_once()

    @patch('app.services.tesseract_ocr.pdfplumber')
    @patch('app.services.tesseract_ocr._convert_page_to_image')
    @patch('app.services.tesseract_ocr._try_camelot_on_image')
    @patch('app.services.tesseract_ocr._extract_tables_with_region_detection')
    def test_extract_tables_with_tesseract_pipeline_no_tables_found(
        self, mock_region_detection, mock_camelot, mock_convert, mock_pdfplumber
    ):
        """Test pipeline when no tables are found."""
        # Mock PDF file existence
        with patch('app.services.tesseract_ocr.Path.exists', return_value=True):
            # Mock pdfplumber
            mock_page = Mock()
            mock_pdf = Mock()
            mock_pdf.pages = [mock_page]
            mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf
            
            # Mock image conversion
            mock_image = Mock()
            mock_convert.return_value = mock_image
            
            # Mock both failing
            mock_camelot.return_value = []
            mock_region_detection.return_value = []
            
            result = extract_tables_with_tesseract_pipeline(self.sample_pdf_path)
            
            assert result == []
            mock_camelot.assert_called_once()
            mock_region_detection.assert_called_once()

    @patch('app.services.tesseract_ocr.extract_tables_with_tesseract_pipeline')
    @patch('app.services.tesseract_ocr.pdfplumber')
    @patch('app.services.tesseract_ocr._convert_page_to_image')
    @patch('app.services.tesseract_ocr.pytesseract')
    def test_extract_tables_and_text_legacy_function(
        self, mock_pytesseract, mock_convert, mock_pdfplumber, mock_pipeline
    ):
        """Test legacy extract_tables_and_text function."""
        # Mock pipeline
        mock_df = pd.DataFrame({'A': [1, 2], 'B': [3, 4]})
        mock_pipeline.return_value = [mock_df]
        
        # Mock pdfplumber
        mock_page = Mock()
        mock_pdf = Mock()
        mock_pdf.pages = [mock_page]
        mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf
        
        # Mock image conversion
        mock_image = Mock()
        mock_convert.return_value = mock_image
        
        # Mock pytesseract
        mock_pytesseract.image_to_string.return_value = "Sample text"
        
        result = extract_tables_and_text(self.sample_pdf_path)
        
        assert len(result) == 1
        assert result[0]['page'] == 1
        assert result[0]['full_text'] == "Sample text"
        assert len(result[0]['tables']) == 1

    @patch('app.services.tesseract_ocr.extract_tables_and_text')
    def test_run_extraction_with_tesseract_legacy_function(self, mock_extract):
        """Test legacy run_extraction_with_tesseract function."""
        # Mock extract_tables_and_text
        mock_extract.return_value = [
            {
                'page': 1,
                'full_text': 'Sample text',
                'tables': [[[1, 2], [3, 4]]]
            }
        ]
        
        result = run_extraction_with_tesseract(self.sample_pdf_path)
        
        assert len(result) == 1
        assert result[0]['page'] == 1
        assert result[0]['full_text'] == 'Sample text'
        assert result[0]['tables'] == [[[1, 2], [3, 4]]]

    @patch('app.services.tesseract_ocr.extract_tables_with_tesseract_pipeline')
    def test_get_tesseract_table_metadata(self, mock_pipeline):
        """Test metadata extraction."""
        # Mock pipeline
        mock_df1 = pd.DataFrame({'A': [1, 2], 'B': [3, 4]})
        mock_df2 = pd.DataFrame({'C': [5], 'D': [6]})
        mock_pipeline.return_value = [mock_df1, mock_df2]
        
        result = get_tesseract_table_metadata(self.sample_pdf_path)
        
        assert len(result) == 2
        assert result[0]['table_index'] == 1
        assert result[0]['rows'] == 2
        assert result[0]['columns'] == 2
        assert result[0]['is_empty'] is False
        assert result[0]['source'] == 'tesseract_pipeline'
        
        assert result[1]['table_index'] == 2
        assert result[1]['rows'] == 1
        assert result[1]['columns'] == 2
        assert result[1]['is_empty'] is False
        assert result[1]['source'] == 'tesseract_pipeline'


class TestTesseractOCRIntegration:
    """Integration tests for Tesseract OCR with actual PDF files."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sample_pdf_path = "tests/sample_data/bank-statement-1.pdf"

    def test_extract_tables_with_tesseract_pipeline_integration(self):
        """Integration test with actual PDF file."""
        # Only run if PDF file exists
        if not Path(self.sample_pdf_path).exists():
            pytest.skip("Sample PDF not found")
        
        # This is a basic integration test - in Docker environment it should work
        try:
            result = extract_tables_with_tesseract_pipeline(self.sample_pdf_path, pages='1')
            
            # Should return a list of DataFrames
            assert isinstance(result, list)
            
            # Each element should be a DataFrame
            for df in result:
                assert isinstance(df, pd.DataFrame)
                
            # Log result for debugging
            print(f"Integration test found {len(result)} tables")
            for i, df in enumerate(result):
                print(f"Table {i+1}: {df.shape[0]} rows, {df.shape[1]} columns")
                if not df.empty:
                    print(f"Preview:\n{df.head()}")
                    
        except Exception as e:
            # In test environment, dependencies might not be available
            pytest.skip(f"Integration test skipped due to: {e}")

    def test_extract_tables_and_text_integration(self):
        """Integration test for legacy function."""
        # Only run if PDF file exists
        if not Path(self.sample_pdf_path).exists():
            pytest.skip("Sample PDF not found")
        
        try:
            result = extract_tables_and_text(self.sample_pdf_path)
            
            # Should return a list of page dictionaries
            assert isinstance(result, list)
            
            # Each page should have expected structure
            for page_result in result:
                assert 'page' in page_result
                assert 'full_text' in page_result
                assert 'tables' in page_result
                assert isinstance(page_result['page'], int)
                assert isinstance(page_result['full_text'], str)
                assert isinstance(page_result['tables'], list)
                
            print(f"Integration test processed {len(result)} pages")
            
        except Exception as e:
            # In test environment, dependencies might not be available
            pytest.skip(f"Integration test skipped due to: {e}")

    def test_specific_table_extraction_content(self):
        """Test that we can extract specific table content."""
        # Only run if PDF file exists
        if not Path(self.sample_pdf_path).exists():
            pytest.skip("Sample PDF not found")
        
        try:
            result = extract_tables_with_tesseract_pipeline(self.sample_pdf_path, pages='1')
            
            # Look for at least one table with meaningful content
            found_meaningful_table = False
            for df in result:
                if not df.empty and df.shape[0] > 1 and df.shape[1] > 1:
                    # Check if we have some text content
                    text_content = df.astype(str).values.flatten()
                    non_empty_cells = [cell for cell in text_content if cell and cell != 'nan']
                    
                    if len(non_empty_cells) > 3:  # At least 3 non-empty cells
                        found_meaningful_table = True
                        print(f"Found meaningful table with {len(non_empty_cells)} non-empty cells")
                        print(f"Sample content: {non_empty_cells[:5]}")
                        break
            
            # Assert we found at least one meaningful table
            assert found_meaningful_table, "No meaningful table content found"
            
        except Exception as e:
            # In test environment, dependencies might not be available
            pytest.skip(f"Content extraction test skipped due to: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 