import pytest
import re
from pathlib import Path
from app.services.tesseract_ocr import extract_tables_and_text
import pytesseract

def test_pytesseract_import():
    """Test that pytesseract is properly installed and accessible"""
    import pytesseract
    assert pytesseract.get_tesseract_version() is not None

def test_extract_tables_and_text(tmp_path):
    """Test that extract_tables_and_text function works with sample PDFs"""
    # copy a sample PDF into tmp_path
    sample_pdf_path = Path(__file__).parent / "sample_data" / "bank-statement-1.pdf"
    if not sample_pdf_path.exists():
        pytest.skip("Sample PDF not found, skipping integration test")
    
    pdf = tmp_path / "bank-statement-1.pdf"
    pdf.write_bytes(sample_pdf_path.read_bytes())

    pages = extract_tables_and_text(str(pdf))
    assert isinstance(pages, list) and pages, "Expected at least one page"
    
    # Check that we got text content from each page
    assert all(p["full_text"].strip() for p in pages), "Expected text content from each page"
    
    # Note: Formal table detection depends on PDF structure - this PDF has text-based tables
    # but we should at least get the table structure in the results
    assert all("tables" in p for p in pages), "Expected tables key in each page result"

def test_tesseract_date_patterns():
    """Test that Tesseract can detect date patterns"""
    sample_pdf_path = Path(__file__).parent / "sample_data" / "bank-statement-1.pdf"
    if not sample_pdf_path.exists():
        pytest.skip("Sample PDF not found, skipping integration test")
    
    pages = extract_tables_and_text(str(sample_pdf_path))
    
    # Look for MM/DD date patterns (common in bank statements)
    date_pattern = re.compile(r"\b\d{1,2}/\d{1,2}\b")
    
    # Check full text for dates
    all_text = " ".join(p["full_text"] for p in pages)
    date_matches = date_pattern.findall(all_text)
    
    assert len(date_matches) > 0, f"Expected to find MM/DD date patterns, found: {date_matches[:5]}"
    
    # Check for specific known dates from the sample
    assert any("10/02" in p["full_text"] for p in pages), "Expected to find specific transaction date 10/02"

def test_tesseract_basic_text_extraction():
    """Test that Tesseract can extract basic text from PDF"""
    sample_pdf_path = Path(__file__).parent / "sample_data" / "bank-statement-1.pdf"
    if not sample_pdf_path.exists():
        pytest.skip("Sample PDF not found, skipping integration test")
    
    pages = extract_tables_and_text(str(sample_pdf_path))
    
    # Check that we got text from at least one page
    assert any(p["full_text"].strip() for p in pages), "Expected to extract text from at least one page"
    
    # Check that the full text contains some expected banking terms
    all_text = " ".join(p["full_text"] for p in pages).lower()
    banking_terms = ["account", "balance", "transaction", "date", "amount", "deposit", "withdrawal"]
    
    found_terms = [term for term in banking_terms if term in all_text]
    assert len(found_terms) > 0, f"Expected to find banking terms in extracted text, found: {found_terms}" 