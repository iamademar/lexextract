import pytest
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.ocr import run_ocr


@pytest.mark.asyncio
async def test_run_ocr_stub():
    """Test that the OCR stub returns expected format"""
    # Call the OCR function with a dummy file path
    result = await run_ocr("dummy.pdf")
    
    # Assert it returns a list
    assert isinstance(result, list)
    
    # Assert it returns exactly two strings
    assert len(result) == 2
    
    # Assert the returned strings match expected values
    assert result[0] == "PAGE1_TEXT"
    assert result[1] == "PAGE2_TEXT"


@pytest.mark.asyncio
async def test_run_ocr_stub_with_different_path():
    """Test that the OCR stub works with different file paths"""
    # Call the OCR function with a different dummy file path
    result = await run_ocr("another_dummy.pdf")
    
    # Assert it still returns the same stub data
    assert isinstance(result, list)
    assert len(result) == 2
    assert result == ["PAGE1_TEXT", "PAGE2_TEXT"] 