import os
import shutil
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from ..db import get_db
from ..models import Statement, Client, Transaction
from ..schemas.statement import StatementRead, StatementProgress, TransactionRead

router = APIRouter()

@router.get("/", response_model=List[StatementRead])
async def list_statements(db: AsyncSession = Depends(get_db)):
    """Get all statements"""
    result = await db.execute(select(Statement))
    return result.scalars().all()

@router.post("/", response_model=StatementRead, status_code=201)
async def upload_statement(
    background_tasks: BackgroundTasks,
    client_id: int = Query(..., description="Client ID for the statement"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """Upload a PDF statement for processing"""
    
    # Validate client_id exists
    client_result = await db.execute(select(Client).where(Client.id == client_id))
    client = client_result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail=f"Client with ID {client_id} not found")
    
    # Validate file is PDF
    if not file.content_type or not file.content_type.startswith("application/pdf"):
        raise HTTPException(status_code=422, detail="Only PDF files are allowed")
    
    # Read file content to check size
    file_content = await file.read()
    file_size_mb = len(file_content) / (1024 * 1024)
    
    # Validate file size (≤10 MB)
    if file_size_mb > 10:
        raise HTTPException(status_code=422, detail="File size must be ≤10 MB")
    
    # Reset file pointer
    await file.seek(0)
    
    # Create uploads directory if it doesn't exist
    uploads_dir = "data/uploads/statements"
    os.makedirs(uploads_dir, exist_ok=True)
    
    # Create statement record first to get ID
    statement = Statement(
        client_id=client_id,
        file_path="",  # Will update after saving file
        status='pending',
        progress=0
    )
    
    db.add(statement)
    await db.flush()  # Get the ID without committing
    
    # Generate filename using statement ID
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{statement.id}_{timestamp}_{file.filename}"
    file_path = os.path.join(uploads_dir, filename)
    
    # Update statement with file path
    statement.file_path = file_path
    
    try:
        # Save file to disk
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Commit the statement record
        await db.commit()
        await db.refresh(statement)
        
        # Schedule background processing
        from ..services.statements import process_statement
        background_tasks.add_task(process_statement, statement.id)
        
        return statement
        
    except Exception as e:
        # Cleanup on error
        await db.rollback()
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

@router.get("/{statement_id}/progress", response_model=StatementProgress)
async def get_statement_progress(statement_id: int, db: AsyncSession = Depends(get_db)):
    """Get processing progress for a statement"""
    result = await db.execute(select(Statement).where(Statement.id == statement_id))
    statement = result.scalar_one_or_none()
    
    if not statement:
        raise HTTPException(status_code=404, detail="Statement not found")
    
    return StatementProgress(progress=statement.progress, status=statement.status)

@router.get("/{statement_id}/transactions", response_model=List[TransactionRead])
async def get_statement_transactions(statement_id: int, db: AsyncSession = Depends(get_db)):
    """Get all transactions for a statement"""
    # First verify statement exists
    statement_result = await db.execute(select(Statement).where(Statement.id == statement_id))
    statement = statement_result.scalar_one_or_none()
    
    if not statement:
        raise HTTPException(status_code=404, detail="Statement not found")
    
    # Get transactions
    result = await db.execute(
        select(Transaction).where(Transaction.statement_id == statement_id)
    )
    return result.scalars().all()

@router.get("/{statement_id}", response_model=StatementRead)
async def get_statement(statement_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific statement"""
    result = await db.execute(select(Statement).where(Statement.id == statement_id))
    statement = result.scalar_one_or_none()
    
    if not statement:
        raise HTTPException(status_code=404, detail="Statement not found")
    
    return statement