import camelot
import pandas as pd
from typing import List
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_tables_with_camelot(pdf_path: str, pages: str = 'all', flavor: str = 'lattice') -> List[pd.DataFrame]:
    """
    Extract tables from vector-PDF using camelot-py.
    
    Args:
        pdf_path: Path to the PDF file to process
        pages: Pages to process (e.g., 'all', '1', '1-3', '1,2,3')
        flavor: Camelot flavor to use ('lattice' or 'stream')
        
    Returns:
        List of pandas DataFrames, one for each detected table
        
    Raises:
        FileNotFoundError: If PDF file doesn't exist
        ValueError: If invalid flavor is provided
        Exception: If camelot processing fails
    """
    try:
        # Validate inputs
        pdf_file = Path(pdf_path)
        if not pdf_file.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        if flavor not in ['lattice', 'stream']:
            raise ValueError(f"Invalid flavor '{flavor}'. Must be 'lattice' or 'stream'")
        
        logger.info(f"Starting Camelot table extraction for: {pdf_path}")
        logger.info(f"Pages: {pages}, Flavor: {flavor}")
        
        # Extract tables using camelot
        tables = camelot.read_pdf(pdf_path, pages=pages, flavor=flavor)
        
        logger.info(f"Camelot detected {len(tables)} tables")
        
        # Convert to list of DataFrames
        dataframes = []
        for i, table in enumerate(tables):
            df = table.df
            logger.info(f"Table {i+1}: {df.shape[0]} rows, {df.shape[1]} columns")
            
            # Log table preview for debugging
            if not df.empty:
                logger.debug(f"Table {i+1} preview:\n{df.head()}")
            
            dataframes.append(df)
        
        logger.info(f"Successfully extracted {len(dataframes)} tables from {pdf_path}")
        return dataframes
        
    except FileNotFoundError:
        logger.error(f"PDF file not found: {pdf_path}")
        raise
    except ValueError as e:
        logger.error(f"Invalid parameter: {e}")
        raise
    except Exception as e:
        logger.error(f"Camelot table extraction failed for {pdf_path}: {e}")
        raise Exception(f"Camelot processing failed: {str(e)}")


def extract_tables_with_confidence(pdf_path: str, pages: str = 'all', 
                                   flavor: str = 'lattice', 
                                   min_accuracy: float = 0.7) -> List[pd.DataFrame]:
    """
    Extract tables with confidence filtering.
    
    Args:
        pdf_path: Path to the PDF file to process
        pages: Pages to process (e.g., 'all', '1', '1-3', '1,2,3')
        flavor: Camelot flavor to use ('lattice' or 'stream')
        min_accuracy: Minimum accuracy threshold (0.0 to 1.0)
        
    Returns:
        List of pandas DataFrames for tables meeting accuracy threshold
    """
    try:
        pdf_file = Path(pdf_path)
        if not pdf_file.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        logger.info(f"Starting Camelot table extraction with confidence filtering")
        logger.info(f"Min accuracy: {min_accuracy}")
        
        # Extract tables using camelot
        tables = camelot.read_pdf(pdf_path, pages=pages, flavor=flavor)
        
        # Filter by accuracy
        filtered_dataframes = []
        for i, table in enumerate(tables):
            accuracy = table.accuracy
            logger.info(f"Table {i+1}: accuracy = {accuracy:.2f}")
            
            if accuracy >= min_accuracy:
                df = table.df
                logger.info(f"Table {i+1} passed accuracy filter: {df.shape[0]} rows, {df.shape[1]} columns")
                filtered_dataframes.append(df)
            else:
                logger.info(f"Table {i+1} rejected (accuracy {accuracy:.2f} < {min_accuracy})")
        
        logger.info(f"Filtered to {len(filtered_dataframes)} high-confidence tables")
        return filtered_dataframes
        
    except Exception as e:
        logger.error(f"Camelot confidence extraction failed: {e}")
        raise


def get_table_metadata(pdf_path: str, pages: str = 'all', flavor: str = 'lattice') -> List[dict]:
    """
    Get table metadata without extracting full DataFrames.
    
    Args:
        pdf_path: Path to the PDF file to process
        pages: Pages to process
        flavor: Camelot flavor to use
        
    Returns:
        List of dictionaries containing table metadata
    """
    try:
        pdf_file = Path(pdf_path)
        if not pdf_file.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        logger.info(f"Getting table metadata for: {pdf_path}")
        
        # Extract tables using camelot
        tables = camelot.read_pdf(pdf_path, pages=pages, flavor=flavor)
        
        metadata = []
        for i, table in enumerate(tables):
            table_info = {
                'table_index': i + 1,
                'page': table.page,
                'accuracy': table.accuracy,
                'whitespace': table.whitespace,
                'order': table.order,
                'rows': table.df.shape[0],
                'columns': table.df.shape[1],
                'flavor': flavor
            }
            metadata.append(table_info)
            
            logger.info(f"Table {i+1}: Page {table.page}, "
                       f"Accuracy {table.accuracy:.2f}, "
                       f"Shape {table.df.shape}")
        
        return metadata
        
    except Exception as e:
        logger.error(f"Failed to get table metadata: {e}")
        raise 