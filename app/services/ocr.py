import os
import logging
from typing import List
from pathlib import Path
import fitz  # PyMuPDF
from paddleocr import PaddleOCR
from PIL import Image
import numpy as np
import io

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize PaddleOCR (will be cached after first use)
ocr = None

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

 