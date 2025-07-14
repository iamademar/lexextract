from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import os
import logging
from dotenv import load_dotenv
from datetime import datetime
import shutil

from .db import get_db
from .models import Statement, Client, Transaction
from .services.ocr import run_ocr
from .services.parser import parse_transactions, run_extraction, run_structure_extraction

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI instance
app = FastAPI(
    title="LexExtract API",
    description="PDF bank statement extraction and analysis tool",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database tables are now managed by Alembic migrations
# Run: alembic upgrade head

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "LexExtract API is running"}

@app.post("/upload/statement", status_code=201)
async def upload_statement(
    file: UploadFile = File(...),
    client_id: int = Query(..., description="Client ID for the statement"),
    db: AsyncSession = Depends(get_db)
):
    """Upload a PDF bank statement for processing"""
    
    # Validate PDF MIME type
    if not file.content_type or not file.content_type.startswith("application/pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    # Read file content to check size
    file_content = await file.read()
    file_size_mb = len(file_content) / (1024 * 1024)
    
    # Validate file size (≤10 MB)
    if file_size_mb > 10:
        raise HTTPException(status_code=400, detail="File size must be ≤10 MB")
    
    # Reset file pointer
    await file.seek(0)
    
    # Validate that client exists
    client_result = await db.execute(select(Client).where(Client.id == client_id))
    client = client_result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail=f"Client with ID {client_id} not found")
    
    # Create uploads directory if it doesn't exist
    uploads_dir = "data/uploads"
    os.makedirs(uploads_dir, exist_ok=True)
    
    # Generate timestamp-based filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{file.filename}"
    file_path = os.path.join(uploads_dir, filename)
    
    # Save file to disk
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Process PDF with unified OCR pipeline and enhanced transaction parsing
    try:
        logger.info(f"Starting unified OCR processing for file: {file_path}")
        
        # Use the unified OCR pipeline that combines Camelot + Tesseract intelligently
        from .services.ocr import run_unified_ocr_pipeline
        ocr_results = run_unified_ocr_pipeline(file_path)
        logger.info(f"Unified OCR completed. Processed {len(ocr_results)} pages")
        
        # Use the enhanced parser that handles multiple formats
        transactions_data = parse_transactions(ocr_results)
        logger.info(f"Enhanced parsing completed. Found {len(transactions_data)} transactions")
        
        # Convert TransactionData objects to dictionaries for database storage
        transactions_dicts = []
        for trans in transactions_data:
            transaction_dict = {
                'date': trans.date,
                'description': trans.payee,
                'amount': trans.amount,
                'balance': trans.balance,
                'type': trans.type,
                'currency': trans.currency
            }
            transactions_dicts.append(transaction_dict)
        
        # Get OCR text for backup/reference
        ocr_text_pages = [page_result.get('full_text', '') for page_result in ocr_results]
        
    except Exception as e:
        logger.error(f"Unified OCR processing failed: {e}")
        logger.info("Falling back to legacy extraction methods")
        
        try:
            # Fallback to structure analysis first
            transactions_dicts = await run_structure_extraction(file_path)
            logger.info(f"Structure analysis fallback completed. Found {len(transactions_dicts)} transactions")
            
            # If structure analysis found no transactions, fall back to regex-based parsing
            if not transactions_dicts:
                logger.info("No transactions found in structure analysis, falling back to regex-based extraction")
                transactions_dicts = await run_extraction(file_path)
                logger.info(f"Regex-based extraction completed. Found {len(transactions_dicts)} transactions")
            
            # Get OCR text for backup
            ocr_text_pages = await run_ocr(file_path)
            logger.info(f"OCR backup completed. Extracted {len(ocr_text_pages)} pages")
        except Exception as fallback_error:
            logger.error(f"All extraction methods failed: {fallback_error}")
            if os.path.exists(file_path):
                os.remove(file_path)
            raise HTTPException(status_code=500, detail=f"All extraction methods failed: {str(fallback_error)}")
    
    # Create Statement and Transaction records in database
    statement = Statement(
        client_id=client_id,
        file_path=file_path,
        ocr_text="\n".join(ocr_text_pages) if ocr_text_pages else ""
    )
    
    db.add(statement)
    await db.flush()  # Flush to get the statement ID without committing
    
    # Create Transaction records in the same transaction
    created_transactions = []
    if transactions_dicts:
        try:
            for trans_data in transactions_dicts:
                transaction = Transaction(
                    statement_id=statement.id,
                    date=trans_data['date'].date() if hasattr(trans_data['date'], 'date') else trans_data['date'],
                    payee=trans_data['description'],
                    amount=trans_data['amount'],
                    type=trans_data['type'],
                    balance=trans_data.get('balance'),
                    currency=trans_data.get('currency', 'USD')
                )
                db.add(transaction)
                created_transactions.append(transaction)
            
            logger.info(f"Created {len(created_transactions)} transaction objects, committing to database...")
        except Exception as e:
            logger.error(f"Failed to create transaction objects: {e}")
            # Continue without transactions
    
    # Commit everything together (Statement + Transactions)
    try:
        await db.commit()
        logger.info(f"Successfully saved Statement {statement.id} with {len(created_transactions)} transactions")
    except Exception as e:
        logger.error(f"Failed to save to database: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Database save failed: {str(e)}")
    
    await db.refresh(statement)
    
    return {
        "statement_id": statement.id,
        "pages_processed": len(ocr_text_pages) if ocr_text_pages else 0,
        "transactions_found": len(transactions_dicts),
        "transactions_saved": len(created_transactions),
        "ocr_preview": ocr_text_pages[0][:200] + "..." if ocr_text_pages and len(ocr_text_pages[0]) > 200 else ocr_text_pages[0] if ocr_text_pages else ""
    }

# Add your API routes here as you develop them
from .routers import chat
app.include_router(chat.router, tags=["chat"])
# from .routes import auth, upload, history
# app.include_router(auth.router, prefix="/auth", tags=["auth"])
# app.include_router(upload.router, prefix="/upload", tags=["upload"])
# app.include_router(history.router, prefix="/history", tags=["history"]) 