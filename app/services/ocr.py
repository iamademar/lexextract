import os
import logging
from typing import List, Dict, Any
from pathlib import Path
import pdfplumber
import pytesseract
from PIL import Image

# Import our new unified pipeline components
from .pdf_utils import is_text_page, is_scanned_page
from .camelot_ocr import extract_tables_with_camelot
from .tesseract_ocr import extract_tables_with_tesseract_pipeline

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_ocr(file_path: str) -> List[str]:
    """
    Extract text from PDF using unified OCR pipeline (Camelot + Tesseract).
    
    Args:
        file_path: Path to the PDF file to process
        
    Returns:
        List of strings, one for each page of the PDF
        
    Raises:
        FileNotFoundError: If the PDF file doesn't exist
        Exception: If OCR processing fails
    """
    try:
        # Check if file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF file not found: {file_path}")
        
        logger.info(f"Starting unified OCR processing for: {file_path}")
        
        # Use unified extraction pipeline
        page_results = run_unified_ocr_pipeline(file_path)
        
        # Extract just the full text from each page
        page_texts = []
        for page_result in page_results:
            full_text = page_result.get('full_text', '')
            page_texts.append(full_text.strip())
            logger.info(f"Processed page {page_result['page']}, extracted {len(full_text)} characters")
        
        logger.info(f"Unified OCR processing completed. Extracted text from {len(page_texts)} pages")
        return page_texts
        
    except FileNotFoundError as e:
        logger.error(f"OCR processing failed for {file_path}: {e}")
        raise e  # Re-raise the original FileNotFoundError
    except Exception as e:
        logger.error(f"OCR processing failed for {file_path}: {e}")
        raise Exception(f"OCR processing failed: {str(e)}")


async def run_structure_analysis(file_path: str) -> List[Dict[str, Any]]:
    """
    Extract structured data from PDF using unified pipeline (Camelot + Tesseract).
    
    Args:
        file_path: Path to the PDF file to process
        
    Returns:
        List of structure analysis results, one for each page
    """
    try:
        # Check if file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF file not found: {file_path}")
        
        logger.info(f"Starting unified structure analysis for: {file_path}")
        
        # Use unified extraction pipeline
        page_results = run_unified_ocr_pipeline(file_path)
        
        # Convert to expected format
        formatted_results = []
        for page_result in page_results:
            formatted_results.append({
                'page': page_result['page'],
                'structure': {
                    'table': page_result['tables']  # Tables as list of rows
                } if page_result['tables'] else []
            })
        
        logger.info(f"Unified structure analysis completed. Processed {len(formatted_results)} pages")
        return formatted_results
        
    except FileNotFoundError as e:
        logger.error(f"Structure analysis failed for {file_path}: {e}")
        raise e
    except Exception as e:
        logger.error(f"Structure analysis failed for {file_path}: {e}")
        raise Exception(f"Structure analysis failed: {str(e)}")


def run_unified_ocr_pipeline(pdf_path: str) -> List[Dict[str, Any]]:
    """
    Unified OCR pipeline that intelligently routes to Camelot or Tesseract based on page type.
    
    Args:
        pdf_path: Path to the PDF file to process
        
    Returns:
        List of dictionaries with 'page', 'tables', and 'full_text' keys
    """
    try:
        logger.info(f"Starting unified OCR pipeline for: {pdf_path}")
        
        results = []
        
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            logger.info(f"Processing {total_pages} pages")
            
            for page_no in range(1, total_pages + 1):
                logger.info(f"Processing page {page_no}/{total_pages}")
                
                # Determine if this is a text page or scanned page
                try:
                    is_text = is_text_page(pdf_path, page_no)
                    page_type = "text" if is_text else "scanned"
                    logger.info(f"Page {page_no} detected as: {page_type}")
                except Exception as e:
                    logger.warning(f"Failed to detect page type for page {page_no}: {e}")
                    is_text = False  # Default to scanned if detection fails
                    page_type = "scanned (fallback)"
                
                tables = []
                extraction_method = ""
                
                if is_text:
                    # Use Camelot for vector-based PDFs
                    try:
                        logger.info(f"Using Camelot extraction for page {page_no}")
                        camelot_tables = extract_tables_with_camelot(pdf_path, pages=str(page_no))
                        
                        # Convert DataFrames to list of lists
                        for df in camelot_tables:
                            if not df.empty:
                                table_as_lists = df.values.tolist()
                                tables.append(table_as_lists)
                        
                        extraction_method = "camelot"
                        logger.info(f"Camelot extracted {len(tables)} tables from page {page_no}")
                        
                    except Exception as e:
                        logger.warning(f"Camelot extraction failed for page {page_no}: {e}")
                        logger.info(f"Falling back to Tesseract for page {page_no}")
                        # Fallback to Tesseract
                        is_text = False
                
                if not is_text:
                    # Use Tesseract for scanned PDFs
                    try:
                        logger.info(f"Using Tesseract extraction for page {page_no}")
                        tesseract_tables = extract_tables_with_tesseract_pipeline(pdf_path, pages=str(page_no))
                        
                        # Convert DataFrames to list of lists
                        for df in tesseract_tables:
                            if not df.empty:
                                table_as_lists = df.values.tolist()
                                tables.append(table_as_lists)
                        
                        extraction_method = "tesseract"
                        logger.info(f"Tesseract extracted {len(tables)} tables from page {page_no}")
                        
                    except Exception as e:
                        logger.error(f"Tesseract extraction failed for page {page_no}: {e}")
                        # Continue with empty tables
                        extraction_method = "failed"
                
                # Extract full text from the page
                full_text = ""
                try:
                    if is_text:
                        # For text pages, use pdfplumber
                        page = pdf.pages[page_no - 1]
                        full_text = page.extract_text() or ""
                        logger.debug(f"Extracted {len(full_text)} characters using pdfplumber")
                    else:
                        # For scanned pages, use Tesseract OCR
                        page = pdf.pages[page_no - 1]
                        page_image = page.to_image(resolution=300)
                        full_text = pytesseract.image_to_string(page_image.original, lang="eng")
                        logger.debug(f"Extracted {len(full_text)} characters using Tesseract")
                        
                except Exception as e:
                    logger.error(f"Full text extraction failed for page {page_no}: {e}")
                    full_text = ""
                
                # Add page results
                page_result = {
                    "page": page_no,
                    "tables": tables,
                    "full_text": full_text.strip(),
                    "page_type": page_type,
                    "extraction_method": extraction_method
                }
                
                results.append(page_result)
                logger.info(f"Page {page_no} completed: {len(tables)} tables, {len(full_text)} characters")
        
        logger.info(f"Unified OCR pipeline completed. Processed {len(results)} pages")
        return results
        
    except Exception as e:
        logger.error(f"Unified OCR pipeline failed for {pdf_path}: {e}")
        raise Exception(f"Unified OCR pipeline failed: {str(e)}")


def extract_tables_from_structure(structure_results: List[Dict]) -> List[Dict[str, Any]]:
    """
    Extract table data from unified structure results.
    
    Args:
        structure_results: Structure analysis results from unified pipeline
        
    Returns:
        List of table dictionaries with reconstructed rows/columns
    """
    all_tables = []
    
    logger.info("=" * 80)
    logger.info("🔍 STARTING TABLE EXTRACTION FROM UNIFIED RESULTS")
    logger.info("=" * 80)
    
    for page_num, page_result in enumerate(structure_results):
        if not page_result or 'structure' not in page_result:
            logger.warning(f"No structure data found for page {page_num + 1}")
            continue
            
        page_tables = []
        structure_data = page_result['structure']
        
        # Unified pipeline returns results with "table" key containing processed rows
        if isinstance(structure_data, dict) and 'table' in structure_data:
            # Direct table data from unified pipeline
            table_data = structure_data['table']
            
            # LOG THE EXTRACTED TABLE - MAKE IT OBVIOUS
            logger.info("🟢" * 50)
            logger.info(f"📊 TABLE FOUND ON PAGE {page_num + 1}")
            logger.info(f"📊 Table type: {type(table_data)}")
            logger.info("🟢" * 50)
            
            if table_data:
                page_tables.append({
                    'page': page_num + 1,
                    'table_data': table_data,
                    'source': 'unified_pipeline'
                })
                
                # Print the actual table structure
                logger.info("📋 TABLE CONTENT:")
                if isinstance(table_data, list):
                    for row_idx, row in enumerate(table_data):
                        if isinstance(row, list):
                            row_text = " | ".join([f"{str(cell):>15}" for cell in row])
                            logger.info(f"Row {row_idx + 1:2d}: {row_text}")
                        else:
                            logger.info(f"Row {row_idx + 1:2d}: {row}")
                else:
                    logger.info(f"Table data: {table_data}")
                
                logger.info("🟢" * 50)
        
        # Check if structure_data is a list (fallback format)
        elif isinstance(structure_data, list):
            for result_idx, result in enumerate(structure_data):
                logger.info(f"Processing result {result_idx}: {type(result)}")
                
                # Check if this result has table data
                if isinstance(result, dict) and 'table' in result:
                    table_data = result['table']
                    
                    logger.info("🟢" * 50)
                    logger.info(f"📊 TABLE FOUND ON PAGE {page_num + 1}, RESULT {result_idx}")
                    logger.info(f"📊 Table has data: {bool(table_data)}")
                    logger.info("🟢" * 50)
                    
                    if table_data:
                        page_tables.append({
                            'page': page_num + 1,
                            'table_data': table_data,
                            'source': 'unified_pipeline'
                        })
                        
                        # Print the actual table structure
                        logger.info("📋 TABLE CONTENT:")
                        if isinstance(table_data, list):
                            for row_idx, row in enumerate(table_data):
                                if isinstance(row, list):
                                    row_text = " | ".join([f"{str(cell):>15}" for cell in row])
                                    logger.info(f"Row {row_idx + 1:2d}: {row_text}")
                                else:
                                    logger.info(f"Row {row_idx + 1:2d}: {row}")
                        else:
                            logger.info(f"Table data: {table_data}")
                        
                        logger.info("🟢" * 50)
                else:
                    logger.info(f"Result {result_idx} has no table data: {result}")
        else:
            logger.warning(f"Unexpected structure_data format: {type(structure_data)}")
        
        if page_tables:
            logger.info(f"✅ Found {len(page_tables)} tables on page {page_num + 1}")
        else:
            logger.info(f"❌ No tables found on page {page_num + 1}")
        all_tables.extend(page_tables)
    
    logger.info("=" * 80)
    logger.info(f"🎯 TOTAL TABLES EXTRACTED: {len(all_tables)}")
    logger.info("=" * 80)
    
    return all_tables

 