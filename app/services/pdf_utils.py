import logging
import pdfplumber
from typing import Union
from pathlib import Path

logger = logging.getLogger(__name__)


def is_text_page(pdf_path: Union[str, Path], page_no: int) -> bool:
    """
    Determine if a PDF page contains extractable text (vector-based).
    
    Args:
        pdf_path: Path to the PDF file
        page_no: Page number (1-indexed)
        
    Returns:
        True if page contains extractable text, False otherwise
        
    Raises:
        FileNotFoundError: If PDF file doesn't exist
        ValueError: If page number is invalid
        Exception: If PDF processing fails
    """
    try:
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        with pdfplumber.open(pdf_path) as pdf:
            # Convert to 0-indexed
            page_index = page_no - 1
            
            # Check if page number is valid
            if page_index < 0 or page_index >= len(pdf.pages):
                raise ValueError(f"Invalid page number {page_no}. PDF has {len(pdf.pages)} pages.")
            
            page = pdf.pages[page_index]
            
            # Extract text from the page
            text = page.extract_text()
            
            # Check if we have any meaningful text
            if text is None:
                logger.debug(f"Page {page_no} has no extractable text")
                return False
            
            # Strip whitespace and check if there's actual content
            text = text.strip()
            
            if not text:
                logger.debug(f"Page {page_no} has only whitespace")
                return False
            
            # Check if text has meaningful content (not just formatting characters)
            meaningful_chars = len([c for c in text if c.isalnum()])
            
            if meaningful_chars == 0:
                logger.debug(f"Page {page_no} has no alphanumeric characters")
                return False
            
            logger.debug(f"Page {page_no} contains {meaningful_chars} meaningful characters")
            return True
            
    except FileNotFoundError:
        raise
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Error processing PDF {pdf_path}, page {page_no}: {e}")
        raise Exception(f"PDF processing failed: {str(e)}")


def is_scanned_page(pdf_path: Union[str, Path], page_no: int) -> bool:
    """
    Determine if a PDF page is scanned (image-based, no extractable text).
    
    This is simply the inverse of is_text_page().
    
    Args:
        pdf_path: Path to the PDF file
        page_no: Page number (1-indexed)
        
    Returns:
        True if page is scanned (no extractable text), False otherwise
        
    Raises:
        FileNotFoundError: If PDF file doesn't exist
        ValueError: If page number is invalid
        Exception: If PDF processing fails
    """
    return not is_text_page(pdf_path, page_no) 