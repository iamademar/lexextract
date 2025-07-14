from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging
import os
import re

from app.services.mistral_chat import query_mistral
from sqlalchemy import create_engine
from langchain_experimental.sql.base import SQLDatabaseChain
from langchain.sql_database import SQLDatabase
from app.llms.mistral_llm import MistralLLM

from starlette.concurrency import run_in_threadpool
import sqlparse

logger = logging.getLogger(__name__)

router = APIRouter()

class ChatRequest(BaseModel):
    client_id: Optional[int] = None
    message: str

class ChatResponse(BaseModel):
    client_id: Optional[int] = None
    response: str
    sql: Optional[str] = None

# ——————————————
# Setup LangChain chain once at import time, using MistralLLM
# ——————————————
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql+psycopg2://postgres:password@postgres/lexextract"
).replace("postgresql+asyncpg://", "postgresql+psycopg2://")
engine = create_engine(DATABASE_URL, echo=False)
database = SQLDatabase(engine)
llm = MistralLLM()
db_chain = SQLDatabaseChain.from_llm(llm, database, verbose=False)

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Chat endpoint that processes messages using NL-to-SQL or Mistral fallback
    
    Args:
        request: ChatRequest containing client_id and message
    
    Returns:
        ChatResponse with the AI-generated response and optional SQL
    """
    try:
        logger.info(f"Processing chat request for client {request.client_id}")
        
        text = request.message.strip()
        sql: Optional[str] = None

        # 1) DB-intent detection - check if this looks like a database query
        if re.match(r"^(list|show|what|give|find|search|how many|count|get|fetch|display)\b.*", text, re.I):
            try:
                logger.info("Attempting to process as database query")
                
                # Generate and execute SQL using LangChain
                sql_result = await run_in_threadpool(db_chain.run, text)
                response = str(sql_result)
                sql = "Database query executed successfully"  # Simplified SQL tracking
                logger.info("Successfully processed database query")
                
            except Exception as e:
                logger.error(f"SQL chain failed, falling back to Mistral: {e}")
                response = query_mistral(text)
                sql = None
        else:
            # General AI fallback for non-database queries
            logger.info("Processing as general chat query")
            response = query_mistral(text)

        logger.info(f"Successfully processed chat request for client {request.client_id}")

        return ChatResponse(
            client_id=request.client_id,
            response=response,
            sql=sql
        )

    except Exception as e:
        logger.error(f"Error processing chat request: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to process chat request"
        ) 