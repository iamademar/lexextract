import os
import logging
from typing import List, Dict, Any
from pathlib import Path
import fitz  # PyMuPDF
from paddleocr import PaddleOCR
from PIL import Image
import numpy as np
import io

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize PaddleOCR instances (will be cached after first use)
ocr = None
structure_ocr = None

# Memory-efficient processing limits
MAX_PIXMAP_WIDTH = 1200  # Much more conservative maximum width
MAX_PIXMAP_HEIGHT = 1200  # Much more conservative maximum height  
MAX_PIXMAP_SAMPLES = 4_000_000  # Much more conservative maximum samples

def get_ocr_instance():
    """Get a singleton instance of PaddleOCR"""
    global ocr
    if ocr is None:
        try:
            ocr = PaddleOCR(
                use_textline_orientation=True,
                lang='en'
            )
            logger.info("PaddleOCR initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize PaddleOCR: {e}")
            raise
    return ocr

def get_structure_ocr_instance():
    """Get a singleton instance of PaddleOCR with structure analysis enabled"""
    global structure_ocr
    if structure_ocr is None:
        try:
            # Use PP-StructureV3 for structure analysis - supported in PaddleOCR 3.1.0
            from paddleocr import PPStructureV3
            structure_ocr = PPStructureV3(
                use_doc_orientation_classify=False,
                use_doc_unwarping=False
            )
            logger.info("PP-StructureV3 initialized successfully for structure analysis")
        except Exception as e:
            logger.error(f"Failed to initialize PP-StructureV3: {e}")
            raise
    return structure_ocr

async def run_ocr(file_path: str) -> List[str]:
    """
    Extract text from PDF using OCR with memory-efficient processing.
    
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
        
        logger.info(f"Starting OCR processing for: {file_path}")
        
        # Get OCR instance
        ocr_instance = get_ocr_instance()
        
        # Open PDF document
        pdf_document = fitz.open(file_path)
        page_texts = []
        
        # Process each page
        for page_num in range(len(pdf_document)):
            try:
                # Get page
                page = pdf_document[page_num]
                page_rect = page.rect
                
                # Calculate safe zoom matrix to prevent memory issues
                matrix = calculate_safe_matrix(page_rect)
                
                # Convert page to image with safe matrix
                pix = page.get_pixmap(matrix=matrix)
                
                # Check if pixmap is too large (ensure samples is treated as int)
                samples_count = len(pix.samples) if hasattr(pix.samples, '__len__') else pix.samples
                if samples_count > MAX_PIXMAP_SAMPLES:
                    logger.warning(f"Page {page_num + 1} pixmap too large ({samples_count} samples), using lower resolution")
                    # Use even lower resolution for very large pages
                    safe_zoom = min(1.0, MAX_PIXMAP_SAMPLES / (page_rect.width * page_rect.height * 3))
                    matrix = fitz.Matrix(safe_zoom, safe_zoom)
                    pix = page.get_pixmap(matrix=matrix)
                    samples_count = len(pix.samples) if hasattr(pix.samples, '__len__') else pix.samples
                
                logger.info(f"Page {page_num + 1} pixmap: {pix.width}x{pix.height}, samples: {samples_count}")
                
                # Convert to PIL Image
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))
                
                # Convert PIL Image to numpy array for PaddleOCR
                img_array = np.array(img)
                
                # Clean up pixmap memory
                pix = None
                
                # Run OCR on the image
                logger.info(f"Running OCR on page {page_num + 1}")
                ocr_result = ocr_instance.ocr(img_array)
                
                # Clean up image memory
                img = None
                img_array = None
                
                logger.info(f"OCR result type: {type(ocr_result)}, length: {len(ocr_result) if ocr_result else 'None'}")
                
                # Extract text from OCR result
                page_text = ""
                if ocr_result and len(ocr_result) > 0:
                    result_dict = ocr_result[0]
                    
                    # Handle new PaddleOCR format (dictionary with rec_texts and rec_scores)
                    if isinstance(result_dict, dict) and 'rec_texts' in result_dict and 'rec_scores' in result_dict:
                        texts = result_dict['rec_texts']
                        scores = result_dict['rec_scores']
                        
                        logger.info(f"Processing {len(texts)} OCR text results")
                        for text, confidence in zip(texts, scores):
                            # Use lower threshold to capture more text
                            if confidence > 0.1:  # Very low threshold to capture more text
                                page_text += text + " "
                    
                    # Handle old PaddleOCR format (list of [bbox, [text, confidence]])
                    elif isinstance(result_dict, list):
                        logger.info(f"Processing {len(result_dict)} OCR result lines (old format)")
                        for line in result_dict:
                            if line and len(line) > 1:
                                text = line[1][0] if line[1] else ""
                                confidence = line[1][1] if line[1] and len(line[1]) > 1 else 0
                                
                                # Use lower threshold to capture more text
                                if confidence > 0.1:
                                    page_text += text + " "
                    else:
                        logger.warning(f"Unexpected OCR result format: {type(result_dict)}")
                else:
                    logger.warning(f"No OCR results found for page {page_num + 1}")
                
                page_texts.append(page_text.strip())
                logger.info(f"Processed page {page_num + 1}/{len(pdf_document)}, extracted {len(page_text)} characters")
                
            except Exception as e:
                logger.error(f"Error processing page {page_num + 1}: {e}")
                page_texts.append(f"Error processing page {page_num + 1}: {str(e)}")
        
        # Close PDF document
        pdf_document.close()
        
        logger.info(f"OCR processing completed. Extracted text from {len(page_texts)} pages")
        return page_texts
        
    except FileNotFoundError as e:
        logger.error(f"OCR processing failed for {file_path}: {e}")
        raise e  # Re-raise the original FileNotFoundError
    except Exception as e:
        logger.error(f"OCR processing failed for {file_path}: {e}")
        raise Exception(f"OCR processing failed: {str(e)}")

async def run_structure_analysis(file_path: str) -> List[Dict[str, Any]]:
    """
    Extract structured data from PDF using PaddleOCR PP-StructureV3.
    
    Args:
        file_path: Path to the PDF file to process
        
    Returns:
        List of structure analysis results, one for each page
    """
    try:
        # Check if file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF file not found: {file_path}")
        
        logger.info(f"Starting PP-StructureV3 analysis for: {file_path}")
        
        # Get structure OCR instance
        structure_instance = get_structure_ocr_instance()
        
        # Open PDF document
        pdf_document = fitz.open(file_path)
        structure_results = []
        
        # Process each page
        for page_num in range(len(pdf_document)):
            try:
                # Get page
                page = pdf_document[page_num]
                page_rect = page.rect
                
                # Calculate safe zoom matrix to prevent memory issues
                matrix = calculate_safe_matrix(page_rect)
                
                # Convert page to image with safe matrix
                pix = page.get_pixmap(matrix=matrix)
                
                # Check if pixmap is too large
                samples_count = len(pix.samples) if hasattr(pix.samples, '__len__') else pix.samples
                if samples_count > MAX_PIXMAP_SAMPLES:
                    logger.warning(f"Page {page_num + 1} pixmap too large ({samples_count} samples), using lower resolution")
                    # Use even lower resolution for very large pages
                    safe_zoom = min(1.0, MAX_PIXMAP_SAMPLES / (page_rect.width * page_rect.height * 3))
                    matrix = fitz.Matrix(safe_zoom, safe_zoom)
                    pix = page.get_pixmap(matrix=matrix)
                    samples_count = len(pix.samples) if hasattr(pix.samples, '__len__') else pix.samples
                
                logger.info(f"Page {page_num + 1} pixmap: {pix.width}x{pix.height}, samples: {samples_count}")
                
                # Convert to PIL Image
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))
                
                # Clean up pixmap memory
                pix = None
                
                # Run structure analysis on the image
                logger.info(f"Running PP-StructureV3 analysis on page {page_num + 1}")
                
                # Convert PIL image to numpy array for PP-StructureV3
                import numpy as np
                img_array = np.array(img)
                
                # PP-StructureV3 expects different input format
                structure_result = structure_instance.predict(input=img_array)
                
                # Clean up image memory
                img = None
                
                logger.info(f"PP-StructureV3 analysis completed for page {page_num + 1}")
                
                # Process structure results
                page_structure = {
                    'page': page_num + 1,
                    'structure': structure_result if structure_result else []
                }
                
                structure_results.append(page_structure)
                
            except Exception as e:
                logger.error(f"Error processing page {page_num + 1}: {e}")
                structure_results.append({
                    'page': page_num + 1,
                    'structure': [],
                    'error': str(e)
                })
        
        # Close PDF document
        pdf_document.close()
        
        logger.info(f"PP-StructureV3 analysis completed. Processed {len(structure_results)} pages")
        return structure_results
        
    except FileNotFoundError as e:
        logger.error(f"Structure analysis failed for {file_path}: {e}")
        raise e
    except Exception as e:
        logger.error(f"Structure analysis failed for {file_path}: {e}")
        raise Exception(f"Structure analysis failed: {str(e)}")

def extract_tables_from_structure(structure_results: List[Dict]) -> List[Dict[str, Any]]:
    """
    Extract table data from PP-StructureV3 results.
    
    Args:
        structure_results: Structure analysis results from PP-StructureV3
        
    Returns:
        List of table dictionaries with reconstructed rows/columns
    """
    all_tables = []
    
    logger.info("=" * 80)
    logger.info("🔍 STARTING TABLE EXTRACTION FROM PP-STRUCTUREV3 RESULTS")
    logger.info("=" * 80)
    
    for page_num, page_result in enumerate(structure_results):
        if not page_result or 'structure' not in page_result:
            logger.warning(f"No structure data found for page {page_num + 1}")
            continue
            
        page_tables = []
        structure_data = page_result['structure']
        
        # PP-StructureV3 returns results in a specific format
        # The structure_data should be a list of result objects
        if isinstance(structure_data, list):
            for result in structure_data:
                logger.info(f"Processing structure result: {type(result)}")
                
                # Check if this is a table result
                if hasattr(result, 'class_name') and result.class_name == 'table':
                    # Extract table information
                    table_html = getattr(result, 'html', None)
                    table_cells = getattr(result, 'cells', None)
                    
                    if table_html or table_cells:
                        # Try to extract table data from HTML or cells
                        table_data = None
                        
                        if table_cells:
                            # Extract from cell data
                            table_data = reconstruct_table_from_cells(table_cells)
                        elif table_html:
                            # Extract from HTML (would need HTML parser)
                            logger.info("Table HTML found but parser not implemented")
                            
                        if table_data:
                            page_tables.append({
                                'page': page_num + 1,
                                'table_data': table_data,
                                'source': 'cells' if table_cells else 'html'
                            })
                            
                            # LOG THE EXTRACTED TABLE - MAKE IT OBVIOUS
                            logger.info("🟢" * 50)
                            logger.info(f"📊 TABLE FOUND ON PAGE {page_num + 1}")
                            logger.info(f"📊 Table has {len(table_data)} rows")
                            logger.info("🟢" * 50)
                            
                            # Print the actual table structure
                            logger.info("📋 TABLE CONTENT:")
                            for row_idx, row in enumerate(table_data):
                                if isinstance(row, list):
                                    row_text = " | ".join([f"{str(cell):>15}" for cell in row])
                                    logger.info(f"Row {row_idx + 1:2d}: {row_text}")
                            
                            logger.info("🟢" * 50)
                else:
                    logger.info(f"Non-table result: {getattr(result, 'class_name', 'unknown')}")
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

def reconstruct_table_from_cells(cells: List[Dict]) -> List[List[str]]:
    """
    Reconstruct table structure from cell bounding boxes and text.
    
    Args:
        cells: List of cell dictionaries with bbox and text
        
    Returns:
        2D list representing table rows and columns
    """
    if not cells:
        logger.warning("🚫 No cells provided for table reconstruction")
        return []
    
    logger.info(f"🔧 Reconstructing table from {len(cells)} cells")
    
    # Extract cell positions and text
    cell_data = []
    for cell in cells:
        bbox = cell.get('bbox', [])
        text = cell.get('text', '').strip()
        
        if len(bbox) >= 4:  # [x1, y1, x2, y2]
            x1, y1, x2, y2 = bbox[:4]
            cell_data.append({
                'text': text,
                'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2,
                'center_x': (x1 + x2) / 2,
                'center_y': (y1 + y2) / 2
            })
    
    if not cell_data:
        logger.warning("🚫 No valid cell data found after processing")
        return []
    
    logger.info(f"✅ Processed {len(cell_data)} valid cells")
    
    # Sort by Y position to identify rows
    cell_data.sort(key=lambda x: x['center_y'])
    
    # Group cells into rows based on Y position
    rows = []
    current_row = []
    current_y = None
    y_tolerance = 10  # Tolerance for row alignment
    
    for cell in cell_data:
        if current_y is None or abs(cell['center_y'] - current_y) <= y_tolerance:
            current_row.append(cell)
            current_y = cell['center_y'] if current_y is None else current_y
        else:
            # Sort current row by X position
            current_row.sort(key=lambda x: x['center_x'])
            rows.append(current_row)
            current_row = [cell]
            current_y = cell['center_y']
    
    # Add final row
    if current_row:
        current_row.sort(key=lambda x: x['center_x'])
        rows.append(current_row)
    
    # Convert to 2D string array
    table_2d = []
    for row in rows:
        table_2d.append([cell['text'] for cell in row])
    
    logger.info(f"🏗️  Reconstructed table with {len(table_2d)} rows")
    
    # LOG THE RECONSTRUCTED TABLE STRUCTURE
    if table_2d:
        logger.info("🔥" * 60)
        logger.info("📊 RECONSTRUCTED TABLE STRUCTURE:")
        logger.info("🔥" * 60)
        
        # Find max width for each column for better formatting
        if table_2d:
            max_cols = max(len(row) for row in table_2d)
            col_widths = [0] * max_cols
            
            for row in table_2d:
                for col_idx, cell in enumerate(row):
                    if col_idx < len(col_widths):
                        col_widths[col_idx] = max(col_widths[col_idx], len(str(cell)))
        
        # Print each row with proper formatting
        for row_idx, row in enumerate(table_2d):
            formatted_cells = []
            for col_idx, cell in enumerate(row):
                width = col_widths[col_idx] if col_idx < len(col_widths) else 15
                formatted_cells.append(f"{str(cell):<{width}}")
            
            row_text = " | ".join(formatted_cells)
            logger.info(f"📋 Row {row_idx + 1:2d}: | {row_text} |")
            
            # Add separator after header row
            if row_idx == 0 and len(table_2d) > 1:
                separator = " | ".join(["-" * width for width in col_widths[:len(row)]])
                logger.info(f"📋      | {separator} |")
        
        logger.info("🔥" * 60)
    
    return table_2d

def calculate_safe_matrix(page_rect, max_width=MAX_PIXMAP_WIDTH, max_height=MAX_PIXMAP_HEIGHT):
    """Calculate a safe zoom matrix that won't exceed memory limits"""
    page_width = page_rect.width
    page_height = page_rect.height
    
    # Calculate zoom factors to fit within limits
    zoom_x = max_width / page_width if page_width > max_width else 1.5
    zoom_y = max_height / page_height if page_height > max_height else 1.5
    
    # Use the smaller zoom to ensure both dimensions fit, cap at 1.5x
    zoom = min(zoom_x, zoom_y, 1.5)  # Conservative cap at 1.5x zoom
    
    # Extra safety: ensure resulting dimensions won't be too large
    resulting_width = page_width * zoom
    resulting_height = page_height * zoom
    if resulting_width > max_width or resulting_height > max_height:
        zoom = min(max_width / page_width, max_height / page_height)
    
    logger.info(f"Page size: {page_width:.1f}x{page_height:.1f}, calculated zoom: {zoom:.2f}")
    return fitz.Matrix(zoom, zoom)

 