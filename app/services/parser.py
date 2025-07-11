import re
import logging
import decimal
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
import pdfplumber
import os
from .ocr import run_ocr, run_structure_analysis, extract_tables_from_structure

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TransactionData(BaseModel):
    """Pydantic model for structured transaction data"""
    date: datetime
    payee: str = Field(..., description="Merchant or transaction description")
    amount: Decimal = Field(..., description="Transaction amount (positive for credits, negative for debits)")
    type: str = Field(..., description="Transaction type (Credit/Debit)")
    balance: Optional[Decimal] = Field(None, description="Account balance after transaction")
    currency: str = Field(default="GBP", description="Currency code")

    @field_validator('amount', mode='before')
    @classmethod
    def parse_amount(cls, v):
        """Convert string amounts to Decimal"""
        if isinstance(v, str):
            # Remove currency symbols and spaces
            clean_amount = re.sub(r'[£$€,\s]', '', v)
            return Decimal(clean_amount)
        return v

    @field_validator('balance', mode='before')
    @classmethod
    def parse_balance(cls, v):
        """Convert string balance to Decimal"""
        if v is None or v == '':
            return None
        if isinstance(v, str):
            # Remove currency symbols and spaces
            clean_balance = re.sub(r'[£$€,\s]', '', v)
            return Decimal(clean_balance)
        return v

    @field_validator('type')
    @classmethod
    def validate_type(cls, v):
        """Ensure transaction type is valid"""
        valid_types = ['Credit', 'Debit']
        if v not in valid_types:
            return 'Debit' if v.lower() in ['debit', 'withdrawal', 'payment', 'purchase'] else 'Credit'
        return v


def parse_transactions(pages: List[str]) -> List[TransactionData]:
    """
    Extract structured transaction data from OCR pages using regex patterns.
    
    Args:
        pages: List of OCR text strings, one for each page
        
    Returns:
        List of TransactionData objects representing parsed transactions
    """
    if not pages:
        logger.warning("No pages provided for parsing")
        return []

    transactions = []
    
    for page_num, page_text in enumerate(pages):
        if not page_text or not page_text.strip():
            logger.warning(f"Empty page {page_num + 1}, skipping")
            continue
            
        logger.info(f"Parsing transactions from page {page_num + 1}")
        
        # Try different bank statement formats
        page_transactions = []
        
        # Format 1: Standard US bank format (from sample data)
        page_transactions.extend(_parse_standard_us_format(page_text))
        
        # Format 2: UK bank format (common patterns)
        page_transactions.extend(_parse_uk_format(page_text))
        
        if page_transactions:
            logger.info(f"Found {len(page_transactions)} transactions on page {page_num + 1}")
            transactions.extend(page_transactions)
        else:
            logger.warning(f"No transactions found on page {page_num + 1}")
    
    logger.info(f"Total transactions parsed: {len(transactions)}")
    return transactions


def _parse_standard_us_format(text: str) -> List[TransactionData]:
    """Parse transactions from standard US bank statement format"""
    transactions = []
    
    # Pattern for transactions with date, description, debit, credit, balance
    # Example: "10/02 POS PURCHASE 4.23 Balance"
    # Example: "10/03 PREAUTHORIZEDCREDIT 65.73 763.01"
    
    # Look for transaction patterns with dates
    date_pattern = r'(\d{1,2}/\d{1,2})\s+'
    
    # Pattern for transaction lines
    transaction_patterns = [
        # Pattern 1: Date Description Amount Balance (debit transactions)
        r'(\d{1,2}/\d{1,2})\s+(.*?)\s+(\d+\.\d{2})\s+(\d+\.\d{2})',
        # Pattern 2: Date Description Credit Amount Balance  
        r'(\d{1,2}/\d{1,2})\s+(.*?)\s+(\d+\.\d{2})\s+(\d+\.\d{2})',
        # Pattern 3: Simple date amount pattern
        r'(\d{1,2}/\d{1,2})\s+(.*?)\s+(\d+\.\d{2})'
    ]
    
    # Split into lines and process each
    lines = text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Look for patterns that indicate transactions
        for pattern in transaction_patterns:
            match = re.search(pattern, line)
            if match:
                try:
                    date_str = match.group(1)
                    description = match.group(2).strip()
                    amount_str = match.group(3)
                    
                    # Parse date (assume current year if not specified)
                    current_year = datetime.now().year
                    month, day = map(int, date_str.split('/'))
                    trans_date = datetime(current_year, month, day)
                    
                    # Parse amount
                    amount = Decimal(amount_str)
                    
                    # Determine transaction type based on description
                    trans_type = _determine_transaction_type(description)
                    
                    # For debits, make amount negative
                    if trans_type == 'Debit':
                        amount = -amount
                    
                    # Extract balance if available
                    balance = None
                    if len(match.groups()) >= 4:
                        try:
                            balance = Decimal(match.group(4))
                        except:
                            balance = None
                    
                    transaction = TransactionData(
                        date=trans_date,
                        payee=description,
                        amount=amount,
                        type=trans_type,
                        balance=balance,
                        currency="USD"  # Assume USD for US format
                    )
                    
                    transactions.append(transaction)
                    break  # Found a match, move to next line
                    
                except Exception as e:
                    logger.error(f"Error parsing transaction from line: {line}, error: {e}")
                    continue
    
    return transactions


def _parse_uk_format(text: str) -> List[TransactionData]:
    """Parse transactions from UK bank statement format"""
    transactions = []
    
    # UK date patterns: DD/MM/YYYY or DD-MM-YYYY
    uk_patterns = [
        # Pattern for UK format: DD/MM Description Amount Balance
        r'(\d{1,2}/\d{1,2}/\d{4}|\d{1,2}/\d{1,2})\s+(.*?)\s+£?(\d+\.\d{2})\s*£?(\d+\.\d{2})?',
        # Pattern for DD-MM format
        r'(\d{1,2}-\d{1,2}-\d{4}|\d{1,2}-\d{1,2})\s+(.*?)\s+£?(\d+\.\d{2})\s*£?(\d+\.\d{2})?'
    ]
    
    lines = text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        for pattern in uk_patterns:
            match = re.search(pattern, line)
            if match:
                try:
                    date_str = match.group(1)
                    description = match.group(2).strip()
                    amount_str = match.group(3)
                    balance_str = match.group(4) if len(match.groups()) >= 4 else None
                    
                    # Parse date
                    if '/' in date_str:
                        date_parts = date_str.split('/')
                    else:
                        date_parts = date_str.split('-')
                        
                    if len(date_parts) == 3:
                        day, month, year = map(int, date_parts)
                    else:
                        day, month = map(int, date_parts)
                        year = datetime.now().year
                        
                    trans_date = datetime(year, month, day)
                    
                    # Parse amount
                    amount = Decimal(amount_str)
                    
                    # Determine transaction type
                    trans_type = _determine_transaction_type(description)
                    
                    # For debits, make amount negative
                    if trans_type == 'Debit':
                        amount = -amount
                    
                    # Parse balance
                    balance = None
                    if balance_str:
                        try:
                            balance = Decimal(balance_str)
                        except:
                            balance = None
                    
                    transaction = TransactionData(
                        date=trans_date,
                        payee=description,
                        amount=amount,
                        type=trans_type,
                        balance=balance,
                        currency="GBP"  # Assume GBP for UK format
                    )
                    
                    transactions.append(transaction)
                    break
                    
                except Exception as e:
                    logger.error(f"Error parsing UK transaction from line: {line}, error: {e}")
                    continue
    
    return transactions


def _determine_transaction_type(description: str) -> str:
    """Determine if transaction is Credit or Debit based on description"""
    description_lower = description.lower()
    
    # Credit indicators
    credit_keywords = [
        'credit', 'deposit', 'interest', 'payroll', 'preauthorized credit',
        'refund', 'salary', 'pension', 'benefit', 'transfer in'
    ]
    
    # Debit indicators  
    debit_keywords = [
        'purchase', 'pos', 'withdrawal', 'atm', 'check', 'payment',
        'debit', 'fee', 'charge', 'service charge', 'transfer out'
    ]
    
    # Check for credit keywords
    for keyword in credit_keywords:
        if keyword in description_lower:
            return 'Credit'
    
    # Check for debit keywords
    for keyword in debit_keywords:
        if keyword in description_lower:
            return 'Debit'
    
    # Default to Debit if uncertain
    return 'Debit'


def _normalize_numeric_string(value: str) -> str:
    """Normalize numeric strings by removing currency symbols and commas"""
    if not value:
        return "0.00"
    # Remove common currency symbols, commas, and whitespace
    return value.replace(',', '').replace('$', '').replace('£', '').replace('€', '').strip()


def _parse_table_date(date_str: str) -> datetime:
    """Parse date string with multiple format attempts"""
    if not date_str:
        raise ValueError("Empty date string")
    
    # Clean the date string
    date_str = date_str.strip()
    
    # Try different date formats
    date_formats = [
        '%m/%d/%y',      # 10/15/24
        '%m/%d/%Y',      # 10/15/2024
        '%d/%m/%y',      # 15/10/24
        '%d/%m/%Y',      # 15/10/2024
        '%m-%d-%y',      # 10-15-24
        '%m-%d-%Y',      # 10-15-2024
        '%d-%m-%y',      # 15-10-24
        '%d-%m-%Y',      # 15-10-2024
        '%Y-%m-%d',      # 2024-10-15
    ]
    
    for date_format in date_formats:
        try:
            return datetime.strptime(date_str, date_format)
        except ValueError:
            continue
    
    # If all formats fail, try to extract components manually
    # Handle cases like "Oct 15, 2024" or other variations
    raise ValueError(f"Unable to parse date: {date_str}")


def _extract_table_transactions(table: List[List[str]]) -> List[Dict[str, Any]]:
    """Extract transactions from a single table"""
    if not table or len(table) < 2:
        return []
    
    # First row is header
    headers = [h.lower().strip() if h else '' for h in table[0]]
    logger.info(f"Table headers: {headers}")
    
    # Find column indices
    date_col = None
    desc_col = None
    amount_col = None
    withdrawal_col = None  # Separate tracking for withdrawal column
    deposit_col = None     # Separate tracking for deposit column
    balance_col = None
    
    # Look for columns by name
    for i, header in enumerate(headers):
        if 'date' in header:
            date_col = i
        elif 'description' in header or 'payee' in header:
            desc_col = i
        elif 'withdrawal' in header or 'debit' in header:
            withdrawal_col = i
        elif 'deposit' in header or 'credit' in header:
            deposit_col = i
        elif 'amount' in header:
            amount_col = i
        elif 'balance' in header:
            balance_col = i
    
    # Fallback to positional columns if names not found
    if date_col is None and len(headers) >= 1:
        date_col = 0
    if desc_col is None and len(headers) >= 2:
        desc_col = 1
    if amount_col is None and withdrawal_col is None and deposit_col is None and len(headers) >= 3:
        amount_col = len(headers) - 2  # Penultimate column
    if balance_col is None and len(headers) >= 4:
        balance_col = len(headers) - 1  # Last column
    
    logger.info(f"Column mapping - Date: {date_col}, Description: {desc_col}, Amount: {amount_col}, Withdrawal: {withdrawal_col}, Deposit: {deposit_col}, Balance: {balance_col}")
    
    transactions = []
    
    # Process data rows (skip header)
    for row_idx, row in enumerate(table[1:], 1):
        try:
            # Ensure row has enough columns
            if len(row) <= max(filter(None, [date_col, desc_col, amount_col, balance_col])):
                logger.warning(f"Row {row_idx} too short: {row}")
                continue
            
            # Extract date
            date_str = row[date_col] if date_col is not None and date_col < len(row) else ""
            if not date_str or not date_str.strip():
                continue
            
            trans_date = _parse_table_date(date_str)
            
            # Extract description
            description = row[desc_col] if desc_col is not None and desc_col < len(row) else ""
            description = description.strip()
            if not description:
                description = "Unknown Transaction"
            
            # Extract amount - handle both single amount column and separate withdrawal/deposit columns
            amount = None
            trans_type = None
            
            # Check for separate withdrawal and deposit columns first
            if withdrawal_col is not None or deposit_col is not None:
                withdrawal_str = ""
                deposit_str = ""
                
                if withdrawal_col is not None and withdrawal_col < len(row):
                    withdrawal_str = row[withdrawal_col].strip()
                if deposit_col is not None and deposit_col < len(row):
                    deposit_str = row[deposit_col].strip()
                
                # Process withdrawal
                if withdrawal_str and withdrawal_str != "":
                    amount_clean = _normalize_numeric_string(withdrawal_str)
                    try:
                        amount = -Decimal(amount_clean)  # Withdrawals are negative
                        trans_type = "Debit"
                    except (ValueError, decimal.InvalidOperation):
                        logger.warning(f"Could not parse withdrawal '{withdrawal_str}' in row {row_idx}")
                
                # Process deposit (if no withdrawal found)
                elif deposit_str and deposit_str != "":
                    amount_clean = _normalize_numeric_string(deposit_str)
                    try:
                        amount = Decimal(amount_clean)  # Deposits are positive
                        trans_type = "Credit"
                    except (ValueError, decimal.InvalidOperation):
                        logger.warning(f"Could not parse deposit '{deposit_str}' in row {row_idx}")
                
                # Skip if no valid amount found in either column
                if amount is None:
                    continue
            else:
                # Handle single amount column
                amount_str = row[amount_col] if amount_col is not None and amount_col < len(row) else ""
                if not amount_str or not amount_str.strip():
                    continue
                
                amount_clean = _normalize_numeric_string(amount_str)
                try:
                    amount = Decimal(amount_clean)
                except (ValueError, decimal.InvalidOperation):
                    logger.warning(f"Could not parse amount '{amount_str}' in row {row_idx}")
                    continue
            
            # Extract balance (optional)
            balance = None
            if balance_col is not None and balance_col < len(row):
                balance_str = row[balance_col]
                if balance_str and balance_str.strip():
                    balance_clean = _normalize_numeric_string(balance_str)
                    try:
                        balance = Decimal(balance_clean)
                    except (ValueError, decimal.InvalidOperation):
                        logger.warning(f"Could not parse balance '{balance_str}' in row {row_idx}")
                        balance = None
            
            # Determine transaction type (only if not already determined from withdrawal/deposit columns)
            if trans_type is None:
                trans_type = _determine_transaction_type(description)
                if trans_type == 'Debit' and amount > 0:
                    amount = -amount
            
            transaction = {
                'date': trans_date,
                'description': description,
                'amount': amount,
                'balance': balance,
                'type': trans_type
            }
            
            transactions.append(transaction)
            logger.info(f"Extracted transaction: {trans_date.strftime('%m/%d/%y')} - {description} - {amount}")
            
        except Exception as e:
            logger.error(f"Error processing table row {row_idx}: {row}, error: {e}")
            continue
    
    return transactions


async def run_extraction(file_path: str) -> List[Dict[str, Any]]:
    """
    Extract transactions from PDF using table extraction first, falling back to OCR+regex.
    
    Args:
        file_path: Path to the PDF file to process
        
    Returns:
        List of transaction dictionaries
        
    Raises:
        FileNotFoundError: If the PDF file doesn't exist
        Exception: If both table extraction and OCR processing fail
    """
    try:
        # Check if file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF file not found: {file_path}")
        
        logger.info(f"Starting extraction for: {file_path}")
        
        all_transactions = []
        
        # Try table extraction with pdfplumber
        try:
            logger.info("Attempting table extraction with pdfplumber")
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    logger.info(f"Processing page {page_num + 1} for tables")
                    
                    # Extract tables from the page
                    tables = page.extract_tables()
                    
                    if tables:
                        logger.info(f"Found {len(tables)} tables on page {page_num + 1}")
                        
                        for table_idx, table in enumerate(tables):
                            if table and len(table) > 1:  # Need at least header + 1 data row
                                logger.info(f"Processing table {table_idx + 1} with {len(table)} rows")
                                
                                # Extract transactions from this table
                                table_transactions = _extract_table_transactions(table)
                                all_transactions.extend(table_transactions)
                                
                                logger.info(f"Extracted {len(table_transactions)} transactions from table {table_idx + 1}")
                    else:
                        logger.info(f"No tables found on page {page_num + 1}, will fall back to OCR")
                        
                        # Fallback to OCR for this page
                        try:
                            # Extract OCR text for just this page
                            ocr_results = await run_ocr(file_path)
                            if page_num < len(ocr_results):
                                page_text = ocr_results[page_num]
                                
                                # Parse using existing regex parsers
                                page_transactions = []
                                page_transactions.extend(_parse_standard_us_format(page_text))
                                page_transactions.extend(_parse_uk_format(page_text))
                                
                                # Convert TransactionData objects to dictionaries
                                for trans in page_transactions:
                                    transaction_dict = {
                                        'date': trans.date,
                                        'description': trans.payee,
                                        'amount': trans.amount,
                                        'balance': trans.balance,
                                        'type': trans.type
                                    }
                                    all_transactions.append(transaction_dict)
                                
                                logger.info(f"Fallback OCR found {len(page_transactions)} transactions on page {page_num + 1}")
                        except Exception as ocr_error:
                            logger.error(f"OCR fallback failed for page {page_num + 1}: {ocr_error}")
        
        except Exception as table_error:
            logger.error(f"Table extraction failed: {table_error}")
            logger.info("Falling back to full OCR processing")
            
            # Full fallback to OCR + regex parsing
            try:
                ocr_results = await run_ocr(file_path)
                parsed_transactions = parse_transactions(ocr_results)
                
                # Convert TransactionData objects to dictionaries
                for trans in parsed_transactions:
                    transaction_dict = {
                        'date': trans.date,
                        'description': trans.payee,
                        'amount': trans.amount,
                        'balance': trans.balance,
                        'type': trans.type
                    }
                    all_transactions.append(transaction_dict)
                
                logger.info(f"OCR fallback extracted {len(parsed_transactions)} transactions")
                
            except Exception as ocr_error:
                logger.error(f"OCR fallback also failed: {ocr_error}")
                raise Exception(f"Both table extraction and OCR processing failed: {str(ocr_error)}")
        
        logger.info(f"Total transactions extracted: {len(all_transactions)}")
        return all_transactions
        
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        raise e
    except Exception as e:
        logger.error(f"Extraction failed for {file_path}: {e}")
        raise Exception(f"Extraction processing failed: {str(e)}") 

async def run_structure_extraction(file_path: str) -> List[Dict[str, Any]]:
    """
    Extract transactions using PaddleOCR structure analysis.
    
    Args:
        file_path: Path to the PDF file to process
        
    Returns:
        List of transaction dictionaries
    """
    try:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF file not found: {file_path}")
        
        logger.info(f"Starting structure-based extraction for: {file_path}")
        
        # Run structure analysis
        structure_results = await run_structure_analysis(file_path)
        
        # Extract tables from structure results
        tables = extract_tables_from_structure(structure_results)
        
        # Convert tables to transactions
        all_transactions = []
        for table_info in tables:
            table_data = table_info['table_data']
            page_num = table_info['page']
            
            logger.info(f"Processing table from page {page_num} with {len(table_data)} rows")
            
            # Use existing table processing logic
            table_transactions = _extract_table_transactions(table_data)
            all_transactions.extend(table_transactions)
            
            logger.info(f"Extracted {len(table_transactions)} transactions from page {page_num}")
        
        logger.info(f"Total transactions extracted via structure analysis: {len(all_transactions)}")
        return all_transactions
        
    except Exception as e:
        logger.error(f"Structure extraction failed for {file_path}: {e}")
        # Re-raise FileNotFoundError as-is, wrap other exceptions
        if isinstance(e, FileNotFoundError):
            raise e
        raise Exception(f"Structure extraction failed: {str(e)}")

def parse_structure_tables(structure_results: List[Dict[str, Any]]) -> List[TransactionData]:
    """
    Parse transactions from PaddleOCR structure analysis results.
    
    Args:
        structure_results: Structure analysis results containing tables
        
    Returns:
        List of TransactionData objects
    """
    transactions = []
    
    # Extract tables from structure results
    tables = extract_tables_from_structure(structure_results)
    
    # Process each table
    for table_info in tables:
        table_data = table_info['table_data']
        
        # Convert table to transaction dictionaries
        table_transactions = _extract_table_transactions(table_data)
        
        # Convert dictionaries to TransactionData objects
        for trans_dict in table_transactions:
            try:
                transaction = TransactionData(
                    date=trans_dict['date'],
                    payee=trans_dict['description'],
                    amount=trans_dict['amount'],
                    type=trans_dict['type'],
                    balance=trans_dict.get('balance'),
                    currency=trans_dict.get('currency', 'USD')
                )
                transactions.append(transaction)
            except Exception as e:
                logger.error(f"Error creating TransactionData: {e}")
                continue
    
    return transactions 