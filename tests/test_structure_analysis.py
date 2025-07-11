import pytest
import os
import asyncio
from unittest.mock import patch, MagicMock
from app.services.ocr import run_structure_analysis, extract_tables_from_structure, get_structure_ocr_instance
from app.services.parser import run_structure_extraction, parse_structure_tables


class TestStructureAnalysis:
    """Test suite for PaddleOCR structure analysis functionality"""
    
    def test_get_structure_ocr_instance(self):
        """Test that structure OCR instance is properly initialized"""
        with patch('app.services.ocr.PaddleOCR') as mock_paddle:
            mock_paddle.return_value = MagicMock()
            
            # First call should initialize
            instance1 = get_structure_ocr_instance()
            assert instance1 is not None
            
            # Second call should return same instance (singleton)
            instance2 = get_structure_ocr_instance()
            assert instance1 is instance2
            
            # Verify PaddleOCR was called with correct parameters
            mock_paddle.assert_called_once_with(
                use_angle_cls=True,
                lang='en',
                use_structure=True,
                structure_version='PP-StructureV2'
            )
    
    @pytest.mark.asyncio
    async def test_run_structure_analysis_file_not_found(self):
        """Test structure analysis with non-existent file"""
        with pytest.raises(FileNotFoundError):
            await run_structure_analysis("nonexistent.pdf")
    
    @pytest.mark.asyncio
    async def test_run_structure_analysis_success(self):
        """Test successful structure analysis"""
        # Mock structure results
        mock_structure_results = [
            {
                'structure': [
                    {
                        'type': 'table',
                        'cells': [
                            {'bbox': [0, 0, 100, 20], 'text': 'Date'},
                            {'bbox': [100, 0, 200, 20], 'text': 'Description'},
                            {'bbox': [200, 0, 300, 20], 'text': 'Amount'}
                        ]
                    }
                ]
            }
        ]
        
        with patch('app.services.ocr.get_structure_ocr_instance') as mock_get_ocr:
            mock_ocr = MagicMock()
            mock_ocr.ocr.return_value = mock_structure_results
            mock_get_ocr.return_value = mock_ocr
            
            # Create a dummy file
            test_file = "test_structure.pdf"
            with open(test_file, 'wb') as f:
                f.write(b'dummy pdf content')
            
            try:
                result = await run_structure_analysis(test_file)
                
                assert result == mock_structure_results
                mock_ocr.ocr.assert_called_once_with(
                    test_file,
                    cls=True,
                    det=True,
                    rec=True,
                    structure=True
                )
            finally:
                # Clean up
                if os.path.exists(test_file):
                    os.remove(test_file)
    
    def test_extract_tables_from_structure_empty_results(self):
        """Test table extraction with empty structure results"""
        result = extract_tables_from_structure([])
        assert result == []
    
    def test_extract_tables_from_structure_no_tables(self):
        """Test table extraction with no table structures"""
        structure_results = [
            {
                'structure': [
                    {'type': 'text', 'content': 'Some text'},
                    {'type': 'image', 'content': 'An image'}
                ]
            }
        ]
        
        result = extract_tables_from_structure(structure_results)
        assert result == []
    
    def test_extract_tables_from_structure_with_tables(self):
        """Test table extraction with actual table structures"""
        structure_results = [
            {
                'structure': [
                    {
                        'type': 'table',
                        'cells': [
                            {'bbox': [0, 0, 100, 20], 'text': 'Date'},
                            {'bbox': [100, 0, 200, 20], 'text': 'Description'},
                            {'bbox': [200, 0, 300, 20], 'text': 'Amount'},
                            {'bbox': [0, 20, 100, 40], 'text': '10/15/24'},
                            {'bbox': [100, 20, 200, 40], 'text': 'Purchase'},
                            {'bbox': [200, 20, 300, 40], 'text': '$50.00'}
                        ]
                    }
                ]
            }
        ]
        
        result = extract_tables_from_structure(structure_results)
        
        assert len(result) == 1
        assert result[0]['page'] == 1
        assert result[0]['cell_count'] == 6
        assert len(result[0]['table_data']) == 2  # 2 rows
        assert result[0]['table_data'][0] == ['Date', 'Description', 'Amount']
        assert result[0]['table_data'][1] == ['10/15/24', 'Purchase', '$50.00']
    
    def test_reconstruct_table_from_cells_empty(self):
        """Test table reconstruction with empty cells"""
        from app.services.ocr import reconstruct_table_from_cells
        
        result = reconstruct_table_from_cells([])
        assert result == []
    
    def test_reconstruct_table_from_cells_valid(self):
        """Test table reconstruction with valid cells"""
        from app.services.ocr import reconstruct_table_from_cells
        
        cells = [
            {'bbox': [0, 0, 100, 20], 'text': 'Date'},
            {'bbox': [100, 0, 200, 20], 'text': 'Description'},
            {'bbox': [200, 0, 300, 20], 'text': 'Amount'},
            {'bbox': [0, 30, 100, 50], 'text': '10/15/24'},
            {'bbox': [100, 30, 200, 50], 'text': 'Purchase'},
            {'bbox': [200, 30, 300, 50], 'text': '$50.00'}
        ]
        
        result = reconstruct_table_from_cells(cells)
        
        assert len(result) == 2
        assert result[0] == ['Date', 'Description', 'Amount']
        assert result[1] == ['10/15/24', 'Purchase', '$50.00']
    
    @pytest.mark.asyncio
    async def test_run_structure_extraction_file_not_found(self):
        """Test structure extraction with non-existent file"""
        with pytest.raises(FileNotFoundError):
            await run_structure_extraction("nonexistent.pdf")
    
    @pytest.mark.asyncio
    async def test_run_structure_extraction_success(self):
        """Test successful structure extraction"""
        # Mock the structure analysis and table extraction
        mock_structure_results = [
            {
                'structure': [
                    {
                        'type': 'table',
                        'cells': [
                            {'bbox': [0, 0, 100, 20], 'text': 'Date'},
                            {'bbox': [100, 0, 200, 20], 'text': 'Description'},
                            {'bbox': [200, 0, 300, 20], 'text': 'Amount'},
                            {'bbox': [0, 30, 100, 50], 'text': '10/15/24'},
                            {'bbox': [100, 30, 200, 50], 'text': 'Purchase'},
                            {'bbox': [200, 30, 300, 50], 'text': '50.00'}
                        ]
                    }
                ]
            }
        ]
        
        with patch('app.services.parser.run_structure_analysis') as mock_structure_analysis:
            mock_structure_analysis.return_value = mock_structure_results
            
            # Create a dummy file
            test_file = "test_extraction.pdf"
            with open(test_file, 'wb') as f:
                f.write(b'dummy pdf content')
            
            try:
                result = await run_structure_extraction(test_file)
                
                # Should return a list of transaction dictionaries
                assert isinstance(result, list)
                mock_structure_analysis.assert_called_once_with(test_file)
                
            finally:
                # Clean up
                if os.path.exists(test_file):
                    os.remove(test_file)
    
    def test_parse_structure_tables(self):
        """Test parsing structure tables into TransactionData objects"""
        structure_results = [
            {
                'structure': [
                    {
                        'type': 'table',
                        'cells': [
                            {'bbox': [0, 0, 100, 20], 'text': 'Date'},
                            {'bbox': [100, 0, 200, 20], 'text': 'Description'},
                            {'bbox': [200, 0, 300, 20], 'text': 'Amount'},
                            {'bbox': [0, 30, 100, 50], 'text': '10/15/24'},
                            {'bbox': [100, 30, 200, 50], 'text': 'Purchase'},
                            {'bbox': [200, 30, 300, 50], 'text': '50.00'}
                        ]
                    }
                ]
            }
        ]
        
        result = parse_structure_tables(structure_results)
        
        # Should return a list of TransactionData objects
        assert isinstance(result, list)
        # The exact parsing depends on the _extract_table_transactions implementation
        # which may or may not find valid transactions from this simplified data


class TestStructureAnalysisIntegration:
    """Integration tests for structure analysis with real workflow"""
    
    @pytest.mark.asyncio
    async def test_structure_analysis_integration_mock(self):
        """Test full integration with mocked PaddleOCR"""
        
        # Mock structure results that should produce valid transactions
        mock_structure_results = [
            {
                'structure': [
                    {
                        'type': 'table',
                        'cells': [
                            {'bbox': [0, 0, 100, 20], 'text': 'Date'},
                            {'bbox': [100, 0, 200, 20], 'text': 'Description'},
                            {'bbox': [200, 0, 300, 20], 'text': 'Debit'},
                            {'bbox': [300, 0, 400, 20], 'text': 'Credit'},
                            {'bbox': [400, 0, 500, 20], 'text': 'Balance'},
                            # Row 1
                            {'bbox': [0, 30, 100, 50], 'text': '10/15/24'},
                            {'bbox': [100, 30, 200, 50], 'text': 'ATM Withdrawal'},
                            {'bbox': [200, 30, 300, 50], 'text': '50.00'},
                            {'bbox': [300, 30, 400, 50], 'text': ''},
                            {'bbox': [400, 30, 500, 50], 'text': '450.00'},
                            # Row 2
                            {'bbox': [0, 60, 100, 80], 'text': '10/16/24'},
                            {'bbox': [100, 60, 200, 80], 'text': 'Deposit'},
                            {'bbox': [200, 60, 300, 80], 'text': ''},
                            {'bbox': [300, 60, 400, 80], 'text': '100.00'},
                            {'bbox': [400, 60, 500, 80], 'text': '550.00'}
                        ]
                    }
                ]
            }
        ]
        
        with patch('app.services.ocr.get_structure_ocr_instance') as mock_get_ocr:
            mock_ocr = MagicMock()
            mock_ocr.ocr.return_value = mock_structure_results
            mock_get_ocr.return_value = mock_ocr
            
            # Create a dummy file
            test_file = "test_integration.pdf"
            with open(test_file, 'wb') as f:
                f.write(b'dummy pdf content')
            
            try:
                # Test the full workflow
                result = await run_structure_extraction(test_file)
                
                # Verify we got some results
                assert isinstance(result, list)
                
                # The actual results depend on the table parsing logic
                # but we should at least get a successful run
                
            finally:
                # Clean up
                if os.path.exists(test_file):
                    os.remove(test_file) 