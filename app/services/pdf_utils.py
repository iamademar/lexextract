import pdfplumber
import fitz  # PyMuPDF
import logging
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
import io

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def is_text_page(pdf_path: str, page_num: int) -> bool:
    """
    Determine if a PDF page contains extractable text (vector-based) or is image-based (scanned).
    
    Args:
        pdf_path: Path to the PDF file
        page_num: Page number (1-indexed)
        
    Returns:
        True if page has extractable text, False if scanned/image-based
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if page_num > len(pdf.pages):
                return False
                
            page = pdf.pages[page_num - 1]
            text = page.extract_text()
            
            # Check if page has substantial text content
            if text and len(text.strip()) > 50:
                # Additional check: ensure text is not just OCR artifacts
                words = text.split()
                if len(words) > 10:
                    return True
            
            return False
    except Exception as e:
        logger.error(f"Error checking if page is text-based: {e}")
        return False


def is_scanned_page(pdf_path: str, page_num: int) -> bool:
    """
    Determine if a PDF page is scanned (image-based).
    
    Args:
        pdf_path: Path to the PDF file
        page_num: Page number (1-indexed)
        
    Returns:
        True if page is scanned, False otherwise
    """
    return not is_text_page(pdf_path, page_num)


def preprocess_image_for_table_detection(image: np.ndarray) -> np.ndarray:
    """
    Preprocess image to improve table detection using computer vision techniques.
    Based on industry best practices for PDF table extraction.
    """
    # Convert to grayscale
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    
    # Apply adaptive thresholding to handle varying lighting
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )
    
    # Apply morphological operations to clean up the image
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    
    return cleaned


def detect_table_structure_cv(image: np.ndarray, min_table_area: int = 1000) -> list:
    """
    Detect table structure using computer vision techniques.
    Based on advanced approaches found in industry research.
    """
    # Preprocess the image
    processed = preprocess_image_for_table_detection(image)
    
    # Find contours
    contours, _ = cv2.findContours(processed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Filter contours by area and aspect ratio
    table_candidates = []
    
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_table_area:
            continue
            
        # Get bounding rectangle
        x, y, w, h = cv2.boundingRect(contour)
        aspect_ratio = w / h
        
        # Tables typically have reasonable aspect ratios
        if 0.1 < aspect_ratio < 10:
            table_candidates.append({
                'bbox': (x, y, w, h),
                'area': area,
                'contour': contour
            })
    
    # Sort by area (largest first)
    table_candidates.sort(key=lambda x: x['area'], reverse=True)
    
    return table_candidates


def enhance_ocr_confidence(pdf_path: str, page_num: int) -> dict:
    """
    Enhance OCR confidence using multiple techniques and validation.
    """
    confidence_metrics = {
        'text_density': 0.0,
        'word_count': 0,
        'line_count': 0,
        'table_likelihood': 0.0,
        'overall_confidence': 0.0
    }
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if page_num > len(pdf.pages):
                return confidence_metrics
                
            page = pdf.pages[page_num - 1]
            
            # Calculate text density
            text = page.extract_text() or ""
            bbox = page.bbox
            page_area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
            
            confidence_metrics['text_density'] = len(text) / page_area if page_area > 0 else 0
            confidence_metrics['word_count'] = len(text.split())
            confidence_metrics['line_count'] = len(text.split('\n'))
            
            # Detect table-like patterns
            tables = page.extract_tables()
            confidence_metrics['table_likelihood'] = min(len(tables) * 0.3, 1.0)
            
            # Calculate overall confidence
            confidence_metrics['overall_confidence'] = min(
                (confidence_metrics['text_density'] * 0.3 +
                 min(confidence_metrics['word_count'] / 100, 1.0) * 0.3 +
                 confidence_metrics['table_likelihood'] * 0.4), 1.0
            )
            
    except Exception as e:
        logger.error(f"Error calculating OCR confidence: {e}")
    
    return confidence_metrics


def validate_extraction_quality(extracted_data: list, confidence_threshold: float = 0.7) -> dict:
    """
    Validate the quality of extracted transaction data.
    """
    validation_results = {
        'passed': False,
        'confidence': 0.0,
        'issues': [],
        'suggestions': []
    }
    
    if not extracted_data:
        validation_results['issues'].append("No transactions extracted")
        validation_results['suggestions'].append("Try different OCR settings or manual review")
        return validation_results
    
    # Check for data consistency
    date_formats = set()
    amount_patterns = set()
    
    for transaction in extracted_data:
        # Validate date formats
        if 'date' in transaction:
            date_str = str(transaction['date'])
            if '/' in date_str:
                date_formats.add('slash')
            elif '-' in date_str:
                date_formats.add('dash')
        
        # Validate amount patterns
        if 'amount' in transaction:
            amount_str = str(transaction['amount'])
            if ',' in amount_str:
                amount_patterns.add('comma')
            if '$' in amount_str:
                amount_patterns.add('dollar')
    
    # Calculate confidence based on consistency
    consistency_score = 1.0
    if len(date_formats) > 2:
        consistency_score -= 0.2
        validation_results['issues'].append("Inconsistent date formats detected")
    
    if len(amount_patterns) > 2:
        consistency_score -= 0.2
        validation_results['issues'].append("Inconsistent amount formats detected")
    
    validation_results['confidence'] = consistency_score
    validation_results['passed'] = consistency_score >= confidence_threshold
    
    if consistency_score < confidence_threshold:
        validation_results['suggestions'].append("Consider manual review of extracted data")
        validation_results['suggestions'].append("Try different extraction methods")
    
    return validation_results 