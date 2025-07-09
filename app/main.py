from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import os
from dotenv import load_dotenv
from datetime import datetime
import shutil

from .db import get_db
from .models import Statement, Client

# Load environment variables
load_dotenv()

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
    
    # Create Statement record in database
    statement = Statement(
        client_id=client_id,  # Use the provided client_id parameter
        file_path=file_path
    )
    
    db.add(statement)
    await db.commit()
    await db.refresh(statement)
    
    return {"statement_id": statement.id}

# Add your API routes here as you develop them
# from .routes import auth, upload, chat, history
# app.include_router(auth.router, prefix="/auth", tags=["auth"])
# app.include_router(upload.router, prefix="/upload", tags=["upload"])
# app.include_router(chat.router, prefix="/chat", tags=["chat"])
# app.include_router(history.router, prefix="/history", tags=["history"]) 