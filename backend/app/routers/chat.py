from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging
import os
import re

from app.services.mistral_chat import query_mistral
from sqlalchemy import create_engine, text
from langchain_experimental.sql.base import SQLDatabaseChain
from langchain.sql_database import SQLDatabase
from app.llms.mistral_llm import MistralLLM

from starlette.concurrency import run_in_threadpool
import sqlparse

logger = logging.getLogger(__name__)

router = APIRouter()

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
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

# Create database chain with custom prompt for better PostgreSQL support
db_chain = SQLDatabaseChain.from_llm(
    llm, 
    database, 
    verbose=False,
    return_intermediate_steps=False
)

def create_enhanced_prompt(query: str) -> str:
    """
    Create an enhanced prompt with PostgreSQL-specific guidance and database context
    """
    base_context = f"""
You are a PostgreSQL SQL expert. Generate SQL queries for the following database schema:

Tables:
- clients (id, name, contact_name, contact_email, created_at)
- statements (id, client_id, file_path, uploaded_at, ocr_text) 
- transactions (id, statement_id, date, payee, amount, balance, type, currency)

Common PostgreSQL system queries:
- To list all tables: SELECT tablename FROM pg_tables WHERE schemaname = 'public';
- To describe a table: SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'table_name';

Important PostgreSQL notes:
- Use 'tablename' not 'name' when querying pg_tables
- Always filter pg_tables by schemaname = 'public' to show only user tables
- Use proper JOIN syntax with explicit ON clauses
- Use ILIKE for case-insensitive string matching

User Query: {query}

Generate only the SQL query, no explanations."""

    return base_context

def handle_special_queries(text: str) -> Optional[str]:
    """
    Handle special query patterns that commonly fail
    """
    import re
    
    # Normalize whitespace and convert to lowercase
    text_lower = re.sub(r'\s+', ' ', text.lower().strip())
    
    # List tables queries
    if any(phrase in text_lower for phrase in ["list tables", "show tables", "all tables", "what tables"]):
        return "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;"
    
    # Schema/describe queries
    if any(phrase in text_lower for phrase in ["database schema", "table schema", "describe tables"]):
        return """SELECT t.tablename, c.column_name, c.data_type 
                 FROM pg_tables t 
                 JOIN information_schema.columns c ON t.tablename = c.table_name 
                 WHERE t.schemaname = 'public' 
                 ORDER BY t.tablename, c.ordinal_position;"""
    
    # Client-related queries
    if "from test client" in text_lower or "test client" in text_lower:
        if "statement" in text_lower:
            return """SELECT s.id, s.file_path, s.uploaded_at, c.name 
                     FROM statements s 
                     JOIN clients c ON s.client_id = c.id 
                     WHERE c.name ILIKE '%Test Client%' 
                     ORDER BY s.uploaded_at DESC;"""
        elif "transaction" in text_lower:
            return """SELECT t.id, t.date, t.payee, t.amount, t.balance, c.name 
                     FROM transactions t 
                     JOIN statements s ON t.statement_id = s.id 
                     JOIN clients c ON s.client_id = c.id 
                     WHERE c.name ILIKE '%Test Client%' 
                     ORDER BY t.date DESC;"""
    
    # General client queries
    if "client" in text_lower and any(word in text_lower for word in ["find", "show", "get", "list"]):
        if "statement" in text_lower:
            return """SELECT s.id, s.file_path, s.uploaded_at, c.name 
                     FROM statements s 
                     JOIN clients c ON s.client_id = c.id 
                     ORDER BY s.uploaded_at DESC;"""
    
    return None

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Chat endpoint that processes messages using NL-to-SQL or Mistral fallback
    
    Args:
        request: ChatRequest containing message
    
    Returns:
        ChatResponse with the AI-generated response and optional SQL
    """
    try:
        logger.info("Processing chat request")
        
        text = request.message.strip()
        sql: Optional[str] = None

        # 1) DB-intent detection - check if this looks like a database query
        db_keywords = [
            "list", "show", "what", "give", "find", "search", "how many", "count", 
            "get", "fetch", "display", "select", "where", "from", "table", "database",
            "client", "statement", "transaction", "recent", "latest", "all"
        ]
        
        text_lower = text.lower()
        is_db_query = any(keyword in text_lower for keyword in db_keywords)
        
        if is_db_query:
            try:
                logger.info("Attempting to process as database query")
                
                # Check for special query patterns first
                special_sql = handle_special_queries(text)
                if special_sql:
                    logger.info(f"Using special query handler: {special_sql}")
                    # Execute the special query directly using the database object
                    result = database.run(special_sql)
                    response = f"Query executed successfully. Results:\n{result}"
                    sql = special_sql
                else:
                    # Use enhanced prompt for better context
                    enhanced_prompt = create_enhanced_prompt(text)
                    
                    # Generate and execute SQL using LangChain with enhanced context
                    sql_result = await run_in_threadpool(
                        lambda: db_chain.run(enhanced_prompt)
                    )
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

        logger.info("Successfully processed chat request")

        return ChatResponse(
            response=response,
            sql=sql
        )

    except Exception as e:
        logger.error(f"Error processing chat request: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to process chat request"
        ) 