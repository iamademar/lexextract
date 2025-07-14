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


def parse_date(date_str: str) -> datetime:
    """
    Parse date string with robust handling of various formats.
    
    Args:
        date_str: Date string in various formats
        
    Returns:
        datetime object
    """
    if not date_str or not date_str.strip():
        raise ValueError("Empty date string")
    
    date_str = date_str.strip()
    
    # Try different date formats
    date_formats = [
        # US formats
        '%m/%d/%Y',      # 10/15/2024
        '%m/%d/%y',      # 10/15/24
        '%m/%d',         # 10/15 (current year)
        # UK formats
        '%d/%m/%Y',      # 15/10/2024
        '%d/%m/%y',      # 15/10/24
        '%d/%m',         # 15/10 (current year)
        # Date with month name
        '%d %B %Y',      # 15 October 2024
        '%d %B',         # 15 October (current year)
        '%d %b %Y',      # 15 Oct 2024
        '%d %b',         # 15 Oct (current year)
        # Compact formats
        '%d%b',          # 19Jan
        '%d%B',          # 19January
        # ISO format
        '%Y-%m-%d',      # 2024-10-15
    ]
    
    for date_format in date_formats:
        try:
            parsed_date = datetime.strptime(date_str, date_format)
            # If no year specified, use current year
            if parsed_date.year == 1900:
                parsed_date = parsed_date.replace(year=datetime.now().year)
            return parsed_date
        except ValueError:
            continue
    
    # Handle special cases like "1 February" or "19Jan"
    # Try to parse month names with day
    month_names = {
        'january': 1, 'jan': 1, 'february': 2, 'feb': 2, 'march': 3, 'mar': 3,
        'april': 4, 'apr': 4, 'may': 5, 'june': 6, 'jun': 6, 'july': 7, 'jul': 7,
        'august': 8, 'aug': 8, 'september': 9, 'sep': 9, 'october': 10, 'oct': 10,
        'november': 11, 'nov': 11, 'december': 12, 'dec': 12
    }
    
    # Try to extract day and month from formats like "1 February" or "19Jan"
    for month_name, month_num in month_names.items():
        if month_name.lower() in date_str.lower():
            # Extract day number
            day_match = re.search(r'(\d+)', date_str)
            if day_match:
                day = int(day_match.group(1))
                return datetime(datetime.now().year, month_num, day)
    
    raise ValueError(f"Unable to parse date: {date_str}")


def parse_mmdd_to_date(date_str: str, statement_year: int) -> datetime:
    """
    Parse MM/DD format dates to a specific statement year.
    
    Args:
        date_str: Date string in MM/DD format
        statement_year: Year to use for the parsed date
        
    Returns:
        datetime object with the specified year
    """
    month, day = map(int, date_str.split('/'))
    return datetime(statement_year, month, day)


def parse_transactions(ocr_output: List[dict]) -> List[TransactionData]:
    """
    Extract structured transaction data from unified OCR output.
    
    Args:
        ocr_output: List of dictionaries from unified OCR pipeline with 'page', 'tables', 'full_text'
        
    Returns:
        List of TransactionData objects representing parsed transactions
    """
    if not ocr_output:
        logger.warning("No OCR output provided for parsing")
        return []

    transactions = []
    
    for page_result in ocr_output:
        if not isinstance(page_result, dict):
            logger.warning(f"Invalid page result format: {type(page_result)}")
            continue
            
        page_num = page_result.get('page', 'unknown')
        tables = page_result.get('tables', [])
        full_text = page_result.get('full_text', '')
        
        logger.info(f"Processing page {page_num}: {len(tables)} tables, {len(full_text)} characters")
        
        page_transactions = []
        
        # Try table extraction first if tables are available
        if tables:
            logger.info(f"Attempting table extraction for page {page_num}")
            for table_idx, table in enumerate(tables):
                if table and len(table) > 1:  # Need at least header + 1 data row
                    table_transactions = _extract_table_transactions(table)
                    
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
                            page_transactions.append(transaction)
                        except Exception as e:
                            logger.error(f"Error creating TransactionData from table: {e}")
                            continue
                    
                    logger.info(f"Table {table_idx} on page {page_num} yielded {len(table_transactions)} transactions")
        
        # If no transactions from tables, try text parsing
        if not page_transactions and full_text:
            logger.info(f"Attempting text parsing for page {page_num}")
            
            # Try different bank statement formats
            page_transactions.extend(_parse_standard_us_format(full_text))
            page_transactions.extend(_parse_uk_format(full_text))
            page_transactions.extend(_parse_detailed_uk_format(full_text))  # New format for bank-statement-2
            page_transactions.extend(_parse_compact_format(full_text))      # New format for bank-statement-4
            
            logger.info(f"Text parsing on page {page_num} yielded {len(page_transactions)} transactions")
        
        if page_transactions:
            transactions.extend(page_transactions)
            logger.info(f"Page {page_num} total: {len(page_transactions)} transactions")
        else:
            logger.warning(f"No transactions found on page {page_num}")
            # Log a sample of the text for debugging
            if full_text:
                sample_text = full_text[:200] + "..." if len(full_text) > 200 else full_text
                logger.debug(f"Sample text from page {page_num}: {sample_text}")
    
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
    
    # Pattern for transaction lines - tightened to be non-greedy
    transaction_patterns = [
        # Pattern 1: Date Description Amount Balance (debit transactions)
        r'(\d{1,2}/\d{1,2}(?:/\d{2,4})?)\s+(.+?)\s+(\d+\.\d{2})\s+(\d+\.\d{2})',
        # Pattern 2: Date Description Credit Amount Balance  
        r'(\d{1,2}/\d{1,2}(?:/\d{2,4})?)\s+(.+?)\s+(\d+\.\d{2})\s+(\d+\.\d{2})',
        # Pattern 3: Simple date amount pattern
        r'(\d{1,2}/\d{1,2}(?:/\d{2,4})?)\s+(.+?)\s+(\d+\.\d{2})'
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
                    
                    # Parse date with robust year handling
                    trans_date = parse_date(date_str)
                    
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
    
    # UK date patterns: DD/MM/YYYY or DD-MM-YYYY - tightened to be non-greedy
    uk_patterns = [
        # Pattern for UK format: DD/MM Description Amount Balance
        r'(\d{1,2}/\d{1,2}(?:/\d{2,4})?)\s+(.+?)\s+£?(\d+\.\d{2})\s*£?(\d+\.\d{2})?',
        # Pattern for DD-MM format
        r'(\d{1,2}-\d{1,2}(?:-\d{2,4})?)\s+(.+?)\s+£?(\d+\.\d{2})\s*£?(\d+\.\d{2})?'
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


def _parse_detailed_uk_format(text: str) -> List[TransactionData]:
    """Parse transactions from detailed UK format (like bank-statement-2.pdf)"""
    transactions = []
    
    # This format has lines like:
    # "1 February Card payment - High St Petrol Station 24.50 39,975.50"
    # "4 February YourJob BiWeekly Payment 2,575.00 42,500.50"
    
    # Pattern to match: Date Description Amount Balance
    # Where date is like "1 February" or "16 February"
    # Amount could be debit or credit
    patterns = [
        # Format: "Date Description Amount Balance"
        r'(\d{1,2} \w+)\s+(.+?)\s+([£$€]?\d{1,3}(?:,\d{3})*\.?\d{0,2})\s+([£$€]?\d{1,3}(?:,\d{3})*\.?\d{0,2})',
        # Alternative format with more flexible spacing
        r'(\d{1,2} \w+)\s+(.+?)\s+([£$€]?\d+(?:,\d{3})*\.?\d{0,2})\s+([£$€]?\d+(?:,\d{3})*\.?\d{0,2})',
    ]
    
    lines = text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                try:
                    date_str = match.group(1)
                    description = match.group(2).strip()
                    amount_str = match.group(3)
                    balance_str = match.group(4)
                    
                    # Skip if description is too short or looks like a header
                    if len(description) < 3 or description.lower() in ['description', 'balance', 'amount']:
                        continue
                    
                    # Parse date
                    trans_date = parse_date(date_str)
                    
                    # Parse amount and balance
                    amount = Decimal(_normalize_numeric_string(amount_str))
                    balance = Decimal(_normalize_numeric_string(balance_str))
                    
                    # Determine transaction type based on description
                    trans_type = _determine_transaction_type(description)
                    
                    # For debits, make amount negative
                    if trans_type == 'Debit':
                        amount = -amount
                    
                    transaction = TransactionData(
                        date=trans_date,
                        payee=description,
                        amount=amount,
                        type=trans_type,
                        balance=balance,
                        currency="GBP"  # UK format typically uses GBP
                    )
                    
                    transactions.append(transaction)
                    break  # Found a match, move to next line
                    
                except Exception as e:
                    logger.error(f"Error parsing detailed UK transaction from line: {line}, error: {e}")
                    continue
    
    return transactions


def _parse_compact_format(text: str) -> List[TransactionData]:
    """Parse transactions from compact format (like bank-statement-4.pdf)"""
    transactions = []
    
    # This format has lines like:
    # "19Jan Woolworths 47.80 952.20"
    # "23Jan Credit wage 1,550.21 2,118.70"
    # Format: Date Transaction [Debit] [Credit] Balance
    
    # Pattern to match transactions
    patterns = [
        # Format: "Date Description Amount Balance" (single amount)
        r'(\d{1,2}[A-Za-z]{3})\s+(.+?)\s+([£$€]?\d{1,3}(?:,\d{3})*\.?\d{0,2})\s+([£$€]?\d{1,3}(?:,\d{3})*\.?\d{0,2})',
        # Format: "Date Description Debit Credit Balance" (where one of debit/credit is empty)
        r'(\d{1,2}[A-Za-z]{3})\s+(.+?)\s+([£$€]?\d+(?:,\d{3})*\.?\d{0,2})\s+([£$€]?\d+(?:,\d{3})*\.?\d{0,2})',
    ]
    
    lines = text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                try:
                    date_str = match.group(1)
                    description = match.group(2).strip()
                    amount_str = match.group(3)
                    balance_str = match.group(4)
                    
                    # Skip if description is too short or looks like a header
                    if len(description) < 3 or description.lower() in ['transaction', 'description', 'balance', 'debit', 'credit']:
                        continue
                    
                    # Parse date
                    trans_date = parse_date(date_str)
                    
                    # Parse amount and balance
                    amount = Decimal(_normalize_numeric_string(amount_str))
                    balance = Decimal(_normalize_numeric_string(balance_str))
                    
                    # Determine transaction type based on description
                    trans_type = _determine_transaction_type(description)
                    
                    # For debits, make amount negative
                    if trans_type == 'Debit':
                        amount = -amount
                    
                    transaction = TransactionData(
                        date=trans_date,
                        payee=description,
                        amount=amount,
                        type=trans_type,
                        balance=balance,
                        currency="USD"  # Assuming USD for this format
                    )
                    
                    transactions.append(transaction)
                    break  # Found a match, move to next line
                    
                except Exception as e:
                    logger.error(f"Error parsing compact transaction from line: {line}, error: {e}")
                    continue
    
    return transactions


def _determine_transaction_type(description: str) -> str:
    """Determine if transaction is Credit or Debit based on description"""
    description_lower = description.lower()
    
    # Strong debit indicators (checked first to avoid conflicts)
    strong_debit_keywords = [
        'card payment', 'pos purchase', 'atm withdrawal', 'cash withdrawal', 
        'direct debit', 'service charge', 'monthly rent', 'cash wdl'
    ]
    
    # Strong credit indicators (checked first to avoid conflicts)
    strong_credit_keywords = [
        'preauthorized credit', 'interest credit', 'salary credit', 'payroll deposit',
        'biweekly payment', 'direct deposit', 'credit wage', 'wage credit'
    ]
    
    # Check strong indicators first
    for keyword in strong_debit_keywords:
        if keyword in description_lower:
            return 'Debit'
    
    for keyword in strong_credit_keywords:
        if keyword in description_lower:
            return 'Credit'
    
    # Regular credit indicators
    credit_keywords = [
        'credit', 'deposit', 'interest', 'payroll', 'refund', 'salary', 
        'pension', 'benefit', 'transfer in', 'wage'
    ]
    
    # Regular debit indicators  
    debit_keywords = [
        'purchase', 'pos', 'withdrawal', 'atm', 'check', 'payment',
        'debit', 'fee', 'charge', 'transfer out', 'wdl'
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
                                
                                # Parse using unified format
                                ocr_unified_format = [{
                                    'page': page_num + 1,
                                    'tables': [],
                                    'full_text': page_text
                                }]
                                page_transactions = parse_transactions(ocr_unified_format)
                                
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
                # Convert old format to new format for parse_transactions
                ocr_unified_format = []
                for page_num, page_text in enumerate(ocr_results, 1):
                    ocr_unified_format.append({
                        'page': page_num,
                        'tables': [],
                        'full_text': page_text
                    })
                
                parsed_transactions = parse_transactions(ocr_unified_format)
                
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
    Extract transactions using unified OCR structure analysis (Tesseract + Camelot).
    
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
    Parse transactions from unified OCR structure analysis results (Tesseract + Camelot).
    
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