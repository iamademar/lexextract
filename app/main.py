from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
import os
from dotenv import load_dotenv

from .db import get_db, engine, Base

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

@app.on_event("startup")
async def startup_event():
    """Create database tables on startup"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "LexExtract API is running"}

# Add your API routes here as you develop them
# from .routes import auth, upload, chat, history
# app.include_router(auth.router, prefix="/auth", tags=["auth"])
# app.include_router(upload.router, prefix="/upload", tags=["upload"])
# app.include_router(chat.router, prefix="/chat", tags=["chat"])
# app.include_router(history.router, prefix="/history", tags=["history"]) 