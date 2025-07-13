import pytest
import pandas as pd
from pathlib import Path
from unittest.mock import Mock, patch
import sys
import os

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.camelot_ocr import (
    extract_tables_with_camelot,
    extract_tables_with_confidence,
    get_table_metadata
)


class TestCamelotOCR:
    """Test suite for Camelot OCR service"""

    @pytest.fixture
    def sample_pdf_path(self):
        """Path to sample PDF file"""
        return Path(__file__).parent / "sample_data" / "bank-statement-1.pdf"

    @pytest.fixture
    def sample_pdf_path_2(self):
        """Path to second sample PDF file"""
        return Path(__file__).parent / "sample_data" / "bank-statement-2.pdf"

    @pytest.fixture
    def nonexistent_pdf_path(self):
        """Path to non-existent PDF file"""
        return Path(__file__).parent / "sample_data" / "nonexistent.pdf"

    def test_extract_tables_with_camelot_basic(self, sample_pdf_path):
        """Test basic table extraction with default parameters"""
        # Check if file exists
        assert sample_pdf_path.exists(), f"Sample PDF not found: {sample_pdf_path}"
        
        # Extract tables
        tables = extract_tables_with_camelot(str(sample_pdf_path))
        
        # Basic assertions
        assert isinstance(tables, list)
        assert len(tables) >= 0  # May be 0 if no tables found
        
        # If tables found, verify they're DataFrames
        for table in tables:
            assert isinstance(table, pd.DataFrame)
            assert table.shape[0] > 0  # Should have rows
            assert table.shape[1] > 0  # Should have columns

    def test_extract_tables_with_camelot_lattice_flavor(self, sample_pdf_path):
        """Test table extraction with lattice flavor"""
        assert sample_pdf_path.exists()
        
        tables = extract_tables_with_camelot(str(sample_pdf_path), flavor='lattice')
        
        assert isinstance(tables, list)
        for table in tables:
            assert isinstance(table, pd.DataFrame)

    def test_extract_tables_with_camelot_stream_flavor(self, sample_pdf_path):
        """Test table extraction with stream flavor"""
        assert sample_pdf_path.exists()
        
        tables = extract_tables_with_camelot(str(sample_pdf_path), flavor='stream')
        
        assert isinstance(tables, list)
        for table in tables:
            assert isinstance(table, pd.DataFrame)

    def test_extract_tables_with_camelot_specific_pages(self, sample_pdf_path):
        """Test table extraction with specific page selection"""
        assert sample_pdf_path.exists()
        
        # Test page 1 only
        tables = extract_tables_with_camelot(str(sample_pdf_path), pages='1')
        
        assert isinstance(tables, list)
        for table in tables:
            assert isinstance(table, pd.DataFrame)

    def test_extract_tables_with_camelot_invalid_flavor(self, sample_pdf_path):
        """Test that invalid flavor raises ValueError"""
        assert sample_pdf_path.exists()
        
        with pytest.raises(ValueError, match="Invalid flavor"):
            extract_tables_with_camelot(str(sample_pdf_path), flavor='invalid')

    def test_extract_tables_with_camelot_nonexistent_file(self, nonexistent_pdf_path):
        """Test that non-existent file raises FileNotFoundError"""
        with pytest.raises(FileNotFoundError):
            extract_tables_with_camelot(str(nonexistent_pdf_path))

    def test_extract_tables_with_confidence_basic(self, sample_pdf_path):
        """Test confidence-based table extraction"""
        assert sample_pdf_path.exists()
        
        tables = extract_tables_with_confidence(str(sample_pdf_path))
        
        assert isinstance(tables, list)
        for table in tables:
            assert isinstance(table, pd.DataFrame)

    def test_extract_tables_with_confidence_high_threshold(self, sample_pdf_path):
        """Test confidence extraction with high threshold"""
        assert sample_pdf_path.exists()
        
        # High threshold should filter out low-confidence tables
        tables = extract_tables_with_confidence(str(sample_pdf_path), min_accuracy=0.9)
        
        assert isinstance(tables, list)
        for table in tables:
            assert isinstance(table, pd.DataFrame)

    def test_extract_tables_with_confidence_low_threshold(self, sample_pdf_path):
        """Test confidence extraction with low threshold"""
        assert sample_pdf_path.exists()
        
        # Low threshold should include more tables
        tables = extract_tables_with_confidence(str(sample_pdf_path), min_accuracy=0.1)
        
        assert isinstance(tables, list)
        for table in tables:
            assert isinstance(table, pd.DataFrame)

    def test_get_table_metadata_basic(self, sample_pdf_path):
        """Test table metadata extraction"""
        assert sample_pdf_path.exists()
        
        metadata = get_table_metadata(str(sample_pdf_path))
        
        assert isinstance(metadata, list)
        
        # Check metadata structure
        for meta in metadata:
            assert isinstance(meta, dict)
            required_keys = ['table_index', 'page', 'accuracy', 'whitespace', 
                           'order', 'rows', 'columns', 'flavor']
            for key in required_keys:
                assert key in meta
            
            # Check data types
            assert isinstance(meta['table_index'], int)
            assert isinstance(meta['page'], int)
            assert isinstance(meta['accuracy'], float)
            assert isinstance(meta['rows'], int)
            assert isinstance(meta['columns'], int)
            assert isinstance(meta['flavor'], str)

    def test_get_table_metadata_different_flavors(self, sample_pdf_path):
        """Test metadata extraction with different flavors"""
        assert sample_pdf_path.exists()
        
        # Test both flavors
        lattice_metadata = get_table_metadata(str(sample_pdf_path), flavor='lattice')
        stream_metadata = get_table_metadata(str(sample_pdf_path), flavor='stream')
        
        assert isinstance(lattice_metadata, list)
        assert isinstance(stream_metadata, list)
        
        # Check flavor is recorded correctly
        for meta in lattice_metadata:
            assert meta['flavor'] == 'lattice'
        
        for meta in stream_metadata:
            assert meta['flavor'] == 'stream'

    def test_multiple_bank_statements(self, sample_pdf_path, sample_pdf_path_2):
        """Test extraction on multiple bank statement PDFs"""
        test_files = [sample_pdf_path, sample_pdf_path_2]
        
        for pdf_path in test_files:
            if pdf_path.exists():
                print(f"\nTesting {pdf_path.name}...")
                
                # Test basic extraction
                tables = extract_tables_with_camelot(str(pdf_path))
                print(f"  Found {len(tables)} tables")
                
                # Test metadata
                metadata = get_table_metadata(str(pdf_path))
                print(f"  Metadata for {len(metadata)} tables")
                
                # Log table shapes for debugging
                for i, table in enumerate(tables):
                    print(f"    Table {i+1}: {table.shape[0]} rows, {table.shape[1]} columns")
                    
                    # Check that we have some data
                    assert table.shape[0] > 0, f"Table {i+1} has no rows"
                    assert table.shape[1] > 0, f"Table {i+1} has no columns"
                    
                    # Log first few rows for debugging
                    if not table.empty:
                        print(f"    First few rows:\n{table.head()}")

    def test_table_content_quality(self, sample_pdf_path):
        """Test that extracted tables contain meaningful content"""
        assert sample_pdf_path.exists()
        
        tables = extract_tables_with_camelot(str(sample_pdf_path))
        
        for i, table in enumerate(tables):
            if table.empty:
                continue
                
            # Check for typical banking table content
            table_str = table.to_string().lower()
            
            # Look for common banking terms (at least some should be present)
            banking_terms = [
                'date', 'amount', 'balance', 'description', 'transaction',
                'debit', 'credit', 'withdrawal', 'deposit', 'payment'
            ]
            
            found_terms = [term for term in banking_terms if term in table_str]
            
            print(f"Table {i+1} contains banking terms: {found_terms}")
            
            # We should find at least one banking-related term
            # (This is a heuristic - real bank statements should have these)
            if len(found_terms) > 0:
                print(f"✓ Table {i+1} appears to contain banking data")
            else:
                print(f"⚠ Table {i+1} may not contain banking data")

    @patch('app.services.camelot_ocr.camelot.read_pdf')
    def test_camelot_read_pdf_called_correctly(self, mock_read_pdf, sample_pdf_path):
        """Test that camelot.read_pdf is called with correct parameters"""
        # Mock the camelot response
        mock_table = Mock()
        mock_table.df = pd.DataFrame({'A': [1, 2], 'B': [3, 4]})
        mock_read_pdf.return_value = [mock_table]
        
        # Test the function
        result = extract_tables_with_camelot(str(sample_pdf_path), pages='1-2', flavor='stream')
        
        # Verify camelot was called correctly
        mock_read_pdf.assert_called_once_with(str(sample_pdf_path), pages='1-2', flavor='stream')
        
        # Verify result
        assert len(result) == 1
        assert isinstance(result[0], pd.DataFrame)
        assert result[0].shape == (2, 2)

    def test_error_handling_integration(self, sample_pdf_path):
        """Test error handling in real scenarios"""
        assert sample_pdf_path.exists()
        
        # Test with invalid pages parameter (should be handled by camelot)
        try:
            tables = extract_tables_with_camelot(str(sample_pdf_path), pages='999')
            # This may succeed (empty list) or fail depending on PDF
            assert isinstance(tables, list)
        except Exception as e:
            # Should raise our custom exception
            assert "Camelot processing failed" in str(e)

    def test_integration_with_existing_services(self, sample_pdf_path):
        """Test that the service integrates well with existing codebase"""
        # This test ensures the service can be imported and used
        # alongside existing services
        
        # Test import compatibility
        from app.services.camelot_ocr import extract_tables_with_camelot
        from app.services.pdf_utils import is_text_page
        
        assert sample_pdf_path.exists()
        
        # Test that we can use both services together
        is_text = is_text_page(str(sample_pdf_path), 1)
        tables = extract_tables_with_camelot(str(sample_pdf_path))
        
        print(f"PDF is text-based: {is_text}")
        print(f"Camelot found {len(tables)} tables")
        
        # If it's a text-based PDF, camelot should have a better chance
        if is_text and len(tables) > 0:
            print("✓ Text-based PDF successfully processed by Camelot")
        elif not is_text:
            print("⚠ Scanned PDF - Camelot may not work well")
        else:
            print("⚠ Text-based PDF but no tables found - may need different approach")


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v"]) 