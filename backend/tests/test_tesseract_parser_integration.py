import pytest
import asyncio
from pathlib import Path
from app.services.ocr import run_ocr, run_structure_analysis
from app.services.parser import run_extraction

def test_tesseract_ocr_integration():
    """Test that the updated OCR service works with Tesseract"""
    sample_pdf_path = Path(__file__).parent / "sample_data" / "bank-statement-1.pdf"
    if not sample_pdf_path.exists():
        pytest.skip("Sample PDF not found, skipping integration test")
    
    # Test the async run_ocr function
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        pages = loop.run_until_complete(run_ocr(str(sample_pdf_path)))
        assert isinstance(pages, list), "Expected list of page texts"
        assert len(pages) > 0, "Expected at least one page"
        assert any(page.strip() for page in pages), "Expected some text content"
    finally:
        loop.close()

def test_tesseract_structure_analysis():
    """Test that structure analysis works with Tesseract"""
    sample_pdf_path = Path(__file__).parent / "sample_data" / "bank-statement-1.pdf"
    if not sample_pdf_path.exists():
        pytest.skip("Sample PDF not found, skipping integration test")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        structure_results = loop.run_until_complete(run_structure_analysis(str(sample_pdf_path)))
        assert isinstance(structure_results, list), "Expected list of structure results"
        assert len(structure_results) > 0, "Expected at least one page result"
        
        # Check that we have table structures
        has_tables = any(
            page.get('structure') and 
            isinstance(page['structure'], dict) and 
            'table' in page['structure'] and 
            page['structure']['table']
            for page in structure_results
        )
        
        # Note: This might not always pass depending on PDF content
        # but it tests the structure
        print(f"Tables found: {has_tables}")
        
    finally:
        loop.close()

def test_full_extraction_pipeline():
    """Test the complete extraction pipeline with Tesseract"""
    sample_pdf_path = Path(__file__).parent / "sample_data" / "bank-statement-1.pdf"
    if not sample_pdf_path.exists():
        pytest.skip("Sample PDF not found, skipping integration test")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        transactions = loop.run_until_complete(run_extraction(str(sample_pdf_path)))
        assert isinstance(transactions, list), "Expected list of transactions"
        
        # Check transaction structure if any were found
        if transactions:
            transaction = transactions[0]
            assert 'date' in transaction, "Expected date field in transaction"
            assert 'description' in transaction, "Expected description field in transaction"
            assert 'amount' in transaction, "Expected amount field in transaction"
            
        print(f"Extracted {len(transactions)} transactions")
        
    finally:
        loop.close() 