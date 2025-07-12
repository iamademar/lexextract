import pdfplumber
import pandas as pd
import numpy as np
from PIL import Image
import pytesseract
import camelot
import tempfile
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


def extract_tables_with_tesseract_pipeline(pdf_path: str, pages: str = 'all', 
                                          min_confidence: float = 60.0,
                                          edge_tol: int = 200) -> List[pd.DataFrame]:
    """
    Extract tables from scanned PDFs using a comprehensive image-based pipeline.
    
    For each page:
    1. Convert PDF page to PNG image
    2. Try camelot.read_pdf on the PNG with lattice flavor
    3. If no tables found, detect table regions and OCR each crop with pytesseract
    4. Return same structure as camelot (List of DataFrames)
    
    Args:
        pdf_path: Path to the PDF file to process
        pages: Pages to process (e.g., 'all', '1', '1-3', '1,2,3')
        min_confidence: Minimum OCR confidence threshold (0-100)
        edge_tol: Edge tolerance for camelot lattice detection
        
    Returns:
        List of pandas DataFrames, one for each detected table
        
    Raises:
        FileNotFoundError: If PDF file doesn't exist
        Exception: If processing fails
    """
    try:
        pdf_file = Path(pdf_path)
        if not pdf_file.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        logger.info(f"Starting Tesseract pipeline for scanned PDF: {pdf_path}")
        logger.info(f"Pages: {pages}, Min confidence: {min_confidence}, Edge tolerance: {edge_tol}")
        
        all_dataframes = []
        
        with pdfplumber.open(pdf_path) as pdf:
            # Determine which pages to process
            if pages == 'all':
                page_numbers = list(range(len(pdf.pages)))
            else:
                page_numbers = _parse_page_specification(pages, len(pdf.pages))
            
            logger.info(f"Processing {len(page_numbers)} pages")
            
            for page_idx in page_numbers:
                page = pdf.pages[page_idx]
                page_num = page_idx + 1
                
                logger.info(f"Processing page {page_num}")
                
                # Convert page to PNG image
                page_image = _convert_page_to_image(page, resolution=300)
                
                # Try camelot on the image first
                camelot_tables = _try_camelot_on_image(page_image, page_num, edge_tol)
                
                if camelot_tables:
                    logger.info(f"Camelot found {len(camelot_tables)} tables on page {page_num}")
                    all_dataframes.extend(camelot_tables)
                else:
                    # Fallback to table region detection + pytesseract OCR
                    logger.info(f"Camelot found no tables on page {page_num}, falling back to region detection")
                    tesseract_tables = _extract_tables_with_region_detection(
                        page, page_image, page_num, min_confidence
                    )
                    
                    if tesseract_tables:
                        logger.info(f"Region detection found {len(tesseract_tables)} tables on page {page_num}")
                        all_dataframes.extend(tesseract_tables)
                    else:
                        logger.info(f"No tables found on page {page_num}")
        
        logger.info(f"Total tables extracted: {len(all_dataframes)}")
        return all_dataframes
        
    except FileNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Tesseract pipeline failed for {pdf_path}: {e}")
        raise Exception(f"Tesseract pipeline failed: {str(e)}")


def _parse_page_specification(pages: str, total_pages: int) -> List[int]:
    """
    Parse page specification string into list of 0-indexed page numbers.
    
    Args:
        pages: Page specification (e.g., '1', '1-3', '1,2,3')
        total_pages: Total number of pages in PDF
        
    Returns:
        List of 0-indexed page numbers
    """
    page_numbers = []
    
    for part in pages.split(','):
        part = part.strip()
        if '-' in part:
            start, end = part.split('-')
            start_idx = int(start) - 1  # Convert to 0-indexed
            end_idx = int(end) - 1
            page_numbers.extend(range(start_idx, end_idx + 1))
        else:
            page_numbers.append(int(part) - 1)  # Convert to 0-indexed
    
    # Filter out invalid page numbers
    valid_pages = [p for p in page_numbers if 0 <= p < total_pages]
    
    return valid_pages


def _convert_page_to_image(page, resolution: int = 300) -> Image.Image:
    """
    Convert a pdfplumber page to PIL Image.
    
    Args:
        page: pdfplumber page object
        resolution: DPI for image conversion
        
    Returns:
        PIL Image object
    """
    try:
        # Use pdfplumber's to_image method
        page_image = page.to_image(resolution=resolution)
        return page_image.original
    except Exception as e:
        logger.error(f"Failed to convert page to image: {e}")
        raise


def _try_camelot_on_image(page_image: Image.Image, page_num: int, edge_tol: int) -> List[pd.DataFrame]:
    """
    Try to extract tables using camelot on the converted image.
    
    Args:
        page_image: PIL Image of the page
        page_num: Page number for logging
        edge_tol: Edge tolerance for camelot lattice detection
        
    Returns:
        List of DataFrames if successful, empty list if no tables found
    """
    try:
        # Save image to temporary file for camelot processing
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
            temp_image_path = tmp_file.name
            page_image.save(temp_image_path, format='PNG')
        
        try:
            # Try camelot lattice on the image
            logger.debug(f"Trying camelot lattice on page {page_num} image")
            tables = camelot.read_pdf(temp_image_path, pages='1', flavor='lattice', edge_tol=edge_tol)
            
            if len(tables) > 0:
                logger.info(f"Camelot extracted {len(tables)} tables from page {page_num}")
                dataframes = []
                for i, table in enumerate(tables):
                    df = table.df
                    if not df.empty:
                        logger.info(f"Table {i+1}: {df.shape[0]} rows, {df.shape[1]} columns")
                        dataframes.append(df)
                
                return dataframes
            else:
                logger.debug(f"Camelot found no tables on page {page_num}")
                return []
                
        finally:
            # Clean up temporary file
            if os.path.exists(temp_image_path):
                os.unlink(temp_image_path)
    
    except Exception as e:
        logger.debug(f"Camelot processing failed on page {page_num}: {e}")
        return []


def _extract_tables_with_region_detection(page, page_image: Image.Image, page_num: int, 
                                         min_confidence: float) -> List[pd.DataFrame]:
    """
    Extract tables using table region detection and pytesseract OCR.
    
    Args:
        page: pdfplumber page object
        page_image: PIL Image of the page
        page_num: Page number for logging
        min_confidence: Minimum OCR confidence threshold
        
    Returns:
        List of DataFrames extracted from table regions
    """
    try:
        # Use pdfplumber to detect table regions
        tables = page.find_tables()
        
        if not tables:
            logger.debug(f"No table regions detected on page {page_num}")
            return []
        
        logger.info(f"Found {len(tables)} table regions on page {page_num}")
        
        dataframes = []
        for table_idx, table in enumerate(tables):
            try:
                # Get table bounding box
                bbox = table.bbox
                logger.debug(f"Table {table_idx + 1} bbox: {bbox}")
                
                # Crop the table region from the image
                table_image = page_image.crop(bbox)
                
                # Apply OCR to the cropped table
                table_df = _ocr_table_image(table_image, table_idx + 1, page_num, min_confidence)
                
                if table_df is not None and not table_df.empty:
                    logger.info(f"OCR extracted table {table_idx + 1}: {table_df.shape[0]} rows, {table_df.shape[1]} columns")
                    dataframes.append(table_df)
                else:
                    logger.debug(f"OCR failed or returned empty table for region {table_idx + 1}")
                    
            except Exception as e:
                logger.error(f"Error processing table region {table_idx + 1} on page {page_num}: {e}")
                continue
        
        return dataframes
        
    except Exception as e:
        logger.error(f"Table region detection failed on page {page_num}: {e}")
        return []


def _ocr_table_image(table_image: Image.Image, table_idx: int, page_num: int, 
                    min_confidence: float) -> Optional[pd.DataFrame]:
    """
    Apply OCR to a table image and convert to DataFrame.
    
    Args:
        table_image: PIL Image of the table region
        table_idx: Table index for logging
        page_num: Page number for logging
        min_confidence: Minimum OCR confidence threshold
        
    Returns:
        DataFrame if successful, None if failed
    """
    try:
        # Get OCR data with bounding boxes and confidence scores
        ocr_data = pytesseract.image_to_data(table_image, output_type=pytesseract.Output.DICT)
        
        # Filter by confidence
        confident_data = []
        for i in range(len(ocr_data['text'])):
            confidence = int(ocr_data['conf'][i])
            text = ocr_data['text'][i].strip()
            
            if confidence >= min_confidence and text:
                confident_data.append({
                    'text': text,
                    'left': ocr_data['left'][i],
                    'top': ocr_data['top'][i],
                    'width': ocr_data['width'][i],
                    'height': ocr_data['height'][i],
                    'confidence': confidence
                })
        
        if not confident_data:
            logger.debug(f"No confident OCR data for table {table_idx} on page {page_num}")
            return None
        
        logger.debug(f"Found {len(confident_data)} confident OCR elements for table {table_idx}")
        
        # Reconstruct table structure from OCR data
        table_df = _reconstruct_table_from_ocr_data(confident_data)
        
        return table_df
        
    except Exception as e:
        logger.error(f"OCR failed for table {table_idx} on page {page_num}: {e}")
        return None


def _reconstruct_table_from_ocr_data(ocr_data: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Reconstruct table structure from OCR data with bounding boxes.
    
    Args:
        ocr_data: List of OCR elements with text and bounding boxes
        
    Returns:
        DataFrame representing the reconstructed table
    """
    if not ocr_data:
        return pd.DataFrame()
    
    # Sort by top position to group into rows
    ocr_data.sort(key=lambda x: x['top'])
    
    # Group elements into rows based on vertical position
    rows = []
    current_row = []
    current_row_top = None
    row_tolerance = 10  # pixels
    
    for element in ocr_data:
        if current_row_top is None or abs(element['top'] - current_row_top) <= row_tolerance:
            current_row.append(element)
            current_row_top = element['top'] if current_row_top is None else current_row_top
        else:
            # Start new row
            if current_row:
                # Sort current row by left position
                current_row.sort(key=lambda x: x['left'])
                rows.append(current_row)
            current_row = [element]
            current_row_top = element['top']
    
    # Add the last row
    if current_row:
        current_row.sort(key=lambda x: x['left'])
        rows.append(current_row)
    
    # Convert to DataFrame
    if not rows:
        return pd.DataFrame()
    
    # Find maximum number of columns
    max_cols = max(len(row) for row in rows)
    
    # Create 2D array
    table_data = []
    for row in rows:
        row_data = [elem['text'] for elem in row]
        # Pad with empty strings if needed
        while len(row_data) < max_cols:
            row_data.append('')
        table_data.append(row_data)
    
    # Create DataFrame
    df = pd.DataFrame(table_data)
    
    # Clean up the DataFrame
    df = df.replace('', pd.NA).dropna(how='all').dropna(axis=1, how='all')
    
    return df


def extract_tables_and_text(pdf_path: str) -> List[Dict]:
    """
    Legacy function for backward compatibility.
    Extract tables and text from PDF using the enhanced pipeline.
    
    Args:
        pdf_path: Path to the PDF file to process
        
    Returns:
        List of page dictionaries with 'page', 'full_text', and 'tables' keys
    """
    try:
        logger.info(f"Starting legacy extract_tables_and_text for: {pdf_path}")
        
        # Use the new pipeline to extract tables
        table_dataframes = extract_tables_with_tesseract_pipeline(pdf_path)
        
        # Also extract full text for each page
        results = []
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                # Convert page to image and extract full text
                page_image = _convert_page_to_image(page)
                full_text = pytesseract.image_to_string(page_image, lang="eng")
                
                # Find tables for this page (simplified approach)
                page_tables = []
                for df in table_dataframes:
                    # Convert DataFrame to list of lists for backward compatibility
                    if not df.empty:
                        table_as_lists = df.values.tolist()
                        page_tables.append(table_as_lists)
                
                results.append({
                    "page": page_num,
                    "full_text": full_text,
                    "tables": page_tables
                })
        
        return results
        
    except Exception as e:
        logger.error(f"Legacy extract_tables_and_text failed: {e}")
        raise


def run_extraction_with_tesseract(pdf_path: str):
    """
    Legacy function for backward compatibility.
    Run extraction using the enhanced Tesseract pipeline.
    
    Args:
        pdf_path: Path to the PDF file to process
        
    Returns:
        List of page dictionaries with processed table data
    """
    try:
        logger.info(f"Starting legacy run_extraction_with_tesseract for: {pdf_path}")
        
        # Use the legacy function which maintains the expected format
        page_dicts = extract_tables_and_text(pdf_path)
        
        # Post-process for backward compatibility
        for page in page_dicts:
            processed_tables = []
            for table in page["tables"]:
                # Convert to expected format (list of row lists)
                if isinstance(table, list):
                    processed_tables.append(table)
                else:
                    # Handle DataFrame case
                    processed_tables.append(table.values.tolist() if hasattr(table, 'values') else [])
            page["tables"] = processed_tables
        
        return page_dicts
        
    except Exception as e:
        logger.error(f"Legacy run_extraction_with_tesseract failed: {e}")
        raise


def get_tesseract_table_metadata(pdf_path: str, pages: str = 'all') -> List[Dict[str, Any]]:
    """
    Get metadata about tables detected by the Tesseract pipeline.
    
    Args:
        pdf_path: Path to the PDF file to process
        pages: Pages to process
        
    Returns:
        List of dictionaries containing table metadata
    """
    try:
        logger.info(f"Getting Tesseract table metadata for: {pdf_path}")
        
        table_dataframes = extract_tables_with_tesseract_pipeline(pdf_path, pages)
        
        metadata = []
        for i, df in enumerate(table_dataframes):
            table_info = {
                'table_index': i + 1,
                'rows': df.shape[0],
                'columns': df.shape[1],
                'is_empty': df.empty,
                'source': 'tesseract_pipeline',
                'extraction_method': 'camelot_on_image' if not df.empty else 'region_detection'
            }
            metadata.append(table_info)
        
        return metadata
        
    except Exception as e:
        logger.error(f"Failed to get Tesseract table metadata: {e}")
        raise 