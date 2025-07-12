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
    
    # Process PDF with structure analysis first, then fallback to regex parsing if needed
    try:
        logger.info(f"Starting structure analysis for file: {file_path}")
        transactions_data = await run_structure_extraction(file_path)
        logger.info(f"Structure analysis completed. Found {len(transactions_data)} transactions")
        
        # If structure analysis found no transactions, fall back to regex-based parsing
        if not transactions_data:
            logger.info("No transactions found in structure analysis, falling back to regex-based extraction")
            try:
                transactions_data = await run_extraction(file_path)
                logger.info(f"Regex-based extraction completed. Found {len(transactions_data)} transactions")
            except Exception as regex_error:
                logger.warning(f"Regex-based extraction also failed: {regex_error}")
                transactions_data = []
        
        # For database storage, also get OCR text for backup/reference
        ocr_results = []
        try:
            ocr_results = await run_ocr(file_path)
            logger.info(f"OCR backup completed. Extracted {len(ocr_results)} pages")
        except Exception as ocr_error:
            logger.warning(f"OCR backup failed: {ocr_error}")
            ocr_results = ["Structure analysis used - OCR backup not available"]
            
    except Exception as e:
        logger.warning(f"Structure analysis failed: {e}, falling back to regex-based extraction")
        try:
            # Fall back to current extraction method
            transactions_data = await run_extraction(file_path)
            logger.info(f"Fallback extraction completed. Found {len(transactions_data)} transactions")
            
            # Get OCR text
            ocr_results = await run_ocr(file_path)
            logger.info(f"OCR completed. Extracted {len(ocr_results)} pages")
        except Exception as fallback_error:
            logger.error(f"Both structure analysis and regex extraction failed: {fallback_error}")
            if os.path.exists(file_path):
                os.remove(file_path)
            raise HTTPException(status_code=500, detail=f"All extraction methods failed: {str(fallback_error)}")
    
    # Create Statement and Transaction records in database
    # Use a single transaction to ensure data consistency
    statement = Statement(
        client_id=client_id,  # Use the provided client_id parameter
        file_path=file_path,
        ocr_text="\n".join(ocr_results)  # Store all pages as joined text
    )
    
    db.add(statement)
    await db.flush()  # Flush to get the statement ID without committing
    
    # Create Transaction records in the same transaction
    created_transactions = []
    if transactions_data:
        try:
            for trans_data in transactions_data:
                transaction = Transaction(
                    statement_id=statement.id,
                    date=trans_data['date'].date() if hasattr(trans_data['date'], 'date') else trans_data['date'],
                    payee=trans_data['description'],  # Updated key name
                    amount=trans_data['amount'],
                    type=trans_data['type'],
                    balance=trans_data.get('balance'),  # Use .get() in case balance is None
                    currency=trans_data.get('currency', 'USD')  # Default currency if not specified
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
        # If commit fails, we still have the statement object in memory
        raise HTTPException(status_code=500, detail=f"Database save failed: {str(e)}")
    
    await db.refresh(statement)
    
    return {
        "statement_id": statement.id,
        "pages_processed": len(ocr_results),
        "transactions_found": len(transactions_data),
        "transactions_saved": len(created_transactions),
        "ocr_preview": ocr_results[0][:200] + "..." if ocr_results and len(ocr_results[0]) > 200 else ocr_results[0] if ocr_results else ""
    }

# Add your API routes here as you develop them
# from .routes import auth, upload, chat, history
# app.include_router(auth.router, prefix="/auth", tags=["auth"])
# app.include_router(upload.router, prefix="/upload", tags=["upload"])
# app.include_router(chat.router, prefix="/chat", tags=["chat"])
# app.include_router(history.router, prefix="/history", tags=["history"]) 