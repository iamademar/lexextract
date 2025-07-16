import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from ..db import get_db
from ..models import Statement, Transaction
from .parser import parse_transactions, run_extraction, run_structure_extraction
from .ocr import run_unified_ocr_pipeline, run_ocr

logger = logging.getLogger(__name__)

async def process_statement(statement_id: int):
    """
    Background task to process a statement and extract transactions
    Updates progress and status throughout the process
    """
    # Get database session
    async for db in get_db():
        try:
            # Load statement
            result = await db.execute(select(Statement).where(Statement.id == statement_id))
            statement = result.scalar_one_or_none()
            
            if not statement:
                logger.error(f"Statement {statement_id} not found")
                return
            
            # Set status to processing
            statement.status = 'processing'
            statement.progress = 10
            await db.commit()
            logger.info(f"Started processing statement {statement_id}")
            
            # Process PDF with unified OCR pipeline
            try:
                logger.info(f"Starting unified OCR processing for statement {statement_id}")
                ocr_results = run_unified_ocr_pipeline(statement.file_path)
                statement.progress = 40
                await db.commit()
                logger.info(f"Unified OCR completed for statement {statement_id}")
                
                # Parse transactions using enhanced parser
                transactions_data = parse_transactions(ocr_results)
                statement.progress = 70
                await db.commit()
                logger.info(f"Enhanced parsing completed for statement {statement_id}. Found {len(transactions_data)} transactions")
                
                # Get OCR text for backup/reference
                ocr_text_pages = [page_result.get('full_text', '') for page_result in ocr_results]
                statement.ocr_text = "\n".join(ocr_text_pages) if ocr_text_pages else ""
                
            except Exception as e:
                logger.error(f"Unified OCR processing failed for statement {statement_id}: {e}")
                logger.info("Falling back to legacy extraction methods")
                
                try:
                    # Fallback to structure analysis first
                    transactions_data = await run_structure_extraction(statement.file_path)
                    statement.progress = 60
                    await db.commit()
                    logger.info(f"Structure analysis fallback completed for statement {statement_id}. Found {len(transactions_data)} transactions")
                    
                    # If structure analysis found no transactions, fall back to regex-based parsing
                    if not transactions_data:
                        logger.info(f"No transactions found in structure analysis for statement {statement_id}, falling back to regex-based extraction")
                        transactions_data = await run_extraction(statement.file_path)
                        logger.info(f"Regex-based extraction completed for statement {statement_id}. Found {len(transactions_data)} transactions")
                    
                    # Get OCR text for backup
                    ocr_text_pages = await run_ocr(statement.file_path)
                    statement.ocr_text = "\n".join(ocr_text_pages) if ocr_text_pages else ""
                    statement.progress = 70
                    await db.commit()
                    
                except Exception as fallback_error:
                    logger.error(f"All extraction methods failed for statement {statement_id}: {fallback_error}")
                    statement.status = 'failed'
                    statement.progress = 0
                    await db.commit()
                    return
            
            # Create Transaction records
            transactions_created = 0
            if transactions_data:
                try:
                    total_transactions = len(transactions_data)
                    for i, trans_data in enumerate(transactions_data):
                        # Handle different data formats
                        if hasattr(trans_data, 'date'):
                            # TransactionData object from unified parser
                            transaction = Transaction(
                                statement_id=statement.id,
                                date=trans_data.date.date() if hasattr(trans_data.date, 'date') else trans_data.date,
                                payee=trans_data.payee,
                                amount=float(trans_data.amount),
                                type=trans_data.type,
                                balance=float(trans_data.balance) if trans_data.balance else None,
                                currency=trans_data.currency
                            )
                        else:
                            # Dictionary format from legacy parsers
                            transaction = Transaction(
                                statement_id=statement.id,
                                date=trans_data['date'].date() if hasattr(trans_data['date'], 'date') else trans_data['date'],
                                payee=trans_data.get('description', trans_data.get('payee', '')),
                                amount=float(trans_data['amount']),
                                type=trans_data['type'],
                                balance=float(trans_data['balance']) if trans_data.get('balance') else None,
                                currency=trans_data.get('currency', 'GBP')
                            )
                        
                        db.add(transaction)
                        transactions_created += 1
                        
                        # Update progress incrementally
                        progress_increment = 25 / total_transactions
                        statement.progress = min(95, int(70 + (i + 1) * progress_increment))
                        await db.commit()
                    
                    logger.info(f"Created {transactions_created} transaction records for statement {statement_id}")
                    
                except Exception as e:
                    logger.error(f"Failed to create transaction records for statement {statement_id}: {e}")
                    statement.status = 'failed'
                    await db.commit()
                    return
            
            # Mark as completed
            statement.status = 'completed'
            statement.progress = 100
            await db.commit()
            
            logger.info(f"Successfully processed statement {statement_id}: {transactions_created} transactions created")
            
        except Exception as e:
            logger.error(f"Unexpected error processing statement {statement_id}: {e}")
            try:
                # Try to mark as failed
                result = await db.execute(select(Statement).where(Statement.id == statement_id))
                statement = result.scalar_one_or_none()
                if statement:
                    statement.status = 'failed'
                    statement.progress = 0
                    await db.commit()
            except Exception as cleanup_error:
                logger.error(f"Failed to mark statement {statement_id} as failed: {cleanup_error}")
        
        finally:
            await db.close()
        
        break  # Exit the async generator loop