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

async def run_ocr(file_path: str) -> List[str]:
    """
    Extract text from PDF using OCR.
    
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
                
                # Convert page to image
                matrix = fitz.Matrix(2.0, 2.0)  # 2x zoom for better quality
                pix = page.get_pixmap(matrix=matrix)
                
                # Convert to PIL Image
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))
                
                # Convert PIL Image to numpy array for PaddleOCR
                img_array = np.array(img)
                
                # Run OCR on the image
                logger.info(f"Running OCR on page {page_num + 1} image array shape: {img_array.shape}")
                ocr_result = ocr_instance.ocr(img_array)
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
                            logger.info(f"OCR line: '{text}' (confidence: {confidence:.3f})")
                            
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
                                
                                logger.info(f"OCR line: '{text}' (confidence: {confidence})")
                                
                                # Use lower threshold to capture more text
                                if confidence > 0.1:
                                    page_text += text + " "
                    else:
                        logger.warning(f"Unexpected OCR result format: {type(result_dict)}")
                else:
                    logger.warning(f"No OCR results found for page {page_num + 1}")
                
                page_texts.append(page_text.strip())
                logger.info(f"Processed page {page_num + 1}/{len(pdf_document)}")
                
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

 